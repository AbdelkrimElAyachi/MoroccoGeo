"""
Exports the warehouse (DWH_DB) as an open dataset for Kaggle, into kaggle/:
  provinces.csv, rainfall_monthly.csv, drought_spi_monthly.csv, vegetation_ndvi_monthly.csv,
  weather_daily.csv, reservoirs.csv, dam_water_monthly.csv, crops_yearly.csv, national_yearly.csv
  + dataset-metadata.json (title, id, licence, description) for the Kaggle website or CLI.

Usage:  python 12_export_kaggle.py <ProjectRoot> [kaggle-username]
"""
import json
import shutil
import sys
import warnings
from pathlib import Path

import pandas as pd
import pyodbc

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
CONN = ("Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=DWH_DB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes")
MONTH = "CONCAT(f.DateKey / 10000, '-', RIGHT(CONCAT('0', f.DateKey / 100 % 100), 2))"
DAY = "CONVERT(char(10), CONVERT(date, CONVERT(char(8), f.DateKey)), 23)"
PROV = "JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey AND g.GeoLevel = 'Province'"

QUERIES = {
    "provinces": """SELECT ProvinceShort province, RegionName region, HcpCode hcp_code, AreaKm2 area_km2,
        PointLat lat, PointLon lon, Pop2024 population_2024, PopUrban2024 urban_2024, PopRural2024 rural_2024
        FROM dbo.DimGeography WHERE GeoLevel = 'Province' ORDER BY ProvinceShort""",
    "rainfall_monthly": f"""SELECT {MONTH} month, g.ProvinceShort province, g.RegionName region,
        ROUND(f.RainMm, 2) rain_mm, ROUND(f.NormalMm, 2) normal_1991_2020_mm,
        ROUND(100.0 * f.RainMm / NULLIF(f.NormalMm, 0), 1) pct_of_normal
        FROM dbo.FactRainfallMonthly f {PROV} ORDER BY f.DateKey, g.ProvinceShort""",
    "drought_spi_monthly": f"""SELECT {MONTH} month, g.ProvinceShort province, g.RegionName region,
        f.SpiScale spi_scale_months, ROUND(f.SpiValue, 3) spi, c.CategoryEn category
        FROM dbo.FactDroughtIndex f {PROV}
        JOIN dbo.DimDroughtCategory c ON c.DroughtCategoryKey = f.DroughtCategoryKey
        ORDER BY f.DateKey, f.SpiScale, g.ProvinceShort""",
    "vegetation_ndvi_monthly": f"""SELECT {MONTH} month, g.ProvinceShort province, g.RegionName region,
        ROUND(f.NdviCrop, 4) ndvi_cropland, ROUND(f.NdviAll, 4) ndvi_all_land, f.CropSharePct cropland_share_pct,
        ROUND(f.NdviCropAnomaly, 4) ndvi_cropland_anomaly
        FROM dbo.FactVegetationMonthly f {PROV} ORDER BY f.DateKey, g.ProvinceShort""",
    "weather_daily": f"""SELECT {DAY} date, g.ProvinceShort province, g.RegionName region,
        f.TmaxC tmax_c, f.TminC tmin_c, f.PrecipMm precip_mm, f.Et0Mm et0_mm
        FROM dbo.FactWeatherDaily f {PROV} ORDER BY f.DateKey, g.ProvinceShort""",
    "reservoirs": """SELECT d.DamName dam, g.ProvinceShort province, d.Lat lat, d.Lon lon,
        d.OsmAreaKm2 osm_outline_km2, d.MaxWaterKm2 max_water_km2
        FROM dbo.DimDam d LEFT JOIN dbo.DimGeography g ON g.GeographyKey = d.GeographyKey
        ORDER BY d.OsmAreaKm2 DESC""",
    "dam_water_monthly": f"""SELECT {MONTH} month, d.DamName dam, ROUND(f.WaterKm2, 3) water_km2,
        ROUND(f.FillIndexPct, 1) pct_of_max_surface, ROUND(f.ClearPct, 1) visible_pct,
        CAST(f.IsReliable AS int) reliable, f.Source source
        FROM dbo.FactReservoirMonthly f JOIN dbo.DimDam d ON d.DamKey = f.DamKey
        ORDER BY f.DateKey, d.DamName""",
    "crops_yearly": """SELECT f.[Year] year, c.CropNameEn crop, c.CropGroup crop_group, CAST(c.IsAggregate AS int) is_aggregate,
        f.AreaHa area_ha, f.YieldKgHa yield_kg_ha, f.ProductionT production_t
        FROM dbo.FactCropProduction f JOIN dbo.DimCrop c ON c.CropKey = f.CropKey
        ORDER BY f.[Year], c.CropNameEn""",
}

