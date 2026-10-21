[app]

# (str) Title of your application
title = Attendance App

# (str) Package name
package.name = attendanceapp

# (str) Package domain (needed for android packaging)
package.domain = org.mhti

# (str) Source files where the let's go
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,json,txt

# (str) Application versioning
version = 2.3.0

# (list) Application requirements
requirements = python3,kivy

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (list) Architectural build targets
android.archs = arm64-v8a,armeabi-v7a

# (bool) Indicate whether the application should be fullscreen or not
fullscreen = 0

# (str) Icon of the application - ده سطر اللوجو اللي ظبطتهولك
icon = logo.jpg

# (str) Presplash background color
#presplash.color = #FFFFFF

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Supported orientation
#orientation = portrait

# (bool) Skip update check
#buildozer.check_application_requirements = True
