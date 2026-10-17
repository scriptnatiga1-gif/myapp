from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
import threading, http.server, json, os, base64, socket, re, subprocess, urllib.parse, mimetypes
from datetime import datetime
from collections import OrderedDict

def get_android_id():
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        Secure = autoclass('android.provider.Settings$Secure')
        return Secure.getString(activity.getContentResolver(), Secure.ANDROID_ID)
    except Exception as e:
        return f"no-id-{os.urandom(2).hex()}"

ANDROID_SERIAL = get_android_id()

SECRET = "Mn2026_Secret_@#_KEY"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "attendance.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LATEST_FILE = os.path.join(BASE_DIR, "latest_link.txt")
DEFAULT_ADMIN_PASS = "admin2026"
DEFAULT_CFG = {"lecturePass": "", "open": "0", "s": "", "max_active": 32, "stay_seconds": 2.0, "ip_check": True, "nid_check": True, "device_check": True, "hw_check": True, "android_check": True, "black_nids": [], "black_ips": [], "white_ips": [], "after_msg": "✅ تم التسجيل في موبايل الدكتور", "done_msg": f"✅ تم تسجيل حضورك - جهاز {ANDROID_SERIAL[:8]}", "batch": 5, "adminPass": DEFAULT_ADMIN_PASS}
active_ips = OrderedDict()
waiting_queue = OrderedDict()

def get_primary_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "192.168.43.1"

def get_local_ips():
    ips=[get_primary_ip(), "192.168.43.1", "192.168.137.1", "192.168.1.1"]
    return list(set(ips))

def load_cfg():
    if not os.path.exists(CONFIG_FILE):
        c=DEFAULT_CFG.copy()
        with open(CONFIG_FILE,'w',encoding='utf-8') as f: json.dump(c,f,ensure_ascii=False,indent=2)
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
    return f"⏳ فاضل قدامك {pos} - متوقع {time_str}", 3

def find_logo_file(): return None
def get_logo_tag(size=90, with_margin=True): return f'<div style="text-align:center"><div style="width:{size}px;height:{size}px;background:#1a73e8;border-radius:18px;margin:0 auto;color:#fff;display:flex;align-items:center;justify-content:center">🎓</div></div>'
def get_header_logo_tag(): return get_logo_tag(44, False)
def simple_hash(s):
    h=0
    for ch in s: h = ((h << 5) - h) + ord(ch); h = h & 0xFFFFFFFF
    return format(abs(h), '36')

SOCIAL_FOOTER = f"<div style='text-align:center;font-size:11px;color:#64748b'>Serial: {ANDROID_SERIAL} - د.م/ محمود منصور</div>"

