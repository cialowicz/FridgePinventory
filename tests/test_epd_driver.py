# Tests for the bundled epd3in97 Waveshare driver.
#
# The driver is not an installed package; it is loaded here under a synthetic
# `waveshare_epd` package with a stubbed epdconfig so no hardware is touched.
# The buffer-conversion tests compare the (vectorized) implementation against
# a pure-Python reference copied verbatim from the original Waveshare code.

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

DRIVERS_DIR = Path(__file__).parent.parent / "waveshare_drivers"


class EpdConfigStub(types.ModuleType):
    """Records SPI traffic; busy pin idles by default."""

    RST_PIN = 17
    DC_PIN = 25
    CS_PIN = 8
    BUSY_PIN = 24

    def __init__(self):
        super().__init__("waveshare_epd.epdconfig")
        self.spi_log = []
        self.busy_level = 0
        self.delays_ms = 0

    def digital_write(self, pin, value):
        pass

    def digital_read(self, pin):
        return self.busy_level

    def delay_ms(self, delaytime):
        self.delays_ms += delaytime

    def spi_writebyte(self, data):
        self.spi_log.append(("byte", list(data)))

    def spi_writebyte2(self, data):
        self.spi_log.append(("bulk", bytes(bytearray(data))))

    def module_init(self, cleanup=False):
        return 0

    def module_exit(self, cleanup=False):
        pass


