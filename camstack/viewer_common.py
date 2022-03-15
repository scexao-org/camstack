'''
    Generic utilies for all the viewers !

    Factorizing some code between buffycam.py, chuckcam.py, renocam.py
'''

import numpy as np
from pyMilk.interfacing.isio_shmlib import SHM
from pygame.locals import (KMOD_LALT, KMOD_LCTRL, KMOD_LSHIFT, KMOD_LMETA,
                           KMOD_RALT, KMOD_RCTRL, KMOD_RSHIFT)

import os
import sys

MILK_SHM_DIR = os.getenv(
    'MILK_SHM_DIR')  # Expected /tmp <- MULTIVERSE FIXING NEEDED


def locate_redis_db():
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


def check_modifiers(mods,
                    lc: bool = False,
                    la: bool = False,
                    ls: bool = False,
                    rc: bool = False,
                    ra: bool = False,
                    rs: bool = False,
                    mw: bool = False):
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


def open_shm(shm_name, dims=(1, 1), check=False):
    return open_shm_fullpath(MILK_SHM_DIR + "/" + shm_name + ".im.shm",
                             dims=dims,
                             check=check)


def open_shm_fullpath(shm_name, dims=(1, 1), check=False):
    data = np.zeros((dims[1], dims[0]), dtype=np.float32).squeeze()
    if not os.path.isfile(shm_name):
        shm_data = SHM(shm_name, data=data, verbose=False)
    else:
        shm_data = SHM(shm_name)
    if check:
        tmp = shm_data.shape_c
        if tmp != dims:
            #if shm_data.mtdata['size'][:2] != dims:
            # TODO THIS WON'T PASS IF OTHER USER OWNS THE SHM
            # os.system("rm %s/%s.im.shm" % (MILK_SHM_DIR, shm_name, ))
            shm_data = SHM(shm_name, data=data,
                           verbose=False)  # This will overwrite

    return shm_data


CRED1_str = 'cred1'
CRED2_str = 'cred2'


# ------------------------------------------------------------------
#  Read database for some stage status
# ------------------------------------------------------------------
def RDB_pull(rdb, rdb_alive: bool, cam_is_buffy: bool):
    '''
        cam_buffy: False for Chuck, True for Buffy
    '''

    PUP_KEY = ('X_CHKPUP', 'X_BUFPUP')[cam_is_buffy]
    if rdb_alive:  # Fetch from RDB
        fits_keys_to_pull = {
            'X_IRCFLT', 'X_IRCBLK', PUP_KEY, 'X_CHKPUS', 'X_NULPKO',
            'X_RCHPKO', 'X_BUFPKO', 'D_IMRPAD', 'D_IMRPAP', 'OBJECT'
        }
        # Now Getting the keys
        made_count = 0
        while made_count < 10:
            try:
                with rdb.pipeline() as pipe:
                    for key in fits_keys_to_pull:
                        pipe.hget(key, 'value')
                    values = pipe.execute()
                break
            except:
                print('Redis error.')
                made_count += 1

        status = {k: v for k, v in zip(fits_keys_to_pull, values)}

        pup = status[PUP_KEY].strip() == 'IN'
        reachphoto = status['X_CHKPUS'].strip() == 'REACH'
        gpin = status['X_NULPKO'].strip() == 'IN'
        rpin = status['X_RCHPKO'].strip() == 'IN'
        slot = status['X_IRCFLT']
        block = status['X_IRCBLK'].strip() == 'IN'
        bpin = status['X_BUFPKO'].strip() == 'IN'
        pap = float(status['D_IMRPAP'])
        pad = float(status['D_IMRPAD'])
        target = status['OBJECT']
    else:  # Sensible defaults?
        pup = False
        reachphoto = False
        gpin = False
        rpin = False
        bpin = False
        slot = 'H-band'
        block = False
        pap = 0
        pad = 0
        target = 'UNKNOWN'

    return (pup, reachphoto, gpin, rpin, bpin, slot, block, pap, pad, target)


def get_img_data(cam,
                 cam_type,
                 bias=None,
                 badpixmap=None,
                 subt_ref=False,
                 ref=None,
                 lin_scale=True,
                 clean=True,
                 check=True):
    ''' ----------------------------------------
    Return the current image data content,
    formatted as a 2D numpy array.
    Reads from the already-opened shared memory
    data structure.
    ---------------------------------------- '''
    if cam_type == CRED1_str:
        temp = cam.get_data(check, reform=True, timeout=1.0).astype(np.float32)
        temp[temp == 65535] = 1.
    elif cam_type == CRED2_str:
        temp = cam.get_data(check, reform=True, timeout=1.0)
        temp = temp.astype(np.float32)  # CONVERSION
    else:
        temp = cam.get_data(check, reform=True, timeout=1.0).astype(np.float32)

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
        temp -= ref
        if not lin_scale:
            temp = np.abs(temp)

    return (temp, isat)


def get_img_data_cred1(cam, *args, **kwargs):
    return get_img_data(cam, CRED1_str, *args, **kwargs)


def get_img_data_cred2(cam, *args, **kwargs):
    return get_img_data(cam, CRED2_str, *args, **kwargs)


def ave_img_data_from_callable(get_img_data,
                               nave,
                               bias=None,
                               badpixmap=None,
                               clean=True,
                               disp=False,
                               tint=0):

    for i in range(nave):
        if disp:
            sys.stdout.write('\r tint = %8.6f s: acq. #%5d' %
                             (tint * 1.e-6, i))
            sys.stdout.flush()
        if i == 0:
            ave_im = get_img_data(bias=bias, badpixmap=badpixmap,
                                  clean=clean)[0] / float(nave)
        else:
            ave_im += get_img_data(bias=bias, badpixmap=badpixmap,
                                   clean=clean)[0] / float(nave)

    return (ave_im)
