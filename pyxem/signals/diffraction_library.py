# -*- coding: utf-8 -*-
# Copyright 2017-2018 The pyXem developers
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

class DiffractionLibrary(dict):
    """Maps crystal structure (phase) and orientation (Euler angles or
    axis-angle pair) to simulated diffraction data.
    """

    ## Possibly obsolete after the changes to DiffractionLibrary
    def set_calibration(self, calibration):
        """Sets the scale of every diffraction pattern simulation in the
        library.

        Parameters
        ----------
        calibration : {:obj:`float`, :obj:`tuple` of :obj:`float`}, optional
            The x- and y-scales of the patterns, with respect to the original
            reciprocal angstrom coordinates.

        """
        for key in self.keys():
            diff_lib = self[key]
            for diffraction_pattern in diff_lib.values():
                diffraction_pattern.calibration = calibration

    ## Again, may well be obsolete
    def set_offset(self, offset):
        """Sets the offset of every diffraction pattern simulation in the
        library.

        Parameters
        ----------
        offset : :obj:`tuple` of :obj:`float`, optional
            The x-y offset of the patterns in reciprocal angstroms. Defaults to
            zero in each direction.

        """
        assert len(offset) == 2
        for key in self.keys():
            diff_lib = self[key]
            for diffraction_pattern in diff_lib.values():
                diffraction_pattern.offset = offset

    def plot(self):
        """Plots the library interactively.
        """
        from pyxem.signals.electron_diffraction import ElectronDiffraction
        sim_diff_dat = []
        for key in self.keys():
            for ori in self[key].keys():
                dpi = self[key][ori]['Sim'].as_signal(128, 0.03, 1)
                sim_diff_dat.append(dpi.data)
        ppt_test = ElectronDiffraction(sim_diff_dat)
        ppt_test.plot()
