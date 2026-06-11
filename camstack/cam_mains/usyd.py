import os

from camstack.core.logger import init_camstack_logger

from camstack.scxkw import MAGIC_HW_STR

from argparse import ArgumentParser

parser = ArgumentParser(prog="usydmain",
                        description="Start USYD cameras -- bundled main.")
parser.add_argument(
        "camflag", choices=['VPG1', 'VPG2', 'VPG3',
                            'CB2'], type=str.upper, help=
        "Camera: vpg1 VIS-PL PG 1 (USB) | vpg2 VIS-PL PG 2 (GigE)  | vpg2 VIS-PL PG 3 (GigE) | CB2 Andor CB2",
        default='vpg1', nargs='?')

if __name__ == "__main__":
    args = parser.parse_args()
    cam_flag: str = args.camflag

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + f"/logs/camstack-{cam_flag}.log")

    if cam_flag == 'VPG1':
        from camstack.cams.spinnakercam import USYD_VIS_PG1
        cam = USYD_VIS_PG1('vispg1', 'vispg1', mode_id='VISPG1',
                           spinnaker_number=17175549)
        pyro_key = 'VPG1'
    elif cam_flag == 'CB2':
        from camstack.cams.flisdkgenicam import AndorCB2_7_1
        cam = AndorCB2_7_1('cb2', 'cb2', mode_id='FULL', flisdk_index=0)
        pyro_key = 'CB2'
    elif cam_flag == 'VPG2':
        from camstack.cams.spinnaker_over_transport import USYD_VIS_PG2
        cam = USYD_VIS_PG2('vispg2', 'vispg2', mode_id=2,
                           spinnaker_number=16048585)
        pyro_key = 'VPG2'
    elif cam_flag == 'VPG3':
        from camstack.cams.spinnaker_over_transport import USYD_VIS_PG3
        cam = USYD_VIS_PG3('vispg3', 'vispg3', mode_id=1,
                           spinnaker_number=24284634)
        pyro_key = 'VPG3'

    else:
        raise NotImplementedError('Cannot be here.')

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=('localhost', 0), nsAddress=('localhost', 51000))
    server.add_device(cam, pyro_key, add_oneway_callables=True)
    server.start()
