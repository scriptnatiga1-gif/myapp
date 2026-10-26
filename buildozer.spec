[app]

# (str) Title of your application
title = حضور - نظام الحضور الذكي

# (str) Package name
package.name = hodour

# (str) Package domain (needed for android packaging)
package.domain = org.mhti

# (str) Source dir
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,json,txt,ttf

# (list) List of inclusions using pattern matching
source.include_patterns = *.ttf,icon.png,presplash.png

# (str) Application version
version = 1.4

# (list) Application requirements - اهم سطر
requirements = python3,kivy==2.3.1,flask,qrcode,pillow,arabic-reshaper,python-bidi

# (list) Permissions
android.permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,VIBRATE

# (list) Features and request permissions
android.request_permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE

# (str) Icon of the application
icon.filename = %(source.dir)s/icon.png

# (str) Presplash background image
presplash.filename = %(source.dir)s/presplash.png

# (str) Presplash background color
presplash.color = #1a1a2e

# (int) Target Android API
android.api = 33

# (int) Minimum API
android.minapi = 21

# (int) Android NDK version
android.ndk = 25b

# (str) Android SDK version
android.sdk = 33

# (str) Android Build Tools version - ده اللي بيحل ايرور Aidl
android.build_tools_version = 33.0.2

# (list) Android archs to build for
android.archs = arm64-v8a

# (str) Bootstrap
p4a.bootstrap = sdl2

# (str) python-for-android fork and branch - دول اللي بيحلوا ايرور AAB
p4a.fork = kivy
p4a.branch = master

# (bool) Accept SDK license
android.accept_sdk_license_agreement = True

# (str) Fullscreen mode
fullscreen = 0

# (string) Orientation
orientation = portrait

[buildozer]

# (int) Log level
log_level = 1

# (int) Display warning if buildozer is run as root
warn_on_root = 1
