from __future__ import annotations

from ..main_arch import CameraLauncherSpec

# Specials notes
BASE_CONFIG = [
        CameraLauncherSpec(
                name='SIMUCAM',
                main='camstack.cam_mains.simucam',
        ),
]
