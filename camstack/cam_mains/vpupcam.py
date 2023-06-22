from camstack.cams.flycapturecam import VampiresPupilFlea

from camstack.core.utilities import shellify_methods
from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_VAMPIRES
from camstack import pyro_keys as pk
from swmain.network.pyroserver_registerable import PyroServer

DEFAULT_SHM_NAME = "vpupcam"

if __name__ == "__main__":
    cam = VampiresPupilFlea("vpup", DEFAULT_SHM_NAME, "CROP_VPUP", 0)
    shellify_methods(cam, globals())
    server = PyroServer(bindTo=(IP_VAMPIRES, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.VPUPCAM, add_oneway_callables=True)
    server.start()
