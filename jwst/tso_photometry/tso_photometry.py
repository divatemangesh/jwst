from collections import OrderedDict

import numpy as np
from astropy.table import QTable
import astropy.units as u
from astropy.time import Time, TimeDelta
from photutils import aperture_photometry, CircularAperture, CircularAnnulus

from ..datamodels import CubeModel


def tso_aperture_photometry(datamodel, xcenter, ycenter, radius, radius_inner,
                            radius_outer):
    """
    Create a photometric catalog for NIRCam TSO imaging observations.

    Parameters
    ----------
    datamodel : `CubeModel`
        The input `CubeModel` of a NIRCam TSO imaging observation.

    xcenter, ycenter : float
        The ``x`` and ``y`` center of the aperture.

    radius : float
        The radius (in pixels) of the circular aperture.

    radius_inner, radius_outer : float
        The inner and outer radii (in pixels) of the circular-annulus
        aperture, used for local background estimation.

    Returns
    -------
    catalog : `~astropy.table.QTable`
        An astropy QTable (Quantity Table) containing the source
        photometry.
    """

    if not isinstance(datamodel, CubeModel):
        raise ValueError('The input data model must be a CubeModel.')

    aper1 = CircularAperture((xcenter, ycenter), r=radius)
    aper2 = CircularAnnulus((xcenter, ycenter), r_in=radius_inner,
                            r_out=radius_outer)

    nimg = datamodel.data.shape[0]
    aperture_sum = []
    aperture_sum_err = []
    annulus_sum = []
    annulus_sum_err = []

    for i in np.arange(nimg):
        tbl1 = aperture_photometry(datamodel.data[i, :, :], aper1,
                                   error=datamodel.err[i, :, :])
        tbl2 = aperture_photometry(datamodel.data[i, :, :], aper2,
                                   error=datamodel.err[i, :, :])

        aperture_sum.append(tbl1['aperture_sum'][0])
        aperture_sum_err.append(tbl1['aperture_sum_err'][0])
        annulus_sum.append(tbl2['aperture_sum'][0])
        annulus_sum_err.append(tbl2['aperture_sum_err'][0])

    # convert array of Quantities to Quantity arrays
    aperture_sum = u.Quantity(aperture_sum)
    aperture_sum_err = u.Quantity(aperture_sum_err)
    annulus_sum = u.Quantity(annulus_sum)
    annulus_sum_err = u.Quantity(annulus_sum_err)

    # construct metadata for output table
    meta = OrderedDict()
    meta['instrument'] = datamodel.meta.instrument.name
    meta['detector'] = datamodel.meta.instrument.detector
    meta['channel'] = datamodel.meta.instrument.channel
    meta['subarray'] = datamodel.meta.subarray.name
    meta['filter'] = datamodel.meta.instrument.filter
    meta['pupil'] = datamodel.meta.instrument.pupil

    meta['target_name'] = datamodel.meta.target.catalog_name
    meta['xcenter'] = xcenter
    meta['ycenter'] = ycenter
    ra_icrs, dec_icrs = datamodel.meta.wcs(xcenter, ycenter)
    meta['ra_icrs'] = ra_icrs
    meta['dec_icrs'] = dec_icrs

    info = ('Photometry measured in a circular aperture of r={0} pixels. '
            'Background calculated as the mean in a circular annulus with '
            'r_inner={1} pixels and r_outer={2} pixels.'
            .format(radius, radius_inner, radius_outer))
    meta['apertures'] = info

    tbl = QTable(meta=meta)

    dt = (datamodel.meta.exposure.group_time *
          (datamodel.meta.exposure.ngroups + 1))
    dt_arr = (np.arange(1, 1 + datamodel.meta.exposure.nints) *
              dt - (dt / 2.))
    int_dt = TimeDelta(dt_arr, format='sec')
    int_times = (Time(datamodel.meta.exposure.start_time, format='mjd') +
                 int_dt)
    tbl['MJD'] = int_times.mjd

    tbl['aperture_sum'] = aperture_sum
    tbl['aperture_sum_err'] = aperture_sum_err
    tbl['annulus_sum'] = annulus_sum
    tbl['annulus_sum_err'] = annulus_sum_err

    annulus_mean = annulus_sum / aper2.area()
    annulus_mean_err = annulus_sum_err / aper2.area()
    tbl['annulus_mean'] = annulus_mean
    tbl['annulus_mean_err'] = annulus_mean_err

    aperture_bkg = annulus_mean * aper1.area()
    aperture_bkg_err = annulus_mean_err * aper1.area()
    tbl['aperture_bkg'] = aperture_bkg
    tbl['aperture_bkg_err'] = aperture_bkg_err

    net_aperture_sum = aperture_sum - aperture_bkg
    net_aperture_sum_err = np.sqrt(aperture_sum_err ** 2 +
                                   aperture_bkg_err ** 2)
    tbl['net_aperture_sum'] = net_aperture_sum
    tbl['net_aperture_sum_err'] = net_aperture_sum_err

    return tbl
