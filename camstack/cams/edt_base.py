#import libtmux as tmux
from camstack.core import tmux as tmux_util
from camstack.core.edtinterface import EdtInterfaceSerial
from pyMilk.interfacing.isio_shmlib import SHM

from typing import List, Any, Union

import os
import time
import subprocess

import threading

class EDTCameraNoModes:
    '''
        Standard basic stuff that is common over EDT framegrabbers
        Written with the mindset "What should be common between CRED2, Andors and OCAM ?"
        And implements the server side management of the imgtake
    '''

    INTERACTIVE_SHELL_METHODS = [
        'send_command', 'close', 'release', '_start', '_stop'
    ]

    KEYWORDS = {  # Format is name: (value, description) - this list CAN be figured out from a redis query.
        'BIN-FCT1': (1, 'Binning factor of the X axis (pixel)'),
        'BIN-FCT2': (1, 'Binning factor of the Y axis (pixel)'),
        'BSCALE': (1.0, 'Real=fits-value*BSCALE+BZERO'),
        'BUNIT': ('ADU', 'Unit of original values'),
        'BZERO': (0.0, 'Real=fits-value*BSCALE+BZERO'),
        'CROP_OR1': (0, 'Origin in X of the cropped window (pixel)'),
        'CROP_OR2': (0, 'Origin in Y of the cropped window (pixel)'),
        'CROP_EN1': (1, 'End in X of the cropped window (pixel)'),
        'CROP_EN2': (1, 'End in Y of the cropped window (pixel)'),
        'CROPPED': ('False', 'Image windowed or full frame'),
        'DET-TMP': (0.0, 'Detector temperature (K)'),
        'DETECTOR': ('DET', 'Name of the detector'),
        'DETGAIN': (1., 'Detector gain'),
        'DETMODE': ('base', 'Detector mode'),
        'EXPTIME': (0.001, 'Total integration time of the frame (sec)'),
        'FRATE': (100., 'Frame rate of the acquisition (Hz)'),
        'GAIN': (1., 'AD conversion factor (electron/ADU)'),
        'NDR': (1, 'Number of non-destructive reads'),
        'EXTTRIG': ('False', 'Extrernal trigger'),
        'DATA-TYP': ('TEST', 'Subaru-style exp. type')
    }

    EDTTAKE_CAST = False  # Only OCAM overrides that
    EDTTAKE_UNSIGNED = False

    def __init__(self,
                 name: str,
                 stream_name: str,
                 height: int,
                 width: int,
                 unit: int,
                 channel: int,
                 basefile: str,
                 no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):
        '''
            Run an SYSTEM init_cam with the cfg file
            Grab the desired/default camera mode
            Prepare the tmux
            Prepare the serial handles (also, think it MAY be overloaded for the Andors)
        '''

        #=======================
        # COPYING ARGS
        #=======================

        self.NAME = name
        self.STREAMNAME = stream_name

        self.height = height
        self.width = width  # IN CASE OF 8/16 CASTING, this is the ISIO width
        self.width_fg = (
            width, 2 *
            width)[self.EDTTAKE_CAST]  # And this is the camlink image width

        self.pdv_unit = unit
        self.pdv_channel = channel

        self.base_config_file = basefile

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
        self.edttake_tmux_name = None
        self.kill_taker_and_dependents()

        #==================================================
        # PREPARE THE FRAMEGRABBER AND OPEN SERIAL/FG IFACE
        #==================================================
        # Set the default config file to the FG board
        # Open a FG register and serial interface
        self.init_pdv_configuration()
        self.edt_iface = EdtInterfaceSerial(self.pdv_unit, self.pdv_channel)

        # ====================
        # PREPARE THE CAMERA
        # ====================
        # Now we have a serial link, in case prepare camera needs it.
        self.prepare_camera_for_size()

        if no_start:
            return

        # ====================
        # START THE TAKE - and thus expect the SHM to be created
        # - we only start the take because we want the keywords to be populated ASAP
        # and starting dependents is the long part.
        # ====================
        self._start_taker_no_dependents()

        # ====================
        # ALLOCATE KEYWORDS
        # ====================

        self.camera_shm = None
        self.grab_shm_fill_keywords()
        # Maybe we can use a class variable as well to define what the expected keywords are ?

        # ================
        # Start dependents
        # ================
        self.start_frame_taker_and_dependents(skip_taker = True)

        # =================================
        # FINALIZE A FEW DETAILS POST-START
        # =================================
        self.prepare_camera_finalize()

    def kill_taker_and_dependents(self):

        self.dependent_processes.sort(key=lambda x: x.kill_order)

        for dep_process in self.dependent_processes:
            dep_process.stop()

        self._kill_taker_no_dependents()

    def close(self):
        '''
            Just an alias
        '''
        self.kill_taker_and_dependents()

    def release(self):
        '''
            Just an alias
        '''
        self.kill_taker_and_dependents()

    def _kill_taker_no_dependents(self):

        self.stop_auxiliary_thread()

        self.edttake_tmux_name = f'{self.NAME}_edt'
        self.take_tmux_pane = tmux_util.find_or_create(self.edttake_tmux_name)
        tmux_util.kill_running(self.take_tmux_pane)

    def _stop(self):
        '''
        Alias
        '''
        self._kill_taker_no_dependents()

    def init_pdv_configuration(self):
        if self.is_taker_running():
            raise AssertionError(
                'Cannot change FG config while taker is running')

        tmp_config = '/tmp/' + os.environ['USER'] + '_' + self.NAME + '.cfg'
        # Adding a username here, because we can't overwrite the file of another user !
        res = subprocess.run(['cp', self.base_config_file, tmp_config],
                             stdout=subprocess.PIPE)
        if res.returncode != 0:
            raise FileNotFoundError(
                f'EDT cfg file {self.base_config_file} not found.')

        with open(tmp_config, 'a') as file:
            file.write(f'\n\n')
            file.write(f'width: {self.width_fg}\n')
            file.write(f'height: {self.height}\n')

        subprocess.run((f'/opt/EDTpdv/initcam -u {self.pdv_unit}'
                        f' -c {self.pdv_channel} -f {tmp_config}').split(' '),
                       stdout=subprocess.PIPE)

    def prepare_camera_for_size(self):
        print(
            'Calling prepare_camera on generic EDTCameraClass. Nothing happens here.'
        )

    def prepare_camera_finalize(self):
        print(
            'Calling prepare_camera on generic EDTCameraClass. Nothing happens here.'
        )

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


    def _start_taker_no_dependents(self):
        exec_path = os.environ['HOME'] + '/src/camstack/src/edttake'
        self.edttake_tmux_command = f'{exec_path} -s {self.STREAMNAME} -u {self.pdv_unit} -c {self.pdv_channel} -l 0 -N 4'
        if self.EDTTAKE_CAST:
            self.edttake_tmux_command += ' -8'  # (byte pair) -> (ushort) casting.
        if self.EDTTAKE_UNSIGNED:
            self.edttake_tmux_command += ' -U'  # Maintain unsigned output (CRED1, OCAM)

        # Let's do it.
        tmux_util.send_keys(self.take_tmux_pane, self.edttake_tmux_command)
        # We recreated the SHM !
        time.sleep(1.)

        if self.taker_cset_prio[1] is not None: # Set rtprio !
            subprocess.run([
                'make_cset_and_rt',
                str(tmux_util.find_pane_running_pid(self.take_tmux_pane)), # PID
                str(self.taker_cset_prio[1]), # PRIORITY
                self.taker_cset_prio[0] # CPUSET
            ])
        self.grab_shm_fill_keywords()
        self.prepare_camera_finalize()

        self.start_auxiliary_thread()

    def _start(self):
        '''
        Alias
        '''
        self._start_taker_no_dependents()

    def grab_shm_fill_keywords(self):
        # Only the init, or the regular updates ?
        self.camera_shm = self._get_SHM()
        self._fill_keywords()

    def _get_SHM(self):
        # Separated to be overloaded if need be (thinking of you, OCAM !)
        return SHM(self.STREAMNAME, symcode=0)

    def _fill_keywords(self):
        # These are pretty much defaults - we don't know anything about this
        # basic abstract camera
        preex_keywords = self.camera_shm.get_keywords(True)
        preex_keywords.update(self.KEYWORDS)

        preex_keywords['DETECTOR'] =  f'FG unit {self.pdv_unit} ch. {self.pdv_channel}'
        preex_keywords['BIN-FCT1'] =  1
        preex_keywords['BIN-FCT2'] =  1
        preex_keywords['CROP_OR1'] =  0
        preex_keywords['CROP_OR2'] =  0
        preex_keywords['CROPPED'] = 'N/A'

        self.camera_shm.set_keywords(preex_keywords)

    def set_camera_size(self, height: int, width: int):
        '''
            That's a pretty agressive change - and thus, we're pretty much restarting everything
            So actually the constructor could just call this ?
        '''
        self.kill_taker_and_dependents()

        self.height = height
        self.width = width
        self.width_fg = (width, 2 * width)[self.EDTTAKE_CAST]
        self.init_pdv_configuration()

        self.start_frame_taker_and_dependents()

        self.grab_shm_fill_keywords()

    def get_fg_parameters(self):
        # We don't need to get them, because we set them in init_pdv_configuration
        pass

    def set_fg_parameters(self):
        pass

    def send_command(self, cmd, base_timeout: float = 100.):
        '''
            Wrap to the serial
            That supposes we HAVE serial... maybe we'll move this to a subclass
        '''
        return self.edt_iface.send_command(cmd, base_timeout=base_timeout)

    def raw(self, cmd):
        '''
            Just an alias
        '''
        return self.send_command(cmd)

    def poll_camera_for_keywords(self):
        print(
            'Calling poll_camera_for_keywords on generic EDTCameraClass. Nothing happens here.'
        )

    def start_auxiliary_thread(self):
        self.event = threading.Event()
        self.thread = threading.Thread(target=self.auxiliary_thread_run_function)
        self.thread.start()

    def stop_auxiliary_thread(self):
        if self.thread is not None:
            self.event.set()
            self.thread.join()


    def auxiliary_thread_run_function(self):
        while True:
            ret = self.event.wait(10)
            if ret: # Signal to break the loop
                break
	
            # Dependents cset + RTprio checking
            for proc in self.dependent_processes:
                proc.make_children_rt()

            # Camera specifics !
            try:
                self.poll_camera_for_keywords()
            except Exception as e:
                print("Polling thread: error ", e)

            print(f'Thread is running at {time.time()}')



