from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, RoundedRectangle
from kivy.core.text import LabelBase
import http.server, json, os, threading, base64, socket, re, subprocess
from datetime import datetime
from collections import OrderedDict
import urllib.parse, mimetypes, socketserver, webbrowser

# --- إعداد ودعم اللغة العربية وشكل النصوص ---
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except ImportError:
    HAS_ARABIC_SUPPORT = False

def ar(text):
    """إعادة تشكيل النص العربي ليظهر بصورة صحيحة وبدون مربعات"""
    if not text:
        return ""
    if HAS_ARABIC_SUPPORT:
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            return str(text)
    return str(text)

# البحث عن خط مدعوم للعربية
SYSTEM_ARABIC_FONT = None
FONT_CANDIDATES = [
    "Amiri-Regular.ttf",
    "/system/fonts/NotoNaskhArabic-Regular.ttf",
    "/system/fonts/DroidSansArabic.ttf",
    "arial.ttf"
]
for font_path in FONT_CANDIDATES:
    if os.path.exists(font_path):
        SYSTEM_ARABIC_FONT = font_path
        break

if SYSTEM_ARABIC_FONT:
    try:
        LabelBase.register(name="ArabicFont", fn_regular=SYSTEM_ARABIC_FONT)
        DEFAULT_FONT_NAME = "ArabicFont"
    except:
        DEFAULT_FONT_NAME = None
else:
    DEFAULT_FONT_NAME = None

def get_android_id():
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        Secure = autoclass('android.provider.Settings$Secure')
        aid = Secure.getString(activity.getContentResolver(), Secure.ANDROID_ID)
        if aid: return str(aid)
    except:
        pass
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
    except:
        target = BASE_DIR
    
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
    "batch": 5, "adminPass": DEFAULT_ADMIN_PASS, "local_app_enabled": True
}
active_ips = OrderedDict()
waiting_queue = OrderedDict()

def get_real_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip.startswith("127."): return "192.168.43.1"
        return ip
    except: return "192.168.43.1"

def get_interface_ips():
    ips = []
    try:
        out = ""
        for cmd in ["ip addr show", "ip -4 addr", "ifconfig"]:
            try:
                out = subprocess.check_output(cmd, shell=True, timeout=1, stderr=subprocess.STDOUT).decode('utf-8','ignore')
                if "inet " in out: break
            except: continue
        found = re.findall(r'inet\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)', out)
        for ip in found:
            if not ip.startswith("127.") and ip not in ips: ips.append(ip)
    except: pass
    return ips

def get_primary_ip():
    real = get_real_ip()
    if real and not real.startswith("127."): return real
    return "192.168.43.1"

def get_local_ips():
    ips = []
    seen = set()
    for ip in get_interface_ips():
        if ip not in seen: ips.append(ip); seen.add(ip)
    primary = get_primary_ip()
    if primary and primary not in seen: ips.append(primary); seen.add(primary)
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
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
            for k, v in DEFAULT_CFG.items():
                if k not in d: d[k] = v
            return d
    except:
        return DEFAULT_CFG.copy()

def save_cfg(c):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(c, f, ensure_ascii=False, indent=2)
    except:
        pass

def free_ip(ip):
    if ip in active_ips: del active_ips[ip]
    if ip in waiting_queue: del waiting_queue[ip]

