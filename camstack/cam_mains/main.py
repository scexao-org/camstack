# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import typing as typ

from argparse import ArgumentParser

from camstack.core.tmux import (find_or_create, send_keys, kill_running,
                                find_or_create_remote)
from camstack.core.utilities import enforce_whichcomp
import scxconf

# This is the main data structure for
# which cameras map to which python modules/files
CAM_INVOCATION: dict[str | None, tuple[str | None, str | None]] = {
        "ALALA": ("camstack.cam_mains.alala_orcam", 'AORTS'),  # nlcwfs?
        "APD": ("camstack.cams.ao_apd", 'AORTS'),  # nlcwfs?
        "APAPANE": ("camstack.cam_mains.apapane", '5'),
        "FIRST": ("camstack.cam_mains.first_orcam", 'K'),
        "FIRST_PUPIL": ("camstack.cam_mains.first_pupil", 'K'),
        "IIWI": ("camstack.cam_mains.iiwi", 'AORTS'),
        "IIWIA": ("camstack.cam_mains.iiwi -- A", 'AORTS'),
        "IIWIG": ("camstack.cam_mains.iiwi -- G", 'AORTS'),
        "IIWII": ("camstack.cam_mains.iiwi -- I", 'AORTS'),
        "IIWI5": ("camstack.cam_mains.iiwi -- 5", '5'),
        "GLINT": ("camstack.cam_mains.glintcam", '5'),
        "KALAOCAM": ("camstack.cam_mains.kalaocam", None),
        "KIWIKIU": ("camstack.cam_mains.kiwikiu", '5'),
        "PALILA": ("camstack.cam_mains.palila", '5'),
        "PUEO": ("camstack.cam_mains.pueo", '5'),
        "SIMUCAM": ("camstack.cam_mains.simucam", None),
        "VCAM1": ("camstack.cam_mains.vcam -- 1", '5'),
        "VCAM2": ("camstack.cam_mains.vcam -- 2", '5'),
        "VPUPCAM": ("camstack.cam_mains.vpupcam", 'V'),
        "NULL": (None, None),
}

CAM_NAMES = [str(k) for k in CAM_INVOCATION]

parser = ArgumentParser(prog="camstart",
                        description="Spin up or restart a camera tmux daemon")
parser.add_argument("camera", choices=CAM_NAMES, type=str.upper,
                    help="Name of camera to start")
_group = parser.add_mutually_exclusive_group()
_group.add_argument(
        '-s', '--sshok', action='store_true', help=
        "Allow SSH bouncing to the correct configured computer (requires scxconf and WHICHCOMP)"
)
_group.add_argument('-l', '--local', action='store_true',
                    help="Disallow SSH bouncing, force local computer")


def main(
        call_from_dunder_main: bool = False,
        cam_name_arg: typ.Optional[str] = None,
        permit_ssh_bounce: bool = False,  # type: ignore # obscuration under
        force_local: bool = False  # type: ignore # obscuration under
) -> None:

    if cam_name_arg is not None:
        # This is a CLI call
        args = parser.parse_args([cam_name_arg])
    else:
        # This is probs a entrypoint bare main() call
        args = parser.parse_args()
        permit_ssh_bounce: bool = args.sshok  # type: ignore
        force_local: bool = args.local  # type: ignore

    cam_name: str = args.camera

    cam_pyinvocationstring, required_machine = CAM_INVOCATION[cam_name]

    # Default cam name e.g. palila_ctrl
    if cam_name.lower().startswith('iiwi'):
        tmux_name = 'iiwi_ctrl'
    elif cam_name.lower() == 'first':
        tmux_name = 'fircam_ctrl'
    elif cam_name.lower() == 'pueo':
        tmux_name = 'ocam_ctrl'
    else:
        tmux_name = f"{cam_name.lower()}_ctrl"

    print(f"Starting {cam_name} in tmux session {tmux_name}")

    if (required_machine is None or force_local or
                enforce_whichcomp(required_machine, err=False)):
        # No request OR local machine
        tmux = find_or_create(tmux_name)
    else:
        # Remote
        if (permit_ssh_bounce and required_machine is not None):
            tmux = find_or_create_remote(
                    tmux_name,
                    scxconf.SSH_LOOKUP_FROM_WHICHCOMP[required_machine])
        else:
            # This always raises.
            tmux = None
            enforce_whichcomp(required_machine, err=True)

    assert tmux is not None  # typing is happy.
    kill_running(tmux)

    # initiating this camera's main method
    print(f"DEBUG: using {cam_pyinvocationstring}")
    send_keys(tmux, f"python -i -m {cam_pyinvocationstring}")

    # all done. no cleanup
    print(f"Finished initiating camera. Inspect {tmux_name} "
          "for further debug information (some cameras take "
          "a little longer to start).")

    if call_from_dunder_main:
        globals().update(locals())


if __name__ == "__main__":
    print('\n------')
    main(call_from_dunder_main=True)
