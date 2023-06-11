import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import VCAM1, VCAM2, BaseVCAM
from camstack.core.logger import init_camstack_logger
import logging

# PYROSERVER
from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_SC5
from camstack import pyro_keys as pk
from swmain.network.pyroserver_registerable import PyroServer
from camstack.core.utilities import shellify_methods
from argparse import ArgumentParser


def launch_vcam1(mode):
    vcam1 = VCAM1(
            "vcam1",
            "vcam1",
            dcam_number=0,
            mode_id=mode,
            taker_cset_prio=("v1_asl", 42),
            dependent_processes=[],
    )
    shellify_methods(vcam1, globals())

    return vcam1


def launch_vcam2(mode):
    vcam2 = VCAM2(
            "vcam2",
            "vcam2",
            dcam_number=1,
            mode_id=mode,
            taker_cset_prio=("v2_asl", 42),
            dependent_processes=[],
    )
    shellify_methods(vcam2, globals())

    return vcam2


parser = ArgumentParser()
parser.add_argument("cam", type=int, choices=(1, 2))
parser.add_argument(
        "-m", "--mode", choices=[
                BaseVCAM.FULL, BaseVCAM.STANDARD, BaseVCAM.MBI,
                BaseVCAM.MBI_REDUCED
        ], default=BaseVCAM.STANDARD,
        help="Camera mode (default is %(default)s)")


def main():
    args = parser.parse_args()
    cam = args.cam
    mode = args.mode.upper()
    os.makedirs(os.environ["HOME"] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ["HOME"] + f"/logs/camstack-vcam{cam}.log")

    if cam == 1:
        vcam = launch_vcam1(mode=mode)
        key = pk.VCAM1
    elif cam == 2:
        vcam = launch_vcam2(mode=mode)
        key = pk.VCAM2

    # start pyro server
    # neep separate port for each camera!
    pyro_port = 8748 + cam
    server = PyroServer(bindTo=(IP_SC5, pyro_port),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(vcam, key, add_oneway_callables=True)
    server.start()


if __name__ == "__main__":
    main()
