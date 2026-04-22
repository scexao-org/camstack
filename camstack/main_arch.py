from __future__ import annotations
'''
Module camstack.main_arch

Definitions / config schema for deployments
'''

from dataclasses import dataclass, field


@dataclass
class CameraLauncherSpec:
    name: str
    main: str
    add_args: list[str] = field(default_factory=list)

    conda_env_string: str = ''  # env loader as a separate command 'conda activate x', mamba, venv, uv, etc.
    ctrl_tmux_name: str = ''  # None default to <name.lower()>_ctrl
    required_machine: str | None = None  # WHICHCOMP mechanism SSH lookup

    def __post_init__(self) -> None:
        if self.ctrl_tmux_name == '':
            self.ctrl_tmux_name = f'{self.name.lower()}_ctrl'
