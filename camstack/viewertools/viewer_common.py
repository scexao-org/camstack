'''
    Generic utilies for all the viewers !

    Factorizing some code between apapane.py, palila.py, renocam.py
'''
from __future__ import annotations

from typing import Tuple, Optional as Op, TYPE_CHECKING, Callable
if TYPE_CHECKING:
    from scxkw.redisutil.typed_db import Redis

import numpy as np
from enum import Enum
from pyMilk.interfacing.isio_shmlib import SHM
from pygame.constants import (KMOD_LALT, KMOD_LCTRL, KMOD_LSHIFT, KMOD_LMETA,
                              KMOD_RALT, KMOD_RCTRL, KMOD_RSHIFT)

import os
import sys
import time

MILK_SHM_DIR = os.getenv(
        'MILK_SHM_DIR')  # Expected /tmp <- MULTIVERSE FIXING NEEDED

# COLORS
WHITE = (255, 255, 255)
GREEN = (147, 181, 44)
BLUE = (0, 0, 255)
RED = (246, 133, 101)  #(185,  95, 196)
RED1 = (255, 0, 0)
BLK = (0, 0, 0)
CYAN = (0, 255, 255)

FGD_COL = WHITE  # foreground color (text)
SAT_COL = RED1  # saturation color (text)
BGD_COL = BLK  # background color
BUT_COL = BLUE  # button color


class CREDWHAT(Enum):
    ONE = 1
    TWO = 2


def locate_redis_db() -> Tuple[Op[Redis], bool]:
    from scxkw.config import REDIS_DB_HOST, REDIS_DB_PORT
    from scxkw.redisutil.typed_db import Redis
    rdb = Redis(host=REDIS_DB_HOST, port=REDIS_DB_PORT)
    # Is the server alive ?
    try:
        rdb_alive = rdb.ping()
        if not rdb_alive:
            raise ConnectionError
    except:
        print('Error: can\'t ping redis DB.')
        rdb = None
        rdb_alive = False

    return rdb, rdb_alive


def check_modifiers(mods: int, lc: bool = False, la: bool = False,
                    ls: bool = False, rc: bool = False, ra: bool = False,
                    rs: bool = False, mw: bool = False) -> bool:
    '''
        Check keyboard modifiers from a pygame event.

        mods: obtained from pygame.key.get_mods
        lc: Left Ctrl
        la: Left Alt
        ls: Left Shift
        rc: Right Ctrl
        ra: Right Alt
        rs: Right Shift
        mw: Meta / Win
    '''

    ok_mods = ((not lc) ^ bool(mods & KMOD_LCTRL)) and \
              ((not la) ^ bool(mods & KMOD_LALT)) and \
              ((not ls) ^ bool(mods & KMOD_LSHIFT)) and \
              ((not rc) ^ bool(mods & KMOD_RCTRL)) and \
              ((not ra) ^ bool(mods & KMOD_RALT)) and \
              ((not rs) ^ bool(mods & KMOD_RSHIFT)) and \
              ((not mw) ^ bool(mods & KMOD_LMETA))

    return ok_mods


def open_shm(shm_name: str, dims: Tuple[int, int] = (1, 1),
             check: bool = False) -> SHM:
    assert MILK_SHM_DIR
    return open_shm_fullpath(MILK_SHM_DIR + "/" + shm_name + ".im.shm",
                             dims=dims, check=check)


def open_shm_fullpath(shm_name: str, dims: Tuple[int, int] = (1, 1),
                      check: bool = False) -> SHM:
    # SHM doesn't exist at all
    if not os.path.isfile(shm_name):
        _data = np.zeros(dims[::-1], dtype=np.float32)
        shm = SHM(shm_name, data=_data, verbose=False)
        return shm

    # SHM exists
    shm = SHM(shm_name)

    if check and (shm.shape_c != dims):
        # SHM is the wrong size.
        _data = np.zeros(dims[::-1], dtype=np.float32)
        shm = SHM(shm_name, data=_data, verbose=False)  # This will overwrite

    return shm


# ------------------------------------------------------------------
#  Read database for some stage status
# ------------------------------------------------------------------
CrazyTuple = Tuple[bool, bool, bool, bool, bool, str, bool, float, float, str,
                   bool]


