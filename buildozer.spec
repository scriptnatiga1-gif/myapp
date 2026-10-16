[app]
title = Mansour Attendance
package.name = mansourattendance
package.domain = com.mansour.attendance
source.dir =.
source.include_exts = py,png,jpg
version = 1.0
requirements = python3,kivy==2.3.0,qrcode,pillow
orientation = portrait

[buildozer]
log_level = 2

[app:android]
permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license_agreement = True
