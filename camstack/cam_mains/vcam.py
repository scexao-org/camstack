import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import VCAM1, VCAM2
from camstack.core.logger import init_camstack_logger
import logging

# PYROSERVER
from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_SC5
from camstack import pyro_keys as pk
from swmain.network.pyroserver_registerable import PyroServer
from camstack.core.utilities import shellify_methods

from argparser import ArgumentParser

parser = ArgumentParser()
parser.add_argument("cam", type=int, choices=(1, 2))


def launch_vcam1():
    vcam1 = VCAM1(
            "vcam1",
            "vcam1",
            dcam_number=0,
            mode_id=0,
            taker_cset_prio=("v0_asl", 42),
            dependent_processes=[],
    )
    shellify_methods(vcam1, globals())

    return vcam1


def launch_vcam2():
    vcam2 = VCAM2(
            "vcam2",
            "vcam2",
            dcam_number=1,
            mode_id=0,
            taker_cset_prio=("v1_asl", 42),
            dependent_processes=[],
    )
    shellify_methods(vcam2, globals())


def main():
    args = parser.parse_args()
    os.makedirs(os.environ["HOME"] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ["HOME"] +
                         f"/logs/camstack-vcam{args.cam}.log")

    if args.cam == 1:
        cam = launch_vcam1()
    elif args.cam == 2:
        cam = launch_vcam2()
    else:
        message = 'Camera number should be 1 or 2.'
        logging.critical(message)
        raise ValueError(message)

    # start pyro server
    server = PyroServer(bindTo=(IP_SC5, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    key = pk.VCAM1 if args.cam == 1 else pk.VCAM2
    server.add_device(cam, key, add_oneway_callables=True)
    server.start()

    return cam, server


if __name__ == "__main__":
    cam, server = main()
