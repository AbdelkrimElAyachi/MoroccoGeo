"""
Step 10 - Vegetation health (NDVI) per province and month, 2000-02 -> latest, via Google Earth Engine.

Data (computed on Google's servers, only a small table comes back):
  - MODIS MOD13Q1 v061 (NASA): NDVI every 16 days at 250 m. Pixels kept only if
    SummaryQA <= 1 (good or marginal quality; clouds/snow removed). NDVI = value x 0.0001.
  - ESA WorldCover v200 (10 m land cover, 2021): class 40 = cropland, class 80 = water.
    The cropland share of each 250 m MODIS cell is computed; cells with >= 50 % cropland count
    as farmland.
For each month: average of the MODIS images of that month, then per province:
  ndvi_crop = mean NDVI over farmland cells, ndvi_all = mean NDVI over all land cells,
  crop_share_pct = share of the province's cells that are farmland.
Speed: the 12 months of a year are stacked into ONE image and sent in ONE request, so the
costly 10 m -> 250 m farmland conversion runs once per year (~4 min) instead of once per
month (~3.5 min each, ~19 h in total).

Output: clean/ndvi_monthly.csv  (month_start ; shape_id ; ndvi_crop ; ndvi_all ; crop_share_pct)
Resumable: each year is cached in raw/ndvi/ndvi_<year>.csv; the current and previous year are
always refreshed (new images arrive every 16 days).
Earth Engine project: droughtmorocco (non-commercial, Community tier).
Usage:  python 08_ndvi.py <ProjectRoot>
"""
import csv
import sys
import time
from datetime import date
from pathlib import Path

import ee
import geopandas as gpd

PROJECT = "droughtmorocco"
FIRST_YEAR = 2000


def provinces_fc(root: Path):
    gdf = gpd.read_file(root / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson")
    gdf["geometry"] = gdf.geometry.simplify(0.003, preserve_topology=True)   # ~300 m, lighter upload
    gdf = gdf[["shapeID", "geometry"]]
    return ee.FeatureCollection(gdf.__geo_interface__), len(gdf)


def layers():
    modis = ee.ImageCollection("MODIS/061/MOD13Q1")
    proj = modis.first().select("NDVI").projection()
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    crop_share = (wc.eq(40).reduceResolution(ee.Reducer.mean(), maxPixels=1024)
                    .reproject(proj))
    land = wc.neq(80).And(wc.neq(0)).reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(proj)
    return modis, crop_share.gte(0.5), land.gte(0.5)


def month_ndvi(modis, y, m):
    start = ee.Date.fromYMD(y, m, 1)
    col = modis.filterDate(start, start.advance(1, "month"))
    return col.map(lambda img: img.select("NDVI")
                   .updateMask(img.select("SummaryQA").lte(1)).multiply(0.0001)).mean()


def fetch_year(fc, modis, crop, land, year, last: date):
    months = [m for m in range(1, 13)
              if date(year, m, 1) <= last and not (year == 2000 and m == 1)]   # MODIS starts 18 Feb 2000
    bands = [crop.unmask(0).rename("cropshare")]
    for m in months:
        nd = month_ndvi(modis, year, m)
        bands += [nd.updateMask(crop).rename(f"c{m:02d}"), nd.updateMask(land).rename(f"a{m:02d}")]
    res = ee.Image.cat(bands).reduceRegions(collection=fc, reducer=ee.Reducer.mean(),
                                            scale=250, tileScale=4)
    for attempt in range(4):
        try:
            feats = res.getInfo()["features"]
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"    retry {year}: {str(e)[:100]}")
            time.sleep(30 * (attempt + 1))

    def val(p, k):
        return "" if p.get(k) is None else round(p[k], 4)

    out = []
    for f in feats:
        p = f["properties"]
        share = round(100 * (p.get("cropshare") or 0), 1)
        for m in months:
            out.append([f"{year}-{m:02d}-01", p["shapeID"], val(p, f"c{m:02d}"), val(p, f"a{m:02d}"), share])
    return sorted(out)


def main(root: Path) -> int:
    ee.Initialize(project=PROJECT)
    cache = root / "raw" / "ndvi"
    cache.mkdir(parents=True, exist_ok=True)
    out_csv = root / "clean" / "ndvi_monthly.csv"

    fc, n_prov = provinces_fc(root)
    modis, crop, land = layers()
    last_ms = modis.aggregate_max("system:time_start").getInfo()
    last = date.fromtimestamp(last_ms / 1000).replace(day=1)
    print(f"MODIS available up to {last:%Y-%m}")

    t0 = time.time()
    for year in range(FIRST_YEAR, last.year + 1):
        f = cache / f"ndvi_{year}.csv"
        if f.exists() and year < last.year - 1:
            continue
        rows = fetch_year(fc, modis, crop, land, year, last)
        with open(f, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter=";", lineterminator="\n").writerows(rows)
        print(f"  {year}: {len(rows)} rows ({time.time() - t0:.0f}s)")

    rows = []
    for year in range(FIRST_YEAR, last.year + 1):
        with open(cache / f"ndvi_{year}.csv", encoding="utf-8") as fh:
            rows += list(csv.reader(fh, delimiter=";"))

    errors = []
    months = sorted({r[0] for r in rows})
    if len(rows) != len(months) * n_prov:
        errors.append(f"expected {len(months) * n_prov} rows, got {len(rows)}")
    vals = [float(r[3]) for r in rows if r[3] != ""]
    if vals and not (-0.2 <= min(vals) and max(vals) <= 1):
        errors.append(f"NDVI out of range: {min(vals)}..{max(vals)}")
    no_all = sum(1 for r in rows if r[3] == "")
    no_crop = sum(1 for r in rows if r[2] == "")

    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["month_start", "shape_id", "ndvi_crop", "ndvi_all", "crop_share_pct"])
        w.writerows(rows)
    print(f"Rows: {len(rows):,} | months: {months[0]} -> {months[-1]} ({len(months)}) | "
          f"no farmland value: {no_crop} | no land value: {no_all}")
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
