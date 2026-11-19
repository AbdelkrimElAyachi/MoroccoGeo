"""
Builds the SSAS Tabular model definition: ssas/Model.bim (JSON, compatibility level 1700).

The model reads the "bi" views of DWH_DB (sql/11_bi_views.sql), links the facts to the
dimensions and defines the measures (DAX) used by every report.
Deploy with: ssas/deploy_model.ps1

Usage:  python scripts/tools/build_model.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ssas" / "Model.bim"
DB_NAME = "DroughtModel"

I, S, D, T, B = "int64", "string", "double", "dateTime", "boolean"


def col(name, dtype, hidden=False, fmt=None, summarize="none", sort_by=None, key=False, category=None):
    c = {"name": name, "dataType": dtype, "sourceColumn": name, "summarizeBy": summarize}
    if hidden:
        c["isHidden"] = True
    if fmt:
        c["formatString"] = fmt
    if sort_by:
        c["sortByColumn"] = sort_by
    if key:
        c["isKey"] = True
    if category:
        c["dataCategory"] = category
    return c


def measure(name, expr, fmt=None, folder=None, desc=None):
    m = {"name": name, "expression": expr}
    if fmt:
        m["formatString"] = fmt
    if folder:
        m["displayFolder"] = folder
    if desc:
        m["description"] = desc
    return m


def table(name, view, columns, measures=None, hierarchies=None, desc=None, category=None):
    t = {"name": name, "columns": columns,
         "partitions": [{"name": name, "mode": "import",
                         "source": {"type": "query", "query": f"SELECT * FROM {view}", "dataSource": "DWH_DB"}}]}
    if measures:
        t["measures"] = measures
    if hierarchies:
        t["hierarchies"] = hierarchies
    if desc:
        t["description"] = desc
    if category:
        t["dataCategory"] = category
    return t


def hier(name, levels, table_cols):
    return {"name": name, "levels": [{"name": lv, "ordinal": i, "column": c}
                                     for i, (lv, c) in enumerate(zip(levels, table_cols))]}


N1, N2, N4, PCT, INT = "#,0.0", "#,0.00", "0.000", "0.0 %", "#,0"

# ---------------------------------------------------------------- dimensions
date = table("Date", "bi.DimDate", [
    col("DateKey", I, hidden=True),
    col("Date", T, key=True, fmt="dd/mm/yyyy"),
    col("Year", I), col("Quarter", I), col("Month", I, hidden=True),
    col("MonthNameFr", S, sort_by="Month"), col("MonthNameAr", S, sort_by="Month"),
    col("YearMonth", S), col("MonthStart", T, fmt="mmm yyyy"), col("Day", I),
    col("DayNameFr", S), col("IsWeekend", B),
    col("AgriSeason", S), col("AgriSeasonStartYear", I), col("AgriSeasonMonthNo", I, hidden=True),
    col("IsRamadan", B),
], hierarchies=[hier("Calendar", ["Year", "Month"], ["Year", "MonthNameFr"]),
                hier("Agricultural season", ["Season", "Month"], ["AgriSeason", "MonthNameFr"])],
   category="Time", desc="Calendar 1990-2030 with agricultural season (Sept-Aug) and Ramadan.")

province = table("Province", "bi.DimGeography", [
    col("GeographyKey", I, hidden=True), col("GeoLevel", S), col("HcpCode", I, hidden=True),
    col("ProvinceName", S), col("ProvinceShort", S), col("ProvinceType", S),
    col("RegionCode", I, hidden=True), col("RegionName", S), col("ShapeID", S, hidden=True),
    col("AreaKm2", D, fmt=INT), col("PointLat", D, category="Latitude"), col("PointLon", D, category="Longitude"),
    col("Pop2024", I, fmt=INT, summarize="sum"), col("PopUrban2024", I, fmt=INT, summarize="sum"),
    col("PopRural2024", I, fmt=INT, summarize="sum"), col("RuralSharePct", D, fmt=N1),
], measures=[
    measure("Population 2024", 'CALCULATE ( SUM ( Province[Pop2024] ), Province[GeoLevel] = "Province" )',
            INT, "Population", "Legal population 2024 (HCP census) of the provinces in the selection."),
    measure("Provinces", 'CALCULATE ( COUNTROWS ( Province ), Province[GeoLevel] = "Province" )',
            INT, "Population"),
], hierarchies=[hier("Region - Province", ["Region", "Province"], ["RegionName", "ProvinceShort"])],
   desc="75 provinces and prefectures (HCP 2024) + country row (GeographyKey 0 = Maroc).")

crop = table("Crop", "bi.DimCrop", [
    col("CropKey", I, hidden=True), col("FaoItemCode", I), col("CropNameEn", S), col("CropNameFr", S),
    col("CropGroup", S), col("IsAggregate", B), col("IsKeyCrop", B)])

dam = table("Dam", "bi.DimDam", [
    col("DamKey", I, hidden=True), col("DamName", S), col("GeographyKey", I, hidden=True),
    col("OsmAreaKm2", D, fmt=N1), col("MaxWaterKm2", D, fmt=N1),
    col("Lat", D, category="Latitude"), col("Lon", D, category="Longitude")])

cat = table("Drought Category", "bi.DimDroughtCategory", [
    col("DroughtCategoryKey", I, hidden=True), col("CategoryFr", S, sort_by="DroughtCategoryKey"),
    col("CategoryEn", S, sort_by="DroughtCategoryKey"), col("MinSpi", D), col("MaxSpi", D),
    col("IsDrought", B), col("ColorHex", S)])

# ---------------------------------------------------------------- facts + measures
SPI_AT_LAST = ("VAR d = CALCULATE ( MAX ( Drought[DateKey] ), Drought[SpiScale] = {k} ) "
               "RETURN CALCULATE ( AVERAGE ( Drought[SpiValue] ), Drought[SpiScale] = {k}, "
               "REMOVEFILTERS ( 'Date' ), 'Date'[DateKey] = d )")

rain = table("Rainfall", "bi.FactRainfall", [
    col("DateKey", I, hidden=True), col("GeographyKey", I, hidden=True),
    col("RainMm", D, hidden=True), col("NormalMm", D, hidden=True), col("AnomalyPct", D, hidden=True),
], measures=[
    measure("Rain (mm)",
            "AVERAGEX ( VALUES ( Province[GeographyKey] ), CALCULATE ( SUM ( Rainfall[RainMm] ) ) )",
            N1, "Rainfall", "Total rain over the selected period, averaged over the selected provinces (CHIRPS)."),
    measure("Normal Rain (mm)",
            "AVERAGEX ( VALUES ( Province[GeographyKey] ), CALCULATE ( SUM ( Rainfall[NormalMm] ) ) )",
            N1, "Rainfall", "Same, for the 1991-2020 normal of the same months."),
    measure("Rain % of Normal", "DIVIDE ( [Rain (mm)], [Normal Rain (mm)] )", PCT, "Rainfall",
            "100 % = normal; below 100 % = drier than usual."),
])

drought = table("Drought", "bi.FactDrought", [
    col("DateKey", I, hidden=True), col("GeographyKey", I, hidden=True),
    col("SpiScale", I), col("SpiValue", D, hidden=True), col("DroughtCategoryKey", I, hidden=True),
], measures=[
    measure("SPI-1", "CALCULATE ( AVERAGE ( Drought[SpiValue] ), Drought[SpiScale] = 1 )", N2, "Drought index"),
    measure("SPI-3", "CALCULATE ( AVERAGE ( Drought[SpiValue] ), Drought[SpiScale] = 3 )", N2, "Drought index"),
    measure("SPI-6", "CALCULATE ( AVERAGE ( Drought[SpiValue] ), Drought[SpiScale] = 6 )", N2, "Drought index"),
    measure("SPI-12", "CALCULATE ( AVERAGE ( Drought[SpiValue] ), Drought[SpiScale] = 12 )", N2, "Drought index",
            "Average SPI-12 over the selection (0 normal, <= -1 drought)."),
    measure("SPI-12 Latest Month", SPI_AT_LAST.format(k=12), N2, "Drought index",
            "SPI-12 at the last month of the selected period."),
    measure("Provinces in Drought",
            "COUNTROWS ( FILTER ( VALUES ( Province[GeographyKey] ), [SPI-12 Latest Month] <= -1 ) )",
            INT, "Drought index", "Provinces with SPI-12 <= -1 at the last month of the period."),
    measure("Provinces with SPI",
            "COUNTROWS ( FILTER ( VALUES ( Province[GeographyKey] ), NOT ISBLANK ( [SPI-12 Latest Month] ) ) )",
            INT, "Drought index"),
    measure("% Provinces in Drought", "DIVIDE ( [Provinces in Drought], [Provinces with SPI] )", PCT, "Drought index"),
    measure("People in Drought",
            "SUMX ( FILTER ( VALUES ( Province[GeographyKey] ), [SPI-12 Latest Month] <= -1 ), "
            "CALCULATE ( SUM ( Province[Pop2024] ) ) )",
            INT, "Drought index", "2024 population of the provinces in drought (SPI-12 <= -1)."),
    measure("% Population in Drought", "DIVIDE ( [People in Drought], [Population 2024] )", PCT, "Drought index"),
])

veg = table("Vegetation", "bi.FactVegetation", [
    col("DateKey", I, hidden=True), col("GeographyKey", I, hidden=True),
    col("NdviCrop", D, hidden=True), col("NdviAll", D, hidden=True), col("CropSharePct", D, hidden=True),
    col("NdviCropNormal", D, hidden=True), col("NdviCropAnomaly", D, hidden=True),
    col("NdviAllNormal", D, hidden=True), col("NdviAllAnomaly", D, hidden=True),
], measures=[
    measure("NDVI Farmland", "AVERAGE ( Vegetation[NdviCrop] )", N4, "Vegetation",
            "Greenness of farmland (MODIS): ~0 bare soil, 0.2-0.3 stressed, 0.5+ healthy crops."),
    measure("NDVI Farmland Normal", "AVERAGE ( Vegetation[NdviCropNormal] )", N4, "Vegetation",
            "Average of the same months over 2001-2020."),
    measure("NDVI Farmland Anomaly", "[NDVI Farmland] - [NDVI Farmland Normal]", "+0.000;-0.000;0.000",
            "Vegetation", "Negative = less green than usual."),
    measure("NDVI All Land", "AVERAGE ( Vegetation[NdviAll] )", N4, "Vegetation"),
])

res = table("Reservoir", "bi.FactReservoir", [
    col("DateKey", I, hidden=True), col("DamKey", I, hidden=True),
    col("WaterKm2", D, hidden=True), col("ClearPct", D, hidden=True), col("IsReliable", B),
    col("FillIndexPct", D, hidden=True),
], measures=[
    measure("Water Surface (km2)",
            "VAR d = CALCULATE ( MAX ( Reservoir[DateKey] ) ) "
            "RETURN CALCULATE ( SUM ( Reservoir[WaterKm2] ), REMOVEFILTERS ( 'Date' ), 'Date'[DateKey] = d )",
            N1, "Reservoirs", "Water surface of the selected dams at the last month of the period (Sentinel-2)."),
    measure("Max Water Surface (km2)", "SUM ( Dam[MaxWaterKm2] )", N1, "Reservoirs"),
    measure("Fill Index", "DIVIDE ( [Water Surface (km2)], [Max Water Surface (km2)] )", PCT, "Reservoirs",
            "Water surface / largest surface observed (surface, not volume)."),
])

crops = table("Crop Production", "bi.FactCropProduction", [
    col("DateKey", I, hidden=True), col("GeographyKey", I, hidden=True), col("CropKey", I, hidden=True),
    col("Year", I, hidden=True), col("AreaHa", D, hidden=True), col("YieldKgHa", D, hidden=True),
    col("ProductionT", D, hidden=True),
], measures=[
    measure("Production (t)", "SUM ( 'Crop Production'[ProductionT] )", INT, "Crops"),
    measure("Area Harvested (ha)", "SUM ( 'Crop Production'[AreaHa] )", INT, "Crops"),
    measure("Yield (kg/ha)", "DIVIDE ( [Production (t)] * 1000, [Area Harvested (ha)] )", INT, "Crops"),
    measure("Wheat Production (t)", "CALCULATE ( [Production (t)], Crop[FaoItemCode] = 15 )", INT, "Crops"),
    measure("Wheat Yield (kg/ha)", "CALCULATE ( [Yield (kg/ha)], Crop[FaoItemCode] = 15 )", INT, "Crops"),
    measure("Production vs Previous Year",
            "VAR y = MAX ( 'Crop Production'[Year] ) VAR cur = [Production (t)] "
            "VAR prev = CALCULATE ( [Production (t)], REMOVEFILTERS ( 'Date' ), 'Date'[Year] = y - 1 ) "
            "RETURN DIVIDE ( cur - prev, prev )", PCT, "Crops"),
])

weather = table("Weather", "bi.FactWeather", [
    col("DateKey", I, hidden=True), col("GeographyKey", I, hidden=True),
    col("TmaxC", D, hidden=True), col("TminC", D, hidden=True), col("PrecipMm", D, hidden=True),
    col("Et0Mm", D, hidden=True),
], measures=[
    measure("Avg Max Temperature (C)", "AVERAGE ( Weather[TmaxC] )", N1, "Weather"),
    measure("Avg Min Temperature (C)", "AVERAGE ( Weather[TminC] )", N1, "Weather"),
    measure("Evapotranspiration (mm)",
            "AVERAGEX ( VALUES ( Province[GeographyKey] ), CALCULATE ( SUM ( Weather[Et0Mm] ) ) )", N1, "Weather",
            "Water demand of the air (FAO-56 ET0) over the period, averaged over provinces."),
    measure("Hot Days (Tmax >= 35C) per Province",
            "DIVIDE ( CALCULATE ( COUNTROWS ( Weather ), Weather[TmaxC] >= 35 ), "
            "DISTINCTCOUNT ( Weather[GeographyKey] ) )", N1, "Weather"),
])


def rel(frm, frm_col, to, to_col="GeographyKey"):
    return {"name": f"{frm}_{frm_col}_{to}", "fromTable": frm, "fromColumn": frm_col,
            "toTable": to, "toColumn": to_col}


relationships = [
    rel("Rainfall", "DateKey", "Date", "DateKey"), rel("Rainfall", "GeographyKey", "Province"),
    rel("Drought", "DateKey", "Date", "DateKey"), rel("Drought", "GeographyKey", "Province"),
    rel("Drought", "DroughtCategoryKey", "Drought Category", "DroughtCategoryKey"),
    rel("Vegetation", "DateKey", "Date", "DateKey"), rel("Vegetation", "GeographyKey", "Province"),
    rel("Reservoir", "DateKey", "Date", "DateKey"), rel("Reservoir", "DamKey", "Dam", "DamKey"),
    rel("Dam", "GeographyKey", "Province"),
    rel("Crop Production", "DateKey", "Date", "DateKey"), rel("Crop Production", "GeographyKey", "Province"),
    rel("Crop Production", "CropKey", "Crop", "CropKey"),
    rel("Weather", "DateKey", "Date", "DateKey"), rel("Weather", "GeographyKey", "Province"),
]

model = {
    "name": DB_NAME,
    "compatibilityLevel": 1700,
    "model": {
        "culture": "fr-FR",
        "description": "Morocco Drought & Water Security Observatory - analytical model (DWH_DB bi views).",
        "dataSources": [{
            "name": "DWH_DB",
            "connectionString": "Provider=MSOLEDBSQL;Data Source=localhost;Initial Catalog=DWH_DB;"
                                "Integrated Security=SSPI;Persist Security Info=False",
            "impersonationMode": "impersonateServiceAccount"}],
        "tables": [date, province, crop, dam, cat, rain, drought, veg, res, crops, weather],
        "relationships": relationships,
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
n_meas = sum(len(t.get("measures", [])) for t in model["model"]["tables"])
print(f"Written: {OUT} | tables: {len(model['model']['tables'])} | relationships: {len(relationships)} "
      f"| measures: {n_meas}")
