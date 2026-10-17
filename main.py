from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
import threading, http.server, json, os, base64, socket, re, subprocess, urllib.parse, mimetypes, uuid
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
        print(f"Android ID fallback: {e}")
        return f"fallback_{str(uuid.getnode())[-8:]}"

ANDROID_SERIAL = get_android_id()

SECRET = "Mn2026_Secret_@#_KEY"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "attendance.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LATEST_FILE = os.path.join(BASE_DIR, "latest_link.txt")
DEFAULT_ADMIN_PASS = "admin2026"
DEFAULT_CFG = {"lecturePass": "", "open": "0", "s": "", "max_active": 32, "stay_seconds": 2.0, "ip_check": True, "nid_check": True, "device_check": True, "hw_check": True, "android_check": True, "black_nids": [], "black_ips": [], "white_ips": [], "after_msg": "✅ تم التسجيل في موبايل الدكتور", "done_msg": f"✅ تم تسجيل حضورك - جهاز {ANDROID_SERIAL[:8]} - توجه لمعمل 3", "batch": 5, "adminPass": DEFAULT_ADMIN_PASS}
active_ips = OrderedDict()
waiting_queue = OrderedDict()

def get_interface_ips():
    ips = []
    try:
        out = subprocess.check_output("ip addr show", shell=True, timeout=2, stderr=subprocess.STDOUT).decode('utf-8','ignore')
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
    return "192.168.43.1"

def get_local_ips():
    ips = []
    seen = set()
    for ip in get_interface_ips():
        if ip not in seen: ips.append(ip); seen.add(ip)
    primary = get_primary_ip()
    if primary and primary not in seen: ips.append(primary); seen.add(primary)
    for common in ["192.168.43.1", "192.168.137.1", "192.168.49.1", "192.168.0.100"]:
        if common not in seen: ips.append(common); seen.add(common)
    return list(set(ips))

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
    return f"⏳ فاضل قدامك {pos} - متوقع {time_str}", 3

def find_logo_file(): return None
def get_logo_tag(size=90, with_margin=True):
    return f'<div style="text-align:center;margin-bottom:12px"><div style="width:{size}px;height:{size}px;background:linear-gradient(135deg,#1a73e8,#0f172a);border-radius:18px;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:30px;font-weight:800">🎓</div></div>'
def get_header_logo_tag():
    return '<div style="width:44px;height:44px;background:linear-gradient(135deg,#60a5fa,#1d4ed8);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff">🎓</div>'

def simple_hash(s):
    h=0
    for ch in s:
        h = ((h << 5) - h) + ord(ch)
        h = h & 0xFFFFFFFF
        if h >= 0x80000000: h -= 0x100000000
    return format(abs(h), '36')

SOCIAL_FOOTER = f"""<div style="margin-top:28px;padding:12px;text-align:center;background:#f8fafc;border-radius:12px;font-size:11px;color:#64748b"><div>Serial: {ANDROID_SERIAL}</div><div>الكلية التكنولوجية بالمحلة - د.م/ محمود منصور</div><div>© 2026</div></div>"""

