#!/usr/bin/env python

import math as m
import numpy as np
import copy, os, sys

import matplotlib.pyplot as plt

from astropy.modeling import models, fitting
from scipy.fftpack import fftfreq
from scipy.interpolate import interp2d
from scipy.ndimage import median_filter, shift
from astropy.io import fits as pf

home = os.getenv('HOME')  # Expected /home/scexao
sys.path.append(home + '/src/lib/python/')

fitter = fitting.LevMarLSQFitter()

# ========= MODEL PSF FOR FITTING =======================
# =======================================================


@models.custom_model
def SubaruPSF(x, y, amplitude=1.0, x_0=0.0, y_0=0.0):
    """Simulation of SCExAO PSF"""
    psf = pf.getdata("%s/src/lib/python/simref.fits" % home)
    psf_func = interp2d(
            np.arange(257) - 128,
            np.arange(257) - 128, psf, kind='linear')
    psf_eval = amplitude * psf_func(x[:, 0] - x_0, y[0, :] - y_0)
    return np.reshape(psf_eval, x.shape)


# ========= MODEL RETROINJECTION FOR FITTING ============
# =======================================================


@models.custom_model
def RetroinjPSF(x, y, amplitude=1.0, x_0=0.0, y_0=0.0):
    """Simulation of Retroinj PSF"""
    psf = pf.getdata("%s/src/lib/python/REACH_retroinj.fits" % home)
    psf_func = interp2d(
            np.arange(129) - 64,
            np.arange(129) - 64, psf, kind='linear')
    psf_eval = amplitude * psf_func(x[:, 0] - x_0, y[0, :] - y_0)
    return np.reshape(psf_eval, x.shape)


# ======= MAKE RAMP =====================================================
# =======================================================================


def make_ramp(*args):
    # make_ramp - Creates a n points ramp between a and b.
    # PURPOSE:
    # This function computes and returns a n point ramp between a and b, b can
    # be excluded or included, with a linear or logarithmic step.
    # INPUTS:
    #    a: left limit, included
    #    b: right limit, excluded or included
    #    n: numer of points in the ramp
    #  leq: OPTIONAL boolean to include b, default is b is excluded
    # loga: OPTIONAL boolean to use a log frequency axis, default is linear.
    # OUPUTS:
    # ramp: ramp

    ni = len(args)

    a = args[0]
    b = args[1]
    n = args[2]
    if ni == 3:
        leq = 0
        loga = 0
    elif ni == 4:
        leq = args[3]
        loga = 0
    else:
        leq = args[3]
        loga = args[4]
        if leq == []:
            leq = 0

    if leq == 1:
        n2 = n - 1
    else:
        n2 = n

    if loga == 1:
        ramptemp = np.array(map(
                float, range(n))) * (m.log10(b) - m.log10(a)) / n2 + m.log10(a)
        ramp = np.power(10, ramptemp)
    else:
        ramp = np.array(map(float, range(n))) * (b - a) / n2 + a

    return ramp


# ========= HOT PIXELS ==================================
#========================================================
def find_outlier_pixels(data, tolerance=3, worry_about_edges=True):
    #This function finds the hot or dead pixels in a 2D dataset.
    #tolerance is the number of standard deviations used to cutoff the hot pixels
    #If you want to ignore the edges and greatly speed up the code, then set
    #worry_about_edges to False.
    #
    #The function returns a list of hot pixels and also an image with with hot pixels removed
    blurred = median_filter(data, size=2)
    difference = data - blurred
    threshold = tolerance * np.std(difference)

    #find the hot pixels, but ignore the edges
    hot_pixels = np.nonzero((np.abs(difference[1:-1, 1:-1]) > threshold))
    hot_pixels = np.array(
            hot_pixels) + 1  #because we ignored the first row and first column

    fixed_image = copy.deepcopy(
            data)  #This is the image with the hot pixels removed
    for y, x in zip(hot_pixels[0], hot_pixels[1]):
        fixed_image[y, x] = blurred[y, x]

    if worry_about_edges == True:
        height, width = np.shape(data)

        ###Now get the pixels on the edges (but not the corners)###

        #left and right sides
        for index in range(1, height - 1):
            #left side:
            med = np.median(data[index - 1:index + 2, 0:2])
            diff = np.abs(data[index, 0] - med)
            if diff > threshold:
                hot_pixels = np.hstack((hot_pixels, [[index], [0]]))
                fixed_image[index, 0] = med

            #right side:
            med = np.median(data[index - 1:index + 2, -2:])
            diff = np.abs(data[index, -1] - med)
            if diff > threshold:
                hot_pixels = np.hstack((hot_pixels, [[index], [width - 1]]))
                fixed_image[index, -1] = med

        #Then the top and bottom
        for index in range(1, width - 1):
            #bottom:
            med = np.median(data[0:2, index - 1:index + 2])
            diff = np.abs(data[0, index] - med)
            if diff > threshold:
                hot_pixels = np.hstack((hot_pixels, [[0], [index]]))
                fixed_image[0, index] = med

            #top:
            med = np.median(data[-2:, index - 1:index + 2])
            diff = np.abs(data[-1, index] - med)
            if diff > threshold:
                hot_pixels = np.hstack((hot_pixels, [[height - 1], [index]]))
                fixed_image[-1, index] = med

        ###Then the corners###

        #bottom left
        med = np.median(data[0:2, 0:2])
        diff = np.abs(data[0, 0] - med)
        if diff > threshold:
            hot_pixels = np.hstack((hot_pixels, [[0], [0]]))
            fixed_image[0, 0] = med

        #bottom right
        med = np.median(data[0:2, -2:])
        diff = np.abs(data[0, -1] - med)
        if diff > threshold:
            hot_pixels = np.hstack((hot_pixels, [[0], [width - 1]]))
            fixed_image[0, -1] = med

        #top left
        med = np.median(data[-2:, 0:2])
        diff = np.abs(data[-1, 0] - med)
        if diff > threshold:
            hot_pixels = np.hstack((hot_pixels, [[height - 1], [0]]))
            fixed_image[-1, 0] = med

        #top right
        med = np.median(data[-2:, -2:])
        diff = np.abs(data[-1, -1] - med)
        if diff > threshold:
            hot_pixels = np.hstack((hot_pixels, [[height - 1], [width - 1]]))
            fixed_image[-1, -1] = med

    return hot_pixels, fixed_image


