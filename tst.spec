# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 파일. macOS .app 번들을 생성한다.

빌드 방법:
    uv run pyinstaller tst.spec

결과물:
    dist/tst.app
"""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# MLX 관련 패키지는 네이티브 확장 + 데이터 파일이 있어서 전체 수집 필요
mlx_datas, mlx_binaries, mlx_hiddenimports = collect_all("mlx")
mlx_audio_datas, mlx_audio_binaries, mlx_audio_hiddenimports = collect_all("mlx_audio")
mlx_lm_datas, mlx_lm_binaries, mlx_lm_hiddenimports = collect_all("mlx_lm")

a = Analysis(
    ["src/tst/__main__.py"],
    pathex=[],
    binaries=mlx_binaries + mlx_audio_binaries + mlx_lm_binaries,
    datas=mlx_datas + mlx_audio_datas + mlx_lm_datas + [
        ("src/tst/icons", "tst/icons"),
    ],
    hiddenimports=[
        "sounddevice",
        "numpy",
        "Quartz",
        "AppKit",
        "Foundation",
    ]
    + mlx_hiddenimports
    + mlx_audio_hiddenimports
    + mlx_lm_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_rth_mlx.py"],
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
    name="tst",
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
    name="tst",
)

app = BUNDLE(
    coll,
    name="tst.app",
    icon="tst.icns",
    bundle_identifier="com.cmygray.tst",
    info_plist={
        "CFBundleName": "Tst",
        "CFBundleDisplayName": "Tst",
        "CFBundleVersion": "0.6.1",
        "CFBundleShortVersionString": "0.6.1",
        "NSMicrophoneUsageDescription": "Tst는 음성인식을 위해 마이크 접근 권한이 필요합니다.",
        "LSUIElement": True,  # Dock에 아이콘을 표시하지 않음 (백그라운드 앱)
    },
)
