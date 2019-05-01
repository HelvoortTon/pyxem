# -*- coding: utf-8 -*-
# Copyright 2017-2019 The pyXem developers
#
# This file is part of pyXem.
#
# pyXem is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyXem is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyXem.  If not, see <http://www.gnu.org/licenses/>.

"""Electron diffraction pattern calibration operations.

"""

import numpy as np
from scipy.optimize import curve_fit
from math import sin, cos

from pyxem.signals.electron_diffraction import ElectronDiffraction
from pyxem.utils.calibration_utils import call_ring_pattern, \
                                          calc_radius_with_distortion

class CalibrationGenerator():
    """Obtains calibration information from common reference standards.

    Parameters
    ----------
    signal : ElectronDiffraction
        The signal of electron diffraction data to be used for calibration.
    standard : string
        Identifier for calibration standard used. At present only "au-x-grating"
        is supported.

    """
    def __init__(self,
                 diffraction_pattern=None,
                 navigation_image=None,
                 standard='au-x-grating'):
        # Verify calibration standard is recognized and set attribute.
        standard_dict = {
            'au-x-grating': 'au-x-grating',
        }
        # Raise a warning if no calibration data is provided.
        if diffraction_pattern is None and navigation_image is None:
            raise ValueError("No calibration data has been provided!")
        if standard in standard_dict:
            self.standard = standard_dict[standard]
        else:
            raise NotImplementedError("The standard `{}` is not recognized. "
                                      "See documentation for available "
                                      "implementations.".format(standard))
        # Check calibration data provided as ElectronDiffraction object.
        if isinstance(diffraction_pattern, ElectronDiffraction) is False:
            raise ValueError("Data for calibration must be provided as an "
                             "ElectronDiffraction object.")
        # Set diffraction patttern in attribute after checking standard form.
        if diffraction_pattern.axes_manager.navigation_shape:
            raise ValueError("Calibration using au-x-grating data requires "
                             "a single diffraction pattern to be provided.")
        else:
            self.diffraction_pattern = diffraction_pattern
        # Set navigation image in attribute.
        if navigation_image:
            self.navigation_image = navigation_image
        # Assign attributes for calibration values to be determined
        self.affine_matrix = None
        self.diffraction_rotation = None
        self.diffraction_calibration = None
        self.navigation_calibration = None

    def get_elliptical_distortion(self, mask_radius, scale=100, amplitude=1000,
                                  spread=2, direct_beam_amplitude=500,
                                  asymmetry=1, rotation=0):
        """Determine elliptical distortion of the diffraction pattern.

        Parameters
        ----------
        mask_radius : int
            The radius in pixels for a mask over the direct beam disc
            (the direct beam disc within given radius will be excluded
            from the fit)
        scale : float
            An initial guess for the diffraction calibration
            in 1/Angstrom units
        amplitude : float
            An initial guess for the amplitude of the polycrystalline rings
            in arbitrary units
        spread : float
            An initial guess for the spread within each ring (Gaussian width)
        direct_beam_amplitude : float
            An initial guess for the background intensity from the direct
            beam disc in arbitrary units
        asymmetry : float
            An initial guess for any elliptical asymmetry in the
            pattern (for a perfectly circular pattern asymmetry=1)
        rotation : float
            An initial guess for the rotation of the (elliptical) pattern
            in radians.

        Returns
        -------
        fit_params : np.array()
            Array of fitting parameters. [scale, amplitude, spread,
                                          direct_beam_amplitude, asymmetry,
                                          rotation].
        affine_matrix : np.array()
            Array defining the affine transformation that corrects for lens
            distortions in the diffraction pattern.

        See Also
        --------
            pyxem.utils.calibration_utils.call_ring_pattern

        """
        # Check that necessary calibration data is provided
        if self.diffraction_pattern is None:
            raise ValueError("This method requires a diffraction_pattern to be "
                             "specified.")
        # Set diffraction pattern variable
        standard_dp = self.diffraction_pattern
        # Define grid values and center indices for ring pattern evaluation
        image_size = standard_dp.data.shape[0]
        xi = np.linspace(0, image_size - 1, image_size)
        yi = np.linspace(0, image_size - 1, image_size)
        x, y = np.meshgrid(xi, yi)
        xcenter = (image_size - 1) / 2
        ycenter = (image_size - 1) / 2
        # Calculate eliptical parameters
        mask = calc_radius_with_distortion(x, y, (image_size - 1) / 2,
                                           (image_size - 1) / 2, 1, 0)
        # Mask direct beam
        mask[mask > mask_radius] = 0
        standard_dp.data[mask > 0] *= 0
        # Manipulate measured data for fitting
        ref = standard_dp.data[standard_dp.data > 0]
        ref = ref.ravel()
        # Define points for fitting
        pts = np.array([x[standard_dp.data > 0].ravel(),
                        y[standard_dp.data > 0].ravel()]).ravel()
        # Set initial parameters for fitting
        x0 = [scale, amplitude, spread, direct_beam_amplitude, asymmetry, rotation]
        # Fit ring pattern to experimental data
        xf, cov = curve_fit(call_ring_pattern(xcenter, ycenter),
                            pts, ref, p0=x0)
        # Calculate affine transform parameters from fit parameters
        scaling = np.array([[1, 0],
                            [0, xf[4]**-0.5]])

        rotation = np.array([[cos(xf[5]), -sin(xf[5])],
                             [sin(xf[5]),  cos(xf[5])]])

        correction = np.linalg.inv(np.dot(rotation.T,
                                          np.dot(scaling, rotation)))

        affine = np.array([[correction[0,0], correction[0,1], 0.00],
                           [correction[1,0], correction[1,1], 0.00],
                           [0.00, 0.00, 1.00]])

        self.affine_matrix = affine

        return affine

    def get_distortion_residuals(self, mask_radius, spread):
        """Determine the diffraction pattern pixel size calibration.

        Parameters
        ----------
        mask_radius : int
            The radius in pixels for a mask over the direct beam disc
            (the direct beam disc within given radius will be excluded
            from the fit)
        spread : float
            An initial guess for the spread within each ring (Gaussian width)

        Returns
        -------
        diff_init : ElectronDiffraction
            Difference between experimental data and simulated symmetric ring
            pattern.
        diff_end : ElectronDiffraction
            Difference between distortion corrected data and simulated symmetric
            ring pattern.
        """
        # Check all required parameters are defined as attributes
        if self.diffraction_pattern is None:
            raise ValueError("This method requires a diffraction_pattern to be "
                             "specified.")
        if self.affine_matrix is None:
            raise ValueError("This method requires a distortion matrix to have "
                             "been determined. Use get_elliptical_distortion "
                             "to determine this matrix.")
        # Set name for experimental data pattern
        dpeg = self.diffraction_pattern
        dpref = call_ring_pattern(mask=True, mask_radius=mask_radius,
                                  scale=ringP[0],
                                  amplitude=ringP[1],
                                  spread=spread,
                                  direct_beam_amplitude=ringP[3],
                                  asymmetry=1, rotation=ringP[5])
        # Apply distortion corrections to experimental data
        dpegs = pxm.stack_method([dpeg, dpeg, dpeg, dpeg])
        dpegs = pxm.ElectronDiffraction(dpegs.data.reshape((2,2,256,256)))
        dpegs.apply_affine_transformation(self.affine_matrix,
                                          preserve_range=True,
                                          inplace=True)
        # Calculate residuals to be returned
        diff_init = ElectronDiffraction(dpeg.data - dpref.data)
        diff_end = ElectronDiffraction(dpegs.inav[0,0].data - dpref.data)

        return diff_init, diff_end

    def get_diffraction_calibration(self):
        """Determine the diffraction pattern pixel size calibration.

        Parameters
        ----------

        Returns
        -------
        diff_cal : float
            Diffraction calibration in reciprocal angstroms per pixel.

        """
        # Check that necessary calibration data is provided
        if self.diffraction_pattern is None:
            raise ValueError("This method requires a diffraction_pattern to be "
                             "specified.")
        # Define line roi along which to take trace for calibration
        line = Line2DROI()
        # Obtain line trace
        trace = line(self.signal)
        # Find peaks in line trace
        peaks = trace.find_peaks()
        # Determine diffraction calibration from peak positions
        diff_cal = 0.01

        return diff_cal

    def get_navigation_calibration(self):
        """Determine the diffraction pattern pixel size calibration.

        Parameters
        ----------

        Returns
        -------
        nav_cal : float
            Navigation calibration in nanometres per pixel.

        """
        # Check that necessary calibration data is provided
        if self.navigation_image is None:
            raise ValueError("This method requires a navigation_image to be "
                             "specified.")
        # Define line roi along which to take trace for calibration
        line = Line2DROI()
        # Obtain line trace
        trace = line(self.signal)
        # Find peaks in line trace
        peaks = trace.find_peaks()
        # Determine diffraction calibration from peak positions
        nav_cal = 1

        return nav_cal

    def get_calibration_dictionary(self):
        """Get determined calibration values as a dictionary.

        Returns
        -------
        calibration_dictionary : dict()
            Dictionary of calibration values.
        """
        # Construct calibration dictionary from object attributes.

        return calibration_dictionary

    def save_calibration_dictionary(self):
        """Get determined calibration values as a dictionary.

        Returns
        -------
        calibration_dictionary : dict()
            Dictionary of calibration values.
        """
        # Construct calibration dictionary from object attributes.

        return calibration_dictionary
