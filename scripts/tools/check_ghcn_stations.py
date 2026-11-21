"""
Independent check of the satellite rainfall (CHIRPS) and of the drought index (SPI-12) against real
rain gauges: NOAA GHCN-Daily, the Moroccan weather stations with rain records after 2005.

Station data: daily PRCP (tenths of mm / 10), values with a NOAA quality flag removed; a month is kept
only if >= 90 % of its days were recorded (a missing day is not a dry day). A longer period (season,
year, 12-month window) is kept only if ALL its months are complete.

Four tests, each comparing the station with the CHIRPS pixel that contains it (point vs point),
except the SPI test, which uses the province SPI-12 the project publishes:
  1. Months            Pearson r of monthly rain.
  2. Seasons           r of 3-month totals: Dec-Feb, Mar-May, Jun-Aug, Sep-Nov.
  3. Years             r of hydrological-year totals, September -> August.
  4. SPI-12            the station's own drought index (standardized 12-month rain: (x - mean) / std of the
                       station's complete 12-month windows) vs the province SPI-12 at the same end month:
                       r, and the share of windows where both agree on "drought" (<= -1) or "no drought",
                       with the province SPI re-centred on the same windows (same reference years; the
                       raw agreement against the published 1991-2020 SPI is reported beside it).
Pass rules (fixed before looking at the results; a station is judged when it has >= 60 months,
>= 20 seasons, >= 5 years, >= 24 SPI windows for that test):
  1. median r >= 0.80 and every station >= 0.60
  2. median r >= 0.85 and every station >= 0.60
  3. median r >= 0.85 and every station >= 0.60
  4. median r >= 0.75, every station >= 0.50, median drought agreement >= 80 %

Downloads go to raw/ghcn/ (one CSV per station, skipped when present; --refresh re-downloads).
Writes clean/ghcn_vs_chirps_monthly.csv and clean/ghcn_station_summary.csv.
Usage:  python scripts/tools/check_ghcn_stations.py [--refresh]
"""
import calendar
import math
import sys
import time
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "ghcn"
CHIRPS_DIR = ROOT / "raw" / "chirps" / "morocco"
BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/"
ACCESS = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/"
UA = {"User-Agent": "drought-observatory-check/1.0"}

# test name -> (minimum points to judge a station, median threshold, minimum threshold)
RULES = {"months": (60, 0.80, 0.60), "seasons": (20, 0.85, 0.60), "years": (5, 0.85, 0.60), "spi12": (24, 0.75, 0.50)}
SPI_AGREE_MIN = 80.0


def download(url, path, refresh=False):
    if path.exists() and not refresh:
        return
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                path.write_bytes(r.read())
            return
        except Exception as e:                       # network: retry with growing pauses
            if attempt == 4:
                raise
            print(f"  retry {url} ({e})")
            time.sleep(10 * (attempt + 1))


def stations(refresh):
    for f in ("ghcnd-stations.txt", "ghcnd-inventory.txt"):
        download(BASE + f, RAW / f, refresh)
    inv = [l.split() for l in (RAW / "ghcnd-inventory.txt").read_text().splitlines() if l.startswith("MO")]
    keep = {s[0] for s in inv if s[3] == "PRCP" and int(s[5]) >= 2005}
    rows = []
    for l in (RAW / "ghcnd-stations.txt").read_text().splitlines():
        if l[:11] in keep:
            rows.append({"station": l[:11], "lat": float(l[12:20]), "lon": float(l[21:30]),
                         "name": l[41:71].strip().title()})
    return pd.DataFrame(rows)


def monthly_station(path):
    d = pd.read_csv(path, usecols=lambda c: c in ("DATE", "PRCP", "PRCP_ATTRIBUTES"), low_memory=False)
    d = d.dropna(subset=["PRCP"])
    qflag = d["PRCP_ATTRIBUTES"].fillna(",,").str.split(",").str[1].str.strip()
    d = d[qflag == ""]                                        # quality flag set = failed a NOAA check
    d["DATE"] = pd.to_datetime(d["DATE"])
    d = d[d["DATE"] >= "1991-01-01"]
    d["month"] = d["DATE"].dt.strftime("%Y-%m")
    g = d.groupby("month").agg(days=("PRCP", "size"), rain=("PRCP", "sum")).reset_index()
    need = g["month"].map(lambda m: math.ceil(0.9 * calendar.monthrange(int(m[:4]), int(m[5:]))[1]))
    g = g[g["days"] >= need]
    g["station_mm"] = g["rain"] / 10.0
    return g[["month", "station_mm"]]


