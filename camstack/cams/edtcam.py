import os
import subprocess
import time
import logging as logg

from typing import Union, Tuple, List, Any

from camstack.cams.base import BaseCamera
from hwmain.edt.edtinterface import EdtInterfaceSerial

from camstack.core.utilities import CameraMode


class EDTCamera(BaseCamera):

    INTERACTIVE_SHELL_METHODS = ['send_command'] + \
        BaseCamera.INTERACTIVE_SHELL_METHODS

    MODES = {}

    KEYWORDS = {}
    KEYWORDS.update(BaseCamera.KEYWORDS)

    # Signed / unsigned EDT output - 8/16 bit mixup at grabbing
    EDTTAKE_CAST = False  # Only OCAM overrides that
    EDTTAKE_UNSIGNED = True
    EDTTAKE_EMBEDMICROSECOND = False  # We want this for CRED1 / 2 but not elsewhere

    def __init__(self, name: str, stream_name: str,
                 mode_id: Union[CameraMode, Tuple[int, int]], pdv_unit: int,
                 pdv_channel: int, pdv_basefile: str, no_start: bool = False,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes: List[Any] = []):

        self.pdv_unit = pdv_unit
        self.pdv_channel = pdv_channel

        self.pdv_basefile = pdv_basefile
        self.pdv_taps = 1  # We will retrive this from the FG.

        self.edt_iface = None  # See self.init_framegrab_backend

        BaseCamera.__init__(self, name, stream_name, mode_id,
                            no_start=no_start, taker_cset_prio=taker_cset_prio,
                            dependent_processes=dependent_processes)

    def init_framegrab_backend(self):
        logg.debug('init_framegrab_backend @ EDTCamera')
        if self.is_taker_running():
            msg = 'Cannot change FG config while FG is running'
            logg.error(msg)
            raise AssertionError(msg)

        self.width_fg = self.width * (1, 2)[self.EDTTAKE_CAST]

        # Prepare a cfg file like the base one + width and height amended

        tmp_config = '/tmp/' + os.environ['USER'] + '_' + self.NAME + '.cfg'
        # Adding a username here, because we can't overwrite the file of another user !
        res = subprocess.run(['cp', self.pdv_basefile, tmp_config],
                             stdout=subprocess.PIPE)
        if res.returncode != 0:
            msg = f'EDT cfg file {self.base_config_file} not found.'
            logg.error(msg)
            raise FileNotFoundError(msg)

        # Find the number of taps from the file.
        with open(tmp_config, 'r') as file:
            for line in file:
                if line == "":  # File finished
                    msg = f'EDT cfg file {self.base_config_file} contains no CL_DATA_PATH_NORM directive.'
                    logg.error(msg)
                    raise AssertionError(msg)
                linespl = line.rstrip().split()
                if len(linespl) > 0 and linespl[0] == "CL_DATA_PATH_NORM:":
                    self.pdv_taps = int('0x' + linespl[1][0], 16) + 1

        with open(tmp_config, 'a') as file:
            file.write(f'\n\n'
                       f'width: {self.width_fg}\n'
                       f'height: {self.height}\n')

        # Init the EDT FG
        subprocess.run((f'/opt/EDTpdv/initcam -u {self.pdv_unit}'
                        f' -c {self.pdv_channel} -f {tmp_config}').split(' '),
                       stdout=subprocess.PIPE)

        # Open a serial handle
        # It's possible initcam messed with it so we reopen it
        self.edt_iface = EdtInterfaceSerial(self.pdv_unit, self.pdv_channel)

    def _prepare_backend_cmdline(self, reuse_shm: bool = False):

        # Prepare the cmdline for starting up!
        exec_path = os.environ['SCEXAO_HW'] + '/bin/hwacq-edttake'
        self.taker_tmux_command = f'{exec_path} -s {self.STREAMNAME} -u {self.pdv_unit} -c {self.pdv_channel} -l 0 -N 4'
        if self.EDTTAKE_CAST:
            self.taker_tmux_command += ' -8'  # (byte pair) -> (ushort) casting.
        if self.EDTTAKE_UNSIGNED:
            self.taker_tmux_command += ' -U'  # Maintain unsigned output (CRED1, OCAM)
        if self.EDTTAKE_EMBEDMICROSECOND:
            self.taker_tmux_command += ' -t'  # Embed microsecond grab time at pixel 8
        if reuse_shm:
            self.taker_tmux_command += ' -R'  # Do not overwrite the SHM.

    def _ensure_backend_restarted(self):
        # Plenty simple enough for EDT, never failed me
        time.sleep(1.0)

    def send_command(self, cmd, base_timeout: float = 100.):
        '''
            Wrap to the serial
            That supposes we HAVE serial... maybe we'll move this to a subclass
        '''
        logg.debug(f'EDTCamera: send_command: "{cmd}"')
        return self.edt_iface.send_command(cmd, base_timeout=base_timeout)

    def raw(self, cmd):
        '''
            Just an alias
        '''
        return self.send_command(cmd)