DESCRIPTION = """# Morocco Drought & Water Observatory (1991-2026)

Monthly drought, rainfall, vegetation, reservoir water and daily weather for **Morocco's 75 provinces**,
built only from open data (satellite and official statistics), plus national crop production and
the 2024 census population. Data up to **{last_month}**.

## Files

| File | Grain | Rows | Period |
|---|---|---|---|
{file_table}

## Key columns

- **drought_spi_monthly**: `spi` = Standardized Precipitation Index on CHIRPS rainfall, accumulated over
  `spi_scale_months` (1, 3, 6, 12), gamma fit on 1991-2020 (WMO method). 0 = normal, <= -1 drought,
  <= -2 extreme drought. Left empty where the method is not valid (desert summers with almost no rain).
- **rainfall_monthly**: province average of CHIRPS v3 pixels (zonal statistics); normal = 1991-2020 mean of the same month.
- **vegetation_ndvi_monthly**: MODIS MOD13Q1 NDVI (good-quality pixels), averaged over cells that are >= 50 %
  cropland (ESA WorldCover 10 m) and over all land; anomaly = difference from the 2000-2026 mean of the month.
- **weather_daily**: Open-Meteo historical archive (ERA5) at one point per province: max / min temperature,
  precipitation, reference evapotranspiration (FAO ET0).
- **dam_water_monthly**: water surface of 26 reservoirs >= 4 km2 measured from space: JRC Global Surface Water
  (Landsat) 2000-2016, Sentinel-2 (NDWI > 0) from 2017. `visible_pct` = share of the lake seen without clouds or
  gaps; `reliable` = 1 when >= 80 %. This is a SURFACE, not the official VOLUME fill rate.
- **crops_yearly**: FAOSTAT national production, area and yield.

## Validation

### 1. Checks against official and independent data (all pass)

| Check | Compared with | Result |
|---|---|---|
| Province list and population | HCP 2024 census (official) | 75 / 75 provinces, 36,828,330 people, exact: PASS |
| Wheat production | FAOSTAT (figures reported by Morocco) | 2024 = 2,441,670 t, identical: PASS |
| Satellite rainfall (CHIRPS) | ERA5 reanalysis (Open-Meteo), an independent source | national monthly correlation 0.92: PASS |
| SPI-12 statistics | WMO definition | mean 0.000, standard deviation 1.001 over 1991-2020: PASS |
| Lake surfaces, two satellites | Landsat (JRC) vs Sentinel-2, 2017-2021 | correlation 0.997, totals within 1.3 %: PASS |
| Reservoir trend | Official fill rates (Ministry of Equipment and Water) | same order on Feb 2024 < Jan 2026 < May 2026: PASS |
| Farmland greenness vs harvest | Official wheat yield (FAOSTAT), 2001-2024 | March NDVI correlation 0.86; the 5 worst harvests (2007, 2020, 2005, 2022, 2016) all had below-median greenness: PASS |
| Completeness | - | 75 provinces every month and every day, no negative rain, no duplicates: PASS |

### 2. Real rain gauges (NOAA GHCN-Daily)

The rainfall and the drought index were compared with the **11 Moroccan weather stations** of NOAA
GHCN-Daily that have rain records after 2005 (1991-2025, 1,932 station-months). Station values with a NOAA
quality flag are removed; a month is used only if at least 90 % of its days were recorded, a season, year or
12-month window only if all its months are complete. Each station is compared with the satellite pixel it
sits in; the SPI test uses the province SPI-12 published here. Pass rules (median / every station) were fixed
before the test was run.

**Result by climate zone** (same rules; zone = the station's own mean annual rain, arid below 250 mm/year,
the usual threshold; this split was added after the first run, when the failures turned out to come from the
driest stations):

| Test | Rule (median / every station) | Semi-arid and humid zone (7 stations) | Arid zone (4 stations) |
|---|---|---|---|
| **SPI-12 drought index** | >= 0.75 / >= 0.50, agreement >= 80 % | **PASS**: median 0.905, lowest 0.73 (Oujda), agreement 84 % | FAIL: median 0.75, lowest 0.45 (Midelt) |
| **3-month seasons** | >= 0.85 / >= 0.60 | **PASS**: median 0.87, lowest 0.69 (Oujda) | FAIL: median 0.65, lowest 0.42 (Ouarzazate) |
| Hydrological years (Sep-Aug) | >= 0.85 / >= 0.60 | FAIL: median 0.90, lowest 0.51 (Oujda, 6 years only) | too few complete years |
| Monthly rain | >= 0.80 / >= 0.60 | FAIL: median 0.88, lowest 0.57 (Oujda) | FAIL: median 0.62, lowest 0.35 (Ouarzazate) |

All 11 stations together: medians pass every test (0.83 monthly, 0.86 seasons, 0.87 years, 0.90 SPI-12),
but the "every station" rule fails because of the arid stations.

Semi-arid / humid stations: Tangier, Tétouan, Kenitra (not judged, 12 complete months), Salé (Rabat), Meknès,
Casablanca-Anfa, Nouasseur, Oujda. Arid stations: Essaouira, Marrakech, Midelt, Ouarzazate.
SPI-12 correlation by station: Salé 0.95, Essaouira 0.93, Meknès 0.91, Casablanca-Anfa 0.91, Tétouan 0.91,
Tangier 0.90, Nouasseur 0.86, Marrakech 0.85, Oujda 0.73, Ouarzazate 0.64, Midelt 0.45.

**What it means**
- **Good:** where most people, farmland and dams are, the drought index (SPI-12) matches the rain gauges
  at 0.85-0.95. Longer periods agree better (median 0.83 monthly → 0.90 for SPI-12), as expected.
- **Weak:** in the dry interior and the mountains (Midelt, Ouarzazate, partly Oujda) monthly values agree
  poorly. Long-term totals still match there (e.g. Ouarzazate 11.1 mm/month measured vs 12.2 mm from
  satellite), so rain is not missing or invented; it is the **timing** that differs. Three reasons:
  1. *Point vs area:* a gauge measures one spot, a pixel averages ~25 km2. In dry areas much of the rain
     comes from small thunderstorms that can hit the gauge and miss the rest of the pixel, or the reverse.
  2. *Satellite limits:* few gauges exist in the interior to correct CHIRPS, and mountains (Midelt, ~1,500 m
     between the Middle and High Atlas) are difficult for all satellite rainfall products.
  3. *Station errors:* the gauge records contain impossible values (e.g. 81 mm in July 1994 at Casablanca,
     82 mm at Ouarzazate in a month when the satellite and the whole province show 0), and only ~40 % of
     months are complete enough to compare.
- **Recommendation:** use the dry interior and Saharan provinces as a trend indicator (SPI-12, seasons),
  not as exact monthly values. Near the -1 drought line, a small difference can flip a drought call.

### 3. Real thermometers (NOAA GHCN-Daily)

Daily maximum temperature in `weather_daily.csv` (Open-Meteo, one representative point per province) was compared
with the thermometers of the same NOAA stations (values with a quality flag removed). Two measures: monthly means,
and daily anomalies (each day minus its normal for that calendar day, so the seasons cannot inflate the score).
Rules fixed before the run: monthly r median >= 0.95 and every station >= 0.90; daily anomalies median >= 0.70 and
every station >= 0.50 (stations with >= 60 complete months are judged).

| Station | km to weather point | Monthly r | Daily anomaly r | Mean difference |
|---|---|---|---|---|
| Meknès | 14 | 0.997 | 0.954 | -0.2 °C |
| Ouarzazate | 35 | 0.997 | 0.927 | -4.4 °C |
| Oujda | 16 | 0.995 | 0.914 | -1.5 °C |
| Midelt | 22 | 0.987 | 0.868 | -6.4 °C |
| Tétouan | 20 | 0.982 | 0.599 | -2.0 °C |
| Salé (Rabat) | 12 | 0.977 | 0.869 | +0.3 °C |
| Essaouira | 17 | 0.685 | 0.356 | +4.3 °C |
| Marrakech, Casablanca-Anfa, Nouasseur, Tangier (fewer complete months, not judged) | 4-25 | 0.97-0.997 | 0.85-0.96 | -1.6 to +0.5 °C |

**Result:** medians pass easily (monthly 0.987, daily anomalies 0.869), but the rule "every station" fails because
of **Essaouira**. This is a real climate difference, not a data error: the station is on the ocean, where the cold
coastal current keeps summer maximums at 21-22 °C all year, while the province's weather point is 17 km inland,
where July reaches 31.7 °C. In the same way, the mean differences at Midelt (-6.4 °C) and Ouarzazate (-4.4 °C) come
from altitude: the weather point and the station are not at the same height. **Use:** the weather columns describe
the province's representative point; for coastal cities and mountain towns, expect an offset of a few degrees, but
the day-to-day and year-to-year changes are reliable.

## Sources and licences

Please credit the original providers:
- CHIRPS v3, Climate Hazards Center, UC Santa Barbara
- Open-Meteo historical weather API (ERA5), CC BY 4.0
- NASA MODIS MOD13Q1 v061; ESA WorldCover v200; JRC Global Surface Water; Copernicus Sentinel-2 (via Google Earth Engine)
- Reservoir outlines: © OpenStreetMap contributors, ODbL
- FAOSTAT (FAO); HCP Morocco, 2024 general population census; geoBoundaries (province outlines)

This derived database is released under the **Open Database License (ODbL 1.0)**.

## Authors

Abdelkrim El Ayachi and Othmane El Khassouani (MSBI school project, ISGA, 2026-2027).

Project and live dashboard: {repo}
"""


