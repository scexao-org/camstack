'''
    Manage the ocam
'''

from .utilities import CameraMode, TmuxMgr, otherstuff


class OCAM2K(EDTcamera):

    MODES = { # For ocam, the CameraMode content is *not* used for the camera setup, only the FG setup
        # Ocam full, unbinned
        1: CameraMode(x0=0, x1=239, y0=0, y1=239, binx=1, biny=1, fgsize=(1056 // 2, 121)),
        # Ocam bin x2
        3: CameraMode(x0=0, x1=119, y0=0, y1=119, binx=2, biny=2, fgsize=(1056 // 2, 62)),
    }

    EDTTAKE_CAST = True

    def __init__(self, name, unit):

        EDTCamera.__init__(self, name, unit, channel=0)

        self.fgtmux = ...  # The edttake tmux session # superclass actually
        self.current_mode = ...

    def set_mode(self, mode_number: int):
        self.stop_fging()
        if mode_number == 1:
            # ocam specific stuff: "binning off"
            pass
        elif mode_number == 3:
            # ocam specific stuff: "binning on"
            pass
        self.start_fging()
