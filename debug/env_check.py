"""Deployment sanity check: SPI device, driver imports, deployed-file match.

Safe to run any time (touches no hardware). Exit code 0 = all checks passed.

    ~/.epaper_venv/bin/python debug/env_check.py
"""

import hashlib
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER_FILES = ("epd3in97.py", "epdconfig.py")

failures = 0


def report(ok: bool, label: str, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f": {detail}"
    print(line)


def md5(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def main() -> int:
    # Platform: are we on a Pi at all?
    model_file = "/proc/device-tree/model"
    if os.path.exists(model_file):
        with open(model_file) as f:
            model = f.read().strip("\x00").strip()
        report("raspberry pi" in model.lower(), "Raspberry Pi platform", model)
    else:
        report(False, "Raspberry Pi platform", f"{model_file} not found")

    # SPI device node (requires dtparam=spi=on / raspi-config)
    report(os.path.exists("/dev/spidev0.0"), "SPI device /dev/spidev0.0",
           "" if os.path.exists("/dev/spidev0.0")
           else "missing — enable SPI via raspi-config")

    # Python deps the driver needs
    for mod in ("spidev", "gpiozero", "numpy", "PIL"):
        try:
            __import__(mod)
            report(True, f"import {mod}")
        except ImportError as e:
            report(False, f"import {mod}", str(e))

    # Deployed waveshare driver present and matching the repo copy
    try:
        from waveshare_epd import epd3in97
        deployed_dir = os.path.dirname(os.path.abspath(epd3in97.__file__))
        report(True, "import waveshare_epd.epd3in97", deployed_dir)
    except ImportError as e:
        report(False, "import waveshare_epd.epd3in97", str(e))
        deployed_dir = None

    if deployed_dir:
        repo_drivers = os.path.join(REPO_ROOT, "waveshare_drivers")
        for name in DRIVER_FILES:
            repo_file = os.path.join(repo_drivers, name)
            deployed_file = os.path.join(deployed_dir, name)
            if not os.path.exists(deployed_file):
                report(False, f"deployed {name}", "missing — re-run deploy.sh")
            elif md5(repo_file) != md5(deployed_file):
                report(False, f"deployed {name} matches repo",
                       "differs — re-run deploy.sh")
            else:
                report(True, f"deployed {name} matches repo")

    print()
    print("All checks passed." if failures == 0
          else f"{failures} check(s) failed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
