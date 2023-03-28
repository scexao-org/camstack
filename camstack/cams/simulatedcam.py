from typing import Union, Tuple, List, Any, Dict, TYPE_CHECKING

import os
import subprocess
import time
import logging as logg

import numpy as np
if TYPE_CHECKING:
    from numpy.typing import DTypeLike

from camstack.cams.base import BaseCamera

from camstack.core import utilities as util

CAMSTACK_HOME = os.environ['HOME'] + '/src/camstack'

NPTYPE_LOOKUP: Dict[str, DTypeLike] = {
        'f32': np.float32,
        'f64': np.float64,
        'c64': np.csingle,
        'c128': np.cdouble,
        'i8': np.int8,
        'i16': np.int16,
        'i32': np.int32,
        'i64': np.int64,
        'u8': np.uint8,
        'u16': np.uint16,
        'u32': np.uint32,
        'u64': np.uint64,
}
INV_NPTYPE_LOOKUP = {NPTYPE_LOOKUP[k]: k for k in NPTYPE_LOOKUP}


class SimulatedCam(BaseCamera):

    INTERACTIVE_SHELL_METHODS = BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    def __init__(self, name: str, stream_name: str,
                 mode_id: util.ModeIDorHWType,
                 data_type: Union[str, DTypeLike] = np.uint16,
                 no_start: bool = False,
                 taker_cset_prio: util.CsetPrioType = ('system', None),
                 dependent_processes: List[util.DependentProcess] = []) -> None:

        if isinstance(data_type, str):
            self.dtype_string = data_type
            self.dtype_np = NPTYPE_LOOKUP[data_type]
        else:
            self.dtype_string = INV_NPTYPE_LOOKUP[data_type]
            self.dtype_np = data_type

        BaseCamera.__init__(self, name, stream_name, mode_id, no_start=no_start,
                            taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

    def init_framegrab_backend(self) -> None:
        logg.debug('init_framegrab_backend @ SimulatedCam')
        if self.is_taker_running():
            msg = 'Cannot change FG config while FG is running'
            logg.error(msg)
            raise AssertionError(msg)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False) -> None:
        # Prepare the cmdline for starting up!
        exec_path = CAMSTACK_HOME + '/src/simcam_framegen'
        w = self.current_mode.y1 - self.current_mode.y0 + 1
        h = self.current_mode.x1 - self.current_mode.x0 + 1
        self.taker_tmux_command = f'{exec_path} {self.STREAMNAME} {w} {h} -t {self.dtype_string}'

        if reuse_shm:
            self.taker_tmux_command += ' -R'  # Do not overwrite the SHM.

    def _ensure_backend_restarted(self) -> None:
        # Plenty simple enough for EDT, never failed me
        time.sleep(1.0)

    def get_tint(self) -> float:
        assert self.camera_shm

        etime = self.camera_shm.get_keywords()['_ETIMEUS'] / 1e6
        self._set_formatted_keyword('EXPTIME', etime)
        self._set_formatted_keyword('FRATE', 1.0 / etime)
        return etime

    def set_tint(self, etime: float) -> float:
        assert self.camera_shm

        self.camera_shm.update_keyword('_ETIMEUS', int(etime * 1e6))
        return self.get_tint()

    def get_fps(self) -> float:
        assert self.camera_shm

        etime = self.camera_shm.get_keywords()['_ETIMEUS'] / 1e6
        self._set_formatted_keyword('EXPTIME', etime)
        self._set_formatted_keyword('FRATE', 1.0 / etime)
        return 1 / etime

    def set_fps(self, fps: float) -> float:
        assert self.camera_shm

        self.camera_shm.update_keyword('_ETIMEUS', int(1e6 / fps))
        return self.get_fps()

    def poll_camera_for_keywords(self) -> None:
        # This just silences the warning of calling it on the Base class
        pass
