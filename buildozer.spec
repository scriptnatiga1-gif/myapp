[app]

# (str) Title of your application
title = Attendance App

# (str) Package name
package.name = attendanceapp

# (str) Package domain (needed for android packaging)
package.domain = org.mhti

# (str) Source files where the let's go (relative to directory of buildozer.spec)
source.dir = .

# (list) Source files to include (let's specify extensions)
source.include_exts = py,png,jpg,json,txt

# (str) Application versioning
version = 2.3.0

# (list) Application requirements
# تأكد من تضمين الحزم الضرورية لعمل جافا وجنيوس وسيرفر بايثون
requirements = python3,kivy,pyjnius,android

# (str) Custom source folders for requirements
#requirements.source.kivy = ../../../kivy

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (list) Architectural build targets
android.archs = arm64-v8a,armeabi-v7a

# (bool) Indicate whether the application should be fullscreen or not
fullscreen = 0

# (string) Presplash background color
#presplash.color = #FFFFFF

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
