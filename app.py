# -*- coding: utf-8 -*-
import os,json,secrets,re,threading,html
from urllib.parse import parse_qs
BASE=os.path.dirname(os.path.abspath(__file__)); DATA_FILE=os.path.join(BASE,'mafia_data.json'); LOCK=threading.RLock()
ROLES={'mafia':('Мафия','black'),'don':('Дон','black'),'sheriff':('Шериф','red'),'civilian':('Мирный','red')}

def load():
    if not os.path.exists(DATA_FILE): return {'pass':'mafia','players':[],'rounds':[],'results':[]}
    try:
        d=json.load(open(DATA_FILE,encoding='utf-8'))
        d.setdefault('pass','mafia');d.setdefault('rounds',[]);d.setdefault('results',[])
        d['players']=[p if isinstance(p,dict) else {'name':p,'image':''} for p in d.get('players',[])]
        return d
    except: return {'pass':'mafia','players':[],'rounds':[],'results':[]}
def save(d):
    t=DATA_FILE+'.tmp';json.dump(d,open(t,'w',encoding='utf-8'),ensure_ascii=False,indent=2);os.replace(t,DATA_FILE)
def E(x): return html.escape(str(x),quote=True)
def F(x):
    x=float(x);return str(int(x)) if x.is_integer() else f'{x:.2f}'.rstrip('0').rstrip('.')
def pts(r):
    team=ROLES[r['role']][1];base=4 if team=='black' and r['outcome']=='win' else 3 if team=='red' and r['outcome']=='win' else 1
    f=int(r.get('fouls',0) or 0);return base+(0 if f<=2 else -.5 if f==3 else -1)+float(r.get('extra',0) or 0)
def stats(d,n):
    a=[r for r in d['results'] if r['player']==n];g=len(a);w=sum(r['outcome']=='win' for r in a);ex=sum(float(r.get('extra',0) or 0) for r in a);fo=sum(int(r.get('fouls',0) or 0) for r in a);p=sum(pts(r) for r in a)
    return {'games':g,'wins':w,'winrate':w/g*100 if g else 0,'extra':ex,'fouls':fo,'points':p,'avg':p/g if g else 0}
def rstats(d,n,role):
    a=[r for r in d['results'] if r['player']==n and r['role']==role]
    if not a:return None
    g=len(a);w=sum(r['outcome']=='win' for r in a);return {'games':g,'wins':w,'winrate':w/g*100,'avg':sum(pts(r) for r in a)/g,'extra':sum(float(r.get('extra',0) or 0) for r in a)/g,'fouls':sum(int(r.get('fouls',0) or 0) for r in a)/g}
def rating(s): return s['avg']+.5*s['extra']+.1*s['games']-.2*s['fouls']
def role_noms(d):
    out=[]
    for role,title in [('mafia','Лучшая мафия'),('don','Лучший дон'),('sheriff','Лучший шериф'),('civilian','Лучший мирный')]:
        c=[]
        for p in d['players']:
            s=rstats(d,p['name'],role)
            if s:c.append((rating(s),p['name'],s))
        c.sort(key=lambda x:(-x[0],-x[2]['games'],x[1].lower()));out.append((title,c[0] if c else None))
    return out
def tactician(d):
    # >=4 games; 45% wins, 25% extra/game, 20% average points, 10% discipline.
    c=[(p['name'],stats(d,p['name'])) for p in d['players'] if stats(d,p['name'])['games']>=4]
    if not c:return None
    mx=max((s['extra']/s['games'] for _,s in c),default=0);out=[]
    for n,s in c:
        ex=s['extra']/s['games'];exs=ex/mx*100 if mx else 50;ps=max(0,min(100,s['avg']/4*100));ds=max(0,min(100,(4-s['fouls']/s['games'])/4*100));score=.45*s['winrate']+.25*exs+.20*ps+.10*ds;out.append((score,n,s))
    out.sort(key=lambda x:(-x[0],-x[2]['wins'],-x[2]['games'],-x[2]['points'],x[1].lower()));return out[0]
