"""把 assets/gaugepunk_icon_source.png 转成 host/assets/gaugepunk.ico (多尺寸).

一次性脚本, 想换图时再跑一次. 输出会被 git 提交, 打包阶段 PyInstaller 会读它.

用法:
    python scripts/make-icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "gaugepunk_icon_source.png"
DST = ROOT / "host" / "assets" / "gaugepunk.ico"

# Windows ICO 推荐的多分辨率档位, 系统会自动按上下文选最近的
SIZES = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)]


def center_crop_square(im: Image.Image) -> Image.Image:
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"找不到源图: {SRC}")
    DST.parent.mkdir(parents=True, exist_ok=True)

    im = Image.open(SRC).convert("RGBA")
    im = center_crop_square(im)
    im = im.resize((256, 256), Image.LANCZOS)
    im.save(DST, format="ICO", sizes=SIZES)
    print(f"OK  {SRC.name} ({im.width}x{im.height})  ->  {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