def outlier_pixels_as_map(data, tolerance=3):
    #This function finds the hot or dead pixels in a 2D dataset.
    #tolerance is the number of standard deviations used to cutoff the hot pixels

    # Ignore the edges entirely, by design
    # Do not correct the data, only compute the mask.

    #The function returns a list of hot pixels and also an image with with hot pixels removed
    blurred = median_filter(data, size=2)
    difference = data - blurred
    threshold = tolerance * np.std(difference[1:-1, 1:-1])

    #find the hot pixels, but ignore the edges
    return np.abs(difference) < threshold


# ========= CENTROID ====================================
# =======================================================


def centroid(image, bias=[], subt_bias=True, fact=0.2, method="default",
             fixrad=False):
    if not subt_bias:
        image2 = image - bias
    else:
        image2 = copy.deepcopy(image)
    imax = np.max(image2)
    imin = fact * imax
    image3 = copy.deepcopy(image2) - imin
    mask = image3 > 0
    image3 *= mask
    total = np.nansum(image3)
    X, Y = np.indices(np.shape(image3))
    cy = (np.nansum(X * image3) / total)
    cx = (np.nansum(Y * image3) / total)
    if method == "default":
        cx2 = cx  #+0.5
        cy2 = cy  #+0.5
    elif method == "gaussian":
        image4 = image2[int(cy) - 64:int(cy) + 64, int(cx) - 64:int(cx) + 64]
        radc = m.sqrt(np.sum(image4 > (imax / 4.)) / m.pi)
        se_param = fit_TwoD_Gaussian(image4, 64, 64, radc, fixrad=fixrad)
        cy2 = se_param.x_mean.value - 64 + int(cy)
        cx2 = se_param.y_mean.value - 64 + int(cx)
    elif method == "airy":
        image4 = image2[int(cy) - 64:int(cy) + 64, int(cx) - 64:int(cx) + 64]
        model_init1 = SubaruPSF(amplitude=imax, x_0=64, y_0=64)
        nx = image4.shape[0]
        ny = image4.shape[1]
        xx, yy = np.mgrid[:nx, :ny]
        psf_fit = fitter(model_init1, xx, yy, image4, maxiter=2000)
        #print("default:",imax,cx,cy)
        cy2 = psf_fit.y_0.value - 64 + int(cy)
        cx2 = psf_fit.x_0.value - 64 + int(cx)
        #print("airy:",psf_fit.amplitude.value,cx2,cy2)
    else:
        print("wrong centroid method")
    return [cx2, cy2]


# ========= RADIAL PROFILE ==============================
# =======================================================


