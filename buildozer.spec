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
android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