def build_att_html():
    cfg=load_cfg()
    LOGO_TAG = get_logo_tag(90, True)
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>حضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}.t1{{font-size:20px;font-weight:800;color:#0f172a}}input{{width:100%;padding:13px 14px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;font-family:'Tajawal';background:#f8fafc;outline:none}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;font-family:'Tajawal';cursor:pointer}}button:disabled{{opacity:.4}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;font-size:15px;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b;border:2px solid #fecaca}}#ok{{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}}#exist,#ipblock,#deviceblock,#hwblock,#androidblock,#wrong,#black{{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}}#closed{{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}}#timer{{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:800;display:none;margin:10px auto;width:fit-content}}</style></head><body><div class="card">{LOGO_TAG}<div style="text-align:center;line-height:1.7;margin:8px 0 14px 0"><div class="t1">📝 تسجيل الحضور</div><div style="font-size:12px;color:#64748b">Serial: {ANDROID_SERIAL[:8]}</div></div><div id="timer">⏳ باقي: <span id="t">--:--</span></div><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" inputmode="numeric" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي عربي"><input id="nid" type="tel" maxlength="14" inputmode="numeric" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div><div id="exist" class="msgbox">⚠️ القومي مسجل</div><div id="ipblock" class="msgbox">❌ IP مسجل</div><div id="deviceblock" class="msgbox">❌ الجهاز سجل قبل كده - VPN</div><div id="hwblock" class="msgbox">❌ بصمة الجهاز متكررة HW</div><div id="androidblock" class="msgbox">❌ السيريال الحقيقي مسجل {ANDROID_SERIAL[:8]}</div><div id="closed" class="msgbox">⛔ مقفول</div><div id="wrong" class="msgbox">❌ كلمة السر غلط</div><div id="black" class="msgbox">⛔ محظور</div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let isClosedByAdmin=false;
function getHardwareFingerprint(){{
  try{{
    let canvas=document.createElement('canvas');let gl=canvas.getContext('webgl')||canvas.getContext('experimental-webgl');let gpu='no-gpu';
    if(gl){{let dbg=gl.getExtension('WEBGL_debug_renderer_info');if(dbg){{gpu=gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)+'_'+gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);}}}}
    let fp=[navigator.userAgent,navigator.platform,navigator.language,screen.width+'x'+screen.height+'x'+screen.colorDepth,Intl.DateTimeFormat().resolvedOptions().timeZone,navigator.hardwareConcurrency||'0',gpu].join('|');
    let h=0;for(let i=0;i<fp.length;i++){{h=((h<<5)-h)+fp.charCodeAt(i);h=h&h;}}return 'hw_'+Math.abs(h).toString(36);
  }}catch(e){{return 'hw_err_'+Math.random().toString(36).slice(2);}}
}}
function getAndroidId(){{return "{ANDROID_SERIAL}";}}
function getDeviceId(){{let stored=localStorage.getItem('device_fingerprint')||sessionStorage.getItem('device_fingerprint');if(stored)return stored;let hw=getHardwareFingerprint();let id=hw+'_'+Math.random().toString(36).slice(2,8);localStorage.setItem('device_fingerprint',id);sessionStorage.setItem('device_fingerprint',id);return id;}}
function isAlreadyRegisteredLocally(){{return localStorage.getItem('already_registered_'+getDeviceId())==='1'||localStorage.getItem('my_nid_registered')!==null;}}
function markAsRegistered(nid){{localStorage.setItem('already_registered_'+getDeviceId(),'1');localStorage.setItem('my_nid_registered',nid);}}
function applyAlreadyRegisteredUI(){{if(isAlreadyRegisteredLocally()){{let btn=document.getElementById('btn');btn.disabled=true;btn.innerText='✅ سجلت قبل كده';document.getElementById('closed').style.display='block';document.getElementById('closed').innerText='✅ سجلت قبل كده - جهاز واحد = طالب واحد';return true;}}return false;}}
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server - Date.now();}}catch(e){{}}}}
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
function getParams(){{let p=new URLSearchParams(location.search);return {{open:p.get('open'),s:p.get('s')}};}}let cached=getParams();
function showMsg(t){{let b=document.getElementById('msgBox');b.innerText=t;b.style.display='block';}}
function hideAll(){{['ok','exist','ipblock','deviceblock','hwblock','androidblock','wrong','closed','msgBox'].forEach(x=>{{let el=document.getElementById(x);if(el)el.style.display='none';}});}}
function forceCloseAll(msg){{isClosedByAdmin=true;let cl=document.getElementById('closed');cl.style.display='block';cl.innerText=msg||'⛔ مقفول';document.getElementById('btn').disabled=true;}}
function updateTimer(){{if(isClosedByAdmin)return;let {{open,s}}=cached;let btn=document.getElementById('btn'),cl=document.getElementById('closed'),tm=document.getElementById('timer');if(applyAlreadyRegisteredUI()){{tm.style.display='none';return;}}if(!open||!s||simpleHash(open+SECRET)!==s){{tm.style.display='none';cl.style.display='none';btn.disabled=false;return;}}let v=parseInt(open);if(nowSynced()>v){{tm.style.display='none';cl.style.display='block';cl.innerText='⛔ انتهى الوقت';btn.disabled=true;return;}}tm.style.display='block';cl.style.display='none';btn.disabled=false;let d=v-nowSynced(),m=Math.floor(d/60000),sc=Math.floor((d%60000)/1000);document.getElementById('t').innerText=m+':'+(sc<10?'0':'')+sc;}}
async function checkIfClosedByAdmin(){{try{{let r=await fetch('/get_config');let j=await r.json();if(!j.open||j.open=="0"||parseInt(j.open)<nowSynced()){{forceCloseAll('⛔ الادمن قفل التسجيل');}}}}catch(e){{}}}}
syncTime().then(()=>{{applyAlreadyRegisteredUI();setInterval(updateTimer,1000);updateTimer();setInterval(checkIfClosedByAdmin,2000);}});
async function sendData(){{if(isAlreadyRegisteredLocally()){{applyAlreadyRegisteredUI();return;}}hideAll();let p=document.getElementById('pass').value.trim(),b=document.getElementById('board').value.trim(),n=document.getElementById('name').value.trim(),id=document.getElementById('nid').value.trim();let {{open,s}}=cached;if(!p||!b||!n||!id){{showMsg('❌ اكمل البيانات');return;}}try{{let deviceId=getDeviceId(),hwId=getHardwareFingerprint(),androidId=getAndroidId(),ua=navigator.userAgent;let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:open||'',s:s||'',name:n,nid:id,board:b,pass:p,deviceId,hwId,androidId,ua}})}});hideAll();if(r.status==200){{markAsRegistered(id);document.getElementById('ok').style.display='block';let d=await r.json();if(d.redirect)location.href=d.redirect;}}else if(r.status==409){{document.getElementById('exist').style.display='block';markAsRegistered(id);}}else if(r.status==410){{document.getElementById('ipblock').style.display='block';markAsRegistered(id);}}else if(r.status==411){{document.getElementById('deviceblock').style.display='block';markAsRegistered(id);}}else if(r.status==412){{document.getElementById('hwblock').style.display='block';markAsRegistered(id);}}else if(r.status==413){{document.getElementById('androidblock').style.display='block';markAsRegistered(id);}}else if(r.status==401){{document.getElementById('wrong').style.display='block';}}else{{document.getElementById('closed').style.display='block';}}}}catch(e){{showMsg('❌ مش متصل');}}}}
</script></body></html>"""

def build_admin_html():
    cfg=load_cfg()
    LOGO_TAG = get_logo_tag(90, True)
    HEADER_LOGO = get_header_logo_tag()
    ips = get_local_ips()
    ips_html = ", ".join(ips)
    router_ip = ips[0] if ips else "192.168.43.1"
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة التحكم Pro</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><style>body{{margin:0;font-family:'Tajawal',Tahoma;background:#f5f7fb;padding:12px}} .container{{max-width:1100px;margin:0 auto}} .header{{background:#0f172a;color:#fff;padding:16px;border-radius:20px;display:flex;justify-content:space-between;align-items:center}} .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:14px 0}} .stat{{background:#fff;border-radius:16px;padding:14px;text-align:center;border:1px solid #e2e8f0}} .stat b{{display:block;font-size:26px;color:#1a73e8}} .card{{background:#fff;border-radius:18px;padding:16px;border:1px solid #e2e8f0;margin-bottom:14px}} label{{font-size:12px;font-weight:700;display:block;margin-top:8px}} input,textarea{{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:12px;font-family:'Tajawal';background:#f8fafc}} .btn{{padding:12px 16px;border:none;border-radius:12px;font-weight:800;font-family:'Tajawal';cursor:pointer}} .btn-success{{background:#16a34a;color:#fff}} .btn-danger{{background:#dc2626;color:#fff}} .btn-dark{{background:#0f172a;color:#fff}} table{{width:100%;border-collapse:collapse}} th{{background:#0f172a;color:#fff;padding:10px}} td{{padding:8px;border-bottom:1px solid #eee;text-align:center;font-size:12px}} #loginBox{{max-width:400px;margin:50px auto;background:#fff;padding:24px;border-radius:22px;text-align:center}}</style></head><body><div id="loginBox">{LOGO_TAG}<h2>دخول لوحة الادمن</h2><p style="font-size:12px;color:#64748b">Serial: {ANDROID_SERIAL}</p><input id="adminPass" type="password" placeholder="باسورد الادمن"><button onclick="login()" class="btn btn-dark" style="width:100%;margin-top:12px">دخول</button><p id="loginErr" style="display:none;color:red">كلمة السر خطأ</p></div><div id="dash" class="container" style="display:none"><div class="header"><div style="display:flex;gap:10px;align-items:center">{HEADER_LOGO}<div><div style="font-weight:800">لوحة تحكم الحضور Pro - {ANDROID_SERIAL[:6]}</div><div style="font-size:11px;opacity:.8">IP: {ips_html}</div></div></div><button onclick="logout()" class="btn" style="background:#fff;color:#000">خروج</button></div><div class="stats"><div class="stat"><b id="count">0</b><span>إجمالي</span></div><div class="stat"><b id="activeCount">0</b><span>النشط</span></div><div class="stat"><b id="waitCount">0</b><span>انتظار</span></div></div><div class="card"><h3>فتح المحاضرة</h3><label>كلمة سر المحاضرة</label><input id="lecturePass" placeholder="مثال 2026"><label>المدة بالدقائق</label><input id="minutes" type="number" value="5"><div style="display:flex;gap:8px;margin-top:10px"><button onclick="openNow()" class="btn btn-success" style="flex:2">✅ افتح</button><button onclick="closeNow()" class="btn btn-danger" style="flex:1">⛔ اقفل</button></div><div id="shareBox" style="display:none;background:#e0f2fe;padding:10px;border-radius:12px;margin-top:10px"><input id="shareLinkLocal" readonly style="direction:ltr"><button onclick="copyById('shareLinkLocal')" class="btn btn-dark">نسخ</button></div></div><div class="card"><h3>البيانات - HW + AndroidID</h3><div style="overflow:auto"><table id="tbl"><thead><tr><th>#</th><th>الوقت</th><th>الاسم</th><th>القومي</th><th>IP</th><th>HW</th><th>AndroidID</th><th>السبورة</th><th>حذف</th></tr></thead><tbody></tbody></table></div><button onclick="clearData()" class="btn btn-danger" style="margin-top:10px">مسح الكل</button></div></div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let lastOpen="",lastSig="";
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server - Date.now();}}catch(e){{}}}} 
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
async function checkAuth(){{if(localStorage.getItem('admin_ok')==='1'){{document.getElementById('loginBox').style.display='none';document.getElementById('dash').style.display='block';await syncTime();refresh();setInterval(refresh,1500);}}}}
function buildAllLinks(){{let host=location.host;let path='/attendance.html?open='+lastOpen+'&s='+lastSig;document.getElementById('shareLinkLocal').value=location.protocol+'//'+host+path;}}
function copyById(id){{let el=document.getElementById(id);el.select();document.execCommand('copy');alert('تم النسخ: '+el.value);}}
async function login(){{let p=document.getElementById('adminPass').value;let r=await fetch('/admin_auth',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{pass:p}})}});let d=await r.json();if(d.ok){{localStorage.setItem('admin_ok','1');checkAuth();}}else{{document.getElementById('loginErr').style.display='block';}}}}
function logout(){{localStorage.removeItem('admin_ok');location.reload();}}
async function openNow(){{let lp=document.getElementById('lecturePass').value.trim();let mins=parseInt(document.getElementById('minutes').value);if(!lp){{alert('اكتب كلمة السر');return;}}let u=nowSynced()+mins*60*1000;let sig=simpleHash(u.toString()+SECRET);lastOpen=u.toString();lastSig=sig;buildAllLinks();document.getElementById('shareBox').style.display='block';await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:u.toString(),s:sig,lecturePass:lp}})}});}}
async function closeNow(){{await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:"0",s:"",lecturePass:""}})}});document.getElementById('shareBox').style.display='none';}}
let cachedData=[];
async function refresh(){{try{{let r=await fetch('/list');let d=await r.json();cachedData=d.list||[];document.getElementById('count').innerText=cachedData.length;document.getElementById('activeCount').innerText=d.active;document.getElementById('waitCount').innerText=d.waiting;let tb=document.querySelector('#tbl tbody');tb.innerHTML='';cachedData.forEach((x,i)=>{{tb.innerHTML+=`<tr><td>${{i+1}}</td><td>${{x.time}}</td><td>${{x.name}}</td><td>${{x.nid}}</td><td>${{x.ip}}</td><td>${{(x.hwId||'').slice(0,8)}}</td><td>${{(x.androidId||'').slice(0,8)}}</td><td>${{x.board}}</td><td><button onclick="deleteOne('${{x.nid}}')" class="btn btn-danger" style="padding:4px">حذف</button></td></tr>`;}});}}catch(e){{}}}}
async function deleteOne(nid){{if(!confirm('تمسح '+nid))return;let r=await fetch('/delete_one',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{nid}})}});let d=await r.json();if(d.ok)refresh();}}
async function clearData(){{if(confirm('تمسح الكل؟')){{await fetch('/clear',{{method:'POST'}});refresh();}}}}
checkAuth();
</script></body></html>"""