def radial_data(data, annulus_width=1, working_mask=None, x=None, y=None,
                rmax=None):
    """
    r = radial_data(data,annulus_width,working_mask,x,y)

    A function to reduce an image to a radial cross-section.

    INPUT:
    ------
    data   - whatever data you are radially averaging.  Data is
            binned into a series of annuli of width 'annulus_width'
            pixels.
    annulus_width - width of each annulus.  Default is 1.
    working_mask - array of same size as 'data', with zeros at
                      whichever 'data' points you don't want included
                      in the radial data computations.
      x,y - coordinate system in which the data exists (used to set
             the center of the data).  By default, these are set to
             integer meshgrids
      rmax -- maximum radial value over which to compute statistics

     OUTPUT:
     -------
      r - a data structure containing the following
                   statistics, computed across each annulus:
          .r      - the radial coordinate used (outer edge of annulus)
          .mean   - mean of the data in the annulus
          .std    - standard deviation of the data in the annulus
          .median - median value in the annulus
          .max    - maximum value in the annulus
          .min    - minimum value in the annulus
          .numel  - number of elements in the annulus
    """

    # 2010-03-10 19:22 IJC: Ported to python from Matlab
    # 2005/12/19 Added 'working_region' option (IJC)
    # 2005/12/15 Switched order of outputs (IJC)
    # 2005/12/12 IJC: Removed decifact, changed name, wrote comments.
    # 2005/11/04 by Ian Crossfield at the Jet Propulsion Laboratory

    import numpy as np

    class radialDat:
        """Empty object container.
        """

        def __init__(self):
            self.mean = None
            self.std = None
            self.median = None
            self.numel = None
            self.max = None
            self.min = None
            self.r = None

    #---------------------
    # Set up input parameters
    #---------------------
    data = np.array(data)

    if working_mask == None:
        working_mask = np.ones(data.shape, bool)

    npix, npiy = data.shape
    #print(npix, npiy)
    try:
        if x == None or y == None:
            x1 = np.arange(-npix / 2., npix / 2.)
            y1 = np.arange(-npiy / 2., npiy / 2.)
            x, y = np.meshgrid(y1, x1)
    except:
        print("x and y provided")

    r = abs(x + 1j * y)

    if rmax == None:
        rmax = r[working_mask].max()

    #---------------------
    # Prepare the data container
    #---------------------
    dr = np.abs([x[0, 0] - x[0, 1]]) * annulus_width
    #print("test",annulus_width,dr, x[0,:])
    radial = np.arange(rmax / dr) * dr + dr / 2.
    nrad = len(radial)
    radialdata = radialDat()
    radialdata.mean = np.zeros(nrad)
    radialdata.std = np.zeros(nrad)
    radialdata.median = np.zeros(nrad)
    radialdata.numel = np.zeros(nrad)
    radialdata.max = np.zeros(nrad)
    radialdata.min = np.zeros(nrad)
    radialdata.r = radial

    #---------------------
    # Loop through the bins
    #---------------------
    for irad in range(nrad):  #= 1:numel(radial)
        minrad = irad * dr
        maxrad = minrad + dr
        thisindex = (r >= minrad) * (r < maxrad) * working_mask
        if not thisindex.ravel().any():
            radialdata.mean[irad] = np.nan
            radialdata.std[irad] = np.nan
            radialdata.median[irad] = np.nan
            radialdata.numel[irad] = np.nan
            radialdata.max[irad] = np.nan
            radialdata.min[irad] = np.nan
        else:
            radialdata.mean[irad] = np.nanmean(data[thisindex])
            radialdata.std[irad] = data[thisindex].std()
            radialdata.median[irad] = np.median(data[thisindex])
            radialdata.numel[irad] = data[thisindex].size
            radialdata.max[irad] = data[thisindex].max()
            radialdata.min[irad] = data[thisindex].min()

    #---------------------
    # Return with data
    #---------------------

    return radialdata


# ========= FFT SHIFT ===================================
# =======================================================


def shift_fft(input_array, shift):
    shift_rows, shift_cols = shift
    nr, nc = input_array.shape
    Nr, Nc = fftfreq(nr), fftfreq(nc)
    Nc, Nr = np.meshgrid(Nc, Nr)
    fft_inputarray = np.fft.fft2(input_array)
    fourier_shift = np.exp(1j * 2 * np.pi * ((shift_rows * Nr) +
                                             (shift_cols * Nc)))
    output_array = np.fft.ifft2(fft_inputarray * fourier_shift)
    return np.real(output_array)


# ========= 2D GAUSSIAN =================================
# =======================================================


def twoD_Gaussian(coor, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    (x, y) = coor
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta)**2) / (2 * sigma_x**2) + (np.sin(theta)**
                                                 2) / (2 * sigma_y**2)
    b = -(np.sin(2 * theta)) / (4 * sigma_x**2) + (np.sin(
            2 * theta)) / (4 * sigma_y**2)
    c = (np.sin(theta)**2) / (2 * sigma_x**2) + (np.cos(theta)**
                                                 2) / (2 * sigma_y**2)
    g = offset + amplitude * np.exp(-(a * ((x - xo)**2) + 2 * b * (x - xo) *
                                      (y - yo) + c * ((y - yo)**2)))
    return g.ravel()


