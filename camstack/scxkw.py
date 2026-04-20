"""
Bind module for scxkw imports.

Re-exports all scxkw symbols used by camstack. When scxkw is not installed,
provides local fallback definitions so that camstack can still be imported
and used.
"""
from __future__ import annotations

import logging
import typing as typ

logg = logging.getLogger(__name__)

HAS_SCXKW = False


class MAGIC_HW_STR:
    HEIGHT = '#HEIGHT#'
    WIDTH = '#WIDTH#'


class MAGIC_BOOL_STR:
    TRUE = '#TRUE#'
    FALSE = '#FALSE#'
    TUPLE = ('#FALSE#', '#TRUE#')


try:
    from scxkw.config import (redis_check_enabled, REDIS_DB_HOST, REDIS_DB_PORT)
    from scxkw.redisutil.typed_db import Redis
    HAS_SCXKW = True

except ImportError:
    logg.warning("scxkw is not installed — using fallback definitions. "
                 "Redis-based features will be unavailable.")

    def redis_check_enabled() -> tuple[typ.Any, bool]:
        return None, False

    REDIS_DB_HOST: str = 'localhost'
    REDIS_DB_PORT: int = 6379

    class Redis:

        def __init__(self, host: str, port: int) -> None:
            raise ImportError('Redis not available as scxkw import failed.')
