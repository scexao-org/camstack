'''
    Manage the ocam
'''

from camstack.cams.edt_base import EDTCamera
from camstack.core.utilities import CameraMode


class OCAM2K(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'set_binning',
        'gain_protection_reset',
        'set_gain',
        'set_synchro',
        'set_fps',
        'get_temperature',
        'set_cooling',
        'set_temperature_setpoint'
    ] + EDTCamera.INTERACTIVE_SHELL_METHODS

    # For ocam, the CameraMode content is *not* used for the camera setup, only the FG setup
    MODES = {
        # Ocam full, unbinned
        1: CameraMode(x0=0, x1=239, y0=0, y1=239, binx=1, biny=1, fgsize=(1056 // 2, 121)),
        # Ocam bin x2 - numbering (1,3) is from first light, for historical origins ?
        3: CameraMode(x0=0, x1=239, y0=0, y1=239, binx=2, biny=2, fgsize=(1056 // 2, 62)),
    }

    KEYWORDS = {} # TODO: see about that later.

    EDTTAKE_CAST = True

    def __init__(self, name: str, stream_name:str,
                 binning: bool = True,
                 unit: int = 3, channel: int = 0):

        # Allocate and start right in the appropriate binning mode

        mode_id = (1, 3)[binning]
        basefile = '/home/scexao/src/camstack/config/ocam_full.cfg'

        self.synchro = True # TODO replace this with a kw dict matching the SHM

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, stream_name,
                           mode_id, unit, channel, basefile)

        # ======
        # AD HOC 
        # ======

        # Issue a few standards for OCAM
        self.send_command('interface 0') # Disable verbosity to be able to parse temp
        self.gain_protection_reset()
        self.set_gain(1)
        self.set_synchro(True) # Is called by the setmode in the constructor.
        
    
    
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

    # ===========================================
    # AD HOC METHODS - TO BE BOUND IN THE SHELL ?
    # ===========================================

    def set_binning(self, binning: bool):
        self.set_camera_mode((1, 3)[binning])

    def gain_protection_reset(self):
        self.send_command('protection_reset')

    def set_gain(self, gain: int):
        self.send_command(f'set gain {gain}')
        # TODO set SHM keyword !

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
        temps = [float(x[:-1]) for x in ret.split('[')[1:]]
        self.is_cooling = bool(temps[8])
        # TODO update keywords & internals
        return temps[0], temps[7] / 10. # temp, setpoint

    def set_cooling(self):
        self.get_temperature()
        self.is_cooling = not self.is_cooling
        self.send_command('temp ' + ('off', 'on')[self.is_cooling])

    def set_temperature_setpoint(self, temp):
        self.send_command(f'temp {int(temp)}')
        return self.get_temperature()[1]

# Quick shorthand for testing
if __name__ == "__main__":
    ocam = OCAM2K('ocam', 'ocam2krc', unit=3, channel=0, binning=True)
    from camstack.core.utilities import shellify_methods
    shellify_methods(ocam, globals())