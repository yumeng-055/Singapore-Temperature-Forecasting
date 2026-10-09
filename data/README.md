# Local data setup and dictionary

This individual academic case uses the supplied SingStat Table Builder export,
**Air Temperature And Sunshine, Relative Humidity And Rainfall, Annual**.
The export identifies **National Environment Agency** as its source, a last-update
date of 10 January 2025 and a generation date of 11 December 2025. These are file
metadata, not a claim that the data are current today. Redistribution permission
has not been established; the original CSV is supplied locally and excluded from this project.

Place your original export at `data/annual_climate.csv` without changing its bytes.
The loader skips nine metadata rows and selects exactly the two series below.

| Field | Source series | Definition | Unit |
|---|---|---|---|
| year | Original year columns | One observation per calendar year, 1960–2024 | Year |
| temperature_c | Air Temperature Means Daily Maximum (Degree Celsius) | Annual mean of daily maximum air temperature; not the highest recorded temperature in a year | °C |
| rainfall_mm | Total Rainfall (Millimetre) | Annual total rainfall | mm |

The analysis uses 65 annual observations: 55 training years (1960–2014) and 10
holdout years (2015–2024). No imputation, clipping or deletion is performed.
IQR flags are screening indicators, not proof that an observation is invalid.
Exact geographical station coverage and detailed measurement methodology are
not specified in the supplied export; do not infer them from the national title.

Published artifacts contain aggregate statistics, annual model predictions and
figures for evidence review. The full source export is kept outside the public project.