@pytest.fixture
def driver():
    stub = EpdConfigStub()
    pkg = types.ModuleType("waveshare_epd")
    pkg.__path__ = [str(DRIVERS_DIR)]
    saved = {
        name: sys.modules.get(name)
        for name in ("waveshare_epd", "waveshare_epd.epdconfig", "waveshare_epd.epd3in97")
    }
    sys.modules["waveshare_epd"] = pkg
    sys.modules["waveshare_epd.epdconfig"] = stub
    spec = importlib.util.spec_from_file_location(
        "waveshare_epd.epd3in97", DRIVERS_DIR / "epd3in97.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["waveshare_epd.epd3in97"] = module
    spec.loader.exec_module(module)
    try:
        yield module, stub
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def make_test_image(width, height):
    """Exact gray levels plus off-level values that exercise quantization."""
    img = Image.new("L", (width, height))
    pixels = img.load()
    values = [0xFF, 0xC0, 0x80, 0x00, 0xE5, 0x9A, 0x55, 0x12, 0x3F, 0x40, 0xBF, 0xC1]
    for y in range(height):
        for x in range(width):
            pixels[x, y] = values[(x * 7 + y * 13) % len(values)]
    return img


def reference_getbuffer_4gray(epd, image):
    """Original Waveshare pure-Python implementation (the spec)."""
    buf = [0xFF] * (int(epd.width / 4) * epd.height)
    image_monocolor = image.convert('L')
    imwidth, imheight = image_monocolor.size
    pixels = image_monocolor.load()
    i = 0
    if imwidth == epd.width and imheight == epd.height:
        for y in range(imheight):
            for x in range(imwidth):
                if pixels[x, y] == 0xC0:
                    pixels[x, y] = 0x80
                elif pixels[x, y] == 0x80:
                    pixels[x, y] = 0x40
                i = i + 1
                if i % 4 == 0:
                    buf[int((x + (y * epd.width)) / 4)] = (
                        (pixels[x - 3, y] & 0xc0)
                        | (pixels[x - 2, y] & 0xc0) >> 2
                        | (pixels[x - 1, y] & 0xc0) >> 4
                        | (pixels[x, y] & 0xc0) >> 6
                    )
    elif imwidth == epd.height and imheight == epd.width:
        for x in range(imwidth):
            for y in range(imheight):
                newx = y
                newy = epd.height - x - 1
                if pixels[x, y] == 0xC0:
                    pixels[x, y] = 0x80
                elif pixels[x, y] == 0x80:
                    pixels[x, y] = 0x40
                i = i + 1
                if i % 4 == 0:
                    buf[int((newx + (newy * epd.width)) / 4)] = (
                        (pixels[x, y - 3] & 0xc0)
                        | (pixels[x, y - 2] & 0xc0) >> 2
                        | (pixels[x, y - 1] & 0xc0) >> 4
                        | (pixels[x, y] & 0xc0) >> 6
                    )
    return buf


def reference_4gray_planes(epd, image):
    """Plane byte streams display_4GRAY must send to 0x24/0x26.

    Per-pixel loop from the official Waveshare 4-gray reference
    (e.g. epd3in7): white=(1,1), light gray=(1,0), dark gray=(0,1),
    black=(0,0) — consistent with Clear(), which writes 0xFF to both
    planes to whiten the panel. (The buffer codes here are post-remap:
    0xC0 = light gray, 0x40 = dark gray.)
    """
    planes = []
    for plane in (0, 1):
        out = []
        image_counter = int(epd.width / 8) * epd.height
        for i in range(0, image_counter):
            temp3 = 0
            for j in range(0, 2):
                temp1 = image[i * 2 + j]
                for k in range(0, 2):
                    for sub in range(2):
                        temp2 = temp1 & 0xC0
                        if plane == 0:
                            bit = 1 if temp2 in (0xC0, 0x80) else 0
                        else:
                            bit = 1 if temp2 in (0xC0, 0x40) else 0
                        temp3 |= bit
                        last = (j == 1 and k == 1 and sub == 1)
                        if not last:
                            temp3 <<= 1
                        temp1 = (temp1 << 2) & 0xFF
            out.append(temp3)
        planes.append(bytes(out))
    return planes


def test_getbuffer_4gray_matches_reference(driver):
    module, _ = driver
    epd = module.EPD()
    epd.width, epd.height = 32, 8  # small panel keeps the reference loop fast

    image = make_test_image(32, 8)
    expected = reference_getbuffer_4gray(epd, image.copy())
    actual = epd.getbuffer_4Gray(image)

    assert list(bytearray(actual)) == expected


def test_getbuffer_4gray_rotated_matches_reference(driver):
    module, _ = driver
    epd = module.EPD()
    epd.width, epd.height = 32, 8

    image = make_test_image(8, 32)  # portrait input gets rotated
    expected = reference_getbuffer_4gray(epd, image.copy())
    actual = epd.getbuffer_4Gray(image)

    assert list(bytearray(actual)) == expected


def test_getbuffer_4gray_wrong_dimensions_returns_blank(driver):
    module, _ = driver
    epd = module.EPD()
    epd.width, epd.height = 32, 8

    actual = epd.getbuffer_4Gray(make_test_image(10, 10))

    assert list(bytearray(actual)) == [0xFF] * (32 // 4 * 8)


def test_display_4gray_sends_reference_planes_bulk(driver):
    module, stub = driver
    epd = module.EPD()
    epd.width, epd.height = 32, 8

    buf = epd.getbuffer_4Gray(make_test_image(32, 8))
    expected_24, expected_26 = reference_4gray_planes(epd, bytearray(buf))

    stub.spi_log.clear()
    epd.display_4GRAY(buf)

    commands = [entry for entry in stub.spi_log if entry[0] == "byte"]
    bulks = [entry[1] for entry in stub.spi_log if entry[0] == "bulk"]
    # 0x24 plane, 0x26 plane, then the TurnOnDisplay command sequence.
    assert [0x24] in [c[1] for c in commands]
    assert [0x26] in [c[1] for c in commands]
    assert bulks[0] == expected_24
    assert bulks[1] == expected_26


def test_display_4gray_white_and_black_polarity(driver):
    """A white image must produce the same all-0xFF planes Clear() sends;
    a black image the complement. Guards against re-inverting the LUTs."""
    module, stub = driver
    epd = module.EPD()
    epd.width, epd.height = 32, 8
    plane_bytes = 32 * 8 // 8

    for level, expected_byte in ((0xFF, 0xFF), (0x00, 0x00)):
        buf = epd.getbuffer_4Gray(Image.new("L", (32, 8), level))
        stub.spi_log.clear()
        epd.display_4GRAY(buf)
        bulks = [entry[1] for entry in stub.spi_log if entry[0] == "bulk"]
        assert bulks[0] == bytes([expected_byte] * plane_bytes)
        assert bulks[1] == bytes([expected_byte] * plane_bytes)


def test_readbusy_times_out_instead_of_hanging(driver):
    module, stub = driver
    epd = module.EPD()
    stub.busy_level = 1  # stuck busy

    with pytest.raises(RuntimeError, match="[Bb]usy"):
        epd.ReadBusy()
