"""
Step 6 - FAOSTAT crop production for Morocco, 2000-2024.

What it does:
  1. Downloads the FAOSTAT "Production: Crops and livestock products" file for Africa
     into raw/faostat/ (skipped if already there, ~4 MB zip).
  2. Keeps Morocco (Area Code 143), years 2000-2024, and the 3 crop elements:
     Area harvested (ha), Yield (kg/ha), Production (t).
  3. Reshapes "one column per year" into rows (the "unpivot"):
       year ; item_code ; item_name ; area_ha ; yield_kg_ha ; production_t
     and writes clean/fao_crops.csv for SSIS to load into Staging_DB.stg.FaoCrops.

Checks: Wheat 2024 production = 2,441,670 t and 2021 = 7,543,848 t (rounded),
        every year 2000-2024 present, no duplicate (year, item).
Usage:  python 04_faostat.py <ProjectRoot>
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Africa.zip"
CSV_IN_ZIP = "Production_Crops_Livestock_E_Africa_NOFLAG.csv"
MOROCCO = 143
YEARS = range(2000, 2025)
ELEMENTS = {5312: "area_ha", 5412: "yield_kg_ha", 5510: "production_t"}


def main(root: Path) -> int:
    zip_path = root / "raw" / "faostat" / "Production_Crops_Livestock_E_Africa.zip"
    out_csv = root / "clean" / "fao_crops.csv"

    if zip_path.exists():
        print(f"Already downloaded: {zip_path}")
    else:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {URL}")
        urllib.request.urlretrieve(URL, zip_path)

    with zipfile.ZipFile(zip_path) as z:
        df = pd.read_csv(io.BytesIO(z.read(CSV_IN_ZIP)), encoding="utf-8")

    df = df[(df["Area Code"] == MOROCCO) & (df["Element Code"].isin(ELEMENTS))]
    year_cols = [f"Y{y}" for y in YEARS]

    # Unpivot: one column per year -> one row per (item, element, year)
    long = df.melt(id_vars=["Item Code", "Item", "Element Code"], value_vars=year_cols,
                   var_name="year", value_name="value")
    long["year"] = long["year"].str[1:].astype(int)
    long["element"] = long["Element Code"].map(ELEMENTS)

    # Back to one row per (year, item) with the 3 elements as columns
    wide = (long.pivot_table(index=["year", "Item Code", "Item"], columns="element",
                             values="value", aggfunc="first")
                .reset_index()
                .rename(columns={"Item Code": "item_code", "Item": "item_name"}))
    for col in ELEMENTS.values():
        if col not in wide:
            wide[col] = pd.NA
    # keep only crops (items that have a harvested area at least once)
    crops = wide.groupby("item_code")["area_ha"].transform(lambda s: s.notna().any())
    wide = wide[crops & wide[["area_ha", "production_t"]].notna().any(axis=1)]
    wide = wide[["year", "item_code", "item_name", "area_ha", "yield_kg_ha", "production_t"]]
    wide = wide.sort_values(["year", "item_code"])

    # Checks
    errors = []
    def wheat(y):
        v = wide.loc[(wide.item_name == "Wheat") & (wide.year == y), "production_t"]
        return round(float(v.iloc[0])) if len(v) else None
    if wheat(2024) != 2_441_670:
        errors.append(f"wheat 2024 = {wheat(2024)}, expected 2,441,670")
    if wheat(2021) != 7_543_848:
        errors.append(f"wheat 2021 = {wheat(2021)}, expected 7,543,848")
    missing = set(YEARS) - set(wide.year)
    if missing:
        errors.append(f"missing years: {sorted(missing)}")
    if wide.duplicated(["year", "item_code"]).any():
        errors.append("duplicate (year, item) rows")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(out_csv, sep=";", index=False, encoding="utf-8", lineterminator="\n",
                float_format="%.2f")
    print(f"Crops: {wide.item_code.nunique()} | years: {wide.year.min()}-{wide.year.max()} "
          f"| rows: {len(wide)} | wheat 2024: {wheat(2024):,} t")
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
