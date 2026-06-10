"""Deployment sanity check: SPI device, driver imports, deployed-file match.

Safe to run any time (touches no hardware). Exit code 0 = all checks passed.

    ~/.epaper_venv/bin/python debug/env_check.py
"""

import hashlib
import os
import shutil
import subprocess
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

    # SPI-related boot config: an overlay can leave /dev/spidev0.0 present
    # while remapping or disabling the actual pins (e.g. spi0-0cs).
    for cfg in ("/boot/firmware/config.txt", "/boot/config.txt"):
        if os.path.exists(cfg):
            with open(cfg) as f:
                spi_lines = [line.strip() for line in f
                             if "spi" in line.lower()
                             and not line.strip().startswith("#")]
            report(any("dtparam=spi=on" in line.replace(" ", "")
                       for line in spi_lines),
                   f"dtparam=spi=on in {cfg}")
            # The driver needs hardware CE0 (GPIO 8); spi0-0cs removes all
            # chip-select lines, so the panel ignores every transfer while
            # /dev/spidev0.0 still exists and writes "succeed".
            report(not any("spi0-0cs" in line for line in spi_lines),
                   "no spi0-0cs overlay",
                   "" if not any("spi0-0cs" in line for line in spi_lines)
                   else f"dtoverlay=spi0-0cs disables CE0 — remove it from "
                        f"{cfg} and reboot")
            for line in spi_lines:
                flagged = "dtoverlay" in line
                print(f"         {line}"
                      + ("   <-- overlay touching SPI, verify it" if flagged
                         else ""))
            break
    else:
        report(False, "boot config.txt", "not found")

    # Pin mux: GPIO 9/10/11 must be in their SPI0 alt function, otherwise the
    # kernel happily "transmits" while the physical pins never move.
    # Pi 5 uses pinctrl; earlier models raspi-gpio (same output format).
    tool = shutil.which("pinctrl") or shutil.which("raspi-gpio")
    if tool is None:
        report(False, "SPI pin mux", "pinctrl/raspi-gpio not found")
    else:
        try:
            out = subprocess.run([tool, "get", "8-11"], capture_output=True,
                                 text=True, timeout=10).stdout
        except Exception as e:
            out = ""
            report(False, "SPI pin mux", f"{tool} failed: {e}")
        if out:
            mux_ok = True
            cs_claimed = True
            for line in out.strip().splitlines():
                print(f"         {line.strip()}")
                gpio = line.split(":")[0].strip()
                # 9-11 (MISO/MOSI/SCLK) must show their SPI0 alt function.
                if gpio in ("9", "10", "11") and "SPI0" not in line:
                    mux_ok = False
                # 8/CE0 is either in its SPI0 alt function or claimed by the
                # SPI driver as a GPIO output (cs-gpios). Function "none"
                # means no chip-select exists in the LIVE device tree, so the
                # panel ignores every transfer.
                if gpio == "8" and "none" in line:
                    cs_claimed = False
            report(mux_ok, "GPIO 9/10/11 muxed to SPI0",
                   "" if mux_ok else
                   "pins not in SPI0 alt function — SPI writes go nowhere; "
                   "check dtoverlays and reboot after config changes")
            report(cs_claimed, "GPIO 8 (CE0) claimed as chip-select",
                   "" if cs_claimed else
                   "CE0 is unclaimed in the running device tree (spi0-0cs "
                   "still active). config.txt is only read at boot — if the "
                   "file is already clean, REBOOT and re-run this check")

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
