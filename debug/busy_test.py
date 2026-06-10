"""Driver-level smoke test: init + Clear with BUSY-line monitoring.

Runs init_4GRAY() and Clear() through the deployed waveshare_epd driver while
a background thread samples the BUSY pin. A healthy panel takes seconds per
step, visibly flashes during Clear(), and asserts BUSY during every refresh.
Sub-second timings with BUSY never asserted mean the panel is not executing
commands at all (run pin_probe.py to isolate power/reset from SPI).

Stop the service first (it holds the pins and SPI device):

    sudo systemctl stop fridgepinventory.service
    ~/.epaper_venv/bin/python debug/busy_test.py
"""

import threading
import time

from waveshare_epd import epd3in97


def main() -> None:
    epd = epd3in97.EPD()
    epdconfig = epd3in97.epdconfig

    # BUSY asserts in two distinct situations: the boot pulse after the
    # hardware reset inside init (GPIO-driven, proves nothing about SPI),
    # and during a refresh after the 0x20 command (proves the panel received
    # SPI commands). Track the phases separately so the verdict keys on the
    # refresh, not the reset.
    phase = {"name": "init"}
    busy_by_phase = {"init": False, "clear": False}
    sample_count = 0
    stop = threading.Event()

    def watch() -> None:
        nonlocal sample_count
        while not stop.is_set():
            if epdconfig.digital_read(epd.busy_pin):
                busy_by_phase[phase["name"]] = True
            sample_count += 1
            time.sleep(0.002)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    t = time.time()
    rc = epd.init_4GRAY()
    init_elapsed = time.time() - t
    print(f"init_4GRAY: rc={rc} in {init_elapsed:.2f}s")
    if rc == -1:
        stop.set()
        print("init returned -1 (module_init failed) — check SPI device and")
        print("GPIO availability (is the service really stopped?).")
        return

    phase["name"] = "clear"
    t = time.time()
    epd.Clear()
    clear_elapsed = time.time() - t
    print(f"Clear: {clear_elapsed:.2f}s")

    stop.set()
    watcher.join()

    print(f"BUSY during init (reset boot pulse, GPIO path): "
          f"{busy_by_phase['init']}")
    print(f"BUSY during Clear refresh (SPI command path):   "
          f"{busy_by_phase['clear']}  ({sample_count} samples)")
    print()
    if busy_by_phase["clear"] and clear_elapsed > 1.0:
        print("Panel is executing refreshes. If the screen stayed blank during")
        print("Clear(), suspect the panel glass / flat-flex data lines — run")
        print("test_pattern.py to check image output.")
    elif busy_by_phase["init"]:
        print("Controller is alive (boot pulse seen) but never received the")
        print("refresh command: SPI path failure. Check MOSI/SCLK/CS wiring or")
        print("the board's interface-select switch; run spi_loopback.py to")
        print("verify the Pi side of the bus.")
    else:
        print("No BUSY activity at all — power/reset problem. Run pin_probe.py.")

    epd.sleep()


if __name__ == "__main__":
    main()
