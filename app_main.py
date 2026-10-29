from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.switch import Switch
from kivy.uix.scrollview import ScrollView
from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle, Rectangle
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
DEFAULT_CFG = {"lecturePass": "", "open": "0", "s": "", "max_active": 32, "stay_seconds": 2.0, "ip_check": False, "nid_check": True, "device_check": True, "hw_check": False, "android_check": True, "black_nids": [], "black_ips": [], "white_ips": [], "after_msg": "✅ تم التسجيل في موبايل الدكتور", "done_msg": "✅ تم تسجيل حضورك - توجه لمعمل 3 عند م/ احمد", "batch": 5, "adminPass": DEFAULT_ADMIN_PASS, "local_app_enabled": True}
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
                out = subprocess.check_output(cmd, shell=True, timeout=2, stderr=subprocess.STDOUT).decode('utf-8','ignore')
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

def get_wait_msg(pos, max_a, stay, batch):
    est_sec = (pos / batch) * stay + 5
    m = int(est_sec // 60); s = int(est_sec % 60)
    time_str = f"{m} دقيقة {s} ثانية" if m>0 else f"{s} ثانية"
    if pos <= 10: return f"⏳ فاضل قدامك {pos} بس - خليك فاتح الصفحة هتدخل لوحدك كمان {time_str}", 3
    else: return f"🧘‍♂️ دورك رقم {pos} - السيستم بيدخل {batch} كل {stay} ثانية", 5

def find_logo_file():
    for n in ["logo.jpg","logo.jpeg","logo.png","logo.webp","logo.JPG","logo.PNG","LOGO.jpg","LOGO.png"]:
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
                    return f'<div style="text-align:center;{mb}"><img src="data:{mime};base64,{b64}" style="width:{size}px;height:{size}px;border-radius:18px;object-fit:cover;border:3px solid #fff;display:block;margin:0 auto"></div>'
        except: pass
    return f'<div style="text-align:center;{mb}"><div style="width:{size}px;height:{size}px;background:linear-gradient(135deg,#1a73e8,#0f172a);border-radius:18px;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:{int(size*0.4)}px;font-weight:800">🎓</div></div>'

def get_header_logo_tag():
    return '<div style="width:44px;height:44px;background:linear-gradient(135deg,#60a5fa,#1d4ed8);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff;flex-shrink:0">🎓</div>'

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div><div style="margin-top:6px;font-size:10px">© حقوق محفوظة 2026</div></div></div>"""

def build_att_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    real_ip = get_real_ip()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الحضور</title><style>body{{font-family:Tahoma,sans-serif;background:#f0f9ff;padding:12px;display:flex;flex-direction:column;align-items:center}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(0,0,0,.1);width:100%}}input{{width:100%;padding:13px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px}}button{{width:100%;padding:14px;background:#1a73e8;color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:bold;cursor:pointer}}</style></head><body><div class="card">{LOGO_TAG}<h2 style="text-align:center">تسجيل الحضور</h2><input id="pass" placeholder="كلمة سر المحاضرة" type="password"><input id="board" type="number" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي"><input id="nid" type="tel" maxlength="14" placeholder="الرقم القومي (14 رقم)"><button onclick="sendData()">ارسال الحضور</button><div id="msg" style="text-align:center;margin-top:10px;color:red;font-weight:bold;"></div></div><script>
async function sendData(){{
  let p=document.getElementById('pass').value, b=document.getElementById('board').value, n=document.getElementById('name').value, id=document.getElementById('nid').value;
  let r=await fetch('/save', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{pass:p, board:b, name:n, nid:id, deviceId:'app_dev', hwId:'app_hw', androidId:''}})}});
  if(r.status==200) alert('تم الحضور بنجاح!'); else alert('حدث خطأ في التسجيل');
}}
</script></body></html>"""

def build_admin_html():
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>لوحة التحكم</title></head><body style="font-family:Tahoma;padding:20px;"><h2>لوحة تحكم الأستاذ</h2><p>مرحباً بك، النظام يعمل بانتظام.</p></body></html>"""

def ensure_files():
    try:
        cfg = load_cfg()
        save_cfg(cfg)
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE,"w",encoding="utf-8") as f: f.write("[]")
    except Exception:
        pass

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        try:
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            all_data = []
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    try: all_data = json.load(f)
                    except: all_data = []
            all_data.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "name": data.get('name',''), "nid": data.get('nid',''), "board": data.get('board','')})
            with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(all_data, f, ensure_ascii=False, indent=2)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.lower()
        if path == '/health' or path == '/time':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "server": int(datetime.now().timestamp()*1000)}).encode('utf-8'))
            return
        if 'admin' in path:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(build_admin_html().encode('utf-8'))
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(build_att_html().encode('utf-8'))

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

def run_server():
    try:
        ensure_files()
        with ThreadingHTTPServer(('0.0.0.0', 8080), Handler) as httpd:
            httpd.serve_forever()
    except Exception as exc:
        print("Server error:", exc)

class MainApp(App):
    def build(self):
        configure_storage(self)
        ensure_files()
        # تشغيل السيرفر في خلفية آمنة لا تتسبب بكراش واجهة المستخدم
        threading.Thread(target=run_server, daemon=True).start()
        
        root = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        lbl = Label(
            text=ar("أهلاً بك في نظام حضور الكلية التكنولوجية\nالتطبيق يعمل بكفاءة وجاهز لاستقبال الطلبة"),
            halign='center',
            valign='middle',
            font_size='18sp'
        )
        if DEFAULT_FONT_NAME:
            lbl.font_name = DEFAULT_FONT_NAME
        lbl.bind(size=lbl.setter('text_size'))
        root.add_widget(lbl)
        
        btn_admin = StyledButton(text=ar("فتح لوحة التحكم الرئيسية"), bg_color=(0.1, 0.45, 0.91, 1), size_hint_y=None, height=55)
        btn_admin.bind(on_press=lambda x: webbrowser.open(f'http://127.0.0.1:8080/admin'))
        root.add_widget(btn_admin)
        
        return root

if __name__ == '__main__':
    MainApp().run()
