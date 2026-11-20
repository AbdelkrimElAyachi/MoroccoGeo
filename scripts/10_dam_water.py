"""
Step 11 (part 2) - Monthly water surface of Morocco's main reservoirs, 2000 -> latest,
via Google Earth Engine, from two satellite sources:

  2017 -> latest: Sentinel-2 (source "S2")
    1. Sentinel-2 L1C images of the month (COPERNICUS/S2_HARMONIZED, 10-20 m).
    2. Clouds removed with the Sentinel-2 cloud probability product (probability < 40 %).
    3. Monthly median image, then water index NDWI = (Green - NIR) / (Green + NIR) = (B3 - B8) / (B3 + B8).
       NDWI > 0 means water (McFeeters 1996).
  2000 -> 2016: JRC Global Surface Water, monthly history (source "JRC")
    Landsat-based water / not-water map per month at 30 m (Pekel et al. 2016), band "water":
    0 = no data, 1 = not water, 2 = water. Coverage over Morocco is patchy before ~2013
    (Landsat 7 sensor fault since 2003, few Landsat 5 images over Africa): those months get a low
    clear_pct and are flagged unreliable downstream (clear_pct < 80).
  For each reservoir (raw/dams/reservoirs.geojson, outline + 300 m) and month:
    water_km2 = area of water pixels; clear_pct = share of the reservoir area with a valid value.

Overlap check: JRC is also computed for 2017-2021 (both sources available) and written to
clean/dam_water_overlap.csv so the two satellites can be compared lake by lake.

The 12 months of a year are computed in one request per year and source (cached in
raw/dams/water_<year>.csv for S2, raw/dams/water_jrc_<year>.csv for JRC; the current and previous
year of S2 are always refreshed; JRC ends in 2021 and never changes).

Output: clean/dam_water_monthly.csv  (month_start ; dam_id ; water_km2 ; clear_pct ; source)
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
FIRST_YEAR = 2017           # first Sentinel-2 year
JRC_FIRST_YEAR = 2000       # JRC used for 2000-2016
JRC_LAST_YEAR = 2021        # JRC ends in December 2021; 2017-2021 used only for the overlap check
JRC_SCALE = 30
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


def fetch_year_jrc(fc, year):
    """JRC monthly water history for one year (12 months stacked, one request)."""
    col = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filter(ee.Filter.eq("year", year))
    area = ee.Image.pixelArea().divide(1e6)
    bands = []
    for m in range(1, 13):
        wat = ee.Image(col.filter(ee.Filter.eq("month", m)).first()).select("water")
        bands += [area.updateMask(wat.eq(2)).rename(f"w{m:02d}"),      # water
                  area.updateMask(wat.gt(0)).rename(f"v{m:02d}")]      # observed (water or land)
    res = ee.Image.cat(bands + [area.rename("total")]).reduceRegions(
        collection=fc, reducer=ee.Reducer.sum(), scale=JRC_SCALE, tileScale=4)
    for attempt in range(4):
        try:
            feats = res.getInfo()["features"]
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"    retry JRC {year}: {str(e)[:120]}")
            time.sleep(30 * (attempt + 1))
    out = []
    for f in feats:
        p = f["properties"]
        tot = p.get("total") or 0
        for m in range(1, 13):
            w, v = p.get(f"w{m:02d}") or 0, p.get(f"v{m:02d}") or 0
            out.append([f"{year}-{m:02d}-01", int(p["dam_id"]), round(w, 3),
                        round(100 * v / tot, 1) if tot else 0])
    return sorted(out)


def read_cache(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.reader(fh, delimiter=";"))


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
        print(f"  S2 {year}: {len(rows)} rows ({time.time() - t0:.0f}s)")

    for year in range(JRC_FIRST_YEAR, JRC_LAST_YEAR + 1):      # JRC never changes: cache forever
        f = cache / f"water_jrc_{year}.csv"
        if f.exists():
            continue
        rows = fetch_year_jrc(fc, year)
        with open(f, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter=";", lineterminator="\n").writerows(rows)
        print(f"  JRC {year}: {len(rows)} rows ({time.time() - t0:.0f}s)")

    s2 = [r + ["S2"] for y in range(FIRST_YEAR, last.year + 1) for r in read_cache(cache / f"water_{y}.csv")]
    jrc_all = [r for y in range(JRC_FIRST_YEAR, JRC_LAST_YEAR + 1) for r in read_cache(cache / f"water_jrc_{y}.csv")]
    jrc = [r + ["JRC"] for r in jrc_all if int(r[0][:4]) < FIRST_YEAR]
    rows = sorted(jrc + s2)

    # Overlap 2017-2021: the same lake and month seen by both satellites
    s2_idx = {(r[0], r[1]): r for r in s2}
    overlap = [[r[0], r[1], r[2], r[3], s2_idx[(r[0], r[1])][2], s2_idx[(r[0], r[1])][3]]
               for r in jrc_all if int(r[0][:4]) >= FIRST_YEAR and (r[0], r[1]) in s2_idx]
    with open(root / "clean" / "dam_water_overlap.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["month_start", "dam_id", "jrc_water_km2", "jrc_clear_pct", "s2_water_km2", "s2_clear_pct"])
        w.writerows(overlap)

    months = sorted({r[0] for r in rows})
    errors = []
    if len(rows) != len(months) * n:
        errors.append(f"expected {len(months) * n} rows, got {len(rows)}")
    if len({(r[0], r[1]) for r in rows}) != len(rows):
        errors.append("duplicate (month, dam) rows")
    low_jrc = sum(1 for r in jrc if float(r[3]) < 80)
    low_s2 = sum(1 for r in s2 if float(r[3]) < 80)

    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["month_start", "dam_id", "water_km2", "clear_pct", "source"])
        w.writerows(rows)
    print(f"Rows: {len(rows):,} | months: {months[0]} -> {months[-1]} | "
          f"unreliable (< 80 % visible): JRC {low_jrc}/{len(jrc)}, S2 {low_s2}/{len(s2)} | "
          f"overlap pairs 2017-2021: {len(overlap)}")
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
