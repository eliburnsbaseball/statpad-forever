const fs = require('fs');
const path = require('path');

const currentPath = path.resolve(__dirname, '..', 'public', 'nfl_players.json');
const legacyPath = 'C:/Users/kayle/OneDrive/Documents/New project/statpad-deploy-latest/public/nfl_players.json';

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function writeJson(p, data) {
  fs.writeFileSync(p, JSON.stringify(data));
}

function normName(v) {
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

function spanOverlap(a, b) {
  const as = num(a && a.start);
  const ae = num(a && a.end);
  const bs = num(b && b.start);
  const be = num(b && b.end);
  if (as == null || ae == null || bs == null || be == null) return -1;
  return Math.max(0, Math.min(ae, be) - Math.max(as, bs) + 1);
}

function buildKey(player) {
  return [
    normName(player.nm),
    player.pos || '',
    num(player.start) || '',
    num(player.end) || '',
  ].join('|');
}

function mergeSeasonObjects(baseSeason, legacySeason) {
  const merged = { ...(legacySeason || {}), ...(baseSeason || {}) };
  for (const [k, v] of Object.entries(legacySeason || {})) {
    if (merged[k] == null || merged[k] === '') merged[k] = v;
  }
  return merged;
}

function mergePlayer(basePlayer, legacyPlayer) {
  const merged = { ...(legacyPlayer || {}), ...(basePlayer || {}) };
  const seasonMap = new Map();
  (legacyPlayer.seasons || []).forEach((s) => {
    const y = num(s && s.year);
    if (y != null) seasonMap.set(y, { ...s });
  });
  (basePlayer.seasons || []).forEach((s) => {
    const y = num(s && s.year);
    if (y == null) return;
    seasonMap.set(y, mergeSeasonObjects(s, seasonMap.get(y)));
  });
  merged.seasons = Array.from(seasonMap.values()).sort((a, b) => num(a.year) - num(b.year));
  const years = merged.seasons.map((s) => num(s.year)).filter((y) => y != null);
  merged.start = years.length ? Math.min(...years) : num(merged.start);
  merged.end = years.length ? Math.max(...years) : num(merged.end);
  if (!merged.id) {
    merged.id = `hist-${normName(merged.nm).replace(/[^a-z0-9]+/g, '-')}-${merged.start || 'na'}-${merged.end || 'na'}`;
  }
  if (!merged.nmL && merged.nm) merged.nmL = normName(merged.nm);
  if (merged.isUndrafted === false) merged.isUndrafted = 0;
  if (merged.isUndrafted === true) merged.isUndrafted = 1;
  return merged;
}

const current = readJson(currentPath);
const legacy = readJson(legacyPath);

const groupedCurrent = new Map();
for (const player of current) {
  const key = normName(player.nm);
  if (!groupedCurrent.has(key)) groupedCurrent.set(key, []);
  groupedCurrent.get(key).push(player);
}

const usedCurrent = new Set();
const mergedPlayers = [];

for (const legacyPlayer of legacy) {
  const candidates = groupedCurrent.get(normName(legacyPlayer.nm)) || [];
  let best = null;
  let bestScore = -Infinity;
  for (const candidate of candidates) {
    if (usedCurrent.has(candidate)) continue;
    let score = spanOverlap(candidate, legacyPlayer);
    if ((candidate.pos || '') === (legacyPlayer.pos || '')) score += 10;
    if ((candidate.col || '') && (legacyPlayer.col || '') && candidate.col === legacyPlayer.col) score += 20;
    if ((candidate.colConf || '') && (legacyPlayer.colConf || '') && candidate.colConf === legacyPlayer.colConf) score += 5;
    if (score > bestScore) {
      bestScore = score;
      best = candidate;
    }
  }
  if (best && bestScore >= 0) {
    usedCurrent.add(best);
    mergedPlayers.push(mergePlayer(best, legacyPlayer));
  } else {
    mergedPlayers.push(mergePlayer({}, legacyPlayer));
  }
}

for (const player of current) {
  if (!usedCurrent.has(player)) {
    mergedPlayers.push(mergePlayer(player, {}));
  }
}

const deduped = new Map();
for (const player of mergedPlayers) {
  const key = buildKey(player);
  if (!deduped.has(key)) deduped.set(key, player);
  else deduped.set(key, mergePlayer(player, deduped.get(key)));
}

const finalPlayers = Array.from(deduped.values()).sort((a, b) => {
  const na = normName(a.nm);
  const nb = normName(b.nm);
  if (na < nb) return -1;
  if (na > nb) return 1;
  return (num(a.start) || 0) - (num(b.start) || 0);
});

writeJson(currentPath, finalPlayers);

const years = [];
for (const player of finalPlayers) {
  (player.seasons || []).forEach((s) => {
    const y = num(s && s.year);
    if (y != null) years.push(y);
  });
}
years.sort((a, b) => a - b);
console.log({
  players: finalPlayers.length,
  min: years[0],
  max: years[years.length - 1],
});
