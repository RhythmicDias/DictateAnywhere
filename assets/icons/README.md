# Icons

The DictateAnywhere tray icon and floating widget icon are **generated
programmatically at runtime** — no static `.ico` or `.png` files are required.

| Component         | Generator                          |
| ----------------- | ---------------------------------- |
| System tray icon  | `ui/tray.py → _make_icon()`        |
| Floating button   | `ui/floating_widget.py → _draw()`  |

Both draw directly onto PIL/Pillow images and tk Canvas objects using
colour-coded circles and microphone shapes.

## PyInstaller builds

The `--add-data "assets;assets"` flag in the build script bundles this
directory into the `.exe` distribution. It is kept for future use (e.g.
custom `.ico` for the window or installer).

To add a custom window icon in the future, place `app.ico` here and
reference it in the PyInstaller spec with `--icon=assets/icons/app.ico`.
