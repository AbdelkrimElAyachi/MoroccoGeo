"""
Exports the warehouse (DWH_DB) into small static files for the public web dashboard (web/).

Writes into web/data/:
  provinces.json      75 provinces: short name, region, 2024 population
  morocco.topojson    province outlines (copy of powerbi/morocco_provinces.topojson)
  spi12.json          SPI-12 per province and month (1991-12 -> latest), compact matrix
  rain.json           monthly rain per province + 1991-2020 monthly normals per province
  national.json       yearly national series: rain % of normal, provinces / people in drought
                      (end of year), avg max temperature, hot days, wheat, March farmland NDVI
  dams.json           26 dams: name, max surface, monthly water surface (2000 -> latest) + reliability
  meta.json           last update, periods, row counts
  csv/*.csv           downloadable tables (open data, same numbers)

Every number comes from the same warehouse tables as the SSAS model and Power BI.
Usage:  python 11_export_web.py <ProjectRoot>
"""
import csv
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pyodbc

CONN = ("Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=DWH_DB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes")


def q(cur, sql):
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def r(x, n=2):
    return None if x is None else round(float(x), n)


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:      # BOM: opens cleanly in Excel
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(root: Path) -> int:
    out = root / "web" / "data"
    (out / "csv").mkdir(parents=True, exist_ok=True)
    cur = pyodbc.connect(CONN).cursor()

    # ---------- provinces ----------
    prov = q(cur, """SELECT GeographyKey k, ProvinceShort name, RegionName region, Pop2024 pop
                     FROM dbo.DimGeography WHERE GeoLevel = 'Province' ORDER BY ProvinceShort""")
    keys = [p["k"] for p in prov]
    idx = {k: i for i, k in enumerate(keys)}
    write_json(out / "provinces.json", [{"name": p["name"], "region": p["region"], "pop": p["pop"]} for p in prov])
    shutil.copyfile(root / "powerbi" / "morocco_provinces.topojson", out / "morocco.topojson")

    # ---------- SPI-12 matrix: months x provinces ----------
    spi = q(cur, """SELECT f.DateKey, f.GeographyKey k, f.SpiValue v FROM dbo.FactDroughtIndex f
                    WHERE f.SpiScale = 12 ORDER BY f.DateKey""")
    months = sorted({s["DateKey"] for s in spi})
    m_idx = {m: i for i, m in enumerate(months)}
    mat = [[None] * len(keys) for _ in months]
    for s in spi:
        mat[m_idx[s["DateKey"]]][idx[s["k"]]] = r(s["v"])
    month_labels = [f"{m // 10000}-{m // 100 % 100:02d}" for m in months]
    write_json(out / "spi12.json", {"months": month_labels, "values": mat})

    # ---------- rain per province and month + normals ----------
    rain = q(cur, """SELECT f.DateKey, f.GeographyKey k, f.RainMm v, d.[Month] mo, f.NormalMm n
                     FROM dbo.FactRainfallMonthly f JOIN dbo.DimDate d ON d.DateKey = f.DateKey
                     ORDER BY f.DateKey""")
    r_months = sorted({x["DateKey"] for x in rain})
    rm_idx = {m: i for i, m in enumerate(r_months)}
    rmat = [[None] * len(keys) for _ in r_months]
    normals = [[None] * 12 for _ in keys]
    for x in rain:
        # 2 decimals like the warehouse (1 decimal made 12-month sums drift by 0.1 mm)
        rmat[rm_idx[x["DateKey"]]][idx[x["k"]]] = r(x["v"], 2)
        normals[idx[x["k"]]][x["mo"] - 1] = r(x["n"], 2)
    write_json(out / "rain.json", {"months": [f"{m // 10000}-{m // 100 % 100:02d}" for m in r_months],
                                   "values": rmat, "normals": normals})

    # ---------- national yearly series ----------
    nat_rain = {x["y"]: x for x in q(cur, """
        SELECT d.[Year] y, AVG(x.r) r, AVG(x.n) n FROM (
            SELECT f.GeographyKey, d.[Year], SUM(f.RainMm) r, SUM(f.NormalMm) n
            FROM dbo.FactRainfallMonthly f JOIN dbo.DimDate d ON d.DateKey = f.DateKey
            GROUP BY f.GeographyKey, d.[Year]) x
        JOIN (SELECT DISTINCT [Year] FROM dbo.DimDate) d ON d.[Year] = x.[Year]
        GROUP BY d.[Year]""")}
    nat_drought = {x["y"]: x for x in q(cur, """
        WITH last AS (SELECT d.[Year] y, MAX(f.DateKey) dk FROM dbo.FactDroughtIndex f
                      JOIN dbo.DimDate d ON d.DateKey = f.DateKey WHERE f.SpiScale = 12 GROUP BY d.[Year])
        SELECT l.y, AVG(f.SpiValue) spi, SUM(CASE WHEN f.SpiValue <= -1 THEN 1 ELSE 0 END) prov,
               SUM(CASE WHEN f.SpiValue <= -1 THEN g.Pop2024 ELSE 0 END) people, MAX(l.dk) dk
        FROM last l JOIN dbo.FactDroughtIndex f ON f.DateKey = l.dk AND f.SpiScale = 12
        JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey GROUP BY l.y""")}
    nat_temp = {x["y"]: x for x in q(cur, """
        SELECT d.[Year] y, AVG(w.TmaxC) tmax,
               1.0 * SUM(CASE WHEN w.TmaxC >= 35 THEN 1 ELSE 0 END) / COUNT(DISTINCT w.GeographyKey) hot,
               COUNT(DISTINCT d.[Month]) months
        FROM dbo.FactWeatherDaily w JOIN dbo.DimDate d ON d.DateKey = w.DateKey GROUP BY d.[Year]""")}
    wheat = {x["y"]: x for x in q(cur, """
        SELECT f.[Year] y, f.ProductionT p, f.YieldKgHa yl FROM dbo.FactCropProduction f
        JOIN dbo.DimCrop c ON c.CropKey = f.CropKey WHERE c.FaoItemCode = 15""")}
    ndvi = {x["y"]: x for x in q(cur, """
        SELECT d.[Year] y, AVG(v.NdviCrop) ndvi FROM dbo.FactVegetationMonthly v
        JOIN dbo.DimDate d ON d.DateKey = v.DateKey WHERE d.[Month] = 3 AND v.NdviCrop IS NOT NULL
        GROUP BY d.[Year]""")}
    years = sorted(set(nat_rain) | set(nat_drought) | set(nat_temp))
    national = []
    for y in years:
        nr, nd, nt, wh, nv = nat_rain.get(y), nat_drought.get(y), nat_temp.get(y), wheat.get(y), ndvi.get(y)
        national.append({
            "year": y,
            "rain_pct": r(100 * nr["r"] / nr["n"], 1) if nr and nr["n"] else None,
            "spi12_end": r(nd["spi"]) if nd else None,
            "provinces_drought_end": nd["prov"] if nd else None,
            "people_drought_end": nd["people"] if nd else None,
            "end_month": f"{nd['dk'] // 10000}-{nd['dk'] // 100 % 100:02d}" if nd else None,
            "tmax_avg": r(nt["tmax"], 2) if nt and nt["months"] == 12 else None,      # full years only
            "hot_days": r(nt["hot"], 1) if nt and nt["months"] == 12 else None,
            "wheat_t": r(wh["p"], 0) if wh else None,
            "wheat_yield": r(wh["yl"], 0) if wh else None,
            "ndvi_march": r(nv["ndvi"], 3) if nv else None,
        })
    write_json(out / "national.json", national)

    # ---------- dams ----------
    dams = q(cur, "SELECT DamKey k, DamName name, MaxWaterKm2 mx, OsmAreaKm2 osm FROM dbo.DimDam ORDER BY OsmAreaKm2 DESC")
    dk = {d["k"]: i for i, d in enumerate(dams)}
    water = q(cur, "SELECT DateKey, DamKey k, WaterKm2 w, IsReliable ok, Source src FROM dbo.FactReservoirMonthly ORDER BY DateKey")
    w_months = sorted({x["DateKey"] for x in water})
    wm_idx = {m: i for i, m in enumerate(w_months)}
    wmat = [[None] * len(dams) for _ in w_months]
    src = [None] * len(w_months)
    for x in water:
        if x["ok"]:                                        # only reliable months (>= 80 % visible)
            wmat[wm_idx[x["DateKey"]]][dk[x["k"]]] = r(x["w"], 2)
        src[wm_idx[x["DateKey"]]] = x["src"]
    write_json(out / "dams.json", {
        "dams": [{"name": d["name"], "max": r(d["mx"], 2)} for d in dams],
        "months": [f"{m // 10000}-{m // 100 % 100:02d}" for m in w_months],
        "source": src, "values": wmat})

    # ---------- meta ----------
    write_json(out / "meta.json", {
        "updated": date.today().isoformat(),
        "spi_months": [month_labels[0], month_labels[-1]],
        "rain_months": [f"{r_months[0] // 10000}-{r_months[0] // 100 % 100:02d}",
                        f"{r_months[-1] // 10000}-{r_months[-1] // 100 % 100:02d}"],
        "dam_months": [f"{w_months[0] // 10000}-{w_months[0] // 100 % 100:02d}",
                       f"{w_months[-1] // 10000}-{w_months[-1] // 100 % 100:02d}"],
        "provinces": len(keys), "dams": len(dams)})

    # ---------- CSV downloads ----------
    names = {p["k"]: (p["name"], p["region"]) for p in prov}
    write_csv(out / "csv" / "spi12_province_month.csv",
              [{"month": f"{s['DateKey'] // 10000}-{s['DateKey'] // 100 % 100:02d}", "province": names[s["k"]][0],
                "region": names[s["k"]][1], "spi12": r(s["v"], 3)} for s in spi])
    write_csv(out / "csv" / "rain_province_month.csv",
              [{"month": f"{x['DateKey'] // 10000}-{x['DateKey'] // 100 % 100:02d}", "province": names[x["k"]][0],
                "region": names[x["k"]][1], "rain_mm": r(x["v"], 2), "normal_1991_2020_mm": r(x["n"], 2)} for x in rain])
    write_csv(out / "csv" / "national_yearly.csv", national)
    write_csv(out / "csv" / "dams_month.csv",
              [{"month": f"{x['DateKey'] // 10000}-{x['DateKey'] // 100 % 100:02d}", "dam": dams[dk[x["k"]]]["name"],
                "water_km2": r(x["w"], 3), "reliable": bool(x["ok"]), "source": x["src"]} for x in water])
    write_csv(out / "csv" / "provinces.csv", [{"province": p["name"], "region": p["region"], "population_2024": p["pop"]} for p in prov])

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"Provinces {len(keys)} | SPI months {len(months)} | rain months {len(r_months)} | "
          f"dam months {len(w_months)} | years {len(years)} | total {size:.1f} MB")
    print(f"Written: {out}")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    sys.exit(main(root))
