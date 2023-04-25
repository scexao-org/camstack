#!/usr/bin/env python

import numpy as np
from scipy.ndimage import median_filter
import copy
import scipy.optimize as opt
from scipy.fftpack import fftfreq
from astropy.modeling import models, fitting
import math as m
import matplotlib.pyplot as plt
plt.ion()

fitter = fitting.LevMarLSQFitter()

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
        n2 = n-1
    else:
        n2 = n
    
    if loga == 1:
        ramptemp = np.array(map(float, range(n)))*(m.log10(b)-m.log10(a))/n2+m.log10(a)
        ramp = np.power(10,ramptemp)
    else:
        ramp = np.array(map(float, range(n)))*(b-a)/n2+a
    
    return ramp

# ========= HOT PIXELS ==================================
#========================================================
def find_outlier_pixels(data,tolerance=3,worry_about_edges=True):
    #This function finds the hot or dead pixels in a 2D dataset. 
    #tolerance is the number of standard deviations used to cutoff the hot pixels
    #If you want to ignore the edges and greatly speed up the code, then set
    #worry_about_edges to False.
    #
    #The function returns a list of hot pixels and also an image with with hot pixels removed
    blurred = median_filter(data, size=2)
    difference = data - blurred
    threshold = tolerance*np.std(difference)

    #find the hot pixels, but ignore the edges
    hot_pixels = np.nonzero((np.abs(difference[1:-1,1:-1])>threshold) )
    hot_pixels = np.array(hot_pixels) + 1 #because we ignored the first row and first column

    fixed_image = copy.deepcopy(data) #This is the image with the hot pixels removed
    for y,x in zip(hot_pixels[0],hot_pixels[1]):
        fixed_image[y,x]=blurred[y,x]

    if worry_about_edges == True:
        height,width = np.shape(data)

        ###Now get the pixels on the edges (but not the corners)###

        #left and right sides
        for index in range(1,height-1):
            #left side:
            med  = np.median(data[index-1:index+2,0:2])
            diff = np.abs(data[index,0] - med)
            if diff>threshold: 
                hot_pixels = np.hstack(( hot_pixels, [[index],[0]]  ))
                fixed_image[index,0] = med

            #right side:
            med  = np.median(data[index-1:index+2,-2:])
            diff = np.abs(data[index,-1] - med)
            if diff>threshold: 
                hot_pixels = np.hstack(( hot_pixels, [[index],[width-1]]  ))
                fixed_image[index,-1] = med

        #Then the top and bottom
        for index in range(1,width-1):
            #bottom:
            med  = np.median(data[0:2,index-1:index+2])
            diff = np.abs(data[0,index] - med)
            if diff>threshold: 
                hot_pixels = np.hstack(( hot_pixels, [[0],[index]]  ))
                fixed_image[0,index] = med

            #top:
            med  = np.median(data[-2:,index-1:index+2])
            diff = np.abs(data[-1,index] - med)
            if diff>threshold: 
                hot_pixels = np.hstack(( hot_pixels, [[height-1],[index]]  ))
                fixed_image[-1,index] = med

        ###Then the corners###

        #bottom left
        med  = np.median(data[0:2,0:2])
        diff = np.abs(data[0,0] - med)
        if diff>threshold: 
            hot_pixels = np.hstack(( hot_pixels, [[0],[0]]  ))
            fixed_image[0,0] = med

        #bottom right
        med  = np.median(data[0:2,-2:])
        diff = np.abs(data[0,-1] - med)
        if diff>threshold: 
            hot_pixels = np.hstack(( hot_pixels, [[0],[width-1]]  ))
            fixed_image[0,-1] = med

        #top left
        med  = np.median(data[-2:,0:2])
        diff = np.abs(data[-1,0] - med)
        if diff>threshold: 
            hot_pixels = np.hstack(( hot_pixels, [[height-1],[0]]  ))
            fixed_image[-1,0] = med

        #top right
        med  = np.median(data[-2:,-2:])
        diff = np.abs(data[-1,-1] - med)
        if diff>threshold: 
            hot_pixels = np.hstack(( hot_pixels, [[height-1],[width-1]]  ))
            fixed_image[-1,-1] = med

    return hot_pixels,fixed_image


