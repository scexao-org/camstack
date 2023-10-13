from argparse import ArgumentParser

from camstack.core.tmux import find_or_create, send_keys, kill_running

# This is the main data structure for
# which cameras map to which python modules/files
CAM_METHODS = {
        "ALALA": "camstack.cam_mains.alala_orcam",
        "APAPANE": "camstack.cam_mains.apapane",
        "FIRST": "camstack.cam_mains.first_orcam",
        "FIRST_PUPIL": "camstack.cam_mains.first_pupil",
        "GLINTCAM": "camstack.cam_mains.glintcam",
        "KALAOCAM": "camstack.cam_mains.kalaocam",
        "KIWIKIU": "camstack.cam_mains.kiwikiu",
        "MILES": "camstack.cam_mains.miles_orcam",
        "PALILA": "camstack.cam_mains.palila",
        "PUEO": "camstack.cam_mains.pueo",
        "SIMUCAM": "camstack.cam_mains.simucam",
        "VAMPIRES": "camstack.cam_mains.vampires",
        "VPUPCAM": "camstack.cam_mains.vpupcam",
        "NULL": "null",
}

CAM_NAMES = [str(k) for k in CAM_METHODS]

parser = ArgumentParser(prog="camstart",
                        description="Spin up or restart a camera tmux daemon")
parser.add_argument("camera", choices=CAM_NAMES, type=str.upper,
                    help="Name of camera to start")
"""
tnew="tmux new-session -d -s"
tsend="tmux send-keys -t"

tname="orcam_ctrl"

# Create tmuxes and issue kills
$tnew $tname
sleep 3.0 # MUST NOT SEND the C-c to interrupt the bashrc !
$tsend $tname C-c
sleep 0.1
$tsend $tname "close()" Enter
sleep 3
$tsend $tname C-c
sleep 0.3
$tsend $tname C-z
sleep 0.3
$tsend $tname "kill %" Enter

echo ""
echo "Remember check if 'cset set' is enabled"
echo "If not sets, run:"
echo "    sudo cset shield -c 12-15,28-31"


$tsend $tname "python -im camstack.cam_mains.alala_orcam" Enter

echo "alalacamstart completed (but actually not yet, just wait a bit)."
"""


def main(call_from_dunder_main: bool = False):
    # print(f'call_from_dunder_main: {call_from_dunder_main}')

    args = parser.parse_args()
    ## Step 1. Create tmux and issue kills
    cam_name = args.camera
    if cam_name not in CAM_NAMES:
        # Can't happen since args will throw an ArgumentError and exit
        raise ValueError(f"{cam_name} not recognized.")
    cam_method = CAM_METHODS[cam_name]

    # default came name e.g. palila_ctrl
    tmux_name = f"{cam_name.lower()}_ctrl"
    print(f"Starting {cam_name} in tmux session {tmux_name}")
    tmux = find_or_create(tmux_name)
    kill_running(tmux)

    # initiating this camera's main method
    print(f"DEBUG: using {cam_method}")
    send_keys(tmux, f"ipython -i -m {cam_method}")
    # all done. no cleanup
    print(f"Finished initiating camera. Inspect {tmux_name} "
          "for further debug information (some cameras take "
          "a little longer to start).")

    if call_from_dunder_main:
        globals().update(locals())


if __name__ == "__main__":
    print('\n------')
    main(call_from_dunder_main=True)