CSS='''
:root{--bg:#f5f6f8;--panel:#fff;--text:#111318;--muted:#6b7280;--line:#e5e7eb;--accent:#111827;--shadow:0 10px 30px rgba(17,24,39,.06)}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,"Segoe UI",Arial,sans-serif}a{color:inherit}.top{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}.nav,.wrap{max-width:1180px;margin:auto}.nav{padding:14px 20px;display:flex;justify-content:space-between;align-items:center;gap:10px}.brand{font-weight:800;letter-spacing:-.02em}.brand span,.muted,.sub{color:var(--muted)}.links{display:flex;gap:8px}.btn{display:inline-block;border:1px solid var(--line);background:#fff;border-radius:10px;padding:9px 13px;text-decoration:none;font-weight:650;font-size:14px;cursor:pointer}.dark{background:#111827;color:#fff;border-color:#111827}.danger{color:#b42318}.wrap{padding:0 20px 50px}.hero{padding:34px 0 20px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:750}.hero h1{font-size:clamp(30px,5vw,46px);margin:8px 0;line-height:1.05}.hero p{color:var(--muted);max-width:720px}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.panel{grid-column:span 12;background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:20px}.half{grid-column:span 6}.third{grid-column:span 4}.panel h2{font-size:17px;margin:0 0 15px}.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:650px}.table th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);text-align:left;padding:9px;border-bottom:1px solid var(--line)}.table td{padding:12px 9px;border-bottom:1px solid #f0f1f3}.player{display:flex;align-items:center;gap:10px;min-width:150px}.avatar{width:38px;height:38px;border-radius:50%;object-fit:cover;background:#eef0f3}.pill{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:700}.black{background:#f0f0f1}.red{background:#fbeaea;color:#9c2018}.score{font-weight:800}.nomgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.nom{border:1px solid var(--line);border-radius:14px;padding:15px}.nomtitle{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-weight:750}.nomname{font-size:17px;font-weight:800;margin:8px 0 4px}.nomstat{font-size:12px;color:var(--muted)}.special{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.notice{padding:12px 14px;background:#f7f7f8;border-radius:10px;color:#4b5563;font-size:13px;line-height:1.5}.input,.select{border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit;background:#fff;width:100%}.formgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.full{grid-column:1/-1}.field label{display:block;font-size:12px;color:var(--muted);font-weight:700;margin-bottom:6px}.roles{display:flex;gap:6px;flex-wrap:wrap}.roles button{border:1px solid var(--line);background:#fff;border-radius:9px;padding:9px 10px}.roles .active{background:#111827;color:#fff}.preview{padding:12px;background:#f7f7f8;border-radius:10px;margin:12px 0;font-weight:700}.chips{display:flex;gap:8px;flex-wrap:wrap}.chip{border:1px solid var(--line);border-radius:999px;padding:6px 10px;font-size:13px}.footer{text-align:center;color:#9ca3af;font-size:12px;padding:25px}@media(max-width:850px){.half,.third{grid-column:span 12}.nomgrid,.special{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.wrap{padding:0 12px 40px}.nav{padding:12px}.nomgrid,.special,.formgrid{grid-template-columns:1fr}.panel{padding:15px}}
'''
def page(title,body,admin=False):
    nav='<a class="btn" href="/">Таблица</a>'+('<a class="btn danger" href="/logout">Выйти</a>' if admin else '<a class="btn dark" href="/admin">Ведущий</a>')
    return '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+E(title)+'</title><style>'+CSS+'</style></head><body><header class="top"><div class="nav"><div class="brand">СПОРТИВНАЯ МАФИЯ <span>/ tournament</span></div><div class="links">'+nav+'</div></div></header><main class="wrap">'+body+'</main><div class="footer">Турнирная система · live</div></body></html>'
def avatar(p):
    im=str(p.get('image','')).strip();initial=E(p['name'][:1].upper())
    if re.fullmatch(r'[A-Za-z0-9_-]{1,40}',im or ''):return '<img class="avatar" src="/images/'+im+'.png" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'" alt=""><span class="avatar" style="display:none;align-items:center;justify-content:center;font-weight:800">'+initial+'</span>'
    return '<span class="avatar" style="display:flex;align-items:center;justify-content:center;font-weight:800">'+initial+'</span>'
