[app]

title = Attendance App
package.name = attendanceapp
package.domain = org.mhti

source.dir = .
source.include_exts = py,html,css,js,png,jpg,json,txt

version = 2.3.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK

# استخدام إصدارات مستقرة ومدعومة بالكامل لتجنب مشاكل البناء
android.api = 33
android.minapi = 21
android.ndk = 25b

android.archs = arm64-v8a,armeabi-v7a

android.accept_sdk_license = True
android.skip_update = False

p4a.branch = master

[buildozer]

log_level = 2
warn_on_root = 1
