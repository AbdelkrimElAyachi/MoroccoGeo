"""
Two more checks of the dataset against real, independent measurements.

TEST 1 - Temperature vs weather stations (NOAA GHCN-Daily, the same 11+ Moroccan stations as
         check_ghcn_stations.py, files in raw/ghcn/). Daily maximum temperature TMAX (tenths of degC / 10),
         values with a NOAA quality flag removed, compared with the project's daily weather (Open-Meteo, ERA5)
         for the province that contains the station. The weather point of a province is its representative
         point, not the station: the distance is reported, and so is the mean difference (altitude and
         coast effects), which is not judged.
         a) monthly mean TMAX (months with >= 90 % of days at the station): Pearson r
         b) daily anomalies: each day minus the station's / the grid's own mean for that calendar day,
            so the summer-winter cycle cannot inflate the score: Pearson r
         Rules (fixed before the run; a station is judged with >= 60 months):
           a) median r >= 0.95 and every station >= 0.90
           b) median r >= 0.70 and every station >= 0.50

TEST 2 - Farmland greenness vs the official wheat harvest. National March NDVI over cropland (mean of the
         provinces, MODIS) vs the wheat yield reported by Morocco to FAOSTAT, 2001-2024.
         Rules (fixed before the run): Pearson r >= 0.70, and in >= 4 of the 5 worst harvest years the
         March NDVI is below its 2001-2024 median.

Writes clean/check_temperature_stations.csv. Usage: python scripts/tools/check_real_world.py
"""
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_ghcn_stations import ACCESS, RAW, ROOT, download, stations  # noqa: E402


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(a))


def station_tmax(path):
    d = pd.read_csv(path, usecols=lambda c: c in ("DATE", "TMAX", "TMAX_ATTRIBUTES"), low_memory=False)
    d = d.dropna(subset=["TMAX"])
    qflag = d["TMAX_ATTRIBUTES"].fillna(",,").str.split(",").str[1].str.strip()
    d = d[(qflag == "") & (d.DATE >= "1991-01-01")]
    return pd.Series(d.TMAX.values / 10.0, index=pd.to_datetime(d.DATE), name="station")


def test_temperature():
    st = stations(False)
    prov = gpd.read_file(ROOT / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson")[["shapeID", "geometry"]]
    pts = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.lon, st.lat), crs="EPSG:4326")
    st = pd.DataFrame(gpd.sjoin(pts, prov.to_crs("EPSG:4326"), how="left", predicate="within").drop(columns="geometry"))
    bp = pd.read_csv(ROOT / "clean" / "boundaries_provinces.csv", sep=";").set_index("shape_id")
    w = pd.read_csv(ROOT / "clean" / "weather_daily.csv", sep=";", usecols=["day", "shape_id", "tmax_c"])
    w["day"] = pd.to_datetime(w["day"])

    rows = []
    for s in st.itertuples():
        download(ACCESS + f"{s.station}.csv", RAW / f"{s.station}.csv")
        sta = station_tmax(RAW / f"{s.station}.csv")
        grid = w[w.shape_id == s.shapeID].set_index("day")["tmax_c"].rename("grid")
        d = pd.concat([sta, grid], axis=1, join="inner").dropna()
        p = bp.loc[s.shapeID]
        dist = km(s.lat, s.lon, p.point_lat, p.point_lon)
        # a) monthly means, months with >= 90 % of days
        d["m"] = d.index.to_period("M")
        mm = d.groupby("m").agg(n=("station", "size"), st=("station", "mean"), gr=("grid", "mean"))
        need = mm.index.map(lambda m: math.ceil(0.9 * m.days_in_month))
        mm = mm[mm.n >= need]
        # b) daily anomalies from each series' own mean for that calendar day
        doy = d.index.strftime("%m-%d")
        an_st = d.station - d.station.groupby(doy).transform("mean")
        an_gr = d.grid - d.grid.groupby(doy).transform("mean")
        rows.append({
            "name": s.name, "km_to_weather_point": round(dist), "days": len(d), "months": len(mm),
            "r_monthly": round(float(np.corrcoef(mm.st, mm.gr)[0, 1]), 3) if len(mm) > 2 else None,
            "r_daily_anomaly": round(float(np.corrcoef(an_st, an_gr)[0, 1]), 3) if len(d) > 2 else None,
            "mean_diff_c": round(float((d.grid - d.station).mean()), 1) if len(d) else None,
        })
    t = pd.DataFrame(rows)
    t.to_csv(ROOT / "clean" / "check_temperature_stations.csv", sep=";", index=False)
    print("TEST 1 - Daily maximum temperature: weather stations (NOAA) vs project weather data (Open-Meteo)")
    print(t.to_string(index=False))
    j = t[t.months >= 60]
    a = j.r_monthly.median() >= 0.95 and j.r_monthly.min() >= 0.90
    b = j.r_daily_anomaly.median() >= 0.70 and j.r_daily_anomaly.min() >= 0.50
    print(f"\n  a) monthly mean   stations {len(j)} | median r {j.r_monthly.median():.3f} (rule >= 0.95) | "
          f"min r {j.r_monthly.min():.3f} (rule >= 0.90, {j.loc[j.r_monthly.idxmin(), 'name']})  {'PASS' if a else 'FAIL'}")
    print(f"  b) daily anomaly  stations {len(j)} | median r {j.r_daily_anomaly.median():.3f} (rule >= 0.70) | "
          f"min r {j.r_daily_anomaly.min():.3f} (rule >= 0.50, {j.loc[j.r_daily_anomaly.idxmin(), 'name']})  {'PASS' if b else 'FAIL'}")
    return a and b


def test_harvest():
    ndvi = pd.read_csv(ROOT / "clean" / "ndvi_monthly.csv", sep=";")
    ndvi = ndvi[ndvi.month_start.str[5:7] == "03"].dropna(subset=["ndvi_crop"])
    march = ndvi.groupby(ndvi.month_start.str[:4].astype(int)).ndvi_crop.mean().rename("ndvi_march")
    fao = pd.read_csv(ROOT / "clean" / "fao_crops.csv", sep=";")
    wheat = fao[fao.item_code == 15].set_index("year")["yield_kg_ha"].rename("wheat_yield")
    d = pd.concat([march, wheat], axis=1, join="inner").loc[2001:2024]
    r = float(np.corrcoef(d.ndvi_march, d.wheat_yield)[0, 1])
    worst = d.nsmallest(5, "wheat_yield")
    below = int((worst.ndvi_march < d.ndvi_march.median()).sum())
    print("\nTEST 2 - March farmland greenness (MODIS NDVI) vs official wheat yield (FAOSTAT), 2001-2024")
    print(f"  years {len(d)} | correlation r = {r:.3f} (rule >= 0.70)")
    print("  5 worst harvests: " + ", ".join(f"{y} ({v:.0f} kg/ha, NDVI {n:.3f})" for y, v, n in
                                             zip(worst.index, worst.wheat_yield, worst.ndvi_march)))
    print(f"  NDVI below its median in {below} / 5 of them (rule >= 4), median NDVI {d.ndvi_march.median():.3f}")
    ok = r >= 0.70 and below >= 4
    print(f"  {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    t1 = test_temperature()
    t2 = test_harvest()
    print(f"\n{int(t1) + int(t2)} / 2 REAL-WORLD TESTS PASSED")
    sys.exit(0 if t1 and t2 else 1)
