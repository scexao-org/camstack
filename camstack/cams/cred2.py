'''
    Chuck, Rajni, GLINT
'''
from camstack.core.edtinterface import EdtInterfaceSerial
import os
import time
from typing import Union

from camstack.cams.edt_base import EDTCamera

from camstack.core.utilities import CameraMode

class CRED2(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'set_synchro', 'set_gain','get_gain', 'set_NDR', 'get_NDR', 'set_fps',
        'get_fps', 'set_tint', 'get_tint', 'get_temperature',
        'set_temperature_setpoint', 'FULL'] + \
        EDTCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'full'

    MODES = {
        # FULL 640 x 512
        FULL:
        CameraMode(x0=0, x1=639, y0=0, y1=511),
        # 320x256 half frame, centered
        0:
        CameraMode(x0=160,
                   x1=479,
                   y0=128,
                   y1=383,
                   fps=1500.082358000,
                   tint=0.000663336),
    }

    KEYWORDS = {}
    KEYWORDS.update(EDTCamera.KEYWORDS)

    EDTTAKE_UNSIGNED = False

    def __init__(self,
                 name: str,
                 stream_name: str,
                 mode_id: int = 0,
                 unit: int = 0,
                 channel: int = 0,
                 taker_cset_prio: Union[str, int] = ('system', None),
                 dependent_processes=[]):

        # Allocate and start right in the appropriate binning mode
        self.synchro = False
        basefile = os.environ['HOME'] + '/src/camstack/config/cred2_16bit.cfg'
        self.NDR = None  # Grabbed in prepare_camera_finalize

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, stream_name, mode_id, unit, channel,
                           basefile, taker_cset_prio=taker_cset_prio, dependent_processes=dependent_processes)

        # ======
        # AD HOC
        # ======

        # Issue a few standards for CRED2
        self.send_command('set cropping on')
        self.send_command('set fan mode manual')
        self.send_command('set fan speed 0')
        self.send_command('set led off')
        self.set_gain('high')
        self.set_temperature_setpoint(-40.0)

    # =====================
    # AD HOC PREPARE CAMERA
    # =====================

    def prepare_camera_for_size(self, mode_id = None):

        if mode_id is None:
            mode_id = self.current_mode_id

        # Not really handling fps/tint for the OCAM, we just assume an ext trigger
        if mode_id == self.FULL:
            pass
            #self.send_command('set cropping off')
            # CRED2 is especially serial-bitchy after a "set cropping"
            #self.edt_iface._serial_read(timeout=3000)
        else:
            pass

        mode = self.MODES[mode_id]
        self._set_check_cropping(mode.x0, mode.x1, mode.y0, mode.y1)

        EDTCamera.prepare_camera_for_size(self, mode_id=mode_id)


    def prepare_camera_finalize(self, mode_id: int = None):

        if mode_id is None:
            mode_id = self.current_mode_id
        cm = self.MODES[mode_id]

        # Changing the binning trips the external sync (at lest on OCAM ?)
        self.set_synchro(self.synchro)

        # Initialization of the camera: reset the NDR to 1.
        if self.NDR is None:
            self.set_NDR(1)

        if cm.fps is not None:
            self.set_fps(cm.fps)
        if cm.tint is not None:
            self.set_tint(cm.tint)

    def send_command(self, cmd, format=True):
        # Just a little bit of parsing to handle the CRED2 format
        res = EDTCamera.send_command(self, cmd)[:-10]

        while 'cli>' in res:
            # We might have gotten a double answer
            # Seems to happen when requesting pressure (CRED1) and pretty often with CRED2
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

        self.get_NDR()  # Sets 'NDR'
        self.get_tint()  # Sets 'EXPTIME'
        self.get_fps()  # Sets 'FRATE'
        
        self.camera_shm.update_keyword('DETECTOR', 'CRED2')
        self.camera_shm.update_keyword('CROPPED',
                                       self.current_mode_id != 'full')

        # Additional fill-up of the camera state
        self.get_gain()  # Sets 'DETGAIN'

        # Call the stuff that we can't know otherwise
        self.poll_camera_for_keywords()  # Sets 'DET-TMP'

    def poll_camera_for_keywords(self):
        self.get_temperature()

    # ===========================================
    # AD HOC METHODS - TO BE BOUND IN THE SHELL ?
    # ===========================================

    def _get_cropping(self):
        res = self.send_command('cropping raw')
        xx, yy = res[1:]
        x0, x1 = [int(xxx) for xxx in xx.split('-')]
        y0, y1 = [int(yyy) for yyy in yy.split('-')]
        return x0, x1, y0, y1

    def _set_check_cropping(self, x0, x1, y0, y1):
        for _ in range(3):
            gx0, gx1, gy0, gy1 = self._get_cropping()
            if gx0 == x0 and gx1 == x1 and gy0 == y0 and gy1 == y1:
                return x0, x1, y0, y1
            if gx0 != x0 or gx1 != x1:
                self.send_command('set cropping columns %u-%u' % (x0, x1))
                # CRED2s are finnicky with cropping, we'll add a wait
                time.sleep(.2)
            if gy0 != y0 or gy1 != y1:
                self.send_command('set cropping rows %u-%u' % (y0, y1))
                time.sleep(.2)
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

    def set_gain(self, gain: Union[int, str]):
        if type(gain) is int:
            gain = ('low', 'medium', 'high')[gain]
        self.send_command(f'set sensibility {gain}')
        return self.get_gain()

    def get_gain(self):
        res = self.send_command('sensibility raw')
        # res is high, medium or low
        self.camera_shm.update_keyword('DETGAIN', res)
        return res

    def set_NDR(self, NDR: int):
        self.send_command(f'set nbreadworeset {NDR}')
        return self.get_NDR()

    def get_NDR(self):
        self.NDR = int(self.send_command(f'nbreadworeset raw'))
        self.camera_shm.update_keyword('NDR', self.NDR)
        self.camera_shm.update_keyword('DETMODE',
                                       ('Single', 'IMRO')[self.NDR > 1])
        return self.NDR

    def set_fps(self, fps: float):
        self.send_command(f'set fps {fps}')
        return self.get_fps()

    def get_fps(self):
        fps = float(self.send_command('fps raw'))
        self.camera_shm.update_keyword('FRATE', fps)
        return fps

    def max_fps(self):
        return float(self.send_command('maxfps raw'))

    def set_tint(self, tint: float):
        self.send_command(f'set tint {tint}')
        return self.get_tint()

    def get_tint(self):
        tint = float(self.send_command('tint raw'))
        self.camera_shm.update_keyword('EXPTIME', tint)
        return tint

    def max_tint(self):
        return float(self.send_command('maxtint raw'))

    def get_temperature(self):
        temp = float(self.send_command('temp raw')[3])

        self.camera_shm.update_keyword('DET-TMP', temp + 273.15)
        return temp

    def set_temperature_setpoint(self, temp: float):
        self.send_command(f'set temp snake {temp:.1f}')
        return float(self.send_command('temp snake setpoint raw'))

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


