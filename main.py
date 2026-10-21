from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
import http.server, json, os, threading, base64, socket, re, subprocess
from datetime import datetime
from collections import OrderedDict
import urllib.parse, mimetypes, socketserver, webbrowser

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
# These paths are redirected to App.user_data_dir on Android before the server starts.
DATA_DIR = BASE_DIR
DATA_FILE = os.path.join(DATA_DIR, "attendance.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LATEST_FILE = os.path.join(DATA_DIR, "latest_link.txt")

def configure_storage(app=None):
 """Use Android's writable private app folder; migrate old adjacent files once."""
 global DATA_DIR, DATA_FILE, CONFIG_FILE, LATEST_FILE
 target = BASE_DIR
 try:
  if app is not None and getattr(app, "user_data_dir", None):
   target = app.user_data_dir
 except Exception:
  pass
 os.makedirs(target, exist_ok=True)
 old_paths = {
  "attendance.json": os.path.join(BASE_DIR, "attendance.json"),
  "config.json": os.path.join(BASE_DIR, "config.json"),
  "latest_link.txt": os.path.join(BASE_DIR, "latest_link.txt"),
 }
 for name, old_path in old_paths.items():
  new_path = os.path.join(target, name)
  if os.path.abspath(old_path) != os.path.abspath(new_path) and os.path.isfile(old_path) and not os.path.exists(new_path):
   try:
    import shutil
    shutil.copy2(old_path, new_path)
   except Exception as exc:
    print("Data migration warning:", name, exc)
 DATA_DIR = target
 DATA_FILE = os.path.join(DATA_DIR, "attendance.json")
 CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
 LATEST_FILE = os.path.join(DATA_DIR, "latest_link.txt")

DEFAULT_ADMIN_PASS = "mansour2026"
DEFAULT_CFG = {"lecturePass": "", "open": "0", "s": "", "max_active": 32, "stay_seconds": 2.0, "ip_check": False, "nid_check": True, "device_check": True, "hw_check": False, "android_check": True, "black_nids": [], "black_ips": [], "white_ips": [], "after_msg": "✅ تم التسجيل في موبايل الدكتور", "done_msg": "✅ تم تسجيل حضورك - توجه لمعمل 3 عند م/ احمد", "batch": 5, "adminPass": DEFAULT_ADMIN_PASS, "local_app_enabled": True}
active_ips = OrderedDict()
waiting_queue = OrderedDict()

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


def normalize_nid(value):
    """Normalize Arabic/Persian digits and remove surrounding whitespace."""
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

def simple_hash(s):
 h = 0
 for ch in s:
  h = ((h << 5) - h) + ord(ch)
  h = h & 0xFFFFFFFF
  if h >= 0x80000000: h -= 0x100000000
 return format(abs(h), '36')

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:10px"><a href="https://twitter.com/eng_mahmoud_man?s=07" target="_blank" style="width:36px;height:36px;background:#000;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-weight:800;font-size:14px">𝕏</a><a href="https://github.com/natiga-script" target="_blank" style="width:36px;height:36px;background:#0f172a;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:11px;font-weight:800">GH</a><a href="https://www.facebook.com/profile.php?id=100009579078219" target="_blank" style="width:36px;height:36px;background:#1877F2;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-weight:800">f</a><a href="https://www.linkedin.com/in/eng-mahmoud-mansour" target="_blank" style="width:36px;height:36px;background:#0A66C2;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:12px;font-weight:800">in</a><a href="https://www.instagram.com/eng_mahmoud_mansour/" target="_blank" style="width:36px;height:36px;background:radial-gradient(circle at 30% 107%,#fdf497 0%,#fdf497 5%,#fd5949 45%,#d6249f 60%,#285AEB 90%);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:11px;font-weight:800">IG</a></div><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div>المعهد الصناعي بالمحلة</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div><div style="margin-top:6px;font-size:10px">© حقوق محفوظة لـ م/ محمود منصور 2026</div></div></div>"""

def build_att_html():
 cfg=load_cfg()
 LOGO_TAG = get_logo_tag(size=90, with_margin=True)
 return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>تسجيل الحضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}.header-lines{{text-align:center;line-height:1.7;margin:8px 0 14px 0}}.t1{{font-size:20px;font-weight:800;color:#0f172a}}.t2{{font-size:13px;color:#334155}}.t3{{font-size:13px;color:#334155}}.t4{{font-size:14px;font-weight:800;color:#1a73e8}}input{{width:100%;padding:13px 14px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;font-family:'Tajawal';background:#f8fafc;outline:none}} input.bad{{border-color:#dc2626;background:#fef2f2}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;font-family:'Tajawal';cursor:pointer}}button:disabled{{opacity:.4;cursor:not-allowed;background:#94a3b8!important}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;font-size:15px;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b;border:2px solid #fecaca}}#ok{{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}}#exist,#ipblock,#wrong,#black,#deviceblock,#hwblock{{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}}#closed{{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}}#timer{{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:800;display:none;margin:10px auto;width:fit-content}}</style></head><body><div class="card">{LOGO_TAG}<div class="header-lines"><div class="t1">📝 تسجيل الحضور V2.3 APK</div><div class="t2">الكلية التكنولوجية بالمحلة الكبرى</div><div class="t3">المعهد الصناعي بالمحلة</div><div class="t4">د.م/ محمود منصور - IP مفتوح</div><div style="font-size:12px;color:#475569;margin-top:6px">IP الحالي: <b id="currentIp">جارٍ الكشف...</b></div><div id="studentQr" style="display:flex;justify-content:center;margin:10px auto"></div><button type="button" onclick="location.href='/local-app'" style="margin-bottom:8px;background:#0f766e">📱 دخول كطالب من نفس التطبيق</button></div><div id="timer">⏳ باقي: <span id="t">--:--</span></div><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" inputmode="numeric" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي عربي"><input id="nid" type="tel" maxlength="14" inputmode="numeric" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div><div id="exist" class="msgbox">⚠️ الرقم القومي مسجل</div><div id="ipblock" class="msgbox">❌ IP مكرر (الخاصية مقفولة حاليا)</div><div id="deviceblock" class="msgbox">❌ الجهاز سجل قبل كده</div><div id="hwblock" class="msgbox">❌ بصمة الجهاز مكررة</div><div id="closed" class="msgbox">⛔ مقفول</div><div id="wrong" class="msgbox">❌ كلمة السر غلط</div><div id="black" class="msgbox">⛔ محظور</div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let isClosedByAdmin=false;let qrInstance=null;function renderStudentQr(url){{let box=document.getElementById("studentQr");if(!box)return;box.innerHTML="";if(window.QRCode){{new QRCode(box,{{text:url,width:132,height:132}});}}else{{box.innerHTML="<small>افتح الرابط من نفس الشبكة: "+url+"</small>";}}}}async function refreshStudentIps(){{try{{let r=await fetch("/my_ips",{{cache:"no-store"}});let j=await r.json();let ip=j.primary||(j.ips||[])[0]||"غير معروف";document.getElementById("currentIp").innerText=ip+":8080";let u="http://"+ip+":8080"+location.pathname+location.search;renderStudentQr(u);}}catch(e){{}}}}
function getHardwareFingerprint(){{try{{let fp=[navigator.userAgent,screen.width,navigator.language].join('|');let h=0;for(let i=0;i<fp.length;i++){{h=((h<<5)-h)+fp.charCodeAt(i);h=h&h;}}return 'hw_'+Math.abs(h).toString(36);}}catch(e){{return 'hw_err';}}}}
function getDeviceId(){{let s=localStorage.getItem('device_fingerprint');if(s)return s;let id=getHardwareFingerprint()+'_'+Math.random().toString(36).slice(2,6);localStorage.setItem('device_fingerprint',id);return id;}}
function isAlreadyRegisteredLocally(){{return localStorage.getItem('already_registered_'+getDeviceId())==='1' || localStorage.getItem('my_nid_registered')!==null;}}
function markAsRegistered(nid){{localStorage.setItem('already_registered_'+getDeviceId(),'1');localStorage.setItem('my_nid_registered',nid);}}
function applyAlreadyRegisteredUI(){{if(isAlreadyRegisteredLocally()){{let btn=document.getElementById('btn');btn.disabled=true;btn.innerText='✅ سجلت قبل كده';document.getElementById('closed').style.display='block';document.getElementById('closed').innerText='✅ سجلت من الجهاز ده - استخدم جهاز تاني لزميلك';return true;}}return false;}}
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}}catch(e){{}}}}
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
function getParams(){{let p=new URLSearchParams(location.search);return {{open:p.get('open'),s:p.get('s')}};}}let cached=getParams();
function showMsg(t,id){{let b=document.getElementById('msgBox');b.innerText=t;b.style.display='block';}}
function hideAll(){{['ok','exist','ipblock','deviceblock','hwblock','wrong','closed','black','msgBox'].forEach(x=>document.getElementById(x).style.display='none');}}
function forceCloseAll(msg){{isClosedByAdmin=true;let btn=document.getElementById('btn'),tm=document.getElementById('timer'),cl=document.getElementById('closed');tm.style.display='none';cl.style.display='block';cl.innerText=msg||'⛔ الادمن قفل';btn.disabled=true;}}
function updateTimer(){{if(isClosedByAdmin)return;let o=cached.open,s=cached.s,btn=document.getElementById('btn'),cl=document.getElementById('closed'),tm=document.getElementById('timer');if(applyAlreadyRegisteredUI()){{tm.style.display='none';return;}}if(!o||!s||simpleHash(o+SECRET)!==s){{tm.style.display='none';cl.style.display='none';btn.disabled=false;return;}}let v=parseInt(o);if(nowSynced()>v){{tm.style.display='none';cl.style.display='block';cl.innerText='⛔ انتهى الوقت';btn.disabled=true;return;}}tm.style.display='block';cl.style.display='none';btn.disabled=false;let d=v-nowSynced(),m=Math.floor(d/60000),sc=Math.floor((d%60000)/1000);document.getElementById('t').innerText=m+':'+(sc<10?'0':'')+sc;}}
async function checkIfClosedByAdmin(){{try{{let r=await fetch('/get_config');let j=await r.json();if(!j.open||j.open=="0"||parseInt(j.open)<nowSynced()){{forceCloseAll('⛔ الادمن قفل التسجيل');}}}}catch(e){{}}}}
syncTime().then(()=>{{applyAlreadyRegisteredUI();setInterval(updateTimer,1000);updateTimer();setInterval(checkIfClosedByAdmin,2000);refreshStudentIps();setInterval(refreshStudentIps,1000);}});
async function sendData(){{
 if(isAlreadyRegisteredLocally()){{applyAlreadyRegisteredUI();return;}}
 hideAll();
 let p=document.getElementById('pass').value.trim(),b=document.getElementById('board').value.trim(),n=document.getElementById('name').value.trim(),id=document.getElementById('nid').value.trim();
 if(!p||!b||!n||!id){{showMsg('اكمل البيانات');return;}}id=id.replace(/[٠-٩۰-۹]/g,c=>'٠١٢٣٤٥٦٧٨٩'.includes(c)?'٠١٢٣٤٥٦٧٨٩'.indexOf(c):'۰۱۲۳۴۵۶۷۸۹'.indexOf(c)).replace(/[^0-9]/g,'');if(!/^\\d{14}$/.test(id)){{showMsg('الرقم القومي يجب أن يتكون من 14 رقمًا صحيحًا');document.getElementById('nid').classList.add('bad');return;}}document.getElementById('nid').classList.remove('bad');
 try{{
  let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:cached.open||'',s:cached.s||'',name:n,nid:id,board:b,pass:p,deviceId:getDeviceId(),hwId:getHardwareFingerprint(),androidId:'',localApp:new URLSearchParams(location.search).get('local-app')==='1'}})}});
  hideAll();
  if(r.status==200){{markAsRegistered(id);document.getElementById('ok').style.display='block';let d=await r.json();if(d.redirect)location.href=d.redirect;}}
  else if(r.status==409)document.getElementById('exist').style.display='block';
  else if(r.status==410)document.getElementById('ipblock').style.display='block';
  else if(r.status==411)document.getElementById('deviceblock').style.display='block';
  else if(r.status==412)document.getElementById('hwblock').style.display='block';
  else if(r.status==422)showMsg('الرقم القومي غير صحيح: راجع 14 رقمًا وتاريخ الميلاد والمحافظة');else if(r.status==401)document.getElementById('wrong').style.display='block';
  else document.getElementById('closed').style.display='block';
 }}catch(e){{showMsg('مش متصل');}}
}}
</script></body></html>"""

def build_admin_html():
 cfg=load_cfg()
 LOGO_TAG = get_logo_tag(size=90, with_margin=True)
 HEADER_LOGO = get_header_logo_tag()
 ips = get_local_ips()
 primary = get_primary_ip() or (ips[0] if ips else "غير متاح")
 router_ip = primary
 hotspot_ip = primary
 for ip in ips:
  if ip.startswith("192.168.0.") or ip.startswith("192.168.1."): router_ip = ip; break
 for ip in ips:
  if ip.startswith("192.168.43.") or ip.startswith("192.168.137."): hotspot_ip = ip; break
 if primary and primary.startswith("10."): hotspot_ip = primary
 if primary and (primary.startswith("192.168.0.") or primary.startswith("192.168.1.")): router_ip = primary
 ips_html = ", ".join(ips)
 return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة تحكم APK V2.3</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#eef2ff,#f5f7fb);padding:12px}} .container{{max-width:1100px;margin:auto}} .hidden{{display:none!important}} .header{{background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;padding:16px;border-radius:20px;display:flex;justify-content:space-between}} .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:14px 0}} .stat{{background:#fff;border-radius:16px;padding:14px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,.06)}} .stat b{{display:block;font-size:26px;color:#1a73e8}} .card{{background:#fff;border-radius:18px;padding:16px;margin-bottom:14px;box-shadow:0 6px 20px rgba(0,0,0,.05)}} .card-title{{font-weight:800;margin-bottom:12px}} label{{font-size:12px;font-weight:700}} input,textarea{{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:12px;margin:4px 0}} .btn{{padding:12px 16px;border:none;border-radius:12px;font-weight:800;cursor:pointer}} .btn-primary{{background:#1a73e8;color:#fff}} .btn-success{{background:#16a34a;color:#fff}} .btn-danger{{background:#dc2626;color:#fff}} .btn-dark{{background:#0f172a;color:#fff}} .btn-warn{{background:#f59e0b;color:#fff}} .btn-light{{background:#f1f5f9}} .toolbar{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}} .table-wrap{{overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:750px}} th{{background:#0f172a;color:#fff;padding:10px}} td{{padding:8px;border-bottom:1px solid #eee;text-align:center}} #loginBox{{max-width:400px;margin:50px auto;background:#fff;padding:24px;border-radius:22px;text-align:center}} #adminTimer{{background:#fff;color:#0f172a;padding:8px 14px;border-radius:999px;font-size:12px;font-weight:800}} .linkBox{{background:#f8fafc;border:1px dashed #94a3b8;border-radius:12px;padding:10px;margin-top:8px}} .linkRow{{display:flex;gap:6px;margin:6px 0}}</style></head><body><div id="loginBox">{LOGO_TAG}<h2>دخول ادمن APK V2.3</h2><p style="font-size:12px;color:#64748b">الكلية التكنولوجية - د.م/ محمود منصور<br>Serial: {ANDROID_SERIAL[:12]} - IP مفتوح</p><input id="adminPass" type="password" placeholder="باسورد الادمن"><button onclick="login()" class="btn btn-primary" style="width:100%;margin-top:12px">🔐 دخول</button><p id="loginErr" style="display:none;color:#dc2626">غلط</p>{SOCIAL_FOOTER}</div><div id="dash" class="container hidden"><div class="header"><div style="display:flex;align-items:center;gap:10px">{HEADER_LOGO}<div><div style="font-weight:800">APK V2.3 Pro - IP مفتوح + سيريال + Logo</div><div style="font-size:11px;opacity:.8">الكلية التكنولوجية - د.م/ محمود منصور</div></div></div><div style="display:flex;gap:8px"><div id="adminTimer">⏱️ <span id="adminT">--:--</span></div><div id="status" style="padding:8px 14px;border-radius:999px;background:#fff;color:#0f172a">🔴 مقفول</div><button onclick="logout()" class="btn btn-light" style="padding:8px">🚪</button></div></div><div class="stats"><div class="stat"><b id="activeCount">0</b><span>النشط</span><div style="font-size:11px">/ <span id="maxCount">{cfg['max_active']}</span></div></div><div class="stat"><b id="waitCount">0</b><span>انتظار</span></div><div class="stat"><b id="count">0</b><span>اجمالي</span></div><div class="stat"><b id="lastMin">0</b><span>اخر دقيقة</span></div><div class="stat"><b id="showCount">0</b><span>المعروض</span></div></div><div class="card" style="background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1px solid #fcd34d"><div class="card-title">🔑 تغيير باسورد الادمن</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>القديم</label><input id="oldAdminPass" type="password"></div><div><label>الجديد</label><input id="newAdminPass" type="password"></div></div><button onclick="changeAdminPass()" class="btn btn-warn" style="width:100%;margin-top:10px">🔒 تغيير</button><div id="adminPassMsg" style="display:none;margin-top:8px;padding:10px;border-radius:10px;text-align:center"></div></div><div class="card" style="background:linear-gradient(135deg,#f8fafc,#eef2ff);border:1px dashed #93c5fd"><div class="card-title">⚙️ 1- اعدادات الطابور - IP مفتوح افتراضي</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>عدد الطابور</label><input id="maxActive" type="number" value="{cfg['max_active']}"></div><div><label>دفعات</label><input id="batch" type="number" value="{cfg['batch']}"></div></div><div><label>مدة بقاء الطالب</label><div style="display:flex;gap:8px"><input id="staySec" type="range" min="1" max="10" step="0.5" value="{cfg['stay_seconds']}" style="flex:1"><span id="stayVal">{cfg['stay_seconds']}s</span></div></div><label>رسالة التسجيل</label><textarea id="afterMsg">{cfg['after_msg']}</textarea><label>رسالة /done</label><textarea id="doneMsg">{cfg['done_msg']}</textarea><button onclick="saveAdv()" class="btn btn-dark" style="width:100%;margin-top:10px">💾 حفظ الاعدادات</button></div><div class="card" style="background:#fffbeb"><div class="card-title">🔒 2- تحكم التسجيل - APK</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label style="display:flex;gap:6px"><input type="checkbox" id="ipCheck" {"checked" if cfg['ip_check'] else ""} style="width:auto"> IP واحد = طالب واحد (شيل الصح عشان هوت سبوت 30 طالب)</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="nidCheck" {"checked" if cfg['nid_check'] else ""} style="width:auto"> منع القومي المكرر</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="deviceCheck" {"checked" if cfg.get('device_check',True) else ""} style="width:auto"> 🔒 منع نفس الجهاز VPN</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="hwCheck" {"checked" if cfg.get('hw_check',True) else ""} style="width:auto"> منع بصمة الجهاز hwId</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="androidCheck" {"checked" if cfg.get('android_check',True) else ""} style="width:auto"> منع سيريال اندرويد</label></div></div><label>قائمة سوداء قومي</label><textarea id="blackNids">{','.join(cfg['black_nids'])}</textarea><label>سوداء IP</label><textarea id="blackIps">{','.join(cfg['black_ips'])}</textarea><label>بيضاء IP</label><textarea id="whiteIps">{','.join(cfg['white_ips'])}</textarea></div><div class="card"><div class="card-title">🔑 3- فتح المحاضرة</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>كلمة سر المحاضرة</label><input id="lecturePass" placeholder="2026"></div><div><label>المدة بالدقائق</label><input id="minutes" type="number" value="30"></div></div><div style="display:flex;gap:8px;margin-top:12px"><button onclick="openNow()" class="btn btn-success" style="flex:2">✅ افتح</button><button onclick="closeNow()" class="btn btn-danger" style="flex:1">⛔ اقفل</button></div><div id="shareBox" style="display:none;background:#e0f2fe;padding:14px;border-radius:14px;margin-top:14px"><div style="font-weight:800">📡 روابط الطلبة APK:</div><div style="text-align:center;background:#fff;border-radius:12px;padding:12px;margin:10px 0"><div id="adminQr" style="display:flex;justify-content:center"></div><div style="font-size:12px;margin-top:6px">امسح الكود من موبايل الطالب</div></div><div class="linkBox"><div class="linkRow"><b>📱 هوتسبوت APK:</b><input id="shareLinkHotspot" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkHotspot')" class="btn btn-warn" style="padding:6px">نسخ</button></div><div style="font-size:11px">IP الهوتسبوت: <b>{hotspot_ip}</b> - كل IPs: {ips_html}</div><div style="display:flex;gap:6px;margin-top:6px"><input id="customHotspotIp" value="{hotspot_ip}" style="flex:1"><button onclick="updateHotspotLink()" class="btn btn-light" style="padding:6px">تحديث</button><button onclick="autoDetectIp()" class="btn btn-success" style="padding:6px">🔄 كشف</button></div></div><div class="linkBox" style="background:#dcfce7"><div class="linkRow"><b>📶 روتر:</b><input id="shareLinkRouter" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkRouter')" class="btn btn-success" style="padding:6px">نسخ</button></div><div style="font-size:11px">IP الراوتر: <b>{router_ip}</b></div><div style="display:flex;gap:6px;margin-top:6px"><input id="customRouterIp" value="{router_ip}" style="flex:1"><button onclick="updateRouterLink()" class="btn btn-light" style="padding:6px">تحديث</button></div></div><div class="linkBox"><div class="linkRow"><b>🖥️ لوكالهوست:</b><input id="shareLinkLocal" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkLocal')" class="btn btn-dark" style="padding:6px">نسخ</button></div></div><div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><button onclick="window.open(document.getElementById('shareLinkLocal').value,'_blank')" class="btn btn-dark" style="flex:1">🖥️ لوكال</button><button onclick="window.open(document.getElementById('shareLinkRouter').value,'_blank')" class="btn btn-success" style="flex:1">📶 روتر</button><button onclick="window.open(document.getElementById('shareLinkHotspot').value,'_blank')" class="btn btn-warn" style="flex:1">📱 هوتسبوت</button><button onclick="window.open('/projector','_blank')" class="btn btn-light" style="flex:1">🖥️ بروجيكتور</button></div><div style="font-size:12px;margin-top:8px">كلمة السر: <b id="currentPass"></b> | المدة: <b id="currentMin"></b> د</div><div style="font-size:11px;margin-top:8px;color:#64748b;background:#fff;padding:8px;border-radius:8px">روابط الادمن: <code>/admin</code> - كل IPs: {ips_html}<br><b>رابط ثابت للطلبة طول الترم:</b> <code>/go</code> - بيحول اوتوماتيك على اخر محاضرة</div></div></div><div class="card"><div class="card-title">📊 4- البيانات والتصدير</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input id="search" placeholder="🔍 بحث بالاسم او القومي"><input id="filterBoard" placeholder="فلتر رقم السبورة"></div><div class="toolbar"><button onclick="exportExcel()" class="btn btn-dark">📥 Excel CSV</button><button onclick="window.location.href='/export'" class="btn btn-success">⬇️ تصدير CSV عربي</button><button onclick="exportPDF()" class="btn btn-light">📄 PDF</button><button onclick="copyWhatsapp()" class="btn" style="background:#22c55e;color:#fff">🟢 واتساب</button><button onclick="clearQueue()" class="btn btn-warn">⚠️ فضي الطابور</button><button onclick="clearData()" class="btn btn-light" style="color:#dc2626">🗑️ مسح الكل</button></div><div class="table-wrap"><table id="tbl"><thead><tr><th>#</th><th>الوقت</th><th>الاسم</th><th>القومي</th><th>IP</th><th>الجهاز</th><th>سبورة</th><th>سيريال</th><th>🗑️ حذف</th></tr></thead><tbody></tbody></table></div>{SOCIAL_FOOTER}</div></div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let lastOpen="",lastSig="";
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}}catch(e){{}}}}
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
async function checkAuth(){{if(localStorage.getItem('admin_ok')==='1'){{document.getElementById('loginBox').classList.add('hidden');document.getElementById('dash').classList.remove('hidden');await syncTime();try{{let rc=await fetch('/get_config');let scfg=await rc.json();if(scfg.open&&scfg.open!="0"&&parseInt(scfg.open)>nowSynced()){{localStorage.setItem('openUntil',scfg.open);lastOpen=scfg.open;lastSig=scfg.s||simpleHash(scfg.open+SECRET);await autoDetectIp();buildAllLinks();document.getElementById('shareBox').style.display='block';document.getElementById('currentPass').innerText=scfg.lecturePass;let mins=Math.round((parseInt(scfg.open)-nowSynced())/60000);document.getElementById('currentMin').innerText=mins>0?mins:0;}}}}catch(e){{}}refresh();setInterval(()=>{{refresh();updateAdminTimer();}},1000);}}}}
function drawAdminQr(){{{{let box=document.getElementById("adminQr");if(!box)return;box.innerHTML="";let u=document.getElementById("shareLinkHotspot")?.value||document.getElementById("shareLinkRouter")?.value||"";if(window.QRCode&&u)new QRCode(box,{{{{text:u,width:180,height:180}}}});else box.innerText=u;}}}}function buildAllLinks(){{{{if(!lastOpen)return;let host=location.host;let baseLocal=location.protocol+'//'+host;let baseHotspot='http://'+(document.getElementById('customHotspotIp').value.trim()||'192.168.43.1')+':8080';let baseRouter='http://'+(document.getElementById('customRouterIp').value.trim()||'{{router_ip}}')+':8080';let path='/attendance.html?open='+lastOpen+'&s='+lastSig;document.getElementById('shareLinkLocal').value=baseLocal+path;document.getElementById('shareLinkHotspot').value=baseHotspot+path;document.getElementById('shareLinkRouter').value=baseRouter+path;fetch('/__save_latest?link='+encodeURIComponent(path));drawAdminQr();}}}}
async function autoDetectIp(){{{{try{{{{let rip=await fetch('/my_ips');let j=await rip.json();if(j.primary){{{{if(j.primary.startsWith('192.168.0.')||j.primary.startsWith('192.168.1.'))document.getElementById('customRouterIp').value=j.primary;if(j.primary.startsWith('10.')||j.primary.startsWith('192.168.43.'))document.getElementById('customHotspotIp').value=j.primary;}}}}if(j.ips){{{{let r=j.ips.find(x=>x.startsWith('192.168.0.')||x.startsWith('192.168.1.'));if(r)document.getElementById('customRouterIp').value=r;let h=j.ips.find(x=>x.startsWith('192.168.43.'))||j.ips.find(x=>x.startsWith('10.'));if(h)document.getElementById('customHotspotIp').value=h;}}}}buildAllLinks();}}}}catch(e){{{{}}}}}}}}
function updateHotspotLink(){{buildAllLinks();}}function updateRouterLink(){{buildAllLinks();}}setInterval(()=>{{autoDetectIp();}},1000);
function copyById(id){{let el=document.getElementById(id);el.select();document.execCommand('copy');alert('تم نسخ:\\n'+el.value);}}
async function login(){{let p=document.getElementById('adminPass').value;let r=await fetch('/admin_auth',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{pass:p}})}});let d=await r.json();if(d.ok){{localStorage.setItem('admin_ok','1');document.getElementById('loginErr').style.display='none';checkAuth();}}else{{document.getElementById('loginErr').style.display='block';}}}}
function logout(){{localStorage.removeItem('admin_ok');location.reload();}}
async function changeAdminPass(){{let oldP=document.getElementById('oldAdminPass').value.trim();let newP=document.getElementById('newAdminPass').value.trim();let msg=document.getElementById('adminPassMsg');if(!oldP||!newP){{msg.style.display='block';msg.style.background='#fee2e2';msg.style.color='#991b1b';msg.innerText='❌ اكتب القديم والجديد';return;}}if(newP.length<4){{msg.style.display='block';msg.style.background='#fee2e2';msg.style.color='#991b1b';msg.innerText='❌ قصير';return;}}let r=await fetch('/change_admin_pass',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{oldPass:oldP,newPass:newP}})}});let d=await r.json();msg.style.display='block';if(d.ok){{msg.style.background='#dcfce7';msg.style.color='#166534';msg.innerText='✅ تم تغيير: '+newP;document.getElementById('oldAdminPass').value='';document.getElementById('newAdminPass').value='';}}else{{msg.style.background='#fee2e2';msg.style.color='#991b1b';msg.innerText='❌ '+(d.error||'خطأ');}}}}
checkAuth();
function updateAdminTimer(){{let u=localStorage.getItem('openUntil');let el=document.getElementById('adminT');if(!u){{el.innerText='--:--';return;}}let diff=parseInt(u)-nowSynced();if(diff<=0){{el.innerText='انتهى';return;}}let m=Math.floor(diff/60000),s=Math.floor((diff%60000)/1000);el.innerText=m+':'+(s<10?'0':'')+s;}}
document.getElementById('staySec')?.addEventListener('input',e=>document.getElementById('stayVal').innerText=e.target.value+'s');
async function saveAdv(){{let cfg={{max_active:parseInt(document.getElementById('maxActive').value),stay_seconds:parseFloat(document.getElementById('staySec').value),batch:parseInt(document.getElementById('batch').value),after_msg:document.getElementById('afterMsg').value,done_msg:document.getElementById('doneMsg').value,ip_check:document.getElementById('ipCheck').checked,nid_check:document.getElementById('nidCheck').checked,device_check:document.getElementById('deviceCheck').checked,hw_check:document.getElementById('hwCheck').checked,android_check:document.getElementById('androidCheck').checked,black_nids:document.getElementById('blackNids').value.split(',').map(s=>s.trim()).filter(s=>s),black_ips:document.getElementById('blackIps').value.split(',').map(s=>s.trim()).filter(s=>s),white_ips:document.getElementById('whiteIps').value.split(',').map(s=>s.trim()).filter(s=>s)}};await fetch('/save_adv',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(cfg)}});alert('✅ تم حفظ');location.reload();}}
async function openNow(){{let lp=document.getElementById('lecturePass').value.trim();let mins=parseInt(document.getElementById('minutes').value);if(!lp){{alert('اكتب كلمة السر');return;}}let u=nowSynced()+mins*60*1000;let sig=simpleHash(u.toString()+SECRET);localStorage.setItem('openUntil',u.toString());lastOpen=u.toString();lastSig=sig;await autoDetectIp();buildAllLinks();let sb=document.getElementById('shareBox');if(sb)sb.style.display='block';document.getElementById('currentPass').innerText=lp;document.getElementById('currentMin').innerText=mins;await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:u.toString(),s:sig,lecturePass:lp}})}});refresh();}}
async function closeNow(){{localStorage.removeItem('openUntil');document.getElementById('shareBox').style.display='none';await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:"0",s:"",lecturePass:""}})}});refresh();alert('⛔ اتقفل عند كل الطلبة');}}
let cachedData=[];let lastCounts=[];
function filterRender(){{let q=document.getElementById('search').value.trim().toLowerCase();let b=document.getElementById('filterBoard').value.trim();let tb=document.querySelector('#tbl tbody');tb.innerHTML='';let filtered=cachedData.filter(x=>{{let ok=true;if(q)ok=x.name.toLowerCase().includes(q)||x.nid.includes(q);if(b)ok=ok&&(x.board||'').includes(b);return ok;}});document.getElementById('showCount').innerText=filtered.length;filtered.forEach((x,i)=>{{tb.innerHTML+=`<tr><td>${{i+1}}</td><td>${{x.time}}</td><td>${{x.name}}</td><td>${{x.nid}}</td><td>${{x.ip||''}}</td><td>${{(x.deviceId||'').slice(0,8)}}</td><td>${{x.board}}</td><td>${{(x.androidId||'').slice(0,8)}}</td><td><button onclick="deleteOne('${{x.nid}}')" class="btn btn-danger" style="padding:4px 8px;font-size:11px">🗑️</button></td></tr>`}});}}
async function refresh(){{let u=localStorage.getItem('openUntil');let st=document.getElementById('status');if(u&&nowSynced()<parseInt(u)){{st.innerHTML='🟢 مفتوح';st.style.background='#22c55e';st.style.color='#fff';}}else{{st.innerHTML='🔴 مقفول';st.style.background='#fff';st.style.color='#0f172a';}}try{{let r=await fetch('/list');let d=await r.json();cachedData=d.list||[];document.getElementById('count').innerText=cachedData.length;document.getElementById('activeCount').innerText=d.active;document.getElementById('maxCount').innerText=d.max_active;document.getElementById('waitCount').innerText=d.waiting;let now=Date.now();lastCounts.push({{t:now,c:cachedData.length}});lastCounts=lastCounts.filter(x=>now-x.t<60000);let lastMinEl=document.getElementById('lastMin');if(lastCounts.length>1){{let diff=cachedData.length-(lastCounts[0]?.c||0);lastMinEl.innerText=Math.max(0,diff);}}filterRender();}}catch(e){{}}}}
async function deleteOne(nid){{if(!confirm('تمسح الطالب ده؟ \\n'+nid))return;let r=await fetch('/delete_one',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{nid}})}});let d=await r.json();if(d.ok){{alert('✅ اتمسح');refresh();}}else{{alert('❌ مش لاقيه');}}}}
document.getElementById('search')?.addEventListener('input',filterRender);document.getElementById('filterBoard')?.addEventListener('input',filterRender);
function exportExcel(){{if(!cachedData.length){{alert('لا يوجد');return;}}let csv='\\uFEFFالوقت,الاسم,القومي,IP,الجهاز,السبورة,سيريال\\n'+cachedData.map(x=>`"${{x.time}}","${{x.name}}","${{x.nid}}","${{x.ip||''}}","${{x.deviceId||''}}","${{x.board}}","${{x.androidId||''}}"`).join('\\n');let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv;charset=utf-8;'}}));a.download='attendance_'+new Date().toISOString().slice(0,10)+'.csv';a.click();}}
function exportPDF(){{let w=window.open('','_blank');let rows=cachedData.map((x,i)=>`<tr><td>${{i+1}}</td><td>${{x.time}}</td><td>${{x.name}}</td><td>${{x.nid}}</td><td>${{x.board}}</td></tr>`).join('');w.document.write(`<html dir="rtl"><head><meta charset="utf-8"><title>PDF</title></head><body><h2>كشف حضور - ${{new Date().toLocaleString('ar-EG')}}</h2><table border="1" style="width:100%;border-collapse:collapse;text-align:center"><tr><th>#</th><th>الوقت</th><th>الاسم</th><th>القومي</th><th>السبورة</th></tr>${{rows}}</table><script>window.print()<\\/script></body></html>`);}}
function copyWhatsapp(){{if(!cachedData.length){{alert('لا يوجد');return;}}let txt=`كشف حضور ${{new Date().toLocaleDateString('ar-EG')}} - العدد ${{cachedData.length}}\\n`+cachedData.map((x,i)=>`${{i+1}}- ${{x.name}} - ${{x.nid}} - سبورة ${{x.board}}`).join('\\n');navigator.clipboard.writeText(txt).then(()=>alert('تم نسخ للواتساب'))}}
async function clearQueue(){{if(confirm('تفضي الطابور؟')){{await fetch('/clear_queue',{{method:'POST'}});refresh();}}}}
async function clearData(){{if(confirm('تمسح الكل؟')){{await fetch('/clear',{{method:'POST'}});refresh();}}}}
</script></body></html>"""

