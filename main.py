# Bootstrap entry point: capture errors that happen while importing app_main.py,
# including failures before Kivy's App.build() can run.
import os
import sys
import runpy
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_NAME = 'hodour_startup_error.txt'
target_app_main = os.path.join(APP_DIR, 'app_main.py')

def _write_log(text):
    targets = []
    for env_key in ('ANDROID_PRIVATE', 'ANDROID_ARGUMENT', 'HOME'):
        base = os.environ.get(env_key)
        if base:
            targets.append(os.path.join(base, LOG_NAME))
    targets.append(os.path.join(APP_DIR, LOG_NAME))
    for path in targets:
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write('HODOUR STARTUP CRASH\n')
                f.write('Python: ' + sys.version + '\n')
                f.write('Executable: ' + sys.executable + '\n')
                f.write('Working directory: ' + os.getcwd() + '\n\n')
                f.write(text)
            break
        except Exception:
            pass
    try:
        from jnius import autoclass
        Log = autoclass('android.util.Log')
        Log.e('HodourStartup', text[-30000:])
    except Exception:
        pass

try:
    if os.path.exists(target_app_main):
        runpy.run_path(target_app_main, run_name='__main__')
    else:
        raise FileNotFoundError(f"تعذر العثور على ملف app_main.py في المسار: {target_app_main}")
except BaseException:
    details = traceback.format_exc()
    print('HODOUR STARTUP CRASH\n' + details, file=sys.stderr, flush=True)
    _write_log(details)
    # Try to leave a visible error screen when Kivy itself is importable.
    try:
        from kivy.app import App
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.scrollview import ScrollView
        class StartupErrorApp(App):
            def build(self):
                root = BoxLayout(orientation='vertical', padding=12, spacing=8)
                root.add_widget(Label(text='فشل بدء تطبيق الحضور. تأكد من وجود ملف app_main.py داخل حزمة APK.', size_hint_y=None, height='64dp'))
                scroll = ScrollView()
                label = Label(text=details, size_hint_y=None, halign='left', valign='top')
                label.bind(width=lambda inst, width: setattr(inst, 'text_size', (width, None)))
                label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1] + 20))
                scroll.add_widget(label)
                root.add_widget(scroll)
                return root
        StartupErrorApp().run()
    except BaseException:
        pass
    raise
