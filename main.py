from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line
from kivy.core.text import LabelBase
import http.server, json, os, threading, base64, socket, re, subprocess, io, webbrowser
from datetime import datetime
from collections import OrderedDict
import urllib.parse, mimetypes, socketserver

# --- 1. معالج اللغة العربية المتكامل (حل جذري للحروف المنفصلة والمربعات والرموز) ---
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_LIBS = True
except ImportError:
    HAS_ARABIC_LIBS = False

ARABIC_FORMS = {
    'ء': ('ﺀ', 'ﺀ', 'ﺀ', 'ﺀ'), 'آ': ('ﺁ', 'ﺂ', 'ﺁ', 'ﺂ'), 'أ': ('ﺃ', 'ﺄ', 'ﺃ', 'ﺄ'),
    'ؤ': ('ﺅ', 'ﺆ', 'ﺅ', 'ﺆ'), 'إ': ('ﺇ', 'ﺈ', 'ﺇ', 'ﺈ'), 'ئ': ('ﺉ', 'ﺌ', 'ﺋ', 'ﺊ'),
    'ا': ('ﺍ', 'ﺎ', 'ﺍ', 'ﺎ'), 'ب': ('ﺏ', 'ﺐ', 'ﺑ', 'ﺒ'), 'ة': ('ﺓ', 'ﺔ', 'ﺓ', 'ﺔ'),
    'ت': ('ﺕ', 'ﺖ', 'ﺗ', 'ﺘ'), 'ث': ('ﺙ', 'ﺚ', 'ﺛ', 'ﺜ'), 'ج': ('ﺝ', 'ﺞ', 'ﺟ', 'ﺠ'),
    'ح': ('ﺡ', 'ﺢ', 'ﺣ', 'ﺤ'), 'خ': ('ﺥ', 'ﺦ', 'ﺧ', 'ﺨ'), 'د': ('ﺩ', 'ﺪ', 'ﺩ', 'ﺪ'),
    'ذ': ('ﺫ', 'ﺬ', 'ﺫ', 'ﺬ'), 'ر': ('ﺭ', 'ﺮ', 'ﺭ', 'ﺮ'), 'ز': ('ﺯ', 'ﺰ', 'ﺯ', 'ﺰ'),
    'س': ('ﺱ', 'ﺲ', 'ﺳ', 'ﺴ'), 'ش': ('ﺵ', 'ﺶ', 'ﺷ', 'ﺸ'), 'ص': ('ﺹ', 'ﺺ', 'ﺻ', 'ﺼ'),
    'ض': ('ﺽ', 'ﺾ', 'ﺿ', 'ﻀ'), 'ط': ('ﻁ', 'ﻂ', 'ﻃ', 'ﻄ'), 'ظ': ('ﻅ', 'ﻆ', 'ﻇ', 'ﻈ'),
    'ع': ('ﻉ', 'ﻊ', 'ﻋ', 'ﻌ'), 'غ': ('ﻍ', 'ﻐ', 'ﻏ', 'ﻐ'), 'ف': ('ﻑ', 'ﻒ', 'ﻓ', 'ﻔ'),
    'ق': ('ﻕ', 'ﻖ', 'ﻗ', 'ﻘ'), 'ك': ('ﻙ', 'ﻚ', 'ﻛ', 'ﻜ'), 'ل': ('ﻝ', 'ﻞ', 'ﻟ', 'ﻠ'),
    'م': ('ﻡ', 'ﻢ', 'ﻣ', 'ﻤ'), 'ن': ('ﻥ', 'ﻦ', 'ﻧ', 'ﻨ'), 'ه': ('ﻩ', 'ﻪ', 'ﻫ', 'ﻬ'),
    'و': ('ﻭ', 'ﻮ', 'ﻭ', 'ﻮ'), 'ى': ('ﻯ', 'ﻰ', 'ﻯ', 'ﻰ'), 'ي': ('ﻱ', 'ﻲ', 'ﻳ', 'ﻴ'),
}
NON_CONNECTING_NEXT = {'ء', 'آ', 'أ', 'ؤ', 'إ', 'ا', 'د', 'ذ', 'ر', 'ز', 'و', 'ى', 'ة'}

