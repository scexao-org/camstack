from __future__ import annotations

from ..main_arch import CameraLauncherSpec

FIRST_CONFIG = [
        CameraLauncherSpec(name='FIRST', main='camstack.cam_mains.first_orcam',
                           required_machine='K', ctrl_tmux_name='fircam_ctrl'),
        CameraLauncherSpec(
                name='FIRST_PUPIL',
                main='camstack.cam_mains.first_pupil',
                required_machine='K',
        ),
]