# ========= 2D GAUSSIAN FIT =============================
# =======================================================


def fit_TwoD_Gaussian(img, xc, yc, rad, circ=False, fixrad=False):

    if fixrad:
        model_init = models.Gaussian2D(
                amplitude=np.max(img), x_mean=xc, y_mean=yc, x_stddev=rad,
                y_stddev=rad, theta=0, fixed={
                        'x_stddev': True,
                        'y_stddev': True
                })
    else:
        model_init = models.Gaussian2D(amplitude=np.max(img), x_mean=xc,
                                       y_mean=yc, x_stddev=rad, y_stddev=rad,
                                       theta=0)
    nx = img.shape[0]
    ny = img.shape[1]

    x, y = np.mgrid[:nx, :ny]

    gauss2_fit = fitter(model_init, x, y, img)

    return gauss2_fit


# ========= CALCULATE SEEING ============================
# =======================================================


def calculate_seeing(image):

    [cx, cy] = centroid(image)
    radc = m.sqrt(np.sum(image > (image.max() / 4.)) / m.pi)
    se_param = fit_TwoD_Gaussian(image, cy, cx, radc)
    se_ystd = se_param.x_stddev.value * 2.355
    se_xstd = se_param.y_stddev.value * 2.355
    se_yc = se_param.x_mean.value
    se_xc = se_param.y_mean.value
    se_theta = se_param.theta.value
    return (se_xstd, se_ystd, se_xc, se_yc, se_theta)


# ========= CIRCULAR MASK ===============================
# =======================================================


def create_circular_mask(h, w, center=None, radius=None):

    if center is None:  # use the middle of the image
        center = [int(w / 2), int(h / 2)]
    if radius is None:  # use the smallest distance between the center and image walls
        radius = min(center[0], center[1], w - center[0], h - center[1])

    Y, X = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y - center[1])**2)

    mask = (dist_from_center <= radius).astype(int)
    return mask


# ========= SIMULATE PSF ================================
# =======================================================


def get_numerical_PSF(file_aperture='pupil.fits', mas_pix=16.2,
                      rotation_angle=-7., wavelength=1.6e-6):
    import hcipy as hci
    #-----------------------------------------------------------------
    # loading relevant files
    #-----------------------------------------------------------------

    # loading relevant files
    aperture = pf.getdata(file_aperture)

    #----------------------------------------------------------------------
    # parameters
    #----------------------------------------------------------------------
    diameter = 7.8  # meter

    # lambda / diameter
    ld = wavelength / diameter  # radians
    ld = np.degrees(ld) * 3600 * 1000  # milli arcsec

    oversampling_factor = 1

    # pixels size in mas
    rad_pix = np.radians(mas_pix / 1000 / 3600) / oversampling_factor

    # number of pixels along one axis in the pupil and focal planes
    Npix_pup = aperture.shape[0]

    Npix_foc = 256 * oversampling_factor

    #----------------------------------------------------------------------
    # setting grids, mode basis, propagators, etc
    #----------------------------------------------------------------------
    # rotating the aperture
    aperture = hci.rotate(aperture, rotation_angle, reshape=False)

    # generating the grids
    pupil_grid = hci.make_pupil_grid(Npix_pup, diameter=diameter)
    focal_grid = hci.make_uniform_grid([Npix_foc + 1, Npix_foc + 1],
                                       [(Npix_foc + 1) * rad_pix,
                                        (Npix_foc + 1) * rad_pix])

    # generating the propagator
    propagator = hci.FraunhoferPropagator(pupil_grid, focal_grid)

    # rotating the aperture to the correct rotation and making it a field
    aperture = hci.Field(aperture.ravel(), pupil_grid)

    # fourier transform of aperture
    a = propagator(hci.Wavefront(aperture, wavelength=wavelength))

    # getting the power
    test_PSF = a.power

    # subsampling the PSF to the resolution of VAMPIRES
    test_PSF = hci.subsample_field(test_PSF, oversampling_factor)
    test_PSF /= test_PSF.max()
    return (test_PSF)


# ========= CALCULATE STREHL ============================
# =======================================================


