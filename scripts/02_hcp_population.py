"""
Step 4 - HCP census 2024: legal population by province / prefecture.

Input : raw/hcp/hcp_population_legale_2024.xlsx  (downloaded from hcp.ma, file 242341)
Output: clean/hcp_population_2024.csv  (for SSIS to load into Staging_DB.stg.HcpPopulation)
   hcp_code ; region_code ; region_name ; province_name ; pop_2024 ; pop_urban_2024 ; pop_rural_2024

How the HCP sheet is organised:
  - one block "Ensemble" (total), then a "(milieu urbain)" block, then a "(milieu rural)" block
  - each block lists the national total, the 12 regions, then provinces/prefectures and communes
  - column D = population, column G = geographic code
    (province code = 4-5 digits; region code = province code // 1000)

Checks: 75 provinces, 12 regions, total = 36,828,330, urban + rural = total for each province.
Usage:  python 02_hcp_population.py <ProjectRoot>
"""
import csv
import re
import sys
import warnings
from pathlib import Path

import openpyxl

EXPECTED_PROVINCES = 75
EXPECTED_REGIONS = 12
EXPECTED_TOTAL = 36_828_330
PROVINCE_RE = re.compile(r"^(Province|Préfecture)\b", re.I)


def block_of(name: str) -> str:
    if name.endswith("(milieu urbain)"):
        return "urban"
    if name.endswith("(milieu rural)"):
        return "rural"
    return "total"


def clean_name(name: str) -> str:
    return re.sub(r"\s*\(milieu (urbain|rural)\)\s*$", "", name).strip()


def main(root: Path) -> int:
    src = root / "raw" / "hcp" / "hcp_population_legale_2024.xlsx"
    out_csv = root / "clean" / "hcp_population_2024.csv"
    warnings.simplefilter("ignore")
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True).worksheets[0]

    regions, provinces = {}, {}
    for row in ws.iter_rows(values_only=True):
        name, pop, code = row[0], row[3], row[6]
        if not isinstance(name, str) or not isinstance(pop, (int, float)) or code is None:
            continue
        name = name.strip()
        block = block_of(name)
        base = clean_name(name)
        if base.startswith("Région") and block == "total":
            regions[int(code)] = base
        elif PROVINCE_RE.match(base) and int(code) < 100_000:
            # province codes have 4-5 digits; longer codes are sub-levels
            # (e.g. Casablanca's "préfectures d'arrondissements", 8 digits)
            p = provinces.setdefault(int(code), {"name": base})
            p[block] = int(pop)

    errors = []
    if len(regions) != EXPECTED_REGIONS:
        errors.append(f"expected {EXPECTED_REGIONS} regions, found {len(regions)}")
    if len(provinces) != EXPECTED_PROVINCES:
        errors.append(f"expected {EXPECTED_PROVINCES} provinces, found {len(provinces)}")
    total = sum(p.get("total", 0) for p in provinces.values())
    if total != EXPECTED_TOTAL:
        errors.append(f"total population {total:,} != {EXPECTED_TOTAL:,}")
    for code, p in provinces.items():
        if p.get("urban", 0) + p.get("rural", 0) != p.get("total"):
            errors.append(f"urban + rural != total for {p['name']} ({code})")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["hcp_code", "region_code", "region_name", "province_name",
                    "pop_2024", "pop_urban_2024", "pop_rural_2024"])
        for code in sorted(provinces):
            p = provinces[code]
            rc = code // 1000
            w.writerow([code, rc, regions.get(rc, ""), p["name"],
                        p.get("total"), p.get("urban", 0), p.get("rural", 0)])

    print(f"Regions: {len(regions)} | Provinces: {len(provinces)} | Total population: {total:,}")
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
