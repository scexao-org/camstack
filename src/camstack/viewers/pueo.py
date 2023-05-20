#!/usr/bin/env python

# ------------------------ #
#    ___                   #
#   / _ \_   _  ___  ___   #
#  / /_)/ | | |/ _ \/ _ \  #
# / ___/| |_| |  __/ (_) | #
# \/     \__,_|\___|\___/  #
#                          #
# ------------------------ #

import os

_CORES = os.sched_getaffinity(0)  # Go around pygame import

import pygame, sys
from pygame.locals import *

# Pygame import (on AMD Epyc) make affinity drop to CPU 0 only !
os.sched_setaffinity(0, _CORES)  # Fix the CPU affinity

import numpy as np
import matplotlib.cm as cm
import struct
from PIL import Image
import time
import math as m
import copy
import datetime as dt
from astropy.io import fits as pf
from pyMilk.interfacing.isio_shmlib import SHM
import camstack.viewers.viewer_common as cvc

MILK_SHM_DIR = os.environ['MILK_SHM_DIR']
home = os.getenv('HOME')

hmsg = """PUEO's INSTRUCTIONS
-------------------

camera controls:
---------------
SPACE  : start/stop data stream
CTRL+b : take new darks

display controls:
----------------
d      : subtract dark for display
c      : display cross
m      : color/gray color-map
f      : display flux mismatch
v      : start/stop accumulating and averaging frames
r      : subtract a reference image
CTRL+r : save the reference
CTRL+s : start/stop logging images

other controls:
---------------
CTRL+ARROW  : steer mod. piezo offset (0.1V)
CTRL+SHIFT+ARROW  : steer mod. piezo offset (0.5V)

mouse controls:
--------------
mouse      : display of the flux under the mouse pointer

ESC   : quit pueo

"""