def r(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if len(a) >= 3 else float("nan")


def longer_periods(g, spi, first, last):
    """Seasons, hydrological years and SPI-12 windows, from complete months only."""
    idx = pd.period_range(first, last, freq="M")
    s = g.set_index(pd.PeriodIndex(g.month, freq="M"))[["station_mm", "chirps_pixel_mm"]].reindex(idx)
    out = {}
    # 2. seasons: 3-month windows ending Feb, May, Aug, Nov (all 3 months complete)
    w3 = s.rolling(3, min_periods=3).sum()
    se = w3[w3.index.month.isin([2, 5, 8, 11])].dropna()
    out["seasons"] = (len(se), r(se.station_mm, se.chirps_pixel_mm))
    # 3. hydrological years: 12-month windows ending in August
    w12 = s.rolling(12, min_periods=12).sum()
    yr = w12[w12.index.month == 8].dropna()
    out["years"] = (len(yr), r(yr.station_mm, yr.chirps_pixel_mm))
    # 4. SPI-12: station standardized 12-month rain vs the province SPI-12 published by the project
    win = w12.dropna()
    z = (win.station_mm - win.station_mm.mean()) / win.station_mm.std()
    p = spi.reindex(win.index)
    ok = p.notna()
    z, p = z[ok], p[ok]
    # The station index is centred on the years the station happens to have complete; the published SPI is
    # centred on 1991-2020. To compare drought calls on the SAME reference years, the province SPI is
    # re-centred on those same windows too (pz). The raw agreement is reported beside it.
    pz = (p - p.mean()) / p.std() if len(p) > 1 else p
    agree = 100.0 * ((z <= -1) == (pz <= -1)).mean() if len(z) else float("nan")
    agree_raw = 100.0 * ((z <= -1) == (p <= -1)).mean() if len(z) else float("nan")
    out["spi12"] = (len(z), r(z, p), agree, int(((z <= -1) & (pz <= -1)).sum()), int((z <= -1).sum()),
                    agree_raw, float(p.mean()) if len(p) else float("nan"))
    return out


def main(refresh=False):
    RAW.mkdir(parents=True, exist_ok=True)
    st = stations(refresh)
    print(f"Stations with rain records after 2005: {len(st)}")

    # province of each station (point in polygon) -> CHIRPS province rain and province SPI-12
    prov = gpd.read_file(ROOT / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson")[["shapeID", "geometry"]]
    pts = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.lon, st.lat), crs="EPSG:4326")
    st = pd.DataFrame(gpd.sjoin(pts, prov.to_crs("EPSG:4326"), how="left", predicate="within").drop(columns="geometry"))
    hcp = pd.read_csv(ROOT / "clean" / "boundaries_provinces.csv", sep=";")
    st["province"] = st["shapeID"].map(dict(zip(hcp["shape_id"], hcp["shape_name"])))
    chirps_prov = pd.read_csv(ROOT / "clean" / "chirps_monthly.csv", sep=";")
    chirps_prov["month"] = chirps_prov["month_start"].str[:7]
    spi = pd.read_csv(ROOT / "clean" / "spi_monthly.csv", sep=";")
    spi = spi[spi.spi_scale == 12]

    # CHIRPS pixel under each station, every month (one pass over the 430 images)
    xy = list(zip(st.lon, st.lat))
    pix = []
    for tif in sorted(CHIRPS_DIR.glob("chirps-v3.0.*.tif")):
        y, m = tif.stem.split(".")[-2:]
        with rasterio.open(tif) as rs:
            vals = [v[0] for v in rs.sample(xy)]
        for s, v in zip(st.station, vals):
            pix.append({"station": s, "month": f"{y}-{m}", "chirps_pixel_mm": None if v < -9000 else float(v)})
    pix = pd.DataFrame(pix)
    first, last = pix["month"].min(), pix["month"].max()

    allm, summary = [], []
    for s in st.itertuples():
        download(ACCESS + f"{s.station}.csv", RAW / f"{s.station}.csv", refresh)
        g = monthly_station(RAW / f"{s.station}.csv")
        g = g.merge(pix[pix.station == s.station], on="month").dropna(subset=["chirps_pixel_mm"])
        cp = chirps_prov[chirps_prov.shape_id == s.shapeID][["month", "rain_mm"]].rename(columns={"rain_mm": "chirps_province_mm"})
        g = g.merge(cp, on="month", how="left")
        g = g[g["month"] <= last]
        g["name"] = s.name
        allm.append(g)
        ps = spi[spi.shape_id == s.shapeID]
        ps = pd.Series(ps.spi.values, index=pd.PeriodIndex(ps.month_start.str[:7], freq="M"))
        lp = longer_periods(g, ps, first, last)
        summary.append({
            "name": s.name, "province": s.province, "months": len(g),
            "r_months": round(r(g.station_mm, g.chirps_pixel_mm), 3),
            "seasons": lp["seasons"][0], "r_seasons": round(lp["seasons"][1], 3),
            "years": lp["years"][0], "r_years": round(lp["years"][1], 3),
            "spi_windows": lp["spi12"][0], "r_spi12": round(lp["spi12"][1], 3),
            "spi_agree_pct": round(lp["spi12"][2], 1),
            "spi_agree_raw_pct": round(lp["spi12"][5], 1),
            "spi_mean_on_windows": round(lp["spi12"][6], 2),
            "station_droughts_seen": f"{lp['spi12'][3]}/{lp['spi12'][4]}",
            "bias_pct": round(100 * (g.chirps_pixel_mm.sum() / g.station_mm.sum() - 1), 1) if len(g) else None,
        })

    pd.concat(allm).to_csv(ROOT / "clean" / "ghcn_vs_chirps_monthly.csv", sep=";", index=False)
    sm = pd.DataFrame(summary)
    sm.to_csv(ROOT / "clean" / "ghcn_station_summary.csv", sep=";", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(sm.drop(columns=["province"]).to_string(index=False))

    print()
    counts = {"months": "months", "seasons": "seasons", "years": "years", "spi12": "spi_windows"}
    cols = {"months": "r_months", "seasons": "r_seasons", "years": "r_years", "spi12": "r_spi12"}
    results = {}
    for test, (n_min, med_min, low_min) in RULES.items():
        j = sm[sm[counts[test]] >= n_min]
        med, low = j[cols[test]].median(), j[cols[test]].min()
        ok = len(j) >= 5 and med >= med_min and low >= low_min
        extra = ""
        if test == "spi12":
            agree = j.spi_agree_pct.median()
            ok = ok and agree >= SPI_AGREE_MIN
            extra = f" | median drought agreement {agree:.0f} % (rule >= {SPI_AGREE_MIN:.0f} %)"
        weakest = j.loc[j[cols[test]].idxmin(), "name"] if len(j) else "-"
        print(f"{test:8s} stations {len(j):2d} | median r {med:.3f} (rule >= {med_min}) | min r {low:.3f} "
              f"(rule >= {low_min}, {weakest}){extra}  {'PASS' if ok else 'FAIL'}")
        results[test] = ok
    passed = sum(results.values())
    print(f"\nAll stations: {passed} / {len(results)} GHCN tests passed")

    # Same rules, by climate zone. Zone = the station's own mean annual rain (mean of each calendar month
    # over its complete months x 12); < 250 mm/year = arid, the usual threshold. This split was added after
    # the first run, once the failures were seen to come from the driest stations; the rules are unchanged.
    allm = pd.concat(allm)
    allm["mo"] = allm.month.str[5:]
    annual = allm.groupby(["name", "mo"]).station_mm.mean().groupby("name").sum()
    sm["annual_mm"] = sm.name.map(annual).round(0)
    sm["zone"] = np.where(sm.annual_mm < 250, "arid (< 250 mm/year)", "semi-arid / humid (>= 250 mm/year)")
    sm.to_csv(ROOT / "clean" / "ghcn_station_summary.csv", sep=";", index=False)
    for zone, zg in sm.groupby("zone", sort=False):
        print(f"\n{zone}: {', '.join(zg.sort_values('annual_mm').name)}")
        for test, (n_min, med_min, low_min) in RULES.items():
            j = zg[zg[counts[test]] >= n_min]
            if len(j) < 3:
                print(f"  {test:8s} stations {len(j):2d} | too few stations to judge")
                continue
            med, low = j[cols[test]].median(), j[cols[test]].min()
            ok = med >= med_min and low >= low_min
            if test == "spi12":
                ok = ok and j.spi_agree_pct.median() >= SPI_AGREE_MIN
            weakest = j.loc[j[cols[test]].idxmin(), "name"]
            print(f"  {test:8s} stations {len(j):2d} | median r {med:.3f} | min r {low:.3f} ({weakest})  {'PASS' if ok else 'FAIL'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main("--refresh" in sys.argv))
