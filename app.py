#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏆 Сервер турнира «Спортивная мафия» — ШКОЛЬНЫЙ КЛУБ
Запуск локально:  python app.py
Деплой: GitHub → Railway (см. README.md)
Требуется только Python 3, библиотеки НЕ нужны!
"""
import json, os, secrets, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get('PORT', 8080))
DATA_FILE = os.environ.get('DATA_FILE', 'mafia_data.json')
LOCK = threading.Lock()

# ------------------- РОЛИ -------------------
# роль: (эмодзи, название, команда)
ROLES = {
    'mafia':    ('🎭', 'Мафия',   'black'),
    'don':      ('👑', 'Дон',     'black'),
    'sheriff':  ('🎯', 'Шериф',   'red'),
    'civilian': ('🏘️', 'Мирный', 'red'),
}
NOMINATIONS = [('mafia', 'Лучшая мафия'), ('don', 'Лучший дон'),
               ('sheriff', 'Лучший шериф'), ('civilian', 'Лучший мирный')]

# ------------------- ДАННЫЕ -------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {"pass": "mafia", "players": [], "rounds": [], "results": []}

def save_data(d):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)

# ------------------- ОЧКИ ЗА ИГРУ -------------------
# Победа за чёрных (мафия/дон) = 4, победа за красных (шериф/мирный) = 3, поражение = 1
# Фолы за игру: 0–2 фола = 0, 3 фола = −0.5, 4 и больше = −1
# Доп. баллы — произвольные, необязательные
def foul_penalty(f):
    if f <= 2: return 0
    if f == 3: return -0.5
    return -1

def entry_points(r):
    team = ROLES[r['role']][2]
    base = 4 if (team == 'black' and r['outcome'] == 'win') else \
           3 if (team == 'red' and r['outcome'] == 'win') else 1
    return base + foul_penalty(r.get('fouls', 0)) + (r.get('extra', 0) or 0)

def fmt(n):
    return str(int(n)) if float(n).is_integer() else f"{n:.2f}".rstrip('0').rstrip('.')

# ------------------- АЛГОРИТМ НОМИНАЦИЙ -------------------
# Рейтинг в роли = средние очки за игру
#   + 0.5 × средние доп. баллы   (главный «сигнал мастерства» от ведущего,
#                                 работает даже при поражениях)
#   + 0.1 × количество игр в роли (небольшой бонус за активность)
#   − 0.2 × средние фолы         (фолы — на втором плане)
def role_rating(entries):
    n = len(entries)
    if n == 0: return None
    pts = sum(entry_points(e) for e in entries) / n
    extra = sum(e.get('extra', 0) or 0 for e in entries) / n
    fouls = sum(e.get('fouls', 0) or 0 for e in entries) / n
    wins = sum(1 for e in entries if e['outcome'] == 'win')
    return {"rating": pts + 0.5 * extra + 0.1 * n - 0.2 * fouls,
            "games": n, "wins": wins,
            "winrate": round(100 * wins / n),
            "avg_extra": extra, "avg_fouls": fouls, "avg_pts": pts}

def nominations(data):
    result = {}
    for role, title in NOMINATIONS:
        best, best_stats = None, None
        for p in data['players']:
            entries = [r for r in data['results'] if r['player'] == p and r['role'] == role]
            st = role_rating(entries)
            if st and (best_stats is None or st['rating'] > best_stats['rating']):
                best, best_stats = p, st
        result[role] = (title, best, best_stats)
    return result

def special_nominations(data):
    players = data['players']
    def games(p): return [r for r in data['results'] if r['player'] == p]
    ag = {p: len(games(p)) for p in players}
    aw = {p: sum(1 for r in games(p) if r['outcome'] == 'win') for p in players}
    ax = {p: sum(r.get('extra', 0) or 0 for r in games(p)) for p in players}

    def top(d, min_v=1):
        cands = [(d[p], p) for p in players if d[p] >= min_v]
        if not cands: return None, 0
        m = max(v for v, p in cands)
        tops = sorted([p for v, p in cands if v == m], key=lambda p: (-aw[p], p.lower()))
        return tops[0], m

    activist, agv = top(ag)
    champion, awv = top(aw)
    leader, axv = top(ax, 0.5)

    # Лучший следователь: шериф с лучшим % побед (минимум 2 игры за шерифа)
    det, det_wr, det_g = None, None, 0
    for p in players:
        sh = [r for r in games(p) if r['role'] == 'sheriff']
        if len(sh) >= 2:
            wr = sum(1 for r in sh if r['outcome'] == 'win') / len(sh)
            if det_wr is None or wr > det_wr:
                det, det_wr, det_g = p, wr, len(sh)

    det_stat = f'{round(det_wr*100)}% побед за {det_g} игр шерифом' if det else ''
    return [('🚀', 'Активист', activist, f'{agv} игр' if activist else ''),
            ('🏆', 'Чемпион', champion, f'{awv} побед' if champion else ''),
            ('💎', 'Лидер', leader, f'{fmt(axv)} доп. баллов' if leader else ''),
            ('🕵️', 'Лучший следователь', det, det_stat)]

def standings(data):
    table = {p: {} for p in data['players']}
    totals = {p: 0 for p in data['players']}
    for r in data['results']:
        p = r['player']
        if p not in table: continue
        table[p][r['round_id']] = r
        totals[p] += entry_points(r)
    return table, totals

# ------------------- HTML/CSS -------------------
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:linear-gradient(135deg,#141428,#1f1f3a 60%,#2a1a3a);color:#eee;min-height:100vh}
.wrap{max-width:1050px;margin:0 auto;padding:20px 15px 60px}
header{background:rgba(20,20,45,.85);backdrop-filter:blur(8px);padding:16px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;border-bottom:1px solid #3a3a6a;position:sticky;top:0;z-index:5}
h1{font-size:1.25rem;letter-spacing:.5px}
.card{background:rgba(30,30,60,.75);border:1px solid #3a3a6a;border-radius:16px;padding:20px;margin-top:20px;box-shadow:0 8px 30px rgba(0,0,0,.35)}
.card h2{font-size:1.05rem;color:#e94560;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.btn{background:#2a2a55;color:#fff;border:1px solid #4a4a8a;padding:9px 18px;border-radius:10px;cursor:pointer;font-size:.95rem;transition:.15s;text-decoration:none;display:inline-block}
.btn:hover{background:#3a3a75;transform:translateY(-1px)}
.btn.primary{background:linear-gradient(135deg,#e94560,#c73650);border:none;font-weight:600}
.btn.primary:hover{filter:brightness(1.15)}
.btn.small{padding:5px 12px;font-size:.82rem}
.btn.danger{background:#5a1a25;border-color:#8a2a3a}
.btn.danger:hover{background:#7a2230}
input,select{background:#1c1c3d;color:#fff;border:1px solid #4a4a8a;padding:10px 14px;border-radius:10px;font-size:.95rem;width:100%}
input:focus,select:focus{outline:none;border-color:#e94560;box-shadow:0 0 0 3px rgba(233,69,96,.2)}
table{width:100%;border-collapse:collapse}
th,td{padding:11px 8px;text-align:left;border-bottom:1px solid #33335c;font-size:.95rem}
th{color:#e94560;font-size:.82rem;text-transform:uppercase;letter-spacing:1px}
tbody tr:hover{background:rgba(233,69,96,.07)}
tbody tr:nth-child(1) td{background:rgba(255,215,0,.06)}
tbody tr:nth-child(2) td{background:rgba(192,192,192,.05)}
tbody tr:nth-child(3) td{background:rgba(205,127,50,.05)}
.medal{font-size:1.2rem}
.total{color:#e94560;font-weight:700;font-size:1.05rem}
.tag{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.78rem;font-weight:600}
.tag.black{background:#3a1a2a;color:#ff8fa8;border:1px solid #a33}
.tag.red{background:#1a2a4a;color:#9fc5ff;border:1px solid #46a}
.pts{font-weight:700}
.pts small{display:block;font-weight:400;color:#889;font-size:.7rem}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.hint{color:#8aa;font-size:.85rem;margin-top:8px}
.msg{color:#e94560;font-size:.9rem;margin-top:10px;min-height:1.2em}
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px}
label.lbl{display:block;font-size:.8rem;color:#8aa;margin-bottom:5px}
.toggle{display:flex;flex-wrap:wrap;gap:6px}
.toggle button{padding:10px 14px;border:1px solid #4a4a8a;background:#1c1c3d;color:#889;border-radius:10px;cursor:pointer;font-size:.9rem;transition:.15s}
.toggle button.on-mafia,.toggle button.on-don{background:linear-gradient(135deg,#8a2a3a,#5a1a25);color:#fff;border-color:#c73a5a;font-weight:600}
.toggle button.on-sheriff{background:linear-gradient(135deg,#2a3a8a,#1a2a5a);color:#fff;border-color:#3a5ac7;font-weight:600}
.toggle button.on-civilian{background:linear-gradient(135deg,#2a6a3a,#1a4a25);color:#fff;border-color:#3ac75a;font-weight:600}
.preview{background:#14142e;border:1px dashed #4a4a8a;border-radius:10px;padding:14px;text-align:center;font-size:1.05rem;margin-bottom:14px}
.preview b{color:#e94560;font-size:1.3rem}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.chip{background:#1c1c3d;border:1px solid #4a4a8a;border-radius:20px;padding:5px 12px;font-size:.85rem;display:flex;gap:8px;align-items:center}
.chip a{color:#e94560;text-decoration:none;font-weight:700;cursor:pointer}
.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;background:#4caf50;margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(76,175,80,.6)}50%{box-shadow:0 0 0 6px rgba(76,175,80,0)}}
.nom-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.nom{background:#14142e;border:1px solid #3a3a6a;border-radius:14px;padding:16px;text-align:center}
.nom .trophy{font-size:1.8rem}
.nom .title{color:#e94560;font-size:.85rem;text-transform:uppercase;letter-spacing:1px;margin:6px 0}
.nom .name{font-size:1.15rem;font-weight:700;margin-bottom:6px}
.nom .stats{color:#8aa;font-size:.78rem;line-height:1.6}
.nom .empty{color:#556;font-size:.85rem;margin:12px 0}
@media(max-width:640px){th,td{padding:8px 5px;font-size:.82rem}h1{font-size:1rem}}
"""

