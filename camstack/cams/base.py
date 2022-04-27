import os
import time
import subprocess
import threading

from camstack.core.utilities import CameraMode
from camstack.core import tmux as tmux_util

from scxkw.config import MAGIC_BOOL_STR

from pyMilk.interfacing.isio_shmlib import SHM

from typing import List, Any, Union, Tuple


class BaseCamera:
    '''
        Standard basic stuff that is common over EDT framegrabbers
        Written with the mindset "What should be common between CRED2, Andors and OCAM ?"
        And implements the server side management of the imgtake
    '''

    INTERACTIVE_SHELL_METHODS = [
        'close', 'release',
        '_start', '_stop',
        'set_camera_mode',
        'set_camera_size',
    ]

    MODES = {}

    KEYWORDS = {
        # Format is name: (value, description, formatter) - this list CAN be figured out from a redis query.
        # but I don't want to add the dependency at this point
        # ALSO SHM caps at 16 chars for strings. The %s formats here are (some) shorter than official ones.
        'BIN-FCT1': (1, 'Binning factor of the X axis (pixel)', '%20d'),
        'BIN-FCT2': (1, 'Binning factor of the Y axis (pixel)', '%20d'),
        'BSCALE': (1.0, 'Real=fits-value*BSCALE+BZERO', '%20.8f'), # Removed to let logshim handle it.
        'BUNIT': ('ADU', 'Unit of original values', '%-10s'),
        'BZERO': (0.0, 'Real=fits-value*BSCALE+BZERO', '%20.8f'),
        'PRD-MIN1': (0, 'Origin in X of the cropped window (pixel)', '%16d'),
        'PRD-MIN2': (0, 'Origin in Y of the cropped window (pixel)', '%16d'),
        'PRD-RNG1': (1, 'Range in X of the cropped window (pixel)', '%16d'),
        'PRD-RNG2': (1, 'Range in Y of the cropped window (pixel)', '%16d'),
        'CROPPED': (False, 'Partial Readout or cropped', 'BOOLEAN'),
        'DET-NSMP': (1, 'Number of non-destructive reads', '%20d'),
        'DET-SMPL': ('base', 'Sampling method', '%-16.16s'),
        'DET-TMP': (0.0, 'Detector temperature (K)', '%20.2f'),
        'DETECTOR': ('DET', 'Name of the detector', '%-16s'),
        'DETGAIN': (1, 'Detector multiplication factor', '%16d'),
        'EXPTIME': (0.001, 'Total integration time of the frame (sec)', '%20.8f'),
        'FRATE': (100., 'Frame rate of the acquisition (Hz)', '%16.3f'),
        'GAIN': (1., 'AD conversion factor (electron/ADU)', '%20.3f'),
        'EXTTRIG': (False, 'Exposure of detector by an external trigger', 'BOOLEAN'),
        'DATA-TYP': ('TEST', 'Subaru-style exp. type', '%-16s'),
    }

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: Union[CameraMode, Tuple[int,int]],
                 no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        #=======================
        # COPYING ARGS
        #=======================

        self.NAME = name
        self.STREAMNAME = stream_name

        if isinstance(mode_id, tuple):  # Allow (width, height) fallback
            self.current_mode_id = 'CUSTOM'
            self.MODES['CUSTOM'] = CameraMode(x0=0,
                                              x1=width - 1,
                                              y0=0,
                                              y1=height - 1)
        else:
            self.current_mode_id = mode_id

        self.current_mode = self.MODES[mode_id]
        self.width, self.height = self._fg_size_from_mode(mode_id)



        self.dependent_processes = dependent_processes
        self.taker_cset_prio = taker_cset_prio

        # Thread:
        self.event = None
        self.thread = None

        #=======================
        # TMUX TAKE SESSION MGMT
        #=======================
        # The taker tmux name will be allocated in the call to kill_taker_and_dependents
        # The tmux will also be created if it doesn't exist
        # If this session dies, we'll have to call this again
        self.take_tmux_name = None
        self.kill_taker_and_dependents()

        #============================================
        # PREPARE THE FRAMEGRABBER AND OPEN INTERFACE
        #============================================
        # This is backend-dependent
        self.init_framegrab_backend()
    
        # ====================
        # PREPARE THE CAMERA
        # ====================
        # Now we have a serial link, in case prepare camera needs it.
        self.prepare_camera_for_size()

        if no_start:
            # We need to quit now
            # That also means not starting will not create the SHM
            # And this __init__ will not populate the keywords :(.
            return

        # ====================
        # START THE TAKE - and thus expect the SHM to be created
        # - we only start the take because we want the keywords to be populated ASAP
        # and starting dependents is the long part.
        # ====================
        self._start_taker_no_dependents()

        # =================
        # ALLOCATE KEYWORDS
        # =================
        self.camera_shm = None
        self.grab_shm_fill_keywords()
        # Maybe we can use a class variable as well to define what the expected keywords are ?

        # ================
        # START DEPENDENTS
        # ================
        self.start_frame_taker_and_dependents(skip_taker=True)

        # =================================
        # FINALIZE A FEW DETAILS POST-START
        # =================================
        self.prepare_camera_finalize()

    def init_framegrab_backend(self):
        # TODO: split into a init_framegrab once (open handles to devices)
        # TODO: and what must be done for every mode change (EDT size change)
        raise NotImplementedError("Must be subclassed from the base class")


    def prepare_camera_for_size(self, mode_id=None):
        # Gets called during constructor and set_mode
        if mode_id is None:
            mode_id = self.current_mode_id
        print('Calling prepare_camera_for_size on generic BaseCamera class. '
              'Setting size for shmimTCPreceive.')
        for dep_proc in self.dependent_processes:
            if 'shmimTCPreceive' in dep_proc.cli_cmd:
                cm = self.current_mode
                h, w = (cm.x1 - cm.x0 + 1) // cm.binx, (cm.y1 - cm.y0 +
                                                        1) // cm.biny
                dep_proc.cli_args = (dep_proc.cli_args[0], h, w)

    def prepare_camera_finalize(self, mode_id=None):
        # Gets called after the framegrabbing has restarted spinning
        if mode_id is None:
            mode_id = self.current_mode_id
        print('Calling prepare_camera on generic BaseCameraClass. '
              'Nothing happens here.')

    def set_camera_mode(self, mode_id):
        '''
            Quite same as above - but mostly meant to be called by subclasses that do have defined modes.
        '''
        self.kill_taker_and_dependents()

        self.current_mode_id = mode_id
        self.current_mode = self.MODES[mode_id]
        self.width, self.height = self._fg_size_from_mode(mode_id)

        self.init_framegrab_backend()

        self.prepare_camera_for_size()

        self.start_frame_taker_and_dependents()

        self.grab_shm_fill_keywords()

        self.prepare_camera_finalize()

    def set_mode(self, mode_id):
        '''
            Alias
        '''
        self.set_camera_mode(mode_id)

    def set_camera_size(self,
                        height: int,
                        width: int,
                        h_offset: int = 0,
                        w_offset: int = 0):
        '''
            That's a pretty agressive change - and thus,
            we're pretty much restarting everything
            So actually the constructor could just call this ?

            This is a back-compatible mode (width, height) over the camera modes
        '''
        self.MODES['CUSTOM'] = CameraMode(x0=w_offset,
                                          x1=w_offset + width - 1,
                                          y0=h_offset,
                                          y1=h_offset + height - 1)

        self.set_camera_mode('CUSTOM')

    def is_taker_running(self):
        '''
            Send a signal to the take process PID to figure out if it's alive
        '''
        return tmux_util.find_pane_running_pid(self.take_tmux_pane) is not None

    def start_frame_taker_and_dependents(self, skip_taker=False):

        if not skip_taker:
            self._start_taker_no_dependents()

        # Now handle the dependent processes
        self.dependent_processes.sort(key=lambda x: x.start_order)
        for dep_process in self.dependent_processes:
            dep_process.start()

    def kill_taker_and_dependents(self, skip_taker=False):

        self.dependent_processes.sort(key=lambda x: x.kill_order)
        for dep_process in self.dependent_processes:
            dep_process.stop()

        if not skip_taker:
            self._kill_taker_no_dependents()

    def release(self):
        '''
            Just an alias
        '''
        self.kill_taker_and_dependents()

    def close(self):
        '''
            Just an alias
        '''
        self.release()


    def _start_taker_no_dependents(self, reuse_shm: bool=False):
        # We have to prepare self.taker_tmux_command
        # we could do that in init_framegrab_backend, but hey we don't

        self._prepare_backend_cmdline(reuse_shm=reuse_shm)
        if not hasattr(self, 'taker_tmux_command'):
            raise AssertionError('self.taker_tmux_command is not defined?!')
        
        # Let's do it.
        tmux_util.send_keys(self.take_tmux_pane, self.taker_tmux_command)
        

        if self.taker_cset_prio[1] is not None:  # Set rtprio !
            subprocess.run([
                'milk-makecsetandrt',
                str(tmux_util.find_pane_running_pid(
                    self.take_tmux_pane)),  # PID
                self.taker_cset_prio[0],  # CPUSET
                str(self.taker_cset_prio[1])  # PRIORITY
            ])

        self._ensure_backend_restarted()
        
        # Should these 3 be there ???
        self.grab_shm_fill_keywords()
        self.prepare_camera_finalize()
        self.start_auxiliary_thread()

    def _start(self):
        '''
        Alias
        '''
        self._start_taker_no_dependents()

    def _prepare_backend_cmdline(self, reuse_shm: bool = False):
        raise NotImplementedError("Must be subclassed from the base class")

    def _ensure_backend_restarted(self):
        raise NotImplementedError("Must be subclassed from the base class")

    def _kill_taker_no_dependents(self):

        self.stop_auxiliary_thread()

        self.take_tmux_name = f'{self.NAME}_fgrab'
        self.take_tmux_pane = tmux_util.find_or_create(self.take_tmux_name)
        tmux_util.kill_running(self.take_tmux_pane)

    def _stop(self):
        '''
        Alias
        '''
        self._kill_taker_no_dependents()

    def grab_shm_fill_keywords(self):
        # Problem: we need to be sure the taker has restarted
        # before filling keywords !
        # Second problem: if the taker is **slow**, we may regrab a
        # pointer to the SHM before the re-creation
        self.camera_shm = self._get_SHM()

        time.sleep(0.3) # Avoid initial race condition on keywords
        self._fill_keywords()

    def _get_SHM(self):
        # Separated to be overloaded if need be (thinking of you, OCAM !)
        
        while True:
            # In case the SHM doesn't exist yet
            try:
                shm = SHM(self.STREAMNAME, symcode=0)
                break
            except:
                time.sleep(0.1)
                
        shm.IMAGE.semflush(shm.semID)
        while shm.IMAGE.semtrywait(shm.semID):
            # We don't want to break a semaphore
            # So wait til the first frame is published
            time.sleep(0.1)
        
        return shm

    def _set_formatted_keyword(self, key, value):
        
        fmt = self.KEYWORDS[key][2]
        val = value
        if value is not None:
            try:
                if fmt == 'BOOLEAN':
                    val = MAGIC_BOOL_STR.TUPLE[value]
                elif fmt[-1] == 'd':
                    val = int(fmt % value)
                elif fmt[-1] == 'f':
                    val = float(fmt % value)
                elif fmt[-1] == 's':  # string
                    val = fmt % value
            except:  # Sometime garbage values cannot be formatted properly...
                print(f"fits_headers: formatting error on {key}, {value}, {fmt}")

        self.camera_shm.update_keyword(key, val)

    def _fill_keywords(self):
        # These are pretty much defaults - we don't know anything about this
        # basic abstract camera
        preex_keywords = self.camera_shm.get_keywords(True)
        preex_keywords.update(self.KEYWORDS)

        self.camera_shm.set_keywords(preex_keywords) # Initialize comments
        # Second pass to enforce formatting...
        # Don't do it on the preex from the framegrabber (MFRATE, _MACQTIME) cause they don't
        # have a formatter
        for kw in self.KEYWORDS:
            self._set_formatted_keyword(kw, preex_keywords[kw][0])

        cm = self.current_mode

        self._set_formatted_keyword('DETECTOR', 'Base Camera')
        self._set_formatted_keyword('BIN-FCT1', cm.binx)
        self._set_formatted_keyword('BIN-FCT2', cm.biny)
        self._set_formatted_keyword('PRD-MIN1', cm.x0)
        self._set_formatted_keyword('PRD-MIN2', cm.y0)
        self._set_formatted_keyword('PRD-RNG1', cm.x1-cm.x0+1)
        self._set_formatted_keyword('PRD-RNG2', cm.y1-cm.y0+1)
        self._set_formatted_keyword('CROPPED',  False)

    def get_fg_parameters(self):
        # We don't need to get them, because we set them in init_pdv_configuration
        pass

    def set_fg_parameters(self):
        pass

    def _fg_size_from_mode(self, mode_id):
        width, height = self.MODES[mode_id].fgsize
        return width, height

    def poll_camera_for_keywords(self):
        print('Calling poll_camera_for_keywords on generic BaseCamera class. '
              'Nothing happens here.')

    def start_auxiliary_thread(self):
        self.event = threading.Event()
        self.thread = threading.Thread(
            target=self.auxiliary_thread_run_function)
        self.thread.start()

    def stop_auxiliary_thread(self):
        if self.thread is not None:
            self.event.set()
            self.thread.join()

    def auxiliary_thread_run_function(self):
        while True:
            ret = self.event.wait(10)
            if ret:  # Signal to break the loop
                break

            # Dependents cset + RTprio checking
            for proc in self.dependent_processes:
                proc.make_children_rt()

            # Camera specifics !
            try:
                self.poll_camera_for_keywords()
            except Exception as e:
                print("Polling thread: error ", e)