# ========= CENTROID ====================================
# =======================================================

def centroid(image,bias=[],subt_bias=True, fact=0.01):
    if not subt_bias:
        image2 = image-bias
    else:
        image2 = copy.deepcopy(image)
    imax = np.max(image2)
    imin  = fact*imax
    image2 -= imin
    mask = image2 > 0
    image2 *= mask
    total = np.nansum(image2)
    X, Y = np.indices(np.shape(image2))
    cy = (np.nansum(X*image2)/total)
    cx = (np.nansum(Y*image2)/total)
    cx += 0.5
    cy += 0.5
    return [cx, cy]

# ========= RADIAL PROFILE ==============================
# =======================================================

def radial_data(data,annulus_width=1,working_mask=None,x=None,y=None,rmax=None):
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
    
    if working_mask==None:
        working_mask = np.ones(data.shape,bool)
    
    npix, npiy = data.shape
    #print(npix, npiy)
    try:
        if x==None or y==None:
            x1 = np.arange(-npix/2.,npix/2.)
            y1 = np.arange(-npiy/2.,npiy/2.)
            x,y = np.meshgrid(y1,x1)
    except:
        print("x and y provided")

    r = abs(x+1j*y)

    if rmax==None:
        rmax = r[working_mask].max()

    #---------------------
    # Prepare the data container
    #---------------------
    dr = np.abs([x[0,0] - x[0,1]]) * annulus_width
    #print("test",annulus_width,dr, x[0,:])
    radial = np.arange(rmax/dr)*dr + dr/2.
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
    for irad in range(nrad): #= 1:numel(radial)
      minrad = irad*dr
      maxrad = minrad + dr
      thisindex = (r>=minrad) * (r<maxrad) * working_mask
      if not thisindex.ravel().any():
        radialdata.mean[irad] = np.nan
        radialdata.std[irad]  = np.nan
        radialdata.median[irad] = np.nan
        radialdata.numel[irad] = np.nan
        radialdata.max[irad] = np.nan
        radialdata.min[irad] = np.nan
      else:
        radialdata.mean[irad] = np.nanmean(data[thisindex])
        radialdata.std[irad]  = data[thisindex].std()
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

def shift_fft(input_array,shift):
    shift_rows,shift_cols = shift
    nr,nc = input_array.shape
    Nr, Nc = fftfreq(nr), fftfreq(nc)
    Nc,Nr = np.meshgrid(Nc,Nr)
    fft_inputarray = np.fft.fft2(input_array)
    fourier_shift = np.exp(1j*2*np.pi*((shift_rows*Nr)+(shift_cols*Nc)))
    output_array = np.fft.ifft2(fft_inputarray*fourier_shift)
    return np.real(output_array)


# ========= 2D GAUSSIAN =================================
# =======================================================

def twoD_Gaussian(coor, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    (x,y) = coor
    xo = float(xo)
    yo = float(yo)    
    a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
    b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
    c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
    g = offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo) 
                            + c*((y-yo)**2)))
    return g.ravel()


# ========= 2D GAUSSIAN FIT =============================
# =======================================================

def fit_TwoD_Gaussian(img, xc, yc, rad):
    model_init = models.Gaussian2D(amplitude=np.max(img), x_mean=xc, y_mean=yc, x_stddev=rad, y_stddev=rad, theta = 0)
    nx = img.shape[0]
    ny = img.shape[1]
    
    x, y = np.mgrid[:nx,:ny]

    gauss2_fit = fitter(model_init,x,y,img)

    return gauss2_fit