PAGE_TOP = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style></head><body>
<header><h1><span>🎭🏆</span> Спортивная мафия — Турнир</h1><nav>{nav}</nav></header>
<div class="wrap">
"""

def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def role_cell(r):
    em, name, team = ROLES[r['role']]
    pts = entry_points(r)
    extra = f' +{fmt(r["extra"])} доп.' if r.get('extra') else ''
    foul_txt = f' ⚠️{r["fouls"]} ф.' if r.get('fouls') else ''
    out = '🏆' if r['outcome'] == 'win' else '💀'
    return (f'<span class="tag {team}">{em} {name}</span><br>'
            f'<span class="pts">{fmt(pts)}<small>{out} {"победа" if r["outcome"]=="win" else "поражение"}'
            f'{foul_txt}{extra}</small></span>')

def standings_html(data):
    table, totals = standings(data)
    order = sorted(data['players'], key=lambda p: (-totals[p], p.lower()))
    medals = ['🥇', '🥈', '🥉']
    h = ['<div class="card"><h2>📊 Турнирная таблица</h2><table><thead><tr><th>#</th><th>Игрок</th>']
    for rnd in data['rounds']:
        h.append(f'<th>{esc(rnd["name"])}</th>')
    h.append('<th>Очки</th></tr></thead><tbody>')
    if not order:
        h.append('<tr><td colspan="20" class="hint">Игроков пока нет — ведущий скоро всё настроит 🎭</td></tr>')
    for i, p in enumerate(order):
        h.append(f'<tr><td class="medal">{medals[i] if i < 3 else i+1}</td><td><b>{esc(p)}</b></td>')
        for rnd in data['rounds']:
            r = table[p].get(rnd['id'])
            h.append(f'<td>{role_cell(r)}</td>' if r else '<td class="hint">—</td>')
        h.append(f'<td class="total">{fmt(totals[p])}</td></tr>')
    h.append('</tbody></table>')
    h.append(f'<div class="hint"><span class="pulse"></span>Автообновление каждые 10 сек · Раундов: {len(data["rounds"])} · Игроков: {len(order)}</div></div>')

    # --- Номинации ---
    noms = nominations(data)
    h.append('<div class="card"><h2>🏅 Номинации</h2><div class="nom-grid">')
    trophies = {'mafia': '🎭', 'don': '👑', 'sheriff': '🎯', 'civilian': '🏘️'}
    for role, (title, best, st) in noms.items():
        h.append(f'<div class="nom"><div class="trophy">{trophies[role]}</div><div class="title">{title}</div>')
        if best:
            h.append(f'<div class="name">{esc(best)}</div>'
                     f'<div class="stats">Игр в роли: {st["games"]} · Побед: {st["winrate"]}%<br>'
                     f'Ср. доп. баллы: {fmt(st["avg_extra"])} · Ср. фолы: {fmt(st["avg_fouls"])}<br>'
                     f'Рейтинг: <b style="color:#e94560">{fmt(st["rating"])}</b></div>')
        else:
            h.append('<div class="empty">Пока никто<br>не играл в эту роль</div>')
        h.append('</div>')
    h.append('</div><div class="hint">Рейтинг = средние очки + 0.5×ср. доп. баллы + 0.1×игры − 0.2×ср. фолы (доп. баллы и фолы считаются только в играх за эту роль)</div></div>')

    # --- Специальные номинации ---
    h.append('<div class="card"><h2>🌟 Специальные номинации</h2><div class="nom-grid">')
    for em, title, best, stat in special_nominations(data):
        h.append(f'<div class="nom"><div class="trophy">{em}</div><div class="title">{title}</div>')
        h.append(f'<div class="name">{esc(best)}</div><div class="stats">{stat}</div>' if best
                 else '<div class="empty">Пока нет кандидатов</div>')
        h.append('</div>')
    h.append('</div></div>')
    return ''.join(h)

VIEW_PAGE = PAGE_TOP + """
{standings}
</div>
<script>
async function upd(){{
  try{{ const r = await fetch('/api/standings'); document.getElementById('st').innerHTML = await r.text(); }}catch(e){{}}
}}
setInterval(upd, 10000);
</script>
</body></html>"""

def view_page(data):
    nav = '<a class="btn" href="/admin">🔑 Вход для ведущего</a>'
    return VIEW_PAGE.format(title='Турнир «Спортивная мафия»', css=CSS, nav=nav,
                            standings=f'<div id="st">{standings_html(data)}</div>')

ADMIN_PAGE = PAGE_TOP + """
<div class="card"><h2>➕ Добавить игрока</h2>
<form method="post" action="/add_player" class="row">
<input name="name" placeholder="Имя игрока" required style="flex:1;min-width:160px">
<button class="btn primary">Добавить</button></form>
<div class="chips">{player_chips}</div></div>

