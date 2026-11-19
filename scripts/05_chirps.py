"""
Step 8 - CHIRPS v3 monthly rainfall per province, 1991 -> latest month available.

For each month:
  1. If the Morocco crop already exists in raw/chirps/morocco/, skip the download.
     Otherwise download the Africa file (~4.9 MB), cut out Morocco, save the small
     crop (~100 KB) and delete the Africa file. Every download is recorded in
     raw/chirps/manifest.csv (file, url, date, size).
  2. Average the pixels inside each of the 75 provinces (zonal statistics).
Then write clean/chirps_monthly.csv for SSIS:
     month_start ; shape_id ; rain_mm

Checks: 75 provinces every month, no missing month, no missing or negative values.
Usage:  python 05_chirps.py <ProjectRoot>
"""
import csv
import re
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterstats import zonal_stats

BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/"
START = date(1991, 1, 1)
PAD = 0.2   # degrees around Morocco when cropping


def latest_month() -> date:
    html = urllib.request.urlopen(BASE, timeout=60).read().decode("utf-8", "ignore")
    months = re.findall(r"chirps-v3\.0\.(\d{4})\.(\d{2})\.tif", html)
    y, m = max((int(a), int(b)) for a, b in months)
    return date(y, m, 1)


def month_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def get_crop(month: date, crop_dir: Path, tmp_dir: Path, bounds, manifest: Path) -> Path:
    name = f"chirps-v3.0.{month:%Y.%m}.tif"
    crop = crop_dir / name
    if crop.exists():
        return crop
    url = BASE + name
    tmp = tmp_dir / name
    for attempt in range(5):
        try:
            # timeout: if the server stops answering for 60 s, give up and retry
            # (urlretrieve has no timeout and once hung for 20+ minutes)
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            break
        except Exception as e:
            if attempt == 4:
                raise
            print(f"  retry {attempt + 1} for {name}: {e}")
            time.sleep(10 * (attempt + 1))
    size = tmp.stat().st_size
    with rasterio.open(tmp) as src:
        win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        data = src.read(1, window=win)
        profile = src.profile.copy()
        profile.update(height=data.shape[0], width=data.shape[1],
                       transform=src.window_transform(win), compress="deflate")
    with rasterio.open(crop, "w", **profile) as dst:
        dst.write(data, 1)
    tmp.unlink()
    new = not manifest.exists()
    with open(manifest, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        if new:
            w.writerow(["file", "url", "downloaded_at", "original_bytes", "crop_bytes"])
        w.writerow([name, url, datetime.now().isoformat(timespec="seconds"), size, crop.stat().st_size])
    return crop


def main(root: Path) -> int:
    crop_dir = root / "raw" / "chirps" / "morocco"
    tmp_dir = root / "raw" / "chirps" / "_tmp"
    manifest = root / "raw" / "chirps" / "manifest.csv"
    out_csv = root / "clean" / "chirps_monthly.csv"
    for d in (crop_dir, tmp_dir, out_csv.parent):
        d.mkdir(parents=True, exist_ok=True)

    prov = gpd.read_file(root / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson")
    minx, miny, maxx, maxy = prov.total_bounds
    bounds = (minx - PAD, miny - PAD, maxx + PAD, maxy + PAD)

    end = latest_month()
    months = list(month_range(START, end))
    print(f"Months: {months[0]:%Y-%m} -> {months[-1]:%Y-%m} ({len(months)})")

    rows, errors = [], []
    t0 = time.time()
    for i, m in enumerate(months, 1):
        tif = get_crop(m, crop_dir, tmp_dir, bounds, manifest)
        stats = zonal_stats(prov, str(tif), stats=["mean"], nodata=-9999)
        for sid, s in zip(prov["shapeID"], stats):
            v = s["mean"]
            if v is None:   # very small province: use every touched pixel
                v = zonal_stats(prov[prov.shapeID == sid], str(tif), stats=["mean"],
                                nodata=-9999, all_touched=True)[0]["mean"]
            rows.append((m.isoformat(), sid, None if v is None else round(float(v), 2)))
        if i % 24 == 0 or i == len(months):
            print(f"  {i}/{len(months)} months done ({time.time() - t0:.0f}s)")

    # Checks
    vals = np.array([r[2] for r in rows if r[2] is not None])
    missing = sum(r[2] is None for r in rows)
    if missing:
        errors.append(f"{missing} province-months without a value")
    if (vals < 0).any():
        errors.append("negative rainfall values")
    if len(rows) != len(months) * len(prov):
        errors.append(f"expected {len(months) * len(prov)} rows, got {len(rows)}")

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["month_start", "shape_id", "rain_mm"])
        w.writerows(rows)

    print(f"Rows: {len(rows):,} | provinces: {len(prov)} | months: {len(months)} "
          f"| mean monthly rain: {vals.mean():.1f} mm")
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