def RDB_pull(rdb: Redis, rdb_alive: bool, cam_apapane: bool,
             do_defaults: bool = True) -> CrazyTuple:
    '''
        cam_apapane: False for Palila, True for Apapane
        do_defaults: if rdb_alive is False, fallback to defaults
                     ortherwise raise a ConnectionError
                    This Error can be caught in order for a call to just "do nothing" and keep prev. values
                    rather than all of a sudden overwrite with all the defaults.
    '''

    import redis  # Need the namespace for the exception to catch

    fits_keys_to_pull = {
            'X_IRCFLT',
            'X_IRCBLK',
            'X_PALPUP',
            'X_PALPUS',
            'X_PHOPKO',
            'X_RCHPKO',
            'X_APAPKO',
            'D_IMRPAD',
            'D_IMRPAP',
            'OBJECT',
            'X_IRCWOL',
    }
    # Now Getting the keys

    if rdb_alive:
        with rdb.pipeline() as pipe:
            for key in fits_keys_to_pull:
                pipe.hget(key, 'value')

            try:
                values = pipe.execute()
                if values is None:
                    rdb_alive = False
                else:
                    status = {k: v for k, v in zip(fits_keys_to_pull, values)}
            except redis.exceptions.TimeoutError:
                rdb_alive = False

    if not rdb_alive and not do_defaults:
        raise ConnectionError("Redis unavailable and not skipping defaults")

    if rdb_alive:  # Fetch from RDB
        pup = status['X_PALPUP'].strip() == 'IN'
        reachphoto = status['X_PALPUS'].strip() == 'REACH'
        gpin = status['X_PHOPKO'].strip() == 'IN'
        rpin = status['X_RCHPKO'].strip() == 'IN'
        slot = status['X_IRCFLT']
        block = status['X_IRCBLK'].strip() == 'IN'
        bpin = status['X_APAPKO'].strip() == 'IN'
        pap = float(status['D_IMRPAP'])
        pad = float(status['D_IMRPAD'])
        target = status['OBJECT']
        pdi = status['X_IRCWOL'] == 'IN'
    else:  # Sensible defaults?
        pup = False
        reachphoto = False
        gpin = False
        rpin = False
        bpin = False
        slot = '!NO REDIS!'
        block = False
        pap = 0.
        pad = 0.
        target = 'UNKNOWN'
        pdi = False

    return (pup, reachphoto, gpin, rpin, bpin, slot, block, pap, pad, target,
            pdi)


def get_img_data(cam: SHM, cam_type: CREDWHAT, bias: Op[np.ndarray] = None,
                 badpixmap: Op[np.ndarray] = None, subt_ref: bool = False,
                 ref: Op[np.ndarray] = None, lin_scale: bool = True,
                 clean: bool = True,
                 check: bool = True) -> Tuple[np.ndarray, float]:
    ''' ----------------------------------------
    Return the current image data content,
    formatted as a 2D numpy array.
    Reads from the already-opened shared memory
    data structure.
    ---------------------------------------- '''
    if cam_type == CREDWHAT.ONE:
        temp = cam.get_data(check, timeout=1.0).astype(np.float32)
        temp[temp == 65535] = 1.
    elif cam_type == CREDWHAT.TWO:
        temp = cam.get_data(check, timeout=1.0)
        temp = temp.astype(np.float32)  # CONVERSION
    else:
        temp = cam.get_data(check, timeout=1.0).astype(np.float32)

    if clean:
        if badpixmap is not None:
            temp *= badpixmap
        #isat = np.percentile(temp, 99.995)
        isat = np.max(temp)
        if bias is not None:
            temp -= bias
    else:
        # isat = np.percentile(temp, 99.995)
        isat = np.max(temp)

    #cam_clean.set_data(temp.astype(np.float32))

    if subt_ref:
        assert ref is not None
        temp -= ref
        if not lin_scale:
            temp = np.abs(temp)

    return (temp, isat)


def ave_img_data_from_callable(get_img_data: Callable, nave: int,
                               bias: Op[np.ndarray] = None,
                               badpixmap: Op[np.ndarray] = None,
                               clean: bool = True, disp: bool = False,
                               tint: float = 0,
                               timeout: Op[float] = None) -> np.ndarray:

    if nave is None:
        nave = 1000000

    if timeout is None:
        timeout = 10.0

    count = 0
    ave_im: Op[np.ndarray] = None

    t_start = time.time()
    for i in range(nave):
        if disp:
            sys.stdout.write('\r tint = %8.6f s: acq. #%5d' % (tint * 1.e-6, i))
            sys.stdout.flush()
        if i == 0:
            ave_im = get_img_data(bias=bias, badpixmap=badpixmap,
                                  clean=clean)[0].astype(np.float32)
        else:
            assert ave_im is not None
            ave_im += get_img_data(bias=bias, badpixmap=badpixmap,
                                   clean=clean)[0]
        count += 1
        if time.time() - t_start > timeout:
            break

    assert ave_im is not None
    ave_im /= float(count)

    return ave_im
