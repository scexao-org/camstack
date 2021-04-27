'''
    Buffy
'''
import os
import time
from typing import Union

from camstack.cams.edt_base import EDTCamera

from camstack.core.utilities import CameraMode


class ROMODES:
    globalresetsingle = 'globalresetsingle'
    globalresetcds = 'globalresetcds'


class CRED1(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'set_readout_mode', 'get_readout_mode', 'set_gain','get_gain',
        'set_NDR', 'get_NDR', 'set_fps',
        'get_fps', 'set_tint', 'get_tint', 'get_temperature', 'FULL'] + \
        EDTCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'full'
    MODES = {
        # FULL 320 x 256
        FULL: CameraMode(x0=0, x1=319, y0=0, y1=255, fps=1738.152),
        # 64x64 centered
        1: CameraMode(x0=128, x1=191, y0=96, y1=159, fps=20679.012),
        # 128x128 centered
        2: CameraMode(x0=96, x1=223, y0=64, y1=191, fps=7008.368),
        # 160x160 16px offside
        3: CameraMode(x0=64, x1=223, y0=64, y1=191, fps=1e4),
        # 192x192 centered
        4: CameraMode(x0=64, x1=255, y0=32, y1=223, fps=1e4),
        # 224x224 16px offside
        5: CameraMode(x0=32, x1=255, y0=32, y1=223, fps=1e4),
        # 256x256 centered
        6: CameraMode(x0=32, x1=287, y0=0, y1=255, fps=1e4), # TODO FIX FPS
    }

    KEYWORDS = {
        'DET-PRES': (0.0, 'Detector pressure (mbar)'),
    }
    KEYWORDS.update(EDTCamera.KEYWORDS)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 'full',
                 unit: int = 1,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):

        # Allocate and start right in the appropriate binning mode
        self.synchro = False
        basefile = os.environ['HOME'] + '/src/camstack/config/cred1_16bit.cfg'
        self.NDR = None  # Grabbed in prepare_camera_finalize

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, stream_name, mode_id, unit, channel,
                           basefile, taker_cset_prio=taker_cset_prio, dependent_processes=dependent_processes)

        # ======
        # AD HOC
        # ======

        # Issue a few standards for CRED1
        self.send_command('set led off')
        self.send_command('set events off')
        self.set_gain(50)

    # =====================
    # AD HOC PREPARE CAMERA
    # =====================

    def prepare_camera_for_size(self, mode_id = None):

        if mode_id is None:
            mode_id = self.current_mode_id

        # Not really handling fps/tint for the OCAM, we just assume an ext trigger
        if mode_id == 'full':  #TODO
            self.send_command('set cropping off')
        else:
            self.send_command('set cropping on')

        mode = self.MODES[mode_id]
        self._set_check_cropping(mode.x0, mode.x1, mode.y0, mode.y1)


    def prepare_camera_finalize(self, mode_id: int = None):

        if mode_id is None:
            mode_id = self.current_mode_id
        cm = self.MODES[mode_id]

        # Changing the binning trips the external sync (at lest on OCAM ?)
        self.set_synchro(self.synchro)

        # Initialization of the camera: reset the NDR to globalresetcds, NDR2.
        if self.NDR is None:
            self.set_readout_mode(ROMODES.globalresetcds)
            self.set_NDR(2)

        if cm.fps is not None:
            self.set_fps(cm.fps)
        if cm.tint is not None:
            self.set_tint(cm.tint)

    def send_command(self, cmd, format=True):
        # Just a little bit of parsing to handle the CRED1 format
        # FLI has *decided* to end all their answers with a return prompt "\r\nfli-cli>"
        res = EDTCamera.send_command(self, cmd)[:-10]

        if 'cli>' in res:
            # We might have gotten a double answer
            # Seems to happen when requesting pressure
            cut = res.index('>')
            res = res[cut+1:]

        if format and ':' in res:
            return res.split(':')
        else:
            return res

    def _fill_keywords(self):
        # Do a little more filling than the subclass after changing a mode
        # And call the thread-polling function
        #TODO: thread temp polling

        EDTCamera._fill_keywords(self)

        self.camera_shm.update_keyword('DETECTOR', 'CRED2')
        self.camera_shm.update_keyword('CROPPED',
                                       self.current_mode_id != 'full')
        self.get_NDR()  # Sets 'NDR'
        self.get_tint()  # Sets 'EXPTIME'
        self.get_fps()  # Sets 'FRATE'

        # Additional fill-up of the camera state
        self.get_gain()  # Sets 'DETGAIN'
        self.get_readout_mode() # Set DETMODE

        # Call the stuff that we can't know otherwise
        self.poll_camera_for_keywords()  # Sets 'DET-TMP'

    def poll_camera_for_keywords(self):
        self.get_temperature() # Sets DET-TMP
        time.sleep(.1)
        self.get_cryo_pressure() # Sets DET-PRES
        time.sleep(.1)

    # ===========================================
    # AD HOC METHODS - TO BE BOUND IN THE SHELL ?
    # ===========================================

    def _get_cropping(self):
        # We mimicked the definition of the cropmodes from the CRED2
        # BUT the CRED1 is 1-base indexed.... remove 1
        xx, yy = self.send_command('cropping raw')[1:]
        x0, x1 = [(int(xxx)-1) for xxx in xx.split('-')]
        x0 = 32 * x0
        x1 = 32 * x1 + 31 # column blocks of 32
        y0, y1 = [int(yyy) - 1 for yyy in yy.split('-')]
        return x0, x1, y0, y1

    def _set_check_cropping(self, x0, x1, y0, y1):
        for _ in range(3):
            gx0, gx1, gy0, gy1 = self._get_cropping()
            if gx0 == x0 and gx1 == x1 and gy0 == y0 and gy1 == y1:
                return x0, x1, y0, y1
            if gx0 != x0 or gx1 != x1:
                # BUT the CRED1 is 1-base indexed.... add 1
                self.send_command('set cropping columns %u-%u' % (x0 // 32 + 1, x1 // 32 + 1))
                # CRED2s are finnicky with cropping, we'll add a wait
                time.sleep(.5)
            if gy0 != y0 or gy1 != y1:
                # BUT the CRED1 is 1-base indexed.... add 1
                self.send_command('set cropping rows %u-%u' % (y0 + 1, y1 + 1))
                time.sleep(.5)
        raise AssertionError(
            f'Cannot set desired crop {x0}-{x1} {y0}-{y1} after 3 tries')

    def set_synchro(self, synchro: bool):
        val = ('off', 'on')[synchro]
        _ = self.send_command(f'set extsynchro {val}')
        res = self.send_command('extsynchro raw')
        self.synchro = {'off': False, 'on': True}[res]
        self.camera_shm.update_keyword('EXTTRIG',
                                       ('False', 'True')[self.synchro])
        return self.synchro

    def set_readout_mode(self, mode):
        self.send_command(f'set mode {mode}')
        return self.get_readout_mode()

    def get_readout_mode(self):
        res = self.send_command('mode raw')
        self.camera_shm.update_keyword('DETMODE', res)
        return res

    def set_gain(self, gain: int):
        self.send_command(f'set gain {gain}')
        return self.get_gain()

    def get_gain(self):
        res = float(self.send_command('gain raw'))
        self.camera_shm.update_keyword('DETGAIN', res)
        return res

    def set_NDR(self, NDR: int):
        if NDR < 1 or not type(NDR) is int:
            raise AssertionError(f'Illegal NDR value: {NDR}')
        self.send_command(f'set nbreadworeset {NDR}')
        return self.get_NDR()

    def get_NDR(self):
        self.NDR = int(self.send_command('nbreadworeset raw'))
        self.camera_shm.update_keyword('NDR', self.NDR)
        self.camera_shm.update_keyword('DETMODE',
                                       ('globalresetsingle', 'globalresetcds')[self.NDR > 1])
        return self.NDR

    def set_fps(self, fps: float):
        self.send_command(f'set fps {fps}')
        return self.get_fps()

    def get_fps(self):
        fps = float(self.send_command('fps raw'))
        self.camera_shm.update_keyword('FRATE', fps)
        self.camera_shm.update_keyword('EXPTIME', 1. / fps)
        return fps

    def max_fps(self):
        return float(self.send_command('maxfps raw'))

    def set_tint(self, tint: float):
        # CRED1 has no tint management
        return 1. / self.set_fps(1 / tint)

    def get_tint(self):
        # CRED1 has no tint management
        return 1. / self.get_fps()

    def get_cryo_pressure(self):
        pres = float(self.send_command('pressure raw'))
        self.camera_shm.update_keyword('DET-PRES', pres)
        return pres

    def get_temperature(self):
        temp = float(self.send_command('temp cryostat diode raw'))
        self.camera_shm.update_keyword('DET-TMP', temp)
        return temp


    def _shutdown(self):
        input(f'Detector temperature {self.get_temperature()} K; proceed anyway ? Ctrl+C aborts.')
        res = self.send_command('shutdown')
        if 'OK' in res:
            while True:
                time.sleep(5)
                print('Camera shutdown was acknowledged.')
                print('Processes on this end were killed.')
                print('You should quit this shell.')
                print('You\'ll need to power cycle the CRED2 to reboot it.')


class Buffy(CRED1):

    INTERACTIVE_SHELL_METHODS = [] + CRED1.INTERACTIVE_SHELL_METHODS

    MODES = {}
    MODES.update(CRED1.MODES)

    KEYWORDS = {}
    KEYWORDS.update(CRED1.KEYWORDS)

    def _fill_keywords(self):
        CRED1._fill_keywords(self)

        # Override detector name
        self.camera_shm.update_keyword('DETECTOR', 'CRED1 - BUFFY')


# Quick shorthand for testing
if __name__ == "__main__":
    cam = Buffy('buffycam', 'kcam', mode_id='full', unit=1, channel=0)
    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
