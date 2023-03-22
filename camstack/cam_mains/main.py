from argparse import ArgumentParser

from camstack.cam_mains import CAM_METHODS
from camstack.core.tmux import find_or_create, send_keys, kill_running

CAM_NAMES = [str(k) for k in CAM_METHODS.keys()]
parser = ArgumentParser(prog="camstart", description="Spin up or restart a camera tmux daemon", 
                        epilog=f"Cameras: {' '.join(CAM_NAMES)}")
parser.add_argument("camera", help="Name of camera to start")

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

def main():
    args = parser.parse_args()
    ## Step 1. Create tmux and issue kills
    cam_name = args.camera.upper()
    if cam_name not in CAM_NAMES:
        raise ValueError(f"{cam_name} not recognized.")
    # default came name e.g. palila_ctrl
    tmux_name = f"{cam_name.lower()}_ctrl"
    print(f"Starting {cam_name} in tmux session {tmux_name}")
    tmux = find_or_create(tmux_name)
    kill_running(tmux)
    # initiating this camera's main method
    cam_method = CAM_METHODS[cam_name]
    print(f"DEBUG: using {cam_method}")
    send_keys(tmux, f"python -im {cam_method}")
    # all done. no cleanup
    print(f"Finished initiating camera. Inspect {tmux_name} for further debug information (some cameras take a little longer to start).")

if __name__ == "__main__":
    main()