class Rajni(CRED2):

    MODES = {}
    MODES.update(CRED2.MODES)
    
    def _fill_keywords(self):
        CRED2._fill_keywords(self)

        # Override detector name
        self.camera_shm.update_keyword('DETECTOR', 'CRED2 - RAJNI')


#class GLINT(CRED2):
'''
    FIXME
    GLINT is not a CRED2 for now, because we decided not to send commands to the camera
    Better, we need to define a passive CRED2, which could send serial commands
    But wouldn't try to alter the camera state
'''
class GLINT(EDTCamera):

    EDTTAKE_UNSIGNED=False

    MODES = {
        # GLINT
        12:
        CameraMode(x0=224,
                   x1=319,
                   y0=80,
                   y1=423,
                   fps=1394.833104000,
                   tint=0.000711851),
    }
    MODES.update(EDTCamera.MODES)

    def __init__(self,
                 name: str,
                 stream_name: str,
                 unit: int = 2,
                 channel: int = 0,
                 mode_id=12,
                 taker_cset_prio=('system', None),
                 dependent_processes=[]):

        basefile = os.environ['HOME'] + '/src/camstack/config/cred2_glint.cfg'

        # Call EDT camera init
        EDTCamera.__init__(self,
                           name,
                           stream_name,
                           mode_id,
                           unit,
                           channel,
                           basefile,
                           taker_cset_prio=taker_cset_prio,
                           dependent_processes=dependent_processes)


    def _fill_keywords(self):
        EDTCamera._fill_keywords(self)

        # Override detector name
        self.camera_shm.update_keyword('DETECTOR', 'CRED2 - GLINT')


class Chuck(CRED2):

    INTERACTIVE_SHELL_METHODS = [] + CRED2.INTERACTIVE_SHELL_METHODS

    MODES = {
        # 224 x 156, centered
        1:
        CameraMode(x0=192,
                   x1=447,
                   y0=178,
                   y1=333,
                   fps=2050.202611000,
                   tint=0.000483913),
        # 128 x 128, centered
        2:
        CameraMode(x0=256,
                   x1=383,
                   y0=192,
                   y1=319,
                   fps=4500.617741000,
                   tint=0.000218568),
        # 64 x 64, centered
        3:
        CameraMode(x0=288,
                   x1=351,
                   y0=224,
                   y1=287,
                   fps=9203.638201000,
                   tint=0.000105249),
        # 192 x 192, centered
        4:
        CameraMode(x0=224,
                   x1=415,
                   y0=160,
                   y1=351,
                   fps=2200.024157000,
                   tint=0.000449819),
        # 96 x 72, centered
        5:
        CameraMode(x0=272,
                   x1=368,
                   y0=220,
                   y1=291,
                   fps=8002.636203000,
                   tint=0.000121555),
    }
    MODES.update(CRED2.MODES)

    # Add modes 6-11 (0-5 offseted 32 pix)
    for i in range(6):
        cm = MODES[i]
        MODES[i + 6] = CameraMode(x0=cm.x0 - 32,
                                  x1=cm.x1 - 32,
                                  y0=cm.y0,
                                  y1=cm.y1,
                                  fps=cm.fps,
                                  tint=cm.tint)

    def _fill_keywords(self):
        CRED2._fill_keywords(self)

        # Override detector name
        self.camera_shm.update_keyword('DETECTOR', 'CRED2 - CHUCK')

# Quick shorthand for testing
if __name__ == "__main__":
    cam = Chuck('chuck', 'ircam0', mode_id=0, unit=0, channel=0)
    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
