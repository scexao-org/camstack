from ctypes import (create_string_buffer, c_uint, c_int, byref)

from camstack.core.edtdll import EdtDLL

import datetime, time
import traceback


class EdtInterfaceSerial:
    """
        Basic EDT passive interface, very dumbed down
        - Implementation of serial-over-cameralink for EDTs
        - Set the FG config file parameters dynamically (TODO)
    """
    def __init__(self, unit, channel=0, devName=b'pdv'):
        self.unit, self.channel = unit, channel
        self.pdvObj = EdtDLL.pdv_open_channel(b'pdv', unit, channel)

        self.camName = f'pdv_{unit}_{channel}'
        self.initialize()

    def initialize(self):
        self.width, self.height = self.get_image_size()
        EdtDLL.pdv_flush_fifo(self.pdvObj)

    def reset(self):
        self.initialize()

    def _serial_command(self, cmd):
        #CRED2: Confirmed and tested
        # SWITCHING FROM UTF8 to LATIN1... because ocam.
        return EdtDLL.pdv_serial_command(self.pdvObj, bytes(cmd, "latin1"))

    def _serial_wait(self, timeout, maxchars):
        #CRED2: Confirmed and tested
        return EdtDLL.pdv_serial_wait(self.pdvObj, timeout, maxchars)

    def _serial_read(self, timeout=10, nchars=5):
        #CRED2: Confirmed and tested
        revbuf = create_string_buffer(b'\000' * 40)
        n = self._serial_wait(timeout, nchars)
        out = []
        while n > 0:
            res = EdtDLL.pdv_serial_read(self.pdvObj, revbuf, nchars)
            #print ("res %s " % res)
            if res > 0:
                data = revbuf.value.decode('latin1')
                out.append(data)
                n = self._serial_wait(timeout, nchars)
            else:
                break
        res = "".join(out).strip()
        #print ("serialRead %s" % (res), " len %d" % len(res))

        if len(res) == 0:
            return ""
        if ord(res[0]) == 6:
            return res[1:]
        # Don't really know why that was there ?
        if len(res) > 1:
            return res
        raise Exception("Error in response")

    def send_command(self, cmd, base_timeout: float = 10):
        #CRED2: Confirmed and tested
        try:  # Try to flush the serial buffer, just in case.
            _ = self._serial_read()
        except:
            pass

        recRes = None
        # Number of attempts in sending the command
        for k in range(3):
            _ = self._serial_command(cmd)
            # Number of attemps at receiving the command, with exp
            # increasing timeouts
            for i in range(8):
                try:
                    recRes = self._serial_read(int(base_timeout) * 2**i)
                    if len(recRes) > 0:
                        print(f'Command {cmd}')
                        print(f'Attempted sends: {k+1}')
                        print(f'Attempted receives: {i+1}')
                        print('----')
                        return recRes
                except:
                    continue
        if recRes is None:
            raise Exception("Error in sendCommand")
        return recRes # Which is an empty string at this point

    def get_image_size(self):
        """
            Gets the size of the image from the EDT configuration.
            Warning: if we expect an 8->16 cast, things may get wrong here.
        """
        width = EdtDLL.pdv_get_width(self.pdvObj)  # n_cols
        height = EdtDLL.pdv_get_height(self.pdvObj)  # n_rows
        return height, width

    def set_image_size(self, height, width):
        """
            Sets the size of the image to the EDT config
            Things may well get wrong if we're acquiring...
        """
        EdtDLL.pdv_set_width(self.pdvObj, height)  # n_cols
        EdtDLL.pdv_get_height(self.pdvObj, width)  # n_rows
        return self.get_image_size()


class EdtInterfaceAcquisition(EdtInterfaceSerial):
    """
        A slightly beefier implementation, that supports opening buffers
        and grabbing images.

        Implements a couple timeout management methods, and image grabbing
    """
    num_buffs = 4

    def __init__(self, unit, channel=0, devName=b'pdv'):
        super().__init__(unit, channel=0, devName=b'pdv')
        self.timeouts = 0
        self.timeout = 0
        self.get_timeouts()

    def initialize(self):
        super().initialize()
        EdtDLL.pdv_multibuf(self.pdvObj, self.num_buffs)

    def get_timeout(self, timeout=1000):
        return EdtDLL.pdv_get_timeout(self.pdvObj)

    def set_timeout(self, timeout=1000):
        if self.timeout == timeout:
            return
        #WCLogger.info ("Setting timeout %.0f" % timeout)
        self.timeout = timeout
        EdtDLL.pdv_set_timeout(self.pdvObj, timeout)

    def start_images(self, n_imgs: int = 0):
        if n_imgs is None:
            n_imgs = 0
        EdtDLL.pdv_start_images(self.pdvObj, 0)

    def get_image(self, wait=False):
        """
        Reads image from EDT image buffer.
        Checks that there is no timeouts.
        Adds the newly read image into the image queue.
        """

        tstamp = (c_uint * 2)(0, 0)
        size = self.width * self.height

        if wait:
            skipped = c_int(0)
            data = EdtDLL.pdv_wait_last_image(self.pdvObj, byref(skipped))
            dmaTime = datetime.datetime.now().timestamp()
        else:
            data = EdtDLL.pdv_last_image_timed(self.pdvObj, byref(tstamp))
            dmaTime = tstamp[0] + 1E-9 * tstamp[1]

        touts = self.get_timeouts()
        print(touts)
        if touts == 0:
            data1 = [max(0, data[i]) for i in range(size)]

            return data1, dmaTime
        else:
            self.restart_timeout()

        return [], 0

    def restart_timeout(self):
        """
            Restart timeouts onboard
        """
        EdtDLL.pdv_timeout_restart(self.pdvObj, 0)
        return

    def get_timeouts(self):
        """
        Gets the number of timeouts after a readout.
        """
        timeouts = EdtDLL.pdv_timeouts(self.pdvObj)
        diff = timeouts - self.timeouts
        self.timeouts = timeouts
        return diff

    def close(self):
        """
            Attempt a clean quit (of the FG pointer)
            This should be moved to camera classes
            and called upon server death
        """
        try:
            EdtDLL.pdv_start_images(self.pdvObj, 1)
            EdtDLL.pdv_close(self.pdvObj)
        except Exception as e:
            print(e)
