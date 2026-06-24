[app]
title = Hidratacion de Ranita
package.name = hidratacionranita
package.domain = org.ranita

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,mp3,wav,ttf,json

version = 1.0

requirements = python3,kivy==2.3.0,plyer,pyjnius

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
# Android 13 = API 33 (lo que corre One UI 5.1)
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a

android.permissions = VIBRATE,WAKE_LOCK,POST_NOTIFICATIONS

# Acepta automáticamente las licencias del SDK en la primera compilación
android.accept_sdk_license = True

p4a.bootstrap = sdl2
