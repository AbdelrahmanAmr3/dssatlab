UFGA8201.MZX is copied byte-for-byte from C:/DSSAT48/Maize/UFGA8201.MZX
(the installed DSSAT 4.8 maize example).

The INITIAL CONDITIONS layout matches the example in the installed DSSAT 4.8
Help/DSSAT_Input_Files.chm, experimentfiles.htm:
@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME
@C  ICBL  SH2O  SNH4  SNO3

C occupies columns 1-2. Subsequent fields occupy six columns: PCR 3-8,
ICDAT 9-14 (YYDDD), ICRES 45-50; layer ICBL 3-8, SH2O 9-14,
SNH4 15-20, SNO3 21-26. TREATMENTS.IC occupies columns 44-46.
PCR is the previous crop code; ICRES is surface residue mass in kg/ha.
ICBL is the layer bottom in cm; SH2O is volumetric water; SNH4 and SNO3
are elemental nitrogen in g/Mg soil (equivalent to mg/kg).

Tests exercise the copied FileX with a mocked subprocess. They do not claim
real-DSSAT proof of the new writer; that is the owner's later integration step.
