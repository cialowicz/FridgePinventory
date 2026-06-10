# *****************************************************************************
# * | File        :	  epd3in97.py (copy and edit of epd2in15g.py)
# * | Author      :   Waveshare team
# * | Function    :   Electronic paper driver
# * | Info        :   3.97" e-paper display driver
# *----------------
# * | This version:   V1.0
# * | Date        :   2024-08-07
# # | Info        :   python demo
# -----------------------------------------------------------------------------
# ******************************************************************************/
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
from . import epdconfig

import numpy as np
import PIL
from PIL import Image
import io

# Display resolution
EPD_WIDTH       = 800
EPD_HEIGHT      = 480

GRAY1  = 0xff #white
GRAY2  = 0xC0
GRAY3  = 0x80 #gray
GRAY4  = 0x00 #Blackest

# Upper bound for a busy-pin wait; a stuck BUSY line (bad wiring, failed
# panel) must surface as an error instead of hanging the caller forever.
BUSY_TIMEOUT_MS = 30000

logger = logging.getLogger(__name__)

class EPD:
    def __init__(self):
        self.reset_pin = epdconfig.RST_PIN
        self.dc_pin = epdconfig.DC_PIN
        self.busy_pin = epdconfig.BUSY_PIN
        self.cs_pin = epdconfig.CS_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.GRAY1  = GRAY1 #white
        self.GRAY2  = GRAY2
        self.GRAY3  = GRAY3 #gray
        self.GRAY4  = GRAY4 #Blackest   

        
    # Hardware reset
    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200) 
        epdconfig.digital_write(self.reset_pin, 0)         # module reset
        epdconfig.delay_ms(2)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)   

    def send_command(self, command):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([command])
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([data])
        epdconfig.digital_write(self.cs_pin, 1)

    # send a lot of data   
    def send_data2(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte2(data)
        epdconfig.digital_write(self.cs_pin, 1)
        
    def ReadBusy(self):
        logger.debug("e-Paper busy H")
        epdconfig.delay_ms(100)
        waited_ms = 0
        while(epdconfig.digital_read(self.busy_pin) == 1):      # 0: idle, 1: busy
            if waited_ms >= BUSY_TIMEOUT_MS:
                raise RuntimeError(
                    f"e-Paper busy pin stuck high for {BUSY_TIMEOUT_MS} ms"
                )
            epdconfig.delay_ms(5)
            waited_ms += 5
        logger.debug("e-Paper busy release")
        
    def TurnOnDisplay(self):
        self.send_command(0x22)
        self.send_data(0xF7)
        self.send_command(0x20)
        self.ReadBusy()

    def TurnOnDisplay_Fast(self):
        self.send_command(0x22)
        self.send_data(0xD7)
        self.send_command(0x20)
        self.ReadBusy()

    def TurnOnDisplay_4GRAY(self):
        self.send_command(0x22)
        self.send_data(0xD7)
        self.send_command(0x20)
        self.ReadBusy()

    def TurnOnDisplay_Partial(self):
        self.send_command(0x22)
        self.send_data(0xFF)
        self.send_command(0x20)
        self.ReadBusy()
        
    def init(self):
        if (epdconfig.module_init() != 0):
            return -1
        # EPD hardware init start
        self.reset()

        self.ReadBusy()
        self.send_command(0x12) 
        self.ReadBusy()

        self.send_command(0x18)
        self.send_data(0x80)

        self.send_command(0x0C)
        self.send_data(0xAE)
        self.send_data(0xC7)
        self.send_data(0xC3)
        self.send_data(0xC0)
        self.send_data(0x80)

        self.send_command(0x01)
        self.send_data(int((self.height-1)%256))
        self.send_data(int((self.height-1)/256))
        self.send_data(0x02)

        self.send_command(0x3C)
        self.send_data(0x01)

        self.send_command(0x11)     
        self.send_data(0x01)

        self.send_command(0x44) 
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(int((self.width-1)%256))    
        self.send_data(int((self.width-1)/256))

        self.send_command(0x45) 
        self.send_data(int((self.height-1)%256))
        self.send_data(int((self.height-1)/256))
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x4E)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(0x4F) 
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

    def init_Fast(self):
        if (epdconfig.module_init() != 0):
            return -1
        # EPD hardware init start
        self.reset()

        self.ReadBusy()
        self.send_command(0x12) 
        self.ReadBusy()

        self.send_command(0x18)
        self.send_data(0x80)

        self.send_command(0x0C)
        self.send_data(0xAE)
        self.send_data(0xC7)
        self.send_data(0xC3)
        self.send_data(0xC0)
        self.send_data(0x80)

        self.send_command(0x01)
        self.send_data(int((self.height-1)%256))
        self.send_data(int((self.height-1)/256))
        self.send_data(0x02)

        self.send_command(0x11)     
        self.send_data(0x01)

        self.send_command(0x44) 
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(int((self.width-1)%256))    
        self.send_data(int((self.width-1)/256))

        self.send_command(0x45) 
        self.send_data(int((self.height-1)%256))
        self.send_data(int((self.height-1)/256))
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x4E)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(0x4F) 
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

        self.send_command(0x3C)
        self.send_data(0x01)

        self.send_command(0x18)
        self.send_data(0x80)

        self.send_command(0x1A)
        self.send_data(0x6A)

    def init_4GRAY(self):
        if (epdconfig.module_init() != 0):
            return -1
        # EPD hardware init start
        self.reset()

        self.ReadBusy()
        self.send_command(0x12) 
        self.ReadBusy()

        self.send_command(0x18)
        self.send_data(0x80)

        self.send_command(0x0C)
        self.send_data(0xAE)
        self.send_data(0xC7)
        self.send_data(0xC3)
        self.send_data(0xC0)
        self.send_data(0x80)

        self.send_command(0x01)
        self.send_data(int((self.height-1)%256))
        self.send_data(int((self.height-1)/256))
        self.send_data(0x02)

        self.send_command(0x11)     
        self.send_data(0x01)

        self.send_command(0x44) 
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(int((self.width-1)%256))    
        self.send_data(int((self.width-1)/256))

        self.send_command(0x45) 
        self.send_data(int((self.height-1)%256))
        self.send_data(int((self.height-1)/256))
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x4E)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(0x4F) 
        self.send_data(0x00)
        self.send_data(0x00)
        self.ReadBusy()

        self.send_command(0x3C)
        self.send_data(0x01)

        self.send_command(0x18)
        self.send_data(0x80)

        self.send_command(0x1A)
        self.send_data(0x5A)


    def getbuffer(self, image):
        img = image
        imwidth, imheight = img.size
        if(imwidth == self.width and imheight == self.height):
            img = img.convert('1')
        elif(imwidth == self.height and imheight == self.width):
            # image has correct dimensions, but needs to be rotated
            img = img.rotate(90, expand=True).convert('1')
        else:
            logger.warning("Wrong image dimensions: must be " + str(self.width) + "x" + str(self.height))
            # return a blank buffer
            return [0x00] * (int(self.width/8) * self.height)

        buf = bytearray(img.tobytes('raw'))
        # The bytes need to be inverted, because in the PIL world 0=black and 1=white, but
        # in the e-paper world 0=white and 1=black.
        # for i in range(len(buf)):
        #     buf[i] ^= 0xFF
        return buf
    
    def getbuffer_Part(self, image, width, height):
        img = image
        imwidth, imheight = img.size
        if(imwidth == width and imheight == height):
            img = img.convert('1')
        elif(imwidth == height and imheight == width):
            # image has correct dimensions, but needs to be rotated
            img = img.rotate(90, expand=True).convert('1')
        else:
            logger.warning("Wrong image dimensions: must be " + str(width) + "x" + str(height))
            # return a blank buffer
            return [0x00] * (int(width/8) * height)

        buf = bytearray(img.tobytes('raw'))
        # The bytes need to be inverted, because in the PIL world 0=black and 1=white, but
        # in the e-paper world 0=white and 1=black.
        for i in range(len(buf)):
            buf[i] ^= 0xFF
        return buf
    
    def getbuffer_4Gray(self, image):
        """Pack an L-mode image into 2-bit codes, 4 pixels per byte (MSB
        first). Vectorized with numpy; byte-identical to the original
        per-pixel Waveshare loop, which took seconds per frame on a Pi."""
        image_monocolor = image.convert('L')
        imwidth, imheight = image_monocolor.size
        arr = np.asarray(image_monocolor, dtype=np.uint8)

        if imwidth == self.width and imheight == self.height:
            logger.debug("Vertical")
        elif imwidth == self.height and imheight == self.width:
            logger.debug("Horizontal")
            arr = np.rot90(arr)  # pixel (x, y) -> (y, height - 1 - x)
        else:
            logger.warning(
                "Wrong image dimensions: must be %dx%d", self.width, self.height
            )
            return bytearray([0xFF] * (int(self.width / 4) * self.height))

        # Remap the exact driver gray levels before truncating to the top two
        # bits: 0xC0 (light gray) -> code 10, 0x80 (dark gray) -> code 01.
        remapped = arr.copy()
        remapped[arr == 0xC0] = 0x80
        remapped[arr == 0x80] = 0x40
        codes = remapped >> 6
        packed = (
            (codes[:, 0::4] << 6)
            | (codes[:, 1::4] << 4)
            | (codes[:, 2::4] << 2)
            | codes[:, 3::4]
        )
        return bytearray(packed.tobytes())

    def display(self, image):
        self.send_command(0x24)
        self.send_data2(image)

        self.TurnOnDisplay()

    def display_Base(self, image):
        self.send_command(0x24)
        self.send_data2(image)

        self.send_command(0x26)
        self.send_data2(image)

        self.TurnOnDisplay()

    def display_Fast(self, image):
        self.send_command(0x24)
        self.send_data2(image)

        self.TurnOnDisplay()

    def display_Fast_Base(self, image):
        self.send_command(0x24)
        self.send_data2(image)

        self.send_command(0x26)
        self.send_data2(image)

        self.TurnOnDisplay()


    def Clear(self):
        self.send_command(0x24)
        self.send_data2([0xFF] * int(self.width * self.height / 8))
        self.send_command(0x26)
        self.send_data2([0xFF] * int(self.width * self.height / 8))

        self.TurnOnDisplay()

    def display_Partial(self, Image, Xstart, Ystart, Xend, Yend):
        start_mod = Xstart % 8
        end_mod = Xend % 8
        if ((start_mod + end_mod == 8 and start_mod > end_mod) or
            (start_mod + end_mod == 0) or
            ((Xend - Xstart) % 8 == 0)):
            Xstart = (Xstart // 8) * 8
            Xend = (Xend // 8) * 8
        else:
            Xstart = (Xstart // 8) * 8
            if end_mod == 0:
                Xend = (Xend // 8) * 8
            else:
                Xend = ((Xend // 8) * 8) + 8

        Width = (Xend - Xstart) // 8
        Height = Yend - Ystart

        self.reset()

        self.send_command(0x18)
        self.send_data(0x80)

        self.send_command(0x3C)
        self.send_data(0x80)

        self.send_command(0x44)
        self.send_data(Xstart%256)  
        self.send_data(Xstart//256)
        self.send_data((Xend-1)%256)
        self.send_data((Xend-1)//256)		

        self.send_command(0x45)
        self.send_data(Ystart%256) 
        self.send_data(Ystart//256)
        self.send_data((Yend-1)%256)
        self.send_data((Yend-1)//256)		

        self.send_command(0x4E)
        self.send_data(Xstart%256)  
        self.send_data(Xstart//256) 

        self.send_command(0x4F)
        self.send_data(Ystart%256) 
        self.send_data(Ystart//256) 

        self.send_command(0x24)
        self.send_data2(Image)

        self.TurnOnDisplay_Partial()

    # Bit per 2-bit gray code (0=black, 1=dark gray, 2=light gray, 3=white)
    # for each controller RAM plane; the (0x24, 0x26) bit pair selects the
    # gray level: white=(1,1), light=(1,0), dark=(0,1), black=(0,0).
    # Polarity anchored by Clear(), which writes 0xFF to both planes for a
    # white screen (and matches the official Waveshare 4-gray reference).
    _PLANE_24_LUT = np.array([0, 0, 1, 1], dtype=np.uint8)
    _PLANE_26_LUT = np.array([0, 1, 0, 1], dtype=np.uint8)

    def _4gray_planes(self, image):
        """Expand a packed 4-gray buffer into the two 1-bit RAM planes.

        Vectorized with numpy; byte-identical to the original per-byte loop,
        which issued ~96k single-byte SPI transfers per refresh."""
        data = np.frombuffer(bytes(bytearray(image)), dtype=np.uint8)
        codes = np.empty((data.size, 4), dtype=np.uint8)
        codes[:, 0] = data >> 6
        codes[:, 1] = (data >> 4) & 0x03
        codes[:, 2] = (data >> 2) & 0x03
        codes[:, 3] = data & 0x03
        flat = codes.reshape(-1)
        plane_24 = np.packbits(self._PLANE_24_LUT[flat])
        plane_26 = np.packbits(self._PLANE_26_LUT[flat])
        return bytearray(plane_24.tobytes()), bytearray(plane_26.tobytes())

    def display_4GRAY(self, image):
        plane_24, plane_26 = self._4gray_planes(image)
        self.send_command(0x24)
        self.send_data2(plane_24)

        self.send_command(0x26)
        self.send_data2(plane_26)

        self.TurnOnDisplay_4GRAY()

    def sleep(self):   
        self.send_command(0x10) # DEEP_SLEEP
        self.send_data(0x01)
        
        epdconfig.delay_ms(2000)
        epdconfig.module_exit()
### END OF FILE ###
