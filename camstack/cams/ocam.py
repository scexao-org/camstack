'''
    Manage the ocam
'''

from camstack.cams.edt_base import EDTCamera
from camstack.core.utilities import CameraMode


class OCAM2K(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'set_binning', 'gain_protection_reset', 'set_gain', 'get_gain',
        'set_synchro', 'set_fps', 'get_temperature', 'set_cooling',
        'set_temperature_setpoint'
    ] + EDTCamera.INTERACTIVE_SHELL_METHODS

    # For ocam, the CameraMode content is *not* used for the camera setup, only the FG setup
    MODES = {
        # Ocam full, unbinned
        1:
        CameraMode(x0=0,
                   x1=239,
                   y0=0,
                   y1=239,
                   binx=1,
                   biny=1,
                   fgsize=(1056 // 2, 121)),
        # Ocam bin x2 - numbering (1,3) is from first light, for historical origins ?
        3:
        CameraMode(x0=0,
                   x1=239,
                   y0=0,
                   y1=239,
                   binx=2,
                   biny=2,
                   fgsize=(1056 // 2, 62)),
    }

    KEYWORDS = {}  # TODO: see about that later.

    EDTTAKE_CAST = True

    def __init__(self,
                 name: str,
                 mangled_stream_name: str,
                 final_stream_name: str,
                 binning: bool = True,
                 unit: int = 3,
                 channel: int = 0,
                 dependent_processes=[]):

        # Allocate and start right in the appropriate binning mode

        mode_id = (1, 3)[binning]
        basefile = '/home/scexao/src/camstack/config/ocam_full.cfg'

        self.synchro = True  # TODO replace this with a kw dict matching the SHM
        self.STREAMNAME_ocam2d = final_stream_name

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, mangled_stream_name, mode_id, unit, channel,
                           basefile, dependent_processes)

        # ======
        # AD HOC
        # ======

        # Issue a few standards for OCAM
        self.send_command(
            'interface 0')  # Disable verbosity to be able to parse temp
        self.gain_protection_reset()
        self.set_gain(1)
        self.set_synchro(True)  # Is called by the setmode in the constructor.

    # =====================
    # AD HOC PREPARE CAMERA
    # =====================

    def prepare_camera(self, mode_id: int = None):

        if mode_id is None:
            mode_id = self.current_mode_id

        # Not really handling fps/tint for the OCAM, we just assume an ext trigger
        if mode_id == 1:
            self.send_command('binning off')
        elif mode_id == 3:
            self.send_command('binning on')

        # Changing the binning trips the external sync.
        self.set_synchro(self.synchro)

        # AD HOC PREPARE DEPENDENTS
        # Change the argument to ocam_decode
        for dep_proc in self.dependent_processes:
            if 'decode' in dep_proc.cli_cmd:
                dep_proc.cli_args = (mode_id,)
            if 'shmimTCPreceive' in dep_proc.cli_cmd:
                cm = self.current_mode
                h, w = (cm.x1 - cm.x0 + 1) // cm.binx, (cm.y1 - cm.y0 + 1) // cm.biny
                dep_proc.cli_args = (dep_proc.cli_args[0], h, w)


    def send_command(self, cmd, format=True):
        # Just a little bit of parsing to handle the OCAM format
        res = EDTCamera.send_command(self, cmd)
        if format:
            wherechevron = res.index('>')
            return res[wherechevron + 2:-1].split('][')
        else:
            return res

    # ===========================================
    # AD HOC METHODS - TO BE BOUND IN THE SHELL ?
    # ===========================================

    def set_binning(self, binning: bool):
        self.set_camera_mode((1, 3)[binning])

    def gain_protection_reset(self):
        self.send_command('protection reset')

    def set_gain(self, gain: int):
        res = self.send_command(f'gain {gain}')
        return int(res[0])
        # TODO set SHM keyword !

    def get_gain(self):
        res = self.send_command('gain')
        # TODO set SHM keyword !
        return int(res[0])

    def set_synchro(self, val: bool):
        self.send_command(f'synchro {("off","on")[val]}')
        self.synchro = val
        # TODO set SHM keyword !
        # TODO disable fps kw

    def set_fps(self, fps: float):
        # 0 sets maxfps
        if self.synchro:
            raise AssertionError('No fps set in synchro mode')
        self.send_command(f'fps {int(fps)}')

    def get_temperature(self):
        return self._get_temperature()[0]

    def _get_temperature(self):
        ret = self.send_command('temp')
        # Expected return: <1>[-45.2][23][13][24][0.1][9][12][-450][1][10594]
        temps = [float(x) for x in ret]
        self.is_cooling = bool(temps[8])
        # TODO update keywords & internals
        return temps[0], temps[7] / 10.  # temp, setpoint

    def set_cooling(self):
        self.get_temperature()
        self.is_cooling = not self.is_cooling
        self.send_command('temp ' + ('off', 'on')[self.is_cooling])

    def set_temperature_setpoint(self, temp):
        self.send_command(f'temp {int(temp)}')
        return self.get_temperature()[1]


# Quick shorthand for testing
if __name__ == "__main__":

    binning, mode = True, 3

    # Prepare dependent processes
    from camstack.core.utilities import DependentProcess, RemoteDependentProcess
    ocam_decode = DependentProcess(
        tmux_name='ocam_decode',
        cli_cmd='/home/scexao/src/camstack/ocamdecode/ocamdecoderun_mode %u',
        cli_args=(mode,),
    )
    tcp_recv = RemoteDependentProcess(
        tmux_name='streamTCPreceive_30107',
        # Urrrrrh this is getting messy
        cli_cmd='milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c aol0COM 30107',
        cli_args=('ocam2dalt', 120, 120),
        remote_host='133.40.161.194'
    )
    tcp_send = DependentProcess(
        tmux_name='ocam_tcp',
        cli_cmd='sleep 5; OMP_NUM_THREADS=1 /home/scexao/bin/shmimTCPtransmit %s %s %u',
        cli_args=('ocam2dalt', '10.20.70.1', 30107),
    )

    ocam = OCAM2K('ocam',
                  'ocam2krc',
                  'ocam2d',
                  unit=3,
                  channel=0,
                  binning=binning,
                  dependent_processes=[ocam_decode, tcp_recv, tcp_send])
    from camstack.core.utilities import shellify_methods
    shellify_methods(ocam, globals())