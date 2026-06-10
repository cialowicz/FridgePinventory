"""SPI loopback test: verifies the Pi's SPI controller and MOSI pin output.

Requires a physical jumper wire between MOSI (physical pin 19, BCM 10) and
MISO (physical pin 21, BCM 9). With the jumper in place, everything written
out on MOSI is read straight back on MISO, so a match proves the Pi side of
the SPI bus (controller, pin mux, MOSI drive) is good end-to-end. Disconnect
the display cable / remove the HAT first so nothing else loads the bus.

Without the jumper, received bytes are typically all 0x00 or 0xFF — the
script detects and reports that case rather than failing cryptically.

    sudo systemctl stop fridgepinventory.service
    ~/.epaper_venv/bin/python debug/spi_loopback.py
"""

import spidev

# Match the driver's bus settings (epdconfig.module_init)
BUS, DEVICE = 0, 0
SPEED_HZ = 4000000


def main() -> None:
    spi = spidev.SpiDev()
    spi.open(BUS, DEVICE)
    spi.max_speed_hz = SPEED_HZ
    spi.mode = 0b00

    tx = list(range(1, 65))  # distinctive non-repeating pattern, no 0x00/0xFF
    rx = spi.xfer2(tx[:])
    spi.close()

    if rx == tx:
        print("PASS: loopback data matched — Pi SPI controller and MOSI/MISO")
        print("pins are working. The problem is downstream: cable, connector,")
        print("or the display driver board.")
    elif all(b == rx[0] for b in rx):
        print(f"NO SIGNAL: received constant 0x{rx[0]:02X} for every byte.")
        print("Either the MOSI->MISO jumper is missing/loose, or the SPI pins")
        print("are not being driven (check dtparam=spi=on and pin mux).")
    else:
        print("FAIL: received data is garbled (partial/corrupted readback).")
        print(f"  sent:     {tx[:16]} ...")
        print(f"  received: {rx[:16]} ...")
        print("Suspect a bad jumper contact; retry, and at a lower speed:")
        print("  edit SPEED_HZ down to 500000 and run again.")


if __name__ == "__main__":
    main()
