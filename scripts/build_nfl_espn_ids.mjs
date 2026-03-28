import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const appPath = path.join(root, 'src', 'App.jsx');
const outPath = path.join(root, 'public', 'nfl_espn_ids.json');

const source = fs.readFileSync(appPath, 'utf8');
const playerIdsStart = source.indexOf('var PLAYER_IDS={');
const nflStart = source.indexOf('  NFL:{', playerIdsStart);
const nbaStart = source.indexOf('  NBA:{', nflStart);

if (playerIdsStart < 0 || nflStart < 0 || nbaStart < 0) {
  throw new Error('Could not find PLAYER_IDS.NFL in src/App.jsx');
}

const body = source.slice(nflStart + '  NFL:{'.length, nbaStart);
const map = {};

for (const line of body.split(/\r?\n/)) {
  const match = line.match(/^\s*"([^"]+)":\s*([0-9]+),?\s*$/);
  if (!match) continue;
  map[match[1]] = Number(match[2]);
}

fs.writeFileSync(outPath, JSON.stringify(map, null, 2) + '\n');
console.log(`Wrote ${Object.keys(map).length} NFL ESPN ids to ${outPath}`);
