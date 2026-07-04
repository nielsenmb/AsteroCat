import json
import numpy as np
from pathlib import Path
from astropy.io import ascii
from asterocat import utils

TABLE        = "https://cdsarc.cds.unistra.fr/viz-bin/nph-Cat/txt?J/ApJS/251/23/table4.dat.gz"
README       = "https://cdsarc.cds.unistra.fr/ftp/J/ApJS/251/23/ReadMe"
ADS_URL      = "https://ui.adsabs.harvard.edu/abs/2020ApJS..251...23Z"
TEFF_ADS_URL = None
INSTRUMENT   = 'K2'
CATALOG      = 'EPIC'
SOURCE       = 'Zinn+2020'


OUTPUT       = Path(f"sources/{SOURCE}.lower().replace('+','').json")


def main():
    print(f"Loading {SOURCE} from CDS...")
    table = ascii.read(TABLE, readme=README)

# INCOMPLETE COMPILE
import warnings
warnings.warn('Incomplete compile')