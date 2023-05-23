import os

from camstack.core.utilities import DependentProcess
from camstack.cams.cred1 import Iiwi

from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-iiwi.log")

    mode = 9

    dependent_processes = []

    cam = Iiwi('iiwi', 'iiwi_raw', unit=0, channel=0, mode_id=mode,
               taker_cset_prio=('irwfs_edt',
                                49), dependent_processes=dependent_processes)

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_AORTS_SUMMIT
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_AORTS_SUMMIT, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.APAPANE, add_oneway_callables=True)
    server.start()
