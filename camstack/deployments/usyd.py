from __future__ import annotations

from ..main_arch import CameraLauncherSpec

USYD_VISPL_CONFIG = [
        CameraLauncherSpec(\
            name='VISPG1', main='camstack.cam_mains.usyd',
            add_args=['VPG1'], conda_env_string='mamba activate py38'),
        CameraLauncherSpec(\
            name='CB2', main='camstack.cam_mains.usyd',
            add_args=['CB2']
        )
]
