from __future__ import annotations

import shutil

# search for mamba first, fall back to conda
MAMBA_OR_CONDA = 'mamba' if shutil.which('mamba') is not None else 'conda'

# TODO: in future, add basic virtualenv, add uv.
