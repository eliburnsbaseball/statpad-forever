import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PLAYERS_PATH = path.join(ROOT, "public", "mlb_players.json");
const OUT_PATH = path.join(ROOT, "scripts", "mlb_bref_sources.json");
const RAW_DIR = path.join(ROOT, "scripts", "mlb_bref_raw");

function rankHeadshot(url) {
  const u = String(url || "").toLowerCase();
  if (u.includes("_mlbam.")) return 0;
  if (u.includes("_br.")) return 1;
  if (u.includes("_sabr.")) return 2;
  if (u.includes("_davis.")) return 3;
  if (u.includes("_milb.")) return 4;
  return 9;
}

function parseArgs(players) {
  const args = process.argv.slice(2).filter(Boolean);
  if (!args.length) return [];
  const byId = new Map(players.map((p) => [String(p.id || ""), p]));
  const byName = new Map(players.map((p) => [String(p.nm || "").toLowerCase(), p]));
  const out = [];
  for (const raw of args) {
    const key = raw.toLowerCase();
    const player = byId.get(raw) || byName.get(key);
    if (player) out.push(player);
  }
  return out;
}

async function getHeadshots(browser, player) {
  const pid = String(player.id || "");
  if (!/^[a-z]/i.test(pid)) return null;
  const first = pid[0].toLowerCase();
  const url = `https://www.baseball-reference.com/players/${first}/${pid}.shtml`;
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    viewport: { width: 1440, height: 1600 },
  });
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(2500);
    const urls = await page.locator("img").evaluateAll((nodes) =>
      nodes.map((n) => n.currentSrc || n.src).filter(Boolean)
    );
    const headshots = urls
      .filter((u) => u.includes("/images/headshots/"))
      .sort((a, b) => rankHeadshot(a) - rankHeadshot(b));
    if (!headshots.length) return null;
    return {
      id: pid,
      nm: player.nm,
      page: url,
      image: headshots[0],
      options: headshots
    };
  } finally {
    await page.close().catch(() => {});
  }
}

async function downloadImage(browser, url, outPath) {
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  });
  try {
    const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (!response || !response.ok()) throw new Error(`Failed to fetch ${url}`);
    const body = await response.body();
    await fs.mkdir(path.dirname(outPath), { recursive: true });
    await fs.writeFile(outPath, body);
  } finally {
    await page.close().catch(() => {});
  }
}

async function main() {
  const players = JSON.parse(await fs.readFile(PLAYERS_PATH, "utf8"));
  const targets = parseArgs(players);
  if (!targets.length) {
    console.error("Usage: node scripts/build_mlb_bref_sources.mjs <bref_id|player name> [...]");
    process.exit(1);
  }
  const browser = await chromium.launch({ headless: true });
  try {
    const out = [];
    for (const player of targets) {
      const result = await getHeadshots(browser, player);
      if (result) {
        const rawPath = path.join(RAW_DIR, `${result.id}.jpg`);
        await downloadImage(browser, result.image, rawPath);
        result.raw = path.relative(ROOT, rawPath).replace(/\\/g, "/");
        out.push(result);
      }
      else console.error(`No BRef headshot found for ${player.nm} (${player.id})`);
    }
    await fs.writeFile(OUT_PATH, JSON.stringify(out, null, 2));
    console.log(`Wrote ${OUT_PATH}`);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
