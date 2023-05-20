import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import MilesOrcam
from camstack.core.logger import init_camstack_logger

# PYROSERVER
from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_ALALA
from camstack import pyro_keys as pk
from swmain.network.pyroserver_registerable import PyroServer
from camstack.core.utilities import shellify_methods

def start_cam():
    # housekeeping
    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-milescam.log")

    # specify cam
    mode = MilesOrcam.FULL
    cam = MilesOrcam(
        'miles',
        'miles',
        dcam_number=1,
        mode_id=mode,
        taker_cset_prio=('user', 42),
        dependent_processes=[]
    )
    # add methods and `cam` to global namespace
    shellify_methods(cam, globals())

    # create pyro server for this camera
    server = PyroServer(
        bindTo=(IP_ALALA, 0),
        nsAddress=(PYRONS3_HOST, PYRONS3_PORT)
    )
    # add camera to pyro server and serve
    server.add_device(cam, pk.MILES_ORCA, add_oneway_callables=True)
    server.start()


if __name__ == "__main__":
    start_cam()