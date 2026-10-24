[app]

# (str) Title of your application
title = Attendance App

# (str) Package name
package.name = attendanceapp

# (str) Package domain
package.domain = org.mhti

# (str) Source files
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,json,txt

# (str) Application versioning
version = 2.3.0

# (list) Application requirements
requirements = python3,kivy==2.3.1

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK

# (int) Target Android API
android.api = 33

# (int) Minimum API
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (str) Android SDK version
android.sdk = 33

# (list) Architectural build targets
android.archs = arm64-v8a,armeabi-v7a

# (str) python-for-android branch
p4a.branch = master
p4a.bootstrap = sdl2

# (bool) Accept SDK license
android.accept_sdk_license_agreement = True

# (bool) Fullscreen
fullscreen = 0

# (str) Icon
icon.filename = %(source.dir)s/logo.jpg

# (str) Orientation
orientation = portrait

[buildozer]

# (int) Log level
log_level = 2

# (int) Warn on root
warn_on_root = 1
