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
        #print(f'{threading.current_thread()} acquiring RLock...', end='')
        r = self.rlock.acquire(*args, **kwargs)
        #print(('DENIED.', 'acquired.')[r])
        return r

    def release(self, *args, **kwargs):
        #print(f'{threading.current_thread()} releasing RLock...', end='')
        self.rlock.release(*args, **kwargs)
        #print('released.')

    def __enter__(self):
        #print(f'{threading.current_thread()} entering RLock...', end='')
        self.rlock.__enter__()
        #print('entered.')

    def __exit__(self, t: type[BaseException] | None, v: BaseException | None,
                 tb: TracebackType | None) -> None:
        #print(f'{threading.current_thread()} exiting RLock...', end='')
        self.rlock.__exit__(t, v, tb)
        #print('exited.')


ApiKeyT = typ.TypeVar('ApiKeyT')


class CommandTransport(typ.Generic[ApiKeyT]):

    def __init__(self, data_stream_name: str) -> None:
        # Do basic stuff
        self.control_shm = SHM(data_stream_name + "_params_fb",
                               np.zeros((1, ), dtype=np.int32))
        # Need an RLock because during the set_camera_mode we eventually get to a _prm_setget_multivalue for fill_keywords.
        self.control_shm_lock = WrappingVerboseRLock()  #threading.RLock()

    def set(self, value: typ.Any,
            api_cam_key: ApiKeyT) -> tuple[typ.Any, typ.Any]:
        return self.setmulti([value], [api_cam_key])[0]

    def get(self, api_cam_key: ApiKeyT) -> tuple[typ.Any, typ.Any]:
        return self.getmulti([api_cam_key])[0]

    def setmulti(self, values: list[typ.Any],
                 api_cam_keys: list[ApiKeyT]) -> list[tuple[typ.Any, typ.Any]]:
        return self.setgetmulti(values, api_cam_keys, getonly_flag=False)

    def getmulti(self,
                 api_cam_keys: list[ApiKeyT]) -> list[tuple[typ.Any, typ.Any]]:
        return self.setgetmulti([None] * len(api_cam_keys), api_cam_keys,
                                getonly_flag=True)

    def setmulti_nofeedback_nosync(self, values: list[typ.Any],
                                   api_cam_keys: list[ApiKeyT]) -> None:
        logg.debug(
                f"CommandTransport setmulti_nofeedback_nosync: {list(zip(api_cam_keys, values))}"
        )
        n_keywords = len(values)
        kvc_list = [
                self.setter_request_to_k_v_c(key, val)
                for key, val in zip(api_cam_keys, values)
        ]
        with self.control_shm_lock:
            self.control_shm.reset_keywords({k: (v, c) for k, v, c in kvc_list})
            self.control_shm.set_data(self.control_shm.get_data() * 0 +
                                      n_keywords)  # Toggle grabber process
            # Flush the semaphores for the post we just did
            while self.control_shm.check_sem_trywait():
                pass

    def setgetmulti(self, values: list[typ.Any], api_keys: list[ApiKeyT],
                    getonly_flag: bool) -> list[tuple[typ.Any, typ.Any]]:
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
                f"ParamsSHMCamera setgetmulti [getonly: {getonly_flag}]: {list(zip(api_keys, values))}"
        )
        assert self.control_shm

        n_keywords = len(values)

        if getonly_flag:
            kvc_list = [self.getter_request_to_k_v_c(key) for key in api_keys]
            # dcam_string_keys =
        else:
            kvc_list = [
                    self.setter_request_to_k_v_c(key, val)
                    for key, val in zip(api_keys, values)
            ]
        key_list = [k for (k, _, _) in kvc_list]

        with self.control_shm_lock:
            self.control_shm.reset_keywords({k: (v, c) for k, v, c in kvc_list})
            self.control_shm.set_data(self.control_shm.get_data() * 0 +
                                      n_keywords)  # Toggle grabber process
            self.control_shm.multi_recv_data(3, True,
                                             timeout=1.0)  # Ensure re-sync

            all_kwc = self.control_shm.get_keywords(True)
            transport_returns = [
                    self.kvc_to_transport_return_vals(k, *all_kwc[k])
                    for k in key_list
            ]

        for_return: list[tuple[float, float]] = []
        for k, v in zip(api_keys, transport_returns):
            for_return += [(self.to_format_val(k, v), self.to_fits_val(k, v))]

        return for_return

    def getter_request_to_k_v_c(self,
                                api_key: ApiKeyT) -> tuple[str, typ.Any, str]:
        '''
            Transforms a getter request for API key api_key into a
            (key, value, comment) triplet to pass
            from the control into the transport SHM keywords.
        '''
        raise NotImplementedError('Subclass expected')

    def setter_request_to_k_v_c(self, api_key: ApiKeyT,
                                value: typ.Any) -> tuple[str, typ.Any, str]:
        '''
            Transforms a setter request for API key api_key with value value into a
            (key, value, comment) triplet to pass
            from the control into the transport SHM keywords.
        '''
        raise NotImplementedError('Subclass expected')

    def kvc_to_transport_return_vals(self, kw_key: str, value: typ.Any,
                                     comment: str) -> typ.Any:
        '''
            Transforms a (key, value, comment) triplet return from the
            transport SHM keywords into a usable value.
            This is to be used when e.g. long strings are packaged into
            the comment field.
        '''
        raise NotImplementedError('Subclass expected')

    def to_format_val(self, api_key: ApiKeyT, value: typ.Any) -> typ.Any:
        '''
            Convert a transport return value (as delivered from kvc_to_transport_return_vals)
            to a value that is appropriate for use through the software
            - including API file enumerations
            - or strings, or number formats, etc.
        '''
        return value  # Nothing to do here

    def to_fits_val(self, api_key: ApiKeyT, value: typ.Any) -> typ.Any:
        '''
            Convert a transport return value (as delivered from kvc_to_transport_return_vals)
            to a proper formatted and compliant value that:
            - can be set to the camera data SHM keywords
            - can be used in FITS files
            as a difference to to_format_val, this excludes ad-hoc enums from the API.
        '''
        return value


class ParamsSHMCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = [] + BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    CLS_SHM_COMMUNICATOR: typ.ClassVar[type[CommandTransport[
            typ.Any]]] = CommandTransport
    ctrl_transport: CommandTransport[typ.Any]

    def __init__(self, *args, **kwargs) -> None:

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

        self.ctrl_transport = self.CLS_SHM_COMMUNICATOR(
                data_stream_name=self.STREAMNAME)

    def set_camera_mode(self, mode_id: util.Typ_mode_id, **kwargs) -> None:
        # Wrap into something thread-safe during the restart.
        with self.ctrl_transport.control_shm_lock:
            return super().set_camera_mode(mode_id, **kwargs)

    def _ensure_backend_restarted(self) -> None:
        # In case we recreated the SHM...
        # The sleep(1.0) used elsewhere, TOO FAST FOR DCAM!
        # so dcamusbtake.c implements a forced feedback

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

            if self.ctrl_transport.control_shm.check_sem_trywait():
                break

            if k == n_secs - 1:
                message = 'dcam/pvcam grabber taking more than 20 sec to restart.'
                # Ensure the state is known by making absolutely sure we kill this.
                self._kill_taker_no_dependents(bypass_aux_thread=True)
                logg.critical(message)
                raise RuntimeError(message)

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

        assert self.event is not None  # type guard

        event_count = 0
        while True:
            ret = self.event.wait(1)
            if ret:  # Signal to break the loop
                break

            event_count += 1
            if event_count % 10 > 0:
                continue

            # This is the bit specific to the subclass
            if not self.ctrl_transport.control_shm_lock.acquire(blocking=False):
                continue

            # And the additional try/finally is also subclass specific.
            try:
                self.auxiliary_thread_inner_function()
            finally:
                self.ctrl_transport.control_shm_lock.release()
