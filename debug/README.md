# Hardware debug scripts

Standalone scripts for diagnosing the e-Paper display on the Pi, independent
of the FridgePinventory service. Run them with the deployment venv's Python,
with the service stopped (it holds the GPIO pins and SPI device):

```bash
sudo systemctl stop fridgepinventory.service
~/.epaper_venv/bin/python debug/<script>.py
```

Suggested order: `env_check.py` → `pin_probe.py` → `busy_test.py` →
`test_pattern.py`. Each script prints its own PASS/FAIL interpretation.

## env_check.py

Deployment sanity check — no hardware access. Verifies the SPI device node
exists, the Waveshare driver imports from the venv, and the deployed
`epd3in97.py`/`epdconfig.py` in site-packages are byte-identical to the
copies in `waveshare_drivers/` (they are copied there by `deploy.sh`; a
mismatch means deploy.sh needs to be re-run).

## pin_probe.py

Bare GPIO probe — no SPI, no driver import. Powers the panel (PWR pin),
performs the same hardware reset sequence the driver uses, and watches the
BUSY line. The panel controller asserts BUSY while it boots after a reset,
so this answers "is the controller alive?" with nothing else in the loop.

- `BUSY asserted after reset: True` — controller is alive; a blank screen is
  then an SPI/data problem, not power/reset.
- `False` — the controller never responded. Check (in order): the flat-flex
  cable between driver board and panel (open the latch, reseat), the
  config/interface switches on the driver board, HAT seating on the GPIO
  header, and finally a failed panel.

## busy_test.py

Full driver-level test: `init_4GRAY()` + `Clear()` through the deployed
`waveshare_epd.epd3in97`, with a background thread sampling BUSY the whole
time. A working panel takes seconds per step, visibly flashes during
`Clear()`, and asserts BUSY. Sub-second timings with `BUSY ever asserted:
False` mean the panel is not executing commands (see pin_probe checklist).

## test_pattern.py

Visual end-to-end check: renders 4-gray vertical bars plus text through the
deployed driver and puts the panel to sleep afterwards. Use this once
busy_test passes, to confirm image data integrity (all four gray levels
should be distinct, text crisp).