def build_att_html():
    cfg=load_cfg()
    LOGO_TAG = get_logo_tag(90, True)
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>حضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}.t1{{font-size:20px;font-weight:800;color:#0f172a}}input{{width:100%;padding:13px 14px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;font-family:'Tajawal';background:#f8fafc;outline:none}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;font-family:'Tajawal';cursor:pointer}}button:disabled{{opacity:.4}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;font-size:15px;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b;border:2px solid #fecaca}}#ok{{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}}#exist,#ipblock,#deviceblock,#hwblock,#androidblock{{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}}#closed{{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}}#timer{{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:800;display:none;margin:10px auto;width:fit-content}}</style></head><body><div class="card">{LOGO_TAG}<div style="text-align:center;line-height:1.7;margin:8px 0 14px 0"><div class="t1">📝 تسجيل الحضور - {ANDROID_SERIAL[:6]}</div></div><div id="timer">⏳ باقي: <span id="t">--:--</span></div><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي"><input id="nid" type="tel" maxlength="14" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div><div id="exist" class="msgbox">⚠️ القومي مسجل</div><div id="ipblock" class="msgbox">❌ IP متكرر</div><div id="deviceblock" class="msgbox">❌ الجهاز سجل</div><div id="hwblock" class="msgbox">❌ بصمة الجهاز متكررة</div><div id="androidblock" class="msgbox">❌ السيريال الحقيقي مسجل - {ANDROID_SERIAL[:8]}</div><div id="closed" class="msgbox">⛔ مقفول</div><div id="wrong" class="msgbox">❌ كلمة السر غلط</div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let isClosedByAdmin=false;
function getHardwareFingerprint(){{try{{let canvas=document.createElement('canvas');let gl=canvas.getContext('webgl');let gpu='no-gpu';if(gl){{let dbg=gl.getExtension('WEBGL_debug_renderer_info');if(dbg)gpu=gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);}}let fp=[navigator.userAgent,navigator.platform,screen.width+'x'+screen.height,gpu].join('|');let h=0;for(let i=0;i<fp.length;i++){{h=((h<<5)-h)+fp.charCodeAt(i);h=h&h;}}return 'hw_'+Math.abs(h).toString(36);}}catch(e){{return 'hw_err';}}}}
function getAndroidId(){{return "{ANDROID_SERIAL}";}}
function getDeviceId(){{let s=localStorage.getItem('device_fingerprint');if(s)return s;let hw=getHardwareFingerprint();let id=hw+'_'+Math.random().toString(36).slice(2,6);localStorage.setItem('device_fingerprint',id);return id;}}
function isAlreadyRegisteredLocally(){{return localStorage.getItem('already_registered_'+getDeviceId())==='1';}}
function markAsRegistered(nid){{localStorage.setItem('already_registered_'+getDeviceId(),'1');localStorage.setItem('my_nid_registered',nid);}}
function applyAlreadyRegisteredUI(){{if(isAlreadyRegisteredLocally()){{let b=document.getElementById('btn');b.disabled=true;b.innerText='✅ سجلت قبل كده';document.getElementById('closed').style.display='block';document.getElementById('closed').innerText='✅ سجلت قبل كده - جهاز واحد = طالب واحد';return true;}}return false;}}
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server - Date.now();}}catch(e){{}}}}
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
function getParams(){{let p=new URLSearchParams(location.search);return {{open:p.get('open'),s:p.get('s')}};}}let cached=getParams();
function showMsg(t,id){{let b=document.getElementById('msgBox');b.innerText=t;b.style.display='block';}}
function hideAll(){{['ok','exist','ipblock','deviceblock','hwblock','androidblock','wrong','closed','msgBox'].forEach(x=>{{let el=document.getElementById(x);if(el)el.style.display='none';}});}}
function forceCloseAll(msg){{isClosedByAdmin=true;document.getElementById('closed').style.display='block';document.getElementById('closed').innerText=msg||'⛔ مقفول';document.getElementById('btn').disabled=true;}}
function updateTimer(){{let {{open,s}}=cached;let btn=document.getElementById('btn'),cl=document.getElementById('closed'),tm=document.getElementById('timer');if(applyAlreadyRegisteredUI()){{tm.style.display='none';return;}}if(!open||!s||simpleHash(open+SECRET)!==s){{tm.style.display='none';cl.style.display='none';btn.disabled=false;return;}}let v=parseInt(open);if(nowSynced()>v){{tm.style.display='none';cl.style.display='block';cl.innerText='⛔ انتهى الوقت';btn.disabled=true;return;}}tm.style.display='block';cl.style.display='none';btn.disabled=false;let d=v-nowSynced(),m=Math.floor(d/60000),sc=Math.floor((d%60000)/1000);document.getElementById('t').innerText=m+':'+(sc<10?'0':'')+sc;}}
syncTime().then(()=>{{setInterval(updateTimer,1000);updateTimer();}});
async function sendData(){{hideAll();let p=document.getElementById('pass').value.trim(),b=document.getElementById('board').value.trim(),n=document.getElementById('name').value.trim(),id=document.getElementById('nid').value.trim();let {{open,s}}=cached;if(!p||!b||!n||!id){{showMsg('❌ اكمل البيانات');return;}}try{{let deviceId=getDeviceId(),hwId=getHardwareFingerprint(),androidId=getAndroidId();let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:open||'',s:s||'',name:n,nid:id,board:b,pass:p,deviceId,hwId,androidId}})}});hideAll();if(r.status==200){{markAsRegistered(id);document.getElementById('ok').style.display='block';let d=await r.json();if(d.redirect)location.href=d.redirect;}}else if(r.status==409){{document.getElementById('exist').style.display='block';markAsRegistered(id);}}else if(r.status==410){{document.getElementById('ipblock').style.display='block';markAsRegistered(id);}}else if(r.status==411){{document.getElementById('deviceblock').style.display='block';markAsRegistered(id);}}else if(r.status==412){{document.getElementById('hwblock').style.display='block';markAsRegistered(id);}}else if(r.status==413){{document.getElementById('androidblock').style.display='block';markAsRegistered(id);}}else if(r.status==401){{document.getElementById('wrong').style.display='block';}}else{{document.getElementById('closed').style.display='block';}}}}catch(e){{showMsg('❌ مش متصل');}}}}
</script></body></html>"""

def build_admin_html():
    cfg=load_cfg()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>Admin</title><style>body{{font-family:Tahoma;padding:12px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ccc;padding:8px;text-align:center}}th{{background:#0f172a;color:#fff}}.btn{{padding:8px 12px;border:none;border-radius:8px;cursor:pointer}}.btn-success{{background:#16a34a;color:#fff}}.btn-danger{{background:#dc2626;color:#fff}}</style></head><body><h2>لوحة تحكم - Serial {ANDROID_SERIAL}</h2><p>IP: {', '.join(get_local_ips())}:8080</p><div><label>كلمة سر المحاضرة</label><input id="lecturePass"><label>المدة دقائق</label><input id="minutes" type="number" value="5"><button onclick="openNow()" class="btn btn-success">فتح</button><button onclick="closeNow()" class="btn btn-danger">قفل</button></div><div id="shareBox" style="display:none"><input id="shareLink" style="width:80%"><button onclick="navigator.clipboard.writeText(document.getElementById('shareLink').value)">نسخ</button></div><h3>المسجلين <span id="count">0</span></h3><table id="tbl"><thead><tr><th>#</th><th>الاسم</th><th>القومي</th><th>IP</th><th>HW</th><th>Android</th><th>السبورة</th></tr></thead><tbody></tbody></table><script>
const SECRET="Mn2026_Secret_@#_KEY";let lastOpen="",lastSig="";function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
async function openNow(){{let lp=document.getElementById('lecturePass').value.trim();let mins=parseInt(document.getElementById('minutes').value);let u=Date.now()+mins*60*1000;let sig=simpleHash(u.toString()+SECRET);lastOpen=u.toString();lastSig=sig;document.getElementById('shareBox').style.display='block';document.getElementById('shareLink').value=location.origin+'/attendance.html?open='+u+'&s='+sig;await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:u.toString(),s:sig,lecturePass:lp}})}});}}
async function closeNow(){{await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:"0",s:"",lecturePass:""}})}});}}
async function refresh(){{let r=await fetch('/list');let d=await r.json();document.getElementById('count').innerText=d.list.length;let tb=document.querySelector('#tbl tbody');tb.innerHTML='';d.list.forEach((x,i)=>{{tb.innerHTML+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td>${{x.nid}}</td><td>${{x.ip}}</td><td>${{x.hwId}}</td><td>${{x.androidId}}</td><td>${{x.board}}</td></tr>`;}});}}
setInterval(refresh,1500);
</script></body></html>"""

