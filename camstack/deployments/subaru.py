from __future__ import annotations

from ..main_arch import CameraLauncherSpec

SUBARU_CONFIG = [
        CameraLauncherSpec(name='ALALA', main='camstack.cam_mains.alala_orcam',
                           required_machine='AORTS'),
        CameraLauncherSpec(name='APD', main='camstack.cams.ao_apd',
                           required_machine='AORTS'),
        CameraLauncherSpec(name='APAPANE', main='camstack.cam_mains.apapane',
                           required_machine='5'),
        CameraLauncherSpec(name='APAPANEG', main='camstack.cam_mains.apapane',
                           required_machine='5', add_args=['G'],
                           ctrl_tmux_name='apapane_ctrl'),
        CameraLauncherSpec(
                name='IIWI',
                main='camstack.cam_mains.iiwi',
                required_machine='AORTS',
        ),
        CameraLauncherSpec(name='IIWIA', main='camstack.cam_mains.iiwi',
                           required_machine='AORTS', add_args=['A'],
                           ctrl_tmux_name='iiwi_ctrl'),
        CameraLauncherSpec(name='IIWIG', main='camstack.cam_mains.iiwi',
                           required_machine='AORTS', add_args=['G'],
                           ctrl_tmux_name='iiwi_ctrl'),
        CameraLauncherSpec(name='IIWII', main='camstack.cam_mains.iiwi',
                           required_machine='AORTS', add_args=['I'],
                           ctrl_tmux_name='iiwi_ctrl'),
        CameraLauncherSpec(name='IIWI5', main='camstack.cam_mains.iiwi',
                           required_machine='5', add_args=['5'],
                           ctrl_tmux_name='iiwi_ctrl'),
        CameraLauncherSpec(
                name='GLINT',
                main='camstack.cam_mains.glintcam',
                required_machine='5',
        ),
        CameraLauncherSpec(
                name='KIWIKIU',
                main='camstack.cam_mains.kiwikiu',
                required_machine='5',
        ),
        CameraLauncherSpec(
                name='PALILA',
                main='camstack.cam_mains.palila',
                required_machine='5',
        ),
        CameraLauncherSpec(name='PUEO', main='camstack.cam_mains.pueo',
                           required_machine='5', ctrl_tmux_name='ocam_ctrl'),
        CameraLauncherSpec(
                name='VCAM1',
                main='camstack.cam_mains.vcam',
                required_machine='5',
                add_args=['1'],
        ),
        CameraLauncherSpec(
                name='VCAM2',
                main='camstack.cam_mains.vcam',
                required_machine='5',
                add_args=['2'],
        ),
        CameraLauncherSpec(
                name='VPUPCAM',
                main='camstack.cam_mains.vpupcam',
                required_machine='V',
                conda_env_string='conda activate pycapture',
        ),
]
