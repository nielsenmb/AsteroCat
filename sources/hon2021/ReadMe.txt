J/ApJ/919/131       Oscillating red giants from the TESS QLP       (Hon+, 2021)
================================================================================
A "quick look" at all-sky Galactic archeology with TESS: 158000 oscillating red
giants from the MIT Quick-Look Pipeline.
    Hon M., Huber D., Kuszlewicz J.S., Stello D., Sharma S., Tayar J.,
    Zinn J.C., Vrard M., Pinsonneault M.H.
   <Astrophys. J., 919, 131 (2021)>
   =2021ApJ...919..131H
================================================================================
ADC_Keywords: Asteroseismology; Stars, giant; Stars, diameters;
              Stars, distances; Effective temperatures; Photometry; Optical
Keywords: Asteroseismology ; Stellar oscillations ; Astronomy data analysis ;
          Galactic archaeology

Abstract:
    We present the first near all-sky yield of oscillating red giants from
    the prime mission data of NASA's Transiting Exoplanet Survey Satellite
    (TESS). We apply machine learning toward long-cadence TESS photometry
    from the first data release by the MIT Quick-look Pipeline to
    automatically detect the presence of red giant oscillations in
    frequency power spectra. The detected targets are conservatively
    vetted to produce a total of 158505 oscillating red giants, which is
    an order of magnitude increase over the yield from Kepler and K2 and a
    lower limit to the possible yield of oscillating giants across TESS's
    nominal mission. For each detected target, we report effective
    temperatures and radii derived from colors and Gaia parallaxes, as
    well as estimates of their frequency at maximum oscillation power.
    Using our measurements, we present the first near all-sky
    Gaia-asteroseismology mass map, which shows global structures
    consistent with the expected stellar populations of our Galaxy. To
    demonstrate the strong potential of TESS asteroseismology for Galactic
    archeology even with only one month of observations, we identify
    354 new candidates for oscillating giants in the Galactic halo,
    display the vertical mass gradient of the Milky Way disk, and
    visualize correlations of stellar masses with kinematic phase-space
    substructures, velocity dispersions, and {alpha}-abundances.

Description:
    We use all Full Frame Image (FFI) light curves from the Quick-Look
    Pipeline (QLP) team's first data release, which comprises observations
    across Sectors 1-26 (Year 1 and 2). This data release includes all
    targets brighter than a TESS magnitude of 13.5 and contains
    24,376,080 light curves that have an observing cadence of ~30min.

File Summary:
--------------------------------------------------------------------------------
 FileName   Lrecl   Records   Explanations
--------------------------------------------------------------------------------
ReadMe         80         .   This file
table1.dat     82    158505   List of seismic detections
--------------------------------------------------------------------------------

See also:
 IV/38 : TESS Input Catalog - v8.0 (TIC-8) (Stassun+, 2019)
 IV/39 : TESS Input Catalog version 8.2 (TIC v8.2) (Paegert+, 2021)
 J/AJ/128/1177    : Galactic stellar abundances (Venn+, 2004)
 J/A+A/453/635    : Modelling the Gal. Interstellar Extinction (Marshall+, 2006)
 J/A+A/497/497    : Physical param. from JHK flux (Gonzalez-Hernandez+, 2009)
 J/A+A/562/A71    : Abundances of solar neighbourhood dwarfs (Bensby+, 2014)
 J/MNRAS/445/2758 : KIC giants Bayesian dist. & extinctions (Rodrigues+ 2014)
 J/ApJ/809/77     : Transiting Exoplanet Survey Satellite (Sullivan+, 2015)
 J/MNRAS/456/2260 : K2 Variability Catalogue II (Armstrong+, 2016)
 J/ApJ/827/50     : Kepler faint red giants (Mathur+, 2016)
 J/A+A/588/A87    : Seismic global parameters of 6111 KIC (Vrard+, 2016)
 J/A+A/597/A30    : Seismology & sp. of CoRoGEE red giants (Anders+, 2017)
 J/ApJ/844/102    : KIC parallaxes from asteroseismology vs Gaia (Huber+, 2017)
 J/ApJ/835/83     : K2 GAP data release. I. Campaign 1 (Stello+, 2017)
 J/A+A/618/A109   : Seismic global parameters of 372 KIC (Mosser+, 2018)
 J/ApJS/239/32    : APOKASC-2 cat. of Kepler evolved stars (Pinsonneault+, 2018)
 J/MNRAS/475/5487 : Stellar properties of KIC stars (Silva Aguirre+, 2018)
 J/ApJS/236/42    : Asteroseismology of ~16000 Kepler red giants (Yu+, 2018)
 J/MNRAS/485/5616 : Red giant solar-like oscillations in Kepler (Hon+, 2019)
 J/ApJS/241/12    : Asteroseismic Target List (ATL) for TESS (Schofield+, 2019)
 J/AJ/160/108     : Gaia-Kepler stellar data cat. II. Planets (Berger+, 2020)
 J/ApJ/889/L34    : Oscillations in red giants from TESS data (Silva+, 2020)
 J/ApJS/251/23    : K2 GAP DR2: campaigns 4, 6 & 7 (Zinn+, 2020)
 J/A+A/645/A85    : Age dissection of the Milky Way discs (Miglio+, 2021)
 J/AJ/164/135     : Red giants fundamental asteroseismic parameters (Hon+, 2022)
 http://archive.stsci.edu/hlsp/qlp : TESS LCs from the MIT Quick-Look Pipeline
 http://tess.mit.edu/qlp/ : MIT's Quick-Look Pipeline (QLP) home page

Byte-by-byte Description of file: table1.dat
--------------------------------------------------------------------------------
   Bytes Format Units   Label  Explanations
--------------------------------------------------------------------------------
   1-  9 I9     ---     TIC    [1078/471010941] TESS identifier
  11- 15 F5.1   uHz     numax  [5.5/244] Frequency at maximum power
  17- 20 F4.1   uHz   e_numax  [0.4/20] Frequency at maximum power uncertainty
  22- 25 F4.1   mag     Tmag   [1.9/14] TESS magnitude
  27- 30 I4     K       Teff   [2959/5896] Surface temperature
  32- 34 I3     K     e_Teff   [59/117] Surface temperature uncertainty
  36- 39 F4.1   Rsun    Rstar  [3.4/38] Stellar radius
  41- 46 F6.1   Rsun  e_Rstar  [0.1/1771] Stellar radius uncertainty
  48- 52 F5.1   Lsun    Lstar  [5.3/290] Luminosity
  54- 61 F8.1   Lsun  e_Lstar  [0.2/992942] Luminosity uncertainty
  63- 68 F6.3   kpc     Dist   [0.03/10.4] Distance
  70- 74 F5.3   kpc   e_Dist   [0/2] Distance uncertainty
  76- 80 F5.2   ---     RUWE   [0.5/42] Gaia DR3 re-normalized unit weight error
      82 I1     ---     Flag   [0/1] Flag indicating normal or unusual scaling
                                mass (1)
--------------------------------------------------------------------------------
Note (1): Flag indicating if the mass derived from Equation 1 is typical
          (Flag=1) or outlier (Flag=0) where typical and outlier are described
          in Section 5.1.
--------------------------------------------------------------------------------

History:
    From electronic version of the journal

================================================================================
(End)                    Prepared by [AAS], Emmanuelle Perret [CDS]  02-Feb-2023
