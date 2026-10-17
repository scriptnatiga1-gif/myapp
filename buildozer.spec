[app]
title = Mansour Attendance Pro
package.name = mansourattendance
package.domain = org.mansour.app
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt
version = 2.0
requirements = python3,kivy==2.3.0,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,ACCESS_FINE_LOCATION
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.build_tools_version = 33.0.2
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license_agreement = True
p4a.bootstrap = sdl2
p4a.branch = develop
p4a.sdk_dir = /opt/android
android.wakelock = True

[buildozer]
log_level = 2
warn_on_root = 1
