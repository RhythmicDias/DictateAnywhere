import os
import sys

# Ensure requests is imported, fallback if not present
try:
    import requests
except ImportError:
    print("[DictateAnywhere] 'requests' not installed, skipping font download.")
    sys.exit(0)

font_urls = {
    "Inter-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/static/Inter-Regular.ttf",
    "Inter-Medium.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/static/Inter-Medium.ttf",
    "Inter-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/static/Inter-Bold.ttf",
}

# Determine script parent -> assets/fonts relative to project root
script_dir = os.path.dirname(os.path.abspath(__file__))
dest_dir = os.path.abspath(os.path.join(script_dir, "..", "assets", "fonts"))
os.makedirs(dest_dir, exist_ok=True)

print("[DictateAnywhere] Checking Inter font assets...")
all_success = True
for name, url in font_urls.items():
    dest_path = os.path.join(dest_dir, name)
    if not os.path.exists(dest_path):
        print(f"[DictateAnywhere] Downloading {name}...")
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(r.content)
            print(f"[DictateAnywhere] Saved {name}")
        except Exception as e:
            print(f"[DictateAnywhere] Error downloading {name}: {e}")
            all_success = False
    else:
        print(f"[DictateAnywhere] {name} already present.")

if all_success:
    print("[DictateAnywhere] Font assets configured successfully.")
else:
    print("[DictateAnywhere] Warning: Some font assets could not be downloaded. System fonts will be used as a fallback.")
