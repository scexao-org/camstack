import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import FIRSTOrcam

from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-firstcam.log")

    # mode = OrcaQuest.FIRST
    mode = FIRSTOrcam.FIRSTPL
    # mode = OrcaQuest.FULL

    cam = FIRSTOrcam('orcam', 'orcam', dcam_number=0, mode_id=mode,
                     taker_cset_prio=('user', 42), dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
    '''
    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.FIRST, add_oneway_callables=True)
    server.start()
    '''
