import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from asterocat import utils

TABLE_SEISMIC= "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/767/127/table1.dat"
TABLE_TEFF   = "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/767/127/table2.dat"
README       = "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/767/127/ReadMe"
ADS_URL      = "https://ui.adsabs.harvard.edu/abs/2013ApJ...767..127H/"
TEFF_ADS_URL = None
INSTRUMENT   = 'Kepler'
CATALOG      = 'KIC'
SOURCE       = 'Huber+2013'


output       = Path(f"sources/json/{SOURCE}.lower().replace('+','').json")

def main():
    print(f"Loading {SOURCE} from CDS...")
    table = ascii.read(TABLE, readme=README)

# INCOMPLETE COMPILE
import warnings
warnings.warn('Incomplete compile')