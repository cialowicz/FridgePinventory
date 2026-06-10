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

    samples = []
    stop = threading.Event()

    def watch() -> None:
        while not stop.is_set():
            samples.append(epdconfig.digital_read(epd.busy_pin))
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

    t = time.time()
    epd.Clear()
    clear_elapsed = time.time() - t
    print(f"Clear: {clear_elapsed:.2f}s")

    stop.set()
    watcher.join()

    busy_seen = 1 in samples
    print(f"BUSY ever asserted: {busy_seen} ({len(samples)} samples)")
    print()
    if busy_seen and clear_elapsed > 1.0:
        print("Panel is executing refreshes. If the screen stayed blank during")
        print("Clear(), suspect the panel glass / flat-flex data lines — run")
        print("test_pattern.py to check image output.")
    else:
        print("Panel did not execute the refresh (no busy pulse, instant return).")
        print("Run pin_probe.py next to separate power/reset from SPI issues.")

    epd.sleep()


if __name__ == "__main__":
    main()
