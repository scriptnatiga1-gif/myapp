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
import sys, traceback, runpy

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

class CardLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[18])
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

class StyledButton(Button):
    def __init__(self, bg_color=(0.1, 0.45, 0.91, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.custom_bg = bg_color
        if DEFAULT_FONT_NAME:
            self.font_name = DEFAULT_FONT_NAME
        self.font_size = '16sp'
        self.bold = True
        with self.canvas.before:
            Color(*self.custom_bg)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[14])
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

class StyledTextInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if DEFAULT_FONT_NAME:
            self.font_name = DEFAULT_FONT_NAME
        self.padding = [12, 12, 12, 12]
        self.background_normal = ''
        self.background_active = ''
        self.background_color = (0.97, 0.98, 0.99, 1)
        self.cursor_color = (0.1, 0.45, 0.91, 1)
        self.hint_text_color = (0.5, 0.5, 0.5, 1)
        self.foreground_color = (0.05, 0.09, 0.16, 1)

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
            print("Wake lock unavailable:", e)

    def _refresh_home(self, *_):
        try:
            ips = get_local_ips()
            primary = get_real_ip()
            txt = f"APK الحضور - AutoDetect\nIP الحالي: {primary}:8080\nكل العناوين: {', '.join(ips[:6])}\nSerial: {ANDROID_SERIAL[:10]}\nالرابط الثابت: http://127.0.0.1:8080/go"
            self.ip_label.text = ar(txt)
        except Exception:
            pass

    def _show_home(self, *_):
        self.root.clear_widgets()
        main_box = BoxLayout(orientation='vertical', padding=16, spacing=14)
        card = CardLayout(orientation='vertical', padding=16, spacing=10, size_hint_y=0.45)
        
        self.ip_label = Label(
            text=ar("جارٍ كشف IP ..."),
            color=(0.06, 0.09, 0.16, 1),
            halign='center',
            valign='middle',
            font_size='15sp',
            line_height=1.3
        )
        if DEFAULT_FONT_NAME:
            self.ip_label.font_name = DEFAULT_FONT_NAME
        self.ip_label.bind(size=self.ip_label.setter('text_size'))
        card.add_widget(self.ip_label)

        btn1 = StyledButton(text=ar("📱 تسجيل حضور الطالب داخل التطبيق"), bg_color=(0.1, 0.45, 0.91, 1), size_hint_y=0.18)
        btn2 = StyledButton(text=ar("🔐 فتح لوحة تحكم الدكتور"), bg_color=(0.06, 0.09, 0.16, 1), size_hint_y=0.18)
        btn3 = StyledButton(text=ar("🌐 فتح صفحة QR والتقارير"), bg_color=(0.06, 0.46, 0.43, 1), size_hint_y=0.18)

        btn1.bind(on_press=self._show_student)
        btn2.bind(on_press=lambda x: webbrowser.open(f'http://{get_real_ip()}:8080/admin'))
        btn3.bind(on_press=lambda x: webbrowser.open(f'http://{get_real_ip()}:8080/'))

        main_box.add_widget(card)
        main_box.add_widget(btn1)
        main_box.add_widget(btn2)
        main_box.add_widget(btn3)
        
        self.root.add_widget(main_box)
        self._refresh_home()

    def _show_student(self, *_):
        root = BoxLayout(orientation='vertical', padding=14, spacing=8)
        
        lbl_header = Label(text=ar("تسجيل الحضور من داخل التطبيق"), size_hint_y=None, height=42, font_size='18sp', bold=True)
        if DEFAULT_FONT_NAME:
            lbl_header.font_name = DEFAULT_FONT_NAME
        root.add_widget(lbl_header)

        self.server_url = StyledTextInput(text=getattr(self, "last_server_url", f"http://{get_real_ip()}:8080"), hint_text=ar("عنوان الدكتور مثل http://192.168.43.1:8080"), multiline=False, size_hint_y=None, height=48)
        self.student_pass = StyledTextInput(hint_text=ar("كلمة سر المحاضرة"), password=True, multiline=False, size_hint_y=None, height=48)
        self.student_board = StyledTextInput(hint_text=ar("رقم السبورة"), multiline=False, input_filter='int', size_hint_y=None, height=48)
        self.student_name = StyledTextInput(hint_text=ar("الاسم رباعي عربي"), multiline=False, size_hint_y=None, height=48)
        self.student_nid = StyledTextInput(hint_text=ar("الرقم القومي 14 رقم"), multiline=False, input_filter='int', size_hint_y=None, height=48)
        
        self.student_msg = Label(text=ar("اتصل بشبكة الدكتور ثم امسح QR أو استخدم الكشف التلقائي."), size_hint_y=0.22, halign='center', valign='middle')
        if DEFAULT_FONT_NAME:
            self.student_msg.font_name = DEFAULT_FONT_NAME
        self.student_msg.bind(size=self.student_msg.setter('text_size'))

        actions = BoxLayout(size_hint_y=None, height=48, spacing=8)
        scan = StyledButton(text=ar("📷 مسح QR"), bg_color=(0.1, 0.45, 0.91, 1))
        discover = StyledButton(text=ar("🔎 اتصال تلقائي"), bg_color=(0.06, 0.46, 0.43, 1))
        scan.bind(on_press=self._scan_qr)
        discover.bind(on_press=self._discover_server)
        actions.add_widget(scan); actions.add_widget(discover)

        send = StyledButton(text=ar("إرسال الحضور"), bg_color=(0.08, 0.64, 0.29, 1), size_hint_y=None, height=52)
        back = StyledButton(text=ar("رجوع"), bg_color=(0.86, 0.15, 0.15, 1), size_hint_y=None, height=44)
        
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
            self.student_msg.text = ar("وجّه الكاميرا إلى QR الخاص بالدكتور.")
        except Exception:
            self.student_msg.text = ar("لم يتم العثور على قارئ QR متوافق. استخدم الاتصال التلقائي أو اكتب عنوان الدكتور يدويًا.")

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
                self.student_msg.text = ar("تم قراءة QR. اضغط إرسال الحضور بعد استكمال البيانات.")
            else:
                self.student_msg.text = ar("QR لا يحتوي على عنوان خادم صالح.")
        except Exception as exc:
            self.student_msg.text = ar("تعذر قراءة نتيجة QR: ") + str(exc)

    def _discover_server(self, *_):
        self.student_msg.text = ar("جارٍ البحث عن محاضرة مفتوحة على الشبكة المحلية...")
        def worker():
            import urllib.request, urllib.error, concurrent.futures, ipaddress
            found = None
            own_ip = get_real_ip()
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
                    self.student_msg.text = ar("✅ تم العثور على محاضرة مفتوحة: ") + found
                else:
                    self.student_msg.text = ar("لم نعثر على محاضرة مفتوحة. تأكد أن الجهازين على الشبكة نفسها وأن الدكتور فتح المحاضرة، ثم امسح QR أو اكتب IP الدكتور.")
            Clock.schedule_once(done, 0)
        threading.Thread(target=worker, daemon=True).start()

    def _submit_native_attendance(self, *_):
        import urllib.request, urllib.error
        server = self._set_server_url(self.server_url.text if hasattr(self, "server_url") else "")
        if not server:
            self.student_msg.text = ar("امسح QR أو اضغط اتصال تلقائي لتحديد هاتف الدكتور أولًا.")
            return
        nid = normalize_nid(self.student_nid.text)
        if not self.student_pass.text.strip() or not self.student_board.text.strip() or not self.student_name.text.strip() or not nid:
            self.student_msg.text = ar("من فضلك أكمل كل البيانات.")
            return
        if not valid_national_id(nid):
            self.student_msg.text = ar("الرقم القومي غير صحيح. راجع 14 رقمًا وتاريخ الميلاد والمحافظة.")
            return
        self.student_msg.text = ar("جارٍ إرسال الحضور إلى هاتف الدكتور...")
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
                message = ar("✅ تم تسجيل الحضور بنجاح") if result.get("ok") else ar("لم يتم التسجيل.")
            except urllib.error.HTTPError as e:
                messages = {401:"كلمة سر المحاضرة غير صحيحة.",403:"المحاضرة مغلقة أو الرقم محظور.",409:"الرقم القومي مسجل بالفعل.",410:"هذا IP مسجل بالفعل.",411:"هذا الجهاز سجل بالفعل.",412:"بصمة الجهاز مسجلة.",413:"معرّف Android مسجل بالفعل.",422:"الرقم القومي غير صحيح.",429:"الطابور ممتلئ، حاول مرة أخرى."}
                message = ar("❌ ") + ar(messages.get(e.code, f"تعذر التسجيل (HTTP {e.code})."))
            except Exception as e:
                message = ar("❌ تعذر الاتصال بخادم الدكتور: ") + str(e)
            Clock.schedule_once(lambda dt: setattr(self.student_msg,'text',message),0)
        threading.Thread(target=worker,daemon=True).start()

    def build(self):
        try:
            configure_storage(self)
            ensure_files()
            threading.Thread(target=run_server, daemon=True).start()
            self._acquire_wake_lock()
            self.root = BoxLayout(orientation='vertical')
            self._show_home()
            Clock.schedule_interval(self._refresh_home, 1)
            return self.root
        except Exception:
            import traceback
            details = traceback.format_exc()
            panel = BoxLayout(orientation='vertical', padding=12, spacing=8)
            panel.add_widget(Label(text='خطأ في بدء التطبيق', size_hint_y=None, height='50dp'))
            scroll = ScrollView()
            msg = Label(text=details, size_hint_y=None, halign='left', valign='top')
            msg.bind(width=lambda inst, width: setattr(inst, 'text_size', (width, None)))
            msg.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1] + 20))
            scroll.add_widget(msg)
            panel.add_widget(scroll)
            return panel

    def on_stop(self):
        try:
            if getattr(self, "_wake_lock", None) and self._wake_lock.isHeld():
                self._wake_lock.release()
        except Exception:
            pass

if __name__ == '__main__':
    MainApp().run()