def ensure_files():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,'w',encoding='utf-8') as f: f.write("[]")
    if not os.path.exists(CONFIG_FILE):
        save_cfg(DEFAULT_CFG.copy())

ensure_files()

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]
        cfg=load_cfg()
        if self.path == '/set_config':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            cfg["lecturePass"]=data.get('lecturePass','')
            cfg["open"]=data.get('open','0')
            cfg["s"]=data.get('s','')
            save_cfg(cfg)
            self.send_response(200); self.end_headers(); return
        if self.path == '/save':
            try:
                length = int(self.headers.get('content-length',0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                now_ms = int(datetime.now().timestamp()*1000)
                cfg_open = cfg.get('open','0')
                if cfg_open == "0" or cfg_open == "" or int(cfg_open) < now_ms:
                    self.send_response(403); self.end_headers(); return
                if cfg.get('lecturePass','').strip() and data.get('pass','').strip()!= cfg.get('lecturePass','').strip():
                    self.send_response(401); self.end_headers(); return
                nid = data.get('nid','').strip()
                deviceId = data.get('deviceId','').strip()
                hwId = data.get('hwId','').strip()
                androidId = data.get('androidId','').strip()
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
                if cfg.get('hw_check',True) and hwId and any(x.get('hwId')==hwId for x in all_data):
                    self.send_response(412); self.end_headers(); return
                if cfg.get('android_check',True) and androidId and any(x.get('androidId')==androidId and x.get('androidId')!='' for x in all_data):
                    self.send_response(413); self.end_headers(); return
                rec={"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"name":data.get('name',''),"nid":nid,"board":data.get('board',''),"ip":client_ip,"deviceId":deviceId,"hwId":hwId,"androidId":androidId}
                all_data.append(rec)
                with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(all_data,f,ensure_ascii=False,indent=2)
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"ok":True,"redirect":"/done"}).encode('utf-8'))
            except Exception as e:
                print(e); self.send_response(500); self.end_headers()
            return
        self.send_response(404); self.end_headers()

    def do_GET(self):
        cfg=load_cfg()
        low = self.path.lower()
        if self.path == '/time':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"server": int(datetime.now().timestamp()*1000)}).encode('utf-8')); return
        if low == '/list':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            data=[]
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE,'r',encoding='utf-8') as f:
                    try: data=json.load(f)
                    except: data=[]
            self.wfile.write(json.dumps({"list":data}).encode('utf-8')); return
        if low == '/done' or low == '/done.html':
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"<html dir='rtl'><body style='text-align:center;padding:30px;font-family:Tahoma'><h1 style='color:green'>{cfg['done_msg']}</h1><p>Serial: {ANDROID_SERIAL}</p><p>تم تسجيل حضورك - جهاز واحد = طالب واحد</p></body></html>".encode('utf-8')); return
        if 'attendance' in low or low == '/' or low == '/index.html' or low == '/go':
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(build_att_html().encode('utf-8')); return
        if 'admin' in low:
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(build_admin_html().encode('utf-8')); return
        return super().do_GET()

def start_server():
    http.server.HTTPServer(('0.0.0.0',8080), Handler).serve_forever()

class MansourApp(App):
    def build(self):
        self.title = f"Mansour Attendance - {ANDROID_SERIAL[:8]}"
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        self.lbl = Label(text=f"🚀 السيرفر شغال\\nSerial الحقيقي:\\n{ANDROID_SERIAL}\\n\\nIP: 192.168.43.1:8080\\nadmin.html", halign='center')
        btn = Button(text="فتح لوحة الادمن", size_hint_y=None, height=60)
        btn.bind(on_press=lambda x: self.open_admin())
        layout.add_widget(self.lbl)
        layout.add_widget(btn)
        threading.Thread(target=start_server, daemon=True).start()
        Clock.schedule_interval(self.update_ip, 2)
        return layout
    def update_ip(self, dt):
        self.lbl.text = f"🚀 شغال\\nSerial: {ANDROID_SERIAL}\\nIPs: {', '.join(get_local_ips())}:8080"
    def open_admin(self):
        try:
            import webbrowser
            webbrowser.open("http://192.168.43.1:8080/admin.html")
        except: pass

if __name__ == '__main__':
    MansourApp().run()
