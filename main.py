from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.core.text import LabelBase
import http.server, json, os, threading, base64, socket, re, subprocess
from datetime import datetime
from collections import OrderedDict
import urllib.parse, mimetypes, socketserver

# --- دعم اللغة العربية وشكل النصوص ---
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except ImportError:
    HAS_ARABIC_SUPPORT = False

def ar(text):
    if not text:
        return ""
    if HAS_ARABIC_SUPPORT:
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            return str(text)
    return str(text)

SYSTEM_ARABIC_FONT = None
FONT_CANDIDATES = [
    "Amiri-Regular.ttf",
    "/system/fonts/NotoNaskhArabic-Regular.ttf",
    "/system/fonts/DroidSansArabic.ttf",
    "/system/fonts/NotoColorEmoji.ttf",
    "arial.ttf",
    "tajawal.ttf"
]
for font_path in FONT_CANDIDATES:
    if os.path.exists(font_path):
        SYSTEM_ARABIC_FONT = font_path
        break

if SYSTEM_ARABIC_FONT:
    try:
        LabelBase.register(name="ArabicFont", fn_regular=SYSTEM_ARABIC_FONT)
        DEFAULT_FONT_NAME = "ArabicFont"
    except Exception:
        DEFAULT_FONT_NAME = None
else:
    DEFAULT_FONT_NAME = None

def get_android_id():
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        Secure = autoclass('android.provider.Settings$Secure')
        return Secure.getString(activity.getContentResolver(), Secure.ANDROID_ID)
    except:
        return f"no-id-{os.urandom(2).hex()}"

