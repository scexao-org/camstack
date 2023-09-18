'''
    Special backend class
    Starts up APDs and a couple SSH tunnels to be able to execute the APD safety swiftly.

    The associated main also defines a pyroserver and
'''
from __future__ import annotations

import typing as typ

import os
import subprocess
import time
import logging as logg

from camstack.cams.base import BaseCamera
from camstack.core import utilities as util

from camstack.core.utilities import (ModeIDorHWType, CsetPrioType,
                                     DependentProcess)


class APDAcquisition(BaseCamera):

    MODES = {0: util.CameraMode(x0=0, x1=215, y0=0, y1=0)}

    def __init__(self, name: str, stream_name: str, fpdp_channel: int,
                 no_start: bool = False, taker_cset_prio: CsetPrioType = ...,
                 dependent_processes: typ.List[DependentProcess] = ...) -> None:

        self.fpdp_channel = fpdp_channel

        # Add a curvature compute dependent.
        # Just put it on the same cset...
        cset = taker_cset_prio[0]
        prio = taker_cset_prio[1] - 1 if taker_cset_prio[1] is not None else 0

        cli_cmd_curv_computer = '\n'.join([
                'cacao << EOF',
                'cacaoio.ao188preproc ..procinfo 1',
                f'cacaoio.ao188preproc ..triggersname {stream_name}',
                'cacaoio.ao188preproc ..triggermode 3',
                'cacaoio.ao188preproc ..loopcntMax -1',
                f'readshmim {stream_name}',
                f'cacaoio.ao188preproc {stream_name}',
                'EOF',
        ])

        # Replace with FPS some day.
        curvature_computation = util.DependentProcess(
                'apd_curv', cli_cmd=cli_cmd_curv_computer, cli_args=[],
                cset=cset, rtprio=prio, kill_upon_create=True)

        self.dependent_processes += [curvature_computation]

        super().__init__(name, stream_name, 0, no_start, taker_cset_prio,
                         dependent_processes)

        # Open 'dem SSH tunnels.
        # Actually this could be totally split into a dedicated tunnel manager class
        self.ssh_tunnel_howfs = subprocess.Popen(
                'ssh -NL 18816:10.0.0.6:18816 obcp'.split(' '))
        self.ssh_tunnel_lowfs = subprocess.Popen(
                'ssh -NL 18818:10.0.0.6:18818 obcp'.split(' '))

        assert self.ssh_tunnel_howfs.poll() is None
        assert self.ssh_tunnel_lowfs.poll() is None

    def init_framegrab_backend(self) -> None:
        logg.debug('init_framegrab_backend @ APDAcquisition')
        ...

    def _prepare_backend_cmdline(self, reuse_shm: bool = True) -> None:
        exec_path = os.environ['SCEXAO_HW'] + '/bin/hwacq-fpdptake'
        self.taker_tmux_command = f'{exec_path} -s {self.STREAMNAME} -u {self.fpdp_channel} -Z'

        if reuse_shm:
            self.taker_tmux_command += ' -R'

    def _ensure_backend_restarted(self) -> None:
        # Plenty simple enough for FPDP, never failed me
        time.sleep(1.0)

    def poll_camera_for_keywords(self) -> None:
        # Monitor that the SSH tunnels are still alive!
        # Monitor that the APD count is still alive
        # Monitor that the curvature dependent is still alive.
        if self.ssh_tunnel_howfs.poll() is not None:
            logg.error('HOWFS SSH tunnel is down. Restarting one...')
            self.ssh_tunnel_howfs = subprocess.Popen(
                    'ssh -NL 18816:10.0.0.6:18816 obcp'.split(' '))

        if self.ssh_tunnel_lowfs.poll() is not None:
            logg.error('LOWFS SSH tunnel is down. Restarting one...')
            self.ssh_tunnel_lowfs = subprocess.Popen(
                    'ssh -NL 18818:10.0.0.6:18818 obcp'.split(' '))

        if not self.dependent_processes[-1].is_running():
            msg = 'Curvature computer crashed!!! Safety disabled!!!'
            logg.critical(msg)
            raise AssertionError(msg)  # Wait this is gonna get catched.