def main(root: Path, user: str) -> int:
    out = root / "kaggle"
    out.mkdir(exist_ok=True)
    cn = pyodbc.connect(CONN)
    info = []
    for name, sql in QUERIES.items():
        df = pd.read_sql(sql, cn)
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8")
        period = ""
        for col in ("month", "date", "year"):
            if col in df.columns:
                period = f"{df[col].min()} → {df[col].max()}"
                break
        info.append((name, len(df), period))
        print(f"{name:26s} {len(df):>9,} rows  {period}")
    shutil.copyfile(root / "web" / "data" / "csv" / "national_yearly.csv", out / "national_yearly.csv")
    n_nat = len(pd.read_csv(out / "national_yearly.csv"))
    info.append(("national_yearly", n_nat, "1991 → 2026"))

    grains = {"provinces": "province (75)", "rainfall_monthly": "province × month", "drought_spi_monthly": "province × month × scale",
              "vegetation_ndvi_monthly": "province × month", "weather_daily": "province × day", "reservoirs": "reservoir (26)",
              "dam_water_monthly": "reservoir × month", "crops_yearly": "crop × year", "national_yearly": "year (national)"}
    table = "\n".join(f"| `{n}.csv` | {grains[n]} | {r:,} | {p} |" for n, r, p in info)
    last = pd.read_csv(out / "rainfall_monthly.csv")["month"].max()
    desc = DESCRIPTION.format(last_month=last, file_table=table,
                              repo="https://github.com/<github-username>/<repository>")
    (out / "README.md").write_text(desc, encoding="utf-8")
    meta = {"title": "Morocco Drought & Water Observatory 1991-2026",
            "subtitle": "Monthly SPI, rainfall, NDVI, dam water and daily weather for 75 provinces",
            "id": f"{user}/morocco-drought-water-observatory",
            "licenses": [{"name": "ODbL-1.0"}],
            "keywords": ["earth and nature", "weather and climate", "agriculture", "africa", "geospatial analysis"],
            "description": desc}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    size = sum(f.stat().st_size for f in out.glob("*.csv")) / 1e6
    print(f"Written: {out}  ({len(info)} CSV files, {size:.1f} MB)")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    user = sys.argv[2] if len(sys.argv) > 2 else "<kaggle-username>"
    sys.exit(main(root, user))