ANDROID_SERIAL = get_android_id()
SECRET = "Mn2026_Secret_@#_KEY"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = BASE_DIR
DATA_FILE = os.path.join(DATA_DIR, "attendance.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LATEST_FILE = os.path.join(DATA_DIR, "latest_link.txt")

def configure_storage(app=None):
    global DATA_DIR, DATA_FILE, CONFIG_FILE, LATEST_FILE
    target = BASE_DIR
    try:
        if app is not None and getattr(app, "user_data_dir", None):
            target = app.user_data_dir
    except Exception:
        pass
    try:
        os.makedirs(target, exist_ok=True)
    except Exception:
        pass
    DATA_DIR = target
    DATA_FILE = os.path.join(DATA_DIR, "attendance.json")
    CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
    LATEST_FILE = os.path.join(DATA_DIR, "latest_link.txt")

DEFAULT_ADMIN_PASS = "mansour2026"
DEFAULT_CFG = {
    "lecturePass": "", "open": "0", "s": "", "max_active": 32, "stay_seconds": 2.0,
    "ip_check": False, "nid_check": True, "device_check": True, "hw_check": False,
    "android_check": True, "black_nids": [], "black_ips": [], "white_ips": [],
    "after_msg": "✅ تم التسجيل في موبايل الدكتور",
    "done_msg": "✅ تم تسجيل حضورك - توجه لمعمل 3 عند م/ احمد",
    "batch": 5, "adminPass": DEFAULT_ADMIN_PASS, "local_app_enabled": True, "lang": "ar"
}
active_ips = OrderedDict()
waiting_queue = OrderedDict()

def get_real_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except:
        pass
    try:
        ips = get_interface_ips()
        for ip in ips:
            if not ip.startswith("127."):
                return ip
    except:
        pass
    return "192.168.43.1"

def get_interface_ips():
    ips = []
    try:
        out = ""
        for cmd in ["ip addr show", "ip -4 addr", "ifconfig"]:
            try:
                out = subprocess.check_output(cmd, shell=True, timeout=2, stderr=subprocess.STDOUT).decode('utf-8','ignore')
                if "inet " in out: break
            except: continue
        found = re.findall(r'inet\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.\d+\.\d+\.\d+)', out)
        for ip in found:
            if not ip.startswith("127.") and ip not in ips: ips.append(ip)
    except: pass
    return ips

def get_local_ips():
    ips = []
    seen = set()
    for ip in get_interface_ips():
        if ip not in seen: ips.append(ip); seen.add(ip)
    primary = get_real_ip()
    if primary and primary not in seen: ips.insert(0, primary); seen.add(primary)
    return ips

def normalize_nid(value):
    value = str(value or '').strip()
    trans = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
    return value.translate(trans)

def valid_national_id(value):
    nid = normalize_nid(value)
    if not re.fullmatch(r'\d{14}', nid):
        return False
    century = {'2': 1900, '3': 2000}.get(nid[0])
    if not century:
        return False
    try:
        year = century + int(nid[1:3])
        month = int(nid[3:5])
        day = int(nid[5:7])
        datetime(year, month, day)
        governorate = int(nid[7:9])
        if not (1 <= governorate <= 88):
            return False
    except (ValueError, TypeError):
        return False
    return True

def load_cfg():
    if not os.path.exists(CONFIG_FILE):
        c = DEFAULT_CFG.copy()
        save_cfg(c)
        return c
    try:
        with open(CONFIG_FILE,'r',encoding='utf-8') as f:
            d = json.load(f)
            for k,v in DEFAULT_CFG.items():
                if k not in d: d[k]=v
            return d
    except: return DEFAULT_CFG.copy()

def save_cfg(c):
    try:
        with open(CONFIG_FILE,'w',encoding='utf-8') as f: json.dump(c,f,ensure_ascii=False,indent=2)
    except: pass

def free_ip(ip):
    if ip in active_ips: del active_ips[ip]
    if ip in waiting_queue: del waiting_queue[ip]

def find_logo_file():
    for n in ["logo.jpg","logo.jpeg","logo.png","logo.webp","logo.JPG","logo.PNG","LOGO.jpg","LOGO.png","logo.jfif","institute.jpg"]:
        p = os.path.join(BASE_DIR, n)
        if os.path.exists(p): return p
    try:
        for f in os.listdir(BASE_DIR):
            lf = f.lower()
            if lf.endswith(('.jpg','.jpeg','.png','.webp','.jfif')) and ('logo' in lf or 'شعار' in lf or 'institute' in lf or 'معهد' in lf):
                return os.path.join(BASE_DIR, f)
    except: pass
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
        except: pass
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

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:10px"><a href="https://twitter.com/eng_mahmoud_man?s=07" target="_blank" style="width:36px;height:36px;background:#000;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-weight:800;font-size:14px">𝕏</a><a href="https://github.com/natiga-script" target="_blank" style="width:36px;height:36px;background:#0f172a;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:11px;font-weight:800">GH</a><a href="https://www.facebook.com/profile.php?id=100009579078219" target="_blank" style="width:36px;height:36px;background:#1877F2;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-weight:800">f</a><a href="https://www.linkedin.com/in/eng-mahmoud-mansour" target="_blank" style="width:36px;height:36px;background:#0A66C2;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:12px;font-weight:800">in</a><a href="https://www.instagram.com/eng_mahmoud_mansour/" target="_blank" style="width:36px;height:36px;background:radial-gradient(circle at 30% 107%,#fdf497 0%,#fdf497 5%,#fd5949 45%,#d6249f 60%,#285AEB 90%);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:11px;font-weight:800">IG</a></div><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div>المعهد الصناعي بالمحلة</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div><div style="margin-top:6px;font-size:10px">© حقوق محفوظة لـ م/ محمود منصور 2026</div></div></div>"""

def build_att_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    real_ip = get_real_ip()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>تسجيل الحضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}.header-lines{{text-align:center;line-height:1.7;margin:8px 0 14px 0}}.t1{{font-size:20px;font-weight:800;color:#0f172a}}.t2{{font-size:13px;color:#334155}}.t3{{font-size:13px;color:#334155}}.t4{{font-size:14px;font-weight:800;color:#1a73e8}}input{{width:100%;padding:13px 14px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;font-family:'Tajawal';background:#f8fafc;outline:none}} input.bad{{border-color:#dc2626;background:#fef2f2}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;font-family:'Tajawal';cursor:pointer}}button:disabled{{opacity:.4;cursor:not-allowed;background:#94a3b8!important}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;font-size:15px;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b;border:2px solid #fecaca}}#ok{{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}}#exist,#ipblock,#wrong,#black,#deviceblock,#hwblock{{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}}#closed{{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}}#timer{{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:800;display:none;margin:10px auto;width:fit-content}}</style></head><body><div class="card">{LOGO_TAG}<div class="header-lines"><div class="t1">📝 تسجيل الحضور V2.3 APK</div><div class="t2">الكلية التكنولوجية بالمحلة الكبرى</div><div class="t3">المعهد الصناعي بالمحلة</div><div class="t4">د.م/ محمود منصور - IP مفتوح</div><div style="font-size:12px;color:#475569;margin-top:6px">IP الحالي: <b id="currentIp">{real_ip}:8080</b></div><div id="studentQr" style="display:flex;justify-content:center;margin:10px auto"></div><button type="button" onclick="location.href='/local-app'" style="margin-bottom:8px;background:#0f766e">📱 دخول كطالب من نفس التطبيق</button></div><div id="timer">⏳ باقي: <span id="t">--:--</span></div><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" inputmode="numeric" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي عربي"><input id="nid" type="tel" maxlength="14" inputmode="numeric" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div><div id="exist" class="msgbox">⚠️ الرقم القومي مسجل</div><div id="ipblock" class="msgbox">❌ IP مكرر</div><div id="deviceblock" class="msgbox">❌ الجهاز سجل قبل كده</div><div id="hwblock" class="msgbox">❌ بصمة الجهاز مكررة</div><div id="closed" class="msgbox">⛔ مقفول</div><div id="wrong" class="msgbox">❌ كلمة السر غلط</div><div id="black" class="msgbox">⛔ محظور</div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let isClosedByAdmin=false;function renderStudentQr(url){let box=document.getElementById("studentQr");if(!box)return;box.innerHTML="";if(window.QRCode){new QRCode(box,{text:url,width:132,height:132});}else{box.innerHTML="<small>افتح الرابط من نفس الشبكة: "+url+"</small>";}}async function refreshStudentIps(){try{let r=await fetch("/my_ips",{cache:"no-store"});let j=await r.json();let ip=j.primary||(j.ips||[])[0]||"{real_ip}";document.getElementById("currentIp").innerText=ip+":8080";let u="http://"+ip+":8080"+location.pathname+location.search;renderStudentQr(u);}catch(e){let ip='{real_ip}';document.getElementById('currentIp').innerText=ip+':8080';renderStudentQr('http://'+ip+':8080'+location.pathname+location.search);}}
function getHardwareFingerprint(){try{let fp=[navigator.userAgent,screen.width,navigator.language].join('|');let h=0;for(let i=0;i<fp.length;i++){h=((h<<5)-h)+fp.charCodeAt(i);h=h&h;}return 'hw_'+Math.abs(h).toString(36);}catch(e){return 'hw_err';}}
function getDeviceId(){let s=localStorage.getItem('device_fingerprint');if(s)return s;let id=getHardwareFingerprint()+'_'+Math.random().toString(36).slice(2,6);localStorage.setItem('device_fingerprint',id);return id;}
function isAlreadyRegisteredLocally(){return localStorage.getItem('already_registered_'+getDeviceId())==='1' || localStorage.getItem('my_nid_registered')!==null;}
function markAsRegistered(nid){localStorage.setItem('already_registered_'+getDeviceId(),'1');localStorage.setItem('my_nid_registered',nid);}
function applyAlreadyRegisteredUI(){if(isAlreadyRegisteredLocally()){let btn=document.getElementById('btn');btn.disabled=true;btn.innerText='✅ سجلت قبل كده';document.getElementById('closed').style.display='block';document.getElementById('closed').innerText='✅ سجلت من الجهاز ده';return true;}return false;}
async function syncTime(){try{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}catch(e){}}
function nowSynced(){return Date.now()+serverOffset;
}
function simpleHash(s){let h=0;for(let i=0;i<s.length;i++){h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}return Math.abs(h).toString(36);}
function getParams(){let p=new URLSearchParams(location.search);return {open:p.get('open'),s:p.get('s');}}let cached=getParams();
function showMsg(t){let b=document.getElementById('msgBox');b.innerText=t;b.style.display='block';}
function hideAll(){['ok','exist','ipblock','deviceblock','hwblock','wrong','closed','black','msgBox'].forEach(x=>document.getElementById(x).style.display='none');}
async function sendData(){
 if(isAlreadyRegisteredLocally()){applyAlreadyRegisteredUI();return;}
 hideAll();
 let p=document.getElementById('pass').value.trim(),b=document.getElementById('board').value.trim(),n=document.getElementById('name').value.trim(),id=document.getElementById('nid').value.trim();
 if(!p||!b||!n||!id){showMsg('اكمل البيانات');return;}
 id=id.replace(/[٠-٩۰-۹]/g,c=>'٠١٢٣٤٥٦٧٨٩'.includes(c)?'٠١٢٣٤٥٦٧٨٩'.indexOf(c):'۰۱۲۳۴۵۶۷۸۹'.indexOf(c)).replace(/[^0-9]/g,'');
 if(!/^\\d{14}$/.test(id)){showMsg('الرقم القومي يجب أن يتكون من 14 رقمًا صحيحًا');document.getElementById('nid').classList.add('bad');return;}
 document.getElementById('nid').classList.remove('bad');
 try{
  let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({open:cached.open||'',s:cached.s||'',name:n,nid:id,board:b,pass:p,deviceId:getDeviceId(),hwId:getHardwareFingerprint(),androidId:'',localApp:new URLSearchParams(location.search).get('local-app')==='1'})});
  hideAll();
  if(r.status==200){markAsRegistered(id);document.getElementById('ok').style.display='block';let d=await r.json();if(d.redirect)location.href=d.redirect;}
  else if(r.status==409)document.getElementById('exist').style.display='block';
  else if(r.status==410)document.getElementById('ipblock').style.display='block';
  else if(r.status==411)document.getElementById('deviceblock').style.display='block';
  else if(r.status==412)document.getElementById('hwblock').style.display='block';
  else if(r.status==422)showMsg('الرقم القومي غير صحيح');
  else if(r.status==401)document.getElementById('wrong').style.display='block';
  else document.getElementById('closed').style.display='block';
 }catch(e){showMsg('مش متصل');}
}
syncTime().then(()=>{refreshStudentIps();setInterval(refreshStudentIps,1000);});
</script></body></html>"""

def build_admin_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    HEADER_LOGO = get_header_logo_tag()
    ips = get_local_ips()
    primary = get_real_ip()
    router_ip = primary
    hotspot_ip = primary
    for ip in ips:
        if ip.startswith("192.168.0.") or ip.startswith("192.168.1."): router_ip = ip; break
    for ip in ips:
        if ip.startswith("192.168.43.") or ip.startswith("192.168.137.") or ip.startswith("10."): hotspot_ip = ip; break
    ips_html = ", ".join(ips)
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة تحكم APK V2.3</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#eef2ff,#f5f7fb);padding:12px}} .container{{max-width:1100px;margin:auto}} .hidden{{display:none!important}} .header{{background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;padding:16px;border-radius:20px;display:flex;justify-content:space-between;align-items:center}} .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:14px 0}} .stat{{background:#fff;border-radius:16px;padding:14px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,.06)}} .stat b{{display:block;font-size:26px;color:#1a73e8}} .card{{background:#fff;border-radius:18px;padding:16px;margin-bottom:14px;box-shadow:0 6px 20px rgba(0,0,0,.05)}} .card-title{{font-weight:800;margin-bottom:12px}} label{{font-size:12px;font-weight:700}} input,textarea{{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:12px;margin:4px 0}} .btn{{padding:12px 16px;border:none;border-radius:12px;font-weight:800;cursor:pointer}} .btn-primary{{background:#1a73e8;color:#fff}} .btn-success{{background:#16a34a;color:#fff}} .btn-danger{{background:#dc2626;color:#fff}} .btn-dark{{background:#0f172a;color:#fff}} .btn-warn{{background:#f59e0b;color:#fff}} .btn-light{{background:#f1f5f9}} .toolbar{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}} .table-wrap{{overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:750px}} th{{background:#0f172a;color:#fff;padding:10px}} td{{padding:8px;border-bottom:1px solid #eee;text-align:center}} .linkBox{{background:#f8fafc;border:1px dashed #94a3b8;border-radius:12px;padding:10px;margin-top:8px}} .linkRow{{display:flex;gap:6px;margin:6px 0}}</style></head><body><div class="container"><div class="header"><div style="display:flex;align-items:center;gap:10px">{HEADER_LOGO}<div><div style="font-weight:800">لوحة تحكم الأدمن الشاملة</div><div style="font-size:11px;opacity:.8">الكلية التكنولوجية - د.م/ محمود منصور</div></div></div><div><button onclick="goBackMain()" class="btn btn-light" style="color:#0f172a">🏠 الرئيسية</button></div></div><div class="stats"><div class="stat"><b id="activeCount">0</b><span>النشط</span></div><div class="stat"><b id="waitCount">0</b><span>انتظار</span></div><div class="stat"><b id="count">0</b><span>إجمالي</span></div></div><div class="card" style="background:#fffbeb"><div class="card-title">🔑 3- فتح المحاضرة وتوليد الباركود (هوتسبوت أو روتر)</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>كلمة سر المحاضرة</label><input id="lecturePass" placeholder="2026"></div><div><label>المدة بالدقائق</label><input id="minutes" type="number" value="30"></div></div><div style="display:flex;gap:8px;margin-top:12px"><button onclick="openNow()" class="btn btn-success" style="flex:2">✅ افتح المحاضرة</button><button onclick="closeNow()" class="btn btn-danger" style="flex:1">⛔ اقفل</button></div><div id="shareBox" style="display:none;background:#e0f2fe;padding:14px;border-radius:14px;margin-top:14px"><div style="font-weight:800">📡 باركود وروابط الطلبة:</div><div style="text-align:center;background:#fff;border-radius:12px;padding:12px;margin:10px 0"><div id="adminQr" style="display:flex;justify-content:center"></div><div style="font-size:12px;margin-top:6px">امسح الباركود من موبايل الطالب</div></div><div class="linkBox"><div class="linkRow"><b>📱 هوتسبوت:</b><input id="shareLinkHotspot" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkHotspot')" class="btn btn-warn" style="padding:6px">نسخ</button></div><div style="font-size:11px">IP الهوتسبوت: <b>{hotspot_ip}</b></div><div style="display:flex;gap:6px;margin-top:6px"><input id="customHotspotIp" value="{hotspot_ip}" style="flex:1"><button onclick="buildAllLinks()" class="btn btn-light" style="padding:6px">تحديث</button></div></div><div class="linkBox" style="background:#dcfce7"><div class="linkRow"><b>📶 روتر:</b><input id="shareLinkRouter" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkRouter')" class="btn btn-success" style="padding:6px">نسخ</button></div><div style="font-size:11px">IP الراوتر: <b>{router_ip}</b></div><div style="display:flex;gap:6px;margin-top:6px"><input id="customRouterIp" value="{router_ip}" style="flex:1"><button onclick="buildAllLinks()" class="btn btn-light" style="padding:6px">تحديث</button></div></div></div></div><div class="card"><div class="card-title">📊 كشوف الحضور والتحكم</div><div class="toolbar"><button onclick="window.location.href='/export'" class="btn btn-success">⬇️ تصدير CSV</button><button onclick="clearData()" class="btn btn-light" style="color:#dc2626">🗑️ مسح الكل</button></div><div class="table-wrap"><table id="tbl"><thead><tr><th>#</th><th>الوقت</th><th>الاسم</th><th>القومي</th><th>IP</th><th>السبورة</th><th>🗑️ حذف</th></tr></thead><tbody></tbody></table></div></div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let lastOpen="",lastSig="";
async function syncTime(){try{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}catch(e){}}
function nowSynced(){return Date.now()+serverOffset;}
function simpleHash(s){let h=0;for(let i=0;i<s.length;i++){h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}return Math.abs(h).toString(36);}
function drawAdminQr(){let box=document.getElementById("adminQr");if(!box)return;box.innerHTML="";let u=document.getElementById("shareLinkHotspot")?.value||"";if(window.QRCode&&u)new QRCode(box,{text:u,width:180,height:180});else box.innerText=u;}
function buildAllLinks(){if(!lastOpen)return;let baseHotspot='http://'+(document.getElementById('customHotspotIp').value.trim()||'{hotspot_ip}')+':8080';let path='/attendance.html?open='+lastOpen+'&s='+lastSig;document.getElementById('shareLinkHotspot').value=baseHotspot+path;document.getElementById('shareLinkRouter').value='http://'+(document.getElementById('customRouterIp').value.trim()||'{router_ip}')+':8080'+path;drawAdminQr();}
async function openNow(){let lp=document.getElementById('lecturePass').value.trim();let mins=parseInt(document.getElementById('minutes').value);if(!lp){alert('اكتب كلمة السر');return;}let u=nowSynced()+mins*60*1000;let sig=simpleHash(u.toString()+SECRET);lastOpen=u.toString();lastSig=sig;buildAllLinks();document.getElementById('shareBox').style.display='block';await fetch('/set_config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({open:u.toString(),s:sig,lecturePass:lp})});refresh();}
async function closeNow(){document.getElementById('shareBox').style.display='none';await fetch('/set_config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({open:"0",s:"",lecturePass:""})});refresh();alert('⛔ تم إغلاق المحاضرة');}
async function refresh(){try{let r=await fetch('/list');let d=await r.json();let cachedData=d.list||[];document.getElementById('count').innerText=cachedData.length;document.getElementById('activeCount').innerText=d.active;document.getElementById('waitCount').innerText=d.waiting;let tb=document.querySelector('#tbl tbody');tb.innerHTML='';cachedData.forEach((x,i)=>{tb.innerHTML+=`<tr><td>${i+1}</td><td>${x.time}</td><td>${x.name}</td><td>${x.nid}</td><td>${x.ip||''}</td><td>${x.board}</td><td><button onclick="deleteOne('${x.nid}')" class="btn btn-danger" style="padding:4px 8px;font-size:11px">🗑️</button></td></tr>`;});}catch(e){}}
async function deleteOne(nid){await fetch('/delete_one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nid})});refresh();}
async function clearData(){if(confirm('مسح الكل؟')){await fetch('/clear',{method:'POST'});refresh();}}
function goBackMain(){window.location.href='/';}
syncTime().then(()=>{refresh();setInterval(refresh,2000);});
</script></body></html>"""

