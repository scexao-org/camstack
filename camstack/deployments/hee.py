from __future__ import annotations

from ..main_arch import CameraLauncherSpec

HEE_CONFIG = [
        CameraLauncherSpec(
                name='HEE',
                main='camstack.cam_mains.hee_orcam',
        ),
        CameraLauncherSpec(
                name='HEE2',
                main='camstack.cam_mains.hee2_orcam',
        ),
]
