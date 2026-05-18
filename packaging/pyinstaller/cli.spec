# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_cli.py'],
    pathex=['src', 'vendor/vtflib_wrapper/src'],
    binaries=[],
    datas=[
        ('src/arc9_sticker_pack_maker', 'arc9_sticker_pack_maker'),
        ('vendor/vtflib_wrapper/src/vtflib', 'vendor/vtflib_wrapper/src/vtflib'),
        ('vendor/libs', 'vendor/libs'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ARC9StickerPackMaker++_CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\logo.ico'],
)
