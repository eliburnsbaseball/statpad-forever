import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = process.cwd();
const appPath = path.join(root, "src", "App.jsx");
const publicDir = path.join(root, "public");
const source = fs.readFileSync(appPath, "utf8");
const lines = source.split(/\r?\n/);

const sections = [
  { sport: "NFL", start: 143, end: 1258, output: "nfl_players.json", global: "NFL_PLAYERS" },
  { sport: "NBA", start: 1394, end: 1703, output: "nba_players.json", global: "NBA_PLAYERS" },
  { sport: "MLB", start: 1704, end: 2321, output: "mlb_players.json", global: "MLB_PLAYERS" },
  { sport: "NHL", start: 2322, end: 2758, output: "nhl_players.json", global: "NHL_PLAYERS" },
];

for (const section of sections) {
  const code = lines.slice(section.start, section.end).join("\n");
  const context = { console, Math, Date, JSON };
  vm.createContext(context);
  vm.runInContext(code, context, { filename: `${section.sport}.vm.js` });
  const players = context[section.global];
  if (!Array.isArray(players)) {
    throw new Error(`Failed to export ${section.sport}: ${section.global} was not created`);
  }
  fs.writeFileSync(
    path.join(publicDir, section.output),
    JSON.stringify(players, null, 2),
    "utf8",
  );
  console.log(`Wrote ${players.length} ${section.sport} players to ${section.output}`);
}
