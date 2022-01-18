import sys
import datetime, time
import json
from enum import Enum
from typing import Union

sys.path.insert(0, "/home/kalao/kalao-cacao/src/pyMilk")

from camstack.core.edtinterface import EdtInterfaceSerial
from camstack.core.utilities import CameraMode
from camstack.cams.edt_base import EDTCamera

class NUVU(EDTCamera):

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

    def __my_init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 0,
                 unit: int = 0,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):
        pass

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 0,
                 unit: int = 0,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):

        debug=0
        self.edt_iface = EdtInterfaceSerial(unit, channel)

        res = self.edt_iface.send_command("ld 0\n")
        (success,self.cfgdict) = self._get_nuvu_response(res,verbose=0)
        if not success:
            return None

        res = self.edt_iface.send_command("ls\n")
        (success,moddict) = self._get_nuvu_response(res, verbose=0)
        if success:
            for i in range(len(moddict)):  self.RO_MODES.append(moddict[str(i)].split()[0])

        res = self.edt_iface.send_command("ld 4\n",base_timeout=400)
        (success,resdict) = self._get_nuvu_response(res, verbose=0)
        if success:
            self.cfgdict.update(resdict)
        else:
            return None
        if debug:
            print(self.cfgdict)

    def _get_nuvu_response(self, response, verbose=0):
        """ convert nuvu response into a key/values dictionary """
        rlines = response.splitlines()
        if not 'OK' in rlines[-2]: return(False,{})
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
            #print(rdict.keys())
            #print(rdict.values())
            print(rdict)
        return(True, rdict)

    def send_command(self, cmd, verbose=0):
        # Just a little bit of parsing to handle the NUVU answer
        if verbose:
            print(cmd)
        resp = EDTCamera.send_command(self, "{command}\n".format(command=cmd))
        (success,resdict) = self._get_nuvu_response(resp)
        return(success,resdict)

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
            return float(answer)
        return 'failed'

    def SetExposureTime(self, texp: float):
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
            return(float(answer['1']))
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

    def GetAnalogicGain(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['AnalogicGetGainCmd']))
        if success:
            return int(answer['Gain 1'])

    def GetAnalogicOffset(self):
        (success,answer) = self.send_command("{cmd}".format(cmd=self.cfgdict['AnalogicGetOffsetCmd']))
        if success:
            return int(answer['CDS offset'])

    def SetAnalogicGain(self, value: int):
        if not str(value) in self.cfgdict['AnalogicGainRange']:
            return(self.GetAnalogicGainCmd())
        cmdstring=self.cfgdict['AnalogicSetGainCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return int(answer['Gain 1'])

    def SetAnalogicOffset(self, value: int):
        minv = int(self.cfgdict['AnalogicOffsetRange'].split(',')[0])
        maxv = int(self.cfgdict['AnalogicOffsetRange'].split(',')[1])
        if maxv < value and value < minv:
            return(self.GetAnalogicOffset())
        cmdstring=self.cfgdict['AnalogicSetOffsetCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return int(answer['CDS offset'])

    def SetEMRawGain(self, value: int):
        minv = int(self.cfgdict['EMRawGainRange'].split(',')[0])
        maxv = int(self.cfgdict['EMRawGainRange'].split(',')[1])
        if maxv < value and value < minv:
            return(self.GetEMRawGain())
        cmdstring=self.cfgdict['EMSetRawGainCmd']%(value)
        (success,answer) = self.send_command(f"{cmdstring}")
        if success:
            return(int(answer['4'].split()[0]),answer['4'].split(' ',2)[2])

    def GetEMCalibratedGain(self):
        (success,answer) = self.send_command("seg")
        if success:
            return float(answer['emgain'].split(',')[0])

    def SetEMCalibratedGain(self, emcgain: float):
        minv = 1.0
        maxv = 5000.0
        ccdtemp = self.GetCCDTemperature()
        mint = float(self.cfgdict['EmGainCalibrationTemperatureRange'].split(',')[0])
        maxt = float(self.cfgdict['EmGainCalibrationTemperatureRange'].split(',')[1])
        if maxt < ccdtemp and ccdtemp < mint:
            return(self.GetEMCalibratedGain())
        if maxv < emcgain and emcgain < minv:
            return(self.GetEMCalibratedGain())
        (success,answer) = self.send_command(f'seg {emcgain}\n')
        if success:
            return float(answer['emgain'])

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

kalao=NUVU(name='ḱalao', stream_name='nuvucam00', unit=0, channel=0)
#kalao.mytemptests()
#kalao.mydivtests()
#kalao.mytrigtests()
#kalao.mygaintests()



