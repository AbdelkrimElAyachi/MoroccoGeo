"""
Step 7 - Open-Meteo daily weather per province, 1991-01-01 -> 7 days ago.

Variables: max and min temperature (°C), precipitation (mm), FAO reference
evapotranspiration ET0 (mm), at a point inside each province (DimGeography.PointLat/Lon,
from clean/boundaries_provinces.csv).

Free API limits (Open-Meteo, non-commercial): 600 per minute, 5,000 per hour,
10,000 per day. One province x 36 years costs ~375, so 75 provinces need ~28,000:
about 3 days. The script is RESUMABLE:
  - each province is saved to raw/openmeteo/<shape_id>.csv as soon as it is downloaded;
  - provinces already on disk are skipped;
  - it waits when the per-minute or per-hour budget is used up, and stops cleanly when
    the daily budget is used up (exit code 2: run it again the next day).
When all 75 provinces are on disk, it writes clean/weather_daily.csv for SSIS:
    day ; shape_id ; tmax_c ; tmin_c ; precip_mm ; et0_mm

Checks: 75 provinces, every day present, Tmax between -15 and 55 °C, Tmin <= Tmax + 0.5.
Usage:  python 07_openmeteo.py <ProjectRoot> [--max-hours N] [--until-done]
  --until-done: never give up at the daily limit; wait for the next quota day (00:05 UTC) and
                continue until all provinces are on disk. Survives laptop sleep (paused, then resumes).
"""
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://archive-api.open-meteo.com/v1/archive"
START = date(1991, 1, 1)
VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
HEADERS = {"User-Agent": "school-drought-observatory/1.0"}


class DailyLimit(Exception):
    pass


