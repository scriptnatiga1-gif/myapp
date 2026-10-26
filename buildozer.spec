[app]

title = حضور - نظام الحضور الذكي
package.name = hodour
package.domain = org.mhti

source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt,ttf
source.include_patterns = *.ttf,icon.png,presplash.png

version = 1.4

requirements = python3,kivy==2.3.1,flask,qrcode,pillow,arabic-reshaper,python-bidi

android.permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,VIBRATE
android.request_permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #1a1a2e

android.api = 33
android.minapi = 21
android.ndk = 25b
android.build_tools_version = 37.0.0
android.archs = arm64-v8a
android.accept_sdk_license_agreement = True

p4a.bootstrap = sdl2
p4a.fork = kivy
p4a.branch = master

fullscreen = 0
orientation = portrait

[buildozer]

log_level = 1
warn_on_root = 1