def fallback_reshape_and_bidi(text):
    res = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch in ARABIC_FORMS:
            prev_ch = text[i - 1] if i > 0 else ''
            next_ch = text[i + 1] if i < n - 1 else ''
            conn_prev = (prev_ch in ARABIC_FORMS) and (prev_ch not in NON_CONNECTING_NEXT)
            conn_next = (next_ch in ARABIC_FORMS) and (ch not in NON_CONNECTING_NEXT)
            forms = ARABIC_FORMS[ch]
            if conn_prev and conn_next:
                res.append(forms[3])
            elif conn_prev:
                res.append(forms[1])
            elif conn_next:
                res.append(forms[2])
            else:
                res.append(forms[0])
        else:
            res.append(ch)
    reshaped_str = "".join(res)
    tokens = re.findall(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]+|[^\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]+', reshaped_str)
    has_ar = any(re.search(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]', t) for t in tokens)
    if not has_ar:
        return text
    out = []
    for t in reversed(tokens):
        if re.search(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]', t):
            out.append(t[::-1])
        else:
            out.append(t)
    return "".join(out)

def sanitize_for_kivy_font(text):
    # الخطوط العربية في أندرويد لا تحتوي على حروف إنجليزية أو رموز الخاصة بـ ASCII مما يسبب ظهور مربعات ▯▯
    # لذلك نُبقي فقط الحروف العربية والأرقام وعلامات الترقيم الأساسية ونحذف أو نستبدل الحروف اللاتينية في واجهة Kivy
    s = str(text)
    s = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27BF]', '', s)
    # استبدال الكلمات الإنجليزية الشائعة في الواجهة بمقابلها العربي أو إزالة الحروف اللاتينية غير المدعومة في الخط العربي
    replacements = {
        "GitHub": "جيت هاب",
        "Facebook": "فيسبوك",
        "LinkedIn": "لينكد إن",
        "Instagram": "انستجرام",
        "Termux": "تيرمكس",
        "Online": "متصل",
        "QR": "كيو آر",
        "IP": "آي بي",
        "http://": "",
        "https://": "",
        "Pro": "برو",
        "V2.5.0": "2.5.0",
        "English": "انجليزي",
        "X": "إكس",
        "->": ":",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    # إزالة أي أحرف لاتينية متبقية حتى لا تظهر كمربعات في خط NotoNaskhArabic
    s = re.sub(r'[A-Za-z]+', '', s)
    # تنظيف الرموز غير المدعومة مثل الشرطات المائلة والأقواس المربعة
    s = s.replace('[', '(').replace(']', ')').replace('/', ' - ').replace('(', '').replace(')', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def ar(text, lang="ar"):
    if not text:
        return ""
    if lang == "en":
        return re.sub(r'[\u0600-\u06FF]+', '', str(text)).strip()
    clean = sanitize_for_kivy_font(text)
    if not clean:
        return ""
    if HAS_ARABIC_LIBS:
        try:
            reshaped = arabic_reshaper.reshape(clean)
            return get_display(reshaped)
        except Exception:
            return fallback_reshape_and_bidi(clean)
    return fallback_reshape_and_bidi(clean)

# تحميل الخط العربي الأفضل
SYSTEM_ARABIC_FONT = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    os.path.join(BASE_DIR, "Amiri-Regular.ttf"),
    os.path.join(BASE_DIR, "tajawal.ttf"),
    "/system/fonts/NotoSansArabic-Regular.ttf",
    "/system/fonts/NotoNaskhArabic-Regular.ttf",
    "/system/fonts/DroidSansArabic.ttf",
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

# --- 2. إعدادات السيرفر والبيانات ---
def get_android_id():
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        Secure = autoclass('android.provider.Settings$Secure')
        return Secure.getString(activity.getContentResolver(), Secure.ANDROID_ID)
    except Exception:
        return f"dev-{os.urandom(3).hex()}"

ANDROID_SERIAL = get_android_id()
SECRET = "Mn2026_Secret_@#_KEY"
APP_VERSION = "V2.5.0 Pro"

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
    os.makedirs(target, exist_ok=True)
    for name in ("attendance.json", "config.json", "latest_link.txt"):
        old_path = os.path.join(BASE_DIR, name)
        new_path = os.path.join(target, name)
        if os.path.abspath(old_path) != os.path.abspath(new_path) and os.path.isfile(old_path) and not os.path.exists(new_path):
            try:
                import shutil
                shutil.copy2(old_path, new_path)
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
recent_connections = []

def log_connection_event(ip, status, detail=""):
    now_str = datetime.now().strftime("%H:%M:%S")
    recent_connections.insert(0, {"time": now_str, "ip": ip, "status": status, "detail": detail})
    if len(recent_connections) > 50:
        recent_connections.pop()

def get_real_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip.startswith("127."):
            return "192.168.43.1"
        return ip
    except Exception:
        return "192.168.43.1"

def get_interface_ips():
    ips = []
    try:
        out = ""
        for cmd in ["ip addr show", "ip -4 addr", "ifconfig"]:
            try:
                out = subprocess.check_output(cmd, shell=True, timeout=2, stderr=subprocess.STDOUT).decode('utf-8', 'ignore')
                if "inet " in out:
                    break
            except Exception:
                continue
        found = re.findall(r'inet\s+(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)', out)
        for ip in found:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips

def get_primary_ip():
    real = get_real_ip()
    if real and not real.startswith("127."):
        return real
    return "192.168.43.1"

def get_local_ips():
    ips = []
    seen = set()
    for ip in get_interface_ips():
        if ip not in seen:
            ips.append(ip); seen.add(ip)
    primary = get_primary_ip()
    if primary and primary not in seen:
        ips.append(primary); seen.add(primary)
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in seen:
                ips.append(ip); seen.add(ip)
    except Exception:
        pass
    def sort_key(ip):
        if ip == primary: return (0, ip)
        if ip.startswith("192.168.0.") or ip.startswith("192.168.1."): return (1, ip)
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
                if k not in d:
                    d[k] = v
            return d
    except Exception:
        return DEFAULT_CFG.copy()

def save_cfg(c):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=2)

def free_ip(ip):
    if ip in active_ips: del active_ips[ip]
    if ip in waiting_queue: del waiting_queue[ip]

def get_wait_msg(pos, max_a, stay, batch):
    est_sec = (pos / batch) * stay + 5
    m = int(est_sec // 60); s = int(est_sec % 60)
    time_str = f"{m} دقيقة {s} ثانية" if m > 0 else f"{s} ثانية"
    if pos <= 10:
        return f"⏳ فاضل قدامك {pos} بس - خليك فاتح الصفحة هتدخل لوحدك كمان {time_str}", 3
    elif pos <= 50:
        return f"🧘‍♂️ دورك رقم {pos} - السيستم بيدخل {batch} كل {stay} ثانية - متوقع {time_str}", 5
    else:
        return f"😅 انت رقم {pos} - الوقت المتوقع حوالي {time_str} - سيب الصفحة مفتوحة", 8

def find_logo_file():
    for n in ["logo.jpg", "logo.jpeg", "logo.png", "icon.png", "logo.webp"]:
        p = os.path.join(BASE_DIR, n)
        if os.path.exists(p):
            return p
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
                    mime, _ = mimetypes.guess_type(lf)
                    if not mime:
                        mime = 'image/jpeg'
                    return f'<div style="text-align:center;{mb}"><img src="data:{mime};base64,{b64}" style="width:{size}px;height:{size}px;border-radius:18px;object-fit:cover;box-shadow:0 6px 18px rgba(0,0,0,.2);border:3px solid #fff;display:block;margin:0 auto"></div>'
        except Exception:
            pass
    return f'<div style="text-align:center;{mb}"><div style="width:{size}px;height:{size}px;background:linear-gradient(135deg,#1a73e8,#0f172a);border-radius:18px;margin:0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:{int(size*0.4)}px;font-weight:800">🎓</div></div>'

def get_header_logo_tag():
    lf = find_logo_file()
    if lf:
        try:
            with open(lf, 'rb') as f:
                data = f.read()
                if len(data) > 100:
                    b64 = base64.b64encode(data).decode('utf-8')
                    mime, _ = mimetypes.guess_type(lf)
                    if not mime:
                        mime = 'image/jpeg'
                    return f'<img src="data:{mime};base64,{b64}" style="width:44px;height:44px;border-radius:12px;object-fit:cover;border:2px solid #fff;display:block;flex-shrink:0">'
        except Exception:
            pass
    return '<div style="width:44px;height:44px;background:linear-gradient(135deg,#60a5fa,#1d4ed8);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff;flex-shrink:0">🎓</div>'

SOCIAL_FOOTER = """<div style="margin-top:28px;padding:16px 10px;border-top:1px solid #e2e8f0;text-align:center;background:linear-gradient(180deg,#fff,#f8fafc);border-radius:0 0 18px 18px"><div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:10px"><a href="https://twitter.com/eng_mahmoud_man?s=07" target="_blank" style="width:36px;height:36px;background:#000;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-weight:800;font-size:14px">𝕏</a><a href="https://github.com/natiga-script" target="_blank" style="width:36px;height:36px;background:#0f172a;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:11px;font-weight:800">GH</a><a href="https://www.facebook.com/profile.php?id=100009579078219" target="_blank" style="width:36px;height:36px;background:#1877F2;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-weight:800">f</a><a href="https://www.linkedin.com/in/eng-mahmoud-mansour" target="_blank" style="width:36px;height:36px;background:#0A66C2;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:12px;font-weight:800">in</a><a href="https://www.instagram.com/eng_mahmoud_mansour/" target="_blank" style="width:36px;height:36px;background:radial-gradient(circle at 30% 107%,#fdf497 0%,#fdf497 5%,#fd5949 45%,#d6249f 60%,#285AEB 90%);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;text-decoration:none;font-size:11px;font-weight:800">IG</a></div><div style="font-size:11px;color:#64748b;line-height:1.8"><div>الكلية التكنولوجية بالمحلة الكبرى</div><div>المعهد الصناعي بالمحلة</div><div style="font-weight:800;color:#0f172a">د.م/ محمود منصور</div><div style="margin-top:6px;font-size:10px">© حقوق محفوظة لـ م/ محمود منصور 2026</div></div></div>"""

def build_att_html():
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    real_ip = get_real_ip()
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>تسجيل الحضور</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#dbeafe,#f0f9ff,#ffffff);min-height:100vh;padding:12px;display:flex;flex-direction:column}}.card{{max-width:440px;margin:auto;background:#fff;padding:22px;border-radius:22px;box-shadow:0 12px 40px rgba(15,23,42,.12);border:1px solid #e2e8f0;width:100%}}.header-lines{{text-align:center;line-height:1.7;margin:8px 0 14px 0}}.t1{{font-size:20px;font-weight:800;color:#0f172a}}.t2{{font-size:13px;color:#334155}}.t3{{font-size:13px;color:#334155}}.t4{{font-size:14px;font-weight:800;color:#1a73e8}}input{{width:100%;padding:13px 14px;margin:7px 0;border:1px solid #cbd5e1;border-radius:14px;font-size:15px;font-family:'Tajawal';background:#f8fafc;outline:none}} input.bad{{border-color:#dc2626;background:#fef2f2}}button{{width:100%;padding:14px;background:linear-gradient(135deg,#1a73e8,#0d47a1);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:800;font-family:'Tajawal';cursor:pointer}}button:disabled{{opacity:.4;cursor:not-allowed;background:#94a3b8!important}}.msgbox{{display:none;padding:13px;border-radius:12px;margin-top:12px;font-weight:800;font-size:15px;text-align:center}}#msgBox{{background:#fee2e2;color:#991b1b;border:2px solid #fecaca}}#ok{{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}}#exist,#ipblock,#wrong,#black,#deviceblock,#hwblock{{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}}#closed{{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}}#timer{{background:linear-gradient(135deg,#0f172a,#1e293b);color:#fff;padding:9px 16px;border-radius:999px;font-size:13px;font-weight:800;display:none;margin:10px auto;width:fit-content}}</style></head><body><div class="card">{LOGO_TAG}<div class="header-lines"><div class="t1">📝 تسجيل الحضور {APP_VERSION}</div><div class="t2">الكلية التكنولوجية بالمحلة الكبرى</div><div class="t3">المعهد الصناعي بالمحلة</div><div class="t4">د.م/ محمود منصور - IP مفتوح</div><div style="font-size:12px;color:#475569;margin-top:6px">IP الحالي: <b id="currentIp">{real_ip}:8080</b></div><div id="studentQr" style="display:flex;justify-content:center;margin:10px auto"></div></div><div id="timer">⏳ باقي: <span id="t">--:--</span></div><input id="pass" placeholder="كلمة سر المحاضرة"><input id="board" type="number" inputmode="numeric" placeholder="رقم السبورة"><input id="name" placeholder="الاسم رباعي عربي"><input id="nid" type="tel" maxlength="14" inputmode="numeric" placeholder="الرقم القومي 14 رقم"><button id="btn" onclick="sendData()">ارسال الحضور</button><div id="msgBox" class="msgbox"></div><div id="ok" class="msgbox">{cfg['after_msg']}</div><div id="exist" class="msgbox">⚠️ الرقم القومي مسجل</div><div id="ipblock" class="msgbox">❌ IP مكرر</div><div id="deviceblock" class="msgbox">❌ الجهاز سجل قبل كده</div><div id="hwblock" class="msgbox">❌ بصمة الجهاز مكررة</div><div id="closed" class="msgbox">⛔ مقفول</div><div id="wrong" class="msgbox">❌ كلمة السر غلط</div><div id="black" class="msgbox">⛔ محظور</div>{SOCIAL_FOOTER}</div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let isClosedByAdmin=false;function renderStudentQr(url){{let box=document.getElementById("studentQr");if(!box)return;box.innerHTML="";if(window.QRCode){{new QRCode(box,{{text:url,width:140,height:140}});}}else{{box.innerHTML="<small>الرابط: "+url+"</small>";}}}}async function refreshStudentIps(){{try{{let r=await fetch("/my_ips",{{cache:"no-store"}});let j=await r.json();let ip=j.primary||(j.ips||[])[0]||"{real_ip}";document.getElementById("currentIp").innerText=ip+":8080";let u="http://"+ip+":8080"+location.pathname+location.search;renderStudentQr(u);}}catch(e){{let ip='{real_ip}';document.getElementById('currentIp').innerText=ip+':8080';renderStudentQr('http://'+ip+':8080'+location.pathname+location.search);}}}}
function getHardwareFingerprint(){{try{{let fp=[navigator.userAgent,screen.width,navigator.language].join('|');let h=0;for(let i=0;i<fp.length;i++){{h=((h<<5)-h)+fp.charCodeAt(i);h=h&h;}}return 'hw_'+Math.abs(h).toString(36);}}catch(e){{return 'hw_err';}}}}
function getDeviceId(){{let s=localStorage.getItem('device_fingerprint');if(s)return s;let id=getHardwareFingerprint()+'_'+Math.random().toString(36).slice(2,6);localStorage.setItem('device_fingerprint',id);return id;}}
function isAlreadyRegisteredLocally(){{return localStorage.getItem('already_registered_'+getDeviceId())==='1' || localStorage.getItem('my_nid_registered')!==null;}}
function markAsRegistered(nid){{localStorage.setItem('already_registered_'+getDeviceId(),'1');localStorage.setItem('my_nid_registered',nid);}}
function applyAlreadyRegisteredUI(){{if(isAlreadyRegisteredLocally()){{let btn=document.getElementById('btn');btn.disabled=true;btn.innerText='✅ سجلت قبل كده';document.getElementById('closed').style.display='block';document.getElementById('closed').innerText='✅ سجلت من الجهاز ده';return true;}}return false;}}
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}}catch(e){{}}}}
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
function getParams(){{let p=new URLSearchParams(location.search);return {{open:p.get('open'),s:p.get('s')}};}}let cached=getParams();
function showMsg(t){{let b=document.getElementById('msgBox');b.innerText=t;b.style.display='block';}}
function hideAll(){{['ok','exist','ipblock','deviceblock','hwblock','wrong','closed','black','msgBox'].forEach(x=>document.getElementById(x).style.display='none');}}
function forceCloseAll(msg){{isClosedByAdmin=true;let btn=document.getElementById('btn'),tm=document.getElementById('timer'),cl=document.getElementById('closed');tm.style.display='none';cl.style.display='block';cl.innerText=msg||'⛔ الادمن قفل';btn.disabled=true;}}
function updateTimer(){{if(isClosedByAdmin)return;let o=cached.open,s=cached.s,btn=document.getElementById('btn'),cl=document.getElementById('closed'),tm=document.getElementById('timer');if(applyAlreadyRegisteredUI()){{tm.style.display='none';return;}}if(!o||!s||simpleHash(o+SECRET)!==s){{tm.style.display='none';cl.style.display='none';btn.disabled=false;return;}}let v=parseInt(o);if(nowSynced()>v){{tm.style.display='none';cl.style.display='block';cl.innerText='⛔ انتهى الوقت';btn.disabled=true;return;}}tm.style.display='block';cl.style.display='none';btn.disabled=false;let d=v-nowSynced(),m=Math.floor(d/60000),sc=Math.floor((d%60000)/1000);document.getElementById('t').innerText=m+':'+(sc<10?'0':'')+sc;}}
async function checkIfClosedByAdmin(){{try{{let r=await fetch('/get_config');let j=await r.json();if(!j.open||j.open=="0"||parseInt(j.open)<nowSynced()){{forceCloseAll('⛔ الادمن قفل التسجيل');}}}}catch(e){{}}}}
syncTime().then(()=>{{applyAlreadyRegisteredUI();setInterval(updateTimer,1000);updateTimer();setInterval(checkIfClosedByAdmin,2000);refreshStudentIps();setInterval(refreshStudentIps,2000);}});
async function sendData(){{
 if(isAlreadyRegisteredLocally()){{applyAlreadyRegisteredUI();return;}}
 hideAll();
 let p=document.getElementById('pass').value.trim(),b=document.getElementById('board').value.trim(),n=document.getElementById('name').value.trim(),id=document.getElementById('nid').value.trim();
 if(!p||!b||!n||!id){{showMsg('اكمل البيانات');return;}}id=id.replace(/[٠-٩۰-۹]/g,c=>'٠١٢٣٤٥٦٧٨٩'.includes(c)?'٠١٢٣٤٥٦٧٨٩'.indexOf(c):'۰۱۲۳۴۵۶۷۸۹'.indexOf(c)).replace(/[^0-9]/g,'');if(!/^\d{{14}}$/.test(id)){{showMsg('الرقم القومي يجب أن يتكون من 14 رقمًا صحيحًا');document.getElementById('nid').classList.add('bad');return;}}document.getElementById('nid').classList.remove('bad');
 try{{
  let r=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{open:cached.open||'',s:cached.s||'',name:n,nid:id,board:b,pass:p,deviceId:getDeviceId(),hwId:getHardwareFingerprint(),androidId:'',localApp:true}})}});
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
    cfg = load_cfg()
    LOGO_TAG = get_logo_tag(size=90, with_margin=True)
    HEADER_LOGO = get_header_logo_tag()
    ips = get_local_ips()
    primary = get_real_ip()
    router_ip = primary
    hotspot_ip = primary
    for ip in ips:
        if ip.startswith("192.168.0.") or ip.startswith("192.168.1."):
            router_ip = ip; break
    for ip in ips:
        if ip.startswith("192.168.43.") or ip.startswith("192.168.137."):
            hotspot_ip = ip; break
    if primary and primary.startswith("10."):
        hotspot_ip = primary
    ips_html = ", ".join(ips)
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>لوحة تحكم {APP_VERSION}</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Tajawal',Tahoma;background:linear-gradient(135deg,#eef2ff,#f5f7fb);padding:12px}} .container{{max-width:1100px;margin:auto}} .hidden{{display:none!important}} .header{{background:linear-gradient(135deg,#1e293b,#0f172a);color:#fff;padding:16px;border-radius:20px;display:flex;justify-content:space-between}} .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:14px 0}} .stat{{background:#fff;border-radius:16px;padding:14px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,.06)}} .stat b{{display:block;font-size:26px;color:#1a73e8}} .card{{background:#fff;border-radius:18px;padding:16px;margin-bottom:14px;box-shadow:0 6px 20px rgba(0,0,0,.05)}} .card-title{{font-weight:800;margin-bottom:12px}} label{{font-size:12px;font-weight:700}} input,textarea{{width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:12px;margin:4px 0}} .btn{{padding:12px 16px;border:none;border-radius:12px;font-weight:800;cursor:pointer}} .btn-primary{{background:#1a73e8;color:#fff}} .btn-success{{background:#16a34a;color:#fff}} .btn-danger{{background:#dc2626;color:#fff}} .btn-dark{{background:#0f172a;color:#fff}} .btn-warn{{background:#f59e0b;color:#fff}} .btn-light{{background:#f1f5f9}} .toolbar{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}} .table-wrap{{overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:750px}} th{{background:#0f172a;color:#fff;padding:10px}} td{{padding:8px;border-bottom:1px solid #eee;text-align:center}} #loginBox{{max-width:400px;margin:50px auto;background:#fff;padding:24px;border-radius:22px;text-align:center}} #adminTimer{{background:#fff;color:#0f172a;padding:8px 14px;border-radius:999px;font-size:12px;font-weight:800}} .linkBox{{background:#f8fafc;border:1px dashed #94a3b8;border-radius:12px;padding:10px;margin-top:8px}} .linkRow{{display:flex;gap:6px;margin:6px 0}}</style></head><body><div id="loginBox">{LOGO_TAG}<h2>دخول ادمن {APP_VERSION}</h2><p style="font-size:12px;color:#64748b">الكلية التكنولوجية - د.م/ محمود منصور<br>Serial: {ANDROID_SERIAL[:12]} - IP مفتوح</p><input id="adminPass" type="password" placeholder="باسورد الادمن"><button onclick="login()" class="btn btn-primary" style="width:100%;margin-top:12px">🔐 دخول</button><p id="loginErr" style="display:none;color:#dc2626">غلط</p>{SOCIAL_FOOTER}</div><div id="dash" class="container hidden"><div class="header"><div style="display:flex;align-items:center;gap:10px">{HEADER_LOGO}<div><div style="font-weight:800">{APP_VERSION} - IP مفتوح + سيريال + Logo</div><div style="font-size:11px;opacity:.8">الكلية التكنولوجية - د.م/ محمود منصور</div></div></div><div style="display:flex;gap:8px"><div id="adminTimer">⏱️ <span id="adminT">--:--</span></div><div id="status" style="padding:8px 14px;border-radius:999px;background:#fff;color:#0f172a">🔴 مقفول</div><button onclick="logout()" class="btn btn-light" style="padding:8px">🚪</button></div></div><div class="stats"><div class="stat"><b id="activeCount">0</b><span>النشط</span><div style="font-size:11px">/ <span id="maxCount">{cfg['max_active']}</span></div></div><div class="stat"><b id="waitCount">0</b><span>انتظار</span></div><div class="stat"><b id="count">0</b><span>اجمالي</span></div><div class="stat"><b id="lastMin">0</b><span>اخر دقيقة</span></div><div class="stat"><b id="showCount">0</b><span>المعروض</span></div></div><div class="card" style="background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1px solid #fcd34d"><div class="card-title">🔑 تغيير باسورد الادمن</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>القديم</label><input id="oldAdminPass" type="password"></div><div><label>الجديد</label><input id="newAdminPass" type="password"></div></div><button onclick="changeAdminPass()" class="btn btn-warn" style="width:100%;margin-top:10px">🔒 تغيير</button><div id="adminPassMsg" style="display:none;margin-top:8px;padding:10px;border-radius:10px;text-align:center"></div></div><div class="card" style="background:linear-gradient(135deg,#f8fafc,#eef2ff);border:1px dashed #93c5fd"><div class="card-title">⚙️ 1- اعدادات الطابور - IP مفتوح افتراضي</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>عدد الطابور</label><input id="maxActive" type="number" value="{cfg['max_active']}"></div><div><label>دفعات</label><input id="batch" type="number" value="{cfg['batch']}"></div></div><div><label>مدة بقاء الطالب</label><div style="display:flex;gap:8px"><input id="staySec" type="range" min="1" max="10" step="0.5" value="{cfg['stay_seconds']}" style="flex:1"><span id="stayVal">{cfg['stay_seconds']}s</span></div></div><label>رسالة التسجيل</label><textarea id="afterMsg">{cfg['after_msg']}</textarea><label>رسالة /done</label><textarea id="doneMsg">{cfg['done_msg']}</textarea><button onclick="saveAdv()" class="btn btn-dark" style="width:100%;margin-top:10px">💾 حفظ الاعدادات</button></div><div class="card" style="background:#fffbeb"><div class="card-title">🔒 2- تحكم التسجيل - APK</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label style="display:flex;gap:6px"><input type="checkbox" id="ipCheck" {"checked" if cfg['ip_check'] else ""} style="width:auto"> IP واحد = طالب واحد</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="nidCheck" {"checked" if cfg['nid_check'] else ""} style="width:auto"> منع القومي المكرر</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="deviceCheck" {"checked" if cfg.get('device_check',True) else ""} style="width:auto"> 🔒 منع نفس الجهاز VPN</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="hwCheck" {"checked" if cfg.get('hw_check',True) else ""} style="width:auto"> منع بصمة الجهاز hwId</label></div><div><label style="display:flex;gap:6px"><input type="checkbox" id="androidCheck" {"checked" if cfg.get('android_check',True) else ""} style="width:auto"> منع سيريال اندرويد</label></div></div><label>قائمة سوداء قومي</label><textarea id="blackNids">{','.join(cfg['black_nids'])}</textarea><label>سوداء IP</label><textarea id="blackIps">{','.join(cfg['black_ips'])}</textarea><label>بيضاء IP</label><textarea id="whiteIps">{','.join(cfg['white_ips'])}</textarea></div><div class="card"><div class="card-title">🔑 3- فتح المحاضرة</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>كلمة سر المحاضرة</label><input id="lecturePass" placeholder="2026"></div><div><label>المدة بالدقائق</label><input id="minutes" type="number" value="30"></div></div><div style="display:flex;gap:8px;margin-top:12px"><button onclick="openNow()" class="btn btn-success" style="flex:2">✅ افتح</button><button onclick="closeNow()" class="btn btn-danger" style="flex:1">⛔ اقفل</button></div><div id="shareBox" style="display:none;background:#e0f2fe;padding:14px;border-radius:14px;margin-top:14px"><div style="font-weight:800">📡 روابط الطلبة APK:</div><div style="text-align:center;background:#fff;border-radius:12px;padding:12px;margin:10px 0"><div id="adminQr" style="display:flex;justify-content:center"></div><div style="font-size:12px;margin-top:6px">امسح الكود من موبايل الطالب</div></div><div class="linkBox"><div class="linkRow"><b>📱 هوتسبوت APK:</b><input id="shareLinkHotspot" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkHotspot')" class="btn btn-warn" style="padding:6px">نسخ</button></div><div style="font-size:11px">IP الهوتسبوت: <b>{hotspot_ip}</b> - كل IPs: {ips_html}</div><div style="display:flex;gap:6px;margin-top:6px"><input id="customHotspotIp" value="{hotspot_ip}" style="flex:1"><button onclick="updateHotspotLink()" class="btn btn-light" style="padding:6px">تحديث</button><button onclick="autoDetectIp()" class="btn btn-success" style="padding:6px">🔄 كشف</button></div></div><div class="linkBox" style="background:#dcfce7"><div class="linkRow"><b>📶 روتر:</b><input id="shareLinkRouter" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkRouter')" class="btn btn-success" style="padding:6px">نسخ</button></div><div style="font-size:11px">IP الراوتر: <b>{router_ip}</b></div><div style="display:flex;gap:6px;margin-top:6px"><input id="customRouterIp" value="{router_ip}" style="flex:1"><button onclick="updateRouterLink()" class="btn btn-light" style="padding:6px">تحديث</button></div></div><div class="linkBox"><div class="linkRow"><b>🖥️ لوكالهوست:</b><input id="shareLinkLocal" readonly style="direction:ltr;font-size:11px;flex:1"><button onclick="copyById('shareLinkLocal')" class="btn btn-dark" style="padding:6px">نسخ</button></div></div><div style="font-size:12px;margin-top:8px">كلمة السر: <b id="currentPass"></b> | المدة: <b id="currentMin"></b> د</div></div></div><div class="card"><div class="card-title">📊 4- البيانات والتصدير</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input id="search" placeholder="🔍 بحث بالاسم او القومي"><input id="filterBoard" placeholder="فلتر رقم السبورة"></div><div class="toolbar"><button onclick="exportExcel()" class="btn btn-dark">📥 Excel CSV</button><button onclick="window.location.href='/export'" class="btn btn-success">⬇️ تصدير CSV عربي</button><button onclick="copyWhatsapp()" class="btn" style="background:#22c55e;color:#fff">🟢 واتساب</button><button onclick="clearQueue()" class="btn btn-warn">⚠️ فضي الطابور</button><button onclick="clearData()" class="btn btn-light" style="color:#dc2626">🗑️ مسح الكل</button></div><div class="table-wrap"><table id="tbl"><thead><tr><th>#</th><th>الوقت</th><th>الاسم</th><th>القومي</th><th>IP</th><th>الجهاز</th><th>سبورة</th><th>سيريال</th><th>🗑️ حذف</th></tr></thead><tbody></tbody></table></div>{SOCIAL_FOOTER}</div></div><script>
const SECRET="Mn2026_Secret_@#_KEY";let serverOffset=0;let lastOpen="",lastSig="";
async function syncTime(){{try{{let r=await fetch('/time');let d=await r.json();serverOffset=d.server-Date.now();}}catch(e){{}}}}
function nowSynced(){{return Date.now()+serverOffset;}}
function simpleHash(s){{let h=0;for(let i=0;i<s.length;i++){{h=((h<<5)-h)+s.charCodeAt(i);h=h&h;}}return Math.abs(h).toString(36);}}
async function checkAuth(){{if(localStorage.getItem('admin_ok')==='1'){{document.getElementById('loginBox').classList.add('hidden');document.getElementById('dash').classList.remove('hidden');await syncTime();try{{let rc=await fetch('/get_config');let scfg=await rc.json();if(scfg.open&&scfg.open!="0"&&parseInt(scfg.open)>nowSynced()){{localStorage.setItem('openUntil',scfg.open);lastOpen=scfg.open;lastSig=scfg.s||simpleHash(scfg.open+SECRET);await autoDetectIp();buildAllLinks();document.getElementById('shareBox').style.display='block';document.getElementById('currentPass').innerText=scfg.lecturePass;let mins=Math.round((parseInt(scfg.open)-nowSynced())/60000);document.getElementById('currentMin').innerText=mins>0?mins:0;}}}}catch(e){{}}refresh();setInterval(()=>{{refresh();updateAdminTimer();}},1000);}}}}
function drawAdminQr(){{let box=document.getElementById("adminQr");if(!box)return;box.innerHTML="";let u=document.getElementById("shareLinkHotspot")?.value||document.getElementById("shareLinkRouter")?.value||"";if(window.QRCode&&u)new QRCode(box,{{text:u,width:180,height:180}});else box.innerText=u;}}function buildAllLinks(){{if(!lastOpen)return;let host=location.host;let baseLocal=location.protocol+'//'+host;let baseHotspot='http://'+(document.getElementById('customHotspotIp').value.trim()||'{hotspot_ip}')+':8080';let baseRouter='http://'+(document.getElementById('customRouterIp').value.trim()||'{router_ip}')+':8080';let path='/attendance.html?open='+lastOpen+'&s='+lastSig;document.getElementById('shareLinkLocal').value=baseLocal+path;document.getElementById('shareLinkHotspot').value=baseHotspot+path;document.getElementById('shareLinkRouter').value=baseRouter+path;fetch('/__save_latest?link='+encodeURIComponent(path));drawAdminQr();}}
async function autoDetectIp(){{try{{let rip=await fetch('/my_ips');let j=await rip.json();if(j.primary){{if(j.primary.startsWith('192.168.0.')||j.primary.startsWith('192.168.1.'))document.getElementById('customRouterIp').value=j.primary;if(j.primary.startsWith('10.')||j.primary.startsWith('192.168.43.'))document.getElementById('customHotspotIp').value=j.primary;}}if(j.ips){{let r=j.ips.find(x=>x.startsWith('192.168.0.')||x.startsWith('192.168.1.'));if(r)document.getElementById('customRouterIp').value=r;let h=j.ips.find(x=>x.startsWith('192.168.43.'))||j.ips.find(x=>x.startsWith('10.'));if(h)document.getElementById('customHotspotIp').value=h;}}buildAllLinks();}}catch(e){{}}}}
function updateHotspotLink(){{buildAllLinks();}}function updateRouterLink(){{buildAllLinks();}}
function copyById(id){{let el=document.getElementById(id);el.select();document.execCommand('copy');alert('تم نسخ:\n'+el.value);}}
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
async function deleteOne(nid){{if(!confirm('تمسح الطالب ده؟ \n'+nid))return;let r=await fetch('/delete_one',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{nid}})}});let d=await r.json();if(d.ok){{alert('✅ اتمسح');refresh();}}else{{alert('❌ مش لاقيه');}}}}
document.getElementById('search')?.addEventListener('input',filterRender);document.getElementById('filterBoard')?.addEventListener('input',filterRender);
function exportExcel(){{if(!cachedData.length){{alert('لا يوجد');return;}}let csv='\uFEFFالوقت,الاسم,القومي,IP,الجهاز,السبورة,سيريال\n'+cachedData.map(x=>`"${{x.time}}","${{x.name}}","${{x.nid}}","${{x.ip||''}}","${{x.deviceId||''}}","${{x.board}}","${{x.androidId||''}}"`).join('\n');let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv;charset=utf-8;'}}));a.download='attendance_'+new Date().toISOString().slice(0,10)+'.csv';a.click();}}
function copyWhatsapp(){{if(!cachedData.length){{alert('لا يوجد');return;}}let txt=`كشف حضور ${{new Date().toLocaleDateString('ar-EG')}} - العدد ${{cachedData.length}}\n`+cachedData.map((x,i)=>`${{i+1}}- ${{x.name}} - ${{x.nid}} - سبورة ${{x.board}}`).join('\n');navigator.clipboard.writeText(txt).then(()=>alert('تم نسخ للواتساب'))}}
async function clearQueue(){{if(confirm('تفضي الطابور؟')){{await fetch('/clear_queue',{{method:'POST'}});refresh();}}}}
async function clearData(){{if(confirm('تمسح الكل؟')){{await fetch('/clear',{{method:'POST'}});refresh();}}}}
</script></body></html>"""

def ensure_files():
    cfg = load_cfg()
    save_cfg(cfg)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write("[]")

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        return

    def do_POST(self):
        client_ip = self.client_address[0]
        cfg = load_cfg()
        if self.path == '/admin_auth':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            ok = data.get('pass', '') == cfg.get('adminPass', DEFAULT_ADMIN_PASS)
            log_connection_event(client_ip, "دخول أدمن" if ok else "فشل دخول أدمن")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": ok}).encode('utf-8'))
            return
        if self.path == '/delete_one':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            nid_to_del = data.get('nid', '').strip()
            deleted = False
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, 'r', encoding='utf-8') as f:
                        all_data = json.load(f)
                    new_data = [x for x in all_data if x.get('nid') != nid_to_del]
                    if len(new_data) != len(all_data):
                        deleted = True
                        with open(DATA_FILE, 'w', encoding='utf-8') as f:
                            json.dump(new_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": deleted}).encode('utf-8'))
            return
        if self.path == '/change_admin_pass':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            old = data.get('oldPass', '')
            new = data.get('newPass', '').strip()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if old != cfg.get('adminPass', DEFAULT_ADMIN_PASS):
                self.wfile.write(json.dumps({"ok": False, "error": "الباسورد الحالي غلط"}).encode('utf-8')); return
            if len(new) < 4:
                self.wfile.write(json.dumps({"ok": False, "error": "الجديد قصير"}).encode('utf-8')); return
            cfg['adminPass'] = new
            save_cfg(cfg)
            self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))
            return
        if self.path == '/save_adv':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            for k in ["max_active", "stay_seconds", "batch", "after_msg", "done_msg", "ip_check", "nid_check", "device_check", "hw_check", "android_check", "black_nids", "black_ips", "white_ips"]:
                if k in data:
                    cfg[k] = data[k]
            save_cfg(cfg)
            self.send_response(200); self.end_headers(); return
        if self.path == '/set_config':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            cfg["lecturePass"] = data.get('lecturePass', '')
            cfg["open"] = data.get('open', '0')
            cfg["s"] = data.get('s', '')
            save_cfg(cfg)
            try:
                if cfg["open"] != "0" and cfg["open"] != "":
                    link = f"/attendance.html?open={cfg['open']}&s={cfg['s']}"
                    with open(LATEST_FILE, 'w', encoding='utf-8') as f:
                        f.write(link)
                    log_connection_event("السيرفر", "فتح المحاضرة", f"باسورد: {cfg['lecturePass']}")
                else:
                    if os.path.exists(LATEST_FILE):
                        os.remove(LATEST_FILE)
                    log_connection_event("السيرفر", "إغلاق المحاضرة")
            except Exception:
                pass
            self.send_response(200); self.end_headers(); return
        if self.path == '/save':
            try:
                length = int(self.headers.get('content-length', 0))
                body = self.rfile.read(length).decode('utf-8')
                data = json.loads(body)
                now_ms = int(datetime.now().timestamp() * 1000)
                cfg_open = cfg.get('open', '0')
                if cfg_open == "0" or cfg_open == "" or int(cfg_open) < now_ms:
                    log_connection_event(client_ip, "مرفوض (مغلقة)", data.get('name', ''))
                    self.send_response(403)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"closed": True}).encode('utf-8')); return
                if cfg.get('lecturePass', '').strip() and data.get('pass', '').strip() != cfg.get('lecturePass', '').strip():
                    log_connection_event(client_ip, "كلمة سر خاطئة", data.get('name', ''))
                    self.send_response(401); self.end_headers(); return
                nid = normalize_nid(data.get('nid', ''))
                if not valid_national_id(nid):
                    log_connection_event(client_ip, "رقم قومي خاطئ", data.get('name', ''))
                    self.send_response(422)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "الرقم القومي غير صحيح"}, ensure_ascii=False).encode('utf-8')); return
                deviceId = data.get('deviceId', '').strip()
                hwId = data.get('hwId', '').strip()
                androidId = data.get('androidId', '').strip()
                is_white = client_ip in cfg.get('white_ips', []) or client_ip == '127.0.0.1'
                if not is_white:
                    if nid in cfg.get('black_nids', []) or client_ip in cfg.get('black_ips', []):
                        log_connection_event(client_ip, "محظور (قائمة سوداء)", data.get('name', ''))
                        self.send_response(403)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"black": True}).encode('utf-8')); return
                all_data = []
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, 'r', encoding='utf-8') as f:
                        try:
                            all_data = json.load(f)
                        except Exception:
                            all_data = []
                if cfg.get('nid_check', True) and any(x.get('nid') == nid for x in all_data):
                    log_connection_event(client_ip, "مكرر (رقم قومي)", data.get('name', ''))
                    self.send_response(409); self.end_headers(); return
                if cfg.get('ip_check', False) and not is_white and any(x.get('ip') == client_ip for x in all_data):
                    self.send_response(410); self.end_headers(); return
                if cfg.get('device_check', True) and deviceId and not is_white and any(x.get('deviceId') == deviceId for x in all_data):
                    self.send_response(411); self.end_headers(); return
                if cfg.get('hw_check', True) and hwId and not is_white and any(x.get('hwId') == hwId for x in all_data):
                    self.send_response(412); self.end_headers(); return
                if cfg.get('android_check', True) and androidId and not is_white and any(x.get('androidId') == androidId for x in all_data):
                    self.send_response(413); self.end_headers(); return
                max_a = cfg.get('max_active', 32)
                if len(active_ips) >= max_a and client_ip not in active_ips and not is_white:
                    if client_ip not in waiting_queue:
                        waiting_queue[client_ip] = datetime.now()
                    pos = list(waiting_queue.keys()).index(client_ip) + 1
                    msg, _ = get_wait_msg(pos, max_a, cfg.get('stay_seconds', 2), cfg.get('batch', 5))
                    self.send_response(429)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"pos": pos, "msg": msg}).encode('utf-8')); return
                if client_ip in waiting_queue:
                    del waiting_queue[client_ip]
                active_ips[client_ip] = datetime.now().strftime("%H:%M:%S")
                rec = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "name": data.get('name', ''), "nid": nid, "board": data.get('board', ''), "pass": data.get('pass', ''), "ip": client_ip, "deviceId": deviceId, "hwId": hwId, "androidId": androidId, "source": "local-app" if data.get("localApp") else "web"}
                all_data.append(rec)
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)
                log_connection_event(client_ip, "تم الحضور بنجاح", data.get('name', ''))
                threading.Timer(float(cfg.get('stay_seconds', 2.0)), free_ip, args=(client_ip,)).start()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "redirect": "/done"}).encode('utf-8'))
            except Exception as e:
                print(e); self.send_response(500); self.end_headers()
        elif self.path == '/clear':
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                f.write("[]")
            active_ips.clear(); waiting_queue.clear()
            log_connection_event("الأدمن", "مسح كافة البيانات")
            self.send_response(200); self.end_headers()
        elif self.path == '/clear_queue':
            waiting_queue.clear(); active_ips.clear()
            self.send_response(200); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        client_ip = self.client_address[0]
        cfg = load_cfg()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = parsed.query
        low = path.lower()
        if low == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(json.dumps({"app": "attendance-local", "ok": True}).encode('utf-8'))
            return
        if low == '/__save_latest':
            params = urllib.parse.parse_qs(query)
            link = params.get('link', [''])[0]
            if link:
                link = urllib.parse.unquote(link)
                try:
                    with open(LATEST_FILE, 'w', encoding='utf-8') as f:
                        f.write(link)
                except Exception:
                    pass
            self.send_response(200); self.send_header('Content-Type', 'text/plain'); self.end_headers(); self.wfile.write(b'Saved'); return
        if low in ('/', '/go', '/go.html', '/index.html') or (low == '/attendance.html' and 'open' not in query):
            if os.path.exists(LATEST_FILE):
                try:
                    with open(LATEST_FILE, 'r', encoding='utf-8') as f:
                        latest = f.read().strip()
                    if latest and 'open=' in latest:
                        cfg_open = cfg.get('open', '0')
                        if cfg_open != "0" and cfg_open != "" and int(cfg_open) > int(datetime.now().timestamp() * 1000):
                            self.send_response(302)
                            self.send_header('Location', latest)
                            self.send_header('Cache-Control', 'no-store')
                            self.end_headers()
                            return
                except Exception:
                    pass
        if low == '/local-app':
            self.send_response(302); self.send_header('Location', '/attendance.html?local-app=1'); self.end_headers(); return
        if low == '/export':
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    export_rows = json.load(f)
            except Exception:
                export_rows = []
            import csv
            output = io.StringIO(newline='')
            writer = csv.writer(output)
            writer.writerow(['الوقت', 'الاسم', 'الرقم القومي', 'IP', 'الجهاز', 'بصمة الجهاز', 'رقم السبورة', 'سيريال أندرويد', 'مصدر التسجيل'])
            for row in export_rows:
                writer.writerow([row.get('time', ''), row.get('name', ''), row.get('nid', ''), row.get('ip', ''), row.get('deviceId', ''), row.get('hwId', ''), row.get('board', ''), row.get('androidId', ''), row.get('source', 'web')])
            payload = output.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="attendance.csv"')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload); return
        if low == '/my_ips':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"ips": get_local_ips(), "primary": get_real_ip(), "all_if": get_interface_ips()}).encode('utf-8')); return
        if path == '/time':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"server": int(datetime.now().timestamp() * 1000)}).encode('utf-8')); return
        if low == '/get_config':
            self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.end_headers()
            safe_cfg = {k: v for k, v in cfg.items() if k != 'adminPass'}
            self.wfile.write(json.dumps(safe_cfg).encode('utf-8')); return
        if low == '/list':
            self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.end_headers()
            data = []
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except Exception:
                        data = []
            last_min = 0
            try:
                now = datetime.now()
                for x in data:
                    t = datetime.strptime(x['time'], "%Y-%m-%d %H:%M:%S")
                    if (now - t).total_seconds() <= 60:
                        last_min += 1
            except Exception:
                pass
            self.wfile.write(json.dumps({"list": data, "active": len(active_ips), "waiting": len(waiting_queue), "max_active": cfg['max_active'], "last_min": last_min}).encode('utf-8')); return
        if low == '/done' or low == '/done.html':
            self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers()
            LOGO_TAG = get_logo_tag(size=90, with_margin=True)
            done_html = f"""<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>تم</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@700;800&display=swap" rel="stylesheet"><style>body{{text-align:center;font-family:'Tajawal',Tahoma;padding:15px;background:linear-gradient(135deg,#f0fdf4,#fff);min-height:100vh}}.card{{max-width:440px;margin:auto;background:#fff;padding:20px;border-radius:20px;box-shadow:0 12px 30px rgba(0,0,0,.1)}}</style></head><body><div class="card">{LOGO_TAG}<h1 style="color:#16a34a;font-size:22px">{cfg['done_msg']}</h1><p style="font-size:13px;line-height:1.7">الكلية التكنولوجية بالمحلة<br>المعهد الصناعي<br><b>د.م/ محمود منصور</b></p>{SOCIAL_FOOTER}</div></body></html>"""
            self.wfile.write(done_html.encode('utf-8')); return
        if 'attendance' in low or low == '/' or low == '/index.html':
            self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(build_att_html().encode('utf-8')); return
        if 'admin' in low:
            self.send_response(200); self.send_header('Content-type', 'text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(build_admin_html().encode('utf-8')); return
        return super().do_GET()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

SERVER_RUNNING = False
def run_server():
    global SERVER_RUNNING
    ensure_files()
    try:
        with ThreadingHTTPServer(('0.0.0.0', 8080), Handler) as httpd:
            SERVER_RUNNING = True
            log_connection_event("0.0.0.0:8080", "تم تشغيل السيرفر بنجاح")
            httpd.serve_forever()
    except OSError as exc:
        SERVER_RUNNING = False
        log_connection_event("0.0.0.0:8080", "خطأ تشغيل السيرفر", str(exc))

# --- 3. مكونات الواجهة الرسومية الاحترافية ---
PALETTE = {
    "bg": (0.94, 0.96, 0.99, 1),
    "primary": (0.10, 0.34, 0.78, 1),
    "primary_dark": (0.06, 0.14, 0.30, 1),
    "accent": (0.04, 0.52, 0.48, 1),
    "success": (0.09, 0.58, 0.28, 1),
    "danger": (0.82, 0.14, 0.16, 1),
    "warn": (0.88, 0.52, 0.05, 1),
    "card": (1, 1, 1, 1),
    "text_dark": (0.07, 0.10, 0.18, 1),
    "text_muted": (0.38, 0.45, 0.55, 1),
    "nav_bg": (0.06, 0.11, 0.22, 1),
}

class CardBox(BoxLayout):
    def __init__(self, bg_color=(1, 1, 1, 1), radius=16, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[dp(self.radius)])
        self.bind(size=self._upd, pos=self._upd)

    def _upd(self, *_):
        self.rect.size = self.size
        self.rect.pos = self.pos

class ArLabel(Label):
    def __init__(self, raw_text="", **kwargs):
        super().__init__(**kwargs)
        self.raw_text = raw_text
        if DEFAULT_FONT_NAME:
            self.font_name = DEFAULT_FONT_NAME
        self.update_lang()

    def set_raw(self, txt):
        self.raw_text = txt
        self.update_lang()

    def update_lang(self):
        app = App.get_running_app()
        lang = getattr(app, "current_lang", "ar") if app else "ar"
        self.text = ar(self.raw_text, lang)

class ModernButton(Button):
    def __init__(self, raw_text="", bg_color=PALETTE["primary"], radius=14, **kwargs):
        super().__init__(**kwargs)
        self.raw_text = raw_text
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.custom_bg = bg_color
        self.radius = radius
        if DEFAULT_FONT_NAME:
            self.font_name = DEFAULT_FONT_NAME
        self.bold = True
        with self.canvas.before:
            self.color_inst = Color(*self.custom_bg)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[dp(self.radius)])
        self.bind(size=self._upd, pos=self._upd)
        self.update_lang()

    def _upd(self, *_):
        self.rect.size = self.size
        self.rect.pos = self.pos

    def set_bg(self, col):
        self.custom_bg = col
        self.color_inst.rgba = col

    def update_lang(self):
        app = App.get_running_app()
        lang = getattr(app, "current_lang", "ar") if app else "ar"
        self.text = ar(self.raw_text, lang)

class ModernInput(TextInput):
    def __init__(self, raw_hint="", **kwargs):
        super().__init__(**kwargs)
        self.raw_hint = raw_hint
        if DEFAULT_FONT_NAME:
            self.font_name = DEFAULT_FONT_NAME
        self.padding = [dp(14), dp(12), dp(14), dp(12)]
        self.font_size = '16sp'
        self.background_normal = ''
        self.background_active = ''
        self.background_color = (0.96, 0.97, 0.99, 1)
        self.foreground_color = PALETTE["text_dark"]
        self.cursor_color = PALETTE["primary"]
        self.hint_text_color = PALETTE["text_muted"]
        self._is_updating = False
        self.raw_value = ""
        self.bind(text=self._on_text_change)
        self.update_lang()

    def _on_text_change(self, instance, val):
        if self._is_updating or self.password:
            return
        # إذا كان النص يحتوي على حروف عربية نعيد تشكيلها مباشرة أثناء الكتابة حتى لا تظهر مقلوبة أو منفصلة
        if re.search(r'[\u0600-\u06FF]', val):
            self._is_updating = True
            # نحتفظ بالنص الخام في raw_value إذا كتب المستخدم حروفاً عادية
            clean_raw = re.sub(r'[\uFE70-\uFEFF]', '', val)
            self.raw_value = clean_raw
            Clock.schedule_once(lambda dt: self._apply_arabic_display(val), 0)

    def _apply_arabic_display(self, val):
        try:
            # نستخدم Roboto للعرض إذا كان النص إنجليزي/أرقام فقط، و ArabicFont إذا كان عربي
            if re.search(r'[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]', val):
                if DEFAULT_FONT_NAME:
                    self.font_name = DEFAULT_FONT_NAME
            else:
                self.font_name = 'Roboto'
        finally:
            self._is_updating = False

    def get_clean_text(self):
        return self.raw_value.strip() if self.raw_value else self.text.strip()

    def update_lang(self):
        app = App.get_running_app()
        lang = getattr(app, "current_lang", "ar") if app else "ar"
        if DEFAULT_FONT_NAME:
            self.font_name = DEFAULT_FONT_NAME
        self.hint_text = ar(self.raw_hint, lang)

# --- 4. الشريط العلوي والسفلي الموحد في جميع الصفحات ---
class TopHeaderBar(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None, height=dp(58), padding=[dp(12), dp(6)], spacing=dp(8), **kwargs)
        with self.canvas.before:
            Color(*PALETTE["nav_bg"])
            self.bg = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._upd, pos=self._upd)

        logo_path = find_logo_file()
        if logo_path:
            img = Image(source=logo_path, size_hint=(None, None), size=(dp(40), dp(40)), allow_stretch=True)
            self.add_widget(img)

        self.title_lbl = ArLabel(
            raw_text="حضور - نظام الحضور الذكي",
            font_size='16sp', bold=True, color=(1, 1, 1, 1), halign='right', valign='middle'
        )
        self.title_lbl.bind(size=self.title_lbl.setter('text_size'))
        self.add_widget(self.title_lbl)

    def _upd(self, *_):
        self.bg.size = self.size
        self.bg.pos = self.pos

class BottomNavBar(BoxLayout):
    def __init__(self, app_ref, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None, height=dp(60), padding=[dp(8), dp(6)], spacing=dp(8), **kwargs)
        self.app_ref = app_ref
        with self.canvas.before:
            Color(*PALETTE["nav_bg"])
            self.bg = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._upd, pos=self._upd)

        self.btn_home = ModernButton(raw_text="الرئيسية", bg_color=PALETTE["primary"], radius=10, font_size='14sp')
        self.btn_settings = ModernButton(raw_text="الإعدادات", bg_color=(0.15, 0.22, 0.35, 1), radius=10, font_size='14sp')
        self.btn_contact = ModernButton(raw_text="اتصل بنا", bg_color=(0.15, 0.22, 0.35, 1), radius=10, font_size='14sp')

        self.btn_home.bind(on_press=lambda *_: self.app_ref.go_screen("role_select"))
        self.btn_settings.bind(on_press=lambda *_: self.app_ref.go_screen("settings"))
        self.btn_contact.bind(on_press=lambda *_: self.app_ref.go_screen("contact"))

        self.add_widget(self.btn_contact)
        self.add_widget(self.btn_settings)
        self.add_widget(self.btn_home)

    def _upd(self, *_):
        self.bg.size = self.size
        self.bg.pos = self.pos

    def highlight(self, screen_name):
        active_col = PALETTE["primary"]
        inactive_col = (0.15, 0.22, 0.35, 1)
        self.btn_home.set_bg(active_col if screen_name in ("role_select", "student", "admin_hub") else inactive_col)
        self.btn_settings.set_bg(active_col if screen_name == "settings" else inactive_col)
        self.btn_contact.set_bg(active_col if screen_name == "contact" else inactive_col)

