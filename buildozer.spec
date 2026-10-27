[app]
title = حضور - نظام الحضور الذكي
package.name = hodour
package.domain = org.mhti

source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt,ttf
source.include_patterns = *.ttf,icon.png,presplash.png
source.exclude_patterns = venv,*.log,bin,.buildozer,.git,__pycache__

version = 2.3.0

# شيلت flask - لو محتاجه للسيرفر خليه بره ال APK
requirements = python3,kivy==2.3.1,Pillow,qrcode,arabic-reshaper,python-bidi

# صلاحيات متوافقة مع اندرويد 13
android.permissions = INTERNET,ACCESS_NETWORK_STATE,CAMERA,VIBRATE,WAKE_LOCK

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #1a1a2e

android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license_agreement = True

android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = False

p4a.branch = master
p4a.bootstrap = sdl2
p4a.fork = kivy
# مهم عشان المكتبات اللي ملهاش وصفة
p4a.whitelist = 
p4a.local_recipes = 

orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