<div class="card"><h2>🎲 Добавить игру (раунд)</h2>
<form method="post" action="/add_round" class="row">
<input name="name" placeholder="Название игры (например: Игра 3)" required style="flex:1;min-width:160px">
<button class="btn primary">Добавить</button></form>
<div class="chips">{round_chips}</div></div>

<div class="card"><h2>📝 Внести результат игрока</h2>
<form method="post" action="/add_result">
<div class="form-grid">
<div><label class="lbl">Игрок</label><select name="player">{player_opts}</select></div>
<div><label class="lbl">Игра</label><select name="round_id">{round_opts}</select></div>
<div><label class="lbl">Роль</label><div class="toggle">
<button type="button" id="b_mafia" onclick="setRole('mafia')">🎭 Мафия</button>
<button type="button" id="b_don" onclick="setRole('don')">👑 Дон</button>
<button type="button" id="b_sheriff" onclick="setRole('sheriff')">🎯 Шериф</button>
<button type="button" id="b_civilian" class="on-civilian" onclick="setRole('civilian')">🏘️ Мирный</button></div>
<input type="hidden" name="role" id="role" value="civilian"></div>
<div><label class="lbl">Исход</label><div class="toggle">
<button type="button" id="btnWin" class="on-civilian" onclick="setOutcome('win')">Победа</button>
<button type="button" id="btnLoss" onclick="setOutcome('loss')">Поражение</button></div>
<input type="hidden" name="outcome" id="outcome" value="win"></div>
<div><label class="lbl">Фолы за игру (3 = −0.5, 4+ = −1)</label><input type="number" name="fouls" value="0" min="0" max="8" oninput="calc()"></div>
<div><label class="lbl">Доп. баллы (необязательно)</label><input type="number" name="extra" step="0.5" placeholder="0" oninput="calc()"></div>
</div>
<div class="preview">Начислится: <b id="prevPts">3</b> очка</div>
<button class="btn primary" style="width:100%">✅ Сохранить результат</button>
<div class="msg">{msg}</div></form></div>

