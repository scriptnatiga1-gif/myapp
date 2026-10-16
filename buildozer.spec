[app]
title = Mansour Attendance
package.name = mansourattendance
package.domain = com.mansour.attendance
source.dir =.
source.include_exts = py,png,jpg,jpeg
version = 1.0
requirements = python3,kivy==2.3.0,qrcode,pillow,android
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2

[app:android]
p4a.fork = kivy
p4a.branch = master
p4a.bootstrap = sdl2
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.arch = armeabi-v7a
android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license_agreement = True