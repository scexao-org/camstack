#import libtmux as tmux
from camstack.core import tmux as tmux_util
from camstack.core.edtinterface import EdtInterfaceSerial
from pyMilk.interfacing.isio_shmlib import SHM

from typing import List, Any

import os
import time
import subprocess


class EDTCameraNoModes:
    '''
        Standard basic stuff that is common over EDT framegrabbers
        Written with the mindset "What should be common between CRED2, Andors and OCAM ?"
        And implements the server side management of the imgtake
    '''

    INTERACTIVE_SHELL_METHODS = ['send_command', 'close', 'release']

    KEYWORDS = {  # Format is name: (value, description) - this list CAN be figured out from a redis query.
        'BIN-FCT1': (1, 'Binning factor of the X axis (pixel)'),
        'BIN-FCT2': (1, 'Binning factor of the Y axis (pixel)'),
        'BSCALE': (1.0, 'Real=fits-value*BSCALE+BZERO'),
        'BUNIT': ('ADU', 'Unit of original values'),
        'BZERO': (0.0, 'Real=fits-value*BSCALE+BZERO'),
        'CROP_OR1': (0, 'Origin in X of the cropped window (pixel)'),
        'CROP_OR2': (0, 'Origin in Y of the cropped window (pixel)'),
        'CROPPED':
        ('False', 'Boolean indicating if the image is windowed or full frame'),
        'DET-TMP': (0.0, 'Detector temperature (K)'),
        'DETECTOR': ('DET', 'Name of the detector'),
        'DETGAIN': (1., 'Detector gain'),
        'DETMODE': ('base', 'Detector mode'),
        'EXPTIME': (0.0, 'Total integration time of the frame (sec)'),
        'FRATE': (0., 'Frame rate of the acquisition (Hz)'),
        'GAIN': (1., 'AD conversion factor (electron/ADU)'),
        'NDR': (1, 'Number of non-destructive reads'),
        'EXTTRIG':
        ('False', 'Boolean indicating if an extrernal trigger is used')
    }

    EDTTAKE_CAST = False  # Only OCAM overrides that

    def __init__(self,
                 name: str,
                 stream_name: str,
                 height: int,
                 width: int,
                 unit: int,
                 channel: int,
                 basefile: str,
                 no_start: bool = False,
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
        # ====================
        self.start_frame_taker_and_dependents()

        # ====================
        # ALLOCATE KEYWORDS
        # ====================

        self.camera_shm = None
        self.grab_shm_fill_keywords()
        # Maybe we can use a class variable as well to define what the expected keywords are ?

        # =================================
        # FINALIZE A FEW DETAILS POST-START
        # =================================
        self.prepare_camera_finalize()

        # TODO csets and RT prios - through CACAO ?

    def kill_taker_and_dependents(self):
        # Kill the dependent processes in reverse order
        for dep_process in self.dependent_processes[::-1]:
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
        self.edttake_tmux_name = f'{self.NAME}_edt'
        self.take_tmux_pane = tmux_util.find_or_create(self.edttake_tmux_name)
        tmux_util.kill_running(self.take_tmux_pane)

    def init_pdv_configuration(self):
        if self.is_taker_running():
            raise AssertionError(
                'Cannot change FG config while taker is running')

        tmp_config = '/tmp/' + self.NAME + '.cfg'
        res = subprocess.run(['cp', self.base_config_file, tmp_config],
                             stdout=subprocess.PIPE)
        if res.returncode != 0:
            raise FileNotFoundError(
                f'EDT cfg file {self.base_config_file} not found.')

        with open(tmp_config, 'a') as file:
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

    def start_frame_taker_and_dependents(self):
        self._start_taker_no_dependents()
        # Now handle the dependent processes

        for dep_process in self.dependent_processes:
            dep_process.start()

    def _start_taker_no_dependents(self):
        exec_path = '/home/scexao/src/camstack/src/edttake'
        self.edttake_tmux_command = f'{exec_path} -s {self.STREAMNAME} -u {self.pdv_unit} -c {self.pdv_channel} -l 0 -N 4'
        if self.EDTTAKE_CAST:
            self.edttake_tmux_command += ' -8'  # (byte pair) -> (ushort) casting.

        # Let's do it.
        tmux_util.send_keys(self.take_tmux_pane, self.edttake_tmux_command)
        time.sleep(1)

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

        self.camera_shm.set_keywords(preex_keywords)

        self.camera_shm.update_keyword('BIN-FCT1', 1)
        self.camera_shm.update_keyword('BIN-FCT2', 1)
        self.camera_shm.update_keyword('CROP_OR1', 0)
        self.camera_shm.update_keyword('CROP_OR2', 0)
        self.camera_shm.update_keyword('CROPPED', 'N/A')

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

    def send_command(self, cmd):
        '''
            Wrap to the serial
            That supposes we HAVE serial... maybe we'll move this to a subclass
        '''
        return self.edt_iface.send_command(cmd)

    def raw(self, cmd):
        '''
            Just an alias
        '''
        return self.send_command(cmd)


class EDTCamera(EDTCameraNoModes):

    INTERACTIVE_SHELL_METHODS = [] + EDTCameraNoModes.INTERACTIVE_SHELL_METHODS

    MODES = {}  # Define the format ?
    EDTTAKE_CAST = False

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id,
                 unit: int,
                 channel: int,
                 basefile: str,
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
                                  dependent_processes=dependent_processes)

    def _fg_size_from_mode(self, mode_id):
        width, height = self.MODES[mode_id].fgsize
        return width, height

    def prepare_camera_for_size(self, mode_id=None):
        # Gets called during constructor and set_mode
        if mode_id is None:
            mode_id = self.current_mode_id
        print(
            'Calling prepare_camera_for_size on generic EDTCameraClass. Nothing happens here.'
        )

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
        print(preex_keywords)
        print(33)
        preex_keywords.update(self.KEYWORDS)

        self.camera_shm.set_keywords(preex_keywords)
        
        cm = self.current_mode

        self.camera_shm.update_keyword('BIN-FCT1', cm.binx)
        self.camera_shm.update_keyword('BIN-FCT2', cm.biny)
        self.camera_shm.update_keyword('CROP_OR1', cm.x0)
        self.camera_shm.update_keyword('CROP_OR2', cm.y0)
        self.camera_shm.update_keyword('CROPPED', 'N/A')

    def change_camera_parameters(self):
        raise NotImplementedError(
            "Set camera mode should have a camera-specific implementation")

    def register_dependent(self):
        pass
