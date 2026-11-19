"""
Step 11 (part 1) - List of Morocco's main reservoirs, from OpenStreetMap.

The dam databases (GRanD, GDW) are not available in our Earth Engine catalog, so reservoir
outlines and names come from OpenStreetMap (open data, ODbL), via the public Overpass API:
water=reservoir areas, plus water areas named "Barrage ..." / "سد ...".

What it does:
  1. Downloads the reservoirs once (cached in raw/dams/osm_reservoirs.json).
  2. Builds polygons, merges pieces with the same name, computes the area.
  3. Keeps the reservoirs >= MIN_KM2 that have a name and lie in Morocco.
  4. Writes raw/dams/reservoirs.geojson (outlines for Earth Engine) and
     clean/reservoirs.csv (for SSIS -> DimDam):
       dam_id ; dam_name ; osm_area_km2 ; lat ; lon ; shape_id (province)

Usage:  python 09_reservoirs.py <ProjectRoot>
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

OVERPASS = ["https://overpass-api.de/api/interpreter",          # main server (often busy)
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
QUERY = """[out:json][timeout:180];
area["ISO3166-1"="MA"][admin_level=2]->.a;
(way["water"="reservoir"](area.a); relation["water"="reservoir"](area.a);
 way["natural"="water"]["name"~"Barrage|barrage|سد"](area.a);
 relation["natural"="water"]["name"~"Barrage|barrage|سد"](area.a););
out geom;"""
# note: "out geom tags" would drop the members of multipolygon relations, i.e. exactly the
# outlines of the largest reservoirs (Al Wahda, Al Massira, ...). "out geom" keeps them.
MIN_KM2 = 4.0
HEADERS = {"User-Agent": "school-drought-observatory/1.0 (non-commercial student project)"}


def fetch(cache: Path) -> dict:
    if cache.exists():
        print(f"Already downloaded: {cache}")
    else:
        data = urllib.parse.urlencode({"data": QUERY}).encode()
        for url in OVERPASS:          # public servers are often overloaded: try the next one
            try:
                req = urllib.request.Request(url, data=data, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=300) as r:
                    cache.write_bytes(r.read())
                break
            except Exception as e:
                print(f"  {url}: {e}")
        else:
            raise RuntimeError("all Overpass servers failed; try again later")
        print(f"Saved: {cache} ({cache.stat().st_size:,} bytes)")
    return json.loads(cache.read_text(encoding="utf-8"))


def element_polygon(el):
    if el["type"] == "way" and "geometry" in el:
        pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
        return Polygon(pts) if len(pts) >= 4 else None
    if el["type"] == "relation":
        outers = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                  for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        polys = list(polygonize(unary_union(outers))) if outers else []
        return unary_union(polys) if polys else None
    return None


def clean_name(tags):
    name = tags.get("name:fr") or tags.get("name") or ""
    return " ".join(name.split())


def main(root: Path) -> int:
    raw = root / "raw" / "dams"
    raw.mkdir(parents=True, exist_ok=True)
    data = fetch(raw / "osm_reservoirs.json")

    recs = []
    for el in data["elements"]:
        geom = element_polygon(el)
        name = clean_name(el.get("tags", {}))
        if geom is None or geom.is_empty or not name:
            continue
        recs.append({"dam_name": name, "geometry": geom.buffer(0)})
    gdf = gpd.GeoDataFrame(recs, crs="EPSG:4326")
    gdf = gdf.dissolve(by="dam_name", as_index=False)           # merge pieces with the same name
    gdf["osm_area_km2"] = (gdf.to_crs("EPSG:6933").area / 1e6).round(2)
    gdf = gdf[gdf.osm_area_km2 >= MIN_KM2].sort_values("osm_area_km2", ascending=False)

    prov = gpd.read_file(root / "raw" / "boundaries" / "geoBoundaries-MAR-ADM2.geojson")[["shapeID", "geometry"]]
    pts = gdf.copy()
    pts["geometry"] = gdf.geometry.representative_point()
    pts = gpd.sjoin(pts, prov, how="left", predicate="within")
    gdf["shape_id"] = pts["shapeID"].values
    gdf = gdf[gdf.shape_id.notna()].reset_index(drop=True)
    gdf["dam_id"] = range(1, len(gdf) + 1)
    rp = gdf.geometry.representative_point()
    gdf["lat"], gdf["lon"] = rp.y.round(5), rp.x.round(5)

    gdf[["dam_id", "dam_name", "osm_area_km2", "shape_id", "geometry"]].to_file(
        raw / "reservoirs.geojson", driver="GeoJSON")
    out_csv = root / "clean" / "reservoirs.csv"
    gdf[["dam_id", "dam_name", "osm_area_km2", "lat", "lon", "shape_id"]].to_csv(
        out_csv, sep=";", index=False, encoding="utf-8", lineterminator="\n")
    print(f"Reservoirs >= {MIN_KM2} km2 with a name: {len(gdf)}")
    print(gdf[["dam_id", "dam_name", "osm_area_km2"]].to_string(index=False))
    print(f"Written: {out_csv}")
    return 0 if len(gdf) >= 5 else 1


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    sys.exit(main(root))
