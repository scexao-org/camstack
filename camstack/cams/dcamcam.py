from typing import Union, Tuple, List, Any

from camstack.core.base import BaseCamera
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

        # Try create a feedback SHM for parameters
        self.control_shm = SHM(self.STREAMNAME + "_params_fb",
                               np.zeros((1, ), dtype=np.int16))

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

        x0, x1 = self.current_mode.x0, self.current_mode.x1
        y0, y1 = self.current_mode.y0, self.current_mode.y1

        params = {
            dcamprop.EProp.SUBARRAYHPOS: x0,
            dcamprop.EProp.SUBARRAYVPOS: y0,
            dcamprop.EProp.SUBARRAYHSIZE: x1 - x0 + 1,
            dcamprop.EProp.SUBARRAYVSIZE: y1 - y0 + 1,
            dcamprop.EProp.EXPOSURETIME: self.current_mode.exposure,
            dcamprop.EProp.SUBARRAYMODE: dcamprop.ESubArrayMode.ON,
        }

        # Convert int keys into hexstrings
        dump_params = {f'{k:08x}': params[k] for k in params}
        self.control_shm.set_keywords(dump_params)
        self.control_shm.set_data(self.control_shm.get_data() + len(params))
        # Find a way to (prepare to) feed to the camera

    def _prepare_backend_cmdline(self, reuse_shm: bool = False):

        # Prepare the cmdline for starting up!
        exec_path = os.environ['HOME'] + '/src/camstack/src/dcamusbtake'
        self.taker_tmux_command = (f'{exec_path} -s {self.STREAMNAME} '
                                   f'-u {self.dcam_number} -l 0 -N 4')
        if reuse_shm:
            self.taker_tmux_command += ' -R'  # Do not overwrite the SHM.

    def _dcam_prm_setvalue(value, fits_key, dcam_key):
        # setter implements a quick feedback
        # the C code overwrites the values of keywords
        # before posting the data anew.
        # To avoid a race, we need to wait twice for a full loop

        dcam_string_key = f'{dcamprop.EProp.EXPOSURETIME:08x}'

        self.control_shm.set_keywords({dcam_string_key: value})
        self.control_shm.set_data(self.control_shm.get_data() +
                                  1)  # Toggle grabber process
        self.camera_shm.multi_recv_data(2, True)  # Ensure re-sync
        fb_value = self.control_shm.get_keywords()[
            dcam_string_key]  # Get back the cam value
        self.camera_shm.update_keyword(fits_key, fb_value)

        return fb_value

    def _dcam_prm_setmultivalue():
        pass

    def get_tint(self):
        # getter is stupidly passive
        return self.camera_shm.get_keywords()['EXPTIME']

    def set_tint(self, tint: float):
        return self._dcam_prm_setvalue(tint, 'EXPTIME',
                                       dcamprop.EProp.EXPOSURETIME)


class OrcaQuestUSB(DCAMUSBCamera):

    INTERACTIVE_SHELL_METHODS = ['K', 'K2'] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    K, K2 = 'K', 'K2'
    MODES = {
        K: CameraMode(x0=1560, x1=2159, y0=980, y1=1279, tint=0.001),
        K2: CameraMode(x0=1260, x1=2459, y0=830, y1=1429, tint=0.001),
    }

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

        DCAMUSBCamera.__init__(self,
                               name,
                               stream_name,
                               mode_id,
                               dcam_number,
                               no_start=no_start,
                               taker_cset_prio=taker_cset_prio,
                               dependent_processes=dependent_processes)
