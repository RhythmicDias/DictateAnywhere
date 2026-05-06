from PIL import Image, ImageDraw
import os

def clean_to_circle(path):
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    
    # Create a circular mask
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    # Draw a white circle on the black mask
    draw.ellipse((0, 0, width, height), fill=255)
    
    # Apply the mask to the alpha channel
    result = img.copy()
    result.putalpha(mask)
    
    result.save(path, "PNG")
    print(f"Cleaned {path} to circular mask")

# Target icons
icons_dir = r"d:\PythonProjects\DictateAnywhere\assets\icons"
for f in ["mic_idle.png", "mic_active.png", "mic_loading.png"]:
    path = os.path.join(icons_dir, f)
    if os.path.exists(path):
        clean_to_circle(path)
