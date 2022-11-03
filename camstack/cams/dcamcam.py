import os
import logging as logg

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
from camstack.core import dcamprop
from camstack.core.utilities import CameraMode

from pyMilk.interfacing.shm import SHM
import numpy as np

import time


class DCAMCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    def __init__(self, name: str, stream_name: str, mode_id: Union[CameraMode,
                                                                   Tuple[int,
                                                                         int]],
                 dcam_number: int, no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        # Do basic stuff
        self.dcam_number = dcam_number
        self.control_shm = None

        BaseCamera.__init__(self, name, stream_name, mode_id,
                            no_start=no_start, taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

    def init_framegrab_backend(self):
        logg.debug('init_framegrab_backend @ DCAMCamera')

        if self.is_taker_running():
            # Let's give ourselves two tries
            time.sleep(3.0)
            if self.is_taker_running():
                msg = 'Cannot change camera config while camera is running'
                logg.error(msg)
                raise AssertionError(msg)

        # Try create a feedback SHM for parameters
        if self.control_shm is None:
            self.control_shm = SHM(self.STREAMNAME + "_params_fb",
                                   np.zeros((1, ), dtype=np.int16))

    def prepare_camera_for_size(self, mode_id=None, params_injection = None):
        logg.debug('prepare_camera_for_size @ DCAMCamera')

        BaseCamera.prepare_camera_for_size(self, mode_id=None)

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        params = {
                dcamprop.EProp.SUBARRAYHPOS: x0,
                dcamprop.EProp.SUBARRAYVPOS: y0,
                dcamprop.EProp.SUBARRAYHSIZE: x1 - x0 + 1,
                dcamprop.EProp.SUBARRAYVSIZE: y1 - y0 + 1,
                dcamprop.EProp.SUBARRAYMODE: dcamprop.ESubArrayMode.ON,
        }

        # Additional parameters for custom calls
        # Designed for e.g. dcamprop.EProp.READOUTSPEED
        # which requires restarting the acquisition
        # This way we can work this out without a full call to set_camera_mode in the base class
        # and avoiding restarting all dependent processes.
        if params_injection is not None: 
            params.update(params_injection)
        
        if self.current_mode.tint is not None:
            params[dcamprop.EProp.EXPOSURETIME] = self.current_mode.tint
        
        # Convert int keys into hexstrings
        # dcam values require FLOATS - we'll multiply everything by 1.0
        dump_params = {f'{k:08x}': 1.0 * params[k] for k in params}
        self.control_shm.reset_keywords(dump_params)
        self.control_shm.set_data(self.control_shm.get_data() * 0 +
                                  len(params))
        # Find a way to (prepare to) feed to the camera

    def _prepare_backend_cmdline(self, reuse_shm: bool = False):

        # Prepare the cmdline for starting up!
        exec_path = os.environ['HOME'] + '/src/camstack/src/dcamusbtake'
        self.taker_tmux_command = (f'{exec_path} -s {self.STREAMNAME} '
                                   f'-u {self.dcam_number} -l 0 -N 4')
        if reuse_shm:
            self.taker_tmux_command += ' -R'  # Do not overwrite the SHM.

    def _ensure_backend_restarted(self):
        # In case we recreated the SHM...
        # The sleep(1.0) used elsewhere, TOO FAST FOR DCAM!
        # so dcamusbtake.c implements a forced feedback
        self.control_shm.get_data(check=True, checkSemAndFlush=True,
                                  timeout=None)

    def _dcam_prm_setvalue(self, value: Any, fits_key: str, dcam_key: int):
        return self._dcam_prm_setmultivalue([value], [fits_key], [dcam_key])[0]

    def _dcam_prm_setmultivalue(self, values: List[Any], fits_keys: List[str],
                                dcam_keys: List[int]):
        return self._dcam_prm_setgetmultivalue(values, fits_keys, dcam_keys,
                                               getonly_flag=False)

    def _dcam_prm_getvalue(self, fits_key: str, dcam_key: int):
        return self._dcam_prm_getmultivalue([fits_key], [dcam_key])[0]

    def _dcam_prm_getmultivalue(self, fits_keys: List[str],
                                dcam_keys: List[int]):
        return self._dcam_prm_setgetmultivalue([0.0] * len(fits_keys),
                                               fits_keys, dcam_keys,
                                               getonly_flag=True)

    def _dcam_prm_setgetmultivalue(self, values: List[Any],
                                   fits_keys: List[str], dcam_keys: List[int],
                                   getonly_flag: bool):
        '''
            Setter - implements a quick feedback between this code and dcamusbtake

            The C code overwrites the values of keywords
            before posting the data anew.
            To avoid a race, we need to wait twice for a full loop

            To perform set-gets and just gets with the same procedure... we leverage the hexmasks
            All parameters (see Eprop in dcamprop.py) are 32 bit starting with 0x0
            We set the first bit to 1 if it's a set.
        '''

        logg.debug(f'DCAMCamera _dcam_prm_setgetmultivalue [getonly: {getonly_flag}]: {list(zip(fits_keys, values))}')

        if getonly_flag:
            dcam_string_keys = [
                    f'{dcam_key | 0x80000000:08x}' for dcam_key in dcam_keys
            ]
        else:
            dcam_string_keys = [f'{dcam_key:08x}' for dcam_key in dcam_keys]

        self.control_shm.reset_keywords({
                dk: v
                for dk, v in zip(dcam_string_keys, values)
        })
        self.control_shm.set_data(self.control_shm.get_data() * 0 +
                                  1)  # Toggle grabber process
        self.camera_shm.multi_recv_data(2, True)  # Ensure re-sync

        fb_values = [
                self.control_shm.get_keywords()[dk] for dk in dcam_string_keys
        ]  # Get back the cam value

        for fk, fbv in zip(fits_keys, fb_values):
            self._set_formatted_keyword(fk, fbv)

        return fb_values


class OrcaQuest(DCAMCamera):

    INTERACTIVE_SHELL_METHODS = ['FIRST', 'FULL', 'set_tint', 'get_tint', 'get_temperature', 
                                 'set_readout_ultraquiet'] + \
        DCAMCamera.INTERACTIVE_SHELL_METHODS

    FIRST, FULL = 'FIRST', 'FULL'
    MODES = {
        FIRST: CameraMode(x0=952, x1=2915, y0=492, y1=727, tint=0.001),
        FULL: CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),
        0: CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),  # Also full
        1: CameraMode(x0=1536, x1=2335, y0=976, y1=1231, tint=0.001),    # Kyohoon is Using for WFS mode
        11: CameraMode(x0=1536, x1=2335, y0=976, y1=1231, tint=0.1), # Same as 1 no tint.
        2: CameraMode(x0=800, x1=3295, y0=876, y1=1531, tint=0.001),      # Kyohoon is Using for WFS align
        3: CameraMode(x0=1148, x1=2947, y0=696, y1=1807, tint=0.001),
        4: CameraMode(x0=1564, x1=1819, y0=976, y1=1231, tint=0.001),    # Jen is using for focal plane mode
    }

    KEYWORDS = {}
    KEYWORDS.update(DCAMCamera.KEYWORDS)

    def __init__(self, name: str, stream_name: str, mode_id: Union[CameraMode,
                                                                   Tuple[int,
                                                                         int]],
                 dcam_number: int, no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        DCAMCamera.__init__(self, name, stream_name, mode_id, dcam_number,
                            no_start=no_start, taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

    def _fill_keywords(self):
        DCAMCamera._fill_keywords(self)

        # Override detector name
        self._set_formatted_keyword('DETECTOR', 'Orca Quest')

    def poll_camera_for_keywords(self):
        self.get_temperature()

    def get_temperature(self):
        # Let's try and play: it's readonly
        # but should trigger the cam calling back home
        val = self._dcam_prm_getvalue('DET-TMP',
                                       dcamprop.EProp.SENSORTEMPERATURE)
        logg.info(f'get_temperature {val}')
        return val

    # And now we fill up... FAN, LIQUID

    def get_tint(self):
        val = self._dcam_prm_getvalue('EXPTIME', dcamprop.EProp.EXPOSURETIME)
        logg.info(f'get_tint {val}')
        return val

    def set_tint(self, tint: float):
        return self._dcam_prm_setvalue(tint, 'EXPTIME',
                                       dcamprop.EProp.EXPOSURETIME)
        
    def set_readout_ultraquiet(self, ultraquiet: bool):
        logg.debug('set_readout_ultraquiet @ OrcaQuest')

        readmode = (dcamprop.EReadoutSpeed.READOUT_FAST,
                    dcamprop.EReadoutSpeed.READOUT_ULTRAQUIET)[ultraquiet]
        
        self._kill_taker_no_dependents()
        self.prepare_camera_for_size(params_injection = {dcamprop.EProp.READOUTSPEED: readmode})
        
        self._start_taker_no_dependents(reuse_shm=True)
        # Are those two necessary in this context??? reuse_shm should cover.
        self.grab_shm_fill_keywords()
        self.prepare_camera_finalize()
        


class FIRSTOrcam(OrcaQuest):

    def _fill_keywords(self):
        OrcaQuest._fill_keywords(self)

        # Override detector name
        self._set_formatted_keyword('DETECTOR', 'FIRST OrcaQ')


class AlalaOrcam(OrcaQuest):

    def _fill_keywords(self):
        OrcaQuest._fill_keywords(self)

        # Override detector name
        self._set_formatted_keyword('DETECTOR', 'ALALA OrcaQ')

class MilesOrcam(OrcaQuest):
    
    def _fill_keywords(self):
        OrcaQuest._fill_keywords(self)

        # Override detector name
        self._set_formatted_keyword('DETECTOR', 'Miles OrcaQ')
