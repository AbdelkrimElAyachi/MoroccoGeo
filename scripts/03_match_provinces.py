"""
Step 4 - Match HCP province names with geoBoundaries province names.

The two sources spell names differently, e.g.
  HCP: "Province d'El Kelâa Des-Sraghna"  geoBoundaries: "Province d'El Kelâat Es-Sraghna إقليم قلعة السراغنة"
  HCP: "Préfecture de Tanger-Assilah"     geoBoundaries: "Prefecture of Tangier - Assilah"

Method (same idea as SSIS Fuzzy Lookup):
  1. Normalise both names: remove "Province de / Préfecture of ...", Arabic and Tifinagh text,
     accents, punctuation and spaces.
  2. Compare every pair with a similarity score (0..1) and keep the best one-to-one matches.
  3. Write clean/province_match_candidates.csv for a human to review.
     Matches below REVIEW_THRESHOLD are flagged "REVIEW".

The reviewed result is stored permanently in sql/05_map_province.sql.
Usage:  python 03_match_provinces.py <ProjectRoot>
"""
import csv
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

REVIEW_THRESHOLD = 0.85
PREFIX_RE = re.compile(
    r"^(province|prefecture|préfecture)\s*(de\s+|d'|d’|of\s+|du\s+)?", re.I)
SUFFIX_RE = re.compile(r"\s+(province|prefecture)$", re.I)


def latin_part(name: str) -> str:
    """Latin part of a name only (drops Arabic / Tifinagh), e.g. for display."""
    return re.sub(r"\s+", " ", "".join(ch for ch in name if ord(ch) < 0x0590)).strip()


def normalise(name: str) -> str:
    # keep only Latin text (drop Arabic / Tifinagh parts)
    latin = "".join(ch for ch in name if ord(ch) < 0x0590)
    s = latin.strip()
    s = PREFIX_RE.sub("", s)
    s = SUFFIX_RE.sub("", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def read(path, key, name_col):
    with open(path, encoding="utf-8") as f:
        return [(r[key], r[name_col]) for r in csv.DictReader(f, delimiter=";")]


def main(root: Path) -> int:
    hcp = read(root / "clean" / "hcp_population_2024.csv", "hcp_code", "province_name")
    geo = read(root / "clean" / "boundaries_provinces.csv", "shape_id", "shape_name")

    pairs = []
    for hc, hn in hcp:
        for gid, gn in geo:
            pairs.append((SequenceMatcher(None, normalise(hn), normalise(gn)).ratio(),
                          hc, hn, gid, gn))
    pairs.sort(reverse=True)

    used_h, used_g, matches = set(), set(), []
    for score, hc, hn, gid, gn in pairs:          # greedy best one-to-one
        if hc in used_h or gid in used_g:
            continue
        used_h.add(hc)
        used_g.add(gid)
        matches.append((hc, hn, gid, gn, score))

    out = root / "clean" / "province_match_candidates.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        # The original multilingual name goes LAST: Arabic is displayed right-to-left and
        # editors would otherwise visually swap it with the neighbouring columns.
        w.writerow(["hcp_code", "hcp_name", "shape_id", "geo_name_latin", "score", "flag",
                    "geo_name_original"])
        for hc, hn, gid, gn, s in sorted(matches, key=lambda m: (m[4], int(m[0]))):
            w.writerow([hc, hn, gid, latin_part(gn), f"{s:.3f}",
                        "REVIEW" if s < REVIEW_THRESHOLD else "OK", gn])

    review = sum(1 for m in matches if m[4] < REVIEW_THRESHOLD)
    print(f"Matched {len(matches)} of {len(hcp)} HCP provinces "
          f"({len(geo)} geoBoundaries provinces); {review} to review")
    print(f"Written: {out}")
    return 0 if len(matches) == len(hcp) == len(geo) else 1


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    sys.exit(main(root))
