# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 파일. macOS .app 번들을 생성한다.

빌드 방법:
    uv run pyinstaller ttstt.spec

결과물:
    dist/ttstt.app
"""

block_cipher = None

a = Analysis(
    ["src/ttstt/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "mlx_audio",
        "mlx_audio.stt",
        "mlx_lm",
        "sounddevice",
        "numpy",
        "Quartz",
        "AppKit",
        "Foundation",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ttstt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 앱 (콘솔 창 없음)
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="ttstt",
)

app = BUNDLE(
    coll,
    name="ttstt.app",
    icon=None,  # TODO: 앱 아이콘 추가
    bundle_identifier="com.cmygray.ttstt",
    info_plist={
        "CFBundleName": "ttstt",
        "CFBundleDisplayName": "ttstt",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSMicrophoneUsageDescription": "ttstt는 음성인식을 위해 마이크 접근 권한이 필요합니다.",
        "LSUIElement": True,  # Dock에 아이콘을 표시하지 않음 (백그라운드 앱)
    },
)
