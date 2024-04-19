from __future__ import annotations

from .pueo import PueoViewerFrontend, PueoViewerBackend


class IiwiViewerFrontend(PueoViewerFrontend):

    BOTTOM_PX_PAD = 125

    WINDOW_NAME = 'Iiwi PyWFS'

    HELP_MSG: str = """
IIWI Camera Viewer
=======================================
h           : display this help message
x, ESC      : quit viewer

Display controls:
--------------------------------------------------
c         : display cross
k         : display camera SHM keywords
d         : subtract dark frame
CTRL + b  : acquire dark frame (uses pywfs_fcs_pickoff)
r         : subtract reference frame
CTRL + r  : acquire reference frame
l         : cycle scaling (lin, root, log)
m         : cycle colormaps
v         : start/stop averaging frames
SPACE     : freeze frame
z         : zoom on the center of the image
SHIFT + z : unzoom image (cycle backwards)
CTRL + z  : reset zoom and crop
ARROWS    : steer crop
f         : Show flux balance arrows
    """

    CARTOON_FILE = 'iiwi.png'


class IiwiViewerBackend(PueoViewerBackend):
    pass