# --- 5. شاشات التطبيق المتكاملة ---
class BaseScreen(Screen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = app_ref
        with self.canvas.before:
            Color(*PALETTE["bg"])
            self.bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._upd_bg, pos=self._upd_bg)

        self.outer = BoxLayout(orientation='vertical')
        self.header = TopHeaderBar()
        self.content_area = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12))
        self.nav = BottomNavBar(app_ref)

        self.outer.add_widget(self.header)
        self.outer.add_widget(self.content_area)
        self.outer.add_widget(self.nav)
        self.add_widget(self.outer)

    def _upd_bg(self, *_):
        self.bg_rect.size = self.size
        self.bg_rect.pos = self.pos

    def on_pre_enter(self, *args):
        self.nav.highlight(self.name)
        self.refresh_texts()

    def refresh_texts(self):
        self.header.title_lbl.update_lang()
        for btn in (self.nav.btn_home, self.nav.btn_settings, self.nav.btn_contact):
            btn.update_lang()

# شاشة 1: اختيار نوع الدخول (طالب / أدمن)
class RoleSelectScreen(BaseScreen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(app_ref, **kwargs)
        scroll = ScrollView()
        box = BoxLayout(orientation='vertical', spacing=dp(16), size_hint_y=None, padding=[dp(4), dp(10)])
        box.bind(minimum_height=box.setter('height'))

        welcome_card = CardBox(orientation='vertical', padding=dp(18), spacing=dp(8), size_hint_y=None, height=dp(190))
        logo_path = find_logo_file()
        if logo_path:
            welcome_card.add_widget(Image(source=logo_path, size_hint=(None, None), size=(dp(76), dp(76)), pos_hint={'center_x': 0.5}))
        self.lbl_inst = ArLabel(raw_text="الكلية التكنولوجية بالمحلة الكبرى", font_size='18sp', bold=True, color=PALETTE["text_dark"], size_hint_y=None, height=dp(32))
        self.lbl_sub = ArLabel(raw_text="المعهد الصناعي بالمحلة - د.م محمود منصور", font_size='14sp', color=PALETTE["primary"], size_hint_y=None, height=dp(26))
        self.lbl_choose = ArLabel(raw_text="اختر نوع الدخول للمتابعة", font_size='15sp', bold=True, color=PALETTE["text_muted"], size_hint_y=None, height=dp(28))
        welcome_card.add_widget(self.lbl_inst)
        welcome_card.add_widget(self.lbl_sub)
        welcome_card.add_widget(self.lbl_choose)

        # تبويب الطالب
        student_card = CardBox(orientation='vertical', padding=dp(16), spacing=dp(10), size_hint_y=None, height=dp(150))
        self.lbl_st_title = ArLabel(raw_text="بوابة الطالب", font_size='18sp', bold=True, color=PALETTE["primary"], size_hint_y=None, height=dp(30))
        self.lbl_st_desc = ArLabel(raw_text="تسجيل الحضور في المحاضرة عبر الباركود أو الشبكة المحلية", font_size='13sp', color=PALETTE["text_muted"], size_hint_y=None, height=dp(26))
        self.btn_student = ModernButton(raw_text="تسجيل حضور كطالب", bg_color=PALETTE["primary"], size_hint_y=None, height=dp(52), font_size='17sp')
        self.btn_student.bind(on_press=lambda *_: self.app_ref.go_screen("student"))
        student_card.add_widget(self.lbl_st_title)
        student_card.add_widget(self.lbl_st_desc)
        student_card.add_widget(self.btn_student)

        # تبويب الأدمن
        admin_card = CardBox(orientation='vertical', padding=dp(16), spacing=dp(10), size_hint_y=None, height=dp(150))
        self.lbl_ad_title = ArLabel(raw_text="بوابة الأدمن والدكتور", font_size='18sp', bold=True, color=PALETTE["primary_dark"], size_hint_y=None, height=dp(30))
        self.lbl_ad_desc = ArLabel(raw_text="إدارة السيرفر، متابعة الطلاب، عرض الباركود، ولوحة التحكم", font_size='13sp', color=PALETTE["text_muted"], size_hint_y=None, height=dp(26))
        self.btn_admin = ModernButton(raw_text="دخول كأدمن", bg_color=PALETTE["primary_dark"], size_hint_y=None, height=dp(52), font_size='17sp')
        self.btn_admin.bind(on_press=self._prompt_admin_password)
        admin_card.add_widget(self.lbl_ad_title)
        admin_card.add_widget(self.lbl_ad_desc)
        admin_card.add_widget(self.btn_admin)

        box.add_widget(welcome_card)
        box.add_widget(student_card)
        box.add_widget(admin_card)
        scroll.add_widget(box)
        self.content_area.add_widget(scroll)

    def _prompt_admin_password(self, *_):
        if getattr(self.app_ref, "admin_authenticated", False):
            self.app_ref.go_screen("admin_hub")
            return
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12))
        lbl = ArLabel(raw_text="أدخل كلمة سر الأدمن للمتابعة", font_size='15sp', color=(1, 1, 1, 1), size_hint_y=None, height=dp(34))
        pwd_input = ModernInput(raw_hint="كلمة سر الأدمن الافتراضية 2026", password=True, multiline=False, size_hint_y=None, height=dp(48))
        pwd_input.font_name = 'Roboto'
        err_lbl = ArLabel(raw_text="", font_size='13sp', color=(1, 0.4, 0.4, 1), size_hint_y=None, height=dp(26))
        btns = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(46))
        btn_ok = ModernButton(raw_text="دخول", bg_color=PALETTE["success"])
        btn_cancel = ModernButton(raw_text="إلغاء", bg_color=PALETTE["danger"])
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_ok)

        content.add_widget(lbl)
        content.add_widget(pwd_input)
        content.add_widget(err_lbl)
        content.add_widget(btns)

        popup = Popup(title=ar("التحقق من صلاحية الأدمن"), content=content, size_hint=(0.9, None), height=dp(260), auto_dismiss=False)
        if DEFAULT_FONT_NAME:
            popup.title_font = DEFAULT_FONT_NAME

        def verify(*_):
            cfg = load_cfg()
            expected = cfg.get("adminPass", DEFAULT_ADMIN_PASS)
            if pwd_input.text.strip() == expected:
                self.app_ref.admin_authenticated = True
                popup.dismiss()
                self.app_ref.go_screen("admin_hub")
            else:
                err_lbl.set_raw("كلمة السر غير صحيحة، حاول مرة أخرى")

        btn_ok.bind(on_press=verify)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

    def refresh_texts(self):
        super().refresh_texts()
        for w in (self.lbl_inst, self.lbl_sub, self.lbl_choose, self.lbl_st_title, self.lbl_st_desc, self.btn_student, self.lbl_ad_title, self.lbl_ad_desc, self.btn_admin):
            w.update_lang()

