#!/usr/bin/env python
"""
Convert cassbeam output Jones dat files into FITS beams for meqtrees

Assumes cassbeam output files contain freq information in the filename of the form <prefix>-<freq>MHz.jones.dat
"""

import sys,os
import datetime
import pyfits as pf
import numpy as n

if __name__ == '__main__':
    from optparse import OptionParser
    o = OptionParser()
    o.set_usage('%prog [options] <CASSBEAM DAT FILES>')
    o.set_description(__doc__)
    o.add_option('-c','--clobber',dest='clobber',action='store_true',
        help='Clobber/overwrite output FITS files if they exist')
    o.add_option('-o','--output',dest='output',default='cassBeam_',
        help='Output FITS filename prefix')
    o.add_option('-p','--pixel',dest='pixel',type='float',default=0.01,
        help='Pixel scale factor in degrees, this is the beampixelscale in the cassbeam output parameter file, default: 0.01')
    opts, args = o.parse_args(sys.argv[1:])

    freqs=[]
    beamCube=[]
    for fid,fn in enumerate(args):
        freq=float(fn.split('MHz')[0].split('-')[-1]) #parse filename for frequency
        print 'Reading %s (%i of %i), frequency is %f MHz'%(fn,fid+1,len(args),freq)
        freqs.append(freq)
        data=n.fromfile(fn,dtype=float,sep=' ')
        data=data.reshape((data.shape[0]/8,8))
        beamCube.append(data)
    freqs=n.array(freqs)*1e6
    beamCube=n.array(beamCube)

    dim=int(n.sqrt(beamCube.shape[1]))
    beamCube=beamCube.reshape((beamCube.shape[0],dim,dim,8))

    #normalize cube so that peak value is 1.0, is this legit or required?
    beamCube/=n.max(n.abs(beamCube))
    
    #generate a fits beam header
    templateCube=n.zeros((1,beamCube.shape[0],dim,dim),dtype=float)
    hdu=pf.PrimaryHDU(templateCube)

    ctime=datetime.datetime.today()
    hdu.header.set('DATE','%s'%ctime)
    hdu.header.set('DATE-OBS','%s'%ctime)
    hdu.header.set('ORIGIN', 'RATT')
    hdu.header.set('TELESCOP', 'VLA')
    hdu.header.set('OBJECT', 'beam')
    hdu.header.set('EQUINOX', 2000.0)

    print 'Using pixel scale factor: %f radians'%opts.pixel
    # note: defining M as the fastest moving axis (FITS uses
    # FORTRAN-style indexing) produces an image that when
    # viewed with kview / ds9 etc looks correct on the sky 
    # with M increasing to left and L increasing toward top
    # of displayed image
    if beamCube.shape[1]%2==0: crpixVal=int(beamCube.shape[1]/2)
    else: crpixVal=int(((beamCube.shape[1]-1)/2)+1)

    hdu.header.set('CTYPE1', 'X', 'points right on the sky')
    hdu.header.set('CUNIT1', 'DEG')
    hdu.header.set('CDELT1', opts.pixel, 'degrees')
    hdu.header.set('CRPIX1', crpixVal, 'reference pixel (one relative)')
    hdu.header.set('CRVAL1', 0.0, '')
    hdu.header.set('CTYPE2', 'Y', 'points up on the sky')
    hdu.header.set('CUNIT2', 'DEG')
    hdu.header.set('CDELT2', opts.pixel, 'degrees')
    hdu.header.set('CRPIX2', crpixVal, 'reference pixel (one relative)')
    hdu.header.set('CRVAL2', 0.0, '')

    #determine frequency step by assuming equal frequency steps and taking the difference of the first two frequencies
    sortFreqs=n.sort(freqs)
    if freqs.shape[0]>1: freqStep=(sortFreqs[-1]-sortFreqs[0])/freqs.shape[0];
    else: freqStep=1.
    hdu.header.set('CTYPE3', 'FREQ')
    hdu.header.set('CDELT3', freqStep, 'frequency step in Hz')
    hdu.header.set('CRPIX3', 1, 'reference frequency postion')
    hdu.header.set('CRVAL3', sortFreqs[0], 'reference frequency')
    hdu.header.set('CTYPE4', 'STOKES')
    hdu.header.set('CDELT4', 1) 
    hdu.header.set('CRPIX4', 1)
    hdu.header.set('CRVAL4', -5)
    
    # in case the frequency range is irregularly sampled, add keywords giving the actual frequency values
    for i,fq in enumerate(sortFreqs):
      hdu.header.set('GFREQ%d'%(i+1),fq);

    # create initial HDUList
    hdulist = pf.HDUList([hdu])
    
    # normalize beam cube to peak gain of 1 in I
    # I beam is 1/2{sum |J_ij|^2}
    peakgain = (0.5*(beamCube**2).sum(3)).max()
    beamCube /= peakgain
    print "Peak gain is %f, normalizing to unity" % peakgain

    #for XX,XY,YX,YY,real,imag: write a fits file
    #for pid,pol in enumerate(['xx','xy','yx','yy']):   # Griffin's old code -- pretty sure xy and yx are swapped
    # for pid,pol in enumerate(['rr','lr','rl','ll']):  
    # see https://github.com/ratt-ru/calibration-pipelines/issues/34#issuecomment-103791910
    # seems cassbeam has RL swapped, so... 
    for pid,pol in enumerate(['ll','rl','lr','rr']):
        for cid,cmplx in enumerate(['re','im','ampl']):
            #write data to FITS data
            if cmplx is 'ampl':
                hdu.data = abs(beamCube[:,:,:,2*pid] + 1j*beamCube[:,:,:,2*pid+1])
            else:
                hdu.data = beamCube[:,:,:,2*pid+cid]
            ofn="%s%s_%s.fits" % ( opts.output, pol, cmplx )
            if opts.clobber or not os.path.exists(ofn): 
                hdulist.writeto(ofn,clobber=opts.clobber)
            else: 
                print 'File: %s exists, and clobber parameter not set, skipping'%ofn
                