def ensure_files():
 cfg=load_cfg()
 save_cfg(cfg)
 if not os.path.exists(DATA_FILE):
  with open(DATA_FILE,"w",encoding="utf-8") as f: f.write("[]")

class Handler(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a): return
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
     with open(DATA_FILE,'r',encoding='utf-8') as f: all_data=json.load(f)
     new_data=[x for x in all_data if x.get('nid')!=nid_to_del]
     if len(new_data)!=len(all_data):
      deleted=True
      with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(new_data,f,ensure_ascii=False,indent=2)
    except: pass
   self.send_response(200)
   self.send_header('Content-Type','application/json')
   self.end_headers()
   self.wfile.write(json.dumps({"ok": deleted}).encode('utf-8'))
   return
  if self.path == '/change_admin_pass':
   length = int(self.headers.get('content-length',0))
   body = self.rfile.read(length).decode('utf-8')
   data = json.loads(body)
   old = data.get('oldPass','')
   new = data.get('newPass','').strip()
   self.send_response(200)
   self.send_header('Content-Type','application/json')
   self.end_headers()
   if old!= cfg.get('adminPass', DEFAULT_ADMIN_PASS):
    self.wfile.write(json.dumps({"ok": False, "error": "الباسورد الحالي غلط"}).encode('utf-8')); return
   if len(new) < 4:
    self.wfile.write(json.dumps({"ok": False, "error": "الجديد قصير"}).encode('utf-8')); return
   cfg['adminPass'] = new
   save_cfg(cfg)
   self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))
   return
  if self.path == '/save_adv':
   length = int(self.headers.get('content-length',0))
   body = self.rfile.read(length).decode('utf-8')
   data = json.loads(body)
   for k in ["max_active","stay_seconds","batch","after_msg","done_msg","ip_check","nid_check","device_check","hw_check","android_check","black_nids","black_ips","white_ips"]:
    if k in data: cfg[k]=data[k]
   save_cfg(cfg)
   self.send_response(200); self.end_headers(); return
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
    cfg_open = cfg.get('open','0')
    if cfg_open == "0" or cfg_open == "" or int(cfg_open) < now_ms:
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
     self.wfile.write(json.dumps({"error":"الرقم القومي غير صحيح، يجب أن يكون 14 رقمًا وتاريخ الميلاد والمحافظة صحيحين"},ensure_ascii=False).encode('utf-8')); return
    deviceId = data.get('deviceId','').strip()
    hwId = data.get('hwId','').strip()
    androidId = data.get('androidId','').strip()
    is_white = client_ip in cfg.get('white_ips',[]) or client_ip == '127.0.0.1'
    if not is_white:
     if nid in cfg.get('black_nids',[]) or client_ip in cfg.get('black_ips',[]):
      self.send_response(403)
      self.send_header('Content-Type','application/json')
      self.end_headers()
      self.wfile.write(json.dumps({"black":True}).encode('utf-8')); return
    all_data=[]
    if os.path.exists(DATA_FILE):
     with open(DATA_FILE,'r',encoding='utf-8') as f:
      try: all_data=json.load(f)
      except: all_data=[]
    if cfg.get('nid_check',True) and any(x.get('nid')==nid for x in all_data):
     self.send_response(409); self.end_headers(); return
    if cfg.get('ip_check',False) and not is_white and any(x.get('ip')==client_ip for x in all_data):
     self.send_response(410); self.end_headers(); return
    if cfg.get('device_check',True) and deviceId and not is_white and any(x.get('deviceId')==deviceId for x in all_data):
     self.send_response(411); self.end_headers(); return
    if cfg.get('hw_check',True) and hwId and not is_white and any(x.get('hwId')==hwId for x in all_data):
     self.send_response(412); self.end_headers(); return
    if cfg.get('android_check',True) and androidId and not is_white and any(x.get('androidId')==androidId for x in all_data):
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
    rec={"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"name":data.get('name',''),"nid":nid,"board":data.get('board',''),"pass":data.get('pass',''),"ip":client_ip,"deviceId":deviceId,"hwId":hwId,"androidId":androidId,"source":"local-app" if data.get("localApp") else "web"}
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
  client_ip = self.client_address[0]
  cfg=load_cfg()
  parsed = urllib.parse.urlparse(self.path)
  path = parsed.path
  query = parsed.query
  low = path.lower()
  if low == '/health':
   self.send_response(200)
   self.send_header('Content-Type','application/json; charset=utf-8')
   self.send_header('Cache-Control','no-store')
   self.end_headers()
   self.wfile.write(json.dumps({"app":"attendance-local","ok":True}).encode('utf-8'))
   return
  if low == '/__save_latest':
   params = urllib.parse.parse_qs(query)
   link = params.get('link', [''])[0]
   if link:
    link = urllib.parse.unquote(link)
    try:
     with open(LATEST_FILE,'w',encoding='utf-8') as f: f.write(link)
    except: pass
   self.send_response(200)
   self.send_header('Content-Type','text/plain')
   self.end_headers()
   self.wfile.write(b'Saved')
   return
  if low == '/' or low == '/go' or low == '/go.html' or low == '/index.html' or (low == '/attendance.html' and 'open' not in query):
   if os.path.exists(LATEST_FILE):
    try:
     with open(LATEST_FILE,'r',encoding='utf-8') as f: latest = f.read().strip()
     if latest and 'open=' in latest:
      cfg_open = cfg.get('open','0')
      if cfg_open!="0" and cfg_open!="" and int(cfg_open) > int(datetime.now().timestamp()*1000):
       self.send_response(302)
       self.send_header('Location', latest)
       self.send_header('Cache-Control','no-store, no-cache, must-revalidate')
       self.end_headers()
       return
    except: pass
  if low == '/local-app':
   self.send_response(302)
   self.send_header('Location', '/attendance.html?local-app=1')
   self.send_header('Cache-Control','no-store')
   self.end_headers()
   return
  if low == '/export':
   try:
    with open(DATA_FILE,'r',encoding='utf-8') as f:
     export_rows=json.load(f)
   except Exception:
    export_rows=[]
   import csv, io
   output=io.StringIO(newline='')
   writer=csv.writer(output)
   writer.writerow(['الوقت','الاسم','الرقم القومي','IP','الجهاز','بصمة الجهاز','رقم السبورة','سيريال أندرويد','مصدر التسجيل'])
   for row in export_rows:
    writer.writerow([row.get('time',''),row.get('name',''),row.get('nid',''),row.get('ip',''),row.get('deviceId',''),row.get('hwId',''),row.get('board',''),row.get('androidId',''),row.get('source','web')])
   payload=output.getvalue().encode('utf-8-sig')
   self.send_response(200)
   self.send_header('Content-Type','text/csv; charset=utf-8')
   self.send_header('Content-Disposition','attachment; filename="attendance.csv"')
   self.send_header('Content-Length',str(len(payload)))
   self.end_headers()
   self.wfile.write(payload)
   return
  if low == '/my_ips':
   self.send_response(200)
   self.send_header('Content-Type','application/json')
   self.send_header('Access-Control-Allow-Origin','*')
   self.end_headers()
   self.wfile.write(json.dumps({"ips": get_local_ips(), "primary": get_primary_ip(), "all_if": get_interface_ips()}).encode('utf-8'))
   return
  if low.startswith('/logo'):
   lf=find_logo_file()
   if lf and os.path.exists(lf):
    mime,_=mimetypes.guess_type(lf)
    self.send_response(200)
    self.send_header('Content-type', mime or 'image/jpeg')
    self.send_header('Cache-Control','no-store')
    self.end_headers()
    with open(lf,'rb') as f: self.wfile.write(f.read())
    return
   self.send_response(204); self.end_headers(); return
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
  if low == '/get_full_config':
   self.send_response(200)
   self.send_header('Content-Type','application/json; charset=utf-8')
   self.end_headers()
   self.wfile.write(json.dumps(cfg).encode('utf-8'))
   return
  if path == '/status':
   pos=0
   if client_ip in waiting_queue: pos=list(waiting_queue.keys()).index(client_ip)+1
   msg, interval = get_wait_msg(pos, cfg['max_active'], cfg['stay_seconds'], cfg['batch']) if pos>0 else ("",3)
   self.send_response(200)
   self.send_header('Content-Type','application/json; charset=utf-8')
   self.end_headers()
   self.wfile.write(json.dumps({"active":len(active_ips),"max":cfg['max_active'],"max_active":cfg['max_active'],"waiting":len(waiting_queue),"pos":pos,"msg":msg,"interval":interval,"can_enter": len(active_ips) < cfg['max_active'] or client_ip in cfg.get('white_ips',[])}).encode('utf-8'))
   return
  if low == '/projector' or low == '/projector.html':
   self.send_response(200)
   self.send_header('Content-type','text/html; charset=utf-8')
   self.end_headers()
   LOGO_TAG = get_logo_tag(size=90, with_margin=True)
   proj = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><title>بروجيكتور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@800&display=swap" rel="stylesheet"><style>body{{font-family:'Tajawal',Tahoma;background:#000;color:#fff;text-align:center;padding:20px}}#big{{font-size:84px;font-weight:800}}#sub{{font-size:22px;margin-top:14px;color:#93c5fd;line-height:1.7}}#msg{{font-size:20px;margin-top:14px;color:#facc15}}.foot{{margin-top:30px;font-size:11px;color:#64748b}}</style></head><body>{LOGO_TAG}<div id="big">--:--</div><div id="sub">النشط <span id="a">0</span> / {cfg['max_active']} | انتظار <span id="w">0</span><br>الكلية التكنولوجية بالمحلة<br>د.م/ محمود منصور - APK V2.3</div><div id="msg"></div><div class="foot">© حقوق محفوظة لـ م/ محمود منصور 2026 - {ANDROID_SERIAL}</div><script>
let serverOffset=0;let openUntil=localStorage.getItem('openUntil');
async function syncTime(){{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}}
function nowSynced(){{return Date.now()+serverOffset;}}
function upd(){{if(!openUntil){{document.getElementById('big').innerText='مقفول';return;}}let diff=parseInt(openUntil)-nowSynced();if(diff<=0){{document.getElementById('big').innerText='انتهى';return;}}let m=Math.floor(diff/60000),s=Math.floor((diff%60000)/1000);document.getElementById('big').innerText=m+':'+(s<10?'0':'')+s;}}
syncTime().then(()=>{{setInterval(upd,1000);upd();}});
setInterval(()=>{{fetch('/list').then(r=>r.json()).then(d=>{{document.getElementById('a').innerText=d.active;document.getElementById('w').innerText=d.waiting;document.getElementById('msg').innerText='اخر دقيقة: '+d.last_min+' طالب';}})}},2000);
</script></body></html>"""
   self.wfile.write(proj.encode('utf-8')); return
  if low == '/done' or low == '/done.html':
   self.send_response(200)
   self.send_header('Content-type','text/html; charset=utf-8')
   self.end_headers()
   LOGO_TAG = get_logo_tag(size=90, with_margin=True)
   done_html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تم</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@700;800&display=swap" rel="stylesheet"><style>body{{text-align:center;font-family:'Tajawal',Tahoma;padding:15px;background:linear-gradient(135deg,#f0fdf4,#fff);min-height:100vh}}.card{{max-width:440px;margin:auto;background:#fff;padding:20px;border-radius:20px;box-shadow:0 12px 30px rgba(0,0,0,.1)}}.btn{{padding:18px 30px;font-size:20px;background:linear-gradient(135deg,#dc2626,#991b1b);color:white;border:none;border-radius:14px;margin-top:20px;width:100%;font-family:'Tajawal';font-weight:800}}#txt{{margin-top:15px;font-weight:800;color:#0f172a;line-height:1.8;font-size:15px;background:#f8fafc;padding:12px;border-radius:12px}}</style></head><body><div class="card">{LOGO_TAG}<h1 style="color:#16a34a;font-size:22px">{cfg['done_msg']}</h1><p style="font-size:13px;line-height:1.7">الكلية التكنولوجية بالمحلة<br>المعهد الصناعي<br><b>د.م/ محمود منصور</b></p><h3>دوس الزرار عشان تفضي مكان لزميلك - النشط {len(active_ips)}/{cfg['max_active']}</h3><button class="btn" onclick="fasl()">📴 افصل الواي فاي واخرج</button><p id="txt"></p>{SOCIAL_FOOTER}</div><script>
function fasl(){{
  let txt=document.getElementById('txt');
  txt.innerHTML="⏳ جاري فتح اعدادات الواي فاي...";
  try{{let a=document.createElement('a');a.href="intent:#Intent;action=android.settings.WIFI_SETTINGS;package=com.android.settings;end";document.body.appendChild(a);a.click();}}catch(e){{window.location.href="intent:#Intent;action=android.settings.WIFI_SETTINGS;package=com.android.settings;end";}}
  setTimeout(()=>{{try{{window.location.href="intent:#Intent;action=android.settings.WIFI_SETTINGS;end";}}catch(e){{}}}},800);
  setTimeout(()=>{{txt.innerHTML="✅ تمام سجلت<br>👆 لو مفتحتش - اسحب الشاشة من فوق<br>واقفل الواي فاي بايدك";}},2200);
}}
</script></body></html>"""
   self.wfile.write(done_html.encode('utf-8')); return
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

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
 allow_reuse_address = True
 daemon_threads = True

def run_server():
 ensure_files()
 try:
  with ThreadingHTTPServer(('0.0.0.0',8080), Handler) as httpd:
   print("Attendance server listening on 0.0.0.0:8080")
   httpd.serve_forever()
 except OSError as exc:
  print("Attendance server could not start:", exc)

class MainApp(App):
 def _acquire_wake_lock(self):
  try:
   from jnius import autoclass
   PythonActivity = autoclass('org.kivy.android.PythonActivity')
   Context = autoclass('android.content.Context')
   PowerManager = autoclass('android.os.PowerManager')
   activity = PythonActivity.mActivity
   pm = activity.getSystemService(Context.POWER_SERVICE)
   self._wake_lock = pm.newWakeLock(PowerManager.SCREEN_DIM_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, "AttendanceApp::AttendanceWakeLock")
   self._wake_lock.acquire()
  except Exception as e:
   print("Wake lock unavailable (ensure android.permission.WAKE_LOCK in Buildozer):", e)

 def _refresh_home(self, *_):
  try:
   ips = get_local_ips()
   primary = get_primary_ip() or (ips[0] if ips else "غير متاح")
   self.ip_label.text = f"APK الحضور - AutoDetect\nIP الحالي: {primary}:8080\nكل العناوين: {', '.join(ips[:6])}\nSerial: {ANDROID_SERIAL[:10]}\nالرابط الثابت: http://127.0.0.1:8080/go"
  except Exception:
   pass

 def _show_home(self, *_):
  self.root.clear_widgets()
  root = BoxLayout(orientation='vertical', padding=12, spacing=10)
  self.ip_label = Label(text="جارٍ كشف IP ...", size_hint_y=0.35)
  btn1 = Button(text="📱 تسجيل حضور الطالب داخل التطبيق", size_hint_y=0.18)
  btn2 = Button(text="🔐 فتح لوحة تحكم الدكتور", size_hint_y=0.18)
  btn3 = Button(text="🌐 فتح صفحة QR والتقارير", size_hint_y=0.18)
  btn1.bind(on_press=self._show_student)
  btn2.bind(on_press=lambda x: webbrowser.open('http://127.0.0.1:8080/admin'))
  btn3.bind(on_press=lambda x: webbrowser.open('http://127.0.0.1:8080/'))
  root.add_widget(self.ip_label)
  root.add_widget(btn1)
  root.add_widget(btn2)
  root.add_widget(btn3)
  self.root.add_widget(root)
  self._refresh_home()

 def _show_student(self, *_):
  root = BoxLayout(orientation='vertical', padding=12, spacing=7)
  root.add_widget(Label(text="تسجيل الحضور من داخل التطبيق", size_hint_y=None, height=42))
  self.server_url = TextInput(text=getattr(self, "last_server_url", ""), hint_text="عنوان الدكتور مثل http://192.168.43.1:8080", multiline=False, size_hint_y=None, height=46)
  self.student_pass = TextInput(hint_text="كلمة سر المحاضرة", password=True, multiline=False, size_hint_y=None, height=46)
  self.student_board = TextInput(hint_text="رقم السبورة", multiline=False, input_filter='int', size_hint_y=None, height=46)
  self.student_name = TextInput(hint_text="الاسم رباعي عربي", multiline=False, size_hint_y=None, height=46)
  self.student_nid = TextInput(hint_text="الرقم القومي 14 رقم", multiline=False, input_filter='int', size_hint_y=None, height=46)
  self.student_msg = Label(text="اتصل بشبكة الدكتور ثم امسح QR أو استخدم الكشف التلقائي.", size_hint_y=0.22)
  actions = BoxLayout(size_hint_y=None, height=46, spacing=6)
  scan = Button(text="📷 مسح QR")
  discover = Button(text="🔎 اتصال تلقائي")
  scan.bind(on_press=self._scan_qr)
  discover.bind(on_press=self._discover_server)
  actions.add_widget(scan); actions.add_widget(discover)
  send = Button(text="إرسال الحضور", size_hint_y=None, height=50)
  back = Button(text="رجوع", size_hint_y=None, height=42)
  send.bind(on_press=self._submit_native_attendance)
  back.bind(on_press=self._show_home)
  for widget in (self.server_url, actions, self.student_pass, self.student_board, self.student_name, self.student_nid, self.student_msg, send, back):
   root.add_widget(widget)
  self.root.clear_widgets(); self.root.add_widget(root)

 def _set_server_url(self, value):
  value = (value or "").strip()
  if value and not value.startswith(("http://", "https://")):
   value = "http://" + value
  if value.endswith("/"):
   value = value[:-1]
  self.last_server_url = value
  if hasattr(self, "server_url"):
   self.server_url.text = value
  return value

 def _scan_qr(self, *_):
  """Launch Android's QR scanner intent if a compatible scanner is installed."""
  try:
   from jnius import autoclass
   Intent = autoclass('android.content.Intent')
   PythonActivity = autoclass('org.kivy.android.PythonActivity')
   intent = Intent("com.google.zxing.client.android.SCAN")
   intent.putExtra("SCAN_MODE", "QR_CODE_MODE")
   activity = PythonActivity.mActivity
   if not getattr(self, "_activity_result_bound", False):
    activity.bind(on_activity_result=self._on_activity_result)
    self._activity_result_bound = True
   activity.startActivityForResult(intent, 1201)
   self.student_msg.text = "وجّه الكاميرا إلى QR الخاص بالدكتور."
  except Exception:
   self.student_msg.text = "لم يتم العثور على قارئ QR متوافق. استخدم الاتصال التلقائي أو اكتب عنوان الدكتور يدويًا."

 def _on_activity_result(self, request_code, result_code, intent):
  try:
   if int(request_code) != 1201 or intent is None:
    return
   data = intent.getStringExtra("SCAN_RESULT")
   if not data:
    return
   from urllib.parse import urlparse
   parsed = urlparse(str(data).strip() if str(data).strip().startswith(('http://','https://')) else 'http://' + str(data).strip())
   if parsed.hostname:
    port = parsed.port or 8080
    self._set_server_url(f"http://{parsed.hostname}:{port}")
    self.student_msg.text = "تم قراءة QR. اضغط إرسال الحضور بعد استكمال البيانات."
   else:
    self.student_msg.text = "QR لا يحتوي على عنوان خادم صالح."
  except Exception as exc:
   self.student_msg.text = "تعذر قراءة نتيجة QR: " + str(exc)

 def _discover_server(self, *_):
  self.student_msg.text = "جارٍ البحث عن محاضرة مفتوحة على الشبكة المحلية..."
  def worker():
   import urllib.request, urllib.error, concurrent.futures, ipaddress
   found = None
   own_ip = get_primary_ip()
   candidates = []
   if own_ip:
    try:
     net = ipaddress.ip_network(own_ip + '/24', strict=False)
     candidates = [str(ip) for ip in net.hosts() if str(ip) != own_ip]
    except Exception:
     candidates = []
   candidates += ["192.168.43.1", "192.168.49.1", "192.168.137.1", "192.168.0.1", "192.168.1.1"]
   candidates = list(dict.fromkeys(candidates))
   def probe(ip):
    try:
     base = 'http://' + ip + ':8080'
     with urllib.request.urlopen(base + '/health', timeout=0.45) as r:
      health = json.loads(r.read().decode('utf-8'))
     if not health.get('ok'):
      return None
     with urllib.request.urlopen(base + '/get_config', timeout=0.45) as r:
      cfg = json.loads(r.read().decode('utf-8'))
     if str(cfg.get('open','0')) not in ('','0') and int(cfg.get('open','0')) > int(datetime.now().timestamp()*1000):
      return base
    except Exception:
     return None
    return None
   try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
     for result in pool.map(probe, candidates):
      if result:
       found = result
       break
   except Exception:
    pass
   def done(_dt):
    if found:
     self._set_server_url(found)
     self.student_msg.text = "✅ تم العثور على محاضرة مفتوحة: " + found
    else:
     self.student_msg.text = "لم نعثر على محاضرة مفتوحة. تأكد أن الجهازين على الشبكة نفسها وأن الدكتور فتح المحاضرة، ثم امسح QR أو اكتب IP الدكتور."
   Clock.schedule_once(done, 0)
  threading.Thread(target=worker, daemon=True).start()

 def _submit_native_attendance(self, *_):
  import urllib.request, urllib.error
  server = self._set_server_url(self.server_url.text if hasattr(self, "server_url") else "")
  if not server:
   self.student_msg.text = "امسح QR أو اضغط اتصال تلقائي لتحديد هاتف الدكتور أولًا."
   return
  nid = normalize_nid(self.student_nid.text)
  if not self.student_pass.text.strip() or not self.student_board.text.strip() or not self.student_name.text.strip() or not nid:
   self.student_msg.text = "من فضلك أكمل كل البيانات."
   return
  if not valid_national_id(nid):
   self.student_msg.text = "الرقم القومي غير صحيح. راجع 14 رقمًا وتاريخ الميلاد والمحافظة."
   return
  self.student_msg.text = "جارٍ إرسال الحضور إلى هاتف الدكتور..."
  device_id = "android-" + str(ANDROID_SERIAL)
  payload = {"name": self.student_name.text.strip(), "nid": nid,
             "board": self.student_board.text.strip(), "pass": self.student_pass.text.strip(),
             "deviceId": device_id, "hwId": device_id, "androidId": str(ANDROID_SERIAL), "localApp": True}
  def worker():
   try:
    with urllib.request.urlopen(server + '/get_config', timeout=4) as resp:
     cfg = json.loads(resp.read().decode('utf-8'))
    payload["open"] = cfg.get("open", "")
    payload["s"] = cfg.get("s", "")
    req = urllib.request.Request(server + '/save', data=json.dumps(payload,ensure_ascii=False).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=8) as resp:
     result = json.loads(resp.read().decode('utf-8'))
    message = "✅ تم تسجيل الحضور بنجاح" if result.get("ok") else "لم يتم التسجيل."
   except urllib.error.HTTPError as e:
    messages = {401:"كلمة سر المحاضرة غير صحيحة.",403:"المحاضرة مغلقة أو الرقم محظور.",409:"الرقم القومي مسجل بالفعل.",410:"هذا IP مسجل بالفعل.",411:"هذا الجهاز سجل بالفعل.",412:"بصمة الجهاز مسجلة.",413:"معرّف Android مسجل بالفعل.",422:"الرقم القومي غير صحيح.",429:"الطابور ممتلئ، حاول مرة أخرى."}
    message = "❌ " + messages.get(e.code, f"تعذر التسجيل (HTTP {e.code}).")
   except Exception as e:
    message = "❌ تعذر الاتصال بخادم الدكتور: " + str(e)
   Clock.schedule_once(lambda dt: setattr(self.student_msg,'text',message),0)
  threading.Thread(target=worker,daemon=True).start()

 def build(self):
  configure_storage(self)
  ensure_files()
  threading.Thread(target=run_server, daemon=True).start()
  self._acquire_wake_lock()
  from kivy.uix.floatlayout import FloatLayout
  self.root = BoxLayout(orientation='vertical')
  self._show_home()
  Clock.schedule_interval(self._refresh_home, 1)
  return self.root

 def on_stop(self):
  try:
   if getattr(self, "_wake_lock", None) and self._wake_lock.isHeld():
    self._wake_lock.release()
  except Exception:
   pass

if __name__ == '__main__':
 MainApp().run()
