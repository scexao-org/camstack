from __future__ import annotations

import os

CAMSTACK_DEPLOYMENT = os.environ.get('CAMSTACK_DEPLOYMENT_ID', 'SUBARU')

from . import base

CAMERA_LAUNCH_CONFIG = base.BASE_CONFIG

if CAMSTACK_DEPLOYMENT == 'SUBARU':
    from . import first, subaru
    CAMERA_LAUNCH_CONFIG += first.FIRST_CONFIG + subaru.SUBARU_CONFIG
elif CAMSTACK_DEPLOYMENT == 'KALAO':
    from . import kalao
    CAMERA_LAUNCH_CONFIG += kalao.KALAO_CONFIG
elif CAMSTACK_DEPLOYMENT == 'USYD':
    from . import usyd
    CAMERA_LAUNCH_CONFIG += usyd.USYD_VISPL_CONFIG