def calculate_strehl(image, wavelength=1.6e-6, mas_pix=16.2, camera="Palila",
                     flt="H", dia_ring_LD=45, a=256, a2=32, target="TEST",
                     savepath=home + "/Documents/Astrometry/Figures",
                     timestamp="", saveplot=True):
    import hcipy as hci

    as_pix = mas_pix / 1000
    nxi = image.shape[1]
    nyi = image.shape[0]
    cxi = int(nxi / 2)
    cyi = int(nyi / 2)
    ca = min(int(a / 2), cxi, cyi)
    ca2 = min(int(a2 / 2), cxi, cyi)
    x, y = np.mgrid[:a2, :a2]
    imgstr1 = image[cyi - ca2:cyi + ca2, cxi - ca2:cxi + ca2]
    indmaxce = np.argmax(imgstr1)
    posce = np.unravel_index(indmaxce, (a2, a2))
    os.system(
            'cp %s/src/lib/python/%s_PSF_%s.fits %s/src/lib/python/simref.fits'
            % (home, camera, flt, home))
    model_init = SubaruPSF(amplitude=np.max(imgstr1), x_0=posce[1],
                           y_0=posce[0])
    fitter1 = fitting.LevMarLSQFitter()
    psf_fitce = fitter1(model_init, x, y, imgstr1, maxiter=2000)
    xoff = psf_fitce.x_0.value - ca2
    yoff = psf_fitce.y_0.value - ca2
    imgstr2 = shift(image, (-yoff, -xoff))[cyi - ca:cyi + ca, cxi - ca:cxi + ca]
    ref = pf.getdata("%s/src/lib/python/simref.fits" % home)
    nxr = ref.shape[1]
    nyr = ref.shape[0]
    Npix_foc = min(nxr, nyr, 2 * ca)
    Npix_foc -= 1 - Npix_foc % 2
    afoc = int(Npix_foc / 2)
    cxr = int(nxr / 2)
    cyr = int(nyr / 2)
    imgstr3 = imgstr2[ca - afoc:ca + afoc + 1, ca - afoc:ca + afoc + 1]
    ref = ref[cyr - afoc:cyr + afoc + 1, cxr - afoc:cxr + afoc + 1]

    diameter = 7.8  # meter

    if flt == "H":
        wavelength = 1.55e-6
    elif flt == "J":
        wavelength = 1.25e-6
    elif flt == "y":
        wavelength = 1.02e-6
    elif flt.isdigit():
        wavelength = int(flt) * 1e-6

    lambda_D_rad = wavelength / diameter

    lambda_D_mas = np.degrees(lambda_D_rad) * 3600 * 1000

    dia_core_LD = 2.44

    dia_core_pix = dia_core_LD * lambda_D_mas / mas_pix
    dia_ring_pix = dia_ring_LD * lambda_D_mas / mas_pix

    grid = hci.make_uniform_grid([Npix_foc, Npix_foc], [Npix_foc, Npix_foc])
    # changing the image to a Field object
    imgstr4 = hci.Field(imgstr3.ravel(), grid)
    ref = hci.Field(ref.ravel(), grid)

    # normalizing the image
    imgstr4 /= imgstr4.max()

    core_mask = hci.circular_aperture(dia_core_pix)(grid)
    ring_mask = hci.circular_aperture(dia_ring_pix)(grid)

    sum_core_ref = np.sum(ref[core_mask == 1])
    sum_ring_ref = np.sum(ref[ring_mask == 1])

    reference = np.sum(ref[core_mask == 1]) / np.sum(ref[ring_mask == 1])

    sum_core = np.sum(imgstr4[core_mask == 1])
    sum_ring = np.sum(imgstr4[ring_mask == 1])
    error_core = np.sqrt(sum_core)
    error_ring = np.sqrt(sum_ring)

    strehl = sum_core / sum_ring / reference
    strehl2 = max(0, min(1, strehl))
    imgstr3 *= strehl2 / imgstr3.max()

    if saveplot:
        fig, ax = plt.subplots()
        plt.imshow(
                np.log10(np.abs(imgstr3)), cmap="inferno",
                extent=[(-afoc + 0.5) * as_pix, (afoc - 0.5) * as_pix,
                        (afoc - 0.5) * as_pix, (-afoc + 0.5) * as_pix])
        plt.clim([-4, 0])
        cbar = plt.colorbar()
        cbar.ax.set_ylabel("Contrast")
        ax.set(xlabel="Angle [arcsec]", ylabel="Angle [arcsec]",
               title="%s, Strehl ratio: %.2f" % (target, strehl))
        plt.savefig("%s%s_Strehl_%s.png" % (savepath, timestamp, target),
                    overwrite=True)
        pf.writeto("%s%s_Strehl_%s.fits" % (savepath, timestamp, target),
                   imgstr3, overwrite=True)

    return strehl, dia_core_pix, dia_ring_pix, xoff, yoff, imgstr3


# ========= BINARY PROCESSING ===========================
# =======================================================


