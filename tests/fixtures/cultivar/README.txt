UFGA8201.MZX is a narrow test fixture, based on the existing scenarios fixture.
CULTIVARS header/row layout was checked against the installed DSSAT 4.8 file
C:/DSSAT48/Maize/UFGA8201.MZX and the official DSSAT/dssat-csm-data Maize example:
https://github.com/DSSAT/dssat-csm-data/blob/master/Maize/UFGA8201.MZX

One-based columns: C=1-2, separator=3, CR=4-5, separator=6,
INGENO=7-12, separator=13, CNAME starts at 14. Treatment CU uses columns 35-37.
The synthetic second level (7) proves levels need not be consecutive.
The writer uses -99 for descriptive CNAME; the cultivar identifier is INGENO.

MZCER048.CUL contains the installed DSSAT 4.8 @VAR# header and two data rows.
VAR# occupies columns 1-6. Coefficients are fixture context, never parsed.
Tests mock the DSSAT subprocess; these fixtures do not constitute real-DSSAT proof.
