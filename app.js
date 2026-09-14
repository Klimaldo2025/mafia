// ===== Турнир «Спортивная мафия» — общая логика =====
const ROLES = {
  mafia:    {emoji:'🎭', name:'Мафия',  team:'black'},
  don:      {emoji:'👑', name:'Дон',    team:'black'},
  sheriff:  {emoji:'🎯', name:'Шериф',  team:'red'},
  civilian: {emoji:'🏘️', name:'Мирный', team:'red'},
};
const NOMINATIONS = [
  ['mafia','Лучшая мафия'], ['don','Лучший дон'],
  ['sheriff','Лучший шериф'], ['civilian','Лучший мирный'],
];

// Фолы за игру: 0–2 = 0, 3 = −0.5, 4+ = −1
function foulPenalty(f){ f = f||0; if(f<=2) return 0; if(f===3) return -0.5; return -1; }

// Победа за чёрных = 4, победа за красных = 3, поражение = 1
function entryPoints(r){
  const team = ROLES[r.role].team;
  const base = (r.outcome==='win') ? (team==='black' ? 4 : 3) : 1;
  return base + foulPenalty(r.fouls) + (r.extra||0);
}

function fmt(n){ return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/,''); }
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function uid(){ return Math.random().toString(36).slice(2,10); }

// Рейтинг в роли = ср. очки + 0.5×ср. доп. баллы + 0.1×игры − 0.2×ср. фолы
// (доп. баллы и фолы считаются ТОЛЬКО в играх за эту роль)
function roleRating(entries){
  const n = entries.length;
  if(!n) return null;
  const pts   = entries.reduce((a,e)=>a+entryPoints(e),0)/n;
  const extra = entries.reduce((a,e)=>a+(e.extra||0),0)/n;
  const fouls = entries.reduce((a,e)=>a+(e.fouls||0),0)/n;
  const wins  = entries.filter(e=>e.outcome==='win').length;
  return { rating: pts + 0.5*extra + 0.1*n - 0.2*fouls,
           games:n, wins, winrate: Math.round(100*wins/n), avg_extra:extra, avg_fouls:fouls };
}

function nominations(data){
  const out = {};
  for(const [role,title] of NOMINATIONS){
    let best = null, bestStats = null;
    for(const p of data.players){
      const st = roleRating(data.results.filter(r=>r.player===p && r.role===role));
      if(st && (!bestStats || st.rating > bestStats.rating)){ best = p; bestStats = st; }
    }
    out[role] = {title, best, stats: bestStats};
  }
  return out;
}

function specialNominations(data){
  const g = p => data.results.filter(r=>r.player===p);
  const ag={}, aw={}, ax={};
  data.players.forEach(p=>{
    const e = g(p);
    ag[p]=e.length; aw[p]=e.filter(x=>x.outcome==='win').length;
    ax[p]=e.reduce((a,x)=>a+(x.extra||0),0);
  });
  function top(d, minV){
    let m = null;
    for(const p of data.players){ const v=d[p]; if(v>=minV && (m===null || v>m)) m=v; }
    if(m===null) return [null,0];
    const tops = data.players.filter(p=>d[p]===m).sort((a,b)=> aw[b]-aw[a] || a.localeCompare(b,'ru'));
    return [tops[0], m];
  }
  const [activist, agv] = top(ag, 1);
  const [champion, awv] = top(aw, 1);
  const [leader,   axv] = top(ax, 0.5);
  let det=null, detWr=null, detG=0;
  for(const p of data.players){
    const sh = g(p).filter(r=>r.role==='sheriff');
    if(sh.length>=2){
      const wr = sh.filter(r=>r.outcome==='win').length/sh.length;
      if(detWr===null || wr>detWr){ det=p; detWr=wr; detG=sh.length; }
    }
  }
  return [
    {emoji:'🚀', title:'Активист',           best:activist, stat: activist ? agv+' игр' : ''},
    {emoji:'🏆', title:'Чемпион',            best:champion, stat: champion ? awv+' побед' : ''},
    {emoji:'💎', title:'Лидер',              best:leader,   stat: leader   ? fmt(axv)+' доп. баллов' : ''},
    {emoji:'🕵️', title:'Лучший следователь', best:det,      stat: det      ? Math.round(detWr*100)+'% побед за '+detG+' игр шерифом' : ''},
  ];
}

