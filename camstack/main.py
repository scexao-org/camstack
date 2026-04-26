# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import typing as typ

from argparse import ArgumentParser

# Let's use absolute imports here sor this file can run in python -i <path> mode
from camstack.core import tmux
from camstack.core.utilities import enforce_whichcomp, get_thiscomp
from camstack.main_arch import CameraLauncherSpec

from camstack.deployments import CAMERA_LAUNCH_CONFIG

try:
    import scxconf
except ImportError as exc:
    scxconf = None
    print('Warning: scxconf is not available, SSH remote camera launch is disabled.'
          )

# This is the main data structure for
# which cameras map to which python modules/files
# TODO toml file? in conf/?

from collections import Counter

cc = Counter([c.name for c in CAMERA_LAUNCH_CONFIG])
if any(cc.values()) > 1:
    raise ValueError(
            f'Duplicate keys {[c for c, v in cc.items() if v > 1]} in CONFIG.CAMERA_LAUNCHERS'
    )
CAM_LAUNCHERS: dict[str, CameraLauncherSpec] = {
        c.name.upper(): c
        for c in CAMERA_LAUNCH_CONFIG
}

parser = ArgumentParser(
        prog="camstart",
        description="Spin up or restart a camera session server")
parser.add_argument("camera", choices=CAM_LAUNCHERS.keys(), type=str.upper,
                    help="Name of camera to start")
_group = parser.add_mutually_exclusive_group()
_group.add_argument(
        '-s', '--sshok', action='store_true', help=
        "Allow SSH bouncing to the correct configured computer (requires scxconf and WHICHCOMP)"
)
_group.add_argument('-l', '--local', action='store_true',
                    help="Disallow SSH bouncing, force local computer")

parser.add_argument('-k', '--kill', action='store_true',
                    help="Kill camera server.")


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

    launch_config = CAM_LAUNCHERS[cam_name]
    tmux_name = launch_config.ctrl_tmux_name

    req_machine = launch_config.required_machine
    if (req_machine is None or force_local or
                enforce_whichcomp(req_machine, err=False)):
        # No request OR local machine
        machine_str = f'local [{get_thiscomp()}]'
        tmux_pane = tmux.find_or_create(tmux_name)
    else:
        # Remote
        if (scxconf and permit_ssh_bounce and req_machine is not None):
            tmux_pane = tmux.find_or_create_remote(
                    tmux_name, scxconf.SSH_LOOKUP_FROM_WHICHCOMP[req_machine])
            machine_str = f'remote [{get_thiscomp()}->{req_machine}]'
        else:
            # This always raises.
            tmux_pane, machine_str = None, None
            enforce_whichcomp(req_machine, err=True)

    assert tmux_pane is not None  # typing is happy.
    assert machine_str is not None

    print((f"{'Killing' if args.kill else 'Starting'} {cam_name} "
           f"in tmux session {tmux_name} on {machine_str}"))  #todo

    # Basically this is to ensure bashrc has finished loading in the tmux we just created.
    # Important for environment + bashrc == conda loaded == can change env
    import time
    time.sleep(2.0)

    if args.kill:
        tmux.kill_running_shell_exit(tmux_pane)
        time.sleep(5.0)
        tmux.kill_running(tmux_pane)
        return

    tmux.kill_running(tmux_pane)

    # initiating this camera's main method
    print(f"DEBUG: using {launch_config.conda_env_string} + python -m {launch_config.main}"
          )
    if launch_config.conda_env_string != '':
        tmux.send_keys(tmux_pane, launch_config.conda_env_string)
    tmux.send_keys(tmux_pane, f"python -i -m {launch_config.main}")

    # all done. no cleanup
    print(f"Completed. Inspect {tmux_name} "
          "for further debug information (some cameras take "
          "a little longer to start).")

    if call_from_dunder_main:
        globals().update(locals())


if __name__ == "__main__":
    print('\n------')
    main(call_from_dunder_main=True)