<div class="card"><h2>📜 Последние результаты</h2>{results_list}</div>

<div class="card"><h2>⚙️ Настройки</h2>
<div class="row">
<form method="post" action="/set_pass" class="row" style="flex:1">
<input type="password" name="pass" placeholder="Новый пароль" required style="max-width:220px">
<button class="btn">Сменить пароль</button></form>
<a class="btn" href="/export">💾 Скачать данные</a>
<form method="post" action="/reset" onsubmit="return confirm('Точно сбросить ВЕСЬ турнир? Все игроки и очки удалятся!')"><button class="btn danger">🗑 Сбросить турнир</button></form>
</div></div>

<div id="st" style="display:none">{standings}</div>
</div>
<script>
let role='civilian', outcome='win';
const BLACK=['mafia','don'];
function setRole(r){{ role=r; document.getElementById('role').value=r;
  for(const x of ['mafia','don','sheriff','civilian'])
    document.getElementById('b_'+x).className = (x===r)?'on-'+r:'';
  calc(); }}
function setOutcome(o){{ outcome=o; document.getElementById('outcome').value=o;
  document.getElementById('btnWin').className = o==='win'?'on-civilian':'';
  document.getElementById('btnLoss').className = o==='loss'?'on-black':''; calc(); }}
function calc(){{
  let team = BLACK.includes(role) ? 'black':'red';
  let base = (outcome==='win') ? (team==='black'?4:3) : 1;
  let f = parseInt(document.querySelector('[name=fouls]').value)||0;
  let pen = f<=2?0:(f===3?-0.5:-1);
  let e = parseFloat(document.querySelector('[name=extra]').value)||0;
  let total = base + pen + e;
  document.getElementById('prevPts').textContent = Number.isInteger(total)? total : total.toFixed(2); }}
