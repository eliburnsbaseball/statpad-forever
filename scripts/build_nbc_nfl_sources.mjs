import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PLAYERS_PATH = path.join(ROOT, "public", "nfl_players.json");
const OUT_PATH = path.join(ROOT, "scripts", "nbc_nfl_sources.json");

function normalizeName(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function nameSlug(value) {
  return normalizeName(value).replace(/ /g, "-");
}

async function loadTargets() {
  const args = process.argv.slice(2).filter(Boolean);
  if (!args.length) return [];
  const players = JSON.parse(await fs.readFile(PLAYERS_PATH, "utf8"));
  const byId = new Map(players.map((p) => [String(p.id || ""), p]));
  const byName = new Map(players.map((p) => [normalizeName(p.nm), p]));
  return args.map((raw) => {
    const key = normalizeName(raw);
    const found = byId.get(raw) || byName.get(key);
    if (found) return { name: found.nm };
    return { name: raw };
  });
}

async function loadExisting() {
  try {
    return JSON.parse(await fs.readFile(OUT_PATH, "utf8"));
  } catch {
    return [];
  }
}

function isPlayerLink(href) {
  return /\/nfl\/[^/]+\/[0-9a-f-]{20,}$/i.test(String(href || ""));
}

function scoreLink(targetName, href, text) {
  const targetNorm = normalizeName(targetName);
  const textNorm = normalizeName(text);
  const hrefNorm = String(href || "").toLowerCase();
  let score = 0;
  if (textNorm === targetNorm) score += 100;
  else if (textNorm && (textNorm.includes(targetNorm) || targetNorm.includes(textNorm))) score += 40;
  if (hrefNorm.includes("/nfl/" + nameSlug(targetName) + "/")) score += 60;
  if (isPlayerLink(href)) score += 20;
  return score;
}

async function findPlayerPage(browser, targetName) {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1600 },
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  });
  try {
    await page.goto("https://www.nbcsports.com/search?q=" + encodeURIComponent(targetName), {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await page.waitForTimeout(3500);
    const links = await page.evaluate(() =>
      Array.from(document.querySelectorAll("a[href]")).map((a) => ({
        href: a.href,
        text: (a.textContent || "").trim(),
      }))
    );
    const filtered = links
      .filter((item) => isPlayerLink(item.href))
      .map((item) => ({ ...item, score: 0 }));
    filtered.forEach((item) => {
      item.score = scoreLink(targetName, item.href, item.text);
    });
    filtered.sort((a, b) => b.score - a.score);
    const best = filtered[0];
    return best && best.score >= 80 ? best.href : null;
  } finally {
    await page.close().catch(() => {});
  }
}

async function main() {
  const targets = await loadTargets();
  if (!targets.length) {
    console.error("Usage: node scripts/build_nbc_nfl_sources.mjs <player name|player id> [...]");
    process.exit(1);
  }
  const existing = await loadExisting();
  const merged = new Map(existing.map((item) => [normalizeName(item.name), item]));
  const browser = await chromium.launch({ headless: true });
  try {
    for (const target of targets) {
      const name = target.name;
      const key = normalizeName(name);
      const foundUrl = await findPlayerPage(browser, name);
      if (!foundUrl) {
        console.error("No NBC player page found for " + name);
        continue;
      }
      merged.set(key, { name, url: foundUrl });
      console.log(`Matched ${name} -> ${foundUrl}`);
    }
  } finally {
    await browser.close();
  }
  const out = Array.from(merged.values()).sort((a, b) => a.name.localeCompare(b.name));
  await fs.writeFile(OUT_PATH, JSON.stringify(out, null, 2));
  console.log(`Wrote ${OUT_PATH}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
