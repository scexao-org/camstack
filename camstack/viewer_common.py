import numpy as np
from pyMilk.interfacing.isio_shmlib import SHM

import os
import sys

MILK_SHM_DIR = os.getenv(
    'MILK_SHM_DIR')  # Expected /tmp <- MULTIVERSE FIXING NEEDED


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


def get_img_data(cam,
                 cam_type,
                 bias=None,
                 badpixmap=None,
                 subt_ref=False,
                 ref=None,
                 line_scale=True,
                 clean=True,
                 check=True):
    ''' ----------------------------------------
    Return the current image data content,
    formatted as a 2D numpy array.
    Reads from the already-opened shared memory
    data structure.
    ---------------------------------------- '''
    if cam_type == CRED1_str:
        temp = cam.get_data(check, reform=True, timeout=1.0).astype('float')
        temp[temp == 65535] = 1.
    elif cam_type == CRED2_str:
        # CHUCK IS ERRONEOUSLY IN UINT16 BUT ACTUALLY ITS INT16
        temp = cam.get_data(check, reform=True, timeout=1.0)
        temp.dtype = np.int16  # DIRTY CASTING
        temp = temp.astype(np.float32)  # CONVERSION
    else:
        temp = cam.get_data(check, reform=True, timeout=1.0).astype('float')

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