calc();
</script></body></html>"""

def admin_page(data, msg=''):
    chips = ''.join(f'<span class="chip">{esc(p)}<a href="/del_player?name={esc(p)}" onclick="return confirm(\'Удалить {esc(p)}?\')">✕</a></span>' for p in data['players']) or '<span class="hint">Пока никого нет</span>'
    rchips = ''.join(f'<span class="chip">🎲 {esc(r["name"])}<a href="/del_round?id={r["id"]}" onclick="return confirm(\'Удалить раунд?\')">✕</a></span>' for r in data['rounds']) or '<span class="hint">Раундов нет</span>'
    popts = ''.join(f'<option>{esc(p)}</option>' for p in data['players']) or '<option value="">— сначала добавьте игроков —</option>'
    ropts = ''.join(f'<option value="{r["id"]}">{esc(r["name"])}</option>' for r in data['rounds']) or '<option value="">— сначала добавьте раунд —</option>'
    rows = []
    for r in reversed(data['results'][-15:]):
        em, rname, team = ROLES[r['role']]
        pts = entry_points(r)
        rows.append(f'<tr><td>{esc(r["round_name"])}</td><td><b>{esc(r["player"])}</b></td>'
                    f'<td><span class="tag {team}">{em} {rname}</span></td>'
                    f'<td>{"🏆 победа" if r["outcome"]=="win" else "💀 поражение"}</td>'
                    f'<td>{("⚠️ " + str(r["fouls"])) if r.get("fouls") else "—"}</td>'
                    f'<td>{("+" + fmt(r["extra"])) if r.get("extra") else "—"}</td>'
                    f'<td class="total">{fmt(pts)}</td>'
                    f'<td><a class="btn small danger" href="/del_result?id={r["id"]}" onclick="return confirm(\'Удалить запись?\')">✕</a></td></tr>')
    rlist = ('<table><tr><th>Игра</th><th>Игрок</th><th>Роль</th><th>Исход</th><th>Фолы</th><th>Доп.</th><th>Очки</th><th></th></tr>'
             + ''.join(rows) + '</table>') if rows else '<div class="hint">Записей пока нет</div>'
    nav = '<a class="btn" href="/">👀 Таблица</a> <a class="btn danger" href="/logout">Выйти</a>'
    return ADMIN_PAGE.format(title='Ведущий — Турнир', css=CSS, nav=nav,
                             player_chips=chips, round_chips=rchips,
                             player_opts=popts, round_opts=ropts,
                             results_list=rlist, standings=standings_html(data), msg=msg)

LOGIN_PAGE = PAGE_TOP + """
<div class="card" style="max-width:400px;margin:60px auto">
<h2>🔑 Вход для ведущего</h2>
<form method="post" action="/login">
<input type="password" name="pass" placeholder="Пароль" style="width:100%;margin-bottom:12px" autofocus>
<button class="btn primary" style="width:100%">Войти</button>
<div class="msg">{msg}</div>
<div class="hint">Пароль по умолчанию: <b>mafia</b> (смените после входа)</div>
</form></div>
</div></body></html>"""

# ------------------- СЕРВЕР -------------------
SESSIONS = set()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, html, code=200, cookie=None):
        b = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(b)

    def _form(self):
        length = int(self.headers.get('Content-Length', 0))
        return {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode('utf-8')).items()}

    def _authed(self):
        cookie = self.headers.get('Cookie', '')
        return any(f'sess={s}' in cookie for s in SESSIONS)

    def _redirect(self, url):
        self.send_response(303)
        self.send_header('Location', url)
        self.end_headers()

    def do_GET(self):
        with LOCK:
            data = load_data()
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)

        if path == '/':
            self._send(view_page(data))
        elif path == '/api/standings':
            self._send(standings_html(data))
        elif path == '/admin':
            if self._authed():
                self._send(admin_page(data))
            else:
                self._send(LOGIN_PAGE.format(title='Вход', css=CSS, nav='<a class="btn" href="/">👀 Таблица</a>', msg=''))
        elif path == '/logout':
            self._send(view_page(data), cookie='sess=; Max-Age=0')
        elif path == '/export':
            b = json.dumps(data, ensure_ascii=False, indent=1).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename=mafia_data.json')
            self.send_header('Content-Length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif not self._authed():
            self._redirect('/admin')
        elif path == '/del_player':
            with LOCK:
                data = load_data()
                name = q.get('name', [''])[0]
                if name in data['players']:
                    data['players'].remove(name)
                    data['results'] = [r for r in data['results'] if r['player'] != name]
                    save_data(data)
            self._redirect('/admin')
        elif path == '/del_round':
            with LOCK:
                data = load_data()
                rid = q.get('id', [''])[0]
                data['rounds'] = [r for r in data['rounds'] if r['id'] != rid]
                data['results'] = [r for r in data['results'] if r['round_id'] != rid]
                save_data(data)
            self._redirect('/admin')
        elif path == '/del_result':
            with LOCK:
                data = load_data()
                rid = q.get('id', [''])[0]
                data['results'] = [r for r in data['results'] if r['id'] != rid]
                save_data(data)
            self._redirect('/admin')
        else:
            self._redirect('/')

    def do_POST(self):
        u = urlparse(self.path)
        f = self._form()
        with LOCK:
            data = load_data()

            if u.path == '/login':
                if f.get('pass') == data['pass']:
                    tok = secrets.token_hex(16)
                    SESSIONS.add(tok)
                    self.send_response(303)
                    self.send_header('Location', '/admin')
                    self.send_header('Set-Cookie', f'sess={tok}; Path=/')
                    self.end_headers()
                else:
                    nav = '<a class="btn" href="/">👀 Таблица</a>'
                    self._send(LOGIN_PAGE.format(title='Вход', css=CSS, nav=nav, msg='❌ Неверный пароль'))
                return

            if not self._authed():
                self._redirect('/admin')
                return

            if u.path == '/add_player':
                name = f.get('name', '').strip()
                if name and name not in data['players'] and len(data['players']) < 100:
                    data['players'].append(name)
                    save_data(data)
                self._redirect('/admin')
            elif u.path == '/add_round':
                name = f.get('name', '').strip()
                if name:
                    data['rounds'].append({'id': secrets.token_hex(4), 'name': name})
                    save_data(data)
                self._redirect('/admin')
            elif u.path == '/add_result':
                player = f.get('player', '').strip()
                rid = f.get('round_id', '')
                rnd = next((r for r in data['rounds'] if r['id'] == rid), None)
                if player in data['players'] and rnd and f.get('role') in ROLES and f.get('outcome') in ('win', 'loss'):
                    fouls = max(0, min(8, int(f.get('fouls', 0) or 0)))
                    extra = float(f.get('extra', 0) or 0)
                    data['results'].append({
                        'id': secrets.token_hex(6), 'player': player, 'round_id': rid,
                        'round_name': rnd['name'], 'role': f['role'], 'outcome': f['outcome'],
                        'fouls': fouls, 'extra': extra})
                    save_data(data)
                self._redirect('/admin')
            elif u.path == '/set_pass':
                if len(f.get('pass', '')) >= 3:
                    data['pass'] = f['pass']
                    save_data(data)
                self._redirect('/admin')
            elif u.path == '/reset':
                data = {"pass": data['pass'], "players": [], "rounds": [], "results": []}
                save_data(data)
                self._redirect('/admin')
            else:
                self._redirect('/admin')

if __name__ == '__main__':
    print('=' * 55)
    print('  🎭🏆 ТУРНИР «СПОРТИВНАЯ МАФИЯ» ЗАПУЩЕН')
    print('=' * 55)
    print(f'  👀 Игроки:    http://localhost:{PORT}')
    print(f'  🔑 Ведущий:   http://localhost:{PORT}/admin  (пароль: mafia)')
    print('  ⛔ Остановить: Ctrl+C')
    print('=' * 55)
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
