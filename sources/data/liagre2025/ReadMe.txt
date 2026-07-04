J/A+A/702/A144          Beyond the Nyquist frequency             (Liagre+, 2025)
================================================================================
Beyond the Nyquist frequency: Asteroseismic catalog of undersampled Kepler late
subgiants and early red giants.
    Liagre B., Garcia R.A., Mathur S., Pinsonneault M.H., Serenelli A.,
    Zinn J.C., Cao K., Godoy-Rivera D., Tayar J., Beck P.G., Grossmann D.H.,
    Palakkatharappil D.B.
    <Astron. Astrophys. 702, A144 (2025)>
    =2025A&A...702A.144L        (SIMBAD/NED BibCode)
================================================================================
ADC_Keywords: Asteroseismology ; Stars, giant ; Abundances ; Optical ;
              Morphology
Keywords: asteroseismology - methods: data analysis - stars: evolution -
          stars: interiors - stars: oscillations

Abstract:
    Subgiants and early red giants are crucial for studying the first
    dredge-up, a key evolutionary phase in which the convective envelope
    deepens, mixing previously interior-processed material and bringing it
    to the surface. Yet, very few have been seismically characterized with
    Kepler because their oscillation frequencies are close to the 30
    minute sampling frequency of the mission. We developed a new method as
    part of the new PyA2Z code of identifying super-Nyquist oscillators
    and inferring their global seismic parameters, {nu}max and large
    separation, {Delta}{nu}.

    Applying PyA2Z to 2065 Kepler targets, we seismically characterize 285
    super-Nyquist and 168 close-to-Nyquist stars with masses from 0.8 to
    1.6M_{sun}_. In combination with APOGEE spectroscopy, Gaia
    spectrophotometry, and stellar models, we derive stellar ages for the
    sample. There is good agreement between the predicted and actual
    positions of stars on the HR diagram (luminosity vs. effective
    temperature) as a function of mass and composition. While the timing
    of dredge-up is consistent with predictions, the magnitude and mass
    dependence show discrepancies with models, possibly due to
    uncertainties in model physics or calibration issues in observed
    abundance scales.

Description:
    The catalog.dat contains the full set of asteroseismic (and
    spectroscopic parameters) derived for 2065 Kepler stars. The catalog
    is based on Kepler long-cadence photometry combined with APOGEE
    spectra, Gaia DR3 astrometry, and literature values. Stellar masses,
    radii, and ages are computed using standard corrected seismic scaling
    relations. Uncertainties are provided for all measured quantities.

File Summary:
--------------------------------------------------------------------------------
 FileName      Lrecl  Records   Explanations
--------------------------------------------------------------------------------
ReadMe            80        .   This file
catalog.dat      500     2065   Asteroseismic and spectroscopic catalog
--------------------------------------------------------------------------------

See also:
   V/133  : Kepler Input Catalog (Kepler Mission Team, 2009)
   IV/39  : TESS Input Catalog version 8.2 (TIC v8.2) (Paegert+, 2021)
   I/355  : Gaia DR3 Part 1. Main source (Gaia Collaboration, 2022)
   II/246 : 2MASS All-Sky Catalog of Point Sources (Cutri+ 2003)

Byte-by-byte Description of file: catalog.dat
--------------------------------------------------------------------------------
   Bytes Format Units     Label      Explanations
--------------------------------------------------------------------------------
   1-  8  I8    ---       KIC        ?=- Kepler Input Catalog identifier
  10- 29 F20.15 uHz       numax      ?=- Frequency of maximum oscillation power
  31- 50 F20.15 uHz       Dnu        ?=- Large frequency separation
  52- 72 F21.16 uHz     e_numax      ?=- Uncertainty on Numax
  74- 97 F24.19 uHz     e_Dnu        ?=- Uncertainty on Dnu
  99-118  A20   ---       Cat        Category (super-Nyquist, sub-Nyquist, etc.)
 120-127  F8.4  ---       [alpha/Fe] ?=- Abundance [alpha/Fe]
 129-136  F8.4  ---     e_[alpha/Fe] ?=- Uncertainty on [alpha/Fe]
 138-143  F6.4  [cm/s2]   loggSpec   ? Spectroscopic surface gravity
 145-150  F6.4  [cm/s2] e_loggSpec   ? Uncertainty on spectroscopic logg
 152-161  F10.4 ---       [C/Fe]     ?=- Abundance [C/Fe]
 163-172  F10.4 ---     e_[C/Fe]     ?=- Uncertainty on [C/Fe]
 174-183  F10.4 ---       [N/Fe]     ?=- Abundance [N/Fe]
 185-194  F10.4 ---     e_[N/Fe]     ?=- Uncertainty on [N/Fe]
 196-215 F20.18 1/Rsun    InvRGaia   ? Inverse Gaia Radius
 217-237 F21.19 1/Rsun  e_InvRGaia   ? Uncertainty on inverse Gaia Radius
 239-245  F7.5  [cm/s2]   loggseis   ? Seismic surface gravity
 247-255  F9.7  [cm/s2] e_loggseis   ? Uncertainty on seismic logg
 257-264  F8.6  Msun      Mass       ? Stellar mass
 266-285 F20.18 Msun    e_Mass       ? Uncertainty on stellar mass
 287-295  F9.6  Rsun      Radius     ? Stellar radius
 297-316 F20.18 Rsun    e_Radius     ? Uncertainty on stellar radius
 318-325  F8.6  ---       Fdnu       ? Frequency separation correction factor
 327-337  F11.9 ---     e_Fdnu       ? Uncertainty on Fdnu
 339-345  F7.4  Gyr       Age        ? Stellar age
 347-353  F7.4  Gyr     E_Age        ? Upper uncertainty on RGB age
 356-361  F6.4  Gyr     e_Age        ? Lower uncertainty on RGB age
 363-371  F9.4  K         Teff       ? Effective temperature
 373-379  F7.4  K       e_Teff       ? Uncertainty on effective temperature
 381-388  A8    ---       Source     Source catalog (APOKASC3, XGBoost, etc.)
 390-396  F7.4  [-]       [Fe/H]     ? Metallicity [Fe/H]
 398-402  F5.3  [-]     e_[Fe/H]     ? Uncertainty on [Fe/H]
 404-425 E22.16 Lsun      L          ? Luminosity
 427-449 E23.16 Lsun    e_L          ? Uncertainty on luminosity
 451-469  I19   ---       GaiaDR3    ? Gaia DR3 source identifier
 471-479  I9    ---       TIC        ? TESS Input Catalog identifier
 481-497  A17   ---       2MASS      2MASS identifier
 499-500  I2    ---       Nquarters  ? Number of Kepler observing quarters
--------------------------------------------------------------------------------

Acknowledgements:
    From Bastien Liagre, bastienliagre(at)hotmail.fr

    This paper includes data collected by the Kepler mission and obtained
    from the MAST data archive at the Space Telescope Science Institute
    (STScI). Funding for the Kepler mission is provided by the NASA
    Science Mission Directorate. STScI is operated by the Association of
    Universities for Research in Astronomy, Inc., under NASA contract NAS
    5-26555.

================================================================================
(End)                                        Patricia Vannier [CDS]  30-Sep-2025
