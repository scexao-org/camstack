#!/usr/bin/env python

# -------------------------------------------------- #
#    ___ _                _      ___                 #
#   / __\ |__  _   _  ___| | __ / __\__ _ _ __ ___   #
#  / /  | '_ \| | | |/ __| |/ // /  / _` | '_ ` _ \  #
# / /___| | | | |_| | (__|   </ /__| (_| | | | | | | #
# \____/|_| |_|\__,_|\___|_|\_\____/\__,_|_| |_| |_| #
#                                                    #
# -------------------------------------------------- #

import pygame
from pygame.locals import *

import numpy as np

from matplotlib import cm

import os, sys
import struct

from PIL import Image
import time
import math as m
import copy
import datetime as dt
from astropy.io import fits as pf
import subprocess

from scxkw.config import REDIS_DB_HOST, REDIS_DB_PORT
from scxkw.redisutil.typed_db import Redis

from pyMilk.interfacing.isio_shmlib import SHM

home = os.getenv('HOME')
conf_dir = home + "/conf/chuckcam_aux/"
sys.path.append(home + '/src/lib/python/')

MILK_SHM_DIR = os.getenv('MILK_SHM_DIR')

import image_processing as impro

ZERO_NODIM = np.array(0., dtype=np.float32)
ONES_NODIM = np.array(1., dtype=np.float32)


# ------------------------------------------------------------------
#             short hands for opening and checking shm
# ------------------------------------------------------------------
def open_shm(shm_name, dims=(1, 1), check=False):
    if not os.path.isfile(MILK_SHM_DIR + "/%s.im.shm" % (shm_name, )):
        os.system("creashmim %s %d %d" % (shm_name, dims[0], dims[1]))
    shm_data = SHM(MILK_SHM_DIR + "/%s.im.shm" % (shm_name, ))
    if check:
        tmp = shm_data.shape_c
        if tmp != dims:
            #if shm_data.mtdata['size'][:2] != dims:
            os.system("rm %s/%s.im.shm" % (MILK_SHM_DIR, shm_name, ))
            os.system("creashmim %s %d %d" % (shm_name, dims[0], dims[1]))
            shm_data = SHM(MILK_SHM_DIR + "/%s.im.shm" % (shm_name, ), verbose=False)

    return shm_data


# ------------------------------------------------------------------
#             short hands for tmux commands
# ------------------------------------------------------------------
def tmux(cargs="", session="ircam0", command="send-keys"):
    ''' ------------------------------------------------------------
    Synthesizes and sends a tmux command. The default option was
    chosen to match the most common one, hence making the code
    below more concise.
    ------------------------------------------------------------ '''
    if cargs == "":
        os.system("tmux %s -t %s" % (command, session))
    else:
        os.system("tmux %s -t %s '%s' Enter" % (command, session, cargs))