def main():
    args = sys.argv[1:]
    zoom = 2  # zoom for the display (default is 2)
    if args != []:
        if isinstance(int(args[0]), int):
            zoom = int(args[0]) + 1
            zoom = min(4, max(2, zoom))

    # pygame fps 1-20 - only used at very end of file
    FPS = 10
    if len(args) >= 2:
        if isinstance(int(args[1]), int):
            FPS = max(1., min(20., int(args[1])))

    # Redis DB
    rdb, rdb_alive = cvc.locate_redis_db()

    # ------------------------------------------------------------------
    #                access to shared memory structures
    # ------------------------------------------------------------------
    cam = SHM("ocam2d", verbose=False)
    bias_shm = SHM('aol0_wfsdark')

    # ------------------------------------------------------------------
    #                       global variables
    # ------------------------------------------------------------------

    mycmap = cm.gray
    (xsize, ysize) = (120, 120)  #cam.size[:cam.naxis]

    # -----------------------
    #   set up the window
    # -----------------------

    #FPS = 10                        # frames per second setting # set by argument at top
    fpsClock = pygame.time.Clock()  # start the pygame clock!

    pygame.display.init()
    pygame.font.init()

    XW, YW = xsize * zoom, (ysize + 50) * zoom

    screen = pygame.display.set_mode((XW, YW), 0, 32)
    pygame.display.set_caption('PUEO camera display!')

    #os.system("tmux new-session -d -s ocam2k") #start a tmux session for messsages


    # ------------------------------------------------------------------
    #             short hands for shared memory data access
    # ------------------------------------------------------------------
    def get_img_data(check=False):
        ''' ----------------------------------------
        Return the current image data content,
        formatted as a 2D numpy array.
        Reads from the already-opened shared memory
        data structure.
        ---------------------------------------- '''
        return (cam.get_data(check, True).astype(float))


    # ------------------------------------------------------------------
    #  another short hand to convert numpy array into image for display
    # ------------------------------------------------------------------
    def arr2im(arr, vmin=0., vmax=10000.0, pwr=1.0):

        arr2 = arr.astype('float')**pwr

        mmin, mmax = arr2.min(), arr2.max()
        arr2 -= mmin
        if mmin < mmax:
            arr2 /= (mmax - mmin)

        if zoom != 1:
            img = Image.fromarray(arr2)
            rimg = img.resize((zoom * ysize, zoom * xsize), resample=Image.NEAREST)
            rarr = np.asarray(rimg)
            test = mycmap(rarr)
        else:
            test = mycmap(arr2)
        return ((255 * test[:, :, :3]).astype('int'))


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

    # ----------------------------
    #          labels
    # ----------------------------

    font1 = pygame.font.SysFont("default", 8 * zoom)
    font2 = pygame.font.SysFont("default", 5 * zoom)
    font3 = pygame.font.SysFont("monospace", 4 * zoom)
    font5 = pygame.font.SysFont("monospace", 4 * zoom)
    font5.set_bold(True)

    path_cartoon = "/home/scexao/conf/pueo_aux/Pueo%d.png" % (zoom, )
    cartoon1 = pygame.image.load(path_cartoon).convert_alpha()

    lbl = font1.render("PUEO camera viewer", True, WHITE, BGCOL)
    rct = lbl.get_rect()
    rct.center = (45 * zoom, 125 * zoom)
    screen.blit(lbl, rct)

    lbl2 = font1.render("Press [h] for help", True, WHITE, BGCOL)
    rct2 = lbl2.get_rect()
    rct2.center = (45 * zoom, 132 * zoom)
    screen.blit(lbl2, rct2)

    lbl3 = font2.render("Meha ke kula, 'a'ohe ke'u pueo.", True, WHITE, BGCOL)
    rct3 = lbl3.get_rect()
    rct3.center = (45 * zoom, 140 * zoom)
    screen.blit(lbl3, rct3)

    imin, imax = 0, 0
    msg = "(min,max) = (%5d,%5d)" % (imin, imax)
    info = font3.render(msg, True, FGCOL, BGCOL)
    rct_info = info.get_rect()
    rct_info.center = (45 * zoom, 145 * zoom)

    xmou, ymou, fmou = 0, 0, 0
    msg2 = " mouse = (%3d,%3d), flux = %5d" % (xmou, ymou, fmou)
    info2 = font3.render(msg2, True, FGCOL, BGCOL)
    rct_info2 = info2.get_rect()
    rct_info2.center = (45 * zoom, 150 * zoom)

    dinfo = font3.render("       ", True, FGCOL, BGCOL)
    rct_dinfo = dinfo.get_rect()
    rct_dinfo.center = (45 * zoom, 155 * zoom)
    screen.blit(dinfo, rct_dinfo)

    dinfo2 = font3.render("                          ", True, FGCOL, BGCOL)
    rct_dinfo2 = dinfo2.get_rect()
    rct_dinfo2.center = (45 * zoom, 160 * zoom)
    screen.blit(dinfo2, rct_dinfo2)

    xws = xsize * zoom
    yws = ysize * zoom

    msgsave1 = "saving images"
    savem1 = font5.render(msgsave1, True, RED1)
    rct_savem1 = savem1.get_rect()
    rct_savem1.bottomright = (xws - 10 * zoom, yws)

    cx = xsize / 2.
    cy = ysize / 2.

    imin, imax = 0, 0
    surf_live = pygame.surface.Surface((xws, yws))

    rect1 = surf_live.get_rect()
    rect1.topleft = (0, 0)

    surf_live2 = pygame.surface.Surface((XW, 50 * zoom))
    rect2b = surf_live2.get_rect()
    rect2b.bottomleft = (0, YW)

    rect2 = cartoon1.get_rect()
    rect2.bottomright = XW, YW
    screen.blit(cartoon1, rect2)
    # End blit stuff func

    plot_cross = False  # flag for display of the hotspot
    subt_bias = False  # flag for bias subtraction
    subt_ref = False  # flag for ref subtraction
    cont_acq = False
    clr_scale = False  # flag for the display color scale
    average = False  # flag for averaging
    saveim = False  # flag to save images
    flux_calc = False  # flag for flux mismatch

    bias = np.zeros((ysize, xsize))
    ref_im = np.zeros((ysize, xsize))

    pygame.mouse.set_cursor(*pygame.cursors.broken_x)
    pygame.display.update()

    cnta = 0
    cnti = 0
    timeexpt = []

    # =======================================================
    # =======================================================
    while True:  # the main game loop
        cnti += 1
        clicked = False

        mycmap = cm.gray
        if clr_scale:
            mycmap = cm.inferno

        # read image
        temp = get_img_data()
        #temp = np.squeeze(np.mean(temp, axis=0))
        isat = np.percentile(temp, 99.995)
        if subt_bias:
            temp -= bias
        if average == True:
            cnta += 1
            if cnta == 1:
                temp2 = copy.deepcopy(temp)
            else:
                temp2 *= float(cnta) / float(cnta + 1)
                temp2 += temp / float(cnta + 1)
        else:
            temp2 = copy.deepcopy(temp)
            cnta = 0
        if flux_calc == True:
            flux1 = np.sum(temp2[:60, :60])
            flux2 = np.sum(temp2[:60, 60:])
            flux3 = np.sum(temp2[60:, :60])
            flux4 = np.sum(temp2[60:, 60:])
            flux14 = flux1 + flux4
            flux23 = flux2 + flux3
            fluxtot = flux14 + flux23
            diff14 = (flux4 - flux1) / flux14
            diff23 = (flux3 - flux2) / flux23
            diffx = (flux4 + flux2 - flux1 - flux3) / fluxtot
            diffy = (flux3 + flux4 - flux2 - flux1) / fluxtot
            diffr = m.sqrt(diffx**2 + diffy**2)
            #print diff14, diff23, diffx, diffy
            diff14b = m.copysign(
                    m.pow(abs(diff14), 0.5) * 30 * zoom * m.sqrt(2), diff14)
            diff23b = m.copysign(
                    m.pow(abs(diff23), 0.5) * 30 * zoom * m.sqrt(2), diff23)
            diffxb = m.pow(abs(diffr), 0.5) * 30 * zoom * m.sqrt(2) * diffx / diffr
            diffyb = m.pow(abs(diffy), 0.5) * 30 * zoom * m.sqrt(2) * diffy / diffr

        imax = np.max(temp2)
        imin = np.percentile(temp2, 0.5)
        temp2b = temp2 - imin
        temp2b *= temp2b > 0
        if subt_ref:
            if subt_bias:
                myim = arr2im((temp2b - ref_im + bias).transpose())
            else:
                myim = arr2im((temp2b - ref_im).transpose())
        else:
            myim = arr2im(temp2b.transpose())
        pygame.surfarray.blit_array(surf_live, myim)
        screen.blit(surf_live, rect1)

        msg = "(min,max) = (%5d,%5d)" % (imin, imax)
        info = font3.render(msg, True, FGCOL, BGCOL)
        screen.blit(info, rct_info)

        # display mouse information
        [xmou, ymou] = pygame.mouse.get_pos()
        xim = xmou // zoom
        yim = ymou // zoom
        if (xim >= 0) and (xim < xsize) and (yim >= 0) and (yim < ysize):
            fim = temp2[yim, xim]
            msg2 = " mouse = (%3d,%3d), flux = %5d" % (xim, yim, fim)
            info2 = font3.render(msg2, True, FGCOL, BGCOL)
            screen.blit(info2, rct_info2)

        # display information
        if subt_bias:
            msg = " bias  "
        else:
            msg = "no-bias"
        dinfo = font3.render(msg, True, FGCOL, BGCOL)
        screen.blit(dinfo, rct_dinfo)

        if isat > 15000:
            msg = "     !!!SATURATION!!!     "
            dinfo2 = font3.render(msg, True, BGCOL, SACOL)
            screen.blit(dinfo2, rct_dinfo2)
        elif isat > 11000 and isat <= 15000:
            msg = "     !!!NON-LINEAR!!!     "
            dinfo2 = font3.render(msg, True, SACOL, BGCOL)
            screen.blit(dinfo2, rct_dinfo2)
        else:
            msg = "                          "
            dinfo2 = font3.render(msg, True, SACOL, BGCOL)
            screen.blit(dinfo2, rct_dinfo2)

        # display the cross
        if plot_cross:
            pygame.draw.line(screen, RED, (0, yws / 2), (xws, yws / 2), 1)
            pygame.draw.line(screen, RED, (xws / 2, 0), (xws / 2, yws), 1)

        # display flux mismatch
        if flux_calc:
            pygame.draw.line(screen, CYAN, (xws / 2, yws / 2),
                            (xws / 2 + diff14b, yws / 2 + diff14b), 2)
            pygame.draw.circle(screen, CYAN,
                            (int(xws / 2 + diff14b), int(yws / 2 + diff14b)),
                            2 * zoom, 2)
            pygame.draw.line(screen, CYAN, (xws / 2, yws / 2),
                            (xws / 2 - diff23b, yws / 2 + diff23b), 2)
            pygame.draw.circle(screen, CYAN,
                            (int(xws / 2 - diff23b), int(yws / 2 + diff23b)),
                            2 * zoom, 2)
            pygame.draw.line(screen, RED1, (xws / 2, yws / 2),
                            (xws / 2 + diffxb, yws / 2 + diffyb), 2)
            pygame.draw.circle(screen, RED1,
                            (int(xws / 2 + diffxb), int(yws / 2 + diffyb)),
                            2 * zoom, 2)
        # saving images
        tmuxon = os.popen('tmux ls |grep ocamlog | awk \'{print $2}\'').read()
        if tmuxon:
            saveim = True
        else:
            saveim = False
        if cnti % 20:
            rects = [rct, rct2, rct3, rect2, rect2b]
        else:
            rects = []

        rects += [rect1, rct_info, rct_info2, rct_dinfo, rct_dinfo2]
        if saveim:
            screen.blit(savem1, rct_savem1)
            rects += [rct_savem1]

        # =====================================
        for event in pygame.event.get():

            # Keyboard modifiers
            mmods = pygame.key.get_mods()

            if event.type == QUIT:
                pygame.quit()

                # close shared memory access
                # --------------------------
                cam.close()  # global disp map
                bias_shm.close()
                print("Pueo has ended normally.")
                sys.exit()

            elif event.type == KEYDOWN:

                if event.key == K_ESCAPE:
                    pygame.quit()
                    # close shared memory access
                    # --------------------------
                    cam.close()  # global disp map
                    print("Pueo has ended normally.")
                    sys.exit()

                if event.key == K_c:
                    plot_cross = not plot_cross

                if event.key == K_f:
                    flux_calc = not flux_calc

                if event.key == K_m:
                    clr_scale = not clr_scale

                if event.key == K_d:
                    subt_bias = not subt_bias
                    if subt_bias:
                        bname = home + "/conf/pueo_aux/bias.fits"
                        try:
                            # bias = pf.getdata(bname)
                            bias = bias_shm.get_data()
                        except:
                            bias = np.zeros_like(temp)

                if event.key == K_h:
                    print(hmsg)

                # secret chuck mode to re-acquire biases for all exp times
                # --------------------------------------------------------
                if event.key == K_b:

                    if cvc.check_modifiers(mmods, lc=True):
                        msg = "  !! Acquiring darks !!   "
                        dinfo2 = font3.render(msg, True, BGCOL, SACOL)
                        screen.blit(dinfo2, rct_dinfo2)
                        pygame.display.update([rct_dinfo2])
                        #os.system("log Chuckcam: Saving internal darks")

                        print("Saving dark.")

                        subt_bias = False

                        ndark = 1000
                        for idark in range(ndark):
                            if idark == 0:
                                temp3 = get_img_data(True) / float(ndark)
                            else:
                                temp3 += get_img_data(True) / float(ndark)

                        bname = home + "/conf/pueo_aux/bias.fits"

                        pf.writeto(bname, temp3, overwrite=True)
                        time.sleep(0.2)

                # Pueo mode to save and subtract a reference image
                # --------------------------------------------------------
                if event.key == K_r:
                    if cvc.check_modifiers(mmods, lc=True):
                        msg = "!! Acquiring reference !! "
                        dinfo2 = font3.render(msg, True, BGCOL, SACOL)
                        screen.blit(dinfo2, rct_dinfo2)
                        pygame.display.update([rct_dinfo2])

                        subt_ref = False

                        nref = 1000
                        for iref in range(nref):
                            if iref == 0:
                                temp3 = get_img_data(True) / float(nref)
                            else:
                                temp3 += get_img_data(True) / float(nref)

                        rname = home + "/conf/pueo_aux/ref.fits"
                        pf.writeto(rname, temp3, overwrite=True)

                    else:
                        rname = home + "/conf/pueo_aux/ref.fits"
                        ref_im = pf.getdata(rname)
                        subt_ref = not subt_ref

                if event.key == K_v:
                    average = not average

                if event.key == K_s:
                    if cvc.check_modifiers(mmods, lc=True):
                        saveim = not saveim
                        if saveim:
                            timestamp = dt.datetime.utcnow().strftime('%Y%m%d')
                            savepath = '/media/data/' + timestamp + '/ocam2k/'
                            ospath = os.path.dirname(savepath)
                            if not os.path.exists(ospath):
                                os.makedirs(ospath)
                            nimsave = 10000
                            # creating a tmux session for logging
                            os.system("tmux new-session -d -s ocamlog")
                            os.system(
                                    "tmux send-keys -t ocamlog \"logshim ocam2d %i %s\" C-m"
                                    % (nimsave, savepath))
                            #os.system("log Chuckcam: start logging images")
                        else:
                            os.system(
                                    "tmux send-keys -t ocamlog \"logshimkill ircam1\""
                            )
                            os.system("tmux kill-session -t ocamlog")
                            #os.system("log Chuckcam: stop logging images")

                # Reset gain safety with Ctrl+Alt+G
                if event.key == K_g and cvc.check_modifiers(mmods, lc=True,
                                                            la=True):
                    os.system("pywfs_gainreset")

                # Direct gains Ctrl+Shift 2**number
                keys = [K_0, K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8, K_9]
                if event.key in keys and \
                    cvc.check_modifiers(mmods, lc=True, ls=True):
                    what_key = keys.index(event.key)
                    os.system(f"pywfs_gain {2**what_key}")

                # Joystick-like TT and pup steering
                if event.key in [K_UP, K_RIGHT, K_DOWN, K_LEFT]:
                    if rdb_alive:
                        if cvc.check_modifiers(mmods, lc=True):  # Ctrl + Arrow
                            action = 'TT'
                            push_amount = 0.1
                        if cvc.check_modifiers(mmods, lc=True,
                                            ls=True):  # Ctrl + Shift + Arrow
                            action = 'TT'
                            push_amount = 0.3
                        if cvc.check_modifiers(mmods, la=True):  # Alt + Arrow
                            action = 'PUP'
                            push_amount = 2000
                        if cvc.check_modifiers(mmods, la=True,
                                            ls=True):  # Alt + Shift + Arrow
                            action = 'PUP'
                            push_amount = 10000

                        if action == 'TT':
                            push_scale = {
                                    K_UP: (-.707, .707),
                                    K_DOWN: (.707, -.707),
                                    K_LEFT: (-.707, -.707),
                                    K_RIGHT: (.707, .707),
                            }[event.key]

                            # Get the current value - redis or analog output
                            with rdb.pipeline() as pipe:
                                pipe.hget('X_ANALGC', 'value')
                                pipe.hget('X_ANALGD', 'value')
                                val_cd = pipe.execute()

                            # Now send commands over to analog output
                            # TODO Include autobounce in analog_output.py
                            new_c = val_cd[0] + push_scale[0] * push_amount
                            new_d = val_cd[1] + push_scale[1] * push_amount
                            os.system(
                                    f'ssh sc2 "source .profile; /home/scexao/bin/devices/analog_output.py voltage C {new_c}"'
                            )
                            # No detach the first one - they'll collide and one will be ignored.
                            os.system(
                                    f'ssh sc2 "source .profile; /home/scexao/bin/devices/analog_output.py voltage D {new_d}" &'
                            )

                        elif action == 'PUP':
                            push_scale = {
                                    K_UP: (0., 1.0),
                                    K_DOWN: (0., -1.0),
                                    K_LEFT: (-1.0, 0.0),
                                    K_RIGHT: (1.0, 0.0),
                            }[event.key]

                            # Get the current value - redis or analog output
                            with rdb.pipeline() as pipe:
                                pipe.hget('X_PYWPPX', 'value')
                                pipe.hget('X_PYWPPY', 'value')
                                val_xy = pipe.execute()

                            # Now send commands over to analog output
                            # TODO Include autobounce in pywfs_pup ! - and check axes
                            new_x = int(
                                    round(val_xy[0] + push_scale[0] * push_amount))
                            new_y = int(
                                    round(val_xy[1] + push_scale[1] * push_amount))
                            os.system(
                                    f'ssh sc2 "source .profile; /home/scexao/bin/devices/pywfs_pup x goto {new_x}"'
                            )
                            os.system(
                                    f'ssh sc2 "source .profile; /home/scexao/bin/devices/pywfs_pup y goto {new_y}"'
                            )

                    else:  # not rdb_alive
                        print('Redis DB unavailable - pass.')

        pygame.display.update(rects)

        #pygame.display.flip()
        fpsClock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()