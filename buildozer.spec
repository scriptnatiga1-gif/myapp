[app]
title = حضور - نظام الحضور الذكي
package.name = hodour
package.domain = org.mhti
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt,ttf
source.include_patterns = *.ttf,icon.png,presplash.png
source.exclude_patterns = venv,bin,.buildozer,.git,__pycache__,*.log
version = 2.3.0
requirements = python3,kivy==2.3.1,Pillow,qrcode,arabic-reshaper,python-bidi,pyjnius,android
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
p4a.bootstrap = sdl2
p4a.fork = kivy
p4a.branch = master
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
