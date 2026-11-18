# Data sources

All sources are real and open. "Verified" = tested by download or API call on 2026-11-17/18.

| # | Source | Content | Format | Period | Access | Verified |
|---|---|---|---|---|---|---|
| 0 | geoBoundaries (MAR ADM2) | 75 province outlines | GeoJSON | 2017 boundaries | Free | ✅ 75 units |
| 1 | CHIRPS v3 (UCSB) | Rainfall, ~5.5 km grid | GeoTIFF | 1981 - Oct 2026 | Free | ✅ |
| 2 | Open-Meteo (ERA5) | Hourly temperature, rain, ET0, wind, humidity | CSV/JSON API | 1940 - now | Free, non-commercial, daily call limit | ✅ |
| 3 | MODIS MOD13Q1 v061 (NASA) | NDVI vegetation, 250 m, 16-day | HDF / GeoTIFF via AppEEARS | 2000 - Oct 2026 | Free NASA Earthdata account | ✅ catalogue |
| 4 | JRC Global Surface Water | Water presence, 30 m, monthly | GeoTIFF / Earth Engine | 1984 - 2021 | Free; monthly history via Earth Engine account | ✅ tile download |
| 4b | Sentinel-2 (ESA Copernicus) | 10 m images, NDWI for water | Earth Engine / Copernicus | 2017 - now | Free account | not yet |
| 5 | Official dam fill rates (Ministry, Maa Dialna, press) | National / basin fill % | Bulletins, articles | daily since ~2018 | Manual collection | ⚠️ no downloadable file |
| 6 | FAOSTAT (QCL) | Crop area, production, yield | Zipped CSV | 1961 - 2024 | Free | ✅ 454 Morocco series |
| 7 | HCP census 2024 (and 2014) | Population by region / province / commune | Excel | 2014, 2024 | Free | ✅ (search) |

## Periods used in the project

| Source | Period kept | Detail |
|---|---|---|
| CHIRPS | 1991-2026 | monthly (30-year SPI reference 1991-2020) |
| Open-Meteo | 1991-2026 | daily: Tmax, Tmin, rain, ET0 |
| MODIS NDVI | 2000-2026 | monthly mean per province (Earth Engine) |
| Dams | 2017-2026 | monthly, Sentinel-2 (Earth Engine); JRC not used |
| FAOSTAT | 2000-2024 | yearly |
| HCP census | 2024 | |

## Links

- geoBoundaries: `https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MAR/ADM2/geoBoundaries-MAR-ADM2.geojson`
- CHIRPS monthly: `https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.YYYY.MM.tif`
- CHIRPS daily: `https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/rnl/YYYY/chirps-v3.0.rnl.YYYY.MM.DD.tif`
- Open-Meteo: `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&hourly=temperature_2m,precipitation,et0_fao_evapotranspiration&format=csv`
- FAOSTAT: `https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Africa.zip`
- MODIS: AppEEARS (appeears.earthdatacloud.nasa.gov), product MOD13Q1.061
- HCP: `https://www.hcp.ma/file/242341/` ("Population légale du Royaume du Maroc selon les
  résultats du RGPH 2024, format EXCEL", 166 KB), saved as `raw/hcp/hcp_population_legale_2024.xlsx`

## Reference values for tests

| Value | Source |
|---|---|
| Morocco wheat production 2019-2024: 4,025,303 / 2,561,898 / 7,543,848 / 2,707,652 / 4,158,471 / 2,441,670 t | FAOSTAT |
| Legal population of Morocco, 1 Sept 2024: 36,828,330 | HCP RGPH 2024 |
| Casablanca daily max temperature 2026-11-01: 24.9 °C | Open-Meteo |
| CHIRPS monthly files available: 1981-01 to 2026-10 (550 files) | CHIRPS server |
| National dam fill rate: ~23% (Feb 2024), 45.2% (8 Jan 2026), ~76% peak (May 2026) | Ministry via press |

## Known limits

- CHIRPS daily values are derived from 5-day totals (not independent daily observations).
- JRC monthly water history ends in 2021.
- Official dam fill rates are not available as a downloadable dataset.
- FAOSTAT is national only; regional crops require HCP statistical yearbooks.
- geoBoundaries outlines come from OpenStreetMap (2017); check them against the official HCP list.
