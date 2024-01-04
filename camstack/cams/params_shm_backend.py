from __future__ import annotations

from types import TracebackType
import typing as typ

import os
import logging as logg

from camstack.cams.base import BaseCamera
from camstack.core import utilities as util
from camstack.core.tmux import find_pane_running_pid

from pyMilk.interfacing.shm import SHM

import numpy as np

import time
import threading


class WrappingVerboseRLock:

    def __init__(self) -> None:
        self.rlock = threading.RLock()

    def acquire(self, *args, **kwargs):
        print(f'{threading.current_thread()} acquiring RLock...', end='')
        r = self.rlock.acquire(*args, **kwargs)
        print(('DENIED.', 'acquired.')[r])
        return r

    def release(self, *args, **kwargs):
        print(f'{threading.current_thread()} releasing RLock...', end='')
        self.rlock.release(*args, **kwargs)
        print('released.')

    def __enter__(self):
        print(f'{threading.current_thread()} entering RLock...', end='')
        self.rlock.__enter__()
        print('entered.')

    def __exit__(self, t: type[BaseException] | None, v: BaseException | None,
                 tb: TracebackType | None) -> None:
        print(f'{threading.current_thread()} exiting RLock...', end='')
        self.rlock.__exit__(t, v, tb)
        print('exited.')


class ParamsSHMCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    # Params SHM key mask to define get vs. set
    # Need to check the selected mask has no conflict with any parameter key
    PARAMS_SHM_GET_MAGIC = 0x8000_0000
    # Arbitrary MAGIC number
    # encodes a "Invalid property" returned from the framegrab process
    PARAMS_SHM_INVALID_MAGIC = -8.0085

    def __init__(self, *args, **kwargs) -> None:

        # Do basic stuff
        self.control_shm: typ.Optional[SHM] = None
        # Need an RLock because during the set_camera_mode we eventually get to a _prm_setget_multivalue for fill_keywords.
        self.control_shm_lock = WrappingVerboseRLock()  #threading.RLock()

        super().__init__(*args, **kwargs)

    def init_framegrab_backend(self) -> None:
        logg.debug("init_framegrab_backend @ ParamsSHMCamera")

        if self.is_taker_running():
            # Let's give ourselves two tries
            time.sleep(3.0)
            if self.is_taker_running():
                msg = "Cannot change camera config while camera is running"
                logg.error(msg)
                raise AssertionError(msg)

        # Try create a feedback SHM for parameters
        if self.control_shm is None:
            self.control_shm = SHM(self.STREAMNAME + "_params_fb",
                                   np.zeros((1, ), dtype=np.int32))

    def set_camera_mode(self, mode_id: util.Typ_mode_id, **kwargs) -> None:
        # Wrap into something thread-safe during the restart.
        with self.control_shm_lock:
            return super().set_camera_mode(mode_id, **kwargs)

    def _ensure_backend_restarted(self) -> None:
        # In case we recreated the SHM...
        # The sleep(1.0) used elsewhere, TOO FAST FOR DCAM!
        # so dcamusbtake.c implements a forced feedback

        assert self.control_shm  # mypy happyness check.

        # This should work, unless the grabber crashes during restart.
        n_secs: int = 20
        for k in range(n_secs):
            time.sleep(1)

            pid = find_pane_running_pid(self.take_tmux_pane)
            assert pid is not None, f"pid in frame taker tmux is None - the framegrab process did not start/crashed."
            try:
                os.kill(pid, 0)
            except OSError:
                logg.error('dcam/pvcam grabber crashed during restart.')
                raise RuntimeError('dcam/pvcam grabber crashed during restard.')

            if self.control_shm.check_sem_trywait():
                break

            if k == n_secs - 1:
                message = 'dcam/pvcam grabber taking more than 20 sec to restart.'
                # Ensure the state is known by making absolutely sure we kill this.
                self._kill_taker_no_dependents(bypass_aux_thread=True)
                logg.critical(message)
                raise RuntimeError(message)

    def _prm_setvalue(self, value: typ.Any, fits_key: typ.Optional[str],
                      api_cam_key: int) -> float:
        return self._prm_setmultivalue([value], [fits_key], [api_cam_key])[0]

    def _prm_setmultivalue(self, values: typ.List[typ.Any],
                           fits_keys: typ.List[typ.Optional[str]],
                           api_cam_keys: typ.List[int]) -> typ.List[float]:
        return self._prm_setgetmultivalue(values, fits_keys, api_cam_keys,
                                          getonly_flag=False)

    def _prm_getvalue(self, fits_key: typ.Optional[str],
                      api_cam_key: int) -> float:
        return self._prm_getmultivalue([fits_key], [api_cam_key])[0]

    def _prm_getmultivalue(self, fits_keys: typ.List[typ.Optional[str]],
                           api_cam_keys: typ.List[int]) -> typ.List[float]:
        return self._prm_setgetmultivalue([0.0] * len(fits_keys), fits_keys,
                                          api_cam_keys, getonly_flag=True)

    def _prm_setgetmultivalue(
            self,
            values: typ.List[typ.Any],
            fits_keys: typ.List[typ.Optional[str]],
            dcam_keys: typ.List[int],
            getonly_flag: bool,
    ) -> typ.List[float]:
        """
            Setter - implements a quick feedback between this code and dcamusbtake

            The C code overwrites the values of keywords
            before posting the data anew.
            To avoid a race, we need to wait twice for a full loop

            To perform set-gets and just gets with the same procedure... we leverage the hexmasks
            All parameters (see Eprop in dcamprop.py) are 32 bit starting with 0x0
            We set the first bit to 1 if it's a set.

            #FIXME: DCAM would really only like to use float64.
            #FIXME: PVCAM is a little more flexible but mostly prefers uint64
        """

        logg.debug(
                f"ParamsSHMCamera _prm_setgetmultivalue [getonly: {getonly_flag}]: {list(zip(fits_keys, values))}"
        )
        assert self.control_shm

        n_keywords = len(values)

        if getonly_flag:
            dcam_string_keys = [
                    f"{dcam_key | self.PARAMS_SHM_GET_MAGIC:08x}"
                    for dcam_key in dcam_keys
            ]
        else:
            dcam_string_keys = [f"{dcam_key:08x}" for dcam_key in dcam_keys]

        with self.control_shm_lock:
            self.control_shm.reset_keywords({
                    dk: v
                    for dk, v in zip(dcam_string_keys, values)
            })
            self.control_shm.set_data(self.control_shm.get_data() * 0 +
                                      n_keywords)  # Toggle grabber process
            self.control_shm.multi_recv_data(3, True,
                                             timeout=1.0)  # Ensure re-sync

            fb_values: typ.List[float] = [
                    self.control_shm.get_keywords()[dk]
                    for dk in dcam_string_keys
            ]  # Get back the cam value

        for idx, (fk, dcamk) in enumerate(zip(fits_keys, dcam_keys)):
            if fk is not None:
                # Can pass None to skip keys entirely.
                fits_value = self._params_shm_return_raw_to_fits_val(
                        dcamk, fb_values[idx])
                self._set_formatted_keyword(fk, fits_value)

            format_value = self._params_shm_return_raw_to_format_val(
                    dcamk, fb_values[idx])
            fb_values[idx] = format_value

        return fb_values

    def _params_shm_return_raw_to_fits_val(self, api_key: int, value: float):
        # This call is intended to be overriden by subclasses
        # So as to amend how the return values from the feeback SHM
        # are given to the camera SHM keywords (think type casting...)
        return value

    def _params_shm_return_raw_to_format_val(self, api_key: int, value: float):
        # This call is intended to be overriden by subclasses
        # So as to amend how the return values from _prm_setgetmultivalue
        # are provided (think enums... se dcamcam)
        return value  # Nothing to do here

    def auxiliary_thread_run_function(self) -> None:
        '''
            I need to subclass this because we're having a freaking deadlock during the joining...
            (in the base version)
            If the control_lock is requested by the main thread,
            this ends up blocking on the control lock during poll_camera_for_keywords
            Then the main thread requests a join... which is impossible because the aux thread is waiting
            on the lock.

            So as a fix, we subclass the entire execution flow of the aux thread,
            and make sure every single iteration is dependent
            on owning the lock... non-blockingly! So we can loop-out and join.
        '''

        assert self.event is not None  # mypy happy assert

        event_count = 0
        while True:
            ret = self.event.wait(1)
            if ret:  # Signal to break the loop
                break

            event_count += 1
            if event_count % 10 > 0:
                continue

            if not self.control_shm_lock.acquire(blocking=False):
                continue

            try:
                if not self.is_taker_running():
                    logg.critical('take_tmux_pane contains no live PID.')

                # Dependents cset + RTprio checking
                for proc in self.dependent_processes:
                    proc.make_children_rt()

                # Camera specifics !
                try:
                    self.poll_camera_for_keywords()
                except Exception as e:
                    logg.error(f"Polling thread: error [{e}]")

                try:
                    self.redis_push_values()
                except Exception as e:
                    logg.error(f"Polling thread: error [{e}]")
            finally:
                self.control_shm_lock.release()
