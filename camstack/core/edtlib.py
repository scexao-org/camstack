#
# 11-2020: This file reduced to ONLY manage the DLL import and binding
# See the original in hardw-cred2
#
#
# Former EDTIf code (python implementation of CRED2) moved to various files: edtcamera.py, cred2.py.
#

import os
from ctypes import *

_EdtLib = CDLL("/opt/EDTpdv/libpdv.so")


def _initEdtIF():
    '''
        Initialize the API signatures

        Dec 2020 - using driver version 5.5.10.0 [Nov 4th 2020 release]
        - may need to check signatures if some stuff is broken
        https://edt.com/api/group__dv.html

    '''
    _EdtLib.pdv_close.argtypes = [c_void_p]
    
    _EdtLib.pdv_enable_external_trigger.argtypes = [c_void_p, c_int]
    
    _EdtLib.pdv_flush_fifo.argtypes = [c_void_p]
    
    _EdtLib.pdv_get_height.argtypes = [c_void_p]
    _EdtLib.pdv_get_height.restype = c_int
    
    _EdtLib.pdv_get_timeout.argtypes = [c_void_p, c_int]
    _EdtLib.pdv_get_timeout.restype = c_int
    
    _EdtLib.pdv_get_width.argtypes = [c_void_p]
    _EdtLib.pdv_get_width.restype = c_int
    
    _EdtLib.pdv_last_image_timed.argtypes = [c_void_p, c_void_p]
    _EdtLib.pdv_last_image_timed.restype = POINTER(c_short)
    
    _EdtLib.pdv_multibuf.argtypes = [c_void_p, c_int]
    
    _EdtLib.pdv_open_channel.argtypes = [c_char_p, c_int, c_int]
    _EdtLib.pdv_open_channel.restype = c_void_p

    _EdtLib.pdv_serial_command.argtypes = [c_void_p, c_char_p]
    _EdtLib.pdv_serial_command.restype = c_int
    
    _EdtLib.pdv_serial_read.argtypes = [c_void_p, c_char_p, c_int]
    _EdtLib.pdv_serial_read.restype = c_int
    
    _EdtLib.pdv_serial_wait.argtypes = [c_void_p, c_int, c_int]
    _EdtLib.pdv_serial_wait.restype = c_int
    
    _EdtLib.pdv_set_exposure.argtypes = [c_void_p, c_int]
    
    _EdtLib.pdv_set_timeout.argtypes = [c_void_p, c_int]
    
    _EdtLib.pdv_start_images.argtypes = [c_void_p, c_int]
    
    _EdtLib.pdv_timeout_restart.argtypes = [c_void_p, c_int]
    
    _EdtLib.pdv_timeouts.argtypes = [c_void_p]
    _EdtLib.pdv_timeouts.restype = c_int
    
    _EdtLib.pdv_wait_image_timed.argtypes = [c_void_p, c_void_p]
    _EdtLib.pdv_wait_image_timed.restype = POINTER(c_short)
    
    _EdtLib.pdv_wait_last_image.argtypes = [c_void_p, c_void_p]
    _EdtLib.pdv_wait_last_image.restype = POINTER(c_short)

_initEdtIF() # Called once and for all upon module import

TIMEOUT_OFFSET = 15000


