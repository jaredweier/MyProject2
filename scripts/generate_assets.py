"""Generate placeholder branding assets for builds."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from paths import app_dir


def _save_logo(path: str):
    img = Image.new("RGB", (256, 256), "#0D1B2A")
    draw = ImageDraw.Draw(img)
    draw.ellipse([40, 40, 216, 216], fill="#1E88E5")
    draw.rectangle([100, 70, 156, 186], fill="#FFFFFF")
    draw.text((72, 200), "DPD", fill="#FFFFFF")
    img.save(path, "PNG")


def _save_team_photo(path: str):
    img = Image.new("RGB", (800, 400), "#152232")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 800, 80], fill="#1E88E5")
    draw.text((24, 28), "Dodgeville Police Department", fill="#FFFFFF")
    draw.text((24, 160), "Scheduler Evaluation Build", fill="#8BA3C7")
    draw.text((24, 200), "Editable roster  ·  14-day rotation", fill="#8BA3C7")
    img.save(path, "JPEG", quality=90)


if __name__ == "__main__":
    root = app_dir()
    _save_logo(f"{root}/logo.png")
    _save_team_photo(f"{root}/team_photo.jpg")
    print("Generated logo.png and team_photo.jpg")
