# scripts/build_sidecar.py
import os
import shutil
import subprocess
import sys

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sidecar_spec = os.path.join(root_dir, "sidecar", "whisper_sidecar.spec")
    
    print("--- 1. Building Python Sidecar with PyInstaller ---")
    
    py_executable = sys.executable
    venv_py = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_py):
        py_executable = venv_py
        print(f"Using project virtual environment Python: {py_executable}")
    
    # Auto-install PyInstaller if not found
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found in virtual environment. Installing PyInstaller...")
        try:
            subprocess.run([py_executable, "-m", "pip", "install", "pyinstaller"], check=True)
        except subprocess.CalledProcessError:
            print("Error: Failed to install PyInstaller automatically.")
            print("Please run: pip install -r requirements-dev.txt")
            sys.exit(1)

    # Execute PyInstaller
    cmd = [
        py_executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--workpath", os.path.join(root_dir, "build_pyinstaller"),
        "--distpath", os.path.join(root_dir, "dist"),
        sidecar_spec
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=os.path.join(root_dir, "sidecar"))
    if result.returncode != 0:
        print("Error: PyInstaller build failed.")
        sys.exit(1)
        
    print("\n--- 2. Setting up Tauri Sidecar Binary ---")
    # Target path: src-tauri/binaries/whisper_sidecar-x86_64-pc-windows-msvc.exe
    binaries_dir = os.path.join(root_dir, "src-tauri", "binaries")
    os.makedirs(binaries_dir, exist_ok=True)
    
    src_exe = os.path.join(root_dir, "dist", "whisper_sidecar.exe")
    target_exe = os.path.join(binaries_dir, "whisper_sidecar-x86_64-pc-windows-msvc.exe")
    
    print(f"Copying {src_exe} -> {target_exe}")
    shutil.copy2(src_exe, target_exe)
    print("Sidecar binary successfully prepared for Tauri dev/build!")

if __name__ == "__main__":
    main()