class EDTCamera(EDTCameraNoModes):

    INTERACTIVE_SHELL_METHODS = ['set_camera_mode'
                                 ] + EDTCameraNoModes.INTERACTIVE_SHELL_METHODS

    MODES = {}  # Define the format ?
    EDTTAKE_CAST = False

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id,
                 unit: int,
                 channel: int,
                 basefile: str,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):
        width, height = self._fg_size_from_mode(mode_id)

        self.current_mode_id = mode_id
        self.current_mode = self.MODES[mode_id]

        EDTCameraNoModes.__init__(self,
                                  name,
                                  stream_name,
                                  height,
                                  width,
                                  unit,
                                  channel,
                                  basefile,
                                  taker_cset_prio = taker_cset_prio,
                                  dependent_processes=dependent_processes)

    def _fg_size_from_mode(self, mode_id):
        width, height = self.MODES[mode_id].fgsize
        return width, height

    def prepare_camera_for_size(self, mode_id=None):
        # Gets called during constructor and set_mode
        if mode_id is None:
            mode_id = self.current_mode_id
        print(
            'Calling prepare_camera_for_size on generic EDTCameraClass. Setting size for shmimTCPreceive.'
        )
        for dep_proc in self.dependent_processes:
            if 'shmimTCPreceive' in dep_proc.cli_cmd:
                cm = self.current_mode
                h, w = (cm.x1 - cm.x0 + 1) // cm.binx, (cm.y1 - cm.y0 + 1) // cm.biny
                dep_proc.cli_args = (dep_proc.cli_args[0], h, w)

    def prepare_camera_finalize(self, mode_id=None):
        # Gets called during constructor and set_mode
        if mode_id is None:
            mode_id = self.current_mode_id
        print(
            'Calling prepare_camera_finalize on generic EDTCameraClass. Nothing happens here.'
        )

    def set_camera_mode(self, mode_id):
        '''
            Quite same as above - but mostly meant to be called by subclasses that do have defined modes.
        '''
        self.kill_taker_and_dependents()

        self.current_mode_id = mode_id
        self.current_mode = self.MODES[mode_id]
        self.width, self.height = self._fg_size_from_mode(mode_id)
        self.width_fg = self.width * (1, 2)[self.EDTTAKE_CAST]

        self.init_pdv_configuration()

        self.prepare_camera_for_size()

        self.start_frame_taker_and_dependents()

        self.grab_shm_fill_keywords()

        self.prepare_camera_finalize()

    def set_mode(self, mode_id):
        '''
            Alias
        '''
        self.set_camera_mode(mode_id)

    def _fill_keywords(self):
        preex_keywords = self.camera_shm.get_keywords(True)
        preex_keywords.update(self.KEYWORDS)

        self.camera_shm.set_keywords(preex_keywords)

        cm = self.current_mode

        self.camera_shm.update_keyword('BIN-FCT1', cm.binx)
        self.camera_shm.update_keyword('BIN-FCT2', cm.biny)
        self.camera_shm.update_keyword('CROP_OR1', cm.x0)
        self.camera_shm.update_keyword('CROP_OR2', cm.y0)
        self.camera_shm.update_keyword('CROP_EN1', cm.x1)
        self.camera_shm.update_keyword('CROP_EN2', cm.y1)
        self.camera_shm.update_keyword('CROPPED', 'N/A')

    def change_camera_parameters(self):
        raise NotImplementedError(
            "Set camera mode should have a camera-specific implementation")

    def register_dependent(self):
        pass
