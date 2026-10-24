import os
import json
import socket
import threading
from datetime import datetime

import kivy
kivy.require('2.3.0')

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.switch import Switch
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.animation import Animation
from kivy.core.text import LabelBase

# مكتبات معالجة اللغة العربية و توليد QR
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC = True
except ImportError:
    HAS_ARABIC = False

try:
    import qrcode
    from io import BytesIO
    from kivy.core.image import Image as CoreImage
    HAS_QR = True
except ImportError:
    HAS_QR = False

try:
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

# تسجيل الخط العربي إن وجد
FONT_PATH = os.path.join(os.path.dirname(__file__), 'Amiri-Regular.ttf')
if os.path.exists(FONT_PATH):
    LabelBase.register(name='AmiriFont', fn_regular=FONT_PATH)
    DEFAULT_FONT = 'AmiriFont'
else:
    DEFAULT_FONT = None

def fix_arabic(text):
    """دالة تحسين وتشكيل النصوص العربية لعرضها بوضوح وبدون مربعات"""
    if not text:
        return ""
    if HAS_ARABIC:
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text
    return text

def get_real_ip():
    """دالة جلب الـ IP الحقيقي الصحيح للشبكة المحسنة"""
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

# إعداد ملفات الحفظ
DATA_FILE = os.path.join(os.path.dirname(__file__), 'attendance_records.json')

def load_records():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_record(name, student_id, board="1", source="Native App"):
    records = load_records()
    record = {
        "id": student_id,
        "name": name,
        "board": board,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source
    }
    records.append(record)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return True

# --- خادم Flask الخلفي للتكامل المباشر ---
server_thread = None
is_server_running = False

if HAS_FLASK:
    flask_app = Flask(__name__)

    @flask_app.route('/api/register', methods=['POST'])
    def api_register():
        data = request.json or {}
        name = data.get('name', '')
        student_id = data.get('student_id', '')
        board = data.get('board', '1')
        if name and student_id:
            save_record(name, student_id, board, source="Web Student")
            return jsonify({"status": "success", "message": "تم تسجيل الحضور بنجاح"}), 200
        return jsonify({"status": "error", "message": "بيانات غير مكتملة"}), 400

    @flask_app.route('/api/records', methods=['GET'])
    def api_records():
        return jsonify(load_records()), 200

def start_flask_server():
    global is_server_running
    if not is_server_running and HAS_FLASK:
        def run():
            flask_app.run(host='0.0.0.0', port=8080, threaded=True)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        is_server_running = True

# --- مكونات الواجهة المخصصة (Material Design UI Components) ---

