[app]

# (str) Title of your application
title = حضور - نظام الحضور الذكي

# (str) Package name
package.name = hodour

# (str) Package domain (needed for android packaging)
package.domain = org.mhti

# (str) Source files where the let's go (relative to directory of spec)
source.dir = .

# (list) Source files to include (let it empty to include all the files)
source.include_exts = py,png,jpg,jpeg,json,txt,ttf,kv

# (list) List of inclusions using pattern matching
source.include_patterns = *.ttf,icon.png,presplash.png,logo.*

# (list) Source files to exclude (let it empty to exclude none)
source.exclude_patterns = venv,bin,.buildozer,.git,__pycache__,*.log

# (str) Application versioning
version = 2.5.0

# (list) Application requirements
# تم إزالة تحديد الإصدار الدقيق لـ kivy لتجنب أخطاء البناء ووصفات p4a
requirements = python3,kivy,pillow,qrcode,arabic-reshaper,python-bidi,pyjnius,android,openssl,urllib3,certifi,idna,charset-normalizer

# (list) Custom source folders for python modules
# source.local_libs = 

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,CHANGE_NETWORK_STATE,CAMERA,VIBRATE,WAKE_LOCK

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 23

# (str) Android NDK version to use
android.ndk = 25b

# (str) Android SDK version to use
android.sdk = 33

# (bool) Indicate whether the screen should be bright or not
android.wakelock = True

# (str) Supported orientations
orientation = portrait

# (bool) Set the application to fullscreen
fullscreen = 0

# (string) Presplash image
presplash.filename = %(source.dir)s/presplash.png

# (string) Icon of the application
icon.filename = %(source.dir)s/icon.png

# (list) Supported architectures
android.archs = arm64-v8a,armeabi-v7a

# (bool) Cleartext traffic allowed (HTTP requests support)
android.allow_cleartext_traffic = True

# (str) python-for-android branch to use
p4a.branch = v2024.01.21

# (str) python-for-android fork to use
p4a.fork = kivy

# (str) Bootstrap to use for android builds
p4a.bootstrap = sdl2

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
