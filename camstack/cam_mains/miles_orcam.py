import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import AlalaOrcam
from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-milescam.log")

    #mode = AlalaOrcam.FULL
    mode = AlalaOrcam.DICHROIC

    cam = AlalaOrcam('miles', 'miles', dcam_number=1, mode_id=mode,
                     taker_cset_prio=('user', 42), dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())



    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_ALALA
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_ALALA, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.MILES_ORCA, add_oneway_callables=True)
    server.start()