'''
    dec 2020: Unused, see EDTCamera and subclasses in milk-org/camstack
'''
class EdtIF:
    numbuffs = 4

    def __init__(self, devName='pdv'):
        """
        """
        self.open(0, 0, devName) # FIXME UNIT AND CHANNEL

        self.camName = devName # Useful ? self.devName too
        self.blackColumns = 0
        self.darkColumns = 0
        self.initialize()
        self.getTimeouts()        
        self.getInfo()


    def open(self, unit, channel, devName):
        #CRED2: Confirmed and tested
        self.unit, self.channel, self.devName = unit, channel, devName
        self.pdvObj = _EdtLib.pdv_open_channel(devName, unit, channel)

    def initialize(self):
        #CRED2: Confirmed and tested
        self.stopContinuousMode()
        _EdtLib.pdv_multibuf(self.pdvObj, self.numbuffs)
        self.width, self.height = self.getImageSize()
        self.expTime = 0
        self.timeouts = 0
        self.timeout = 0
        self.extMode = 0
        self.hdBinning = 1
        self.setExtMode(0)      #CRED2 should work w/ internal trigger
                                    #As such, use 0, NOT 2
        ##WCLogger.info("Little Joe version " + self.getVersion())
        #self.setProgNum(0)     #CRED2: Not needed, see function
        _EdtLib.pdv_flush_fifo(self.pdvObj)
        self.setExposureTime(.05) 
        #self.startInfoReaderThread() #CRED2: Not needed, see function
        self.startContinuousMode()
        self.startReaderThread()
        self.getLastImage(wait=True) 
        self.enableTriggers(0)
        #self._startFreeRun()
        return    

    def reset (self):
        self.initialize()

    def _serialCommand(self, cmd):
        #CRED2: Confirmed and tested
        return _EdtLib.pdv_serial_command(self.pdvObj, bytes(cmd, "UTF-8"))

    def _serialWait (self, timeout, maxchars):
        #CRED2: Confirmed and tested
        return _EdtLib.pdv_serial_wait(self.pdvObj, timeout, maxchars)

    def _serialRead(self, timeout=100, nchars=32):
        #CRED2: Confirmed and tested
        revbuf = create_string_buffer(b'\000' * 40)
        n = self._serialWait(timeout, nchars) 
        out = []
        while n > 0:
            res = _EdtLib.pdv_serial_read(self.pdvObj, revbuf, nchars)
            #print ("res %s " % res)
            if res > 0:
                data = revbuf.value.decode('UTF-8')
                out.append (data)
                n = self._serialWait(timeout, nchars)
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
        raise Exception ("Error in response")

    def _sendCommand(self, cmd):
        #CRED2: Confirmed and tested
        with self.lockComm:
            return self._sendCommandLocked(cmd)
            
    def _sendCommandLocked(self, cmd):
        #CRED2: Confirmed and tested        
        try:
            res = self._serialRead() 
        except Exception as e:
            pass
        for i in range(3):
            try :
                sentRes = self._serialCommand(cmd)
                recRes = self._serialRead()
                ###WCLogger.info ("Sent res=%s, rec res=%s" % (sentRes, recRes))
                return recRes
            except Exception as e:
                ##WCLogger.error ("warning while sending " + cmd + " " + str(e))
                continue
        raise Exception ("Error in sendCommand")

    def getVersion (self):
        '''
        CRED2: returns single, printable string with all version values
        ie: use print(getVersion()) to print the result
        '''
        #CRED2: Confirmed and tested
        res = self._sendCommand("version")
        return "".join(res.split('\r'))

    def setExtMode(self, mode=0):
        """
        returns early if invalid mode is provided
        mode = 0, internal
        mode = 2, external
        """
        #CRED2: Confirmed and tested
        if mode == 0:
            mdstr = "off"
        elif mode == 2:
            mdstr = "on"
        else:
            return mode
        res = self._sendCommand("set extsynchro " + mdstr)
        #WCLogger.info("Set external mode %d" % mode)
        self.extMode = mode
        return mode

    def getExtMode (self):
        #CRED2: Confirmed and tested
        res = self._sendCommand("extsynchro")
        return " ".join (res.split()[1:])
        
    def setRepMode(self, rep=0):
        """
        Sets the number of additional repetition of the accumulation sequence.
        rep=0 means 1 time
        """
        #CRED2: Not needed for CRED2
        #CRED2 has no command to repeat captures like this, maybe IMRO
        #res = self._sendCommand("@REP %d" %rep) 
        pass

    def getRepMode(self):
        #CRED2: Not needed; no equivalent command
            #Though maybe IMRO is this, not sure
        #res = self._sendCommand("@REP?")
        #return int(self._parseResponse(res)[0])
        pass


    def getTemperatures (self, full=None):
        """
        Default is to return just sensor temperature
        Returns
            full = None: (float) just sensor temperature
            full != None: (str) 
                single, printable string with all temp values
                ie: use print(getVersion()) to print the result
        """
        #CRED2: Confirmed and tested
        if full is None:
            res = self._sendCommand("temperatures snake raw")
            return float(res.split()[0])
        else:
            res = self._sendCommand("temperatures")
            return "".join(res.split('\r'))
        
    def getTempSetpoint (self):
        '''
        Returns setpoint for the camera's sensor (float)
        '''
        #CRED2: Confirmed and tested
        res = self._sendCommand("temperatures snake setpoint raw")
        return float(res.split()[0])
        
    def setTemperature (self, degC):
        '''
        Set the temperature for the camera (sensor)
        degC: temperature to set in Celsius
        '''
        #CRED2: Confirmed and tested
        #WCLogger.info("Setting temp to %d degC" % degC)
        self._sendCommand("set temperatures snake " + str(degC))
        
    def getTimeout (self, timeout=1000):
        return _EdtLib.pdv_get_timeout (self.pdvObj)

    def setTimeout (self, timeout=1000):
        if self.timeout == timeout:
            return
        #WCLogger.info ("Setting timeout %.0f" % timeout)
        self.timeout = timeout
        _EdtLib.pdv_set_timeout (self.pdvObj, timeout)

    def _startFreeRun(self):
        _EdtLib.pdv_start_images(self.pdvObj, 0)

    def _startImage(self, nimgs=1):
        _EdtLib.pdv_start_images(self.pdvObj, nimgs)

    def _getImage (self, wait=False):
        #CRED2: Confirmed and tested
        def ts2str (timeStamp, ndigits=11):
            dtime = datetime.datetime.fromtimestamp(timeStamp)
            return dtime.strftime('%H:%M:%S.%f')[:ndigits]
        """
        Reads image from EDT image buffer.
        Checks that there is no timeouts.
        Adds the newly read image into the image queue.
        """
        
        tstamp = (c_uint * 2)(0, 0)
        size = self.width * self.height

        if wait:
            skipped = c_int(0)
            data = _EdtLib.pdv_wait_last_image(self.pdvObj, byref(skipped))
            dmaTime = datetime.datetime.now().timestamp()
        else:
            data = _EdtLib.pdv_last_image_timed(self.pdvObj, byref(tstamp))
            dmaTime = tstamp[0] + 1E-9 * tstamp[1]

        touts = self.getTimeouts() 
        if touts == 0:            
            data1 = [max(0,data[i]) for i in range(size)]
            ##WCLogger.info ("lowest %d " % min(data1))
            ##WCLogger.info ("Read image " + ts2str(dmaTime))
                     
            return data1, dmaTime
        else:
            #WCLogger.warn("Timeouts= %d" % (touts))            
            self.restartTimeout () 
            
        #WCLogger.warn("Out _getImage with error")
        
        return [], 0
 
    def _waitForExposure(self):
        #CRED2: Confirmed and tested
        start = datetime.datetime.now().timestamp()       
        
        data, ts = self.imageBuffer
        while start > ts:
            if self.expTime >= 1:
                time.sleep(0.5)
            else:
                time.sleep(self.expTime)
            data, ts = self.imageBuffer
            if ts == 0:
                break
            
        now = datetime.datetime.now().timestamp()    
        return now - start

    def waitForExposure (self):
        #CRED2: Confirmed and tested
        wtime = self._waitForExposure()
        #WCLogger.info("Waited for %.2f s" % wtime)
        
                            
    def getLastImage (self, wait=False):
        #CRED2: Confirmed and tested
        try:
            if wait:
                #self.imageBuffer = self._getImage(wait=True)
                self.waitForExposure()
            return self.imageBuffer
        except Exception as e:
            traceback.print_exc()
            #WCLogger.info("GetLastImage failed " + str(e))
            return [], 0

    def restartTimeout(self):
        _EdtLib.pdv_timeout_restart(self.pdvObj, 0)
        if self.continuousMode:
            self._startFreeRun()
        else:
            self._startImage(1)
        #WCLogger.warning ("Restarting after timeout " + str(self.timeout))
        return 

    def enableTriggers(self, flags=0):
        """
        This is to allow the external control.
        Not sure if really needed.
        flag 0: off, 1: photo trigger, 
            2: field ID trigger (not for PCI C-Link)
        """
        #CRED2: We don't use triggers but I kept this in just in case the 
            #FG boots into trigger mode or something. ie. probs not needed
        _EdtLib.pdv_enable_external_trigger (self.pdvObj, flags)
        
    def getTimeouts(self):
        """
        Gets the number of timeouts after a readout.
        """
        timeouts = _EdtLib.pdv_timeouts(self.pdvObj)
        diff = timeouts - self.timeouts
        self.timeouts = timeouts
        return diff

    def getImageSize(self):
        """
        Gets the size of the image from the EDT configuration.
        """
        width =_EdtLib.pdv_get_width(self.pdvObj)
        height =_EdtLib.pdv_get_height(self.pdvObj)
        return width, height

    def close(self):
        """
        Puts the camera in internal mode before quiting.
        """
        try:
            self.setSeq(1)
            #self.setExtMode(0)
            _EdtLib.pdv_start_images(self.pdvObj, 1)
            _EdtLib.pdv_close(self.pdvObj)
        except:
            pass