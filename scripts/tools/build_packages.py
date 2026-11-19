"""
Builds the Phase 2 SSIS packages into ssis/_incoming/ (then add them to the Visual Studio
project with "Add Existing Package").

Usage:  python scripts/tools/build_packages.py [package_name ...]
"""
import sys
from pathlib import Path

from make_package import bulk_insert_step, make_package

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ssis" / "_incoming"

PACKAGES = {
    "03_Crops": dict(
        description="Step 6: FAOSTAT crop production 2000-2024 (Python), staging, DimCrop + FactCropProduction.",
        python_script="04_faostat.py",
        sql_steps=[
            bulk_insert_step("stg.FaoCrops", "fao_crops.csv"),
            {"name": "SQL Load FactCropProduction", "desc": "Calls dbo.usp_LoadCrops",
             "conn": "DWH_DB", "sql": "EXEC dbo.usp_LoadCrops;", "rows": True},
        ]),
    "04_Rainfall": dict(
        description="Step 8: CHIRPS v3 monthly rainfall 1991-2026 per province (Python), staging, FactRainfallMonthly.",
        python_script="05_chirps.py",
        sql_steps=[
            bulk_insert_step("stg.ChirpsMonthly", "chirps_monthly.csv"),
            {"name": "SQL Load FactRainfallMonthly", "desc": "Calls dbo.usp_LoadRainfall",
             "conn": "DWH_DB", "sql": "EXEC dbo.usp_LoadRainfall;", "rows": True},
        ]),
    "05_Drought": dict(
        description="Step 9: rainfall normals (1991-2020) and SPI-1/3/6/12 (Python), staging, FactDroughtIndex.",
        python_script="06_spi.py",
        sql_steps=[
            bulk_insert_step("stg.SpiMonthly", "spi_monthly.csv"),
            {"name": "SQL Load FactDroughtIndex", "desc": "Calls dbo.usp_LoadDroughtIndex",
             "conn": "DWH_DB", "sql": "EXEC dbo.usp_LoadDroughtIndex;", "rows": True},
        ]),
    "06_Weather": dict(
        description="Step 7: Open-Meteo daily weather 1991-2026 per province (Python), staging, FactWeatherDaily.",
        python_script="07_openmeteo.py",
        sql_steps=[
            bulk_insert_step("stg.WeatherDaily", "weather_daily.csv"),
            {"name": "SQL Load FactWeatherDaily", "desc": "Calls dbo.usp_LoadWeather",
             "conn": "DWH_DB", "sql": "EXEC dbo.usp_LoadWeather;", "rows": True},
        ]),
    "07_Vegetation": dict(
        description="Step 10: MODIS NDVI per province and month 2000-2026 (Python + Earth Engine), staging, FactVegetationMonthly.",
        python_script="08_ndvi.py",
        sql_steps=[
            bulk_insert_step("stg.NdviMonthly", "ndvi_monthly.csv"),
            {"name": "SQL Load FactVegetationMonthly", "desc": "Calls dbo.usp_LoadVegetation",
             "conn": "DWH_DB", "sql": "EXEC dbo.usp_LoadVegetation;", "rows": True},
        ]),
    "08_Reservoirs": dict(
        description="Step 11: reservoir list (OpenStreetMap) and monthly water surface 2017-2026 (Sentinel-2, Earth Engine), DimDam + FactReservoirMonthly.",
        python_script=["09_reservoirs.py", "10_dam_water.py"],
        sql_steps=[
            bulk_insert_step("stg.Reservoirs", "reservoirs.csv"),
            bulk_insert_step("stg.DamWaterMonthly", "dam_water_monthly.csv"),
            {"name": "SQL Load FactReservoirMonthly", "desc": "Calls dbo.usp_LoadReservoirs",
             "conn": "DWH_DB", "sql": "EXEC dbo.usp_LoadReservoirs;", "rows": True},
        ]),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(PACKAGES)
    for n in names:
        (OUT / f"{n}.dtsx").write_text(make_package(n, **PACKAGES[n]), encoding="utf-8")
        print(f"Written: {OUT / (n + '.dtsx')}")
