'''
    Andors are pretty dumb cameras in the current regard
    It's really only about managing the initialization file and the acquisition tmux
'''
import os
import logging as logg

from camstack.cams.autodumbedt import AutoDumbEDTCamera
from camstack.core.utilities import CameraMode


class AutoAndor897(AutoDumbEDTCamera):
    MODES = {
            # FULL 512 x 512
            512: CameraMode(x0=0, x1=511, y0=0, y1=511),
    }

    EDTTAKE_EMBEDMICROSECOND = False

    def __init__(self, name: str, stream_name: str, unit: int = 2,
                 channel: int = 0, mode_id=512,
                 taker_cset_prio=('system', None), dependent_processes=[]):

        # Since this is a no-control, auto-detect camera, this is really only useful for the number of taps.
        basefile = os.environ['HOME'] + '/src/camstack/config/andor_897.cfg'

        # Call EDT camera init
        AutoDumbEDTCamera.__init__(self, name, stream_name, mode_id, unit,
                                   channel, basefile,
                                   taker_cset_prio=taker_cset_prio,
                                   dependent_processes=dependent_processes)


class Vampires(AutoAndor897):
    MODES = {
            # 256x256 half frame, centered
            256: CameraMode(x0=128, x1=383, y0=128, y1=383),
            # Etc...
            128: CameraMode(x0=192, x1=319, y0=192, y1=319),
            64: CameraMode(x0=224, x1=287, y0=224, y1=287),
            32: CameraMode(x0=240, x1=271, y0=240, y1=271),
    }
    MODES.update(AutoAndor897.MODES)

    EDTTAKE_EMBEDMICROSECOND = False

    def __init__(self, name: str, stream_name: str, unit: int = 2,
                 channel: int = 0, mode_id=512,
                 taker_cset_prio=('system', None), dependent_processes=[]):
        # Just register the vampires camera number... which is the camlink channel.
        self.vcam_num = channel

        AutoAndor897.__init__(self, name, stream_name, unit, channel, mode_id,
                              taker_cset_prio, dependent_processes)

    def _fill_keywords(self):
        AutoAndor897._fill_keywords(self)

        # Override detector name
        self._set_formatted_keyword('DETECTOR',
                                    f'Andor - VCAM{self.vcam_num:1d}')
        # We can guess the cropping
        self._set_formatted_keyword('CROPPED', (self.height < 512) or
                                    ((self.width < 512)))


class First(AutoAndor897):
    MODES = {
            # 512 x 204
            1: CameraMode(x0=0, x1=511, y0=0, y1=203),
    }
    MODES.update(AutoAndor897.MODES)

    EDTTAKE_EMBEDMICROSECOND = False


# Basic testing:

if __name__ == "__main__":

    from camstack.core.logger import init_camstack_logger

    init_camstack_logger('/tmp/andors.py.log')
    logger = logg.getLogger()
    stdouthandler = logger.handlers[0]
    stdouthandler.setLevel(logg.DEBUG)
    cam = Vampires(name='vcam0', stream_name='vcamim0', unit=2, channel=0,
                   mode_id=512)