def binary_processing(im, target="TEST", mas_pix=16.2, pad=0, nst=2, a=128,
                      a2=16, rm=10, camera="Palila", flt="H", savepath=home +
                      "/Documents/Astrometry/Figures", timestamp="",
                      saveplot=True, retroinj=False, strehlcalc=True,
                      verbose=True, trackstar=-1, trackcen=True, posst=[]):

    as_pix = mas_pix / 1000
    fitter1 = fitting.LevMarLSQFitter()
    os.system(
            'cp %s/src/lib/python/%s_PSF_%s.fits %s/src/lib/python/simref.fits'
            % (home, camera, flt, home))

    if type(rm) == int:
        rm = rm * np.ones(nst + int(retroinj) - 1)

    nx = im.shape[1]
    ny = im.shape[0]
    cx = int(nx / 2)
    cy = int(ny / 2)
    if (a < nx) or (a < ny):
        ca = int(a / 2)
        im = im[cy - ca:cy + ca, cx - ca:cx + ca]
        nx = ny = a
        cx = cy = ca

    postmp = np.zeros((nst + int(retroinj), 2))
    postmp[0, :] = [cy, cx]
    fluxtmp = np.zeros(nst + int(retroinj))
    fluxtmp[0] = im.max()
    ym = cy
    xm = cx
    maskedim = copy.deepcopy(im)
    if trackcen:
        model_init = SubaruPSF(amplitude=fluxtmp[0], y_0=postmp[0, 0],
                               x_0=postmp[0, 1])
    x, y = np.mgrid[:ny, :nx]

    if retroinj:
        os.system(
                'cp %s/src/lib/python/%s_REACH_retroinj.fits %s/src/lib/python/REACH_retroinj.fits'
                % (home, camera, home))
        mask = create_circular_mask(ny, nx, center=[ym, xm], radius=rm[0])
        maskedim = maskedim * (1 - mask)
        retrotmp = np.array(centroid(maskedim)).astype(np.int)
        model_init_retro = RetroinjPSF(
                amplitude=maskedim.max(), x_0=retrotmp[0], y_0=retrotmp[1],
                bounds={
                        'x_0': (retrotmp[0] - 20, retrotmp[0] + 20),
                        'y_0': (retrotmp[1] - 20, retrotmp[1] + 20)
                })
        if trackcen:
            model_init += model_init_retro
        else:
            model_init = model_init_retro
        psf_fit = fitter1(model_init_retro, x, y, maskedim, maxiter=2000)
        maskedim -= psf_fit(x, y)
        retrotmp = psf_fit.parameters[1:]
    for i in range(nst - 1):
        mask = create_circular_mask(ny, nx, center=[ym, xm],
                                    radius=rm[i + int(retroinj)])
        maskedim = maskedim * (1 - mask)
        plt.savefig("test1.png", overwrite=True)
        if retroinj and trackstar > 0 and i + 1 == trackstar:
            print("tracking this star")
            postmp[i + int(retroinj) + 1, :] = retrotmp[::-1]
        else:
            indmaxco = np.argmax(maskedim)
            postmp[i + int(retroinj) +
                   1, :] = np.unravel_index(indmaxco, (ny, nx))
        print(postmp[i + int(retroinj) + 1, :])
        fluxtmp[i + int(retroinj) + 1] = maskedim.max(
        )  #im[postmp[i+int(retroinj)+1,:].astype(np.int)]
        if i == 0 and not trackcen and not retroinj:
            model_init = SubaruPSF(
                    amplitude=fluxtmp[i + int(retroinj) + 1],
                    x_0=postmp[i + int(retroinj) + 1, 1],
                    y_0=postmp[i + int(retroinj) + 1, 0], bounds={
                            'x_0': (postmp[i + int(retroinj) + 1, 1] - 10,
                                    postmp[i + int(retroinj) + 1, 1] + 10),
                            'y_0': (postmp[i + int(retroinj) + 1, 0] - 10,
                                    postmp[i + int(retroinj) + 1, 0] + 10)
                    })
        else:
            model_init += SubaruPSF(
                    amplitude=fluxtmp[i + int(retroinj) + 1],
                    x_0=postmp[i + int(retroinj) + 1, 1],
                    y_0=postmp[i + int(retroinj) + 1, 0], bounds={
                            'x_0': (postmp[i + int(retroinj) + 1, 1] - 10,
                                    postmp[i + int(retroinj) + 1, 1] + 10),
                            'y_0': (postmp[i + int(retroinj) + 1, 0] - 10,
                                    postmp[i + int(retroinj) + 1, 0] + 10)
                    })

        ym = postmp[i + int(retroinj) + 1, 1]
        xm = postmp[i + int(retroinj) + 1, 0]
        plt.savefig("test2.png", overwrite=True)

    posst = np.zeros((nst + int(retroinj), 2))
    psf_fit = fitter1(model_init, x, y, im, maxiter=2000)
    #plt.figure()
    #plt.imshow(np.log10(np.abs(im)))
    #plt.figure()
    #plt.imshow(np.log10(np.abs(psf_fit(x,y))))
    fluxst = psf_fit.parameters[::3]
    contrast = psf_fit.parameters[::3] / psf_fit.parameters[0]
    posst[:, 0] = psf_fit.parameters[1::3]
    posst[:, 1] = psf_fit.parameters[2::3]
    xoff = posst[0, 0] - cx
    yoff = posst[0, 1] - cy
    im = shift(im, (-yoff, -xoff))
    posst -= np.tile(posst[0, :], (nst + int(retroinj), 1))
    x = x.astype(np.float) + psf_fit.parameters[1] - cx
    y = y.astype(np.float) + psf_fit.parameters[2] - cy

    distco = np.sqrt((posst[1:, 0] - posst[0, 0])**2 +
                     (posst[1:, 1] - posst[0, 1])**2)
    angleco = -np.rad2deg(
            np.arctan((posst[1:, 1] - posst[0, 1]) /
                      (posst[1:, 0] - posst[0, 0])))
    for i in range(nst + int(retroinj) - 1):
        if posst[0, 0] < posst[i + 1, 0]:
            angleco[i] += 180

    angleco += pad
    for i in range(nst + int(retroinj) - 1):
        if angleco[i] < 0:
            angleco[i] += 360

    imce = im / fluxst[0]
    for i in range(nst + int(retroinj) - 1):
        for j in range(2):
            imce -= (-1)**j * contrast[i + 1]**(j + 1) * shift(
                    imce, ((j + 1) * (posst[i + 1, 1] - posst[0, 1]),
                           (j + 1) * (posst[i + 1, 0] - posst[0, 0])))

    if strehlcalc:
        strehl, tmp1, dia_ring, tmp3, tmp4, tmp5 = calculate_strehl(
                imce, camera=camera, flt=flt, saveplot=False)
        #strehl2 = max(0, min(1, strehl))
    else:
        strehl = 1
        dia_ring = 45

    if saveplot:
        cnx = 0.8 * cx * as_pix
        cny = 0.8 * cy * as_pix
        rn = 0.06 * nx * as_pix
        rn2 = 0.075 * nx * as_pix
        posstb = posst * as_pix
        corrlabels = np.zeros((nst + int(retroinj) - 1, 2))
        corrlabels[:, 1] = 0.05 * ny * as_pix
        fig, ax = plt.subplots()
        plt.imshow(
                np.log10(np.abs(im[1:, 1:] / np.max(im))), cmap="inferno",
                extent=[(-cx + 0.5) * as_pix, (cx - 0.5) * as_pix,
                        (cy - 0.5) * as_pix, (-cy + 0.5) * as_pix])
        plt.clim([-4, 0])
        cbar = plt.colorbar()
        cbar.ax.set_ylabel("Contrast")
        if strehlcalc:
            ax.set(xlabel="Angle [arcsec]", ylabel="Angle [arcsec]",
                   title="%s, Strehl ratio: %.2f" % (target, strehl))
        else:
            ax.set(xlabel="Angle [arcsec]", ylabel="Angle [arcsec]",
                   title="%s" % target)
        ax.scatter(posstb[0, 0], posstb[0, 1], s=1000 * 256 / a,
                   edgecolor="white", facecolor="none", alpha=0.25)
        ax.scatter(posstb[0, 0], posstb[0, 1], marker='+', color="red")
        plt.plot(posstb[:, 0], posstb[:, 1], color="orange", alpha=0.5)
        for i in range(nst + int(retroinj) - 1):
            ax.scatter(posstb[i + 1, 0], posstb[i + 1, 1], s=1000 * 256 / a,
                       edgecolor="white", facecolor="none", alpha=0.25)
            ax.scatter(posstb[i + 1, 0], posstb[i + 1, 1], marker='+',
                       color="red")
            plt.text((posstb[i + 1, 0] + posstb[0, 0]) / 2 + corrlabels[i, 0],
                     (posstb[i + 1, 1] + posstb[0, 1]) / 2 + corrlabels[i, 1],
                     "%.1f mas\n%.1f deg" % (distco[i] * mas_pix, angleco[i]),
                     color="orange", ha="center", va="center")
        plt.plot([
                cny - rn * m.cos(np.deg2rad(pad)), cny,
                cny - rn * m.sin(np.deg2rad(pad))
        ], [
                cnx - rn * m.sin(np.deg2rad(pad)), cnx,
                cnx + rn * m.cos(np.deg2rad(pad))
        ], color="yellow")
        plt.text(cny - rn2 * m.cos(np.deg2rad(pad)),
                 cnx - rn2 * m.sin(np.deg2rad(pad)), "N", color="yellow",
                 ha="center", va="center")
        plt.text(cny - rn2 * m.sin(np.deg2rad(pad)),
                 cnx + rn2 * m.cos(np.deg2rad(pad)), "E", color="yellow",
                 ha="center", va="center")
        plt.savefig("%s%s_Binary_%s.png" % (savepath, timestamp, target),
                    overwrite=True)
        pf.writeto("%s%s_Binary_%s.fits" % (savepath, timestamp, target),
                   im[1:, 1:] / np.max(im), overwrite=True)

        fig, ax = plt.subplots()
        plt.imshow(
                np.log10(np.abs(psf_fit(x, y)[1:, 1:] / np.max(psf_fit(x, y)))),
                cmap="inferno",
                extent=[(-cx + 0.5) * as_pix, (cx - 0.5) * as_pix,
                        (cy - 0.5) * as_pix, (-cy + 0.5) * as_pix])
        plt.clim([-4, 0])
        cbar = plt.colorbar()
        cbar.ax.set_ylabel("Contrast")
        if strehlcalc:
            ax.set(xlabel="Angle [arcsec]", ylabel="Angle [arcsec]",
                   title="%s, Strehl ratio: %.2f" % (target, strehl))
        else:
            ax.set(xlabel="Angle [arcsec]", ylabel="Angle [arcsec]",
                   title="%s" % target)
        ax.scatter(posstb[0, 0], posstb[0, 1], s=1000 * 256 / a,
                   edgecolor="white", facecolor="none", alpha=0.25)
        ax.scatter(posstb[0, 0], posstb[0, 1], marker='+', color="red")
        plt.plot(posstb[:, 0], posstb[:, 1], color="orange", alpha=0.5)
        for i in range(nst + int(retroinj) - 1):
            ax.scatter(posstb[i + 1, 0], posstb[i + 1, 1], s=1000 * 256 / a,
                       edgecolor="white", facecolor="none", alpha=0.25)
            ax.scatter(posstb[i + 1, 0], posstb[i + 1, 1], marker='+',
                       color="red")
            plt.text((posstb[i + 1, 0] + posstb[0, 0]) / 2 + corrlabels[i, 0],
                     (posstb[i + 1, 1] + posstb[0, 1]) / 2 + corrlabels[i, 1],
                     "%.1f mas\n%.1f deg" % (distco[i] * mas_pix, angleco[i]),
                     color="orange", ha="center", va="center")
        plt.plot([
                cny - rn * m.cos(np.deg2rad(pad)), cny,
                cny - rn * m.sin(np.deg2rad(pad))
        ], [
                cnx - rn * m.sin(np.deg2rad(pad)), cnx,
                cnx + rn * m.cos(np.deg2rad(pad))
        ], color="yellow")
        plt.text(cny - rn2 * m.cos(np.deg2rad(pad)),
                 cnx - rn2 * m.sin(np.deg2rad(pad)), "N", color="yellow",
                 ha="center", va="center")
        plt.text(cny - rn2 * m.sin(np.deg2rad(pad)),
                 cnx + rn2 * m.cos(np.deg2rad(pad)), "E", color="yellow",
                 ha="center", va="center")
        plt.savefig("%s%s_Binary_%s_fit.png" % (savepath, timestamp, target),
                    overwrite=True)
        pf.writeto("%s%s_Binary_%s_fit.fits" % (savepath, timestamp, target),
                   psf_fit(x, y)[1:, 1:] / np.max(psf_fit(x, y)),
                   overwrite=True)

    if verbose:
        txt = "TARGET: %s\n" % (target, )
        txt += "IMAGE ROTATOR PAD: %.2f deg\n" % (pad, )
        if strehlcalc:
            txt += "STREHL RATIO: %.2f\n" % strehl
        for i in range(nst + int(retroinj) - 1):
            if nst + int(retroinj) > 2:
                txt += "COMPANION #%d\n" % (i + 1, )
            txt += "SEPARATION: %.1f mas\n" % (distco[i] * mas_pix, )
            txt += "POSITION ANGLE: %.1f deg\n" % (angleco[i], )
            if contrast[i + 1] > 0:
                txt += "CONTRAST: %.2e (%.1f)\n" % (contrast[i + 1], -2.5 *
                                                    m.log10(contrast[i + 1]))
            else:
                txt += "CONTRAST: %.2e\n" % contrast[i + 1]
        print(txt)

        txtfile = open("%s%s_Binary_%s_log.txt" % (savepath, timestamp, target),
                       "w")
        txtfile.write(txt)
        txtfile.close()

    return (posst, xoff, yoff, strehl, dia_ring, distco * mas_pix, angleco,
            contrast)
