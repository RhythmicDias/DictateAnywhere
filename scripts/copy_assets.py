import os
import shutil
from PIL import Image

def main():
    brain_dir = r"C:\Users\diass\.gemini\antigravity-ide\brain\3be2908f-3de7-4440-b763-16ec5924489c"
    src_icon = os.path.join(brain_dir, "dictate_anywhere_icon_1780298098399.png")
    src_logo = os.path.join(brain_dir, "dictate_anywhere_logo_1780298118263.png")

    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(project_dir, "assets")
    
    os.makedirs(assets_dir, exist_ok=True)
    
    dest_icon = os.path.join(assets_dir, "icon.png")
    dest_logo = os.path.join(assets_dir, "logo.png")
    dest_ico = os.path.join(assets_dir, "icon.ico")

    # Copy files
    print(f"Copying {src_icon} -> {dest_icon}")
    shutil.copy2(src_icon, dest_icon)

    print(f"Copying {src_logo} -> {dest_logo}")
    shutil.copy2(src_logo, dest_logo)

    # Convert to ICO
    print(f"Converting {dest_icon} -> {dest_ico}")
    img = Image.open(dest_icon)
    
    # Standard ICO sizes: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(dest_ico, format='ICO', sizes=sizes)
    print("Done copying and converting assets successfully!")

if __name__ == "__main__":
    main()
