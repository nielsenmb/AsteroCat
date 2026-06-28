J/A+A/669/A67       Solar-like oscillators catalogue               (Hatt+, 2023)
================================================================================
Catalogue of solar-like oscillators observed by TESS in 120-s and 20-s cadence.
    Hatt E., Nielsen M.B., Chaplin W.J., Ball W.H., Davies G.R., Bedding T.R.,
    Buzasi D.L., Chontos A., Huber D., Kayhan C., Li Y., White T.R., Cheng C.,
    Metcalfe T.S., Stello D.
    <Astron. Astrophys. 669, A67 (2023)>
    =2023A&A...669A..67H        (SIMBAD/NED BibCode)
================================================================================
ADC_Keywords: Asteroseismology ; Surveys
Keywords: asteroseismology - catalogs - stars: oscillations -
          methods: data analysis

Abstract:
    The Transiting Exoplanet Survey Satellite (TESS) mission has provided
    photometric light curves for stars across nearly the entire sky. This
    allows for the application of asteroseismology to a pool of potential
    solar-like oscillators that is unprecedented in size.

    We aim to produce a catalogue of solar-like oscillators observed by
    TESS in the 120-second and 20-second cadence modes. The catalogue is
    intended to highlight stars oscillating at frequencies above the TESS
    30-minute cadence Nyquist frequency with the purpose of encompassing
    the main sequence and subgiant evolutionary phases. We aim to provide
    estimates for the global asteroseismic parameters {nu}_max_ and
    {Delta}{nu}.

    We apply a new probabilistic detection algorithm to the 120-second and
    20-second light curves of over 250000 stars. This algorithm flags
    targets that show characteristic signatures of solar-like
    oscillations. We manually vet the resulting list of targets to confirm
    the presence of solar-like oscillations. Using the probability
    densities computed by the algorithm, we measure the global
    asteroseismic parameters {nu}_max_ and {Delta}{nu}.

    We produce a catalogue of 4177 solar-like oscillators, reporting
    {Delta}{nu} and {nu}_max_ 98% of the total star count. The
    asteroseismic data reveals vast coverage of the Hertzsprung-Russell
    diagram, populating the red giant branch, the subgiant regime and
    extending toward the main sequence.

    A crossmatch with external catalogs shows that 25 of the detected
    solar-like oscillators are a component of a spectroscopic binary, and
    28 are confirmed planet host stars. These results provide the
    potential for precise, independent asteroseismic constraints on these
    and any additional TESS targets of interest.

Description:
    Global asteroseismic parameters {Delta}{nu} and {nu}_max_ for
    solar-like oscillators detected in TESS 120-sec and 20-sec cadence
    data. Each star is identified by the TIC ID. The following columns
    contain the number of sectors used to make the detection, the responses
    in the repeating pattern (RP) and power excess (PE) modules, the
    frequency at maximum power (numax), the large frequency spacing (dnu),
    the sample the star belongs to and associated flags. Flags identify
    whether the star appeared in the Ninth Catalogue of Spectroscopic
    Binary Orbits (SB9) or in NASA's Exoplanet Archive.

File Summary:
--------------------------------------------------------------------------------
 FileName      Lrecl  Records   Explanations
--------------------------------------------------------------------------------
ReadMe            80        .   This file
catalog.dat       61     4177   Solar-like oscillators catalog
--------------------------------------------------------------------------------

See also:
         B/sb9   : SB9: 9th Catalogue of Spectroscopic Binary Orbits
                                                   (Pourbaix+ 2004-2014)
         IV/38   : TESS Input Catalog - v8.0 (TIC-8) (Stassun+, 2019)

 J/A+A/506/465   : Solar-like oscillations in red giants (Hekker+, 2009)
 J/A+A/525/A131  : Solar-like oscillations in Kepler red giants (Hekker+, 2011)
 J/ApJS/241/12   : Asteroseismic Target List (ATL) for TESS (Schofield+, 2019)
 J/MNRAS/482/616 : Detecting solar-like oscillations (Bell+, 2019)
 J/A+A/657/A31   : Solar-like oscillations in Kepler DR25 SC data (Mathur+ 2022)
 J/A+A/663/A51   : A probabilistic method for detecting solar-like oscillations
                                                           (Nielsen+, 2022)

Byte-by-byte Description of file: catalog.dat
--------------------------------------------------------------------------------
   Bytes Format Units   Label     Explanations
--------------------------------------------------------------------------------
   1-  9  I9    ---     TIC       TESS Input Catalogue Identifier
  11- 12  I2    ---     NSectors  [1/26] Number of sectors of TESS data used
      16  I1    ---     RP        [0/1] Repeating pattern module flag
      20  I1    ---     PE        [0/1] Power excess module flag
  24- 30  F7.2  uHz     numax     [3.72/3344.47]? Frequency at maximum power
  32- 37  F6.2  uHz   e_numax     ? Uncertainty on frequency at maximum power
  39- 44  F6.2  uHz     dnu       [0.61/141.13]? Large frequency separation
  46- 49  F4.2  uHz   e_dnu       ? Uncertainty on large frequency separation
  51- 57  A7    ---     sample    Sample target belongs to (20-sec or 120-sec)
  59- 61  A3    ---     Flag      Cross check results (1)
--------------------------------------------------------------------------------
Note (1): Cross check results flag as follows:
           SB9 = Ninth Catalogue of Spectroscopic Binary Orbits (Cat. B/sb9)
           PH  = NASA's Exoplanet Archive
--------------------------------------------------------------------------------

Acknowledgements:
     Emily Hatt, exh698(at)student.bham.ac.uk

================================================================================
(End)                                        Patricia Vannier [CDS]  17-Oct-2022
