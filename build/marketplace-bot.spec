# -*- mode: python ; coding: utf-8 -*-
# Spec do PyInstaller — modo onedir.
#
# Build (na raiz do repositório):
#   pyinstaller build/marketplace-bot.spec --noconfirm
#
# Saída: dist/MarketplaceBot/MarketplaceBot.exe
#
# Os navegadores NÃO são empacotados: o bot usa o Google Chrome do sistema
# (channel="chrome"); o instalador garante a presença dele via
# "MarketplaceBot.exe --install-browser".
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(SPECPATH)  # SPECPATH = pasta build/
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(ROOT, "assets")
ICON = os.path.join(ASSETS, "icon.ico")

# O Playwright precisa do driver Node (playwright/driver) dentro do bundle
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")

a = Analysis(
    [os.path.join(SRC, "main.py")],
    pathex=[SRC],
    binaries=pw_binaries,
    datas=pw_datas + [(ASSETS, "assets")],
    hiddenimports=pw_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarketplaceBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # GUI Tkinter — sem janela de console; o processo do bot é um filho
    # deste mesmo exe (--run-bot) com stdout capturado pela interface
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MarketplaceBot",
)
