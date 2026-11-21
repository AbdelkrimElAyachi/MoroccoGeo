"""
Checks that the web dashboard data (web/data/*.json) shows the same numbers as the warehouse.
Same idea as ssas/tests/reconcile_model.ps1, for the public website.

Usage:  python scripts/tools/check_web_export.py
Expected last line: ALL WEB EXPORT CHECKS PASSED
"""
import json
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web" / "data"
CONN = ("Driver={ODBC Driver 18 for SQL Server};Server=localhost;Database=DWH_DB;"
        "Trusted_Connection=yes;TrustServerCertificate=yes")


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def main():
    cur = pyodbc.connect(CONN).cursor()
    one = lambda sql: cur.execute(sql).fetchone()[0]
    prov, spi, rain, nat, dams = load("provinces"), load("spi12"), load("rain"), load("national"), load("dams")
    pi = {p["name"]: i for i, p in enumerate(prov)}
    natd = {n["year"]: n for n in nat}

    aug22 = spi["values"][spi["months"].index("2022-08")]
    settat_i = pi["Settat"]
    checks = [
        ("Provinces", 75, len(prov)),
        ("Population 2024", one("SELECT SUM(Pop2024) FROM dbo.DimGeography WHERE GeoLevel='Province'"), sum(p["pop"] for p in prov)),
        ("SPI-12 values", one("SELECT COUNT(*) FROM dbo.FactDroughtIndex WHERE SpiScale=12"),
         sum(v is not None for row in spi["values"] for v in row)),
        ("Provinces in drought, Aug 2022", one("SELECT COUNT(*) FROM dbo.FactDroughtIndex WHERE SpiScale=12 AND DateKey=20220801 AND SpiValue<=-1"),
         sum(v is not None and v <= -1 for v in aug22)),
        ("People in drought, Aug 2022", one("""SELECT SUM(g.Pop2024) FROM dbo.FactDroughtIndex f JOIN dbo.DimGeography g ON g.GeographyKey=f.GeographyKey
                                              WHERE f.SpiScale=12 AND f.DateKey=20220801 AND f.SpiValue<=-1"""),
         sum(prov[i]["pop"] for i, v in enumerate(aug22) if v is not None and v <= -1)),
        ("Settat rain 2024 (mm)", round(float(one("""SELECT SUM(f.RainMm) FROM dbo.FactRainfallMonthly f JOIN dbo.DimGeography g ON g.GeographyKey=f.GeographyKey
                                                    WHERE g.ProvinceShort=N'Settat' AND f.DateKey BETWEEN 20240101 AND 20241201""")), 1),
         round(sum(rain["values"][rain["months"].index(f"2024-{m:02d}")][settat_i] for m in range(1, 13)), 1)),
        ("Wheat 2024 (t)", round(float(one("""SELECT ProductionT FROM dbo.FactCropProduction f JOIN dbo.DimCrop c ON c.CropKey=f.CropKey
                                             WHERE c.FaoItemCode=15 AND f.[Year]=2024"""))), natd[2024]["wheat_t"]),
        ("Dam months x dams", one("SELECT COUNT(*) FROM dbo.FactReservoirMonthly"), len(dams["months"]) * len(dams["dams"])),
        ("National avg Tmax 2023", round(float(one("SELECT AVG(TmaxC) FROM dbo.FactWeatherDaily WHERE DateKey BETWEEN 20230101 AND 20231231")), 2),
         natd[2023]["tmax_avg"]),
    ]
    fail = 0
    for name, sql_v, web_v in checks:
        ok = abs(float(sql_v) - float(web_v)) < 0.051
        fail += not ok
        print(f"{name:38s} sql={sql_v!s:>14}  web={web_v!s:>14}  {'PASS' if ok else 'FAIL'}")
    print("ALL WEB EXPORT CHECKS PASSED" if not fail else f"{fail} CHECK(S) FAILED")
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
