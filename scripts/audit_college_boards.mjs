import fs from "fs";

function hashSeedParts(...parts){
  let h=2166136261>>>0;
  for(const partRaw of parts){
    const part=String(partRaw===undefined?"":partRaw);
    for(let i=0;i<part.length;i++){
      h^=part.charCodeAt(i);
      h=Math.imul(h,16777619)>>>0;
    }
    h=Math.imul(h^0x9e3779b9,16777619)>>>0;
  }
  return h>>>0;
}

function getCollegeMode(seed,sport,catId,collegeCount){
  if((sport!=="NFL"&&sport!=="NBA")||!collegeCount) return "none";
  if(sport==="NBA"){
    const nbaRoll=hashSeedParts("college",sport,catId,seed)%160;
    if(collegeCount>=5&&nbaRoll<1) return "all";
    if(nbaRoll<8) return "single";
    return "none";
  }
  const roll=hashSeedParts("college",sport,catId,seed)%80;
  if(collegeCount>=5&&roll<1) return "all";
  if(roll<10) return "single";
  return "none";
}

function isUsableCollegeName(name){
  const v=String(name||"").trim();
  return !!v && !/unknown/i.test(v);
}

function getTopCollegeNames(players,limit=25){
  const counts=new Map();
  for(const p of players){
    const col=String((p&&p.col)||"").trim();
    if(!isUsableCollegeName(col)) continue;
    counts.set(col,(counts.get(col)||0)+1);
  }
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,limit).map(([name])=>name);
}

function load(name){
  return JSON.parse(fs.readFileSync(`C:/Users/kayle/Downloads/statpad-deploy/statpad-deploy/public/${name}`,"utf8"));
}

function topCollegeCoverage(players,categories,sport){
  const colleges=getTopCollegeNames(players,25);
  const byCollege=new Map(colleges.map(c=>[c,players.filter(p=>String(p.col||"").trim()===c)]));
  return categories.map(cat=>{
    const viable=colleges.filter(col=>{
      const matches=(byCollege.get(col)||[]).filter(p=>{
        if(sport==="NFL"&&cat.pos) return cat.pos.includes(p.pos);
        if(sport==="NBA"&&cat.pos) return p.pos===cat.pos;
        return true;
      });
      return matches.length>0;
    });
    return {catId:cat.id,viableColleges:viable.length};
  });
}

const nflCats=[
  {id:"scrimmage",pos:["RB","WR","TE"]},
  {id:"rush",pos:["RB","QB"]},
  {id:"rec",pos:["WR","RB","TE"]},
  {id:"pass",pos:["QB"]},
  {id:"passTd",pos:["QB"]},
  {id:"rushTd",pos:["RB","QB"]},
  {id:"recTd",pos:["WR","RB","TE"]},
  {id:"rushRecTd",pos:["RB","WR","TE"]},
  {id:"fpts",pos:["RB","WR","TE","QB"]},
  {id:"tackles",pos:["CB","S","LB","DE","DT"]},
  {id:"int",pos:["CB","S"]},
  {id:"fgMade",pos:["K"]},
  {id:"fgMissed",pos:["K"]},
  {id:"pointsScored",pos:["RB","WR","TE","QB","K"]},
  {id:"sbwins"}
];

const nbaCats=[
  {id:"pts"},{id:"reb"},{id:"ast"},{id:"stl"},{id:"blk"},{id:"fg3m"},
  {id:"totReb"},{id:"totPts"},{id:"totAst"},{id:"totStl"},{id:"totBlk"},
  {id:"tot3pm"},{id:"totFga"},{id:"totFta"},{id:"totTov"},{id:"totFouls"},
  {id:"ftpct"},{id:"ftpct100"},{id:"ringwins"}
];

const nfl=load("nfl_players.json");
const nba=load("nba_players.json");

console.log("NFL top 25 colleges:",getTopCollegeNames(nfl,25));
console.log("NBA top 25 colleges:",getTopCollegeNames(nba,25));
console.log("NFL category college coverage:",topCollegeCoverage(nfl,nflCats,"NFL"));
console.log("NBA category college coverage:",topCollegeCoverage(nba,nbaCats,"NBA"));

const samples=100000;
for(const sport of ["NFL","NBA"]){
  for(const cat of (sport==="NFL"?nflCats:nbaCats)){
    let none=0,single=0,all=0;
    const collegeCount=25;
    for(let seed=1;seed<=samples;seed++){
      const mode=getCollegeMode(seed,sport,cat.id,collegeCount);
      if(mode==="all") all++;
      else if(mode==="single") single++;
      else none++;
    }
    console.log({sport,catId:cat.id,allPct:(all/samples*100).toFixed(2),singlePct:(single/samples*100).toFixed(2),anyPct:((all+single)/samples*100).toFixed(2)});
  }
}
