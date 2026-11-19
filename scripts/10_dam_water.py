"""
Step 11 (part 2) - Monthly water surface of Morocco's main reservoirs, 2017 -> latest,
from Sentinel-2 via Google Earth Engine.

For each reservoir (raw/dams/reservoirs.geojson from 09_reservoirs.py, outline + 300 m) and month:
  1. Sentinel-2 L1C images of the month (COPERNICUS/S2_HARMONIZED, 10-20 m).
  2. Clouds removed with the Sentinel-2 cloud probability product (probability < 40 %).
  3. Monthly median image, then water index NDWI = (Green - NIR) / (Green + NIR) = (B3 - B8) / (B3 + B8).
     NDWI > 0 means water (McFeeters 1996).
  4. water_km2 = area of water pixels; clear_pct = share of the reservoir area with a cloud-free
     value that month (months with little clear sky are flagged, not dropped).
The 12 months of a year are computed in one request per year (cached in raw/dams/water_<year>.csv;
current and previous year always refreshed).

Output: clean/dam_water_monthly.csv  (month_start ; dam_id ; water_km2 ; clear_pct)
Usage:  python 10_dam_water.py <ProjectRoot>
"""
import csv
import sys
import time
from datetime import date
from pathlib import Path

import ee
import geopandas as gpd

PROJECT = "droughtmorocco"
FIRST_YEAR = 2017
BUFFER_M = 300
SCALE = 20          # metres; enough for reservoirs of several km2, 4x cheaper than 10 m
CLOUD_PROB_MAX = 40


def reservoirs_fc(root: Path):
    gdf = gpd.read_file(root / "raw" / "dams" / "reservoirs.geojson")
    g = gdf.to_crs("EPSG:32629")
    g["geometry"] = g.geometry.buffer(BUFFER_M).simplify(30)
    gdf = g.to_crs("EPSG:4326")[["dam_id", "geometry"]]
    return ee.FeatureCollection(gdf.__geo_interface__), len(gdf)


def month_water(y, m, region):
    start = ee.Date.fromYMD(y, m, 1)
    end = start.advance(1, "month")
    s2 = ee.ImageCollection("COPERNICUS/S2_HARMONIZED").filterBounds(region).filterDate(start, end)
    prob = ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY").filterBounds(region).filterDate(start, end)
    joined = ee.Join.saveFirst("cloud").apply(
        s2, prob, ee.Filter.equals(leftField="system:index", rightField="system:index"))

    def mask(img):
        img = ee.Image(img)
        clear = ee.Image(img.get("cloud")).select("probability").lt(CLOUD_PROB_MAX)
        return img.select(["B3", "B8"]).updateMask(clear)

    med = ee.ImageCollection(joined).map(mask).median()
    ndwi = med.normalizedDifference(["B3", "B8"])
    area = ee.Image.pixelArea().divide(1e6)                          # km2 per pixel
    water = area.updateMask(ndwi.gt(0)).rename(f"w{m:02d}")
    valid = area.updateMask(ndwi.mask()).rename(f"v{m:02d}")
    return water, valid


def fetch_year(fc, year, last: date):
    months = [m for m in range(1, 13) if date(year, m, 1) <= last]
    region = fc.geometry().bounds()
    bands = [area for m in months for area in month_water(year, m, region)]
    total = ee.Image.pixelArea().divide(1e6).rename("total")
    res = ee.Image.cat(bands + [total]).reduceRegions(
        collection=fc, reducer=ee.Reducer.sum(), scale=SCALE, tileScale=4)
    for attempt in range(4):
        try:
            feats = res.getInfo()["features"]
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"    retry {year}: {str(e)[:120]}")
            time.sleep(30 * (attempt + 1))
    out = []
    for f in feats:
        p = f["properties"]
        tot = p.get("total") or 0
        for m in months:
            w, v = p.get(f"w{m:02d}") or 0, p.get(f"v{m:02d}") or 0
            out.append([f"{year}-{m:02d}-01", int(p["dam_id"]), round(w, 3),
                        round(100 * v / tot, 1) if tot else 0])
    return sorted(out)


def main(root: Path) -> int:
    ee.Initialize(project=PROJECT)
    cache = root / "raw" / "dams"
    out_csv = root / "clean" / "dam_water_monthly.csv"
    fc, n = reservoirs_fc(root)
    last_ms = (ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
               .filterBounds(fc.geometry().bounds()).filterDate("2026-01-01", "2030-01-01")
               .aggregate_max("system:time_start").getInfo())
    last = date.fromtimestamp(last_ms / 1000).replace(day=1)
    print(f"Reservoirs: {n} | Sentinel-2 available up to {last:%Y-%m}")

    t0 = time.time()
    for year in range(FIRST_YEAR, last.year + 1):
        f = cache / f"water_{year}.csv"
        if f.exists() and year < last.year - 1:
            continue
        rows = fetch_year(fc, year, last)
        with open(f, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter=";", lineterminator="\n").writerows(rows)
        print(f"  {year}: {len(rows)} rows ({time.time() - t0:.0f}s)")

    rows = []
    for year in range(FIRST_YEAR, last.year + 1):
        with open(cache / f"water_{year}.csv", encoding="utf-8") as fh:
            rows += list(csv.reader(fh, delimiter=";"))
    months = sorted({r[0] for r in rows})
    errors = []
    if len(rows) != len(months) * n:
        errors.append(f"expected {len(months) * n} rows, got {len(rows)}")
    low_clear = sum(1 for r in rows if float(r[3]) < 80)

    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["month_start", "dam_id", "water_km2", "clear_pct"])
        w.writerows(rows)
    print(f"Rows: {len(rows):,} | months: {months[0]} -> {months[-1]} | "
          f"months with < 80 % clear sky: {low_clear}")
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
