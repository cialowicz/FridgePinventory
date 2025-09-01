# hardware_test.py
import sys
from inky.auto import auto
from PIL import Image, ImageDraw, ImageFont

print("--- Inky Display Hardware Test ---")

# This script attempts to initialize the display and show a simple message.
# It is designed to be run directly on the Raspberry Pi to test the hardware connection.

# The Inky library can produce a UserWarning: "SPI: Cannot disable chip-select!".
# This is often non-fatal, but if the script fails to display anything, it could
# indicate a problem with the SPI bus configuration or a physical connection issue.

try:
    print("1. Initializing display with auto(verbose=True)...")
    # The 'auto' function attempts to automatically detect the Inky display type.
    # verbose=True will print debugging information about the detection process.
    display = auto(verbose=True)
    print(f"   Success. Detected: {type(display)}")
    print(f"   Display dimensions: {display.width}x{display.height}")

    print("2. Creating a new black and white image...")
    # 'P' mode is for paletted images, which Inky displays use.
    image = Image.new("P", (display.width, display.height))
    draw = ImageDraw.Draw(image)
    print("   Success. Image created.")

    print("3. Loading font...")
    try:
        # Attempt to load a common font from the Raspberry Pi OS.
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        print("   Success. Loaded DejaVuSans-Bold font.")
    except IOError:
        print("   DejaVu font not found. Loading the default PIL font.")
        font = ImageFont.load_default()

    print("4. Drawing 'Hardware OK' text onto the image...")
    message = "Hardware OK"
    # Calculate text position to center it on the screen.
    text_bbox = draw.textbbox((0, 0), message, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (display.width - text_width) // 2
    y = (display.height - text_height) // 2
    draw.text((x, y), message, fill=display.BLACK, font=font)
    print(f"   Success. Text drawn at position ({x}, {y}).")

    print("5. Sending image to the display...")
    # This is the final step that actually updates the eInk screen.
    display.set_image(image)
    display.show()
    print("   --- TEST COMPLETE: Success! Check the display. ---")

except Exception as e:
    print(f"\n--- TEST FAILED: An error occurred ---", file=sys.stderr)
    print(f"Error Type: {type(e).__name__}", file=sys.stderr)
    print(f"Error Details: {e}", file=sys.stderr)
    print("\nTroubleshooting suggestions:")
    print("  - Double-check that the Inky display is securely connected to the GPIO pins.")
    print("  - Ensure the SPI interface is enabled on your Raspberry Pi (use 'sudo raspi-config').")
    print("  - Verify that the 'inky' and 'Pillow' libraries are correctly installed in your virtual environment.")
    sys.exit(1)
