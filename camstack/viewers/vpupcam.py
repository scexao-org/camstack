from swmain.network.pyroclient import connect
from camstack.viewers import GenericViewerBackend, GenericViewerFrontend
from camstack.viewers import backend_utils as buts
import pygame.constants as pgmc
from functools import partial


help_msg = """VPUPCAM controls
---------------
h           : display this message
ESC         : quit vpupcam

camera controls:
----------------
q           : increase exposure time
a           : decrease exposure time
CTRL+o      : increase frame rate
CTRL+l      : decrease frame rate

desplay controls:
-----------------
l           : linear/non-linear display
c           : [TODO] estimate pupil position

pupil wheel controls:
---------------------
CTRL+1-- :  change filter wheel slot
        1:  EmptySlot
        2:  7hole
        3:  9hole
        4:  18hole
        5:  18holeNudged
        6:  AnnulusNudged
        7:  Mirror
        8:  OldAnnulus
        9:  LyotStop
        0:  EmptySlot2
        -:  Annulus_Ref
CTRL+ARROW:  Nudge wheel in y (left/right) and y (up/down)
CTRL+SHIFT+LEFT/RIGHT:  Rotate wheel CCW (left; angle increase) or CW (right; angle decrease)
CTRL+S:  Save current position to preset
CTRL+F:  Change preset file
"""

class VAMPIRESPupilCamViewerBackend(GenericViewerBackend):

    # add additional shortcuts
    def __init__(self, name_shm=None):
        if name_shm is None:
            name_shm = "vpupcam"
        self.SHORTCUTS = {
            buts.Shortcut(pgmc.K_LEFT, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_LEFT),
            buts.Shortcut(pgmc.K_RIGHT, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_RIGHT),
            buts.Shortcut(pgmc.K_UP, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_UP),
            buts.Shortcut(pgmc.K_DOWN, pgmc.KMOD_LCTRL): partial(self.nudge_wheel, pgmc.K_DOWN),
            buts.Shortcut(pgmc.K_LEFT, pgmc.KMOD_LCTRL | pgmc.K_LSHIFT): partial(self.rotate_wheel, pgmc.K_LEFT),
            buts.Shortcut(pgmc.K_RIGHT, pgmc.KMOD_LCTRL | pgmc.K_LSHIFT): partial(self.rotate_wheel, pgmc.K_RIGHT)
        }
        self.wheel = connect("VAMPIRES_MASK")
        return super().__init__(name_shm=name_shm)

    def nudge_wheel(self, modifier):
        if modifier & pgmc.K_LEFT:
            substage = "x"
            sign = 1
        elif modifier & pgmc.K_RIGHT:
            substage = "x"
            sign = -1
        elif modifier & pgmc.K_UP:
            substage = "y"
            sign = 1
        elif modifier & pgmc.K_DOWN:
            substage = "y"
            sign = -1
        nudge_value = 0.1
        self.wheel.move_relative(substage, sign * nudge_value)

    def rotate_wheel(self, modifier):
        if modifier & pgmc.K_LEFT:
            sign = 1
        elif modifier & pgmc.K_RIGHT:
            sign = -1
        nudge_value = 0.1
        self.wheel.move_relative("theta", sign * nudge_value)

class VAMPIRESPupilCamViewerFrontend(GenericViewerFrontend):
    pass