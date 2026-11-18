"""
Step 3 - Province boundaries (geoBoundaries, Morocco ADM2).

What it does:
  1. Downloads the GeoJSON of Morocco's provinces into raw/boundaries/
     (skips the download if the file is already there).
  2. Checks it: 75 provinces, valid geometries, WGS84 coordinates.
  3. Writes clean/boundaries_provinces.csv for SSIS to load into Staging_DB:
       shape_id ; shape_name ; area_km2 ; point_lat ; point_lon
     point_lat/lon = a point guaranteed to be inside the province
     (used later to request weather data per province).

Usage:  python 01_boundaries.py <ProjectRoot>
Exit code 0 = OK, 1 = a check failed (SSIS then logs "Failed").
"""
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd

URL = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
       "releaseData/gbOpen/MAR/ADM2/geoBoundaries-MAR-ADM2.geojson")
EXPECTED_PROVINCES = 75


def main(project_root: Path) -> int:
    raw_file = project_root / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson"
    out_csv = project_root / "clean" / "boundaries_provinces.csv"

    # 1. Download (only if missing)
    if raw_file.exists():
        print(f"Already downloaded: {raw_file}")
    else:
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {URL}")
        urllib.request.urlretrieve(URL, raw_file)
        print(f"Saved: {raw_file} ({raw_file.stat().st_size:,} bytes)")

    # 2. Checks
    gdf = gpd.read_file(raw_file)
    errors = []
    if len(gdf) != EXPECTED_PROVINCES:
        errors.append(f"expected {EXPECTED_PROVINCES} provinces, found {len(gdf)}")
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        errors.append(f"unexpected coordinate system: {gdf.crs}")
    invalid = (~gdf.geometry.is_valid).sum()
    if invalid:
        print(f"Warning: {invalid} invalid geometries, repairing them")
        gdf["geometry"] = gdf.geometry.make_valid()
    if gdf["shapeName"].duplicated().any():
        errors.append("duplicate province names: "
                      + ", ".join(gdf.loc[gdf["shapeName"].duplicated(), "shapeName"]))

    # 3. Area (equal-area projection) and an inside point per province
    area_km2 = gdf.to_crs("EPSG:6933").area / 1e6
    inside = gdf.geometry.representative_point()
    out = gdf[["shapeID", "shapeName"]].rename(
        columns={"shapeID": "shape_id", "shapeName": "shape_name"})
    out["area_km2"] = area_km2.round(1)
    out["point_lat"] = inside.y.round(5)
    out["point_lon"] = inside.x.round(5)
    out = out.sort_values("shape_name")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, sep=";", index=False, encoding="utf-8", lineterminator="\n")

    print(f"Provinces: {len(out)}  |  total area: {out['area_km2'].sum():,.0f} km2")
    print(f"Written: {out_csv}")
    if errors:
        for e in errors:
            print(f"CHECK FAILED: {e}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    sys.exit(main(root))