class GradientWidget(BoxLayout):
    """عنصر خلفية متدرجة عصرية"""
    def __init__(self, color1=(0.1, 0.1, 0.18, 1), color2=(0.06, 0.06, 0.1, 1), **kwargs):
        super().__init__(**kwargs)
        self.color1 = color1
        self.color2 = color2
        with self.canvas.before:
            Color(*self.color1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update, pos=self._update)

    def _update(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

class CardButton(Button):
    """بطاقات عصرية بتصميم متدرج أزرق/بنفسجي لـ Material 3"""
    def __init__(self, bg_color1=(0.22, 0.48, 1.0, 1), bg_color2=(0.54, 0.36, 0.96, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.c1 = bg_color1
        if DEFAULT_FONT:
            self.font_name = DEFAULT_FONT
        self.font_size = '18sp'
        self.bold = True
        with self.canvas.before:
            Color(*self.c1)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[18])
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

class CustomLabel(Label):
    """Label مخصص يدعم الخط العربي افتراضياً"""
    def __init__(self, text="", **kwargs):
        if DEFAULT_FONT:
            kwargs['font_name'] = DEFAULT_FONT
        super().__init__(text=fix_arabic(text), **kwargs)

    def set_ar_text(self, text):
        self.text = fix_arabic(text)

class CustomTextInput(TextInput):
    def __init__(self, **kwargs):
        if DEFAULT_FONT:
            kwargs['font_name'] = DEFAULT_FONT
        super().__init__(**kwargs)
        self.padding = [12, 12, 12, 12]
        self.background_normal = ''
        self.background_color = (0.95, 0.96, 0.98, 1)

class TopAppBar(BoxLayout):
    """شريط علوي متكرر يحتوي على أيقونات الإعدادات والتواصل"""
    def __init__(self, title_text="حضور", **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 56
        self.padding = [12, 8, 12, 8]
        self.spacing = 8

        with self.canvas.before:
            Color(0.1, 0.1, 0.18, 0.95)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update, pos=self._update)

        lbl = CustomLabel(text=title_text, font_size='20sp', bold=True, size_hint_x=0.6, halign='right')
        lbl.bind(size=lbl.setter('text_size'))
        
        btn_contact = Button(text=fix_arabic("اتصل بنا"), size_hint_x=0.2, font_name=DEFAULT_FONT if DEFAULT_FONT else None)
        btn_settings = Button(text=fix_arabic("الإعدادات"), size_hint_x=0.2, font_name=DEFAULT_FONT if DEFAULT_FONT else None)

        btn_contact.bind(on_press=self.go_contact)
        btn_settings.bind(on_press=self.go_settings)

        self.add_widget(btn_contact)
        self.add_widget(btn_settings)
        self.add_widget(lbl)

    def _update(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def go_contact(self, instance):
        App.get_running_app().sm.current = 'contact'

    def go_settings(self, instance):
        App.get_running_app().sm.current = 'settings'

# --- الشاشات (Screens) ---

class SplashScreen(Screen):
    """شاشة الترحيب مع أنيميشن اللوجو والتمهيد"""
    def on_enter(self, *args):
        self.clear_widgets()
        layout = FloatLayout()
        
        with layout.canvas.before:
            Color(0.1, 0.1, 0.18, 1)
            self.rect = Rectangle(size=layout.size, pos=layout.pos)
        layout.bind(size=lambda inst, val: setattr(self.rect, 'size', inst.size))

        self.logo = CustomLabel(
            text="🎓 حضور",
            font_size='38sp',
            bold=True,
            pos_hint={'center_x': 0.5, 'center_y': 0.55},
            opacity=0
        )
        self.sub = CustomLabel(
            text="مرحبا بكم - نظام الحضور الذكي",
            font_size='18sp',
            pos_hint={'center_x': 0.5, 'center_y': 0.42},
            opacity=0
        )

        layout.add_widget(self.logo)
        layout.add_widget(self.sub)
        self.add_widget(layout)

        # أنيميشن ظهور اللوجو والانتفال بعد 3 ثوانٍ
        anim = Animation(opacity=1, font_size=46, duration=1.5) + Animation(opacity=1, duration=1.5)
        anim.start(self.logo)
        
        anim_sub = Animation(opacity=1, duration=2)
        anim_sub.start(self.sub)

        Clock.schedule_once(self.go_next, 3.5)

    def go_next(self, dt):
        self.manager.current = 'role'

class RoleScreen(Screen):
    """شاشة اختيار الدور (دكتور / طالب)"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical')
        layout.add_widget(TopAppBar(title_text="حضور - اختيار الدور"))

        content = BoxLayout(orientation='vertical', padding=24, spacing=20)
        
        lbl = CustomLabel(text="اختر نوع الدخول للاستمرار", font_size='22sp', bold=True, size_hint_y=0.2)
        
        btn_admin = CardButton(
            text="أنا دكتور / أدمن 🔐",
            bg_color1=(0.22, 0.48, 1.0, 1),
            size_hint_y=0.35
        )
        btn_student = CardButton(
            text="أنا طالب 👨‍🎓",
            bg_color1=(0.54, 0.36, 0.96, 1),
            size_hint_y=0.35
        )

        btn_admin.bind(on_press=self.check_admin_login)
        btn_student.bind(on_press=self.go_student)

        content.add_widget(lbl)
        content.add_widget(btn_admin)
        content.add_widget(btn_student)
        layout.add_widget(content)
        self.add_widget(layout)

    def check_admin_login(self, instance):
        # Popup طلب كلمة سر الأدمن
        box = BoxLayout(orientation='vertical', padding=12, spacing=10)
        inp = CustomTextInput(hint_text="كلمة السر", password=True, size_hint_y=0.4)
        btn = CardButton(text="دخول", size_hint_y=0.4)
        box.add_widget(inp)
        box.add_widget(btn)

        popup = Popup(title=fix_arabic("تسجيل دخول الأدمن"), content=box, size_hint=(0.85, 0.35))

        def validate(btn_inst):
            if inp.text.strip() == "mansour2026" or inp.text.strip() == "admin":
                popup.dismiss()
                start_flask_server()
                self.manager.current = 'admin'
            else:
                inp.text = ""
                inp.hint_text = fix_arabic("كلمة سر خاطئة!")

        btn.bind(on_press=validate)
        popup.open()

    def go_student(self, instance):
        self.manager.current = 'student'

class AdminScreen(Screen):
    """شاشة لوحة تحكم الدكتور/الأدمن"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical')
        self.layout.add_widget(TopAppBar(title_text="لوحة تحكم المحاضرة"))

        self.body = BoxLayout(orientation='vertical', padding=16, spacing=12)
        
        # كارت عرض IP الشبكة
        self.ip = get_real_ip()
        self.ip_card = BoxLayout(orientation='vertical', padding=10, size_hint_y=0.18)
        with self.ip_card.canvas.before:
            Color(0.92, 0.95, 1.0, 1)
            self.ip_rect = RoundedRectangle(size=self.ip_card.size, pos=self.ip_card.pos, radius=[12])
        self.ip_card.bind(size=lambda inst, val: setattr(self.ip_rect, 'size', inst.size),
                          pos=lambda inst, val: setattr(self.ip_rect, 'pos', inst.pos))

        self.lbl_ip = CustomLabel(text=f"عنوان الـ IP المحلي: http://{self.ip}:8080", color=(0.1, 0.2, 0.4, 1), bold=True)
        self.ip_card.add_widget(self.lbl_ip)

        # عرض QR Code
        self.qr_box = Image(size_hint_y=0.4)
        self.generate_qr()

        # أزرار الإجراءات
        btn_view = CardButton(text="عرض كشف الحضور (جدول) 📊", size_hint_y=0.15)
        btn_back = CardButton(text="تسجيل الخروج", bg_color1=(0.85, 0.2, 0.2, 1), size_hint_y=0.15)

        btn_view.bind(on_press=self.show_attendance_table)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'role'))

        self.body.add_widget(self.ip_card)
        self.body.add_widget(self.qr_box)
        self.body.add_widget(btn_view)
        self.body.add_widget(btn_back)

        self.layout.add_widget(self.body)
        self.add_widget(self.layout)

    def generate_qr(self):
        url = f"http://{self.ip}:8080"
        if HAS_QR:
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            core_img = CoreImage(buffer, ext='png')
            self.qr_box.texture = core_img.texture

    def show_attendance_table(self, instance):
        records = load_records()
        content = BoxLayout(orientation='vertical', padding=10, spacing=8)
        scroll = ScrollView()
        grid = GridLayout(cols=3, spacing=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # عناويني الجدول
        grid.add_widget(CustomLabel(text="الاسم", bold=True, size_hint_y=None, height=30))
        grid.add_widget(CustomLabel(text="رقم القومي/الكارنيه", bold=True, size_hint_y=None, height=30))
        grid.add_widget(CustomLabel(text="الوقت", bold=True, size_hint_y=None, height=30))

        for r in records:
            grid.add_widget(CustomLabel(text=r.get('name',''), size_hint_y=None, height=28))
            grid.add_widget(CustomLabel(text=r.get('id',''), size_hint_y=None, height=28))
            grid.add_widget(CustomLabel(text=r.get('time','').split(' ')[1] if ' ' in r.get('time','') else r.get('time',''), size_hint_y=None, height=28))

        scroll.add_widget(grid)
        content.add_widget(scroll)

        btn_close = Button(text=fix_arabic("إغلاق"), size_hint_y=0.15, font_name=DEFAULT_FONT if DEFAULT_FONT else None)
        popup = Popup(title=fix_arabic("كشف الحضور المسجل"), content=content, size_hint=(0.9, 0.8))
        btn_close.bind(on_press=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()

class StudentScreen(Screen):
    """شاشة الطالب - Kivy Native بالكامل"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical')
        layout.add_widget(TopAppBar(title_text="تسجيل حضور الطالب"))

        content = BoxLayout(orientation='vertical', padding=20, spacing=12)

        self.inp_name = CustomTextInput(hint_text=fix_arabic("اسم الطالب رباعي"), multiline=False, size_hint_y=0.15)
        self.inp_id = CustomTextInput(hint_text=fix_arabic("الرقم القومي / رقم الكارنيه"), multiline=False, size_hint_y=0.15)
        self.inp_board = CustomTextInput(hint_text=fix_arabic("رقم السبورة / المجموعة"), multiline=False, size_hint_y=0.15)

        btn_submit = CardButton(text="تسجيل الحضور الان 📝", bg_color1=(0.1, 0.65, 0.3, 1), size_hint_y=0.18)
        btn_back = CardButton(text="رجوع", bg_color1=(0.5, 0.5, 0.5, 1), size_hint_y=0.15)

        self.lbl_msg = CustomLabel(text="", size_hint_y=0.15)

        btn_submit.bind(on_press=self.submit)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'role'))

        content.add_widget(self.inp_name)
        content.add_widget(self.inp_id)
        content.add_widget(self.inp_board)
        content.add_widget(btn_submit)
        content.add_widget(self.lbl_msg)
        content.add_widget(btn_back)

        layout.add_widget(content)
        self.add_widget(layout)

    def submit(self, instance):
        name = self.inp_name.text.strip()
        sid = self.inp_id.text.strip()
        board = self.inp_board.text.strip() or "1"

        if name and sid:
            save_record(name, sid, board, source="Native Student Screen")
            self.lbl_msg.set_ar_text("✅ تم تسجيل حضورك بنجاح!")
            self.inp_name.text = ""
            self.inp_id.text = ""
            self.inp_board.text = ""
        else:
            self.lbl_msg.set_ar_text("⚠️ يرجى إدخال كافة البيانات بشكل صحيح")

class SettingsScreen(Screen):
    """شاشة الإعدادات"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical')
        layout.add_widget(TopAppBar(title_text="الإعدادات"))

        content = BoxLayout(orientation='vertical', padding=20, spacing=16)

        # خيار اللغة
        row1 = BoxLayout(size_hint_y=0.15)
        row1.add_widget(CustomLabel(text="اللغة العربية / English"))
        row1.add_widget(Switch(active=True))

        # رقم الإصدار
        row2 = BoxLayout(size_hint_y=0.15)
        row2.add_widget(CustomLabel(text="رقم الإصدار"))
        row2.add_widget(CustomLabel(text="1.4"))

        # الوضع الليلي
        row3 = BoxLayout(size_hint_y=0.15)
        row3.add_widget(CustomLabel(text="تفعيل الوضع الليلي"))
        row3.add_widget(Switch(active=True))

        btn_back = CardButton(text="رجوع", size_hint_y=0.15)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'role'))

        content.add_widget(row1)
        content.add_widget(row2)
        content.add_widget(row3)
        content.add_widget(Widget(size_hint_y=0.25))
        content.add_widget(btn_back)

        layout.add_widget(content)
        self.add_widget(layout)

class ContactScreen(Screen):
    """شاشة اتصل بنا بها أزرار السوشيال ميديا بألوانها الرسمية"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical')
        layout.add_widget(TopAppBar(title_text="اتصل بنا"))

        content = BoxLayout(orientation='vertical', padding=20, spacing=14)

        grid = GridLayout(cols=2, spacing=14, size_hint_y=0.7)

        btn_fb = CardButton(text="Facebook", bg_color1=(0.09, 0.46, 0.95, 1))
        btn_wa = CardButton(text="WhatsApp", bg_color1=(0.14, 0.78, 0.35, 1))
        btn_tg = CardButton(text="Telegram", bg_color1=(0.16, 0.62, 0.86, 1))
        btn_ig = CardButton(text="Instagram", bg_color1=(0.88, 0.19, 0.43, 1))

        grid.add_widget(btn_fb)
        grid.add_widget(btn_wa)
        grid.add_widget(btn_tg)
        grid.add_widget(btn_ig)

        btn_back = CardButton(text="رجوع", size_hint_y=0.15)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'role'))

        content.add_widget(grid)
        content.add_widget(btn_back)

        layout.add_widget(content)
        self.add_widget(layout)

# --- التطبيق الرئيسي ---

class HodourApp(App):
    def build(self):
        self.title = "حضور - نظام الحضور الذكي"
        self.sm = ScreenManager(transition=FadeTransition(duration=0.25))
        
        self.sm.add_widget(SplashScreen(name='splash'))
        self.sm.add_widget(RoleScreen(name='role'))
        self.sm.add_widget(AdminScreen(name='admin'))
        self.sm.add_widget(StudentScreen(name='student'))
        self.sm.add_widget(SettingsScreen(name='settings'))
        self.sm.add_widget(ContactScreen(name='contact'))

        return self.sm

if __name__ == '__main__':
    HodourApp().run()
