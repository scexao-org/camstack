import os

from camstack.cams.spinnakercam import USYD_VIS_PG1
from camstack.core.logger import init_camstack_logger

from camstack.scxkw import MAGIC_HW_STR

from argparse import ArgumentParser

parser = ArgumentParser(prog="usydmain",
                        description="Start USYD cameras -- bundled main.")
parser.add_argument("camflag", choices=['VPG1'], type=str.upper,
                    help="Camera: vpg1 VIS-PL PG 1", default='vpg1', nargs='?')

if __name__ == "__main__":
    args = parser.parse_args()
    cam_flag: str = args.camflag

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + f"/logs/camstack-{cam_flag}.log")

    if cam_flag == 'VPG1':
        cam = USYD_VIS_PG1('vispg1', 'vispg1', mode_id='VISPG1',
                           spinnaker_number=17175549, taker_cset_prio=('system',
                                                                       None),
                           dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
