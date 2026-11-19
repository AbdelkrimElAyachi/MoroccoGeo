"""
Step 9 - Standardized Precipitation Index (SPI) per province, scales 1, 3, 6 and 12 months.

Input : clean/chirps_monthly.csv  (month_start ; shape_id ; rain_mm), from Step 8
Output: clean/spi_monthly.csv     (month_start ; shape_id ; spi_scale ; spi)

Method (McKee et al. 1993; WMO "Standardized Precipitation Index User Guide", 2012):
  1. For scale k, sum rainfall over the last k months (e.g. SPI-3 for March = Jan+Feb+Mar).
  2. For each province, scale and calendar month, fit a gamma distribution to the sums of the
     calibration period 1991-2020 (30 years, as recommended).
     Months with zero rain are handled with q = share of zeros: H(x) = q + (1 - q) * G(x).
  3. SPI = the value of a standard normal distribution with the same probability H(x).
     0 = normal, -1 = moderately dry, -1.5 = severely dry, -2 = extremely dry.
  When fewer than 10 of the 30 calibration values are non-zero (desert provinces in summer),
  the SPI is not meaningful and is left out.

Checks: over 1991-2020, SPI-12 has mean ~0 and standard deviation ~1 in every province.
Usage:  python 06_spi.py <ProjectRoot>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SCALES = (1, 3, 6, 12)
CAL_START, CAL_END = 1991, 2020
MIN_NONZERO = 10
P_CLIP = 1e-6          # keeps SPI within about +/- 4.75


def spi_series(rain: pd.Series, k: int) -> pd.Series:
    acc = rain.rolling(k, min_periods=k).sum()
    out = pd.Series(np.nan, index=acc.index)
    for month in range(1, 13):
        sel = acc.index.month == month
        x = acc[sel]
        cal = x[(x.index.year >= CAL_START) & (x.index.year <= CAL_END)].dropna()
        nonzero = cal[cal > 0]
        if len(cal) < 25 or len(nonzero) < MIN_NONZERO:
            continue
        q = 1 - len(nonzero) / len(cal)
        a, loc, scale = stats.gamma.fit(nonzero, floc=0)
        h = q + (1 - q) * stats.gamma.cdf(x.clip(lower=0), a, loc=0, scale=scale)
        h = np.where(x <= 0, q, h)
        out[sel] = stats.norm.ppf(np.clip(h, P_CLIP, 1 - P_CLIP))
    out[acc.isna()] = np.nan
    return out


def main(root: Path) -> int:
    src = root / "clean" / "chirps_monthly.csv"
    out_csv = root / "clean" / "spi_monthly.csv"
    df = pd.read_csv(src, sep=";", parse_dates=["month_start"])

    results, errors, check_rows = [], [], []
    for sid, g in df.groupby("shape_id"):
        rain = g.set_index("month_start")["rain_mm"].sort_index()
        for k in SCALES:
            s = spi_series(rain, k).dropna()
            results.append(pd.DataFrame({"month_start": s.index.date, "shape_id": sid,
                                         "spi_scale": k, "spi": s.round(3).values}))
            if k == 12:
                cal = s[(s.index.year >= CAL_START) & (s.index.year <= CAL_END)]
                check_rows.append((sid, cal.mean(), cal.std()))

    out = pd.concat(results).sort_values(["month_start", "shape_id", "spi_scale"])
    out.to_csv(out_csv, sep=";", index=False, encoding="utf-8", lineterminator="\n")

    chk = pd.DataFrame(check_rows, columns=["shape_id", "mean", "std"])
    bad = chk[(chk["mean"].abs() > 0.15) | ((chk["std"] - 1).abs() > 0.2)]
    if len(bad):
        errors.append(f"{len(bad)} provinces with SPI-12 mean/std far from 0/1 over 1991-2020")
    print(f"Rows: {len(out):,} | provinces: {out.shape_id.nunique()} | "
          f"SPI-12 over 1991-2020: mean of means {chk['mean'].mean():+.3f}, mean std {chk['std'].mean():.3f}")
    for k in SCALES:
        n = (out.spi_scale == k).sum()
        print(f"  SPI-{k:<2}: {n:,} values")
    print(f"Written: {out_csv}")
    if errors:
        for e in errors:
            print(f"CHECK FAILED: {e}")
        print(bad.to_string(index=False))
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    sys.exit(main(root))
