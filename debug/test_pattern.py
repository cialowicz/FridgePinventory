"""Visual end-to-end test: render 4-gray bars + text through the driver.

Use after busy_test.py passes. Draws four vertical bands at the panel's
exact gray levels (white / light gray / dark gray / black) with a label in
each, displays via the deployed waveshare_epd driver, then sleeps the panel.
All four bands should be clearly distinct and the text crisp; missing bands
or garbled output point at the data path or a damaged panel.

Stop the service first:

    sudo systemctl stop fridgepinventory.service
    ~/.epaper_venv/bin/python debug/test_pattern.py
"""

import time

from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd3in97

# Panel gray levels, matching the driver's GRAY1-GRAY4
BANDS = [
    (0xFF, "WHITE"),
    (0xC0, "LIGHT"),
    (0x80, "DARK"),
    (0x00, "BLACK"),
]

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def main() -> None:
    epd = epd3in97.EPD()

    print("Initializing (init_4GRAY)...")
    if epd.init_4GRAY() == -1:
        print("init returned -1 (module_init failed) — check SPI/GPIO.")
        return

    try:
        font = ImageFont.truetype(FONT_PATH, 36)
    except OSError:
        font = ImageFont.load_default()

    image = Image.new("L", (epd.width, epd.height), 0xFF)
    draw = ImageDraw.Draw(image)
    band_width = epd.width // len(BANDS)
    for i, (level, label) in enumerate(BANDS):
        x0 = i * band_width
        draw.rectangle((x0, 0, x0 + band_width - 1, epd.height - 1), fill=level)
        # Label in a contrasting level so it is visible on every band
        text_fill = 0x00 if level >= 0x80 else 0xFF
        draw.text((x0 + 20, epd.height // 2 - 20), label, fill=text_fill, font=font)
    draw.text((20, 20), time.strftime("%Y-%m-%d %H:%M:%S"), fill=0x00, font=font)

    print("Displaying test pattern (a full refresh takes a few seconds)...")
    t = time.time()
    epd.display_4GRAY(epd.getbuffer_4Gray(image))
    print(f"Refresh completed in {time.time() - t:.2f}s")

    print("Putting panel to sleep. The pattern should persist on screen.")
    epd.sleep()


if __name__ == "__main__":
    main()