def public(d):
    ss={p['name']:stats(d,p['name']) for p in d['players']};order=sorted(d['players'],key=lambda p:(-ss[p['name']]['points'],p['name'].lower()));rows=[]
    for i,p in enumerate(order,1):
        s=ss[p['name']];cells=[]
        for rd in d['rounds']:
            a=[r for r in d['results'] if r['player']==p['name'] and r['round_id']==rd['id']]
            if a:r=a[-1];rn,t=ROLES[r['role']];cells.append('<td><span class="pill '+t+'">'+rn+'</span><span class="sub">'+F(pts(r))+' очк.</span></td>')
            else:cells.append('<td class="muted">—</td>')
        rows.append('<tr><td>'+str(i)+'</td><td><div class="player">'+avatar(p)+'<div><b>'+E(p['name'])+'</b><span class="sub">'+str(s['games'])+' игр · '+str(s['wins'])+' побед</span></div></div></td>'+''.join(cells)+'<td><span class="score">'+F(s['points'])+'</span><span class="sub">'+str(round(s['winrate']))+'% побед</span></td></tr>')
    heads=''.join('<th>'+E(r['name'])+'</th>' for r in d['rounds']);noms=[]
    for title,c in role_noms(d):
        if c:noms.append('<div class="nom"><div class="nomtitle">'+title+'</div><div class="nomname">'+E(c[1])+'</div><div class="nomstat">'+str(c[2]['games'])+' игр · '+str(round(c[2]['winrate']))+'% побед · рейтинг '+F(rating(c[2]))+'</div></div>')
        else:noms.append('<div class="nom"><div class="nomtitle">'+title+'</div><div class="nomname">—</div><div class="nomstat">Недостаточно данных</div></div>')
    t=tactician(d);tcard='<div class="nom"><div class="nomtitle">Тактик турнира</div><div class="nomname">'+(E(t[1]) if t else '—')+'</div><div class="nomstat">'+(('Индекс %.1f/100 · %s побед из %s игр'%(t[0],t[2]['wins'],t[2]['games'])) if t else 'Нужно минимум 4 игры')+'</div></div>'
    body='<section class="hero"><div class="eyebrow">SEASON / LIVE STANDINGS</div><h1>Турнирная таблица</h1><p>Минималистичная публичная страница: места, результаты, очки и номинации.</p></section><div class="grid"><section class="panel"><div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px"><input id="q" class="input" style="max-width:280px" placeholder="Поиск игрока…"></div><div class="tablewrap"><table class="table" id="tab"><thead><tr><th>#</th><th>Игрок</th>'+heads+'<th>Итого</th></tr></thead><tbody>'+(''.join(rows) or '<tr><td colspan="99" class="muted">Пока нет данных.</td></tr>')+'</tbody></table></div><div class="muted" style="margin-top:12px">Игроков: '+str(len(order))+' · Раундов: '+str(len(d['rounds']))+' · автообновление 10 сек.</div></section><section class="panel"><h2>Номинации по ролям</h2><div class="nomgrid">'+''.join(noms)+'</div></section><section class="panel half"><h2>Специальные</h2><div class="special">'+tcard+'<div class="nom"><div class="nomtitle">Активист</div><div class="nomname">—</div><div class="nomstat">Считается по числу игр</div></div><div class="nom"><div class="nomtitle">Чемпион</div><div class="nomname">—</div><div class="nomstat">Считается по числу побед</div></div><div class="nom"><div class="nomtitle">Лидер</div><div class="nomname">—</div><div class="nomstat">Считается по доп. баллам</div></div></div></section><section class="panel half"><h2>Тактик — формула</h2><div class="notice"><b>45%</b> процент побед · <b>25%</b> доп. баллы/игру · <b>20%</b> средние очки · <b>10%</b> дисциплина. Минимум 4 игры.<br><br>Показатель использует только реально заносимые данные, а не выдумывает оценку решений.</div></section></div><script>const q=document.getElementById("q");q.oninput=()=>document.querySelectorAll("#tab tbody tr").forEach(r=>r.style.display=(r.children[1]?.innerText||"").toLowerCase().includes(q.value.toLowerCase())?"":"none");setTimeout(()=>location.reload(),10000)</script>'
    return page('Спортивная мафия — таблица',body)
