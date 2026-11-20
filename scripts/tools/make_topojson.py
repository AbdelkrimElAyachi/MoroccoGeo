"""
Builds the Morocco province map for the Power BI "Shape map" visual: powerbi/morocco_provinces.topojson

- Outlines: raw/boundaries/geoBoundaries-MAR-ADM2.geojson (75 provinces)
- Names: taken from DWH_DB.dbo.DimGeography (ProvinceShort, e.g. "Settat"), joined on ShapeID, so the map
  keys match the model's Province[ProvinceShort] values exactly.
- Simplified (~500 m tolerance) so the file stays small and Power BI draws it quickly.

Usage:  python scripts/tools/make_topojson.py
"""
import subprocess
from pathlib import Path

import geopandas as gpd
import topojson as tp

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "powerbi" / "morocco_provinces.topojson"

# ShapeID -> ProvinceShort / RegionName from the warehouse
rows = subprocess.run(
    ["sqlcmd", "-S", "localhost", "-E", "-C", "-h", "-1", "-W", "-s", "|", "-f", "65001", "-Q",
     "SET NOCOUNT ON; SELECT ShapeID, ProvinceShort, RegionName FROM DWH_DB.dbo.DimGeography WHERE GeoLevel = 'Province'"],
    capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
names = {}
for line in rows:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) == 3 and parts[0]:
        names[parts[0]] = (parts[1], parts[2])

gdf = gpd.read_file(ROOT / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson")
gdf["ProvinceShort"] = gdf["shapeID"].map(lambda s: names[s][0])
gdf["RegionName"] = gdf["shapeID"].map(lambda s: names[s][1])
gdf = gdf[["ProvinceShort", "RegionName", "geometry"]]

topo = tp.Topology(gdf, prequantize=True, toposimplify=0.005, object_name="provinces")
OUT.parent.mkdir(parents=True, exist_ok=True)
topo.to_json(OUT)
print(f"Written: {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {len(gdf)} provinces)")
