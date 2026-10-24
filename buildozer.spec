[app]

title = Attendance App
package.name = attendanceapp
package.domain = org.mhti
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt,ttf
source.include_patterns = *.ttf
version = 2.3.0
requirements = python3,kivy==2.3.1,arabic_reshaper,python-bidi,jnius
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
p4a.branch = master
p4a.bootstrap = sdl2
android.accept_sdk_license_agreement = True
fullscreen = 0
orientation = portrait

[buildozer]
log_level = 2
warn_on_root = 1
