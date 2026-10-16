import http.server, json, os, threading, base64, socket, re, subprocess, io
from datetime import datetime
from collections import OrderedDict
import urllib.parse, mimetypes
import qrcode

# Kivy - للواجهة بتاعة التطبيق
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock

# ===== نفس متغيراتك القديمة =====
SECRET = "Mn2026_Secret_@#_KEY"
DATA_FILE = "attendance.json"
CONFIG_FILE = "config.json"
LATEST_FILE = "latest_link.txt"
DEFAULT_ADMIN_PASS = "admin2026"

DEFAULT_CFG = {"lecturePass": "", "open": "0", "s": "", "max_active": 32, "stay_seconds": 2.0, "ip_check": True, "nid_check": True, "device_check": True, "black_nids": [], "black_ips": [], "white_ips": [], "after_msg": "✅ تم التسجيل في موبايل الدكتور", "done_msg": "✅ تم تسجيل حضورك - توجه لمعمل 3 عند م/ احمد", "batch": 5, "adminPass": DEFAULT_ADMIN_PASS}
active_ips = OrderedDict()
waiting_queue = OrderedDict()

# عشان يشتغل على اندرويد - يحدد مكان الحفظ
try:
    from android.storage import app_storage_path
    BASE_DIR = app_storage_path()
except:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, "attendance.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LATEST_FILE = os.path.join(BASE_DIR, "latest_link.txt")

# ===== كل دوالك القديمة زي ما هي بدون نقصان =====
def get_interface_ips():
    ips = []
    try:
        out = ""
        for cmd in ["ip addr show", "ip -4 addr", "ifconfig"]:
            try:
                out = subprocess.check_output(cmd, shell=True, timeout=2, stderr=subprocess.STDOUT).decode('utf-8','ignore')
                if "inet " in out: break
            except: continue
        found = re.findall(r'inet\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)', out)
        for ip in found:
            if not ip.startswith("127.") and ip not in ips: ips.append(ip)
    except: pass
    return ips

def get_primary_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."): return ip
    except: pass
    return None

def get_local_ips():
    ips = []
    seen = set()
    for ip in get_interface_ips():
        if ip not in seen: ips.append(ip); seen.add(ip)
    primary = get_primary_ip()
    if primary and primary not in seen: ips.append(primary); seen.add(primary)
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in seen: ips.append(ip); seen.add(ip)
    except: pass
    for common in ["192.168.43.1", "192.168.137.1", "192.168.49.1", "192.168.0.100", "192.168.1.15"]:
        if common not in seen: ips.append(common); seen.add(common)
    def sort_key(ip):
        if ip == primary: return (0, ip)
        if ip.startswith("192.168.0."): return (1, ip)
        if ip.startswith("192.168.1."): return (1, ip)
        if ip.startswith("192.168.43."): return (2, ip)
        if ip.startswith("192.168."): return (3, ip)
        if ip.startswith("10."): return (2, ip)
        return (4, ip)
    ips_sorted = sorted(list(set(ips)), key=sort_key)
    if primary and primary in ips_sorted:
        ips_sorted.remove(primary)
        ips_sorted = [primary] + ips_sorted
    return ips_sorted

def load_cfg():
    if not os.path.exists(CONFIG_FILE):
        c=DEFAULT_CFG.copy()
        save_cfg(c)
        return c
    try:
        with open(CONFIG_FILE,'r',encoding='utf-8') as f:
            d=json.load(f)
            for k,v in DEFAULT_CFG.items():
                if k not in d: d[k]=v
            return d
    except: return DEFAULT_CFG.copy()

def save_cfg(c):
    with open(CONFIG_FILE,'w',encoding='utf-8') as f: json.dump(c,f,ensure_ascii=False,indent=2)

def free_ip(ip):
    if ip in active_ips: del active_ips[ip]
    if ip in waiting_queue: del waiting_queue[ip]

