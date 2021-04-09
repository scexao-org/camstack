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
        return EdtDLL.pdv_serial_command(self.pdvObj, bytes(cmd, "UTF-8"))

    def _serial_wait(self, timeout, maxchars):
        #CRED2: Confirmed and tested
        return EdtDLL.pdv_serial_wait(self.pdvObj, timeout, maxchars)

    def _serial_read(self, timeout=100, nchars=32):
        #CRED2: Confirmed and tested
        revbuf = create_string_buffer(b'\000' * 40)
        n = self._serial_wait(timeout, nchars)
        out = []
        while n > 0:
            res = EdtDLL.pdv_serial_read(self.pdvObj, revbuf, nchars)
            #print ("res %s " % res)
            if res > 0:
                data = revbuf.value.decode('UTF-8')
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
        if len(res) > 3:
            return res
        raise Exception("Error in response")

    def send_command(self, cmd):
        #CRED2: Confirmed and tested
        try:  # Try to flush the serial buffer, just in case.
            _ = self._serial_read()
        except:
            pass
        for _ in range(3):
            try:
                _ = self._serial_command(cmd)
                recRes = self._serial_read()
                ###WCLogger.info ("Sent res=%s, rec res=%s" % (sentRes, recRes))
                return recRes
            except:
                ##WCLogger.error ("warning while sending " + cmd + " " + str(e))
                continue
        raise Exception("Error in sendCommand")

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

    #=========================================================
    #
    # FIXME METHODS - stuff that should move to camera classes
    # (This is CRED2 stuff)
    #=========================================================


    def getVersion(self):
        '''
        CRED2: returns single, printable string with all version values
        ie: use print(getVersion()) to print the result

        # FIXME: camera function
        '''
        #CRED2: Confirmed and tested
        res = self.send_command("version")
        return "".join(res.split('\r'))

    def setExtMode(self, mode=0):
        """
        returns early if invalid mode is provided
        mode = 0, internal
        mode = 2, external

        # FIXME: camera function
        """
        #CRED2: Confirmed and tested
        if mode == 0:
            mdstr = "off"
        elif mode == 2:
            mdstr = "on"
        else:
            return mode
        _ = self.send_command("set extsynchro " + mdstr)
        #WCLogger.info("Set external mode %d" % mode)
        self.extMode = mode
        return mode

    def getExtMode(self):
        #CRED2: Confirmed and tested
        """
            FIXME: camera function
        """
        res = self.send_command("extsynchro")
        return " ".join(res.split()[1:])

    def getTemperatures(self, full=None):
        """
        Default is to return just sensor temperature
        Returns
            full = None: (float) just sensor temperature
            full != None: (str) 
                single, printable string with all temp values
                ie: use print(getVersion()) to print the result

        FIXME: camera command
        """
        #CRED2: Confirmed and tested
        if full is None:
            res = self.send_command("temperatures snake raw")
            return float(res.split()[0])
        else:
            res = self.send_command("temperatures")
            return "".join(res.split('\r'))

    def getTempSetpoint(self):
        '''
        Returns setpoint for the camera's sensor (float)
        # FIXME: camera command
        '''
        #CRED2: Confirmed and tested
        res = self.send_command("temperatures snake setpoint raw")
        return float(res.split()[0])

    def setTemperature(self, degC):
        '''
        Set the temperature for the camera (sensor)
        degC: temperature to set in Celsius
        # FIXME: camera command
        '''
        #CRED2: Confirmed and tested
        #WCLogger.info("Setting temp to %d degC" % degC)
        self.send_command("set temperatures snake " + str(degC))