def login(msg=''):return page('Вход','<section class="panel" style="max-width:420px;margin:70px auto"><div class="eyebrow">ADMIN</div><h1>Вход ведущего</h1><form method="post" action="/login"><input class="input" type="password" name="pass" placeholder="Пароль" autofocus><button class="btn dark" style="width:100%;margin-top:10px">Войти</button><p style="color:#b42318">'+E(msg)+'</p></form></section>')
def admin(d,msg=''):
    po=''.join('<option>'+E(p['name'])+'</option>' for p in d['players']) or '<option>— нет игроков —</option>';ro=''.join('<option value="'+E(r['id'])+'">'+E(r['name'])+'</option>' for r in d['rounds']) or '<option>— нет игр —</option>'
    chips=''.join('<span class="chip">'+E(p['name'])+' · фото '+E(p.get('image') or '—')+' <a href="/del_player?name='+E(p['name'])+'">×</a></span>' for p in d['players']) or '<span class="muted">Нет игроков</span>'
    rchips=''.join('<span class="chip">'+E(r['name'])+' <a href="/del_round?id='+E(r['id'])+'">×</a></span>' for r in d['rounds']) or '<span class="muted">Нет раундов</span>'
    recent=[]
    for r in reversed(d['results'][-20:]):
        rn,t=ROLES[r['role']];recent.append('<tr><td>'+E(r['round_name'])+'</td><td>'+E(r['player'])+'</td><td><span class="pill '+t+'">'+rn+'</span></td><td>'+('Победа' if r['outcome']=='win' else 'Поражение')+'</td><td>'+str(r.get('fouls',0))+'</td><td>'+F(r.get('extra',0))+'</td><td>'+F(pts(r))+'</td><td><a class="btn" href="/del_result?id='+E(r['id'])+'">Удалить</a></td></tr>')
    rb=''.join('<button type="button" data-role="'+r+'" onclick="setRole(\''+r+'\')">'+n+'</button>' for r,(n,_) in ROLES.items())
    body='<section class="hero"><div class="eyebrow">ADMIN / CONTROL ROOM</div><h1>Панель ведущего</h1><p>Фото: положи <b>1.png</b>, <b>2.png</b> и т.д. в папку <b>images/</b>, затем укажи номер фото игроку.</p></section><div class="grid"><section class="panel third"><h2>Игрок</h2><form method="post" action="/add_player" class="formgrid"><div class="field"><label>Имя</label><input class="input" name="name" required></div><div class="field"><label>Фото №</label><input class="input" name="image" placeholder="1"></div><div class="full"><button class="btn dark" style="width:100%">Добавить</button></div></form><div class="chips" style="margin-top:12px">'+chips+'</div></section><section class="panel third"><h2>Раунд</h2><form method="post" action="/add_round"><input class="input" name="name" placeholder="Игра 1" required><button class="btn dark" style="width:100%;margin-top:10px">Добавить</button></form><div class="chips" style="margin-top:12px">'+rchips+'</div></section><section class="panel third"><h2>Система</h2><div class="notice">Сохраняем старую систему очков: чёрные +4 за победу, красные +3, поражение +1; фолы 3 = −0.5, 4+ = −1; доп. баллы добавляются.</div><a class="btn" href="/export">Экспорт JSON</a></section><section class="panel"><h2>Новый результат</h2><form method="post" action="/add_result"><div class="formgrid"><div class="field"><label>Игрок</label><select class="select" name="player">'+po+'</select></div><div class="field"><label>Раунд</label><select class="select" name="round_id">'+ro+'</select></div><div class="field"><label>Роль</label><div class="roles">'+rb+'</div><input type="hidden" name="role" id="role" value="civilian"></div><div class="field"><label>Исход</label><select class="select" name="outcome" id="outcome"><option value="win">Победа</option><option value="loss">Поражение</option></select></div><div class="field"><label>Фолы</label><input class="input" type="number" name="fouls" value="0" min="0" max="8" oninput="calc()"></div><div class="field"><label>Доп. баллы</label><input class="input" type="number" name="extra" value="0" step="0.5" oninput="calc()"></div><div class="full"><div class="preview">Начислится: <span id="preview">3</span></div><button class="btn dark" style="width:100%">Сохранить</button><p style="color:#b42318">'+E(msg)+'</p></div></div></form></section><section class="panel"><h2>Последние результаты</h2><div class="tablewrap"><table class="table"><thead><tr><th>Раунд</th><th>Игрок</th><th>Роль</th><th>Исход</th><th>Фолы</th><th>Доп.</th><th>Очки</th><th></th></tr></thead><tbody>'+(''.join(recent) or '<tr><td colspan="8">Нет записей</td></tr>')+'</tbody></table></div></section><section class="panel"><h2>Безопасность</h2><form method="post" action="/set_pass" style="display:flex;gap:8px;flex-wrap:wrap"><input class="input" style="max-width:260px" type="password" name="pass" placeholder="Новый пароль" required><button class="btn">Сменить</button></form><form method="post" action="/reset" style="margin-top:10px"><button class="btn danger">Сбросить турнир</button></form></section></div><script>let role="civilian",black=["mafia","don"];function setRole(r){role=r;document.getElementById("role").value=r;document.querySelectorAll("[data-role]").forEach(b=>b.classList.toggle("active",b.dataset.role===r));calc()}function calc(){let t=black.includes(role)?"black":"red",o=document.getElementById("outcome").value,b=o==="win"?(t==="black"?4:3):1,f=+document.querySelector("[name=fouls]").value||0,e=+document.querySelector("[name=extra]").value||0;document.getElementById("preview").textContent=b+(f<=2?0:f===3?-0.5:-1)+e}document.getElementById("outcome").onchange=calc;setRole("civilian");calc()</script>'
    return page('Панель ведущего',body,True)