// ---- данные в ссылке (base64url) ----
function encodeData(data){
  return btoa(unescape(encodeURIComponent(JSON.stringify(data))))
    .replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
function decodeData(s){
  s = s.replace(/-/g,'+').replace(/_/g,'/');
  while(s.length % 4) s += '=';
  return JSON.parse(decodeURIComponent(escape(atob(s))));
}

function freshData(){ return {pass:'mafia', players:[], rounds:[], results:[], updated:null}; }

// ---- рендер таблицы ----
function roleCell(r){
  const R = ROLES[r.role];
  const pts = entryPoints(r);
  const extra = r.extra ? ' +'+fmt(r.extra)+' доп.' : '';
  const foul  = r.fouls ? ' ⚠️'+r.fouls+' ф.' : '';
  const out   = r.outcome==='win' ? '🏆' : '💀';
  return `<span class="tag ${R.team}">${R.emoji} ${R.name}</span><br>` +
         `<span class="pts">${fmt(pts)}<small>${out} ${r.outcome==='win'?'победа':'поражение'}${foul}${extra}</small></span>`;
}

function renderStandings(data){
  const totals = {};
  data.players.forEach(p=> totals[p] = data.results.filter(r=>r.player===p).reduce((a,r)=>a+entryPoints(r),0));
  const order = [...data.players].sort((a,b)=> totals[b]-totals[a] || a.localeCompare(b,'ru'));
  const medals = ['🥇','🥈','🥉'];
  let h = `<div class="card"><h2>📊 Турнирная таблица</h2><table><thead><tr><th>#</th><th>Игрок</th>`;
  data.rounds.forEach(r=> h += `<th>${esc(r.name)}</th>`);
  h += `<th>Очки</th></tr></thead><tbody>`;
  if(!order.length) h += `<tr><td colspan="20" class="hint">Игроков пока нет — ведущий скоро всё настроит 🎭</td></tr>`;
  order.forEach((p,i)=>{
    h += `<tr><td class="medal">${medals[i]||i+1}</td><td><b>${esc(p)}</b></td>`;
    data.rounds.forEach(rnd=>{
      const res = data.results.find(r=>r.player===p && r.round_id===rnd.id);
      h += res ? `<td>${roleCell(res)}</td>` : `<td class="hint">—</td>`;
    });
    h += `<td class="total">${fmt(totals[p])}</td></tr>`;
  });
  h += `</tbody></table>`;
  h += `<div class="hint">Раундов: ${data.rounds.length} · Игроков: ${order.length}` +
       (data.updated ? ` · Обновлено: ${new Date(data.updated).toLocaleString('ru-RU')}` : '') + `</div></div>`;

  // Ролевые номинации
  const noms = nominations(data);
  const trophies = {mafia:'🎭', don:'👑', sheriff:'🎯', civilian:'🏘️'};
  h += `<div class="card"><h2>🏅 Номинации</h2><div class="nom-grid">`;
  for(const [role, nom] of Object.entries(noms)){
    h += `<div class="nom"><div class="trophy">${trophies[role]}</div><div class="title">${nom.title}</div>`;
    if(nom.best){
      const st = nom.stats;
      h += `<div class="name">${esc(nom.best)}</div>` +
           `<div class="stats">Игр в роли: ${st.games} · Побед: ${st.winrate}%<br>` +
           `Ср. доп. баллы: ${fmt(st.avg_extra)} · Ср. фолы: ${fmt(st.avg_fouls)}<br>` +
           `Рейтинг: <b style="color:#e94560">${fmt(st.rating)}</b></div>`;
    } else {
      h += `<div class="empty">Пока никто<br>не играл в эту роль</div>`;
    }
    h += `</div>`;
  }
  h += `</div><div class="hint">Рейтинг = средние очки + 0.5×ср. доп. баллы + 0.1×игры − 0.2×ср. фолы (доп. баллы и фолы считаются только в играх за эту роль)</div></div>`;

  // Специальные номинации
  h += `<div class="card"><h2>🌟 Специальные номинации</h2><div class="nom-grid">`;
  for(const nom of specialNominations(data)){
    h += `<div class="nom"><div class="trophy">${nom.emoji}</div><div class="title">${nom.title}</div>`;
    h += nom.best ? `<div class="name">${esc(nom.best)}</div><div class="stats">${nom.stat}</div>`
                  : `<div class="empty">Пока нет кандидатов</div>`;
    h += `</div>`;
  }
  h += `</div></div>`;
  return h;
}
