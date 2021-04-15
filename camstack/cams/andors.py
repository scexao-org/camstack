'''
    Andors are pretty dumb cameras in the current regard
    It's really only about managing the initialization file and the acquisition tmux
'''
import os
from camstack.cams.edt_base import EDTCamera
from camstack.core.utilities import CameraMode


class Andor897(EDTCamera):
    MODES = {
        # FULL 512 x 512
        512: CameraMode(x0=0, x1=511, y0=0, y1=511),
    }

    def __init__(self, name: str, stream_name:str,
                 unit: int = 2, channel: int = 0,
                 mode = 512):
        
        basefile = os.environ['HOME'] + '/src/camstack/config/andor_897.cfg'

        # Call EDT camera init
        EDTCamera.__init__(self, name, stream_name,
                           mode, unit, channel, basefile)

class Vampires(Andor897):
    MODES = {
        # 256x256 half frame, centered
        256: CameraMode(x0=128, x1=383, y0=128, y1=383),
        # Etc...
        128: CameraMode(x0=192, x1=319, y0=192, y1=319),
        64: CameraMode(x0=224, x1=287, y0=224, y1=287),
        32: CameraMode(x0=240, x1=271, y0=240, y1=271),
    }
    MODES.update(Andor897.MODES)


class First(Andor897):
    MODES = {
        # 512 x 204
        1 : CameraMode(x0=0, x1=511, y0=0, y1=203), # TODO Get to know the actual y0-y1
    }
    MODES.update(Andor897.MODES)
