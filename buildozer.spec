[app]
title = Hidratacion de Ranita
package.name = hidratacionranita
package.domain = org.ranita
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,mp3,wav,ttf,json
version = 1.4
requirements = python3,kivy==2.2.1
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1

[app:android]
android.api = 31
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.permissions = VIBRATE,WAKE_LOCK
android.accept_sdk_license = True
p4a.bootstrap = sdl2
