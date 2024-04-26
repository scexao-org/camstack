'''
    Manage the ocam
'''
from typing import List, Optional as Op, Tuple

import os
import logging as logg

from camstack.cams.edtcam import EDTCamera
from camstack.core import utilities as util

from pyMilk.interfacing.isio_shmlib import SHM


class OCAM2K(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
            'set_binning', 'gain_protection_reset', 'set_gain', 'get_gain',
            'set_synchro', 'set_fps', 'get_temperature', 'toggle_cooling',
            'set_temperature_setpoint'
    ] + EDTCamera.INTERACTIVE_SHELL_METHODS

    # For ocam, the CameraMode content is *not* used for the camera setup, only the FG setup
    # yapf: disable
    MODES = {
            # Ocam full, unbinned
            1: util.CameraMode(x0=0, x1=239, y0=0, y1=239, binx=1, biny=1,
                               fgsize=(1056 // 2, 121)),
            # Ocam bin x2 - numbering (1,3) is from First Light.
            3: util.CameraMode(x0=0, x1=239, y0=0, y1=239, binx=2, biny=2,
                               fgsize=(1056 // 2, 62)),
    }
    # yapf: enable

    KEYWORDS = {
            'FILTER01': ('UNKNOWN', 'PyWFS filter state', '%-16s', 'FILTR'),
            'PICKOFF1': ('UNKNOWN', 'PyWFS pickoff state', '%-16s', 'PICKO'),
    }
    KEYWORDS.update(EDTCamera.KEYWORDS)

    EDTTAKE_CAST = True
    EDTTAKE_UNSIGNED = True

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = 'x_P'

    def __init__(self, name: str, mangled_stream_name: str,
                 final_stream_name: str, binning: bool = True, unit: int = 3,
                 channel: int = 0,
                 taker_cset_prio: util.Typ_tuple_cset_prio = ('system', None),
                 dependent_processes: List[util.DependentProcess] = []) -> None:

        # Allocate and start right in the appropriate binning mode

        mode_id = (1, 3)[binning]
        basefile = os.environ['HOME'] + '/src/camstack/config/ocam_full.cfg'

        self.synchro = True
        self.STREAMNAME_ocam2d = final_stream_name

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, mangled_stream_name, mode_id, unit,
                           channel, basefile, taker_cset_prio=taker_cset_prio,
                           dependent_processes=dependent_processes)

        # ======
        # AD HOC
        # ======

        # Issue a few standards for OCAM
        self.send_command_parsed(
                'interface 0')  # Disable verbosity to be able to parse temp
        self.toggle_cooling(True)
        self.set_temperature_setpoint(-45.0)
        self.send_command_parsed('led off')
        self.send_command_parsed('temp reset')
        self.gain_protection_reset()
        self.set_gain(1)
        #self.set_synchro(True)  # Is called by the setmode in the constructor.

    # =====================
    # AD HOC PREPARE CAMERA
    # =====================

    def prepare_camera_for_size(self,
                                mode_id: Op[util.Typ_mode_id] = None) -> None:
        logg.debug('prepare_camera_for_size @ OCAM2K')

        # This function called during the EDTCamera.__init__ from self.__init__

        # The "interface 0" in the constructor does not happen early enough.
        # We need format=False because if the camera was verbose til now, output is not yet parsable.
        self.send_command_parsed('interface 0')

        if mode_id is None:
            mode_id = self.current_mode_id

        # Not really handling fps/tint for the OCAM, we just assume an ext trigger
        if mode_id == 1:
            self.send_command_parsed('binning off')
        elif mode_id == 3:
            self.send_command_parsed('binning on')

        super().prepare_camera_for_size(mode_id)

        # AD HOC PREPARE DEPENDENTS
        # Change the argument to ocam_decode
        for dep_proc in self.dependent_processes:
            if 'decode' in dep_proc.cli_cmd:
                dep_proc.cli_args = [mode_id]

    def prepare_camera_finalize(self,
                                mode_id: Op[util.Typ_mode_id] = None) -> None:
        logg.debug('prepare_camera_finalize @ OCAM2K')

        if mode_id is None:
            mode_id = self.current_mode_id

        # Changing the binning trips the external sync.
        self.set_synchro(self.synchro)

    def send_command_parsed(self, cmd: str,
                            base_timeout: float = 100.) -> List[str]:
        # Just a little bit of parsing to handle the OCAM format
        # We override the method signature from the superclass.
        logg.debug(f'OCAM2K send_command: "{cmd}"')

        ret_str = self.send_command(cmd, base_timeout)
        wherechevron = ret_str.index('>')
        ret_split = ret_str[wherechevron + 2:-1].split('][')
        return ret_split

    def _fill_keywords(self) -> None:
        # Do a little more filling than the subclass after changing a mode
        # And call the thread-polling function
        #TODO: thread temp polling

        EDTCamera._fill_keywords(self)

        self._set_formatted_keyword('DETECTOR', 'OCAM2K (RENO)')
        self._set_formatted_keyword('DET-SMPL', 'GlobRstSingle')
        self._set_formatted_keyword('DETPXSZ1', 0.024)
        self._set_formatted_keyword('DETPXSZ2', 0.024)

        self._set_formatted_keyword('BIN-FCT1', self.current_mode.binx)
        self._set_formatted_keyword('BIN-FCT2', self.current_mode.biny)

        self._set_formatted_keyword('F-RATIO', 0.0)  # FIXME
        self._set_formatted_keyword('INST-PA', -360.0)  # FIXME

        self._set_formatted_keyword('CROPPED',
                                    False)  # Ocam bins but never crops.
        self._set_formatted_keyword('DET-NSMP', 1)

        # Additional fill-up of the camera state
        self.get_gain()  # Sets 'DETGAIN'

        # Call the stuff that we can't know otherwise
        self.poll_camera_for_keywords()  # Sets 'DET-TMP'

    def poll_camera_for_keywords(self) -> None:
        if self.HAS_REDIS:
            try:
                with self.RDB.pipeline() as pipe:
                    pipe.hget('X_PYWFLT', 'value')
                    pipe.hget('X_PYWPKO', 'value')
                    vals = pipe.execute()
                self._set_formatted_keyword('FILTER01', vals[0])
                self._set_formatted_keyword('PICKOFF1', vals[1])
            except:
                pass  # TODO some proper logging.log() some day.
        self.get_temperature()

    # ===========================================
    # AD HOC METHODS - TO BE BOUND IN THE SHELL ?
    # ===========================================

    def set_binning(self, binning: bool) -> None:
        self.set_camera_mode((1, 3)[binning])

    def gain_protection_reset(self) -> None:
        logg.warning('gain_protection_reset')
        self.send_command_parsed('protection reset')

    def set_gain(self, gain: int) -> int:
        res = self.send_command_parsed(f'gain {gain}')
        val = int(res[0])
        self._set_formatted_keyword('DETGAIN', val)
        logg.info(f'set_gain: {val}')
        return val

    def get_gain(self) -> int:
        res = self.send_command_parsed('gain')
        val = int(res[0])
        self._set_formatted_keyword('DETGAIN', val)
        logg.info(f'get_gain: {val}')
        return val

    def set_synchro(self, val: bool) -> None:
        val = bool(val)
        self.send_command_parsed(f'synchro {("off","on")[val]}')
        self.synchro = val
        self._set_formatted_keyword('EXTTRIG', val)
        logg.info(f'set_synchro: {self.synchro}')

    def get_fps(self) -> float:
        res = self.send_command_parsed('fps')
        val = float(res[0])
        self._set_formatted_keyword('FRATE', val)
        logg.info(f'get_fps: {val}')
        return val

    def set_fps(self, fps: float) -> float:
        # 0 sets maxfps
        if self.synchro:
            raise AssertionError('No fps set in synchro mode')
        res = self.send_command_parsed(f'fps {int(fps)}')
        if len(res) == 1:  # Success
            val = float(res[0])
        else:  # Retcode + value
            logg.warning(f'set_fps failure {int(fps)} not accepted')
            return self.get_fps()

        self._set_formatted_keyword('FRATE', val)
        logg.info(f'set_fps: {val}')
        return val

    def get_temperature(self) -> float:
        val = self._get_temperature()[0]
        logg.info(f'get_temperature: {val}')
        return val

    def _get_temperature(self) -> Tuple[float, float]:
        ret = self.send_command_parsed('temp')
        # Expected raw return: <1>[-45.2][23][13][24][0.1][9][12][-450][1][10594]
        temps = [float(s) for s in ret]

        self.is_cooling = bool(temps[8])
        self._set_formatted_keyword('DET-TMP', temps[0] + 273.15)
        return temps[0], temps[7] / 10.  # temp, setpoint

    def toggle_cooling(self, cooling: Op[bool] = None) -> bool:
        if cooling is None:  # Perform a toggle
            self.get_temperature()  # Populate self.is_cooling = bool(temp[8])
            cooling = not self.is_cooling
        self.send_command_parsed('temp ' + ('off', 'on')[self.is_cooling])
        self.is_cooling = cooling

        return self.is_cooling

    def set_temperature_setpoint(self, temp: float) -> float:
        self.send_command_parsed(f'temp {int(temp)}')
        logg.info(f'set_temperature_setpoint: {temp}')
        return self.get_temperature()
