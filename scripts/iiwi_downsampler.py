import numpy as np
import cv2

from pyMilk.interfacing.shm import SHM

iiwi_cred2 = SHM('iiwi_raw')
iiwi_160 = SHM('iiwi', ((160, 160), np.uint16))

while True:
    iiwi_160.set_data(
            cv2.resize(iiwi_cred2.get_data(True), (160, 160)).astype(np.uint16))
