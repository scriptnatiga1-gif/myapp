from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
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

def configure_storage(app=None):
    global DATA_DIR, DATA_FILE, CONFIG_FILE
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
    return "192.168.43.1"

def get_local_ips():
    ips = [get_real_ip()]
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
        except: pass
    return f'<div style="text-align:center;{mb}"><div style="width:{size}px;height:{size}px;background:linear-gradient(135deg,#1a73e8,#0f172a);border-radius:18px;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:{int(size*0.4)}px;font-weight:800">🎓</div></div>'

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div>المعهد الصناعي بالمحلة</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div><div style="margin-top:6px;font-size:10px">© حقوق محفوظة لـ م/ محمود منصور 2026</div></div></div>"""

def build_att_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    real_ip = get_real_ip()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تسجيل الحضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}input{{width:100%;padding:13px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;background:#f8fafc;outline:none}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;cursor:pointer}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b}}#ok{{background:#dcfce7;color:#166534}}</style></head><body><div class="card">{LOGO_TAG}<div style="text-align:center"><h3>تسجيل الحضور V2.3</h3><p>د.م/ محمود منصور</p></div><input id="pass" placeholder="كلمة سر المحاضرة" type="password"><input id="board" placeholder="رقم السبورة" type="number"><input id="name" placeholder="الاسم رباعي"><input id="nid" placeholder="الرقم القومي (14 رقم)" maxlength="14"><button onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div>{SOCIAL_FOOTER}</div><script>
async function sendData(){{let p=document.getElementById('pass').value,b=document.getElementById('board').value,n=document.getElementById('name').value,id=document.getElementById('nid').value;let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pass:p,board:b,name:n,nid:id})});if(r.status==200)document.getElementById('ok').style.display='block';else alert('خطأ في البيانات أو المحاضرة مغلقة');}}
</script></body></html>"""

def ensure_files():
    try:
        cfg = load_cfg()
        save_cfg(cfg)
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE,"w",encoding="utf-8") as f: f.write("[]")
    except: pass

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): return
    def do_POST(self):
        try:
            if self.path == '/save':
                length = int(self.headers.get('content-length',0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                nid = normalize_nid(data.get('nid',''))
                if not valid_national_id(nid):
                    self.send_response(422); self.end_headers(); return
                all_data = []
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE,'r',encoding='utf-8') as f:
                        try: all_data = json.load(f)
                        except: all_data = []
                all_data.append({"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"name":data.get('name',''),"nid":nid,"board":data.get('board','')})
                with open(DATA_FILE,'w',encoding='utf-8') as f: json.dump(all_data,f,ensure_ascii=False,indent=2)
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"ok":True}).encode('utf-8'))
            else:
                self.send_response(404); self.end_headers()
        except:
            self.send_response(500); self.end_headers()

    def do_GET(self):
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
    except: pass

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
        
        title = Label(text=ar("🎓 نظام الحضور الذكي - الكلية التكنولوجية"), font_size='20sp', bold=True, size_hint_y=None, height=60)
        self.apply_arabic_font(title)
        box.add_widget(title)

        sub = Label(text=ar("اختر نوع الدخول للبدء:"), font_size='16sp', size_hint_y=None, height=40)
        self.apply_arabic_font(sub)
        box.add_widget(sub)

        btn_student = Button(text=ar("👨‍🎓 دخول طالب (تسجيل الحضور)"), background_color=(0.1, 0.45, 0.91, 1), size_hint_y=None, height=60, bold=True)
        self.apply_arabic_font(btn_student)
        btn_student.bind(on_press=lambda x: self.show_student_screen())
        box.add_widget(btn_student)

        btn_admin = Button(text=ar("🔐 دخول أدمن (لوحة التحكم والإعدادات)"), background_color=(0.06, 0.09, 0.16, 1), size_hint_y=None, height=60, bold=True)
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
            self.s_msg.text = ar("❌ الرقم القومي غير صحيح (14 رقمًا)")
            return
        try:
            payload = {"name": self.s_name.text.strip(), "nid": nid, "board": self.s_board.text.strip(), "pass": self.s_pass.text.strip()}
            req = urllib.request.Request(server + '/save', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.s_msg.text = ar("✅ تم تسجيل الحضور بنجاح!")
        except Exception:
            self.s_msg.text = ar("❌ تعذر الاتصال بالسيرفر المحلي")

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
        lbl = Label(text=ar("⚙️ إعدادات التطبيق واختيار اللغة\n📌 رقم الإصدار: V2.3 Pro (2026)"), size_hint_y=None, height=80)
        self.apply_arabic_font(lbl)
        content.add_widget(lbl)
        btn_close = Button(text=ar("إغلاق"), size_hint_y=None, height=45)
        self.apply_arabic_font(btn_close)
        popup = Popup(title=ar("الإعدادات"), content=content, size_hint=(0.8, 0.4))
        btn_close.bind(on_press=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

    def show_contact_popup(self):
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        lbl = Label(text=ar("📞 الكلية التكنولوجية بالمحلة الكبرى\nالمعهد الصناعي بالمحلة\nتطوير: د.م/ محمود منصور"), size_hint_y=None, height=100)
        self.apply_arabic_font(lbl)
        content.add_widget(lbl)
        btn_close = Button(text=ar("إغلاق"), size_hint_y=None, height=45)
        self.apply_arabic_font(btn_close)
        popup = Popup(title=ar("اتصل بنا"), content=content, size_hint=(0.85, 0.5))
        btn_close.bind(on_press=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

if __name__ == '__main__':
    MainApp().run()
