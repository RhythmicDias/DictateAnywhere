# Icons

Place your icon files here. DictateAnywhere expects:

| File       | Size     | Used for                          |
|------------|----------|-----------------------------------|
| `mic.ico`  | 256×256  | Windows taskbar / .exe icon       |
| `mic.png`  | 256×256  | Fallback / About dialog           |

## Generating icons

**Quick option — use a free online converter:**
1. Create or download a microphone SVG (e.g. from [heroicons.com](https://heroicons.com))
2. Convert to `.ico` at [icoconvert.com](https://icoconvert.com)

**From the command line (requires Pillow):**
```bash
pip install Pillow
python - <<'EOF'
from PIL import Image, ImageDraw

def make_mic_icon(path: str, size: int = 256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = "#4A90D9"
    draw.ellipse([4, 4, size-4, size-4], fill=c)
    # body
    bw, bh = size*0.25, size*0.40
    bx, by = (size-bw)/2, size*0.08
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=size//10, fill="white")
    img.save(path)

make_mic_icon("mic.png")
img = Image.open("mic.png")
img.save("mic.ico", format="ICO", sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
print("Icons generated.")
EOF
```

The application generates tray icons programmatically at runtime using Pillow,
so the `.ico` file is only required for the packaged `.exe` build.