def get_wait_msg(pos, max_a, stay, batch):
    est_sec = (pos / batch) * stay + 5
    m = int(est_sec // 60); s = int(est_sec % 60)
    time_str = f"{m} دقيقة {s} ثانية" if m>0 else f"{s} ثانية"
    if pos <= 10: return f"⏳ فاضل قدامك {pos} بس - خليك فاتح الصفحة هتدخل لوحدك كمان {time_str}", 3
    elif pos <= 50: return f"🧘‍♂️ دورك رقم {pos} - السيستم بيدخل {batch} كل {stay} ثانية - سيب الموبايل مفتوح - متوقع {time_str}", 5
    else: return f"😅 انت رقم {pos} - الوقت المتوقع حوالي {time_str} - سيب الصفحة مفتوحة متعملش تحديث، هتدخل لوحدك", 8

def find_logo_file():
    for n in ["logo.jpg","logo.jpeg","logo.png","logo.webp","logo.JPG","logo.PNG","LOGO.jpg","LOGO.png","logo.jfif","institute.jpg"]:
        p = os.path.join(BASE_DIR, n)
        if os.path.exists(p): return p
    return None

def get_logo_tag(size=90, with_margin=True):
    lf = find_logo_file()
    mb = "margin-bottom:12px" if with_margin else ""
    if lf:
        try:
            with open(lf,'rb') as f:
                data = f.read()
                if len(data) > 100:
                    b64 = base64.b64encode(data).decode('utf-8')
                    mime,_ = mimetypes.guess_type(lf)
                    if not mime: mime='image/jpeg'
                    return f'<div style="text-align:center;{mb}"><img src="data:{mime};base64,{b64}" style="width:{size}px;height:{size}px;border-radius:18px;object-fit:cover;box-shadow:0 6px 18px rgba(0,0,0,.2);border:3px solid #fff;display:block;margin:0 auto"></div>'
        except Exception as e: print(f"Logo read error {lf}: {e}")
    return f'<div style="text-align:center;{mb}"><div style="width:{size}px;height:{size}px;background:linear-gradient(135deg,#1a73e8,#0f172a);border-radius:18px;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:{int(size*0.4)}px;font-weight:800">🎓</div></div>'

def get_header_logo_tag():
    lf = find_logo_file()
    if lf:
        try:
            with open(lf,'rb') as f:
                data = f.read()
                if len(data) > 100:
                    b64 = base64.b64encode(data).decode('utf-8')
                    mime,_ = mimetypes.guess_type(lf)
                    if not mime: mime='image/jpeg'
                    return f'<img src="data:{mime};base64,{b64}" style="width:44px;height:44px;border-radius:12px;object-fit:cover;border:2px solid #fff;display:block;flex-shrink:0">'
        except: pass
    return '<div style="width:44px;height:44px;background:linear-gradient(135deg,#60a5fa,#1d4ed8);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff;flex-shrink:0">🎓</div>'

def simple_hash(s):
    h = 0
    for ch in s:
        h = ((h << 5) - h) + ord(ch)
        h = h & 0xFFFFFFFF
        if h >= 0x80000000: h -= 0x100000000
    return format(abs(h), '36')

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div>المعهد الصناعي بالمحلة</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div></div></div>"""

# ===== هنا نفس build_att_html و build_admin_html بتوعك القديم =====
def build_att_html():
    cfg=load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>تسجيل الحضور</title><style>body{{margin:0;font-family:Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}input{{width:100%;padding:13px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px}}button{{width:100%;padding:14px;background:#1a73e8;color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800}}</style></head><body><div class="card">{LOGO_TAG}<h2 style="text-align:center">📝 تسجيل الحضور</h2><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي"><input id="nid" maxlength="14" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="ok" style="display:none;background:#dcfce7;padding:10px;margin-top:10px">{cfg['after_msg']}</div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
function getParams(){{let p=new URLSearchParams(location.search);return {{open:p.get('open'),s:p.get('s')}};}}
async function sendData(){{let p=document.getElementById('pass').value,b=document.getElementById('board').value,n=document.getElementById('name').value,id=document.getElementById('nid').value;let gp=getParams();let deviceId=localStorage.getItem('device_fingerprint')||'dev_'+Math.random().toString(36).slice(2);localStorage.setItem('device_fingerprint',deviceId);let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:gp.open||'',s:gp.s||'',name:n,nid:id,board:b,pass:p,deviceId:deviceId}})}});if(r.status==200){{document.getElementById('ok').style.display='block';let d=await r.json(); if(d.redirect) window.location.href=d.redirect;}} else{{alert('خطأ '+r.status);}}}}
</script></body></html>"""

def build_admin_html():
    cfg=load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    ips = get_local_ips()
    primary = get_primary_ip() or (ips[0] if ips else "192.168.43.1")
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة التحكم</title></head><body style="font-family:Tahoma;padding:15px"><div style="max-width:900px;margin:auto">{LOGO_TAG}<h2>لوحة تحكم - IP: {primary} - كل IPs: {', '.join(ips)}</h2><p>باسورد الادمن: {cfg.get('adminPass')}</p><p>عدد المسجلين: <span id="count">0</span></p><div><input id="lecturePass" placeholder="كلمة سر المحاضرة"><input id="minutes" type="number" value="30"><button onclick="openNow()">افتح</button><button onclick="closeNow()">اقفل</button></div><div id="shareBox" style="display:none;background:#e0f2fe;padding:10px;margin-top:10px"><input id="shareLinkLocal" readonly style="width:100%"><input id="shareLinkRouter" readonly style="width:100%;margin-top:5px"><input id="shareLinkHotspot" readonly style="width:100%;margin-top:5px"></div><table id="tbl" border="1" style="width:100%;margin-top:15px"><thead><tr><th>#</th><th>الاسم</th><th>القومي</th><th>السبورة</th></tr></thead><tbody></tbody></table></div><script>
const SECRET="Mn2026_Secret_@#_KEY";let lastOpen="",lastSig="";function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
async function openNow(){{let lp=document.getElementById('lecturePass').value;let mins=parseInt(document.getElementById('minutes').value);let u=Date.now()+mins*60*1000;let sig=simpleHash(u.toString()+SECRET);lastOpen=u.toString();lastSig=sig;let host=location.host;let path='/attendance.html?open='+u+'&s='+sig;document.getElementById('shareLinkLocal').value=location.protocol+'//'+host+path;document.getElementById('shareLinkRouter').value='http://'+host.split(':')[0]+':8080'+path;document.getElementById('shareLinkHotspot').value='http://192.168.43.1:8080'+path;document.getElementById('shareBox').style.display='block';await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:u.toString(),s:sig,lecturePass:lp}})}});}}
async function closeNow(){{await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:"0",s:"",lecturePass:""}})}});alert('اتقفل');}}
setInterval(()=>{{fetch('/list').then(r=>r.json()).then(d=>{{document.getElementById('count').innerText=d.list.length;let tb=document.querySelector('#tbl tbody');tb.innerHTML='';d.list.forEach((x,i)=>{{tb.innerHTML+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td>${{x.nid}}</td><td>${{x.board}}</td></tr>`}});}})}},2000);
</script></body></html>"""

def ensure_files():
    cfg=load_cfg()
    save_cfg(cfg)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,"w",encoding="utf-8") as f: f.write("[]")

# ===== نفس Handler القديم بالظبط =====
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]
        cfg=load_cfg()
        if self.path == '/admin_auth':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            ok = data.get('pass','') == cfg.get('adminPass', DEFAULT_ADMIN_PASS)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"ok": ok}).encode('utf-8')); return
        if self.path == '/delete_one':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            nid_to_del = data.get('nid','').strip()
            deleted=False
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE,'r',encoding='utf-8') as f: all_data=json.load(f)
                    new_data=[x for x in all_data if x.get('nid')!=nid_to_del]
                    if len(new_data)!=len(all_data):
                        deleted=True
                        with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(new_data,f,ensure_ascii=False,indent=2)
                except: pass
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"ok": deleted}).encode('utf-8')); return
        if self.path == '/change_admin_pass':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            old = data.get('oldPass',''); new = data.get('newPass','').strip()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            if old!= cfg.get('adminPass'): self.wfile.write(json.dumps({"ok": False, "error": "الباسورد الحالي غلط"}).encode('utf-8')); return
            cfg['adminPass'] = new; save_cfg(cfg)
            self.wfile.write(json.dumps({"ok": True}).encode('utf-8')); return
        if self.path == '/save_adv':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            for k in ["max_active","stay_seconds","batch","after_msg","done_msg","ip_check","nid_check","device_check","black_nids","black_ips","white_ips"]:
                if k in data: cfg[k]=data[k]
            save_cfg(cfg); self.send_response(200); self.end_headers(); return
        if self.path == '/set_config':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            cfg["lecturePass"]=data.get('lecturePass',''); cfg["open"]=data.get('open','0'); cfg["s"]=data.get('s',''); save_cfg(cfg)
            try:
                if cfg["open"]!="0":
                    link = f"/attendance.html?open={cfg['open']}&s={cfg['s']}"
                    with open(LATEST_FILE,'w',encoding='utf-8') as f: f.write(link)
                else:
                    if os.path.exists(LATEST_FILE): os.remove(LATEST_FILE)
            except: pass
            self.send_response(200); self.end_headers(); return
        if self.path == '/save':
            try:
                length = int(self.headers.get('content-length',0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                now_ms = int(datetime.now().timestamp()*1000)
                if cfg.get('open','0') == "0" or int(cfg.get('open','0')) < now_ms:
                    self.send_response(403); self.end_headers(); return
                if cfg.get('lecturePass','').strip() and data.get('pass','').strip()!= cfg.get('lecturePass','').strip():
                    self.send_response(401); self.end_headers(); return
                nid = data.get('nid','').strip(); deviceId = data.get('deviceId','').strip()
                all_data=[]
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE,'r',encoding='utf-8') as f:
                        try: all_data=json.load(f)
                        except: all_data=[]
                if cfg.get('nid_check',True) and any(x.get('nid')==nid for x in all_data):
                    self.send_response(409); self.end_headers(); return
                if cfg.get('ip_check',True) and any(x.get('ip')==client_ip for x in all_data):
                    self.send_response(410); self.end_headers(); return
                if cfg.get('device_check',True) and deviceId and any(x.get('deviceId')==deviceId for x in all_data):
                    self.send_response(411); self.end_headers(); return
                if len(active_ips) >= cfg.get('max_active',32) and client_ip not in active_ips:
                    if client_ip not in waiting_queue: waiting_queue[client_ip]=datetime.now()
                    pos = list(waiting_queue.keys()).index(client_ip) + 1
                    msg, _ = get_wait_msg(pos, cfg['max_active'], cfg['stay_seconds'], cfg['batch'])
                    self.send_response(429); self.send_header('Content-Type','application/json'); self.end_headers()
                    self.wfile.write(json.dumps({"pos":pos,"msg":msg}).encode('utf-8')); return
                if client_ip in waiting_queue: del waiting_queue[client_ip]
                active_ips[client_ip]=datetime.now().strftime("%H:%M:%S")
                rec={"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"name":data.get('name',''),"nid":nid,"board":data.get('board',''),"pass":data.get('pass',''),"ip":client_ip,"deviceId":deviceId}
                all_data.append(rec)
                with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(all_data,f,ensure_ascii=False,indent=2)
                threading.Timer(float(cfg.get('stay_seconds',2.0)), free_ip, args=(client_ip,)).start()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({"ok":True,"redirect":"/done"}).encode('utf-8'))
            except Exception as e:
                print(e); self.send_response(500); self.end_headers()
        elif self.path == '/clear':
            with open(DATA_FILE,'w',encoding='utf-8') as f: f.write("[]")
            active_ips.clear(); waiting_queue.clear()
            self.send_response(200); self.end_headers()
        elif self.path == '/clear_queue':
            waiting_queue.clear(); active_ips.clear()
            self.send_response(200); self.end_headers()
        else: self.send_response(404); self.end_headers()

    def do_GET(self):
        client_ip = self.client_address[0]
        cfg=load_cfg()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = parsed.query
        low = path.lower()
        if low == '/__save_latest':
            params = urllib.parse.parse_qs(query)
            link = params.get('link', [''])[0]
            if link:
                try:
                    with open(LATEST_FILE,'w',encoding='utf-8') as f: f.write(urllib.parse.unquote(link))
                except: pass
            self.send_response(200); self.end_headers(); self.wfile.write(b'Saved'); return
        if low == '/' or low == '/go' or low == '/go.html':
            if os.path.exists(LATEST_FILE):
                try:
                    with open(LATEST_FILE,'r',encoding='utf-8') as f: latest = f.read().strip()
                    if latest and 'open=' in latest:
                        if cfg.get('open','0')!="0" and int(cfg.get('open','0')) > int(datetime.now().timestamp()*1000):
                            self.send_response(302); self.send_header('Location', latest); self.end_headers(); return
                except: pass
        if low == '/my_ips':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"ips": get_local_ips(), "primary": get_primary_ip()}).encode('utf-8')); return
        if low == '/time':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({"server": int(datetime.now().timestamp()*1000)}).encode('utf-8')); return
        if low == '/get_config':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            safe_cfg = {k:v for k,v in cfg.items() if k!='adminPass'}
            self.wfile.write(json.dumps(safe_cfg).encode('utf-8')); return
        if low == '/list':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            data=[]
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE,'r',encoding='utf-8') as f:
                    try: data=json.load(f)
                    except: data=[]
            self.wfile.write(json.dumps({"list":data,"active":len(active_ips),"waiting":len(waiting_queue),"max_active":cfg['max_active']}).encode('utf-8')); return
        if low == '/done' or low == '/done.html':
            self.send_response(200); self.send_header('Content-type','text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(f"<html><body style='text-align:center;padding:20px'><h2>{cfg['done_msg']}</h2><button onclick='window.location.href=\"intent:#Intent;action=android.settings.WIFI_SETTINGS;end\"' style='padding:15px;background:red;color:white;border:none;border-radius:10px;width:90%'>افصل الواي فاي</button></body></html>".encode('utf-8')); return
        if 'attendance' in low or low == '/' or low == '/index.html':
            self.send_response(200); self.send_header('Content-type','text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(build_att_html().encode('utf-8')); return
        if 'admin' in low:
            self.send_response(200); self.send_header('Content-type','text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(build_admin_html().encode('utf-8')); return
        return super().do_GET()

def start_server():
    ensure_files()
    print(f"Server started on 0.0.0.0:8080 IPs: {get_local_ips()}")
    http.server.HTTPServer(('0.0.0.0',8080), Handler).serve_forever()

# ===== Kivy App - واجهة الموبايل اللي تعرض QR =====
class MansourApp(App):
    def build(self):
        # شغل السيرفر القديم في الخلفية
        threading.Thread(target=start_server, daemon=True).start()

        self.root_box = BoxLayout(orientation='vertical', padding=15, spacing=10)
        self.label = Label(text="جاري تشغيل السيرفر...\nانتظر 3 ثواني", font_size=20)
        self.img = Image()
        self.root_box.add_widget(self.label)
        self.root_box.add_widget(self.img)

        # بعد 3 ثواني اعرض الـ QR
        Clock.schedule_once(self.show_qr, 3)
        return self.root_box

    def show_qr(self, dt):
        ip = get_primary_ip() or "192.168.43.1"
        url = f"http://{ip}:8080/go"
        self.label.text = f"السيرفر شغال ✅\n{url}\nAdmin: {ip}:8080/admin.html\nيتحمل 500 طالب"
        qr = qrcode.make(url)
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        buf.seek(0)
        cim = CoreImage(buf, ext='png')
        self.img.texture = cim.texture

if __name__ == '__main__':
    MansourApp().run()