def wait_for_next_quota_day():
    """Wait until 00:05 UTC (new Open-Meteo day). Checks the real clock every 5 minutes, so a
    laptop sleep in the middle does not break the wait: after waking it simply continues."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    target = (now.replace(hour=0, minute=5, second=0, microsecond=0)
              + (timedelta(days=1) if now.hour > 0 or now.minute >= 5 else timedelta(0)))
    print(f"  waiting for the next quota day ({target:%Y-%m-%d %H:%M} UTC)...", flush=True)
    while datetime.now(timezone.utc) < target:
        time.sleep(300)


MAX_NETWORK_RETRIES = 6      # set to None by --until-done: never give up because of the network


def fetch(lat, lon, end: date) -> tuple[str, dict]:
    url = (f"{API}?latitude={lat}&longitude={lon}&start_date={START}&end_date={end}"
           f"&daily={VARS}&timezone=Africa%2FCasablanca&format=csv")
    network_errors = 0
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=180) as r:
                return r.read().decode("utf-8"), dict(r.headers)
        except urllib.error.HTTPError as e:          # the server answered with an error code
            body = e.read().decode("utf-8", "ignore")
            if e.code != 429:
                raise
            reason = json.loads(body).get("reason", body) if body.startswith("{") else body
            if "Daily" in reason:
                raise DailyLimit(reason)
            wait = 3600 - int(time.time()) % 3600 + 5 if "Hourly" in reason else 65
            print(f"  limit reached ({reason.strip()}), waiting {wait}s")
            time.sleep(wait)
        except (TimeoutError, ConnectionError, urllib.error.URLError) as e:
            # slow or dropped connection / internet down: wait and retry (1, 2, 4, 8, 16, 30, 30 ... min)
            network_errors += 1
            if MAX_NETWORK_RETRIES is not None and network_errors > MAX_NETWORK_RETRIES:
                raise
            wait = min(60 * 2 ** (network_errors - 1), 1800)
            print(f"  network problem ({e}); retry {network_errors} in {wait // 60} min", flush=True)
            time.sleep(wait)


def parse(text: str, shape_id: str):
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("time,"))
    for row in csv.reader(io.StringIO("\n".join(lines[start + 1:]))):
        if row:
            yield [row[0], shape_id] + [v if v != "" else "" for v in row[1:5]]


def main(root: Path, max_hours: float, until_done: bool = False) -> int:
    raw_dir = root / "raw" / "openmeteo"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_csv = root / "clean" / "weather_daily.csv"
    end = date.today() - timedelta(days=7)

    with open(root / "clean" / "boundaries_provinces.csv", encoding="utf-8") as f:
        provinces = list(csv.DictReader(f, delimiter=";"))

    deadline = time.time() + max_hours * 3600
    while True:
        todo = [p for p in provinces if not (raw_dir / f"{p['shape_id']}.csv").exists()]
        print(f"Provinces on disk: {len(provinces) - len(todo)}/{len(provinces)}; to download: {len(todo)}",
              flush=True)
        try:
            for p in todo:
                if not until_done and time.time() > deadline:
                    print("Time budget for this run used up.")
                    break
                text, headers = fetch(p["point_lat"], p["point_lon"], end)
                rows = list(parse(text, p["shape_id"]))
                tmp = raw_dir / f"{p['shape_id']}.part"
                with open(tmp, "w", encoding="utf-8", newline="") as f:
                    csv.writer(f, delimiter=";", lineterminator="\n").writerows(rows)
                tmp.replace(raw_dir / f"{p['shape_id']}.csv")
                cost = float(headers.get("X-RateLimit-Cost", 0) or 0)
                left = float(headers.get("X-RateLimit-Remaining", 600) or 600)
                print(f"  {p['shape_name'][:40]:40s} {len(rows):6d} days (cost {cost:.0f})", flush=True)
                if left < cost:                # next call would exceed the per-minute budget
                    time.sleep(62)
            break
        except DailyLimit as e:
            print(f"Daily limit reached: {e}", flush=True)
            if not until_done:
                break
            wait_for_next_quota_day()         # --until-done: continue tomorrow by itself

    done = [p for p in provinces if (raw_dir / f"{p['shape_id']}.csv").exists()]
    if len(done) < len(provinces):
        print(f"INCOMPLETE: {len(done)}/{len(provinces)} provinces downloaded. Run again later to continue.")
        return 2

    # All provinces on disk: combine, check, write the clean file.
    # Provinces downloaded on different days end on different days ("7 days ago" moves): cut every
    # province to the last day they ALL have, so every day has all 75 provinces.
    last_days = {}
    for p in provinces:
        with open(raw_dir / f"{p['shape_id']}.csv", encoding="utf-8") as f:
            last_days[p["shape_id"]] = max(r[0] for r in csv.reader(f, delimiter=";") if r)
    common_end = min(last_days.values())
    if len(set(last_days.values())) > 1:
        print(f"Provinces end between {common_end} and {max(last_days.values())}: "
              f"all cut to the common last day {common_end}")

    errors, n_rows = [], 0
    expected_days = None
    with open(out_csv, "w", encoding="utf-8", newline="") as out:
        w = csv.writer(out, delimiter=";", lineterminator="\n")
        w.writerow(["day", "shape_id", "tmax_c", "tmin_c", "precip_mm", "et0_mm"])
        for p in provinces:
            with open(raw_dir / f"{p['shape_id']}.csv", encoding="utf-8") as f:
                rows = [r for r in csv.reader(f, delimiter=";") if r and r[0] <= common_end]
            expected_days = expected_days or len(rows)
            if len(rows) != expected_days:
                errors.append(f"{p['shape_name']}: {len(rows)} days instead of {expected_days}")
            for r in rows:
                if r[2] and not -15 <= float(r[2]) <= 55:
                    errors.append(f"{p['shape_name']} {r[0]}: Tmax {r[2]}")
                if r[2] and r[3] and float(r[3]) > float(r[2]) + 0.5:
                    errors.append(f"{p['shape_name']} {r[0]}: Tmin > Tmax")
            w.writerows(rows)
            n_rows += len(rows)
    print(f"Rows: {n_rows:,} | provinces: {len(provinces)} | days per province: {expected_days}")
    print(f"Written: {out_csv}")
    if errors:
        for e in errors[:20]:
            print(f"CHECK FAILED: {e}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    hours = 6.0
    until_done = "--until-done" in args      # keep going across days (waits for the next quota day)
    if until_done:
        args.remove("--until-done")
        MAX_NETWORK_RETRIES = None
    if "--max-hours" in args:
        i = args.index("--max-hours")
        hours = float(args[i + 1])
        del args[i:i + 2]
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    sys.exit(main(root, hours, until_done))
