Format references copied unchanged from the installed DSSAT 4.8 examples:
  C:/DSSAT48/Maize/UFGA8201.MZX
  C:/DSSAT48/Wheat/KSAS8101.WHX

These are complete real FileX files, including their original fixed columns.
The skeleton uses their shared sections and the v0.6 writers' planting and
initial-condition headers. SMODEL is supplied explicitly (MZCER048/WHCER048).
Unlike these examples, initial conditions are absent (IC=0) until overridden.
Tests use fake cultivar tables in a temporary data directory; no installed
DSSAT or external files are needed to run the test suite.

Manual smoke check (2026-09-30, installed DSSAT 4.8.5.017): generated maize
and wheat skeletons both returned 0 and produced Summary.OUT without ERROR.OUT.
Maize used MZCER048. Wheat warned that the ticket's requested WHCER048 model
is invalid and fell back to CSCER048 (the installed DSSATPRO.v48 MWH entry).
WHCER048.CUL is nevertheless the wheat genotype filename. The crop table
retains the explicit ticket #89 model code; the wheat run is NOT proof that
WHCER048 model selection works. Resolve that model-code discrepancy before
claiming wheat model selection is proven. Existing example soil/weather
warnings were also present; no missing-weather warning occurred.
