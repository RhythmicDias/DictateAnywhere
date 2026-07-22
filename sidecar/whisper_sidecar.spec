# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# We need to include the dictateanywhere source folder so it can import it
src_dir = os.path.abspath(os.path.join(SPECPATH, "..", "src"))
print(f"[Spec Build] src_dir is: {src_dir}")

datas = collect_data_files("faster_whisper") + collect_data_files("ctranslate2")
datas += collect_data_files("sounddevice")

binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("sounddevice")

# Collect NVIDIA DLLs from virtual environment
nvidia_binaries = []
try:
    import site
    prefixes = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        prefixes.append(site.getusersitepackages())
    prefixes.append(sys.prefix)
    
    for prefix in prefixes:
        paths_to_check = [
            os.path.join(prefix, "Lib", "site-packages", "nvidia"),
            os.path.join(prefix, "nvidia"),
        ]
        for nvidia_dir in paths_to_check:
            if os.path.exists(nvidia_dir):
                for root, _, files in os.walk(nvidia_dir):
                    for file in files:
                        if file.lower().endswith(".dll"):
                            full_path = os.path.join(root, file)
                            nvidia_binaries.append((full_path, "."))
                            print(f"[Spec Build] Collected DLL: {full_path}")
except Exception as e:
    print(f"[Spec Build] Warning: Failed to collect NVIDIA DLLs: {e}")

binaries += nvidia_binaries

a = Analysis(
    ['whisper_sidecar.py'],
    pathex=[src_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'dictateanywhere',
        'dictateanywhere.audio',
        'dictateanywhere.audio.capture',
        'dictateanywhere.audio.vad',
        'dictateanywhere.transcription',
        'dictateanywhere.transcription.local_engine',
        'dictateanywhere.transcription.cloud_engine',
        'dictateanywhere.transcription.sarvam_engine',
        'dictateanywhere.transcription.gemini_engine',
        'dictateanywhere.transcription.engine',
        'dictateanywhere.utils',
        'dictateanywhere.utils.config',
        'dictateanywhere.utils.secure_storage',
        'dictateanywhere.core',
        'dictateanywhere.core.punctuation',
        'dictateanywhere.core.corrections',
        'dictateanywhere.core.polish',
        'webrtcvad',
        'sounddevice',
        'numpy',
        'faster_whisper',
        'ctranslate2'
    ],
    hookspath=['hooks'],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='whisper_sidecar',
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
)
