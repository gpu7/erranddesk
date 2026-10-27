# Generates src/static/og-image.png (1200x630) in Errand Desk colors from src/assets/style.css. No logos, no photos.
from PIL import Image, ImageDraw, ImageFont
W, H = 1200, 630
INK, MUTED, SOFT, LINE, ACCENT, AMBER = "#1d2329", "#5b6670", "#f5f7f9", "#dfe3e7", "#1f5f8b", "#e0a800"
INTER = "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"
def font(size, weight):
    f = ImageFont.truetype(INTER, size)
    try: f.set_variation_by_axes([32, weight])  # opsz, wght
    except Exception:
        try: f.set_variation_by_axes([weight])
        except Exception: pass
    return f
img = Image.new("RGB", (W, H), SOFT)
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 24, H], fill=ACCENT)
d.rectangle([24, H - 8, W, H], fill=LINE)
x = 96
d.text((x, 150), "Errand Desk", font=font(104, 800), fill=INK)
d.rectangle([x, 290, x + 120, 298], fill=AMBER)
d.text((x, 330), "Plain, sourced answers for paperwork errands", font=font(44, 500), fill=INK)
d.text((x, 400), "Fax  ·  Notary  ·  Passport photos", font=font(38, 600), fill=ACCENT)
d.text((x, 520), "erranddesk.com", font=font(30, 500), fill=MUTED)
d.text((W - 96, 520), "Every price sourced and dated", font=font(30, 500), fill=MUTED, anchor="ra")
img.save("src/static/og-image.png", optimize=True)
print(img.size)
