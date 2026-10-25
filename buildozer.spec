[app]

# (str) Title of your application
title = حضور - نظام الحضور الذكي

# (str) Package name
package.name = hodour

# (str) Package domain (needed for android packaging)
package.domain = org.mhti

# (str) Source files where the *.py files live
source.dir = .

# (list) Source files to include (let it empty to include all files)
source.include_exts = py,png,jpg,jpeg,json,txt,ttf

# (list) List of inclusions using pattern matching
source.include_patterns = *.ttf,icon.png,presplash.png

# (list) Application version
version = 1.4

# (list) Application requirements (مكتبات بايثون الأساسية وتصميم الواجهة ودعم اللغة العربية)
requirements = python3,kivy==2.3.0,flask,qrcode,pillow,arabic-reshaper,python-bidi,p4a
# (list) Permissions
android.permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,VIBRATE

# (list) Features and request permissions
android.request_permissions = CAMERA,INTERNET,ACCESS_NETWORK_STATE

# (str) Icon of the application
icon.filename = %(source.dir)s/icon.png

# (str) Presplash background image of the application
presplash.filename = %(source.dir)s/presplash.png

# (str) Presplash background color
presplash.color = #1a1a2e

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (int) Android NDK version to use
android.ndk = 25b

# (list) Android archs to build for
android.archs = arm64-v8a

# (str) Bootstrap to use for android build
p4a.bootstrap = sdl2

# (bool) Indicate whether the application should accept the Android SDK license
android.accept_sdk_license_agreement = True

# (str) Fullscreen mode
fullscreen = 0

# (string) Orientation
orientation = portrait


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
