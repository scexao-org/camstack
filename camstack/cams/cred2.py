'''
    Chuck, Rajni, GLINT
'''

from camstack.core.edtcamera import EDTCamera

from camstack.core.utilities import CameraMode

# CameraModes: copy, ...

# Camera: reloadshm, populatekeywords

class CRED2(EDTCamera):

    INTERACTIVE_SHELL_METHODS = [] + EDTCamera.INTERACTIVE_SHELL_METHODS

    MODES = {
        # FULL 640 x 512
        -1: CameraMode(x0=0, x1=639, y0=0, y1=511),
        # 320x256 half frame, centered
        0: CameraMode(x0=160, x1=479, y0=128, y1=383, fps=1500.082358000, tint=0.000663336),
    }

    KEYWORDS = {} # TODO: see about that later.

    def __init__(self, name:str, stream_name: str,
                 mode_id: int = 1, unit: int = 0, channel: int = 0):
        
        # Allocate and start right in the appropriate binning mode
        basefile = '/home/scexao/src/camstack/config/cred2_14bit.cfg'


class Rajni(CRED2):

    INTERACTIVE_SHELL_METHODS = [] + CRED2.INTERACTIVE_SHELL_METHODS

    MODES = {}
    MODES.update(CRED2.MODES)

    KEYWORDS = {} # TODO: see about that later.


    def __init__(self, name:str, stream_name: str,
                 mode: int, unit: int = 0, channel: int = 0):
        CRED2.__init__(self, name, str_name, mode, unit, channel)

class GLINT(CRED2):
    MODES = {
        # GLINT
        12: CameraMode(x0=224, x1=319, y0=80, y1=423, fps=1394.833104000, tint=0.000711851),
    }
    MODES.update(CRED2.MODES)
class Chuck(CRED2):
    MODES = {
        # 224 x 156, centered
        1: CameraMode(x0=192, x1=415, y0=160, y1=347, fps=2050.202611000, tint=0.000483913),
        # 128 x 128, centered
        2: CameraMode(x0=256, x1=383, y0=192, y1=319, fps=4500.617741000, tint=0.000218568),
        # 64 x 64, centered
        3: CameraMode(x0=288, x1=351, y0=224, y1=287, fps=9203.638201000, tint=0.000105249),
        # 192 x 192, centered
        4: CameraMode(x0=224, x1=415, y0=160, y1=351, fps=2200.024157000, tint=0.000449819),
        # 96 x 72, centered
        5: CameraMode(x0=256, x1=351, y0=220, y1=291, fps=8002.636203000, tint=0.000121555),
    }
    MODES.update(CRED2.MODES)

    # Add modes 6-11 (0-5 offseted 32 pix)
    for i in range(6):
        cm = MODES[i]
        MODES[i+6] = CameraMode(x0=cm.x0-32, x1=cm.x1-32, y0=cm.y0, y1=cm.y1, fps=cm.fps, tint=cm.tint)


# Quick shorthand for testing
if __name__ == "__main__":
    ocam = Rajni('rajni', 'rajnicam', unit=1, channel=0, binning=True)
    from camstack.core.utilities import shellify_methods
    shellify_methods(ocam, globals())