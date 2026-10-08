"""
Генерация иконки приложения.

Создаёт:
    assets/icon.ico     — для Windows-сборки
    assets/icon.png     — универсальный (Linux, README)
    assets/icon_256.png — крупная версия для macOS .icns (см. ниже)

Запуск:
    python assets/make_icon.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
BG = (30, 30, 40)
FG = (90, 200, 255)
ACCENT = (255, 180, 60)


def _font(size: int):
    """Пытается найти системный моношрифт, иначе — дефолт Pillow."""
    candidates = [
        "DejaVuSansMono-Bold.ttf",
        "consolab.ttf",
        "arialbd.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_image(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG + (255,))
    d = ImageDraw.Draw(img)

    # скруглённый фон
    radius = size // 6
    d.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=BG,
        outline=FG,
        width=max(2, size // 32),
    )

    # текст «0x»
    font = _font(int(size * 0.42))
    text = "0x"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - size * 0.02),
        text,
        font=font,
        fill=FG,
    )

    # маленькая «стрелка/полоска» акцентом — намёк на конвертацию
    bar_w = int(size * 0.5)
    bar_h = max(3, size // 24)
    x0 = (size - bar_w) // 2
    y0 = int(size * 0.72)
    d.rounded_rectangle(
        (x0, y0, x0 + bar_w, y0 + bar_h),
        radius=bar_h // 2,
        fill=ACCENT,
    )

    return img


def main() -> None:
    base = make_image(256)
    base.save(HERE / "icon.png")
    base.save(HERE / "icon_256.png")

    # .ico с несколькими размерами
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [make_image(s[0]).resize(s) for s in sizes]
    ico_images[0].save(
        HERE / "icon.ico",
        format="ICO",
        sizes=sizes,
        append_images=ico_images[1:],
    )

    print("Готово:")
    print(f"  {HERE / 'icon.ico'}")
    print(f"  {HERE / 'icon.png'}")
    print(f"  {HERE / 'icon_256.png'}")


if __name__ == "__main__":
    main()