# ------------------------------------------------------------------
#             short hands for shared memory data access
# ------------------------------------------------------------------
def get_img_data(bias=None,
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
    temp = cam.get_data(check, reform=True, timeout=1.0).astype('float')
    if clean:
        if badpixmap is not None:
            temp *= badpixmap
        #isat = np.percentile(temp, 99.995)
        isat = np.max(temp)
        if bias is not None:
            temp -= bias
    else:
        #isat = np.percentile(temp, 99.995)
        isat = np.max(temp)

    #cam_clean.set_data(temp.astype(np.float32))

    if subt_ref:
        temp -= ref
        if not lin_scale:
            temp = np.abs(temp)

    return (temp, isat)


# ------------------------------------------------------------------
#             short hands for image averaging
# ------------------------------------------------------------------
def ave_img_data(nave,
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


# ------------------------------------------------------------------
#  another short hand to convert numpy array into image for display
# ------------------------------------------------------------------
def arr2im(arr,
           vmin=0.,
           vmax=10000.0,
           pwr=1.0,
           subt_ref=False,
           lin_scale=True,
           pos=[0, 0]):

    (ysizeim, xsizeim) = arr.shape
    ymin = xmin = 0
    ymax = ysizeim
    xmax = xsizeim
    if z2 != 1:
        ymin = max(256 + round(pos[1] + cor[1] - crop[2] - ysizeim / 2. / z2),
                   0)
        ymax = min(256 + round(pos[1] + cor[1] - crop[2] + ysizeim / 2. / z2),
                   ysizeim)
        xmin = max(320 + round(pos[0] + cor[0] - crop[0] - xsizeim / 2. / z2),
                   0)
        xmax = min(320 + round(pos[0] + cor[0] - crop[0] + xsizeim / 2. / z2),
                   xsizeim)
        if ymin == 0:
            ymax = round(ysizeim / float(z2))
        elif ymax == ysizeim:
            ymin = ysizeim - round(ysizeim / float(z2))
        if xmin == 0:
            xmax = round(xsizeim / float(z2))
        elif xmax == xsizeim:
            xmin = xsizeim - round(xsizeim / float(z2))
        ymin, ymax = int(ymin), int(ymax)
        xmin, xmax = int(xmin), int(xmax)
        arr2 = arr[ymin:ymax, xmin:xmax].astype('float')
    else:
        arr2 = arr.astype('float')

    if not lin_scale:
        lmin = np.percentile(arr2, 0.8)
        arr2 -= lmin
        mask = arr2 > 0
        arr2 *= mask
    arr3 = arr2**pwr
    mmin, mmax = arr3.min(), arr3.max()
    if subt_ref and lin_scale:
        if mmax > abs(mmin):
            arr3[0, 0] = -mmax
            arr3[0, 1] = -mmin
            mmin = -mmax
        else:
            arr3[0, 0] = -mmin
            arr3[0, 1] = -mmax
            mmax = -mmin
    arr3 -= mmin
    if mmin < mmax:
        arr3 /= (mmax - mmin)

    z3 = xsize / float(xsizeim)
    xshift = yshift = 0
    if xsizeim / float(ysizeim) < xsize / float(ysize):
        z3 = ysize / float(ysizeim)
        xsizeim2 = int(xsize / z3)
        temp = np.zeros(
            (round(ysizeim / float(z2)), round(xsizeim2 / float(z2))))
        temp[:, :round(xsizeim / float(z2))] = arr3
        xshift = int(round((xsizeim2 - xsizeim) / z2 / 2))
        arr3 = np.roll(temp, xshift, axis=1)

    elif xsizeim / float(ysizeim) > xsize / float(ysize):
        z3 = xsize / float(xsizeim)
        ysizeim2 = int(ysize / z3)
        temp = np.zeros(
            (round(ysizeim2 / float(z2)), round(xsizeim / float(z2))))
        temp[:round(ysizeim / float(z2)), :] = arr3
        yshift = int(round((ysizeim2 - ysizeim) / z2 / 2))
        arr3 = np.roll(temp, yshift, axis=0)

    img = Image.fromarray(arr3)
    rimg = img.resize((xws, yws), resample=Image.NEAREST)
    rarr = np.asarray(rimg)
    test = mycmap(rarr.transpose())
    return ((255 * test[:, :, :3]).astype('int'), z3, xmin, xmax, ymin, ymax,
            xshift, yshift)


# ------------------------------------------------------------------
#  define range of frequencies
# ------------------------------------------------------------------
def whatfps(fps, crop):

    #define if we are in a predifined crop mode and set max FPS
    cropmode = -1
    fpsmax = max(
        fps, 600.
    )  # if unknow configuration, set current fps as max or 600Hz (full frame) as a safeguard. Usually the current frame rate is the max one.
    for i in range(12):
        if np.all(crop == setcrops[:, i]):
            cropmode = i
            fpsmax = fpsmaxs[i]
    fpss2 = fpss[np.where(fpss < fpsmax)[0]]
    fpss2 = np.append(fpss2, fpsmax)
    nfps2 = np.size(fpss2)

    if fps <= fpss2[-1]:
        findex = np.where(np.abs(fpss2 - fps) == np.min(np.abs(fpss2 -
                                                               fps)))[0][0]
    else:
        findex = nfps2 - 1

    return (fpss2, nfps2, findex)


# ------------------------------------------------------------------
#  define range of expt
# ------------------------------------------------------------------
def whatexpt(etime, fps, delay=0.):

    # and the closest matching value in our etimes array
    if np.where(1e6 / fps - delay == etimes)[0].shape[0] > 0:
        net2 = np.where(1e6 / fps - delay == etimes)[0][0] + 1
        etimes2 = etimes[:net2]
    else:
        etimes2 = etimes[np.where(etimes < 1.e6 / fps - delay)[0]]
        etimes2 = np.append(etimes2, 1.e6 / fps - delay)
        net2 = np.size(etimes2)
    if etime <= etimes2[-1]:
        tindex = np.where(
            np.abs(etimes2 - etime) == np.min(np.abs(etimes2 - etime)))[0][0]
    else:
        tindex = net2 - 1

    return (etimes2, net2, tindex)


# ------------------------------------------------------------------
#  define NDR index
# ------------------------------------------------------------------
def whatndr(ndr):

    if ndr <= ndrs[-1]:
        nindex = np.where(ndrs >= ndr)[0][0]
    else:
        nindex = nndr - 1

    return (nindex)


# ------------------------------------------------------------------
#  Update dark and badpixmap
# ------------------------------------------------------------------
def updatebiasbpm():

    bpname = conf_dir + "badpixmap%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
             % (fps, etime, ndr, crop[0], crop[2], xsizeim, ysizeim)
    try:
        badpixmap = pf.getdata(bpname)
        cam_badpixmap.set_data(badpixmap.astype(np.float32))
        print("badpixmap loaded")
    except:
        bpmhere = False
        badpixmap = np.ones((ysizeim, xsizeim))
        print("badpixmap NOT loaded")
    else:
        bpmhere = True

    bname = conf_dir + "bias%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
            % (fps, etime, ndr, crop[0], crop[2], xsizeim, ysizeim)
    try:
        bias = pf.getdata(bname)
        cam_dark.set_data(bias.astype(np.float32))
        bias *= badpixmap
        print("bias loaded")
    except:
        biashere = False
        bias = np.zeros((ysizeim, xsizeim))
        print("bias NOT loaded")
    else:
        biashere = True

    return (badpixmap, bias, bpmhere, biashere)


# ------------------------------------------------------------------
#  Make badpixmap from bias
# ------------------------------------------------------------------
def make_badpix(bias, filt=3.5):
    ''' -------------------------------------------------------
    Builds and returns a badpixel map based on the statistical
    properties of the current dark.

    Parameter:
    ---------
    - filt (default=3.5): filters beyond this many sigmas
    ------------------------------------------------------- '''
    bpmap = np.ones_like(bias)
    rms = np.std(bias)
    mu = np.median(bias)
    bpmap[bias > mu + filt * rms] = 0.0
    bpmap[bias < mu - filt * rms] = 0.0
    return (bpmap)

# ------------------------------------------------------------------
#  Read database for some stage status
# ------------------------------------------------------------------
def RDB_pull(rdb):

    fits_keys_to_pull = {'X_IRCFLT','X_IRCBLK','X_CHKPUP','X_CHKPUS','X_NULPKO','X_RCHPKO','D_IMRPAD','D_IMRPAP'}
    # Now Getting the keys
    with rdb.pipeline() as pipe:
        for key in fits_keys_to_pull:
            pipe.hget(key, 'FITS header')
            pipe.hget(key, 'value')
        values = pipe.execute()
    status = {k: v for k,v in zip(values[::2], values[1::2])}

    pup = status['X_CHKPUP'].strip() == 'IN'
    reachphoto = status['X_CHKPUS'].strip() == 'REACH'
    gpin = status['X_NULPKO'].strip() == 'IN'
    rpin = status['X_RCHPKO'].strip() == 'IN'
    slot = status['X_IRCFLT']
    block = status['X_IRCBLK'].strip() == 'IN'
    pap = float(status['D_IMRPAP'])
    pad = float(status['D_IMRPAD'])

    return(pup,reachphoto,gpin,rpin,slot,block,pap,pad)

# ------------------------------------------------------------------
#  Filter message
# ------------------------------------------------------------------
def whatfilter(reachphoto, slot, block):
    if reachphoto:
        msgwhl = "      OPEN      "
    else:
        if block:
            msgwhl = "     BLOCK      "
        else:
            msgwhl = slot
    return(msgwhl)

# ------------------------------------------------------------------
#  Top message
# ------------------------------------------------------------------
def whatmsg(pup, reachphoto, gpin, rpin):
    msgtops = [
        "                ", "     PUPIL      ", "     REACH      ",
        "REACH PHOTOMETRY", "     GLINT      "
    ]
    if reachphoto:
        msgtop = msgtops[3]
    else:
        if pup and not rpin:
            msgtop = msgtops[1]

        elif rpin:
            msgtop = msgtops[2]
        else:
            if gpin:
                msgtop = msgtops[4]
            else:
                msgtop = msgtops[0]
    return (msgtop)


# ------------------------------------------------------------------
# ------------------------------------------------------------------

hmsg = """CHUCK's INSTRUCTIONS
-------------------

camera controls:
---------------
q           : increase exposure time
a           : decrease exposure time
CTRL+q      : increase number of NDR
CTRL+a      : decrease number of NDR
CRTL+o      : increase frame rate
CTRL+l      : decrease frame rate
CTRL+h      : hotspotalign
CTRL+p      : camera to pupil plane/focus plane
CTRL+i      : REACH mode in/out
CTRL+b      : take new darks
CTRL+SHIFT+b: take new dark for current exp
CTRL+r      : save a reference image
CTRL+s      : start/stop logging images
CTRL+SHIFT+s: start/stop archiving images
CTRL+d      : save a HDR image
CTRL+n      : switch to external/internal trigger
CTRL+1-6    : change filter wheel slot:
              1. OPEN 
              2. y-band
              3. 1550 nm, 25 nm BW
              4. 1550 nm, 50 nm BW
              5. J-band
              6. H-band
CTRL+7      : ircam block
CTRL+ARROW  : move PSF in focal plane
CTRL+ALT+f  : change to full frame
CTRL+ALT+0-=: change window size:
  [0]  320 x 256    ( 160-479 x  128-383)  fps = 1500.1 Hz
  [1]  224 x 188    ( 192-415 x  160-347)  fps = 2050.2 Hz
  [2]  128 x 128    ( 256-383 x  192-319)  fps = 4500.6 Hz
  [3]   64 x  64    ( 288-351 x  224-287)  fps = 9203.6 Hz
  [4]  192 x 192    ( 224-415 x  160-351)  fps = 2200.0 Hz
  [5]   96 x  72    ( 256-351 x  220-291)  fps = 8002.6 Hz
  [6]  320 x 256    ( 128-447 x  128-383)  fps = 1500.1 Hz
  [7]  224 x 188    ( 160-383 x  160-347)  fps = 2050.2 Hz
  [8]  128 x 128    ( 224-351 x  192-319)  fps = 4500.6 Hz
  [9]   64 x  64    ( 256-319 x  224-287)  fps = 9203.6 Hz
  [-]  192 x 192    ( 192-383 x  160-351)  fps = 2200.0 Hz
  [=]   96 x  72    ( 224-319 x  220-291)  fps = 8002.6 Hz

display controls:
----------------
d         : subtract dark for display
c         : display hotstpot crosses
l         : linear/non-linear display
m         : color/gray color-map
o         : bullseye on the PSF
i         : history of PSF positions
v         : start/stop accumulating and averaging frames
g         : seeing measurement (averaging must be on)
z         : zoom/unzoom on the center of the image
r         : subtract a reference image

mouse controls:
--------------
mouse     : display of the flux under the mouse pointer
left click: measure distances in mas
 
ESC       : quit chuckcam

"""

args = sys.argv[1:]
z1 = 1  # zoom for the display (default is 1)
if args != []:
    if isinstance(int(args[0]), int):
        z1 = int(args[0])
        z1 = min(2, max(1, z1))

# ------------------------------------------------------------------
#                access to shared memory structures
# ------------------------------------------------------------------
camid = 0  # camera identifier (0: science camera)
cam = SHM(MILK_SHM_DIR + "/ircam%d.im.shm" % (camid, ), verbose=False)
xsizeim, ysizeim = cam.shape_c

(xsize, ysize) = (320, 256)  #Force size of old chuck for the display

cam_dark = open_shm("ircam%d_dark" % (camid, ),
                    dims=(xsizeim, ysizeim),
                    check=True)
cam_badpixmap = open_shm("ircam%d_badpixmap" % (camid, ),
                         dims=(xsizeim, ysizeim),
                         check=True)
cam_paused = open_shm("ircam%d_paused" % (camid, ))
new_dark = open_shm("ircam%d_newdark" % (camid, ))
ircam_synchro = open_shm("ircam_synchro", dims=(6, 1))

# ------------------------------------------------------------------
#            Configure communication with SCExAO's redis
# ------------------------------------------------------------------
rdb = Redis(host=REDIS_DB_HOST, port=REDIS_DB_PORT)
# Is the server alive ?
try:
    alive = rdb.ping()
    if not alive:
        raise ConnectionError
except:
    print('Error: can\'t ping redis DB.')
    sys.exit(1)

pup,reachphoto,gpin,rpin,slot,block,pap,pad = RDB_pull(rdb)

pscale = 16.9  #mas per pixel in Chuckcam

filename = "/home/scexao/conf/chuckcam_aux/hotspots_cor.txt"
cors = [line.rstrip('\n') for line in open(filename)]
ncor = len(cors)
cort = np.zeros((2, ncor))
for i in range(ncor):
    corparam = cors[i].split(';')
    cort[0, i] = float(corparam[2])
    cort[1, i] = float(corparam[3])
cort /= pscale
cor = np.array([0, 0])
if gpin:
    cor = cort[:, 0]

# ------------------------------------------------------------------
#                       global variables
# ------------------------------------------------------------------

mycmap = cm.gray

# -----------------------
#   set up the window
# -----------------------
pygame.display.init()
pygame.font.init()

FPSdisp = 20  # frames per second setting
fpsClock = pygame.time.Clock()  # start the pygame clock!
XW, YW = xsize * z1, (ysize + 100) * z1

screen = pygame.display.set_mode((XW, YW), 0, 32)
pygame.display.set_caption('SCIENCE camera display!')

os.system("tmux new-session -d -s ircam%d" %
          (camid, ))  #start a tmux session for messsages
os.system("tmux new-session -d -s ircam_synchro"
          )  #start a tmux session for FLC synchro
res = subprocess.check_output("ps aux | grep ircam_synchro", shell=True)
if b'/home/scexao/bin/devices/ircam_synchro' not in res:
    tmux("ircam_synchro", session="ircam_synchro")

# ------------------------------------------------------------------
#              !!! now we are in business !!!!
# ------------------------------------------------------------------

WHITE = (255, 255, 255)
GREEN = (147, 181, 44)
BLUE = (0, 0, 255)
RED1 = (255, 0, 0)
RED = (246, 133, 101)  #(185,  95, 196)
BLK = (0, 0, 0)
CYAN = (0, 255, 255)

FGCOL = WHITE  # foreground color (text)
SACOL = RED1  # saturation color (text)
BGCOL = BLK  # background color
BTCOL = BLUE  # *button* color

background = pygame.Surface(screen.get_size())
background = background.convert()

etimes = np.array([
    10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000,
    200000, 500000
])
net = np.size(etimes)

fpss = np.array([10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000])
nfps = np.size(fpss)
fpsmaxs = np.array([
    1500.2, 2050.2, 4500.6, 9203.6, 2200.0, 8002.6, 1500.2, 2050.2, 4500.6,
    9203.6, 2200.0, 8002.6
])

setcrops = np.zeros((4, 12))
setcrops[:, 0] = [160, 479, 128, 383]
setcrops[:, 1] = [192, 415, 160, 347]
setcrops[:, 2] = [256, 383, 192, 319]
setcrops[:, 3] = [288, 351, 224, 287]
setcrops[:, 4] = [224, 415, 160, 351]
setcrops[:, 5] = [256, 351, 220, 291]
setcrops[:, 6] = [128, 447, 128, 383]
setcrops[:, 7] = [160, 383, 160, 347]
setcrops[:, 8] = [224, 351, 192, 319]
setcrops[:, 9] = [256, 319, 224, 287]
setcrops[:, 10] = [192, 383, 160, 351]
setcrops[:, 11] = [224, 319, 220, 291]

ndrs = np.array([1, 2, 4, 8, 16, 32, 64, 128, 255])
nndr = np.size(ndrs)

# get initial values for expt, fps and ndr
tmux("get_tint()", session="ircam%dctrl" % (camid, ))
time.sleep(1)
tmux("get_NDR()", session="ircam%dctrl" % (camid, ))
time.sleep(1)
tmux("get_fps()", session="ircam%dctrl" % (camid, ))
time.sleep(1)
sync_param = ircam_synchro.get_data().astype(np.int)
lag = 7
cam_ro = 22 - lag
sync_param[4] = 160
flc_oft = sync_param[4] - lag
ircam_synchro.set_data(sync_param.astype(np.float32))
if not sync_param[0] and sync_param[1]:
    etime = sync_param[2]
    fps = sync_param[3]
    delay = cam_ro + flc_oft + 3 * lag
else:
    etime = cam.get_expt() * 1e6
    fps = cam.get_fps()
    delay = 0
ndr = int(cam.get_ndr())
crop = cam.get_crop().astype(int)
etimet = etime * ndr

(fpss2, nfps2, findex) = whatfps(fps, crop)
(etimes2, net2, tindex) = whatexpt(etime, fps, delay)
nindex = whatndr(ndr)

# ----------------------------
#          labels
# ----------------------------
font1 = pygame.font.SysFont("default", 20 * z1)
font2 = pygame.font.SysFont("default", 14 * z1)
font3 = pygame.font.SysFont("monospace", 5 * (z1 + 1))
font4 = pygame.font.SysFont("monospace", 7 + 3 * z1)
font5 = pygame.font.SysFont("monospace", 7 + 3 * z1)
font5.set_bold(True)

xws = xsize * z1
yws = ysize * z1

path_cartoon = conf_dir + "Chuck%d.png" % (z1, )
cartoon1 = pygame.image.load(path_cartoon).convert_alpha()

lbl = font1.render("SCIENCE camera viewer", True, WHITE, BGCOL)
rct = lbl.get_rect()
rct.center = (110 * z1, 270 * z1)
screen.blit(lbl, rct)

lbl2 = font3.render("Chuck helps the weak who press [h]", True, WHITE, BGCOL)
rct2 = lbl2.get_rect()
rct2.center = (110 * z1, 285 * z1)
screen.blit(lbl2, rct2)

msg0 = "x0,y0 = %3d,%3d sx,sy = %3d,%3d" % (crop[0], crop[2], xsizeim, ysizeim)
info0 = font3.render(msg0, True, FGCOL, BGCOL)
rct_info0 = info0.get_rect()
rct_info0.center = (110 * z1, 295 * z1)

msg1 = ("t = %f" % (etime))[:8] + (" us FPS = %4d NDR = %3d" % (fps, ndr))
info1 = font3.render(msg1, True, FGCOL, BGCOL)
rct_info1 = info1.get_rect()
rct_info1.center = (110 * z1, 305 * z1)

imin, imax = 10000, 10000
msg2 = ("t = %f" % (etimet))[:8] + (" min,max = %5d,%5d" % (imin, imax))
info2 = font3.render(msg2, True, FGCOL, BGCOL)
rct_info2 = info2.get_rect()
rct_info2.center = (110 * z1, 315 * z1)

xmou, ymou, fmou = 100, 100, 10000
msg3 = " mouse = %3d,%3d flux = %5d" % (xmou, ymou, fmou)
info3 = font3.render(msg3, True, FGCOL, BGCOL)
rct_info3 = info3.get_rect()
rct_info3.center = (110 * z1, 325 * z1)

msgli = " "
mli = font4.render(msgli, True, CYAN)
rct_mli = mli.get_rect()
rct_mli.center = (xmou, ymou)

msgcoor = "                          "
mcoor = font4.render(msgcoor, True, CYAN)
rct_mcoor = mcoor.get_rect()
rct_mcoor.bottomleft = (15 * z1, 230 * z1)

msgcoor2 = "                          "
mcoor2 = font4.render(msgcoor2, True, CYAN)
rct_mcoor2 = mcoor2.get_rect()
rct_mcoor2.bottomleft = (15 * z1, 240 * z1)

msgsee = "                                     "
msee = font4.render(msgsee, True, CYAN)
rct_msee = msee.get_rect()
rct_msee.center = (xws / 2, 30 * z1)

dinfo = font3.render("                     ", True, FGCOL, BGCOL)
rct_dinfo = dinfo.get_rect()
rct_dinfo.center = (110 * z1, 335 * z1)
screen.blit(dinfo, rct_dinfo)

dinfo2 = font3.render("                          ", True, FGCOL, BGCOL)
rct_dinfo2 = dinfo2.get_rect()
rct_dinfo2.center = (110 * z1, 345 * z1)
screen.blit(dinfo2, rct_dinfo2)

msgsave1 = "saving images"
msgsave2 = "  before I   "
msgsave3 = "kick your ass"
savem1 = font5.render(msgsave1, True, RED1)
savem2 = font5.render(msgsave2, True, RED1)
savem3 = font5.render(msgsave3, True, RED1)
rct_savem1 = savem1.get_rect()
rct_savem2 = savem2.get_rect()
rct_savem3 = savem3.get_rect()
h_savem2 = savem2.get_height()
h_savem3 = savem3.get_height()
rct_savem1.bottomright = (xws - 10 * z1, yws - h_savem2 - h_savem3)
rct_savem2.bottomright = (xws - 10 * z1, yws - h_savem3)
rct_savem3.bottomright = (xws - 10 * z1, yws)

cx = xsize / 2.
cy = ysize / 2.

#bullseye size
bc = 2 + 4 * z1
bl = 2 * bc

#scale
ktot = 500 / pscale * z1
kstep = np.zeros(5)
for k in range(5):
    kstep[k] = (k + 1) * 100 / pscale * z1
ksize = np.array([1, 1, 1, 1, 2]) * (1 + z1)
xsc = 10 * z1
ysc = 246 * z1
msgsc1 = "0.5\""
sc1 = font4.render(msgsc1, True, CYAN)
rct_sc1 = sc1.get_rect()
rct_sc1.center = (xsc + ktot + 2 * z1 + 3, ysc + 5 * z1)
sc2 = font4.render(msgsc1, True, CYAN)
rct_sc2 = sc2.get_rect()
rct_sc2.bottomleft = (5 * z1 - 4, ysc - ktot)

#REACH Photometry parameters
dreachphoto = 64. * z1
xreachphoto = 7.5 * z1
yreachphoto = -11.5 * z1
preachphoto = dreachphoto / 7.
reachphotoc = preachphoto / 2.

#parallactic angles
xcpa = xws - 25 * z1
ycpa = yws - 25 * z1
msgpa1 = "N"
pa1 = font3.render(msgpa1, True, RED)
rct_pa1 = pa1.get_rect()
msgpa2 = "E"
pa2 = font3.render(msgpa2, True, RED)
rct_pa2 = pa2.get_rect()
msgpa3 = "Az"
pa3 = font3.render(msgpa3, True, GREEN)
rct_pa3 = pa3.get_rect()
msgpa4 = "El"
pa4 = font3.render(msgpa4, True, GREEN)
rct_pa4 = pa4.get_rect()

#z1
z2 = 1
iz = 0
zs2 = [1., 2., 4., 8.]
msgzm = "  "
zm = font1.render(msgzm, True, CYAN)
rct_zm = zm.get_rect()
rct_zm.topleft = (5 * z1, 5 * z1)

#ircam_filter
msgwhl = whatfilter(reachphoto, slot, block)
wh = font1.render(msgwhl, True, CYAN)
rct_wh = wh.get_rect()
rct_wh.topright = (xws - 8 * z1, 5 * z1)

#pupil lens
msgtop = whatmsg(pup, reachphoto, gpin, rpin)
topm = font1.render(msgtop, True, CYAN)
rct_top = topm.get_rect()
rct_top.midtop = (xws / 2, 5 * z1)

imin, imax = 0, 0
surf_live = pygame.surface.Surface((xws, yws))
rect1 = surf_live.get_rect()
rect1.topleft = (0, 0)

surf_live2 = pygame.surface.Surface((XW, 100 * z1))
rect2b = surf_live2.get_rect()
rect2b.bottomleft = (0, YW)

rect2 = cartoon1.get_rect()
rect2.bottomright = XW, YW + 10 * z1
screen.blit(cartoon1, rect2)

idt = 0
datatyp = ["OBJECT","DARK","FLAT","SKYFLAT","DOMEFLAT","COMPARISON","TEST"]
ndt = len(datatyp)
for i in range(ndt):
    exec("dtline%d = font1.render(datatyp[i], True, CYAN, BGCOL)" %i)
    exec("dtliner%d = font1.render(datatyp[i], True, RED, BGCOL)" %i)
    exec("rctline%d = dtline%d.get_rect()" %(i,i))
    exec("rctliner%d = dtline%d.get_rect()" %(i,i))
    if i == 0:
        dth = rctline0.h
    exec("rctline%d.center = (XW/2, yws/2+2*(i-(ndt-1)/2)*dth)" %i)
    exec("rctliner%d.center = (XW/2, yws/2+2*(i-(ndt-1)/2)*dth)" %i)
    exec("screen.blit(dtline%d,rctline%d)" %(i,i))

# ------------------------------------------------------------------
# Initialize variables
# ------------------------------------------------------------------
plot_cross = True  # flag for display of the crosses
plot_hotspot = False  # flag for display of the hotspot
plot_history = False  # flag for display of position history
subt_bias = True  # flag for bias subtraction
subt_ref = False  # flag for ref subtraction
lin_scale = True  # flag for linear range
average = False  # flag for averaging
saveim = False  # flag to save images
logexpt = False  # flag to log the exposure time
logndr = False  # flag to log the exposure time
seeing = False
seeing_plot = False
plot_pa = False
clr_scale = 0  # flag for the display color scale
shmreload = 0
keeprpin = False
waitfordt = False

(badpixmap, bias, bpmhere, biashere) = updatebiasbpm()

ref_im = np.zeros_like(bias) * badpixmap

pygame.mouse.set_cursor(*pygame.cursors.broken_x)
pygame.display.update()

cntl = 0
cnta = 0
cnti = 0
timeexpt = []
timendr = []

nhist = 100
ih = 0
coor = np.zeros((2, nhist))
coor2 = np.zeros((2, nhist))

with open(conf_dir + 'hotspots.txt') as file:
    pos = np.array([[float(digit) for digit in line.split()] for line in file])
pos2 = pos[0, :]

# ================================================================================
# ================================================================================
while True:  # the main game loop
    cnti += 1
    clicked = False
    pwr0 = 1.0
    if not lin_scale:
        pwr0 = 0.3

    if clr_scale == 0:
        mycmap = cm.gray
    else:
        if (subt_ref & lin_scale):
            mycmap = cm.seismic
        else:
            if clr_scale == 1:
                mycmap = cm.inferno
            else:
                mycmap = cm.plasma

    # ------------------------------------------------------------------
    # check if camera is paused due to change of window size from other chuckcam
    campaused = int(cam_paused.get_data())
    while campaused:
        print("Chuck is changing size")
        time.sleep(1)
        campaused = int(cam_paused.get_data())
        shmreload = True

    # Save new darks for the current exposure time
    # -------------------------------------
    newdark = int(new_dark.get_data())
    if newdark:
        msg = "  !! Acquiring a dark !!  "
        dinfo2 = font3.render(msg, True, BGCOL, SACOL)
        screen.blit(dinfo2, rct_dinfo2)
        os.system("scexaostatus set darkchuck 'NEW INT DARK    ' 0")
        os.system("log Chuckcam: Saving current internal dark")

        print("In the time it takes Chuck Norris to sidekick a")
        print("red-headed stepchild, we'll acquire this dark.")

        if not block:
            os.system("ircam_block")  # blocking the light
        msgwhl = "     BLOCK      "
        wh = font1.render(msgwhl, True, RED1)
        screen.blit(wh, rct_wh)
        pygame.display.update([rct_dinfo2, rct_wh])
        time.sleep(1.0)  # safety

        ndark = int(10 * fps / float(ndr))  # 10s of dark
        ave_dark = ave_img_data(ndark, clean=False, disp=True, tint=etime)
        bname = conf_dir + "bias%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
                % (fps, etime, ndr, crop[0], crop[2], xsizeim, ysizeim)
        pf.writeto(bname, ave_dark, overwrite=True)

        bpname = conf_dir + "badpixmap%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
                 % (fps, etime, ndr, crop[0], crop[2], xsizeim, ysizeim)
        badpixmap = make_badpix(ave_dark)
        pf.writeto(bpname, badpixmap, overwrite=True)

        bias = ave_dark * badpixmap
        time.sleep(0.2)

        os.system("ircam_block")  # blocking the light
        os.system("scexaostatus set darkchuck 'OFF             ' 1")
        os.system("log Chuckcam: Done saving current internal dark")
        cam_dark.set_data(bias.astype(np.float32))
        cam_badpixmap.set_data(badpixmap.astype(np.float32))
        new_dark.set_data(ONES_NODIM)

    # ------------------------------------------------------------------
    # Relaod shared memory with different size due to change in window size
    if shmreload:
        print("reloading SHM")
        cam = SHM(MILK_SHM_DIR + "/ircam%d.im.shm" % (camid, ), verbose=False)
        xsizeim, ysizeim = cam.shape_c
        #(xsizeim, ysizeim) = cam.mtdata['size'][:2]#size[:cam.naxis]
        print("image xsize=%d, ysize=%d" % (xsizeim, ysizeim))
        os.system("rm %s/ircam%d_*" % (MILK_SHM_DIR, camid, ))
        time.sleep(1)
        cam_dark = open_shm("ircam%d_dark" % (camid, ),
                            dims=(xsizeim, ysizeim),
                            check=True)
        cam_badpixmap = open_shm("ircam%d_badpixmap" % (camid, ),
                                 dims=(xsizeim, ysizeim),
                                 check=True)
        #cam_clean = open_shm("ircam%d_clean" % (camid,), dims=(xsizeim, ysizeim), check=True)
        time.sleep(1)
        tmux("get_tint()", session="ircam%dctrl" % (camid, ))
        time.sleep(1)
        tmux("get_NDR()", session="ircam%dctrl" % (camid, ))
        time.sleep(1)
        tmux("get_fps()", session="ircam%dctrl" % (camid, ))
        time.sleep(1)
        shmreload = False
    else:
        # ------------------------------------------------------------------
        # read changes in expt, fps, ndr and crop
        sync_param = ircam_synchro.get_data().astype(np.int)
        flc_oft = sync_param[4] - lag
        if not sync_param[0] and sync_param[1]:
            etimen = sync_param[2]
            fpsn = sync_param[3]
            delay = cam_ro + flc_oft + 3 * lag
        else:
            try:
                etimen = cam.get_expt() * 1e6
                fpsn = cam.get_fps()
                delay = 0
            except KeyError:
                time.sleep(5.)
                shmreload = True
                continue
        ndrn = int(cam.get_ndr())
        cropn = cam.get_crop().astype(int)
        if gpin:
            cor = cort[:, 0]
        else:
            cor = np.array([0, 0])
        if etimen != etime or fpsn != fps or ndrn != ndr or np.any(
                cropn != crop):
            print("reloading bias and badpixmap")
            (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()
            (fpss2, nfps2, findex) = whatfps(fpsn, cropn)
            (etimes2, net2, tindex) = whatexpt(etimen, fpsn, delay)
            nindex = whatndr(ndrn)
            etime = etimen
            fps = fpsn
            ndr = ndrn
            crop = cropn
            etimet = etime * ndr
            nindex = np.where(ndrs >= ndr)[0][0]
        # ------------------------------------------------------------------
        # read image
        temp, isat = get_img_data(bias, badpixmap, subt_ref, ref_im, lin_scale, check=False)
        # ------------------------------------------------------------------
        # averaging
        if average:
            cnta += 1
            if cnta == 1:
                temp2 = copy.deepcopy(temp)
            else:
                temp2 *= float(cnta - 1) / float(cnta)
                temp2 += temp / float(cnta)
            if seeing:
                #try:
                pf.writeto("seeing.fits", temp2, overwrite=True)
                [cx, cy] = impro.centroid(temp2)
                radc = m.sqrt(np.sum(temp2 > (temp2.max() / 4.)) / m.pi)
                se_param = impro.fit_TwoD_Gaussian(temp2, cy, cx, radc)
                seeing = False
                seeing_plot = True
                se_ystd = se_param.x_stddev.value
                se_xstd = se_param.y_stddev.value
                se_yc = se_param.x_mean.value
                se_xc = se_param.y_mean.value
                se_theta = se_param.theta.value

        else:
            temp2 = copy.deepcopy(temp)
            cnta = 0
        imax = np.max(temp2)
        imin = np.min(temp2)
        (myim, z3, xmin, xmax, ymin, ymax, xshift,
         yshift) = arr2im(temp2,
                          pwr=pwr0,
                          subt_ref=subt_ref,
                          lin_scale=lin_scale,
                          pos=pos2)
        pygame.surfarray.blit_array(surf_live, myim)
        screen.blit(surf_live, rect1)
        if average and seeing_plot:
            msgsee = "x = %.2f as, y = %.2f as, t = %d deg" % (
                se_ystd * pscale / 1000. * 2.355,
                se_xstd * pscale / 1000. * 2.355, np.rad2deg(se_theta))
            msee = font4.render(msgsee, True, CYAN)
            screen.blit(msee, rct_msee)
            cx = (se_xc + 0.5 - xmin + xshift) * z1 * z2 * z3
            cy = (se_yc - ymin + yshift) * z1 * z2 * z3
            stdx = se_xstd * z1 * z2 * z3 * 2.355 / 2.
            stdy = se_ystd * z1 * z2 * z3 * 2.355 / 2.
            pygame.draw.line(
                screen, RED1,
                (cx - stdx * m.cos(se_theta), cy - stdx * m.sin(se_theta)),
                (cx + stdx * m.cos(se_theta), cy + stdx * m.sin(se_theta)), 1)
            pygame.draw.line(
                screen, RED1,
                (cx - stdy * m.sin(se_theta), cy + stdy * m.cos(se_theta)),
                (cx + stdy * m.sin(se_theta), cy - stdy * m.cos(se_theta)), 1)

        # ------------------------------------------------------------------
        # display expt and image information
        msg0 = "x0,y0 = %3d,%3d sx,sy = %3d,%3d" % (crop[0], crop[2], xsizeim,
                                                    ysizeim)
        info0 = font3.render(msg0, True, FGCOL, BGCOL)
        screen.blit(info0, rct_info0)

        if etime < 1e3:
            msg1 = ("t = %f" % (etime))[:8] + (" us FPS = %4d NDR = %3d" %
                                               (fps, ndr))
        elif etime >= 1e3 and etime < 1e6:
            msg1 = ("t = %f" %
                    (etime / 1.e3))[:8] + (" ms FPS = %4d NDR = %3d" %
                                           (fps, ndr))
        else:
            msg1 = ("t = %f" %
                    (etime / 1.e6))[:8] + (" s  FPS = %4d NDR = %3d" %
                                           (fps, ndr))

        info1 = font3.render(msg1, True, FGCOL, BGCOL)
        screen.blit(info1, rct_info1)

        if etimet < 1e3:
            msg2 = ("t = %f" % (etimet))[:8] + (" us min,max = %5d,%5d" %
                                                (imin, imax))
        elif etimet >= 1e3 and etimet < 1e6:
            msg2 = ("t = %f" %
                    (etimet / 1.e3))[:8] + (" ms min,max = %5d,%5d" %
                                            (imin, imax))
        else:
            msg2 = ("t = %f" %
                    (etimet / 1.e6))[:8] + (" s  min,max = %5d,%5d" %
                                            (imin, imax))

        info2 = font3.render(msg2, True, FGCOL, BGCOL)
        rct_info2 = info2.get_rect()
        rct_info2.center = (110 * z1, 315 * z1)
        screen.blit(info2, rct_info2)

        # ------------------------------------------------------------------
        # display the bullseye on the PSF
        if plot_hotspot:
            [cx, cy] = impro.centroid(temp2)
            if (cx >= 0) and (cx < xsizeim) and (cy >= 0) and (cy < ysizeim):
                fh = temp2[int(cy), int(cx)]
                msg3 = "center = %3d,%3d flux = %5d" % (cx, cy, fh)
                info3 = font3.render(msg3, True, FGCOL, BGCOL)
                screen.blit(info3, rct_info3)
            cx = (cx + 0.5 - xmin + xshift) * z1 * z2 * z3
            cy = (cy - ymin + yshift) * z1 * z2 * z3
            pygame.draw.line(screen, RED1, (cx - bl * z2, cy),
                             (cx + bl * z2, cy), 1)
            pygame.draw.line(screen, RED1, (cx, cy - bl * z2),
                             (cx, cy + bl * z2), 1)
            pygame.draw.circle(screen, RED1, (int(cx), int(cy)), int(bc * z2),
                               1)

        # ------------------------------------------------------------------
        # display of position history
        if plot_history:
            [cx, cy] = impro.centroid(temp2)
            try:
                fh = temp2[int(cy), int(cx)]
            except:
                fh = 0
            coor[:, ih] = np.array([cx, cy])
            msg3 = "center = %3d,%3d flux = %5d" % (cx, cy, fh)
            info3 = font3.render(msg3, True, FGCOL, BGCOL)
            screen.blit(info3, rct_info3)
            coor2[0, ih] = (coor[0, ih] + 0.5 - xmin + xshift) * z1 * z2 * z3
            coor2[1, ih] = (coor[1, ih] - ymin + yshift) * z1 * z2 * z3
            for ih2 in range(nhist):
                pygame.draw.line(screen, RED1,
                                 (coor2[0, ih2] - 1, coor2[1, ih2] - 1),
                                 (coor2[0, ih2] + 1, coor2[1, ih2] + 1), 1)
                pygame.draw.line(screen, RED1,
                                 (coor2[0, ih2] + 1, coor2[1, ih2] - 1),
                                 (coor2[0, ih2] - 1, coor2[1, ih2] + 1), 1)
            ih += 1
            ih %= nhist
            stds = np.std(coor, axis=1) * pscale
            cx2 = (np.mean(coor, axis=1)[0] - 320 + crop[0] - pos2[0] -
                   cor[0]) * pscale
            cy2 = -(np.mean(coor, axis=1)[1] - 256 + crop[2] - pos2[1] -
                    cor[1]) * pscale
            msgcoor = "rms = %.1f mas, %.1f mas, %.1f mas" % (
                stds[0], stds[1], m.sqrt(np.sum(stds**2) / 2.))
            mcoor = font4.render(msgcoor, True, CYAN)
            screen.blit(mcoor, rct_mcoor)
            msgcoor2 = "dis = %.1f mas, %.1f mas, %.1f mas" % (
                cx2, cy2, m.sqrt(cx2**2 + cy2**2))
            mcoor2 = font4.render(msgcoor2, True, CYAN)
            screen.blit(mcoor2, rct_mcoor2)

        else:
            # ------------------------------------------------------------------
            # display mouse information
            [xmou, ymou] = pygame.mouse.get_pos()
            xim = int(xmou / z1 / z2 / z3 + xmin - xshift)
            yim = int(ymou / z1 / z2 / z3 + ymin - yshift)
            if not plot_hotspot and not plot_history:
                try:
                    fim = temp2[yim, xim]
                except:
                    fim = 0
                msg3 = " mouse = %3d,%3d flux = %5d" % (xim, yim, fim)
                info3 = font3.render(msg3, True, FGCOL, BGCOL)
                screen.blit(info3, rct_info3)

        # ------------------------------------------------------------------
        # display information
        if not biashere and bpmhere:
            msg = "NO BIAS FOR THIS CONF"
            dinfo = font3.render(msg, True, BGCOL, SACOL)
        elif not bpmhere and biashere:
            msg = "   NO BAD PIX MAP    "
            dinfo = font3.render(msg, True, BGCOL, SACOL)
        elif not bpmhere and not biashere:
            msg = "NO BIAS AND BAD PIX M"
            dinfo = font3.render(msg, True, BGCOL, SACOL)
        else:
            if lin_scale:
                msg = "    linear // "
            else:
                msg = "non-linear // "
            if subt_bias:
                msg += "   bias"
            else:
                msg += "no-bias"
            dinfo = font3.render(msg, True, FGCOL, BGCOL)
        screen.blit(dinfo, rct_dinfo)

        if isat > 12000:
            msg = "     !!!SATURATION!!!     "
            dinfo2 = font3.render(msg, True, BGCOL, SACOL)
            screen.blit(dinfo2, rct_dinfo2)
        elif isat > 10000 and isat <= 12000:
            msg = "     !!!NON-LINEAR!!!     "
            dinfo2 = font3.render(msg, True, SACOL, BGCOL)
            screen.blit(dinfo2, rct_dinfo2)
        else:
            msg = "                          "
            dinfo2 = font3.render(msg, True, SACOL, BGCOL)
            screen.blit(dinfo2, rct_dinfo2)

        # ------------------------------------------------------------------
        # display the scale
        pygame.draw.line(screen, CYAN, (xsc, ysc), (xsc + ktot * z2 * z3, ysc))
        pygame.draw.line(screen, CYAN, (xsc, ysc), (xsc, ysc - ktot * z2 * z3))
        for k in range(5):
            pygame.draw.line(screen, CYAN, (xsc, ysc - kstep[k] * z2 * z3),
                             (xsc + ksize[k], ysc - kstep[k] * z2 * z3))
            pygame.draw.line(screen, CYAN, (xsc + kstep[k] * z2 * z3, ysc),
                             (xsc + kstep[k] * z2 * z3, ysc - ksize[k]))
        rct_sc1.center = (xsc + ktot * z2 * z3 + 2 * z1 + 3, ysc + 5 * z1)
        screen.blit(sc1, rct_sc1)
        rct_sc2.bottomleft = (5 * z1 - 4, ysc - ktot * z2 * z3)
        screen.blit(sc2, rct_sc2)
        screen.blit(zm, rct_zm)
        screen.blit(wh, rct_wh)
        screen.blit(topm, rct_top)

        # ------------------------------------------------------------------
        # display the cross
        if plot_cross:
            if reachphoto:
                #REACH spot positions
                for i in range(8):
                    pygame.draw.circle(screen, GREEN,
                                       (int(xws / 2 + xreachphoto * z2 * z3 +
                                            (i - 3.5) * preachphoto * z2 * z3),
                                        int(yws / 2 + yreachphoto * z2 * z3)),
                                       int(reachphotoc * z2 * z3), 1)
            else:
                if pup:
                    #Pupil cross
                    pos2 = pos[1, :]
                    color = GREEN
                else:
                    #Focus cross
                    pos2 = pos[0, :]
                    color = RED
                ycross = (256 - crop[2] + pos2[1] + cor[1] - ymin +
                          yshift) * z1 * z2 * z3
                xcross = (320 - crop[0] + pos2[0] + cor[0] - xmin +
                          xshift) * z1 * z2 * z3
                pygame.draw.line(screen, color, (0, ycross), (xws, ycross), 1)
                pygame.draw.line(screen, color, (xcross, 0), (xcross, yws), 1)

        if plot_pa:
            pygame.draw.line(screen, RED, (xcpa, ycpa),
                             (xcpa - 20 * z1 * m.cos(m.radians(pad)),
                              ycpa - 20 * z1 * m.sin(m.radians(pad))), 1)
            pygame.draw.line(screen, RED, (xcpa, ycpa),
                             (xcpa - 20 * z1 * m.sin(m.radians(pad)),
                              ycpa + 20 * z1 * m.cos(m.radians(pad))), 1)
            pygame.draw.line(screen, GREEN, (xcpa, ycpa),
                             (xcpa + 20 * z1 * m.cos(m.radians(pap)),
                              ycpa + 20 * z1 * m.sin(m.radians(pap))), 1)
            pygame.draw.line(screen, GREEN, (xcpa, ycpa),
                             (xcpa + 20 * z1 * m.sin(m.radians(pap)),
                              ycpa - 20 * z1 * m.cos(m.radians(pap))), 1)
            rct_pa1.center = (xcpa - 23 * z1 * m.cos(m.radians(pad)),
                              ycpa - 23 * z1 * m.sin(m.radians(pad)))
            rct_pa2.center = (xcpa - 23 * z1 * m.sin(m.radians(pad)),
                              ycpa + 23 * z1 * m.cos(m.radians(pad)))
            rct_pa3.center = (xcpa + 23 * z1 * m.cos(m.radians(pap)),
                              ycpa + 23 * z1 * m.sin(m.radians(pap)))
            rct_pa4.center = (xcpa + 23 * z1 * m.sin(m.radians(pap)),
                              ycpa - 23 * z1 * m.cos(m.radians(pap)))
            screen.blit(pa1, rct_pa1)
            screen.blit(pa2, rct_pa2)
            screen.blit(pa3, rct_pa3)
            screen.blit(pa4, rct_pa4)

        # ------------------------------------------------------------------
        # measure distances
        if pygame.mouse.get_pressed()[0]:
            if (xim >= 0) and (xim < 320) and (yim >= 0) and (yim < 256):
                if cntl == 0:
                    xl1 = xmou
                    yl1 = ymou
                else:
                    pygame.draw.line(screen, RED1, (xl1, yl1), (xmou, ymou))
                    dist = m.sqrt((xmou - xl1)**2 +
                                  (ymou - yl1)**2) * pscale / z1 / z2 / z3
                    msgli = "%.1f mas" % (dist, )
                    mli = font4.render(msgli, True, CYAN)
                    rct_mli = mli.get_rect()
                    if xmou < 246:
                        rct_mli.midleft = (xmou + 5 + 5 * z1, ymou)
                    else:
                        rct_mli.midright = (xmou - 5 - 5 * z1, ymou)
                    screen.blit(mli, rct_mli)
                cntl += 1
        else:
            cntl = 0

        # ------------------------------------------------------------------
        # Menu for the DATA-TYP for archiving
        if waitfordt:
            pygame.draw.rect(screen, BGCOL, (xws/4,yws/2-dth*ndt,xws/2, 2*dth*ndt), 0)
            rctlines = []
            for i in range(ndt):
                if i != idt:
                    exec("screen.blit(dtline%d,rctline%d)" %(i,i))
                    exec("rctlines += [rctline%d]" %i)
                else:
                    exec("screen.blit(dtliner%d,rctliner%d)" %(i,i))
                    exec("rctlines += [rctliner%d]" %i)
                
        # ------------------------------------------------------------------
        # saving images
        tmuxon = os.popen('tmux ls |grep ircam%dlog | awk \'{print $2}\'' %
                          (camid, )).read()
        if tmuxon:
            saveim = True
        else:
            saveim = False
        if cnti % 20:
            rects = [rect2b, rect2, rct, rct2]
        else:
            rects = []
        rects += [
            rect1, rct_info0, rct_info1, rct_info2, rct_info3, rct_zm,
            rct_dinfo, rct_dinfo2, rct_sc1, rct_sc2, rct_wh, rct_top
        ]
        if saveim:
            screen.blit(savem1, rct_savem1)
            screen.blit(savem2, rct_savem2)
            screen.blit(savem3, rct_savem3)
            rects += [rct_savem1, rct_savem2, rct_savem3]
            
        if waitfordt:
            rects += rctlines
            
        if logexpt:
            time.sleep(0.1)
            timeexpt = np.append(timeexpt, time.time())
            time.sleep(0.1)
            if timeexpt[-1] - timeexpt[0] > 4:
                os.system(
                    "/home/scexao/bin/log Chuckcam: changing exposure time to %d"
                    % etime)
                timeexpt = []
                logexpt = False
        if logndr:
            time.sleep(0.1)
            timendr = np.append(timendr, time.time())
            time.sleep(0.1)
            if timendr[-1] - timendr[0] > 4:
                os.system(
                    "/home/scexao/bin/log Chuckcam: changing exposure time to %d"
                    % etime)
                timendr = []
                logndr = False
        if cnti % 20 == 0:
            pup,reachphoto,gpin,rpin,slot,block,pap,pad = RDB_pull(rdb)
            msgwhl = whatfilter(reachphoto, slot, block)
            wh = font1.render(msgwhl, True, CYAN)
            msgtop = whatmsg(pup, reachphoto, gpin, rpin)
            topm = font1.render(msgtop, True, CYAN)

    # =====================================================================
    # KEYBOARD CONTROLS
    # =====================================================================
    for event in pygame.event.get():

        # exit ChuckCam
        #------------------------------------------------------------------
        if event.type == QUIT:
            pygame.quit()

            cam.close()
            cam_dark.close()
            cam_badpixmap.close()
            #cam_clean.close()
            new_dark.close()
            print("Chuckcam has ended normally.")
            sys.exit()
        elif event.type == KEYDOWN:

            if event.key == K_ESCAPE:
                pygame.quit()
                cam.close()
                cam_dark.close()
                cam_badpixmap.close()
                #cam_clean.close()
                new_dark.close()
                print("Chuckcam has ended normally.")
                sys.exit()

            # CAMERA CONTROLS
            #--------------------------------------------------------------

            # Increase exposure time/NDR
            #---------------------------
            if event.key == K_q:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (nindex < nndr - 1):
                        nindex += 1
                        ndrc = ndrs[nindex]
                        tmux("set_NDR(%d)" % (ndrc, ),
                             session="ircam%dctrl" % (camid, ))
                        time.sleep(1)
                        ndr = cam.get_ndr()
                        etimet = etime * ndr
                        nindex = whatndr(ndr)
                        logndr = True
                else:
                    if (tindex < net2 - 1):
                        tindex += 1
                        etimec = etimes2[tindex]
                        sync_param = ircam_synchro.get_data().astype(np.int)
                        if not sync_param[0] and sync_param[1]:
                            sync_param[2] = etimec
                            sync_param[0] = 1
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                            time.sleep(1)
                            sync_param = ircam_synchro.get_data().astype(
                                np.int)
                            etime = sync_param[2]
                            flc_oft = sync_param[4] - lag
                            delay = cam_ro + flc_oft + 3 * lag
                        else:
                            tmux("set_tint(%f)" % (etimec * 1.e-6, ),
                                 session="ircam%dctrl" % (camid, ))
                            time.sleep(1)
                            etime = cam.get_expt() * 1e6
                            delay = 0
                        etimet = etime * ndr
                        (etimes2, net2, tindex) = whatexpt(etime, fps, delay)
                        logexpt = True
                (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()

            # Decrease exposure time/NDR
            #---------------------------
            if event.key == K_a:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (nindex > 0):
                        nindex -= 1
                        ndrc = ndrs[nindex]
                        tmux("set_NDR(%d)" % (ndrc, ),
                             session="ircam%dctrl" % (camid, ))
                        time.sleep(1)
                        ndr = cam.get_ndr()
                        etimet = etime * ndr
                        nindex = whatndr(ndr)
                        logndr = True
                else:
                    if (tindex > 0):
                        tindex -= 1
                        etimec = etimes2[tindex]
                        sync_param = ircam_synchro.get_data().astype(np.int)
                        if not sync_param[0] and sync_param[1]:
                            sync_param[2] = etimec
                            sync_param[0] = 1
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                            time.sleep(1)
                            sync_param = ircam_synchro.get_data().astype(
                                np.int)
                            etime = sync_param[2]
                            flc_oft = sync_param[4] - lag
                            delay = cam_ro + flc_oft + 3 * lag
                        else:
                            tmux("set_tint(%f)" % (etimec * 1.e-6, ),
                                 session="ircam%dctrl" % (camid, ))
                            time.sleep(1)
                            etime = cam.get_expt() * 1e6
                            delay = 0
                        etimet = etime * ndr
                        (etimes2, net2, tindex) = whatexpt(etime, fps, delay)
                        logexpt = True
                (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()

            # Increase frame rate/display target on PSF
            #---------------------------
            if event.key == K_o:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (findex < nfps2 - 1):
                        findex += 1
                        fpsc = fpss2[findex]
                        sync_param = ircam_synchro.get_data().astype(np.int)
                        if not sync_param[0] and sync_param[1]:
                            sync_param[3] = fpsc
                            sync_param[0] = 1
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                            time.sleep(1)
                            sync_param = ircam_synchro.get_data().astype(
                                np.int)
                            fps = sync_param[3]
                            etime = sync_param[2]
                            flc_oft = sync_param[4] - lag
                            delay = cam_ro + flc_oft + 3 * lag
                        else:
                            tmux("set_fps(%f)" % (fpsc, ),
                                 session="ircam%dctrl" % (camid, ))
                            time.sleep(1)
                            fps = cam.get_fps()
                            tmux("get_tint()",
                                 session="ircam%dctrl" % (camid, ))
                            time.sleep(1)
                            etime = cam.get_expt() * 1e6
                            delay = 0
                        (etimes2, net2, tindex) = whatexpt(etime, fps, delay)
                        (fpss2, nfps2, findex) = whatfps(fps, crop)
                        logfps = True
                        (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()

                else:
                    plot_hotspot = not plot_hotspot

            # Decrease frame rate/linear-log scale
            #---------------------------
            if event.key == K_l:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (findex > 0):
                        findex -= 1
                        fpsc = fpss2[findex]
                        sync_param = ircam_synchro.get_data().astype(np.int)
                        if not sync_param[0] and sync_param[1]:
                            sync_param[3] = fpsc
                            sync_param[0] = 1
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                            time.sleep(1)
                            sync_param = ircam_synchro.get_data().astype(
                                np.int)
                            fps = sync_param[3]
                            etime = sync_param[2]
                            flc_oft = sync_param[4] - lag
                            delay = cam_ro + flc_oft + 3 * lag
                        else:
                            tmux("set_fps(%f)" % (fpsc, ),
                                 session="ircam%dctrl" % (camid, ))
                            time.sleep(1)
                            fps = cam.get_fps()
                            tmux("get_tint()",
                                 session="ircam%dctrl" % (camid, ))
                            time.sleep(1)
                            etime = cam.get_expt() * 1e6
                            delay = 0
                        (etimes2, net2, tindex) = whatexpt(etime, fps, delay)
                        (fpss2, nfps2, findex) = whatfps(fps, crop)
                        logfps = True
                        (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()

                else:
                    lin_scale = not lin_scale

            # hotspotalign/display help
            #--------------------------
            if event.key == K_h:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    tmux("hotspotalign")
                else:
                    print(hmsg)

            # Camera to Pupil/Focus//Display of parallactic angle
            #----------------------
            if event.key == K_p:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if pup:
                        tmux("chuck_pup")
                        if reachphoto:
                            tmux("chuck_pup_fcs pupil &")
                            tmux("reach_pickoff out &")
                            tmux("buffy_pickoff out &")
                        tmux("ircam_fcs chuck")
                    else:
                        lin_scale = True
                        tmux("chuck_pup")
                        tmux("chuck_pup_fcs pupil &")
                        tmux("ircam_fcs chuck_pup")
                else:
                    plot_pa = not plot_pa

            # Save new darks for one/all exposure times
            # -----------------------------------------
            if event.key == K_b:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LSHIFT):
                        # Save new darks for the current exposure time
                        # -------------------------------------
                        msg = "  !! Acquiring a dark !!  "
                        dinfo2 = font3.render(msg, True, BGCOL, SACOL)
                        screen.blit(dinfo2, rct_dinfo2)
                        os.system(
                            "scexaostatus set darkchuck 'NEW INT DARK    ' 0")
                        os.system("log Chuckcam: Saving current internal dark")

                        print(
                            "In the time it takes Chuck Norris to sidekick a")
                        print("red-headed stepchild, we'll acquire this dark.")
                        if not reachphoto:
                            if not block:
                                os.system("ircam_block")  # blocking the light
                        else:
                            os.system("PG1_pickoff")
                        msgwhl = "     BLOCK      "
                        wh = font1.render(msgwhl, True, RED1)
                        screen.blit(wh, rct_wh)
                        pygame.display.update([rct_dinfo2, rct_wh])
                        time.sleep(1.0)  # safety

                        ndark = int(10 * fps / float(ndr))  # 10s of dark
                        ave_dark = ave_img_data(ndark,
                                                clean=False,
                                                disp=True,
                                                tint=etime)
                        bname = conf_dir + "bias%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
                                % (fps, etime, ndr, crop[0], crop[2], xsizeim, ysizeim)
                        pf.writeto(bname, ave_dark, overwrite=True)

                        bpname = conf_dir + "badpixmap%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
                                % (fps, etime, ndr, crop[0], crop[2], xsizeim, ysizeim)
                        badpixmap = make_badpix(ave_dark)
                        pf.writeto(bpname, badpixmap, overwrite=True)

                        bias = ave_dark * badpixmap
                        time.sleep(0.2)
                        if not reachphoto:
                            os.system("ircam_block")  # blocking the light
                        else:
                            os.system("PG1_pickoff")
                        os.system(
                            "scexaostatus set darkchuck 'OFF             ' 1")
                        os.system(
                            "log Chuckcam: Done saving current internal dark")
                        cam_dark.set_data(bias.astype(np.float32))
                        cam_badpixmap.set_data(badpixmap.astype(np.float32))

                    else:
                        # Save new darks for all exposure times
                        # -------------------------------------
                        msg = "  !! Acquiring darks !!   "
                        dinfo2 = font3.render(msg, True, BGCOL, SACOL)
                        screen.blit(dinfo2, rct_dinfo2)
                        os.system(
                            "scexaostatus set darkchuck 'ALL INT DARKS   ' 0")
                        os.system("log Chuckcam: Saving internal darks")

                        print(
                            "In the time it takes Chuck Norris to sidekick a")
                        print(
                            "red-headed stepchild, we'll acquire all biases.")
                        if not reachphoto:
                            if not block:
                                os.system("ircam_block")  # blocking the light
                        else:
                            os.system("PG1_pickoff")
                        msgwhl = "     BLOCK      "
                        wh = font1.render(msgwhl, True, RED1)
                        screen.blit(wh, rct_wh)
                        pygame.display.update([rct_dinfo2, rct_wh])
                        time.sleep(1.0)  # safety

                        sync_param = ircam_synchro.get_data().astype(np.int)
                        for tint in etimes2:
                            if not sync_param[0] and sync_param[1]:
                                sync_param[2] = tint
                                fps = sync_param[3]
                                sync_param[0] = 1
                                ircam_synchro.set_data(
                                    sync_param.astype(np.float32))
                                time.sleep(1)
                                sync_param = ircam_synchro.get_data().astype(
                                    np.int)
                                tint = sync_param[2]
                            else:
                                tmux("set_tint(%f)" % (tint * 1.e-6, ),
                                     session="ircam%dctrl" % (camid, ))
                                time.sleep(1)
                                tint = cam.get_expt() * 1e6
                            ndark = int(1 * fps /
                                        float(ndr))  # 1s of dark per exposure
                            ave_dark = ave_img_data(ndark,
                                                    clean=False,
                                                    disp=True,
                                                    tint=tint)
                            bname = conf_dir + "bias%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
                                    % (fps, tint, ndr, crop[0], crop[2], xsizeim, ysizeim)
                            pf.writeto(bname, ave_dark, overwrite=True)
                            bpname = conf_dir + "badpixmap%04d_%06d_%03d_%03d_%03d_%03d_%03d.fits" \
                                % (fps, tint, ndr, crop[0], crop[2], xsizeim, ysizeim)
                            badpixmapi = make_badpix(ave_dark)
                            pf.writeto(bpname, badpixmapi, overwrite=True)

                            time.sleep(0.2)
                        print(
                            "\nChuck sidekicked the crap out of the poor kid.")
                        if not reachphoto:
                            os.system("ircam_block")  # opening the shutter
                        else:
                            os.system("PG1_pickoff")
                        os.system(
                            "scexaostatus set darkchuck 'OFF             ' 1")
                        os.system("log Chuckcam: Done saving internal darks")

                        if not sync_param[0] and sync_param[1]:
                            sync_param[2] = tint
                            sync_param[0] = 1
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                        else:
                            tmux("set_tint(%f)" % (tint * 1.e-6, ),
                                 session="ircam%dctrl" % (camid, ))
                        biashere = True
                        bpmhere = True

            # Save a reference image/subtract the reference image
            # ---------------------------------------------------
            if event.key == K_r:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    msg = "!! Acquiring reference !! "
                    dinfo2 = font3.render(msg, True, BGCOL, SACOL)
                    screen.blit(dinfo2, rct_dinfo2)
                    pygame.display.update([rct_dinfo2])

                    subt_ref = False

                    nref = int(5 * fps / float(ndr))  # 5s of ref
                    ave_ref = ave_img_data(nref,
                                           bias=bias,
                                           badpixmap=badpixmap,
                                           disp=True,
                                           tint=etime)
                    rname = conf_dir + "ref.fits"
                    pf.writeto(rname, ave_ref, overwrite=True)

                else:
                    rname = conf_dir + "ref.fits"
                    try:
                        ref_im = pf.getdata(rname) * badpixmap
                    except:
                        ref_im = np.zeros((ysizeim, xsizeim))
                    if ref_im.shape[1] != xsizeim or ref_im.shape[0] != ysizeim:
                        ref_im = np.zeros((ysizeim, xsizeim))
                    subt_ref = not subt_ref

            # Start/stop logging images
            #--------------------------
            if event.key == K_s:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    saveim = not saveim
                    if saveim:
                        timestamp = dt.datetime.utcnow().strftime('%Y%m%d')
                        if (mmods & KMOD_LSHIFT):
                            waitfordt = True
                        else:
                            savepath = '/media/data/' + timestamp + \
                                '/ircam%dlog/' % (camid, )
                            ospath = os.path.dirname(savepath)
                            if not os.path.exists(ospath):
                                os.makedirs(ospath)
                            nimsave = int(min(10000, (50000000 / etimet)))
                            # creating a tmux session for logging
                            os.system("tmux new-session -d -s ircam%dlog" %
                                      (camid, ))
                            tmux("logshim ircam%d %i %s" %
                                 (camid, nimsave, savepath),
                                 session="ircam%dlog" % (camid, ))
                            os.system("log Chuckcam: start logging images")
                            os.system(
                                "scexaostatus set logchuck 'LOGGING         ' 3")

                    else:
                        tmux("logshimkill", session="ircam%dlog" % (camid, ))
                        tmux("",
                             session="ircam%dlog" % (camid, ),
                             command="kill-session")
                        os.system("log Chuckcam: stop logging images")
                        os.system(
                            "scexaostatus set logchuck 'OFF             ' 1")
            
            # Start archiving images
            #--------------------------
            if event.key == K_RETURN and waitfordt:
                cam.update_keyword("DATA-TYP",datatyp[idt])
                timestamp = dt.datetime.utcnow().strftime('%Y%m%d')
                savepath = '/media/data/ARCHIVED_DATA/' + timestamp + \
                           '/ircam%dlog/' % (camid, )
                waitfordt = False
                ospath = os.path.dirname(savepath)
                if not os.path.exists(ospath):
                    os.makedirs(ospath)
                nimsave = int(min(20000, (50000000 / etimet)))
                # creating a tmux session for logging
                os.system("tmux new-session -d -s ircam%dlog" %
                          (camid, ))
                tmux("logshim ircam%d %i %s" %
                     (camid, nimsave, savepath),
                     session="ircam%dlog" % (camid, ))
                os.system("log Chuckcam: start archiving images")
                os.system(
                    "scexaostatus set logchuck 'ARCHIVING       ' 3")

            # Save an HDR image/Subtract dark
            #--------------------------------
            if event.key == K_d:
                mmods = pygame.key.get_mods()

                if (mmods & KMOD_LCTRL):
                    # increase exposure time if max flux is too low
                    #print imax, isat, tindex
                    while ((imax < 4000) & (tindex < net2 - 1)):
                        tindex += 1
                        etime = etimes2[tindex]
                        cam_cmd("tint %d %d" % (camid, etime), False)
                        (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()
                        logexpt = True
                        time.sleep(2)
                        temp, isat = get_img_data(bias, badpixmap)
                        temp *= badpixmap
                        isat = np.percentile(temp[1:-1, 1:-1], 99.995)
                        temp -= bias
                        imax = np.max(temp)
                        #print imax, isat, tindex
                    # decrease exposure time if saturating or non-linear
                    while ((isat > 11000) & (tindex > 0)):
                        tindex -= 1
                        etime = etimes2[tindex]
                        cam_cmd("tint %d %d" % (camid, etime), False)
                        (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()
                        logexpt = True
                        time.sleep(2)
                        temp, isat = get_img_data(bias, badpixmap)
                        temp *= badpixmap
                        isat = np.percentile(temp[1:-1, 1:-1], 99.995)
                        temp -= bias
                        imax = np.max(temp)
                        #print imax, isat, tindex

                    etimetmp = etime
                    v1 = 100
                    v2 = 11000
                    mask2 = (v1 < temp) * (temp < v2)
                    hdim = np.zeros(temp.shape)
                    hdim[:, :] = temp[:, :]
                    hdim[temp < v1] = 0.0
                    #starting HDR!
                    for k in range(11):
                        if (tindex < net2 - 1):
                            temp2 = copy.deepcopy(temp)
                            etime2 = copy.deepcopy(etime)
                            tindex += 1
                            etime = etimes2[tindex]
                            cam_cmd("tint %d %d" % (camid, etime), False)
                            (badpixmap, bias, bpmhere,
                             biashere) = updatebiasbpm()
                            logexpt = True
                            time.sleep(2)
                            temp, isat = get_img_data(bias, badpixmap)
                            temp *= badpixmap
                            temp -= bias
                            mask1 = copy.deepcopy(mask2)
                            mask2 = (v1 < temp) * (temp < v2)
                            mask = mask1 * mask2
                            coeff = etime / float(
                                etime2)  #(temp/temp2)[mask].mean()
                            #print coeff, etime/float(etime2)
                            hdim *= coeff
                            hdim += temp
                            hdim /= 2.0
                            hdim[temp < v1] = 0.0

                    timestamp = dt.datetime.utcnow().strftime('%Y%m%d')
                    timestamp2 = dt.datetime.utcnow().strftime('%H:%M:%S.%f')
                    savepath = '/media/data/' + timestamp + '/ircam%dlog/' % (
                        camid, )
                    pf.writeto(savepath + 'ircam%d_hdr_' % (camid, ) +
                               timestamp2 + '.fits',
                               hdim / hdim.max(),
                               overwrite=True)
                    cam_cmd("tint %d %d" % (camid, etimetmp), False)

                else:
                    subt_bias = not subt_bias
                    (badpixmap, bias, bpmhere, biashere) = updatebiasbpm()
                    if not subt_bias:
                        bias = np.zeros_like(temp)

            # Display hotspot crosses
            #------------------------
            if event.key == K_c:
                plot_cross = not plot_cross
                if plot_cross:
                    with open(conf_dir + 'hotspots.txt') as file:
                        pos = np.array(
                            [[float(digit) for digit in line.split()]
                             for line in file])
                    pos2 = pos[0, :]

            # Color/grayscale map
            #--------------------
            if event.key == K_m:
                clr_scale += 1
                clr_scale %= 3

            # Display history of position/REACH mode
            #-------------------------------------
            if event.key == K_i:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LSHIFT):
                        if rpin:
                            tmux("reach_pickoff out &")
                            tmux("oap4 onaxis &")
                            tmux("steering onaxis &")
                            keeprpin = False
                        else:
                            tmux("reach_pickoff in &")
                            tmux("oap4 reach &")
                            tmux("steering reach &")
                            keeprpin = True
                    else:
                        if reachphoto:
                            tmux("chuck_pup")
                            tmux("chuck_pup_fcs pupil &")
                            tmux("buffy_pickoff out &")
                            if not keeprpin:
                                tmux("reach_pickoff out &")
                                tmux("oap4 onaxis &")
                                tmux("steering onaxis &")
                        else:
                            if not pup:
                                tmux("chuck_pup")
                            tmux("chuck_pup_fcs reach &")
                            tmux("buffy_pickoff in &")
                            if not rpin:
                                tmux("reach_pickoff in &")
                                tmux("oap4 reach &")
                                tmux("steering reach &")
                else:
                    plot_history = not plot_history

            # Start/stop accumulating frames
            #-------------------------------
            if event.key == K_v:
                average = not average
                seeing_plot = False

            # Start/stop seeing measurement
            #------------------------------
            if event.key == K_g:
                if average:
                    seeing = True
                else:
                    seeing = False

            # Zoom/unzoom
            #------------
            if event.key == K_z:
                iz += 1
                iz %= 4
                z2 = zs2[iz]
                if z2 != 1:
                    msgzm = "x%d" % (z2, )
                else:
                    msgzm = "  "
                zm = font1.render(msgzm, True, CYAN)

            # Ext trig
            #---------------------
            if event.key == K_n:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LALT):
                        sync_param = ircam_synchro.get_data().astype(np.int)
                        if not sync_param[0] and not sync_param[1]:
                            sync_param[2] = etime
                            sync_param[3] = fps
                            sync_param[0] = 1
                            sync_param[1] = 1
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                            time.sleep(1)
                        else:
                            sync_param[0] = 1
                            sync_param[1] = 0
                            ircam_synchro.set_data(
                                sync_param.astype(np.float32))
                            time.sleep(1)

            # Crop modes and full frame
            #---------------------
            CROP_KEYLIST = [
                K_0, K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8, K_9, K_MINUS,
                K_EQUALS, K_f
            ]
            if event.key in CROP_KEYLIST:
                what_key = CROP_KEYLIST.index(event.key)
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL) and (mmods & KMOD_LALT):
                    # Index 12 == Ctrl+alt+f == full
                    mode_id = (str(what_key), "FULL")[event.key == K_f]
                    if event.key == K_f and xsizeim == 640 and ysizeim == 512:
                        # Skip full frame if full frame already
                        print('Camera already in full frame - skipping set_camera_mode()')
                    else:
                        cam_paused.set_data(ONES_NODIM)
                        tmux("set_camera_mode(%s)" % mode_id,
                            session="ircam%dctrl" % (camid, ))
                        time.sleep(12)
                        cam_paused.set_data(ZERO_NODIM)
                        shmreload = True

            # Ircam Filter/block
            #------------------------------

            FILT_KEYLIST = [K_1, K_2, K_3, K_4, K_5, K_6, K_7]
            if event.key in FILT_KEYLIST:
                what_key = FILT_KEYLIST.index(event.key)
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL) and not (
                        mmods & KMOD_LALT):  # Ctrl but no alt, filter set
                    if what_key == 6:
                        os.system('ircam_block')
                    else:
                        os.system('ircam_filter %d' % (what_key+1,))

            # DM stage/select DATA-TYP for archiving
            #-----------------------------------------
            if event.key == K_UP:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LSHIFT):
                        tmux("dm_stage y push -100")
                    else:
                        tmux("dm_stage y push -20")
                else:
                    if waitfordt:
                        idt -= 1
                        idt %= ndt

            if event.key == K_DOWN:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LSHIFT):
                        tmux("dm_stage y push +100")
                    else:
                        tmux("dm_stage y push +20")
                else:
                    if waitfordt:
                        idt += 1
                        idt %= ndt

            if event.key == K_LEFT:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LSHIFT):
                        tmux("dm_stage x push -100")
                    else:
                        tmux("dm_stage x push -20")

            if event.key == K_RIGHT:
                mmods = pygame.key.get_mods()
                if (mmods & KMOD_LCTRL):
                    if (mmods & KMOD_LSHIFT):
                        tmux("dm_stage x push +100")
                    else:
                        tmux("dm_stage x push +20")

    pygame.display.update(rects)

    fpsClock.tick(FPSdisp)

pygame.quit()
sys.exit()
