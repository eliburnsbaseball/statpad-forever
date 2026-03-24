const fs = require('fs');
const path = require('path');

const OUT_PATH = path.resolve(__dirname, '..', 'public', 'nfl_headshots.json');
const PLAYERS_PATH = path.resolve(__dirname, '..', 'public', 'nfl_players.json');

function norm(v) {
  return String(v || '')
    .toLowerCase()
    .replace(/['.`]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

async function fetchText(url) {
  const res = await fetch(url, {
    headers: {
      'user-agent': 'Mozilla/5.0',
      'accept': '*/*',
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return await res.text();
}

function spanScore(player, ext) {
  const ps = num(player.start);
  const pe = num(player.end);
  const es = num(ext.start);
  const ee = num(ext.end);
  if (ps == null || pe == null || es == null || ee == null) return -999;
  const overlap = Math.max(0, Math.min(pe, ee) - Math.max(ps, es) + 1);
  const penalty = Math.abs(ps - es) + Math.abs(pe - ee);
  return overlap * 100 - penalty;
}

async function main() {
  const html = await fetchText('https://statpadgame.com/NFL');
  const assetMatch = html.match(/<script type="module" crossorigin src="([^"]+index-[^"]+\.js)"/i);
  if (!assetMatch) throw new Error('Could not find Statpad JS bundle');
  const bundleUrl = new URL(assetMatch[1], 'https://statpadgame.com/').toString();
  const js = await fetchText(bundleUrl);

  const rowRegex = /([A-Za-z0-9]{8}),([^,\n]+),([^,\n]+),(https:\/\/a\.espncdn\.com\/combiner\/i\?img=\/i\/headshots\/nfl\/players\/full\/\d+\.png&w=350&h=254),((?:19|20)\d{2}),([A-Z0-9]{2,3})/g;
  const extracted = new Map();
  let m;
  while ((m = rowRegex.exec(js))) {
    const first = m[2];
    const last = m[3];
    const fullName = `${first} ${last}`.trim();
    const year = Number(m[5]);
    const url = m[4];
    const key = norm(fullName);
    let item = extracted.get(key);
    if (!item) {
      item = { fullName, url, start: year, end: year };
      extracted.set(key, item);
    } else {
      item.start = Math.min(item.start, year);
      item.end = Math.max(item.end, year);
      item.url = url;
    }
  }

  const players = JSON.parse(fs.readFileSync(PLAYERS_PATH, 'utf8'));
  const existing = JSON.parse(fs.readFileSync(OUT_PATH, 'utf8'));

  let matched = 0;
  for (const player of players) {
    const nameKey = norm(player.nm);
    const candidate = extracted.get(nameKey);
    if (!candidate) continue;
    const siblings = players.filter((p) => norm(p.nm) === nameKey);
    let best = siblings[0];
    let bestScore = spanScore(best, candidate);
    for (const sibling of siblings.slice(1)) {
      const score = spanScore(sibling, candidate);
      if (score > bestScore) {
        best = sibling;
        bestScore = score;
      }
    }
    if (best.id === player.id && bestScore >= 0) {
      existing[player.id] = candidate.url;
      matched += 1;
    }
  }

  fs.writeFileSync(OUT_PATH, JSON.stringify(existing));
  console.log({ extracted: extracted.size, matched });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
