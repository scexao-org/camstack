'''
    Apapane
'''
from typing import Union, Optional as Op, Tuple, TYPE_CHECKING, List
if TYPE_CHECKING:
    from camstack.core.utilities import DependentProcess

import os
import time
import logging as logg

from camstack.cams.edtcam import EDTCamera

from camstack.core.utilities import CameraMode, ModeIDType, CsetPrioType

from scxkw.config import MAGIC_BOOL_STR


class ROMODES:
    single = 'globalresetsingle'
    cds = 'globalresetcds'
    bursts = 'globalresetbursts'


class CRED1(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [
        'set_synchro', 'set_readout_mode',
        'get_readout_mode', 'set_gain', 'get_gain',
        'set_NDR', 'get_NDR', 'set_fps',
        'get_fps', 'set_tint', 'get_tint',
        'get_temperature', 'FULL'] + \
        EDTCamera.INTERACTIVE_SHELL_METHODS

    FULL = 'full'
    # yapf: disable
    MODES = {
            # FULL 320 x 256
            FULL: CameraMode(x0=0, x1=319, y0=0, y1=255, fps=3460.),
            0: CameraMode(x0=0, x1=319, y0=0, y1=255, fps=3460.),
            # 64x64 centered
            1: CameraMode(x0=128, x1=191, y0=96, y1=159, fps=40647.),  # 40647. Limiting for now
            # 128x128 centered
            2: CameraMode(x0=96, x1=223, y0=64, y1=191, fps=14331.),
            # 160x160 16px offside
            3: CameraMode(x0=64, x1=223, y0=48, y1=207, fps=9805.),
            # 192x192 centered
            4: CameraMode(x0=64, x1=255, y0=32, y1=223, fps=7115.),
            # 224x224 16px offside
            5: CameraMode(x0=32, x1=255, y0=16, y1=239, fps=5390.),
            # 256x256 centered
            6: CameraMode(x0=32, x1=287, y0=0, y1=255, fps=4225.),
            # 160x80
            7: CameraMode(x0=64, x1=223, y0=88, y1=167, fps=18460.),
            # 192x80
            8: CameraMode(x0=64, x1=255, y0=88, y1=167, fps=16020.),
    }
    # yapf: enable

    KEYWORDS = {
            'DET-PRES': (0.0, 'Detector pressure (mbar)', '%20.8f', 'PRESR'),
    }
    KEYWORDS.update(EDTCamera.KEYWORDS)

    EDTTAKE_UNSIGNED = True
    EDTTAKE_EMBEDMICROSECOND = True

    def __init__(self, name: str, stream_name: str,
                 mode_id: ModeIDType = 'full', unit: int = 1, channel: int = 0,
                 taker_cset_prio: CsetPrioType = ('system', None),
                 dependent_processes: List[DependentProcess] = []) -> None:

        # Allocate and start right in the appropriate binning mode
        self.synchro: bool = False
        basefile = os.environ['HOME'] + '/src/camstack/config/cred1_16bit.cfg'
        self.NDR: Op[int] = None  # Grabbed in prepare_camera_finalize

        # Call EDT camera init
        # This should pre-kill dependent sessions
        # But we should be able to "prepare" the camera before actually starting
        EDTCamera.__init__(self, name, stream_name, mode_id, unit, channel,
                           basefile, taker_cset_prio=taker_cset_prio,
                           dependent_processes=dependent_processes)

        # ======
        # AD HOC
        # ======

        # Issue a few standards for CRED1
        self.send_command('set led off')
        self.send_command('set events off')

        self.send_command('set rawimages on')
        self.send_command('set imagetags on')

        self.set_gain(self.get_maxpossiblegain())

    # =====================
    # AD HOC PREPARE CAMERA
    # =====================

    def prepare_camera_for_size(self, mode_id: Op[ModeIDType] = None) -> None:
        # Note: when called the first time, this immediately follows
        # self.init_framegrab_backend()
        # So, the serial port is live, but we haven't tried to talk yet.
        # Great time to check camera status!

        self.process_camera_status(self.get_camera_status())

        logg.debug('prepare_camera_for_size @ CRED1')

        if mode_id is None:
            mode_id = self.current_mode_id

        # Not really handling fps/tint for the OCAM, we just assume an ext trigger
        if mode_id == 'full':  #TODO
            self.send_command('set cropping off')
        else:
            self.send_command('set cropping on')

        mode = self.MODES[mode_id]
        self._set_check_cropping(mode.x0, mode.x1, mode.y0, mode.y1)

        EDTCamera.prepare_camera_for_size(self, mode_id=mode_id)

    def prepare_camera_finalize(self, mode_id: Op[ModeIDType] = None) -> None:
        logg.debug('prepare_camera_finalize @ CRED1')

        if mode_id is None:
            mode_id = self.current_mode_id
        cm = self.MODES[mode_id]

        # Changing the binning trips the external sync (at lest on OCAM ?)
        self.set_synchro(self.synchro)

        # Initialization of the camera: reset the NDR to globalresetcds, NDR2.
        if self.NDR is None:
            self.set_readout_mode(ROMODES.cds)
            self.set_NDR(2)

        if cm.fps is not None:
            self.set_fps(cm.fps)
        if cm.tint is not None:
            self.set_tint(cm.tint)

    def send_command(self, cmd: str) -> str:
        # Just a little bit of parsing to handle the CRED1 format
        # FLI has *decided* to end all their answers with a return prompt "\r\nfli-cli>"
        logg.debug(f'CRED1 send_command: "{cmd}"')
        res = EDTCamera.send_command(self, cmd)[:-10]

        if 'cli>' in res:
            # We might have gotten a double answer
            # Seems to happen when requesting pressure
            cut = res.index('>')
            res = res[cut + 1:]

        return res

    def _fill_keywords(self) -> None:
        # Do a little more filling than the subclass after changing a mode
        # And call the thread-polling function
        #TODO: thread temp polling

        EDTCamera._fill_keywords(self)

        self._set_formatted_keyword('DETECTOR', 'CRED1')
        self._set_formatted_keyword('CROPPED',
                                    self.current_mode_id != self.FULL)
        self.get_NDR()  # Sets 'NDR'
        self.get_tint()  # Sets 'EXPTIME'
        self.get_fps()  # Sets 'FRATE'

        # Additional fill-up of the camera state
        self.get_gain()  # Sets 'DETGAIN'
        self.get_readout_mode()  # Set DET-SMPL

        # Call the stuff that we can't know otherwise
        self.poll_camera_for_keywords()  # Sets 'DET-TMP'

    def poll_camera_for_keywords(self, shm_write: bool = True) -> None:

        self.get_temperature(shm_write=shm_write)  # Sets DET-TMP
        time.sleep(.1)
        self.get_cryo_pressure(shm_write=shm_write)  # Sets DET-PRES
        time.sleep(.1)
        water_temp = self.get_water_temperature()
        if water_temp > 40.0:
            self._emergency_abort()

    # ===========================================
    # AD HOC METHODS - TO BE BOUND IN THE SHELL ?
    # ===========================================

    def _get_cropping(self) -> Tuple[int, int, int, int]:
        # We mimicked the definition of the cropmodes from the CRED2
        # BUT the CRED1 is 1-base indexed.... remove 1
        logg.debug('_get_cropping @ CRED1')
        _, xx, yy = self.send_command('cropping raw').split(
                ':')  # return is "(on|off):x0-x1:y0-y1"
        x0, x1 = [(int(xxx) - 1) for xxx in xx.split('-')]
        x0 = 32 * x0
        x1 = 32 * x1 + 31  # column blocks of 32
        y0, y1 = [int(yyy) - 1 for yyy in yy.split('-')]
        return x0, x1, y0, y1

    def _set_check_cropping(self, x0: int, x1: int, y0: int,
                            y1: int) -> Tuple[int, int, int, int]:
        for _ in range(3):
            logg.debug('_set_check_cropping attempt @ CRED1')
            gx0, gx1, gy0, gy1 = self._get_cropping()
            if gx0 == x0 and gx1 == x1 and gy0 == y0 and gy1 == y1:
                return x0, x1, y0, y1
            if gx0 != x0 or gx1 != x1:
                # BUT the CRED1 is 1-base indexed.... add 1
                self.send_command('set cropping columns %u-%u' %
                                  (x0 // 32 + 1, x1 // 32 + 1))
                # CRED2s are finnicky with cropping, we'll add a wait
                time.sleep(.5)
            if gy0 != y0 or gy1 != y1:
                # BUT the CRED1 is 1-base indexed.... add 1
                self.send_command('set cropping rows %u-%u' % (y0 + 1, y1 + 1))
                time.sleep(.5)

        msg = f'Cannot set desired crop {x0}-{x1} {y0}-{y1} after 3 tries'
        logg.error(msg)
        raise AssertionError(msg)

    def _emergency_abort(self) -> None:
        # Doing this automatically avoids falling in safe mode
        # and needing a power cycle.
        logg.critical('Stopping cooling because water is too hot!')
        # Self.shutdown is a trap, no return expected ever.
        self.send_command("set cooling off")

    def set_synchro(self, synchro: bool) -> bool:
        val = ('off', 'on')[synchro]
        _ = self.send_command(f'set extsynchro {val}')
        res = self.send_command('extsynchro raw')
        self.synchro = {'off': False, 'on': True}[res]
        self._set_formatted_keyword('EXTTRIG', self.synchro)

        logg.info(f'set_synchro: {self.synchro}')
        return self.synchro

    def get_camera_status(self) -> str:
        res = self.send_command('status raw')
        logg.info(f'get_camera_status: {res}')
        if res == '':
            # Second chance:
            res = self.send_command('status raw')
            logg.info(f'get_camera_status: {res}')

        return res

    def process_camera_status(self, status: str) -> None:

        class InitializationError(Exception):
            pass

        if status == 'operational':
            return

        if status == 'standby':
            logg.error(
                    "Camera is in standby mode! Need to disable by serial command 'set standby off'."
            )
            raise InitializationError(
                    'Disable stanby mode manually and restart.')

        if status in ['prevsafe', 'poorvacuum']:
            logg.error(f"Camera status {status}")
            self.send_command("continue")
            time.sleep(1.0)
            # Now expecting 'ready'
            status = self.get_camera_status()

        if status == 'ready':
            logg.error(
                    f"Camera status is 'ready' (OK but warm). Temp = {self.get_temperature(shm_write=False):.1f}"
            )
            self.send_command("set cooling on")
            # Now expecting 'isbeingcooled'
            status = self.get_camera_status()

        if status == 'isbeingcooled':
            # Start a temperature capture loop.
            logg.warning(
                    'Starting temperature watch loop... Ctrl + C to interrupt and abort.'
            )
            try:
                while status == 'isbeingcooled':
                    # self.poll... will ask for water temperature AND trigger and emergency shutdown if needed.
                    self.poll_camera_for_keywords(shm_write=False)
                    status = self.get_camera_status()
                    print(f'status = {status} - Cryo temp = {self.get_temperature(shm_write=False):.1f} - Water temp = {self.get_water_temperature():.1f}'
                          )

                logg.warning(f'Camera now cold - status: {status}.')

            except KeyboardInterrupt:
                logg.error(
                        'Abort during cooling wait. Camera is still cooling tho!'
                )
                self.release()

                raise InitializationError('CRED1 not cold yet.')

        if status != 'operational':
            logg.critical(f'Camera status {status} - fatal.')
            raise InitializationError('Take actions by hand and restart.')

    def set_readout_mode(self, mode: str) -> str:
        self.send_command(f'set mode {mode}')
        return self.get_readout_mode()

    def get_readout_mode(self) -> str:
        res = self.send_command('mode raw')
        res = res[:6] + res[
                11:]  # Removing "reset" after "global", otherwise too long for shm keywords
        self._set_formatted_keyword('DET-SMPL', res)
        logg.info(f'get_readout_mode: {res}')
        return res

    def set_gain(self, gain: int) -> int:
        self.send_command(f'set gain {gain}')
        return self.get_gain()

    def get_gain(self) -> int:
        res = int(self.send_command('gain raw'))
        self._set_formatted_keyword('DETGAIN', res)
        logg.info(f'get_gain: {res}')
        return res

    def get_maxpossiblegain(self) -> int:
        return int(self.send_command('maxpossiblegain raw'))

    def set_NDR(self, NDR: int) -> int:
        if NDR < 1 or not type(NDR) is int:
            raise AssertionError(f'Illegal NDR value: {NDR}')

        gain_now = self.get_gain(
        )  # Setting detmode seems to reset the EM gain to 1.

        # Attempt: stabilize by re-setting always readout mode and maxfps
        clippedNDR = min(3, NDR)
        currentNDR = min(3, self.get_NDR())
        readout_modes = {1: ROMODES.single, 2: ROMODES.cds, 3: ROMODES.bursts}

        readout_mode = readout_modes[clippedNDR]
        curr_readout_mode = readout_modes[currentNDR]

        # DO NOT set the mode, this reverts setting the NDR... or does it ? Getting the mode seems to unlock the weird behavior.
        self.send_command(f'set nbreadworeset {NDR}')

        if readout_mode != curr_readout_mode:
            # These two lines to help iron out firmware glitches at mode/ndr changes
            self.get_readout_mode()
            self.get_NDR()

            time.sleep(1.)
            self._kill_taker_no_dependents()
            self._start_taker_no_dependents(reuse_shm=True)

        time.sleep(1.)
        self.set_readout_mode(readout_mode)

        self.set_fps(
                self.current_mode.fps
        )  # Systematically - because AUTO rescaling of fps occurs when changing NDR...

        self.set_gain(gain_now)

        return self.get_NDR()

    def get_NDR(self) -> int:
        self.NDR = int(self.send_command('nbreadworeset raw'))
        self._set_formatted_keyword('DET-NSMP', self.NDR)
        self._set_formatted_keyword('DET-SMPL',
                                    ('globalsingle', 'globalcds')[self.NDR > 1])
        logg.info(f'get_NDR: {self.NDR}')
        return self.NDR

    def set_fps(self, fps: float) -> float:
        self.send_command(f'set fps {fps}')
        return self.get_fps()

    def get_fps(self) -> float:
        fps = float(self.send_command('fps raw'))
        self._set_formatted_keyword('FRATE', fps)
        self._set_formatted_keyword('EXPTIME', 1. / fps)
        logg.info(f'get_fps: {fps}')
        return fps

    def max_fps(self) -> float:
        return float(self.send_command('maxfps raw'))

    def set_tint(self, tint: float) -> float:
        # CRED1 has no tint management
        return 1. / self.set_fps(1 / tint)

    def get_tint(self) -> float:
        # CRED1 has no tint management
        return 1. / self.get_fps()

    def get_cryo_pressure(self, shm_write: bool = True) -> float:
        pres = float(self.send_command('pressure raw'))
        if shm_write:
            self._set_formatted_keyword('DET-PRES', pres)
        logg.info(f'get_cryo_pressure: {pres}')
        return pres

    def get_temperature(self, shm_write: bool = True) -> float:
        # We're gonna need this method even when the SHM has not been initialized yet.
        temp = float(self.send_command('temp cryostat diode raw'))
        if shm_write:
            self._set_formatted_keyword('DET-TMP', temp)
        logg.info(f'get_temperature: {temp}')
        return temp

    def get_water_temperature(self) -> float:
        temp = float(self.send_command('temp water raw'))
        logg.info(f'get_water_temperature: {temp}')
        if temp > 30.0:
            logg.warn(f'get_water_temperature: {temp}')
        if temp > 40.0:
            logg.critical(f'get_water_temperature: {temp}')

        return temp

    def _shutdown(self, force: bool = False) -> None:
        if not force:
            input(f'Detector temperature {self.get_temperature()} K; proceed anyway ? Ctrl+C aborts.'
                  )
        else:
            print(f'Force shutdown... temp {self.get_temperature()} K')

        res = self.send_command('shutdown')
        if 'OK' in res:
            while True:
                time.sleep(5)
                logg.warning(
                        'Camera shutdown was acknowledged.\n'
                        'Processes on this end were killed.\n'
                        'You should quit this shell.\n'
                        'You\'ll need to power cycle the CRED1 to reboot it.')


class Apapane(CRED1):

    INTERACTIVE_SHELL_METHODS = [] + CRED1.INTERACTIVE_SHELL_METHODS

    MODES = {}
    MODES.update(CRED1.MODES)

    # yapf: disable
    KEYWORDS = {
        # Warning: this means that the two following keywords
        # CANNOT be set anymore by gen2/auxfitsheader
        # Because the stream keywords WILL supersede.

        'FILTER01': ('UNKNOWN', 'IRCAMs filter state', '%-16s', 'FILTR'),
        'RET-ANG1': (0.0, 'Position angle of first retarder plate (deg)', '%20.2f', 'HWPAG'),

        'CDELT1': (4.5e-6, 'X Scale projected on detector (#/pix)', '%20.8f', 'CDEL1'),
        'CDELT2': (4.5e-6, 'Y Scale projected on detector (#/pix)', '%20.8f', 'CDEL2'),
        'C2ELT1': (4.5e-6, 'X Scale projected on detector (#/pix)', '%20.8f', 'C2EL1'),
        'C2ELT2': (4.5e-6, 'Y Scale projected on detector (#/pix)', '%20.8f', 'C2EL2'),
        'CTYPE1': ('RA--TAN   ', 'Pixel coordinate system', '%-10s', 'CTYP1'),
        'CTYPE2': ('DEC--TAN  ', 'Pixel coordinate system', '%-10s', 'CTYP2'),
        'C2YPE1': ('RA--TAN   ', 'Pixel coordinate system', '%-10s', 'C2YP1'),
        'C2YPE2': ('DEC--TAN  ', 'Pixel coordinate system', '%-10s', 'C2YP2'),
        'CUNIT1': ('DEGREE    ', 'Units used in both CRVAL1 and CDELT1', '%-10s', 'CUNI1'),
        'CUNIT2': ('DEGREE    ', 'Units used in both CRVAL2 and CDELT2', '%-10s', 'CUNI2'),
        'C2NIT1': ('DEGREE    ', 'Units used in both C2VAL1 and C2ELT1', '%-10s', 'C2NI1'),
        'C2NIT2': ('DEGREE    ', 'Units used in both C2VAL2 and C2ELT2', '%-10s', 'C2NI2'),

        # Those will change with cropmode
        'CRPIX1': ( 40., 'Reference pixel in X (pixel)', '%20.1f', 'CRPX1'),
        'CRPIX2': ( 80., 'Reference pixel in Y (pixel)', '%20.1f', 'CRPX2'),
        'C2PIX1': (120., 'Reference pixel in X (pixel)', '%20.1f', 'C2PX1'),
        'C2PIX2': ( 80., 'Reference pixel in Y (pixel)', '%20.1f', 'C2PX2'),

        'CD1_1': (4.5e-6, 'Pixel coordinate translation matrix', '%20.8f', 'CD1_1'),
        'CD1_2': (    0., 'Pixel coordinate translation matrix', '%20.8f', 'CD1_2'),
        'CD2_1': (    0., 'Pixel coordinate translation matrix', '%20.8f', 'CD2_1'),
        'CD2_2': (4.5e-6, 'Pixel coordinate translation matrix', '%20.8f', 'CD2_2'),
    }
    # yapf: enable
    KEYWORDS.update(CRED1.KEYWORDS)

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = 'x_B'  # LOWERCASE x to not get mixed with the SCExAO keys

    def _fill_keywords(self) -> None:
        CRED1._fill_keywords(self)

        doing_pdi = True

        if self.HAS_REDIS:
            try:
                self._set_formatted_keyword('FILTER01',
                                            self.RDB.hget('X_IRCFLT', 'value'))
                doing_pdi = self.RDB.hget('OBS-MOD', 'value') == 'IMAG-PDI'
            except:
                logg.warning(
                        'REDIS unavailable @ poll_camera_for_keywords @ CRED1')
                pass

        # Hotspot of physical detector in the current crop coordinates.
        # Could be beyond the sensor if the crop does not include the detector center.
        # Warning: in CRED1, hotspot is 16 pixel off-center along the rows!
        xfull2 = (self.MODES[self.FULL].x1 - self.MODES[self.FULL].x0 +
                  1) / 2. - 16.
        yfull2 = (self.MODES[self.FULL].y1 - self.MODES[self.FULL].y0 + 1) / 2.

        self._set_formatted_keyword('CRPIX2', yfull2 - self.current_mode.y0)
        self._set_formatted_keyword('C2PIX2', yfull2 - self.current_mode.y0)
        if doing_pdi:
            # +/- 40 off of the central column
            self._set_formatted_keyword('CRPIX1',
                                        xfull2 - 40. - self.current_mode.x0)
            self._set_formatted_keyword('C2PIX1',
                                        xfull2 + 40. - self.current_mode.x0)
        else:
            # Central column
            self._set_formatted_keyword('CRPIX2', xfull2 - self.current_mode.x0)
            self._set_formatted_keyword('C2PIX2', xfull2 - self.current_mode.x0)

        # Override detector name
        self._set_formatted_keyword('DETECTOR', 'CRED1 - APAPANE')
        self._set_formatted_keyword('GAIN', 0.45)

        # Note: RET-ANG1 is set externally by a call to "updatekw apapane RET-ANG1" from HWP scripts.
        # This avoids latency in reporty HWP states.


class Iiwi(CRED1):

    INTERACTIVE_SHELL_METHODS = [] + CRED1.INTERACTIVE_SHELL_METHODS

    MODES = {}
    MODES.update(CRED1.MODES)

    KEYWORDS = {}
    KEYWORDS.update(CRED1.KEYWORDS)

    REDIS_PUSH_ENABLED = True
    REDIS_PREFIX = 'x_I'  # LOWERCASE x to not get mixed with the SCExAO keys

    def _fill_keywords(self) -> None:
        CRED1._fill_keywords(self)

        # Override detector name
        self._set_formatted_keyword('DETECTOR', 'CRED1 - IIWI')
        self._set_formatted_keyword('GAIN', 1.98)


# Quick shorthand for testing
if __name__ == "__main__":
    cam = Apapane('apapane', 'apapane', mode_id='full', unit=1, channel=0)
    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