def get_wait_msg(pos, max_a, stay, batch):
    est_sec = (pos / batch) * stay + 5
    m = int(est_sec // 60); s = int(est_sec % 60)
    time_str = f"{m} دقيقة {s} ثانية" if m > 0 else f"{s} ثانية"
    if pos <= 10: return f"⏳ فاضل قدامك {pos} بس - خليك فاتح الصفحة هتدخل لوحدك كمان {time_str}", 3
    else: return f"🧘‍♂️ دورك رقم {pos} - السيستم بيدخل {batch} كل {stay} ثانية - سيب الموبايل مفتوح", 5

def find_logo_file():
    for n in ["logo.jpg", "logo.jpeg", "logo.png", "logo.webp"]:
        p = os.path.join(BASE_DIR, n)
        if os.path.exists(p): return p
    return None

def get_logo_tag(size=90, with_margin=True):
    lf = find_logo_file()
    mb = "margin-bottom:12px" if with_margin else ""
    if lf:
        try:
            with open(lf, 'rb') as f:
                data = f.read()
                if len(data) > 100:
                    b64 = base64.b64encode(data).decode('utf-8')
                    return f'<div style="text-align:center;{mb}"><img src="data:image/jpeg;base64,{b64}" style="width:{size}px;height:{size}px;border-radius:18px;object-fit:cover;border:3px solid #fff;display:block;margin:0 auto"></div>'
        except: pass
    return f'<div style="text-align:center;{mb}"><div style="width:{size}px;height:{size}px;background:linear-gradient(135deg,#1a73e8,#0f172a);border-radius:18px;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:{int(size*0.4)}px;font-weight:800">🎓</div></div>'

def get_header_logo_tag():
    return '<div style="width:44px;height:44px;background:linear-gradient(135deg,#60a5fa,#1d4ed8);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff;flex-shrink:0">🎓</div>'

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div>المعهد الصناعي بالمحلة</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div><div style="margin-top:6px;font-size:10px">© حقوق محفوظة لـ م/ محمود منصور 2026</div></div></div>"""

def build_att_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    real_ip = get_real_ip()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>تسجيل الحضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}.header-lines{{text-align:center;line-height:1.7;margin:8px 0 14px 0}}.t1{{font-size:20px;font-weight:800;color:#0f172a}}.t2{{font-size:13px;color:#334155}}.t3{{font-size:13px;color:#334155}}.t4{{font-size:14px;font-weight:800;color:#1a73e8}}input{{width:100%;padding:13px 14px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;font-family:'Tajawal';background:#f8fafc;outline:none}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;font-family:'Tajawal';cursor:pointer}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;font-size:15px;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b}}#ok{{background:#dcfce7;color:#166534}}#exist,#ipblock,#wrong,#black,#deviceblock,#hwblock{{background:#fee2e2;color:#991b1b}}#closed{{background:#fef9c3;color:#854d0e}}</style></head><body><div class="card">{LOGO_TAG}<div class="header-lines"><div class="t1">📝 تسجيل الحضور V2.3 APK</div><div class="t2">الكلية التكنولوجية بالمحلة الكبرى</div><div class="t3">المعهد الصناعي بالمحلة</div><div class="t4">د.م/ محمود منصور</div><div style="font-size:12px;color:#475569;margin-top:6px">IP الحالي: <b id="currentIp">{real_ip}:8080</b></div><div id="studentQr" style="display:flex;justify-content:center;margin:10px auto"></div><button type="button" onclick="location.href='/local-app'" style="margin-bottom:8px;background:#0f766e">📱 دخول كطالب من نفس التطبيق</button></div><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" inputmode="numeric" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي عربي"><input id="nid" type="tel" maxlength="14" inputmode="numeric" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div><div id="exist" class="msgbox">⚠️ الرقم القومي مسجل</div><div id="closed" class="msgbox">⛔ مقفول</div>{SOCIAL_FOOTER}</div><script>
function renderStudentQr(url){{let box=document.getElementById("studentQr");if(!box)return;box.innerHTML="";if(window.QRCode){{new QRCode(box,{{text:url,width:132,height:132}});}}}}
async function refreshStudentIps(){{try{{let r=await fetch("/my_ips");let j=await r.json();let ip=j.primary||"{real_ip}";document.getElementById("currentIp").innerText=ip+":8080";renderStudentQr("http://"+ip+":8080"+location.pathname);}}catch(e){{}}}}
refreshStudentIps();
async function sendData(){{
 let p=document.getElementById('pass').value.trim(),b=document.getElementById('board').value.trim(),n=document.getElementById('name').value.trim(),id=document.getElementById('nid').value.trim();
 if(!p||!b||!n||!id){{let m=document.getElementById('msgBox');m.innerText='اكمل البيانات';m.style.display='block';return;}}
 try{{
  let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n,nid:id,board:b,pass:p}})}});
  if(r.status==200){{document.getElementById('ok').style.display='block';let d=await r.json();if(d.redirect)location.href=d.redirect;}}
  else {{document.getElementById('exist').style.display='block';}}
 }}catch(e){{alert('مش متصل');}}
}}
</script></body></html>"""

def build_admin_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    HEADER_LOGO = get_header_logo_tag()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة تحكم APK</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:#f5f7fb;padding:12px}} .container{{max-width:1100px;margin:auto}} .card{{background:#fff;border-radius:18px;padding:16px;margin-bottom:14px}} input{{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:12px;margin:4px 0}} .btn{{padding:12px 16px;border:none;border-radius:12px;font-weight:800;cursor:pointer}} .btn-primary{{background:#1a73e8;color:#fff}}</style></head><body><div class="container"><div class="card"><h2>لوحة تحكم الأستاذ الدكتور</h2><input id="lecturePass" placeholder="كلمة سر المحاضرة"><input id="minutes" type="number" value="30"><button onclick="openNow()" class="btn btn-primary" style="margin-top:10px">افتح المحاضرة</button></div></div><script>
async function openNow(){{let lp=document.getElementById('lecturePass').value;let mins=parseInt(document.getElementById('minutes').value);let u=Date.now()+mins*60*1000;await fetch('/set_config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:u.toString(),lecturePass:lp}})}});alert('تم فتح المحاضرة بنجاح');}}
</script></body></html>"""

def ensure_files():
    cfg = load_cfg()
    save_cfg(cfg)
    if not os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f: f.write("[]")
        except: pass

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): return
    def do_POST(self):
        client_ip = self.client_address[0]
        cfg = load_cfg()
        if self.path == '/set_config':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            cfg["lecturePass"] = data.get('lecturePass', '')
            cfg["open"] = data.get('open', '0')
            save_cfg(cfg)
            self.send_response(200); self.end_headers(); return
        if self.path == '/save':
            try:
                length = int(self.headers.get('content-length', 0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                nid = normalize_nid(data.get('nid', ''))
                if not valid_national_id(nid):
                    self.send_response(422); self.end_headers(); return
                all_data = []
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, 'r', encoding='utf-8') as f:
                        try: all_data = json.load(f)
                        except: all_data = []
                if any(x.get('nid') == nid for x in all_data):
                    self.send_response(409); self.end_headers(); return
                
                rec = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "name": data.get('name', ''), "nid": nid, "board": data.get('board', ''), "ip": client_ip}
                all_data.append(rec)
                with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(all_data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "redirect": "/done"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500); self.end_headers()
            return
        self.send_response(404); self.end_headers()

    def do_GET(self):
        low = self.path.lower()
        if low == '/health':
            self.send_response(200); self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if low == '/my_ips':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ips": get_local_ips(), "primary": get_real_ip()}).encode('utf-8'))
            return
        if low == '/admin':
            self.send_response(200); self.end_headers()
            self.wfile.write(build_admin_html().encode('utf-8'))
            return
        if low == '/done':
            self.send_response(200); self.end_headers()
            self.wfile.write(b'<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><title>تم</title></head><body style="text-align:center;font-family:Tahoma;padding:50px"><h1 style="color:green">✅ تم تسجيل حضورك بنجاح</h1></body></html>')
            return
        self.send_response(200); self.end_headers()
        self.wfile.write(build_att_html().encode('utf-8'))

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

def run_server():
    ensure_files()
    try:
        with ThreadingHTTPServer(('0.0.0.0', 8080), http.server.SimpleHTTPRequestHandler if False else Handler) as httpd:
            httpd.serve_forever()
    except Exception as exc:
        print("Server error:", exc)

class MainApp(App):
    def build(self):
        try:
            configure_storage(self)
            ensure_files()
        except:
            pass
        
        # تشغيل السيرفر المحلي في خلفية التطبيق بأمان تام
        try:
            threading.Thread(target=run_server, daemon=True).start()
        except:
            pass

        root = BoxLayout(orientation='vertical')
        
        # واجهة أساسية داخل التطبيق تعرض الأزرار والروابط لمنع أي تعطل
        lbl = Label(
            text=ar("أهلاً بك في نظام الحضور الذكي\n\nيعمل السيرفر المحلي الآن في الخلفية\nيمكنك فتح لوحة التحكم أو صفحة التسجيل عبر المتصفح"),
            halign='center',
            valign='middle'
        )
        if DEFAULT_FONT_NAME:
            lbl.font_name = DEFAULT_FONT_NAME
        lbl.bind(size=lbl.setter('text_size'))
        root.add_widget(lbl)
        
        btn_box = BoxLayout(size_hint_y=0.2, spacing=10, padding=10)
        b1 = Button(text=ar("فتح لوحة التحكم"), background_color=(0.1, 0.45, 0.91, 1))
        b2 = Button(text=ar("فتح صفحة الحضور"), background_color=(0.08, 0.64, 0.29, 1))
        if DEFAULT_FONT_NAME:
            b1.font_name = DEFAULT_FONT_NAME
            b2.font_name = DEFAULT_FONT_NAME
            
        b1.bind(on_press=lambda x: webbrowser.open(f'http://{get_real_ip()}:8080/admin'))
        b2.bind(on_press=lambda x: webbrowser.open(f'http://{get_real_ip()}:8080/'))
        
        btn_box.add_widget(b1)
        btn_box.add_widget(btn_box.add_widget(b2) if False else b2)
        root.add_widget(btn_box)
        
        return root

if __name__ == '__main__':
    MainApp().run()
