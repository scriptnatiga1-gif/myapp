[app]

# (str) Title of your application
title = Attendance App

# (str) Package name
package.name = attendanceapp

# (str) Package domain (needed for android packaging)
package.domain = org.mhti

# (str) Source files where the *.py files live
source.dir = .

# (list) Source files to include (let it empty to include all files)
source.include_exts = py,png,jpg,jpeg,json,txt

# (list) Application version
version = 2.3.0

# (list) Application requirements (تمت إضافة مكتبات دعم اللغة العربية لتجنب ظهور المربعات)
requirements = python3,kivy==2.3.1,arabic_reshaper,python-bidi

# (list) List of permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (int) Android NDK version to use
android.ndk = 25b

# (int) Android SDK version to use
android.sdk = 33

# (list) Android archs to build for, can be: arm64-v8a, armeabi-v7a, x86, x86_64
android.archs = arm64-v8a

# (str) python-for-android branch to use
p4a.branch = master

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

# (str) Path to build artifact storage, absolute or relative to spec file
#bin_dir = ./bin

# (str) Path to build output (default is ./.buildozer)
#build_dir = ./.buildozer