def ensure_files():
    cfg = load_cfg()
    save_cfg(cfg)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE,"w",encoding="utf-8") as f: f.write("[]")

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): return
    def do_POST(self):
        client_ip = self.client_address[0]
        cfg = load_cfg()
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
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE,'r',encoding='utf-8') as f: all_data=json.load(f)
                    new_data=[x for x in all_data if x.get('nid')!=nid_to_del]
                    with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(new_data,f,ensure_ascii=False,indent=2)
                except: pass
            self.send_response(200); self.end_headers(); return
        if self.path == '/set_config':
            length = int(self.headers.get('content-length',0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            cfg["lecturePass"] = data.get('lecturePass','')
            cfg["open"] = data.get('open','0')
            cfg["s"] = data.get('s','')
            save_cfg(cfg)
            self.send_response(200); self.end_headers(); return
        if self.path == '/save':
            try:
                length = int(self.headers.get('content-length',0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                now_ms = int(datetime.now().timestamp()*1000)
                cfg_open = cfg.get('open','0')
                if cfg_open == "0" or int(cfg_open) < now_ms:
                    self.send_response(403)
                    self.send_header('Content-Type','application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"closed":True}).encode('utf-8')); return
                if cfg.get('lecturePass','').strip() and data.get('pass','').strip()!= cfg.get('lecturePass','').strip():
                    self.send_response(401); self.end_headers(); return
                nid = normalize_nid(data.get('nid',''))
                if not valid_national_id(nid):
                    self.send_response(422)
                    self.send_header('Content-Type','application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error":"الرقم القومي غير صحيح"},ensure_ascii=False).encode('utf-8')); return
                all_data=[]
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE,'r',encoding='utf-8') as f:
                        try: all_data=json.load(f)
                        except: all_data=[]
                if cfg.get('nid_check',True) and any(x.get('nid')==nid for x in all_data):
                    self.send_response(409); self.end_headers(); return
                rec = {"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"name":data.get('name',''),"nid":nid,"board":data.get('board',''),"ip":client_ip}
                all_data.append(rec)
                with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(all_data,f,ensure_ascii=False,indent=2)
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"ok":True,"redirect":"/done"}).encode('utf-8'))
            except Exception:
                self.send_response(500); self.end_headers()
        elif self.path == '/clear':
            with open(DATA_FILE,'w',encoding='utf-8') as f: f.write("[]")
            self.send_response(200); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.lower()
        if path == '/health':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok":True}).encode('utf-8'))
            return
        if path == '/export':
            try:
                with open(DATA_FILE,'r',encoding='utf-8') as f: rows=json.load(f)
            except: rows=[]
            import csv, io
            output=io.StringIO(newline='')
            writer=csv.writer(output)
            writer.writerow(['الوقت','الاسم','الرقم القومي','IP','السبورة'])
            for r in rows: writer.writerow([r.get('time',''),r.get('name',''),r.get('nid',''),r.get('ip',''),r.get('board','')])
            payload=output.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type','text/csv; charset=utf-8')
            self.send_header('Content-Disposition','attachment; filename="attendance.csv"')
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == '/my_ips':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ips": get_local_ips(), "primary": get_real_ip()}).encode('utf-8'))
            return
        if path == '/time':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"server": int(datetime.now().timestamp()*1000)}).encode('utf-8'))
            return
        if path == '/get_config':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            cfg = load_cfg()
            self.wfile.write(json.dumps({k:v for k,v in cfg.items() if k!='adminPass'}).encode('utf-8'))
            return
        if path == '/list':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            data=[]
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE,'r',encoding='utf-8') as f:
                    try: data=json.load(f)
                    except: data=[]
            self.wfile.write(json.dumps({"list":data,"active":len(active_ips),"waiting":len(waiting_queue)}).encode('utf-8'))
            return
        if 'admin' in path:
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(build_admin_html().encode('utf-8'))
            return
        if 'done' in path:
            self.send_response(200)
            self.send_header('Content-type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write('<html><body dir="rtl" style="text-align:center;font-family:Tahoma;padding:50px"><h1 style="color:green">✅ تم تسجيل حضورك بنجاح!</h1><p>يمكنك العودة للشاشة الرئيسية.</p><a href="/">الرئيسية</a></body></html>'.encode('utf-8'))
            return
        self.send_response(200)
        self.send_header('Content-type','text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(build_att_html().encode('utf-8'))

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

def run_server():
    ensure_files()
    try:
        with ThreadingHTTPServer(('0.0.0.0',8080), Handler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass

class MainApp(App):
    def build(self):
        configure_storage(self)
        ensure_files()
        threading.Thread(target=run_server, daemon=True).start()
        
        self.root_layout = BoxLayout(orientation='vertical')
        self.show_role_selection()
        return self.root_layout

    def apply_arabic_font(self, widget):
        if DEFAULT_FONT_NAME and hasattr(widget, 'font_name'):
            widget.font_name = DEFAULT_FONT_NAME

    def show_role_selection(self):
        self.root_layout.clear_widgets()
        
        box = BoxLayout(orientation='vertical', padding=24, spacing=16)
        
        title = Label(
            text=ar("🎓 نظام الحضور الذكي - الكلية التكنولوجية"),
            font_size='20sp',
            bold=True,
            size_hint_y=None,
            height=60,
            halign='center',
            valign='middle'
        )
        self.apply_arabic_font(title)
        box.add_widget(title)

        sub = Label(
            text=ar("اختر نوع الدخول للبدء:"),
            font_size='16sp',
            size_hint_y=None,
            height=40,
            halign='center'
        )
        self.apply_arabic_font(sub)
        box.add_widget(sub)

        btn_student = Button(
            text=ar("👨‍🎓 دخول طالب (تسجيل الحضور)"),
            background_color=(0.1, 0.45, 0.91, 1),
            size_hint_y=None,
            height=60,
            font_size='16sp',
            bold=True
        )
        self.apply_arabic_font(btn_student)
        btn_student.bind(on_press=lambda x: self.show_student_screen())
        box.add_widget(btn_student)

        btn_admin = Button(
            text=ar("🔐 دخول أدمن (لوحة التحكم والإعدادات)"),
            background_color=(0.06, 0.09, 0.16, 1),
            size_hint_y=None,
            height=60,
            font_size='16sp',
            bold=True
        )
        self.apply_arabic_font(btn_admin)
        btn_admin.bind(on_press=lambda x: self.show_admin_login_popup())
        box.add_widget(btn_admin)

        nav_bar = self.build_navigation_bar()
        
        self.root_layout.add_widget(box)
        self.root_layout.add_widget(nav_bar)

    def build_navigation_bar(self):
        nav = BoxLayout(size_hint_y=None, height=55, padding=4, spacing=4)
        
        btn_home = Button(text=ar("🏠 الرئيسية"), background_color=(0.2, 0.2, 0.2, 1))
        self.apply_arabic_font(btn_home)
        btn_home.bind(on_press=lambda x: self.show_role_selection())

        btn_settings = Button(text=ar("⚙️ الإعدادات"), background_color=(0.2, 0.2, 0.2, 1))
        self.apply_arabic_font(btn_settings)
        btn_settings.bind(on_press=lambda x: self.show_settings_popup())

        btn_contact = Button(text=ar("📞 اتصل بنا"), background_color=(0.2, 0.2, 0.2, 1))
        self.apply_arabic_font(btn_contact)
        btn_contact.bind(on_press=lambda x: self.show_contact_popup())

        nav.add_widget(btn_home)
        nav.add_widget(btn_settings)
        nav.add_widget(btn_contact)
        return nav

    def show_student_screen(self):
        self.root_layout.clear_widgets()
        
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', padding=16, spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter('height'))

        lbl = Label(text=ar("📱 تسجيل حضور الطالب"), font_size='18sp', bold=True, size_hint_y=None, height=40)
        self.apply_arabic_font(lbl)
        content.add_widget(lbl)

        ip_info = Label(text=ar(f"IP السيرفر الحالي: {get_real_ip()}:8080"), font_size='13sp', size_hint_y=None, height=30)
        self.apply_arabic_font(ip_info)
        content.add_widget(ip_info)

        self.s_pass = TextInput(hint_text=ar("كلمة سر المحاضرة"), password=True, multiline=False, size_hint_y=None, height=45)
        self.s_board = TextInput(hint_text=ar("رقم السبورة"), multiline=False, input_filter='int', size_hint_y=None, height=45)
        self.s_name = TextInput(hint_text=ar("الاسم رباعي عربي"), multiline=False, size_hint_y=None, height=45)
        self.s_nid = TextInput(hint_text=ar("الرقم القومي (14 رقم)"), multiline=False, input_filter='int', maxlength=14, size_hint_y=None, height=45)

        for ti in [self.s_pass, self.s_board, self.s_name, self.s_nid]:
            self.apply_arabic_font(ti)
            content.add_widget(ti)

        self.s_msg = Label(text="", size_hint_y=None, height=40)
        self.apply_arabic_font(self.s_msg)
        content.add_widget(self.s_msg)

        btn_send = Button(text=ar("إرسال الحضور"), background_color=(0.1, 0.6, 0.2, 1), size_hint_y=None, height=50, bold=True)
        self.apply_arabic_font(btn_send)
        btn_send.bind(on_press=self.submit_attendance_native)
        content.add_widget(btn_send)

        btn_back = Button(text=ar("رجوع للقائمة الرئيسية"), background_color=(0.8, 0.2, 0.2, 1), size_hint_y=None, height=45)
        self.apply_arabic_font(btn_back)
        btn_back.bind(on_press=lambda x: self.show_role_selection())
        content.add_widget(btn_back)

        scroll.add_widget(content)
        self.root_layout.add_widget(scroll)

    def submit_attendance_native(self, *args):
        import urllib.request
        server = f"http://{get_real_ip()}:8080"
        nid = normalize_nid(self.s_nid.text)
        if not self.s_pass.text.strip() or not self.s_board.text.strip() or not self.s_name.text.strip() or not nid:
            self.s_msg.text = ar("❌ يرجى إكمال جميع البيانات بدقة")
            return
        if not valid_national_id(nid):
            self.s_msg.text = ar("❌ الرقم القومي غير صحيح (يجب أن يكون 14 رقمًا صحيحًا)")
            return
        
        try:
            with urllib.request.urlopen(server + '/get_config', timeout=3) as resp:
                cfg = json.loads(resp.read().decode('utf-8'))
            payload = {
                "open": cfg.get("open", ""), "s": cfg.get("s", ""),
                "name": self.s_name.text.strip(), "nid": nid,
                "board": self.s_board.text.strip(), "pass": self.s_pass.text.strip(),
                "deviceId": "app-" + ANDROID_SERIAL, "hwId": ANDROID_SERIAL
            }
            req = urllib.request.Request(server + '/save', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=5) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                if res.get("ok"):
                    self.s_msg.text = ar("✅ تم تسجيل الحضور بنجاح!")
                else:
                    self.s_msg.text = ar("❌ فشل التسجيل، تأكد من حالة المحاضرة.")
        except Exception as e:
            self.s_msg.text = ar("❌ تعذر الاتصال بالسيرفر المحلي تأكد من شبكة الراوتر/الهوتسبوت")

    def show_admin_login_popup(self):
        content = BoxLayout(orientation='vertical', padding=14, spacing=10)
        lbl = Label(text=ar("أدخل كلمة مرور الأدمن الافتراضية:\nmansour2026"), size_hint_y=None, height=50)
        self.apply_arabic_font(lbl)
        content.add_widget(lbl)

        pass_input = TextInput(hint_text=ar("كلمة المرور"), password=True, multiline=False, size_hint_y=None, height=45)
        self.apply_arabic_font(pass_input)
        content.add_widget(pass_input)

        msg_lbl = Label(text="", size_hint_y=None, height=30)
        self.apply_arabic_font(msg_lbl)
        content.add_widget(msg_lbl)

        btn_login = Button(text=ar("دخول لوحة التحكم"), background_color=(0.1, 0.45, 0.91, 1), size_hint_y=None, height=50)
        self.apply_arabic_font(btn_login)
        
        popup = Popup(title=ar("تسجيل دخول الأدمن"), content=content, size_hint=(0.85, 0.55))

        def verify_admin(instance):
            cfg = load_cfg()
            if pass_input.text.strip() == cfg.get('adminPass', DEFAULT_ADMIN_PASS):
                popup.dismiss()
                self.show_admin_dashboard()
            else:
                msg_lbl.text = ar("❌ كلمة المرور غير صحيحة!")

        btn_login.bind(on_press=verify_admin)
        content.add_widget(btn_login)
        popup.open()

    def show_admin_dashboard(self):
        self.root_layout.clear_widgets()
        box = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        lbl = Label(text=ar("🔐 مرحباً بك في لوحة تحكم الأدمن"), font_size='20sp', bold=True, size_hint_y=None, height=50)
        self.apply_arabic_font(lbl)
        box.add_widget(lbl)

        info = Label(text=ar(f"السيرفر يعمل الآن على الشبكة:\nIP: {get_real_ip()}:8080\nيمكنك فتح لوحة الإدارة الكاملة بالأسفل:"), size_hint_y=None, height=80)
        self.apply_arabic_font(info)
        box.add_widget(info)

        import webbrowser
        btn_open_web = Button(text=ar("🌐 فتح لوحة التحكم التفاعلية الشاملة"), background_color=(0.1, 0.6, 0.3, 1), size_hint_y=None, height=60, bold=True)
        self.apply_arabic_font(btn_open_web)
        btn_open_web.bind(on_press=lambda x: webbrowser.open(f"http://{get_real_ip()}:8080/admin"))
        box.add_widget(btn_open_web)

        btn_back = Button(text=ar("🏠 العودة للرئيسية"), background_color=(0.8, 0.2, 0.2, 1), size_hint_y=None, height=50)
        self.apply_arabic_font(btn_back)
        btn_back.bind(on_press=lambda x: self.show_role_selection())
        box.add_widget(btn_back)

        self.root_layout.add_widget(box)

    def show_settings_popup(self):
        content = BoxLayout(orientation='vertical', padding=15, spacing=12)
        
        lbl = Label(text=ar("⚙️ إعدادات التطبيق واختيار اللغة"), font_size='16sp', bold=True, size_hint_y=None, height=40)
        self.apply_arabic_font(lbl)
        content.add_widget(lbl)

        lang_lbl = Label(text=ar("لغة التطبيق الحالية: العربية"), size_hint_y=None, height=35)
        self.apply_arabic_font(lang_lbl)
        content.add_widget(lang_lbl)

        ver_lbl = Label(text=ar("📌 رقم الإصدار: V2.3 Pro (2026)"), size_hint_y=None, height=35)
        self.apply_arabic_font(ver_lbl)
        content.add_widget(ver_lbl)

        btn_close = Button(text=ar("إغلاق"), size_hint_y=None, height=45)
        self.apply_arabic_font(btn_close)
        popup = Popup(title=ar("الإعدادات"), content=content, size_hint=(0.8, 0.5))
        btn_close.bind(on_press=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

    def show_contact_popup(self):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        
        lbl = Label(text=ar("📞 اتصل بنا ومواقع التواصل الاجتماعي"), font_size='16sp', bold=True, size_hint_y=None, height=40)
        self.apply_arabic_font(lbl)
        content.add_widget(lbl)

        info = Label(text=ar("الكلية التكنولوجية بالمحلة الكبرى\nالمعهد الصناعي بالمحلة\nتطوير: د.م/ محمود منصور"), size_hint_y=None, height=100)
        self.apply_arabic_font(info)
        content.add_widget(info)

        btn_close = Button(text=ar("إغلاق"), size_hint_y=None, height=45)
        self.apply_arabic_font(btn_close)
        popup = Popup(title=ar("اتصل بنا"), content=content, size_hint=(0.85, 0.6))
        btn_close.bind(on_press=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

if __name__ == '__main__':
    MainApp().run()