# شاشة 2: صفحة الطالب لتسجيل الحضور (محدثة لعرض واجهة المتصفح الكاملة أو التسجيل المباشر)
class StudentScreen(BaseScreen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(app_ref, **kwargs)
        scroll = ScrollView()
        form = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, padding=[dp(2), dp(4)])
        form.bind(minimum_height=form.setter('height'))

        card = CardBox(orientation='vertical', padding=dp(14), spacing=dp(10), size_hint_y=None)
        card.bind(minimum_height=card.setter('height'))

        self.lbl_title = ArLabel(raw_text="تسجيل حضور الطالب", font_size='19sp', bold=True, color=PALETTE["primary"], size_hint_y=None, height=dp(36))
        card.add_widget(self.lbl_title)

        # زر فتح صفحة الطالب الكاملة بنفس تنسيق المتصفح تماماً
        self.btn_web_student = ModernButton(raw_text="فتح صفحة الطالب الكاملة بالتنسيق الكامل", bg_color=PALETTE["primary_dark"], size_hint_y=None, height=dp(48), font_size='15sp')
        self.btn_web_student.bind(on_press=self._open_full_student_page)
        card.add_widget(self.btn_web_student)

        self.server_url = ModernInput(text=f"http://{get_real_ip()}:8080", raw_hint="عنوان السيرفر", multiline=False, size_hint_y=None, height=dp(50))
        self.server_url.font_name = 'Roboto'
        card.add_widget(self.server_url)

        actions = BoxLayout(orientation='horizontal', spacing=dp(8), size_hint_y=None, height=dp(48))
        self.btn_scan = ModernButton(raw_text="مسح الباركود", bg_color=PALETTE["primary"], font_size='14sp')
        self.btn_discover = ModernButton(raw_text="اتصال تلقائي بالشبكة", bg_color=PALETTE["accent"], font_size='14sp')
        self.btn_scan.bind(on_press=self._scan_qr)
        self.btn_discover.bind(on_press=self._discover_server)
        actions.add_widget(self.btn_scan)
        actions.add_widget(self.btn_discover)
        card.add_widget(actions)

        self.student_pass = ModernInput(raw_hint="كلمة سر المحاضرة", password=True, multiline=False, size_hint_y=None, height=dp(50))
        self.student_board = ModernInput(raw_hint="رقم السبورة", multiline=False, input_filter='int', size_hint_y=None, height=dp(50))
        self.student_name = ModernInput(raw_hint="الاسم رباعي باللغة العربية", multiline=False, size_hint_y=None, height=dp(50))
        self.student_nid = ModernInput(raw_hint="الرقم القومي 14 رقم", multiline=False, input_filter='int', size_hint_y=None, height=dp(50))

        for inp in (self.student_pass, self.student_board, self.student_name, self.student_nid):
            card.add_widget(inp)

        self.student_msg = ArLabel(
            raw_text="اتصل بشبكة الدكتور ثم امسح الباركود أو اضغط اتصال تلقائي",
            font_size='14sp', bold=True, color=PALETTE["text_dark"], size_hint_y=None, height=dp(56), halign='center', valign='middle'
        )
        self.student_msg.bind(size=self.student_msg.setter('text_size'))
        card.add_widget(self.student_msg)

        self.btn_send = ModernButton(raw_text="إرسال وتسجيل الحضور", bg_color=PALETTE["success"], size_hint_y=None, height=dp(54), font_size='17sp')
        self.btn_send.bind(on_press=self._submit_native_attendance)
        card.add_widget(self.btn_send)

        form.add_widget(card)
        scroll.add_widget(form)
        self.content_area.add_widget(scroll)

    def _open_full_student_page(self, *_):
        base = self._set_server_url(self.server_url.text)
        if not base:
            base = f"http://{get_real_ip()}:8080"
        self.app_ref.open_in_app_webview('/attendance.html', base_url=base)

    def _set_server_url(self, value):
        value = (value or "").strip()
        if value and not value.startswith(("http://", "https://")):
            value = "http://" + value
        if value.endswith("/"):
            value = value[:-1]
        self.server_url.text = value
        self.server_url.font_name = 'Roboto'
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
            self.student_msg.set_raw("وجه الكاميرا إلى باركود الدكتور")
        except Exception:
            self.student_msg.set_raw("استخدم زر الاتصال التلقائي بالشبكة أو اكتب عنوان الدكتور يدوياً")

    def _on_activity_result(self, request_code, result_code, intent):
        try:
            if int(request_code) != 1201 or intent is None:
                return
            data = intent.getStringExtra("SCAN_RESULT")
            if not data:
                return
            from urllib.parse import urlparse
            raw = str(data).strip()
            parsed = urlparse(raw if raw.startswith(('http://', 'https://')) else 'http://' + raw)
            if parsed.hostname:
                port = parsed.port or 8080
                base = f"http://{parsed.hostname}:{port}"
                self._set_server_url(base)
                self.student_msg.set_raw("تم مسح الباركود بنجاح! جارٍ فتح صفحة الحضور...")
                full_path = parsed.path + ("?" + parsed.query if parsed.query else "")
                Clock.schedule_once(lambda dt: self.app_ref.open_in_app_webview(full_path or '/attendance.html', base_url=base), 0.2)
        except Exception:
            self.student_msg.set_raw("تعذر قراءة الباركود، حاول مرة أخرى")

    def _discover_server(self, *_):
        self.student_msg.set_raw("جارٍ البحث عن سيرفر المحاضرة على الشبكة...")
        def worker():
            import urllib.request, concurrent.futures, ipaddress
            found = None
            own_ip = get_real_ip()
            candidates = []
            if own_ip:
                try:
                    net = ipaddress.ip_network(own_ip + '/24', strict=False)
                    candidates = [str(ip) for ip in net.hosts() if str(ip) != own_ip]
                except Exception:
                    pass
            candidates += ["192.168.43.1", "192.168.49.1", "192.168.137.1", "192.168.0.1", "192.168.1.1", "127.0.0.1"]
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
                    if str(cfg.get('open', '0')) not in ('', '0') and int(cfg.get('open', '0')) > int(datetime.now().timestamp() * 1000):
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
                    self.student_msg.color = PALETTE["success"]
                    self.student_msg.set_raw("تم الاتصال بسيرفر الدكتور بنجاح")
                    self.app_ref.open_in_app_webview('/attendance.html', base_url=found)
                else:
                    self.student_msg.color = PALETTE["danger"]
                    self.student_msg.set_raw("لم يتم العثور على محاضرة مفتوحة. تأكد من الاتصال بنفس الشبكة")
            Clock.schedule_once(done, 0)
        threading.Thread(target=worker, daemon=True).start()

    def _submit_native_attendance(self, *_):
        import urllib.request, urllib.error
        server = self._set_server_url(self.server_url.text)
        if not server:
            self.student_msg.set_raw("حدد عنوان السيرفر أولاً")
            return
        nid = normalize_nid(self.student_nid.text)
        name_val = self.student_name.get_clean_text()
        if not self.student_pass.text.strip() or not self.student_board.text.strip() or not name_val or not nid:
            self.student_msg.color = PALETTE["danger"]
            self.student_msg.set_raw("من فضلك أكمل جميع البيانات المطلوبة")
            return
        if not valid_national_id(nid):
            self.student_msg.color = PALETTE["danger"]
            self.student_msg.set_raw("الرقم القومي غير صحيح يجب أن يكون 14 رقماً صحيحاً")
            return
        self.student_msg.color = PALETTE["primary"]
        self.student_msg.set_raw("جارٍ إرسال بيانات الحضور...")
        device_id = "android-" + str(ANDROID_SERIAL)
        payload = {
            "name": name_val, "nid": nid,
            "board": self.student_board.text.strip(), "pass": self.student_pass.text.strip(),
            "deviceId": device_id, "hwId": device_id, "androidId": str(ANDROID_SERIAL), "localApp": True
        }
        def worker():
            try:
                with urllib.request.urlopen(server + '/get_config', timeout=4) as resp:
                    cfg = json.loads(resp.read().decode('utf-8'))
                payload["open"] = cfg.get("open", "")
                payload["s"] = cfg.get("s", "")
                req = urllib.request.Request(server + '/save', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(req, timeout=8) as resp:
                    result = json.loads(resp.read().decode('utf-8'))
                ok = result.get("ok", False)
                msg = "تم تسجيل حضورك بنجاح في كشف الدكتور" if ok else "تعذر التسجيل"
                col = PALETTE["success"] if ok else PALETTE["danger"]
            except urllib.error.HTTPError as e:
                messages = {
                    401: "كلمة سر المحاضرة غير صحيحة", 403: "المحاضرة مغلقة حالياً",
                    409: "هذا الرقم القومي مسجل مسبقاً", 410: "هذا الجهاز سجل مسبقاً",
                    411: "هذا الهاتف سجل الحضور بالفعل", 422: "الرقم القومي غير صحيح",
                    429: "الطابور ممتلئ، انتظر ثوانٍ وحاول مجدداً"
                }
                msg = messages.get(e.code, "خطأ في التسجيل")
                col = PALETTE["danger"]
            except Exception:
                msg = "تعذر الاتصال بهاتف الدكتور. تأكد من الواي فاي أو الهوتسبوت"
                col = PALETTE["danger"]
            def upd(_dt):
                self.student_msg.color = col
                self.student_msg.set_raw(msg)
            Clock.schedule_once(upd, 0)
        threading.Thread(target=worker, daemon=True).start()

    def refresh_texts(self):
        super().refresh_texts()
        for w in (self.lbl_title, self.btn_web_student, self.btn_scan, self.btn_discover, self.student_pass, self.student_board, self.student_name, self.student_nid, self.student_msg, self.btn_send):
            w.update_lang()

# شاشة 3: مركز تحكم الأدمن (السيرفر الحي + لوحة التحكم الكاملة داخل التطبيق + الباركود)
class AdminHubScreen(BaseScreen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(app_ref, **kwargs)
        tabs_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(46), spacing=dp(6))
        self.tab_srv = ModernButton(raw_text="السيرفر والاتصال", bg_color=PALETTE["primary"], radius=10, font_size='13sp')
        self.tab_dash = ModernButton(raw_text="لوحة تحكم الأدمن", bg_color=PALETTE["primary_dark"], radius=10, font_size='13sp')
        self.tab_qr = ModernButton(raw_text="باركود الطلاب", bg_color=PALETTE["accent"], radius=10, font_size='13sp')

        self.tab_srv.bind(on_press=lambda *_: self._switch_subview("server"))
        self.tab_dash.bind(on_press=lambda *_: self.app_ref.open_in_app_webview('/admin'))
        self.tab_qr.bind(on_press=lambda *_: self._switch_subview("qr"))

        tabs_bar.add_widget(self.tab_qr)
        tabs_bar.add_widget(self.tab_dash)
        tabs_bar.add_widget(self.tab_srv)
        self.content_area.add_widget(tabs_bar)

        self.sub_container = BoxLayout(orientation='vertical')
        self.content_area.add_widget(self.sub_container)
        self._build_server_view()
        self._build_qr_view()
        self._switch_subview("server")
        Clock.schedule_interval(self._update_server_stats, 2)

    def _build_server_view(self):
        self.srv_scroll = ScrollView()
        box = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
        box.bind(minimum_height=box.setter('height'))

        status_card = CardBox(orientation='vertical', padding=dp(14), spacing=dp(8), size_hint_y=None, height=dp(205))
        self.lbl_srv_head = ArLabel(raw_text="حالة السيرفر المحلي", font_size='17sp', bold=True, color=PALETTE["primary"], size_hint_y=None, height=dp(28))
        self.lbl_srv_info = ArLabel(raw_text="جارٍ فحص الشبكة...", font_size='14sp', color=PALETTE["text_dark"], size_hint_y=None, height=dp(105), halign='center', valign='middle')
        self.lbl_srv_info.bind(size=self.lbl_srv_info.setter('text_size'))

        btn_open_web = ModernButton(raw_text="فتح لوحة الإعدادات والكشوفات داخل التطبيق", bg_color=PALETTE["primary_dark"], size_hint_y=None, height=dp(46), font_size='14sp')
        btn_open_web.bind(on_press=lambda *_: self.app_ref.open_in_app_webview('/admin'))

        status_card.add_widget(self.lbl_srv_head)
        status_card.add_widget(self.lbl_srv_info)
        status_card.add_widget(btn_open_web)

        log_card = CardBox(orientation='vertical', padding=dp(14), spacing=dp(8), size_hint_y=None, height=dp(260))
        self.lbl_log_head = ArLabel(raw_text="سجل اتصال وحضور الطلاب المباشر", font_size='16sp', bold=True, color=PALETTE["accent"], size_hint_y=None, height=dp(28))
        self.lbl_live_logs = ArLabel(raw_text="في انتظار اتصال الطلاب...", font_size='13sp', color=PALETTE["text_dark"], size_hint_y=None, height=dp(200), halign='right', valign='top')
        self.lbl_live_logs.bind(size=self.lbl_live_logs.setter('text_size'))
        log_card.add_widget(self.lbl_log_head)
        log_card.add_widget(self.lbl_live_logs)

        box.add_widget(status_card)
        box.add_widget(log_card)
        self.srv_scroll.add_widget(box)

    def _build_qr_view(self):
        self.qr_card = CardBox(orientation='vertical', padding=dp(16), spacing=dp(12))
        self.lbl_qr_title = ArLabel(raw_text="امسح الباركود بكاميرا هاتف الطالب للدخول", font_size='17sp', bold=True, color=PALETTE["primary_dark"], size_hint_y=None, height=dp(34))
        self.qr_img = Image(size_hint=(1, 0.65), allow_stretch=True, keep_ratio=True)
        self.lbl_qr_url = Label(text="", font_size='14sp', bold=True, color=PALETTE["primary"], size_hint_y=None, height=dp(40))
        btn_refresh_qr = ModernButton(raw_text="تحديث الباركود وعنوان الشبكة", bg_color=PALETTE["accent"], size_hint_y=None, height=dp(46), font_size='15sp')
        btn_refresh_qr.bind(on_press=lambda *_: self._generate_qr_image())

        self.qr_card.add_widget(self.lbl_qr_title)
        self.qr_card.add_widget(self.qr_img)
        self.qr_card.add_widget(self.lbl_qr_url)
        self.qr_card.add_widget(btn_refresh_qr)

    def _generate_qr_image(self):
        ip = get_real_ip()
        cfg = load_cfg()
        if cfg.get("open", "0") not in ("", "0"):
            url = f"http://{ip}:8080/attendance.html?open={cfg['open']}&s={cfg.get('s', '')}"
        else:
            url = f"http://{ip}:8080/go"
        self.lbl_qr_url.text = url
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            buf.seek(0)
            self.qr_img.texture = CoreImage(buf, ext="png").texture
        except Exception:
            pass

    def _switch_subview(self, mode):
        self.sub_container.clear_widgets()
        if mode == "server":
            self.sub_container.add_widget(self.srv_scroll)
            self._update_server_stats()
        elif mode == "qr":
            self._generate_qr_image()
            self.sub_container.add_widget(self.qr_card)

    def _update_server_stats(self, *_):
        if self.name != "admin_hub":
            return
        ip = get_real_ip()
        all_ips = " - ".join(get_local_ips()[:4])
        state = "يعمل بنشاط" if SERVER_RUNNING else "جارٍ التهيئة"
        total_reg = 0
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    total_reg = len(json.load(f))
            except Exception:
                pass
        info = f"حالة السيرفر: {state}\nالعنوان الرئيسي: {ip}:8080\nشبكات متاحة: {all_ips}\nالنشط حالياً: {len(active_ips)} | إجمالي المسجلين: {total_reg}"
        self.lbl_srv_info.set_raw(info)

        if recent_connections:
            lines = []
            for ev in recent_connections[:8]:
                lines.append(f"{ev['time']} - {ev['ip']} : {ev['status']} {ev['detail']}")
            self.lbl_live_logs.set_raw("\n".join(lines))

    def refresh_texts(self):
        super().refresh_texts()
        for w in (self.tab_srv, self.tab_dash, self.tab_qr, self.lbl_srv_head, self.lbl_srv_info, self.lbl_log_head, self.lbl_live_logs, self.lbl_qr_title):
            w.update_lang()

# شاشة 4: الإعدادات (تغيير اللغة + رقم الإصدار)
class SettingsScreen(BaseScreen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(app_ref, **kwargs)
        card = CardBox(orientation='vertical', padding=dp(18), spacing=dp(14), size_hint_y=None, height=dp(330))
        self.lbl_title = ArLabel(raw_text="إعدادات التطبيق", font_size='20sp', bold=True, color=PALETTE["primary_dark"], size_hint_y=None, height=dp(38))
        self.lbl_lang = ArLabel(raw_text="لغة واجهة التطبيق", font_size='16sp', bold=True, color=PALETTE["text_dark"], size_hint_y=None, height=dp(30))

        lang_row = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(50))
        self.btn_ar = ModernButton(raw_text="اللغة العربية", bg_color=PALETTE["primary"])
        self.btn_en = ModernButton(raw_text="انجليزي", bg_color=PALETTE["text_muted"])
        self.btn_ar.bind(on_press=lambda *_: self._set_lang("ar"))
        self.btn_en.bind(on_press=lambda *_: self._set_lang("en"))
        lang_row.add_widget(self.btn_en)
        lang_row.add_widget(self.btn_ar)

        self.lbl_ver = ArLabel(raw_text="إصدار التطبيق: 2.5.0 برو", font_size='15sp', bold=True, color=PALETTE["accent"], size_hint_y=None, height=dp(32))
        self.lbl_dev = ArLabel(raw_text="تطوير: د.م محمود منصور - الكلية التكنولوجية بالمحلة", font_size='13sp', color=PALETTE["text_muted"], size_hint_y=None, height=dp(30))

        self.btn_logout_admin = ModernButton(raw_text="تسجيل خروج الأدمن", bg_color=PALETTE["danger"], size_hint_y=None, height=dp(46))
        self.btn_logout_admin.bind(on_press=self._logout_admin)

        card.add_widget(self.lbl_title)
        card.add_widget(self.lbl_lang)
        card.add_widget(lang_row)
        card.add_widget(self.lbl_ver)
        card.add_widget(self.lbl_dev)
        card.add_widget(self.btn_logout_admin)
        self.content_area.add_widget(card)
        self.content_area.add_widget(BoxLayout())

    def _set_lang(self, lang):
        self.app_ref.current_lang = lang
        cfg = load_cfg()
        cfg["lang"] = lang
        save_cfg(cfg)
        self.btn_ar.set_bg(PALETTE["primary"] if lang == "ar" else PALETTE["text_muted"])
        self.btn_en.set_bg(PALETTE["primary"] if lang == "en" else PALETTE["text_muted"])
        self.refresh_texts()

    def _logout_admin(self, *_):
        self.app_ref.admin_authenticated = False
        self.app_ref.go_screen("role_select")

    def refresh_texts(self):
        super().refresh_texts()
        for w in (self.lbl_title, self.lbl_lang, self.btn_ar, self.btn_en, self.lbl_ver, self.lbl_dev, self.btn_logout_admin):
            w.update_lang()

# شاشة 5: اتصل بنا (أيقونات وروابط السوشيال ميديا بدون أي مربعات)
class ContactScreen(BaseScreen):
    def __init__(self, app_ref, **kwargs):
        super().__init__(app_ref, **kwargs)
        scroll = ScrollView()
        box = BoxLayout(orientation='vertical', spacing=dp(12), size_hint_y=None, padding=[dp(2), dp(6)])
        box.bind(minimum_height=box.setter('height'))

        header_card = CardBox(orientation='vertical', padding=dp(16), spacing=dp(8), size_hint_y=None, height=dp(135))
        self.lbl_title = ArLabel(raw_text="تواصل معنا والدعم الفني", font_size='19sp', bold=True, color=PALETTE["primary_dark"], size_hint_y=None, height=dp(34))
        self.lbl_sub = ArLabel(raw_text="د.م محمود منصور\nالكلية التكنولوجية بالمحلة الكبرى - المعهد الصناعي", font_size='14sp', color=PALETTE["text_muted"], size_hint_y=None, height=dp(55))
        header_card.add_widget(self.lbl_title)
        header_card.add_widget(self.lbl_sub)
        box.add_widget(header_card)

        socials = [
            ("منصة تويتر إكس", "https://twitter.com/eng_mahmoud_man?s=07", (0.08, 0.09, 0.11, 1)),
            ("حساب جيت هاب للمشاريع", "https://github.com/natiga-script", (0.14, 0.16, 0.18, 1)),
            ("صفحة فيسبوك الرسمية", "https://www.facebook.com/profile.php?id=100009579078219", (0.09, 0.46, 0.95, 1)),
            ("حساب لينكد إن المهني", "https://www.linkedin.com/in/eng-mahmoud-mansour", (0.04, 0.40, 0.76, 1)),
            ("حساب انستجرام الرسمي", "https://www.instagram.com/eng_mahmoud_mansour/", (0.83, 0.18, 0.47, 1)),
        ]
        self.social_btns = []
        for title, url, col in socials:
            btn = ModernButton(raw_text=title, bg_color=col, size_hint_y=None, height=dp(52), font_size='16sp')
            btn.bind(on_press=lambda _, u=url: webbrowser.open(u))
            box.add_widget(btn)
            self.social_btns.append(btn)

        scroll.add_widget(box)
        self.content_area.add_widget(scroll)

    def refresh_texts(self):
        super().refresh_texts()
        self.lbl_title.update_lang()
        self.lbl_sub.update_lang()
        for b in self.social_btns:
            b.update_lang()

# --- 6. التطبيق الرئيسي وعرض صفحات الويب الكاملة داخل التطبيق (WebView) ---
class MainApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_lang = "ar"
        self.admin_authenticated = False

    def _acquire_wake_lock(self):
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            PowerManager = autoclass('android.os.PowerManager')
            activity = PythonActivity.mActivity
            pm = activity.getSystemService(Context.POWER_SERVICE)
            self._wake_lock = pm.newWakeLock(PowerManager.SCREEN_DIM_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, "AttendanceApp::WakeLock")
            self._wake_lock.acquire()
        except Exception:
            pass

    def go_screen(self, name):
        if hasattr(self, "sm") and self.sm.has_screen(name):
            self.sm.current = name

    def open_in_app_webview(self, path='/admin', base_url='http://127.0.0.1:8080'):
        """فتح صفحة الأدمن أو الطالب الكاملة داخل التطبيق بنفس تنسيق المتصفح تماماً"""
        target_url = base_url.rstrip('/') + path
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            from android.runnable import run_on_ui_thread
        except Exception:
            webbrowser.open(target_url)
            return

        app = self
        class CloseListener(PythonJavaClass):
            __javainterfaces__ = ['android/view/View$OnClickListener']
            __javacontext__ = 'app'
            @java_method('(Landroid/view/View;)V')
            def onClick(self, view):
                app._close_in_app_webview()

        @run_on_ui_thread
        def show():
            try:
                # إغلاق أي WebView سابق إن وجد
                if getattr(app, '_android_webview_frame', None) is not None:
                    parent = app._android_webview_frame.getParent()
                    if parent is not None:
                        parent.removeView(app._android_webview_frame)

                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                FrameLayout = autoclass('android.widget.FrameLayout')
                LinearLayout = autoclass('android.widget.LinearLayout')
                AndroidButton = autoclass('android.widget.Button')
                WebView = autoclass('android.webkit.WebView')
                WebViewClient = autoclass('android.webkit.WebViewClient')
                WebChromeClient = autoclass('android.webkit.WebChromeClient')
                LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
                Color = autoclass('android.graphics.Color')
                activity = PythonActivity.mActivity

                frame = FrameLayout(activity)
                frame.setBackgroundColor(Color.WHITE)
                column = LinearLayout(activity)
                column.setOrientation(1)

                bar = LinearLayout(activity)
                bar.setOrientation(0)
                bar.setBackgroundColor(Color.parseColor('#0F172A'))
                bar.setPadding(16, 12, 16, 12)

                close_btn = AndroidButton(activity)
                close_btn.setText('رجوع إلى التطبيق')
                close_btn.setTextColor(Color.WHITE)
                close_btn.setTextSize(15.0)
                close_btn.setAllCaps(False)
                close_btn.setBackgroundColor(Color.parseColor('#1D4ED8'))
                bar.addView(close_btn, LinearLayout.LayoutParams(-1, -2))
                column.addView(bar, LinearLayout.LayoutParams(-1, -2))

                web = WebView(activity)
                settings = web.getSettings()
                settings.setJavaScriptEnabled(True)
                settings.setDomStorageEnabled(True)
                settings.setDatabaseEnabled(True)
                settings.setAllowFileAccess(True)
                settings.setUseWideViewPort(True)
                settings.setLoadWithOverviewMode(True)
                settings.setBuiltInZoomControls(True)
                settings.setDisplayZoomControls(False)
                web.setWebViewClient(WebViewClient())
                web.setWebChromeClient(WebChromeClient())

                column.addView(web, LinearLayout.LayoutParams(-1, 0, 1.0))
                frame.addView(column, FrameLayout.LayoutParams(-1, -1))

                listener = CloseListener()
                close_btn.setOnClickListener(listener)
                activity.addContentView(frame, LayoutParams(-1, -1))
                app._android_webview = web
                app._android_webview_frame = frame
                app._android_webview_listener = listener
                web.loadUrl(target_url)
            except Exception as exc:
                print('WEBVIEW_ERR:', exc)

        show()

    def _close_in_app_webview(self):
        try:
            from android.runnable import run_on_ui_thread
            @run_on_ui_thread
            def close():
                frame = getattr(self, '_android_webview_frame', None)
                if frame is not None:
                    parent = frame.getParent()
                    if parent is not None:
                        parent.removeView(frame)
                self._android_webview = None
                self._android_webview_frame = None
            close()
        except Exception:
            pass

    def build(self):
        configure_storage(self)
        cfg = load_cfg()
        self.current_lang = cfg.get("lang", "ar")
        ensure_files()
        threading.Thread(target=run_server, daemon=True).start()
        self._acquire_wake_lock()

        self.sm = ScreenManager(transition=FadeTransition(duration=0.18))
        self.sm.add_widget(RoleSelectScreen(self, name="role_select"))
        self.sm.add_widget(StudentScreen(self, name="student"))
        self.sm.add_widget(AdminHubScreen(self, name="admin_hub"))
        self.sm.add_widget(SettingsScreen(self, name="settings"))
        self.sm.add_widget(ContactScreen(self, name="contact"))
        self.sm.current = "role_select"
        return self.sm

    def on_stop(self):
        self._close_in_app_webview()
        try:
            if getattr(self, "_wake_lock", None) and self._wake_lock.isHeld():
                self._wake_lock.release()
        except Exception:
            pass

if __name__ == '__main__':
    MainApp().run()