SESSIONS=set()
def token(env):
    for x in env.get('HTTP_COOKIE','').split(';'):
        if x.strip().startswith('sess='):return x.strip()[5:]
    return ''
def auth(env):return token(env) in SESSIONS
def send(start,status,body,headers=None):
    b=body.encode();h=[('Content-Type','text/html; charset=utf-8'),('Content-Length',str(len(b)))]+(headers or []);start(status,h);return [b]
def app(env,start):
    path=env.get('PATH_INFO') or '/';q=parse_qs(env.get('QUERY_STRING',''));d=load()
    if path.startswith('/images/'):
        fn=os.path.basename(path);fp=os.path.join(BASE,'images',fn)
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',fn) or not os.path.isfile(fp):return send(start,'404 Not Found','')
        b=open(fp,'rb').read();mime='image/png' if fn.lower().endswith('.png') else 'image/jpeg';start('200 OK',[('Content-Type',mime),('Content-Length',str(len(b))) ]);return [b]
    if path=='/export':
        b=json.dumps(d,ensure_ascii=False,indent=2).encode();start('200 OK',[('Content-Type','application/json'),('Content-Disposition','attachment; filename="mafia_data.json"'),('Content-Length',str(len(b)))]);return [b]
    if env.get('REQUEST_METHOD')=='GET':
        if path=='/':return send(start,'200 OK',public(d))
        if path=='/admin':return send(start,'200 OK',admin(d) if auth(env) else login())
        if path=='/logout':SESSIONS.discard(token(env));return send(start,'200 OK',public(d),[('Set-Cookie','sess=; Max-Age=0; Path=/')])
        if not auth(env):return send(start,'303 See Other','',[('Location','/admin')])
        with LOCK:d=load()
        if path=='/del_player':n=q.get('name',[''])[0];d['players']=[p for p in d['players'] if p['name']!=n];d['results']=[r for r in d['results'] if r['player']!=n];save(d)
        elif path=='/del_round':i=q.get('id',[''])[0];d['rounds']=[r for r in d['rounds'] if r['id']!=i];d['results']=[r for r in d['results'] if r['round_id']!=i];save(d)
        elif path=='/del_result':i=q.get('id',[''])[0];d['results']=[r for r in d['results'] if r['id']!=i];save(d)
        else:return send(start,'404 Not Found','')
        return send(start,'303 See Other','',[('Location','/admin')])
    length=int(env.get('CONTENT_LENGTH','0') or 0);f={k:v[-1] for k,v in parse_qs(env['wsgi.input'].read(length).decode()).items()}
    if path=='/login':
        if f.get('pass')==d['pass']:
            s=secrets.token_hex(24);SESSIONS.add(s);return send(start,'303 See Other','',[('Location','/admin'),('Set-Cookie',f'sess={s}; Path=/; HttpOnly; SameSite=Lax')])
        return send(start,'200 OK',login('Неверный пароль'))
    if not auth(env):return send(start,'303 See Other','',[('Location','/admin')])
    with LOCK:d=load()
    if path=='/add_player':
        n=f.get('name','').strip();im=f.get('image','').strip()
        if n and not any(p['name']==n for p in d['players']):d['players'].append({'name':n,'image':im});save(d)
    elif path=='/add_round':
        n=f.get('name','').strip()
        if n:d['rounds'].append({'id':secrets.token_hex(5),'name':n});save(d)
    elif path=='/add_result':
        p=f.get('player','');rid=f.get('round_id','');role=f.get('role','civilian');o=f.get('outcome','win');rd=next((r for r in d['rounds'] if r['id']==rid),None)
        if rd and any(x['name']==p for x in d['players']) and role in ROLES and o in ('win','loss'):
            try:fo=max(0,min(8,int(f.get('fouls','0'))));ex=float(f.get('extra','0') or 0)
            except:fo,ex=0,0
            d['results']=[r for r in d['results'] if not(r['player']==p and r['round_id']==rid)];d['results'].append({'id':secrets.token_hex(6),'player':p,'round_id':rid,'round_name':rd['name'],'role':role,'outcome':o,'fouls':fo,'extra':ex});save(d)
    elif path=='/set_pass':
        if len(f.get('pass',''))>=6:d['pass']=f['pass'];save(d)
    elif path=='/reset':d={'pass':d['pass'],'players':[],'rounds':[],'results':[]};save(d)
    return send(start,'303 See Other','',[('Location','/admin')])
