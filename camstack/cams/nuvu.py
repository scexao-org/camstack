'''
    KALAO NuVu Camera driver
'''
import os,sys
import datetime, time
import json
import logging
###from struct import pack,unpack
from enum import Enum
from typing import Union


camstack_home = '/home/kalao/kalao-camstack'

sys.path.insert(0, "/home/kalao/kalao-cacao/src/pyMilk")
#sys.path.insert(0, "/home/kalao/kalaco-camstack")
sys.path.insert(0, camstack_home)

#from camstack.core.edtinterface import EdtInterfaceSerial
from camstack.core.utilities import CameraMode
from camstack.cams.edt_base import EDTCamera

class NUVU(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'GetReadoutMode', 'SetExposureTime','GetReadoutTime', 'GetExposureTime', 'SetExposureTime', 'SetCCDTemperature',
        'GetCCDTemperature', 'GetEMCalibratedGain', 'SetEMCalibratedGain', 'GetEMRawGain', 'SetEMRawGain',
        'GetAnalogicGain', 'SetAnalogicGain', 'FULL'] + \
        EDTCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'full'

    MODES = {
        # FULL 128 x 128
        FULL: CameraMode(x0=0, x1=127, y0=0, y1=127),
        0: CameraMode(x0=0, x1=127, y0=0, y1=127, fps=1500., tint=0.0006),
        1: CameraMode(x0=0, x1=65, y0=0, y1=65, fps=1500., tint=0.0006, fgsize=(70,64)),
    }

    KEYWORDS = {}
    KEYWORDS.update(EDTCamera.KEYWORDS)

    EDTTAKE_UNSIGNED = False

    class _ShutterExternal(Enum):
        NO = 0
        YES = 1

    class _Polarity(Enum):
        NEG = -1
        POS = 1

    class _ShutterMode(Enum):
        OPEN = 2
        CLOSE = -2
        AUTO= 0

    class _TriggerMode(Enum):
        EXT_H2L_EXP = -2
        EXT_H2L = -1
        INT = 0
        EXT_L2H = 1
        EXT_L2H_EXP = 2

    cfgdict = {}
    edt_iface = None
    RO_MODES=[]
    logging.basicConfig(filename=camstack_home+os.sep+'kalao_nuvu.log', format='kalao_nuvu %(asctime)s %(message)s',level=logging.DEBUG)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 1,
                 unit: int = 0,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):

        debug=1
        #basefile = os.environ['HOME'] + '/src/camstack/config/nuvu_kalao_16bit.cfg'
        basefile = camstack_home + '/config/nuvu_kalao_16bit.cfg'

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, stream_name, mode_id, unit, channel,
                           basefile, taker_cset_prio=taker_cset_prio, dependent_processes=dependent_processes)

        # ======
        # AD HOC
        # ======

        #time.sleep(120)
        success = self._update_nuvu_config(retries=5,timeout=100.)
        if not success:
            logging.error("Error updating nuvu config")
            return None

        success = self._update_romodes_list()
        if not success:
            logging.error("Error updating readout modes list")
            return None

        success = self.SetReadoutModeStr('EM_20MHz_10MHz')
        if not success:
            logging.error("Error updating readout mode")
            return None

        self.SetEMRawGain(0)
        self.SetSeqRegisters(11,4,[128,0,0,0,0,8,1,0,0,128,6])
        self.SetSeqRegisters(10,0,[131,0,0,3,128,0,0,0,0,5])
        self.SetAnalogicGain(1)
        self.SetEMCalibratedGain(1.0)
        self.SetWaitingTime(0)
        self.SetAnalogicOffset(-1000)
        self.SetCCDTemperature(-60.0)
        self.SetSeqRegisters(13,1,[1,0,1,0,67,0,0,0,1,1,5,0,64])
        self.SetBinning(2)
        self.SetExposureTime(0) # milliseconds
        self.SetWaitingTime(0)
        self.SetEMCalibratedGain(1.0)
        self.SetShutterMode(2)
        self.SetTriggerMode(0,1)
        self.SetContinuousAcquisition()

        #self.camera_shm.update_keyword('DETECTOR', "NUVU - %s"%(self.cfgdict['CCDPartNumber']))

        logging.debug(self.cfgdict)


    def _get_nuvu_response(self, response, verbose=0):
        """ convert nuvu response into a key/values dictionary """
        rlines = response.splitlines()
        logging.debug(rlines)
        if not 'OK' in rlines[-2]:
            return(False,{})
        try:
            return(True,int(rlines[0]))
        except ValueError:
            try:
                return(True,float(rlines[0]))
            except ValueError:
                #pass
                if 3 == len(rlines) and not ':' in rlines[0]: return(True,rlines[0].split())
        rlines=list(filter(lambda x:':' in x, rlines))
        rlist=[x.split(":") for x in rlines]
        rdict = dict(zip(list(map(lambda x: x[0], rlist)), list(map(lambda x: x[1], rlist))))
        if verbose:
            pass
            #print(rdict.keys())
            #print(rdict.values())
        logging.debug(rdict)
        return(True, rdict)

    def send_command(self, cmd, timeout: float = 100.):
        # Just a little bit of parsing to handle the NUVU answer
        logging.info(cmd)
        resp = EDTCamera.send_command(self, "{command}\n".format(command=cmd), base_timeout=timeout)
        logging.debug(resp)
        (success,resdict) = self._get_nuvu_response(resp)
        return(success,resdict)

    def _update_nuvu_config(self, retries: int = 3, timeout: float = 100.):
        r = 0
        while r < retries:
            resp = EDTCamera.send_command(self, "ld 0\n", base_timeout=timeout)
            if len(resp) > 0:
                break
            logging.debug("ld 0 command failed")
            r += 1
            time.sleep(30)
        else:
            logging.error("Unable to communicate with camera.")
            return None
        (success,resdict) = self._get_nuvu_response(resp)
        #(success,resdict) = self.send_command("ld 0", timeout=400.)
        if success:
            self.cfgdict.update(resdict)
        return success

    def SetReadoutModeStr(self, romode):
        if not romode in self.RO_MODES:
            return False
        (success,resdict) = self.send_command("ld %d"%(self.RO_MODES.index(romode)), timeout=400.)
        if success:
            self.camera_shm.update_keyword('DETMODE', romode)
            self.cfgdict.update(resdict)
        else:
            logging.error("Error setting Readoutmode")
        return success

    def SetReadoutModeInt(self, romode: int):
        if 0 > i and i > len(self.RO_MODES):
            return False
        (success,resdict) = self.send_command("ld %d"%(romode), timeout=400.)
        if success:
            self.camera_shm.update_keyword('DETMODE', self.RO_MODES['romode'])
            self.cfgdict.update(resdict)
        else:
            logging.error("Error setting Readoutmode")
        return success

    def _update_romodes_list(self):
        (success,resdict) = self.send_command("ls")
        if success:
            for i in range(len(resdict)):  self.RO_MODES.append(resdict[str(i)].split()[0])
        return success

    def SetSeqRegisters(self, nbreg: int = 0, start: int = 0, values = []):
        #           0    1    2    3    4    5    6    7    8    9   10   11   12   13   14
        #values = [131,   1,   0,   1,   0,  67,   0,   0,   0,   1,   1,   5,   0,  64,   6]
        #values = [130,   1,   1, 128,   0,   1, 128,   0,   0,   0,   0,   7,   4,  64,   1]
        #values = [130,   1,   1,  64,   0,   1,   0,  64,   0,   0,   0,   7,   4,  64,   1]
        #values = [130,   0,   0,  1,   0,   67,   0,  0,   0,   1,   1,   5,   0,  64,   0]

        if len(values) < nbreg:
            return 'failed'

        (success,resdict) = self.send_command("dsv 15")
        ovalues = list(map(int,resdict.values()))

        idx = start
        for i in range(nbreg):
            bval = values[i]
            (success,resdict) = self.send_command(f'ssv {idx} {bval}')
            ovalues[idx] = bval
            idx = idx+1
        (success,resdict) = self.send_command("dsv 15")
        x = set(ovalues)
        responses = list(map(int,resdict.values()))
        y = set(responses)
        if  x == y:
            print(success,resdict)
            return(success,resdict)
        return 'failed'


    def SetBinning(self, binning: int):
        (success,answer) = self.send_command(f'cdsbinmode {binning}')
        'CDS binning mode'
        if success:
            return int(answer['CDS binning mode'])
        return 'failed'


    def GetReadoutMode(self):
        (success,answer) = self.send_command("ld")
        if success:
            return(int(answer),self.RO_MODES[int(answer)])
        return 'failed'

    def GetReadoutTime(self):
        (success,answer) = self.send_command("rsrt")
        if success:
            return float(answer)
        return 'failed'

    def GetExposureTime(self):
        (success,answer) = self.send_command("se")
        if success:
            texp = float(answer)
            self.camera_shm.update_keyword('EXPTIME', texp)
            self.camera_shm.update_keyword('FRATE', 1. /texp)
            return float(answer)
        return 'failed'

    def SetExposureTime(self, texp: float): # milliseconds
        if texp > 1172812000.0:
            return self.GetExposureTime()
        (success,answer) = self.send_command(f'se {texp}')
        if success:
            return float(answer)
        return 'failed'

    def GetWaitingTime(self):
        (success,answer) = self.send_command("sw")
        if success:
            return float(answer)
        return 'failed'

    def SetWaitingTime(self, twait: float):
        if twait > 1172812000.0:
            return self.GetWaitingTime()
        (success,answer) = self.send_command(f'sw {twait}')
        if success:
            return float(answer)
        return 'failed'

    def GetExternalShutterMode(self):
        (success,answer) = self.send_command("sesm")
        if success:
            return answer
        return 'failed'

    def SetExternalShutterMode(self, smode: _ShutterMode):
        if not smode in [item.value for item in self._ShutterMode]:
            return self.GetExternalShutterMode()
        (success,answer) = self.send_command(f'sesm {smode}')
        if success:
            return answer
        return 'failed'

    def GetExternalShutterDelay(self):
        (success,answer) = self.send_command("ssd")
        if success:
            return float(answer)
        return 'failed'

    def SetExternalShutterDelay(self, sdelay: float):
        if sdelay > 1172812000.0:
            return self.GetExternalShutterDelay()
        (success,answer) = self.send_command(f'ssd {sdelay}')
        if success:
            return float(answer)
        return 'failed'

    def GetShutterMode(self):
        (success,answer) = self.send_command("ssm")
        if success:
            return answer
        return 'failed'

    def SetShutterMode(self, smode: _ShutterMode):
        if not smode in [item.value for item in self._ShutterMode]:
            return self.GetShutterMode()
        (success,answer) = self.send_command(f'ssm {smode}')
        if success:
            return answer
        return 'failed'

    def GetShutterExternal(self):
        (success,answer) = self.send_command("sesp")
        if success:
            return answer
        return 'failed'

    def SetShutterExternal(self, sext: _ShutterExternal):
        if not sext in [item.value for item in self._ShutterExternal]:
            return self.GetShutterExternal()
        (success,answer) = self.send_command(f'sesp {sext}')
        if success:
            return answer
        return 'failed'

    def GetShutterPolarity(self):
        (success,answer) = self.send_command("ssp")
        if success:
            return answer
        return 'failed'

    def SetShutterPolarity(self, spol: _Polarity):
        if not spol in [item.value for item in self._Polarity]:
            return self.GetShutterPolarity()
        (success,answer) = self.send_command(f'ssp {spol}')
        if success:
            return answer
        return 'failed'

    def GetFirePolarity(self):
        (success,answer) = self.send_command("sfp")
        if success:
            return answer
        return 'failed'

    def SetFirePolarity(self, fpol: _Polarity):
        if not fpol in [item.value for item in self._Polarity]:
            return self.GetFirePolarity()
        (success,answer) = self.send_command(f'sfp {fpol}')
        if success:
            return answer
        return 'failed'

    def GetTriggerMode(self):
        (success,answer) = self.send_command("stm")
        if success:
            self.camera_shm.update_keyword('EXTTRIG', str(answer))
            return answer
        return 'failed'

    def SetTriggerMode(self, tmode: _TriggerMode, nimages: int):
        if not tmode in [item.value for item in self._TriggerMode]:
            return self.GetTriggerMode()
        (success,answer) = self.send_command(f'stm {tmode} {nimages}')
        if success:
            return answer
        return 'failed'

    def  GetCtrlTemperature(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['GetTempCtrlCmd']))
        if success:
            return(float(answer['0']))
        return 'failed'

    def  GetCCDTemperature(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['GetTempCCDCmd']))
        if success:
            temp = float(answer['1'])
            self.camera_shm.update_keyword('DET-TMP', temp + 273.15)
            return(temp)
        return 'failed'

    def GetSetCCDTemperature(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['GetSetTempCCDCmd']))
        if success:
            return float(answer['1'])
        return 'failed'

    def SetCCDTemperature(self, value: float):
        minv = float(self.cfgdict['TempCCDRange'].split(',')[0])
        maxv = float(self.cfgdict['TempCCDRange'].split(',')[1])
        if maxv < value and value < minv:
            return(self.GetCCDTemperature())
        cmdstring=self.cfgdict['SetTempCCDCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return float(answer['1'])
        return 'failed'

    def GetEMRawGain(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['EMGetRawGainCmd']))
        if success:
            return(int(answer['4'].split()[0]),answer['4'].split(' ',2)[2])
        return 'failed'

    def GetAnalogicGain(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['AnalogicGetGainCmd']))
        if success:
            gain = int(answer['Gain 1'])
            self.camera_shm.update_keyword('GAIN', gain)
            return gain
        return 'failed'

    def GetAnalogicOffset(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['AnalogicGetOffsetCmd']))
        if success:
            return int(answer['CDS offset'])
        return 'failed'

    def SetAnalogicGain(self, value: int):
        if not str(value) in self.cfgdict['AnalogicGainRange']:
            return(self.GetAnalogicGainCmd())
        cmdstring=self.cfgdict['AnalogicSetGainCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return int(answer['Gain 1'])
        return 'failed'

    def SetAnalogicOffset(self, value: int):
        minv = int(self.cfgdict['AnalogicOffsetRange'].split(',')[0])
        maxv = int(self.cfgdict['AnalogicOffsetRange'].split(',')[1])
        if maxv < value and value < minv:
            return(self.GetAnalogicOffset())
        cmdstring=self.cfgdict['AnalogicSetOffsetCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return int(answer['CDS offset'])
        return 'failed'

    def SetEMRawGain(self, value: int):
        minv = int(self.cfgdict['EMRawGainRange'].split(',')[0])
        maxv = int(self.cfgdict['EMRawGainRange'].split(',')[1])
        maxv = 200
        logging.debug(f'SetEMRawGain({minv} <= {value} <= {maxv})')
        if maxv < value and value < minv:
            return(self.GetEMRawGain())
        cmdstring=self.cfgdict['EMSetRawGainCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return(int(answer['4'].split()[0]),answer['4'].split(' ',2)[2])
        return 'failed'

    def GetEMCalibratedGain(self):
        (success,answer) = self.send_command("seg")
        if success:
            return float(answer['emgain'].split(',')[0])
        return 'failed'

    def SetEMCalibratedGain(self, emcgain: float):
        minv = 1.0
        maxv = 5000.0
        ccdtemp = self.GetCCDTemperature()
        mint = float(self.cfgdict['EmGainCalibrationTemperatureRange'].split(',')[0])
        maxt = float(self.cfgdict['EmGainCalibrationTemperatureRange'].split(',')[1])
        logging.debug(f'SetEMCalibratedGain({mint} <= {ccdtemp} <= {maxt})')
        if maxt < ccdtemp and ccdtemp < mint:
            return(self.GetEMCalibratedGain())
        logging.debug(f'SetEMCalibratedGain({minv} <= {emcgain} <= {maxv})')
        if maxv < emcgain and emcgain < minv:
            return(self.GetEMCalibratedGain())
        (success,answer) = self.send_command(f'seg {emcgain}\n')
        if success:
            return float(answer['emgain'].split(',')[0])
        return 'failed'

    def SetContinuousAcquisition(self):
        (success,answer) = self.send_command("re -1")
        if success:
            return answer
        return 'failed'

    def AbortAcquisition(self):
        (success,answer) = self.send_command("abort")
        if success:
            return answer
        return 'failed'


    def mytemptests(self):
        print(self.SetCCDTemperature(-59.5))
        print(self.GetCtrlTemperature())
        print(self.GetSetCCDTemperature())
        print(self.GetCCDTemperature())

    def mydivtests(self):
        print(self.GetReadoutMode())
        print(self.GetReadoutTime())
        print(self.GetExposureTime())
        print(self.SetExposureTime(0))
        print(self.SetShutterMode(3.4))
        print(self.GetShutterMode())

    def mytrigtests(self):
        print(self.GetTriggerMode())
        print(self.SetTriggerMode(2,1))
        print(self.GetTriggerMode())
        print(self.SetTriggerMode(0,1))
        print(self.GetTriggerMode())

    def mygaintests(self):
        print(self.GetEMRawGain())
        print(self.SetEMRawGain(0))
        print(self.GetEMRawGain())
        print(self.GetAnalogicGain())
        print(self.SetAnalogicGain(1))
        print(self.GetAnalogicGain())
        print(self.GetAnalogicOffset())
        print(self.SetAnalogicOffset(-1000))
        print(self.GetAnalogicOffset())
        print(self.GetEMCalibratedGain())

class Kalao(NUVU):

    INTERACTIVE_SHELL_METHODS = [] + NUVU.INTERACTIVE_SHELL_METHODS

    MODES = {}
    MODES.update(NUVU.MODES)

    KEYWORDS = {}
    KEYWORDS.update(NUVU.KEYWORDS)

    def _fill_keywords(self):
        NUVU._fill_keywords(self)

        # Override detector name
        self.camera_shm.update_keyword('DETECTOR', 'NUVU - KALAO')

# Quick shorthand for testing

if __name__ == "__main__":
    cam = Kalao(name='nuvu', stream_name='nuvu0', unit=0, channel=0)
    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
    #kalao.mytemptests()
    #kalao.mydivtests()
    #kalao.mytrigtests()
    #kalao.mygaintests()





