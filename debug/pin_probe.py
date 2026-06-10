"""Bare GPIO probe: is the panel controller alive?

Uses gpiozero directly (no SPI, no waveshare driver). Powers the panel,
performs the driver's exact hardware-reset sequence on the RST line, and
watches BUSY. The controller asserts BUSY while it boots after a reset, so
BUSY never moving means the panel is not powered/connected/responding —
independent of any SPI or driver problem.

Stop the service first (it holds the pins):

    sudo systemctl stop fridgepinventory.service
    ~/.epaper_venv/bin/python debug/pin_probe.py
"""

import time

import gpiozero

# BCM pin numbers — keep in sync with waveshare_drivers/epdconfig.py
RST_PIN = 17
PWR_PIN = 18
BUSY_PIN = 24

WATCH_SECONDS = 2.0


def main() -> None:
    pwr = gpiozero.LED(PWR_PIN)
    rst = gpiozero.LED(RST_PIN)
    # pull_up=False matches epdconfig: BUSY idles low, panel drives it high
    busy = gpiozero.Button(BUSY_PIN, pull_up=False)

    pwr.on()
    time.sleep(0.1)
    print(f"BUSY after power-on: {int(busy.value)}")

    # Same reset sequence as EPD.reset(): high 200ms, low 2ms, high 200ms.
    # Sample BUSY throughout, since the controller's busy pulse can fall
    # inside the trailing 200ms settle window.
    rst.on()
    time.sleep(0.2)
    rst.off()
    time.sleep(0.002)
    rst.on()

    seen_high = False
    transitions = 0
    last = int(busy.value)
    deadline = time.time() + WATCH_SECONDS
    while time.time() < deadline:
        value = int(busy.value)
        if value != last:
            transitions += 1
            last = value
        if value:
            seen_high = True
        time.sleep(0.001)

    print(f"BUSY asserted after reset: {seen_high} "
          f"({transitions} transition(s) in {WATCH_SECONDS:.0f}s, "
          f"final level {last})")
    print()
    if seen_high:
        print("Controller is alive. A blank screen is an SPI/data problem")
        print("(MOSI/SCLK path) rather than power or reset — run busy_test.py.")
    else:
        print("Controller never responded to the hardware reset. Check, in order:")
        print("  1. Flat-flex cable between driver board and panel (reseat).")
        print("  2. Config/interface switches on the driver board.")
        print("  3. HAT seating on the GPIO header.")
        print("  4. Failed panel/driver board.")

    pwr.off()


if __name__ == "__main__":
    main()
