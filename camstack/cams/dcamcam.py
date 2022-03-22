import os

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
from camstack.core import dcamprop
from camstack.core.utilities import CameraMode

from pyMilk.interfacing.shm import SHM
import numpy as np


class DCAMUSBCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: Union[CameraMode, Tuple[int, int]],
                 dcam_number: int,
                 no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        # Do basic stuff
        self.dcam_number = dcam_number

        BaseCamera.__init__(self,
                            name,
                            stream_name,
                            mode_id,
                            no_start=no_start,
                            taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

    def init_framegrab_backend(self):

        if self.is_taker_running():
            raise AssertionError('Cannot change FG config while FG is running')

        # Try create a feedback SHM for parameters
        self.control_shm = SHM(self.STREAMNAME + "_params_fb",
                               np.zeros((1, ), dtype=np.int16))

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        params = {
            dcamprop.EProp.SUBARRAYHPOS: x0,
            dcamprop.EProp.SUBARRAYVPOS: y0,
            dcamprop.EProp.SUBARRAYHSIZE: x1 - x0 + 1,
            dcamprop.EProp.SUBARRAYVSIZE: y1 - y0 + 1,
            dcamprop.EProp.EXPOSURETIME: self.current_mode.tint,
            dcamprop.EProp.SUBARRAYMODE: dcamprop.ESubArrayMode.ON,
        }

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

    def _dcam_prm_setvalue(self, value: Any, fits_key: str, dcam_key: int):
        return self._dcam_prm_setmultivalue([value], [fits_key], [dcam_key])[0]

    def _dcam_prm_setmultivalue(self, values: List[Any], fits_keys: List[str],
                                dcam_keys: List[int]):
        return self._dcam_prm_setgetmultivalue(values,
                                               fits_keys,
                                               dcam_keys,
                                               getonly_flag=False)

    def _dcam_prm_getvalue(self, fits_key: str, dcam_key: int):
        return self._dcam_prm_getmultivalue([fits_key], [dcam_key])[0]

    def _dcam_prm_getmultivalue(self, fits_keys: List[str],
                                dcam_keys: List[int]):
        return self._dcam_prm_setgetmultivalue([0.0] * len(fits_keys),
                                               fits_keys,
                                               dcam_keys,
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

        if getonly_flag:
            dcam_string_keys = [
                f'{dcam_key | 0x80000000:08x}' for dcam_key in dcam_keys
            ]
        else:
            dcam_string_keys = [f'{dcam_key:08x}' for dcam_key in dcam_keys]

        self.control_shm.reset_keywords(
            {dk: v
             for dk, v in zip(dcam_string_keys, values)})
        self.control_shm.set_data(self.control_shm.get_data() * 0 +
                                  1)  # Toggle grabber process
        self.camera_shm.multi_recv_data(2, True)  # Ensure re-sync

        fb_values = [
            self.control_shm.get_keywords()[dk] for dk in dcam_string_keys
        ]  # Get back the cam value

        for fk, fbv in zip(fits_keys, fb_values):
            self.camera_shm.update_keyword(fk, fbv)

        return fb_values


class OrcaQuestUSB(DCAMUSBCamera):

    INTERACTIVE_SHELL_METHODS = ['FIRST', 'FULL', 'set_tint', 'get_tint', 'get_temperature'] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    FIRST, FULL = 'FIRST', 'FULL'
    MODES = {
        FULL: CameraMode(x0=0, x1=4095, y0=0, y1=2303, tint=0.001),
        1: CameraMode(x0=1748, x1=2347, y0=1000, y1=1303, tint=0.001),
        2: CameraMode(x0=1448, x1=2647, y0=848, y1=1555, tint=0.001),
        3: CameraMode(x0=1148, x1=2947, y0=696, y1=1807, tint=0.001),
        4: CameraMode(x0=1848, x1=3147, y0=848, y1=1555, tint=0.001),
        FIRST: CameraMode(x0=256, x1=3835, y0=256, y1=1047, tint=0.001),
    }

    KEYWORDS = {}
    KEYWORDS.update(DCAMUSBCamera.KEYWORDS)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: Union[CameraMode, Tuple[int, int]],
                 dcam_number: int,
                 no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        DCAMUSBCamera.__init__(self,
                               name,
                               stream_name,
                               mode_id,
                               dcam_number,
                               no_start=no_start,
                               taker_cset_prio=taker_cset_prio,
                               dependent_processes=dependent_processes)

    def poll_camera_for_keywords(self):
        self.get_temperature()

    def get_temperature(self):
        # Let's try and play: it's readonly
        # but should trigger the cam calling back home
        return self._dcam_prm_getvalue('DET-TMP',
                                       dcamprop.EProp.SENSORTEMPERATURE)

    # And now we fill up... FAN, LIQUID

    def get_tint(self):
        # getter is stupidly passive
        return self.camera_shm.get_keywords()['EXPTIME']

    def set_tint(self, tint: float):
        return self._dcam_prm_setvalue(tint, 'EXPTIME',
                                       dcamprop.EProp.EXPOSURETIME)