def ensure_files():
    cfg=load_cfg()
    save_cfg(cfg)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,"w",encoding="utf-8") as f: f.write("[]")

ensure_files()

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]
        cfg=load_cfg()
        if self.path == '/admin_auth':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            ok = data.get('pass','') == cfg.get('adminPass', DEFAULT_ADMIN_PASS)
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": ok}).encode('utf-8'))
            return
        if self.path == '/delete_one':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            nid_to_del = data.get('nid','').strip()
            deleted=False
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE,'r',encoding='utf-8') as f:
                        all_data=json.load(f)
                    new_data=[x for x in all_data if x.get('nid')!=nid_to_del]
                    if len(new_data)!=len(all_data):
                        deleted=True
                        with open(DATA_FILE,'w',encoding='utf-8') as f:
                            json.dump(new_data,f,ensure_ascii=False,indent=2)
                except: pass
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": deleted}).encode('utf-8'))
            return
        if self.path == '/set_config':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            cfg["lecturePass"]=data.get('lecturePass','')
            cfg["open"]=data.get('open','0')
            cfg["s"]=data.get('s','')
            save_cfg(cfg)
            try:
                if cfg["open"]!="0" and cfg["open"]!="":
                    link = f"/attendance.html?open={cfg['open']}&s={cfg['s']}"
                    with open(LATEST_FILE,'w',encoding='utf-8') as f:
                        f.write(link)
                else:
                    if os.path.exists(LATEST_FILE):
                        os.remove(LATEST_FILE)
            except: pass
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
                ua = data.get('ua','')[:200]
                is_white = client_ip in cfg.get('white_ips',[]) or client_ip == '127.0.0.1'
                all_data=[]
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE,'r',encoding='utf-8') as f:
                        try: all_data=json.load(f)
                        except: all_data=[]
                if cfg.get('nid_check',True) and any(x.get('nid')==nid for x in all_data):
                    self.send_response(409); self.end_headers(); return
                if cfg.get('ip_check',True) and not is_white and any(x.get('ip')==client_ip for x in all_data):
                    self.send_response(410); self.end_headers(); return
                if cfg.get('device_check',True) and deviceId and not is_white and any(x.get('deviceId')==deviceId for x in all_data):
                    self.send_response(411); self.end_headers(); return
                if cfg.get('hw_check',True) and hwId and not is_white and any(x.get('hwId')==hwId for x in all_data):
                    self.send_response(412); self.end_headers(); return
                if cfg.get('android_check',True) and androidId and androidId!='' and not is_white and any(x.get('androidId')==androidId and x.get('androidId')!='' for x in all_data):
                    self.send_response(413); self.end_headers(); return
                max_a = cfg.get('max_active',32)
                if len(active_ips) >= max_a and client_ip not in active_ips and not is_white:
                    if client_ip not in waiting_queue: waiting_queue[client_ip]=datetime.now()
                    pos = list(waiting_queue.keys()).index(client_ip) + 1
                    msg, _ = get_wait_msg(pos, max_a, cfg.get('stay_seconds',2), cfg.get('batch',5))
                    self.send_response(429)
                    self.send_header('Content-Type','application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"pos":pos,"msg":msg}).encode('utf-8')); return
                if client_ip in waiting_queue: del waiting_queue[client_ip]
                active_ips[client_ip]=datetime.now().strftime("%H:%M:%S")
                rec={"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"name":data.get('name',''),"nid":nid,"board":data.get('board',''),"pass":data.get('pass',''),"ip":client_ip,"deviceId":deviceId,"hwId":hwId,"androidId":androidId,"ua":ua}
                all_data.append(rec)
                with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(all_data,f,ensure_ascii=False,indent=2)
                threading.Timer(float(cfg.get('stay_seconds',2.0)), free_ip, args=(client_ip,)).start()
                self.send_response(200)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.end_headers()
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
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        cfg=load_cfg()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = parsed.query
        low = path.lower()
        if low == '/__save_latest':
            params = urllib.parse.parse_qs(query)
            link = params.get('link', [''])[0]
            if link:
                link = urllib.parse.unquote(link)
                try:
                    with open(LATEST_FILE,'w',encoding='utf-8') as f:
                        f.write(link)
                except: pass
            self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers(); self.wfile.write(b'Saved'); return
        if low == '/' or low == '/go' or low == '/index.html' or (low == '/attendance.html' and 'open' not in query):
            if os.path.exists(LATEST_FILE):
                try:
                    with open(LATEST_FILE,'r',encoding='utf-8') as f:
                        latest = f.read().strip()
                    if latest and 'open=' in latest:
                        cfg_open = cfg.get('open','0')
                        if cfg_open!="0" and cfg_open!="" and int(cfg_open) > int(datetime.now().timestamp()*1000):
                            self.send_response(302)
                            self.send_header('Location', latest)
                            self.end_headers()
                            return
                except: pass
        if low == '/my_ips':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            self.wfile.write(json.dumps({"ips": get_local_ips(), "primary": get_primary_ip()}).encode('utf-8'))
            return
        if path == '/time':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"server": int(datetime.now().timestamp()*1000)}).encode('utf-8'))
            return
        if low == '/get_config':
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.end_headers()
            safe_cfg = {k:v for k,v in cfg.items() if k!='adminPass'}
            self.wfile.write(json.dumps(safe_cfg).encode('utf-8'))
            return
        if low == '/list':
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.end_headers()
            data=[]
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE,'r',encoding='utf-8') as f:
                    try: data=json.load(f)
                    except: data=[]
            last_min=0
            try:
                now=datetime.now()
                for x in data:
                    t=datetime.strptime(x['time'],"%Y-%m-%d %H:%M:%S")
                    if (now-t).total_seconds()<=60: last_min+=1
            except: pass
            self.wfile.write(json.dumps({"list":data,"active":len(active_ips),"waiting":len(waiting_queue),"max_active":cfg['max_active'],"last_min":last_min}).encode('utf-8')); return
        if low == '/projector':
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            proj = f"""<html dir="rtl"><body style="background:#000;color:#fff;text-align:center;padding:20px"><h1 id="big">--:--</h1><div>النشط <span id="a">0</span> / {cfg['max_active']} | انتظار <span id="w">0</span></div><script>async function sync(){{let r=await fetch('/time');let d=await r.json();return d.server-Date.now();}} let off=0; sync().then(o=>{{off=o; setInterval(()=>{{let u=localStorage.getItem('openUntil'); if(!u)return; let diff=parseInt(u)-(Date.now()+off); if(diff<=0){{document.getElementById('big').innerText='انتهى';return;}} let m=Math.floor(diff/60000),s=Math.floor((diff%60000)/1000);document.getElementById('big').innerText=m+':'+(s<10?'0':'')+s;}},1000);}}); setInterval(()=>{{fetch('/list').then(r=>r.json()).then(d=>{{document.getElementById('a').innerText=d.active;document.getElementById('w').innerText=d.waiting;}})}},2000);</script></body></html>"""
            self.wfile.write(proj.encode('utf-8')); return
        if low == '/done' or low == '/done.html':
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            done_html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تم</title><style>body{{text-align:center;font-family:Tahoma;padding:15px;background:linear-gradient(135deg,#f0fdf4,#fff)}}.card{{max-width:440px;margin:auto;background:#fff;padding:20px;border-radius:20px}}</style></head><body><div class="card"><h1 style="color:#16a34a">{cfg['done_msg']}</h1><p>Serial: {ANDROID_SERIAL}</p><p>النشط {len(active_ips)}/{cfg['max_active']}</p><p style="font-size:12px">جهاز واحد = طالب واحد - HW + AndroidID</p></div></body></html>"""
            self.wfile.write(done_html.encode('utf-8')); return
        if 'attendance' in low or low == '/' or low == '/index.html':
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
    print(f"=== شغال 0.0.0.0:8080 - Serial {ANDROID_SERIAL} - HW + AndroidID ===")
    http.server.HTTPServer(('0.0.0.0',8080), Handler).serve_forever()

class MansourApp(App):
    def build(self):
        self.title = f"Mansour Attendance - {ANDROID_SERIAL[:6]}"
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        self.lbl = Label(text=f"🚀 السيرفر شغال\nSerial:\n{ANDROID_SERIAL}\n\nIP: 192.168.43.1:8080\nadmin.html", halign='center')
        btn = Button(text="فتح لوحة الادمن", size_hint_y=None, height=60)
        btn.bind(on_press=lambda x: self.open_admin())
        layout.add_widget(self.lbl)
        layout.add_widget(btn)
        threading.Thread(target=start_server, daemon=True).start()
        Clock.schedule_interval(self.update_ip, 2)
        return layout
    def update_ip(self, dt):
        ips = get_local_ips()
        self.lbl.text = f"🚀 شغال\nSerial: {ANDROID_SERIAL}\nIPs: {', '.join(ips)}:8080"
    def open_admin(self):
        try:
            import webbrowser
            webbrowser.open("http://192.168.43.1:8080/admin.html")
        except: pass

if __name__ == '__main__':
    MansourApp().run()
