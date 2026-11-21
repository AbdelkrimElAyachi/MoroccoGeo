r"""
Builds the project report as a PDF: docs/Rapport_Observatoire_Secheresse_Maroc.pdf
HTML (this script) -> PDF with Microsoft Edge headless (--print-to-pdf).
Figures: docs/report/img/ (real data images) + charts drawn here as SVG from the warehouse numbers.
Usage:  venv\Scripts\python.exe docs\report\build_report.py
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_HTML = HERE / "rapport.html"
OUT_PDF = HERE.parent / "Rapport_Observatoire_Secheresse_Maroc.pdf"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# ---------------------------------------------------------------- figure: provinces in drought each August
AUGUST = [(1992, 3), (1993, 48), (1994, 5), (1995, 37), (1996, 0), (1997, 0), (1998, 1), (1999, 38), (2000, 22),
          (2001, 37), (2002, 1), (2003, 4), (2004, 0), (2005, 20), (2006, 0), (2007, 1), (2008, 1), (2009, 0),
          (2010, 2), (2011, 2), (2012, 30), (2013, 2), (2014, 0), (2015, 0), (2016, 47), (2017, 1), (2018, 1),
          (2019, 9), (2020, 49), (2021, 9), (2022, 61), (2023, 45), (2024, 47), (2025, 43), (2026, 4)]


def drought_chart():
    left, right, base, y0, mx = 44, 700, 270, 30, 75
    band = (right - left) / len(AUGUST)
    bw = band * 0.7
    Y = lambda v: base - v / mx * (base - y0)
    s = [f"<svg viewBox='0 0 720 300' xmlns='http://www.w3.org/2000/svg' font-family='Segoe UI' font-size='11'>"]
    for v in (0, 25, 50, 75):
        s.append(f"<line x1='{left}' x2='{right}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='#E3E1DC'/>"
                 f"<text x='{left-6}' y='{Y(v)+4:.1f}' text-anchor='end' fill='#6B6B6B'>{v}</text>")
    s.append(f"<line x1='{left}' x2='{right}' y1='{Y(37.5):.1f}' y2='{Y(37.5):.1f}' stroke='#8A8A8A' stroke-dasharray='4 4'/>"
             f"<text x='{left + 14*band:.1f}' y='{Y(37.5)-6:.1f}' fill='#6B6B6B'>la moitié des provinces</text>")
    for i, (yr, n) in enumerate(AUGUST):
        x = left + i * band + (band - bw) / 2
        col = "#1F4E9C" if yr == 2022 else "#B9B7AE"
        s.append(f"<rect x='{x:.1f}' y='{Y(n):.1f}' width='{bw:.1f}' height='{base-Y(n):.1f}' fill='{col}'/>")
        if n >= 40 or yr == 2026:
            s.append(f"<text x='{x+bw/2:.1f}' y='{Y(n)-5:.1f}' text-anchor='middle' fill='#222' "
                     f"font-weight='{600 if yr == 2022 else 400}'>{n}</text>")
        if yr % 4 == 0 or yr == 2026:
            s.append(f"<text x='{x+bw/2:.1f}' y='{base+16}' text-anchor='middle' fill='#6B6B6B'>{yr}</text>")
    s.append(f"<line x1='{left}' x2='{right}' y1='{base}' y2='{base}' stroke='#555'/></svg>")
    return "".join(s)


# ---------------------------------------------------------------- figure: architecture
def arch_chart():
    def box(x, y, w, h, title, lines, main=False):
        fill, stroke, sw = ("#E8EFFA", "#1F4E9C", 2) if main else ("#FFFFFF", "#8A8A8A", 1.2)
        t = [f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{fill}' stroke='{stroke}' stroke-width='{sw}'/>",
             f"<text x='{x+14}' y='{y+22}' font-weight='600' fill='#1A1A1A'>{title}</text>"]
        for k, ln in enumerate(lines):
            t.append(f"<text x='{x+14}' y='{y+40+16*k}' fill='#333'>{ln}</text>")
        return "".join(t)

    cw = (672 - 32) / 3
    c1, c2, c3 = 24, 24 + cw + 16, 24 + 2 * (cw + 16)
    a = "marker-end='url(#ar)' stroke='#8A8A8A' stroke-width='1.2' fill='none'"
    s = ["<svg viewBox='0 0 720 520' xmlns='http://www.w3.org/2000/svg' font-family='Segoe UI' font-size='12'>",
         "<defs><marker id='ar' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='6' markerHeight='6' orient='auto'>"
         "<path d='M0 0L10 5L0 10z' fill='#8A8A8A'/></marker></defs>",
         box(24, 10, 672, 72, "1. Sources ouvertes",
             ["CHIRPS (pluie) · Open-Meteo (météo) · MODIS (végétation) · JRC + Sentinel-2 (lacs)",
              "FAOSTAT (récoltes) · HCP (recensement 2024) · geoBoundaries + OpenStreetMap (contours)"]),
         f"<path d='M360 82V106' {a}/>",
         box(24, 108, 672, 72, "2. Acquisition et transformation : Python + Google Earth Engine",
             ["téléchargement, découpage du Maroc, statistiques zonales, SPI, NDVI agricole, eau (NDWI)",
              "résultat : fichiers CSV propres (dossier clean/)"]),
         f"<path d='M360 180V204' {a}/>",
         box(24, 206, 672, 88, "3. Chargement : SSIS (9 packages) vers SQL Server",
             ["Staging_DB : BULK INSERT des CSV bruts",
              "DWH_DB : MERGE incrémental vers le schéma en étoile (6 faits, 5 dimensions, 1,17 M lignes)",
              "etl.RunLog + etl.LoadAudit : journal et reçu de chaque chargement"], main=True),
         f"<path d='M{c1 + (2*cw+16)/2:.1f} 294V318' {a}/>",
         box(c1, 320, round(2 * cw + 16), 72, "4. Modèle : SSAS Tabular (DroughtModel)",
             ["lit les vues bi en lecture seule · 38 mesures DAX", "rapproché avec SQL : 16 / 16 identiques"]),
         f"<path d='M{c3 + cw/2:.1f} 294V418' {a}/>",
         f"<text x='{c3 + cw/2 - 8:.1f}' y='346' text-anchor='end' font-size='11' fill='#6B6B6B'>export Python</text>",
         f"<text x='{c3 + cw/2 - 8:.1f}' y='361' text-anchor='end' font-size='11' fill='#6B6B6B'>JSON + CSV</text>",
         f"<path d='M{c1 + cw/2:.1f} 392V418' {a}/>", f"<path d='M{c2 + cw/2:.1f} 392V418' {a}/>",
         box(round(c1), 420, round(cw), 88, "5a. Power BI", ["connexion directe au modèle", "6 pages, page 1 terminée", "sur ce poste uniquement"]),
         box(round(c2), 420, round(cw), 88, "5b. Report Server", ["bulletin PDF mensuel", "+ alertes", "prévu (étape 16)"]),
         box(round(c3), 420, round(cw), 88, "5c. Site web public", ["carte et graphiques (D3)", "données téléchargeables", "GitHub Pages"]),
         "</svg>"]
    return "".join(s)


def table(head, rows):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def fig(n, inner, caption):
    return f"<figure>{inner}<figcaption><b>Figure {n}.</b> {caption}</figcaption></figure>"


def img(name):
    return f"<img src='img/{name}'>"


def mapcrop(name):
    """Show only the map part (x 90-1090 of 1920) of a video_kit data image, without its English text panel."""
    return f"<div class='mapcrop'><img src='img/{name}'></div>"


def massira_chart():
    import csv
    rows = []
    with open(HERE.parents[1] / "clean" / "dam_water_monthly.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["dam_id"] == "2" and float(r["clear_pct"]) >= 80:
                y, m = int(r["month_start"][:4]), int(r["month_start"][5:7])
                rows.append((y + (m - 1) / 12, float(r["water_km2"]), r["month_start"][:7]))
    left, right, base, y0 = 44, 700, 270, 30
    X = lambda t: left + (t - 2000) / 27 * (right - left)
    Y = lambda v: base - v / 100 * (base - y0)
    s = ["<svg viewBox='0 0 720 300' xmlns='http://www.w3.org/2000/svg' font-family='Segoe UI' font-size='11'>"]
    for v in (0, 25, 50, 75, 100):
        s.append(f"<line x1='{left}' x2='{right}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='#E3E1DC'/>"
                 f"<text x='{left-6}' y='{Y(v)+4:.1f}' text-anchor='end' fill='#6B6B6B'>{v}</text>")
    for yr in range(2000, 2028, 4):
        s.append(f"<text x='{X(yr):.1f}' y='{base+16}' text-anchor='middle' fill='#6B6B6B'>{yr}</text>")
    pts = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v, _ in rows)
    s.append(f"<polygon points='{X(rows[0][0]):.1f},{base} {pts} {X(rows[-1][0]):.1f},{base}' fill='#1F4E9C' fill-opacity='0.12'/>")
    s.append(f"<polyline points='{pts}' fill='none' stroke='#1F4E9C' stroke-width='1.8'/>")
    marks = {"2010-06": ("plein : 90,9 km²", -10, "middle"), "2024-04": ("avril 2024 : 10,9 km² (12 %)", 22, "end"),
             "2026-04": ("avril 2026 : 68,7 km² (75 %)", -12, "end")}
    for t, v, k in rows:
        if k in marks:
            lab, dy, anc = marks[k]
            col = "#B3261E" if k == "2024-04" else "#1F4E9C"
            s.append(f"<circle cx='{X(t):.1f}' cy='{Y(v):.1f}' r='4' fill='{col}'/>"
                     f"<text x='{X(t) + (-8 if anc == 'end' else 0):.1f}' y='{Y(v)+dy:.1f}' text-anchor='{anc}' fill='#222' font-weight='600'>{lab}</text>")
    s.append(f"<text x='{left}' y='16' fill='#6B6B6B'>km² d'eau</text>")
    s.append(f"<line x1='{left}' x2='{right}' y1='{base}' y2='{base}' stroke='#555'/></svg>")
    return "".join(s)


SOURCES = table(["Source", "Contenu", "Période", "Accès", "Volume → résultat"], [
    ["CHIRPS v3 (UC Santa Barbara)", "Pluie mensuelle par satellite, ~5 km", "1991-01 → 2026-10", "HTTPS, 1 GeoTIFF Afrique / mois", "430 fichiers, 2,25 Go → 87 Mo → 32 250 lignes"],
    ["Open-Meteo (ERA5)", "Météo quotidienne : Tmax, Tmin, pluie, ETo", "1991-01-01 → 2026-11-11", "API web gratuite", "52 Mo → 982 425 lignes"],
    ["MODIS MOD13Q1 (NASA)", "Végétation (NDVI), 250 m, 16 jours", "2000-02 → 2026-10", "Google Earth Engine", "24 075 lignes"],
    ["JRC GSW + Sentinel-2", "Surface d'eau de 26 lacs de barrage", "2000-01 → 2026-10", "Google Earth Engine", "8 398 lignes"],
    ["OpenStreetMap", "Contours des 26 réservoirs ≥ 4 km²", "2026", "API Overpass", "26 contours"],
    ["FAOSTAT", "Production agricole nationale", "2000 → 2024", "Fichier zip", "4,2 Mo → 2 546 lignes"],
    ["HCP, recensement 2024", "Population légale par province", "2024", "Fichier Excel", "75 provinces, 36 828 330 hab."],
    ["geoBoundaries", "Contours des provinces (ADM2)", "2017", "GeoJSON", "75 contours"]])

STAR = table(["Table", "Type", "Grain", "Lignes"], [
    ["FactWeatherDaily", "Fait", "province × jour", "982 425"],
    ["FactDroughtIndex", "Fait", "province × mois × échelle SPI (1, 3, 6, 12)", "127 578"],
    ["FactRainfallMonthly", "Fait", "province × mois (pluie + normale 1991-2020)", "32 250"],
    ["FactVegetationMonthly", "Fait", "province × mois", "24 075"],
    ["FactReservoirMonthly", "Fait", "barrage × mois (surface, % visible, source)", "8 398"],
    ["FactCropProduction", "Fait", "culture × année", "2 546"],
    ["DimDate", "Dimension", "jour 1940-2030 (mois, saison agricole, Ramadan)", "33 238"],
    ["DimGeography", "Dimension", "province, région, population 2024", "75 + national"],
    ["DimDam", "Dimension", "réservoir, surface maximale", "26"],
    ["DimCrop", "Dimension", "culture FAO", "103"],
    ["DimDroughtCategory", "Dimension", "classe SPI, libellé et couleur", "7"]])

TESTS = table(["Niveau", "Fichier", "Ce qui est vérifié", "Résultat"], [
    ["Fondations", "sql/tests/phase1_tests.sql", "75 provinces, population 36 828 330, calendrier sans trou ni doublon, Ramadan 2024", "20 tests PASS"],
    ["Sources", "sql/tests/phase2_tests.sql", "75 provinces chaque mois et chaque jour, aucune pluie négative, SPI centré réduit, accords entre sources", "29+ tests PASS"],
    ["Entrepôt", "sql/tests/phase3_tests.sql", "clés, nombres de lignes, ré-exécution sans changement, nouveau mois simulé", "12 tests PASS"],
    ["Modèle", "ssas/tests/reconcile_model.ps1", "même question posée en DAX et en SQL", "16 / 16 identiques"],
    ["Site web", "scripts/tools/check_web_export.py", "chiffres du site contre SQL", "9 / 9 identiques"]])

PROBLEMS = table(["Problème", "Cause", "Solution", "Preuve"], [
    ["Téléchargement CHIRPS bloqué 20 min au mois 28, sans erreur", "Téléchargement sans délai d'attente", "Délai de 60 s, nouvelles tentatives, reprise sur les fichiers présents", "430 mois en ~37 min"],
    ["Limite de l'API météo (10 000 unités / jour)", "~28 000 unités nécessaires", "Téléchargement reprenable sur 3 jours, sans contourner la limite", "982 425 lignes"],
    ["83 provinces au lieu de 75", "Arrondissements de Casablanca lus comme provinces", "Codes de niveau province uniquement", "Test 75 / 36 828 330 PASS"],
    ["Ramadan 2024 au 10 mars", "Calendrier Hijri par défaut de SQL Server", "Calendrier Umm al-Qura, écart d'un jour documenté", "Test calendrier PASS"],
    ["Pixels de mer à -9999 non déclarés", "Métadonnée absente du fichier", "Valeur exclue explicitement", "Aucune pluie négative"],
    ["Calcul de végétation : 19 h", "Conversion 10 m → 250 m répétée chaque mois", "Une requête par année", "~2 h au total"],
    ["11 lacs trouvés, aucun grand barrage", "Requête OSM ignorant les formes multi-parties", "Requête corrigée (out geom)", "26 réservoirs"],
    ["Trous Landsat avant 2013", "Panne du capteur Landsat 7", "% visible par mois, seuil 80 %", "JRC / Sentinel-2 : r = 0,997"],
    ["Rechargements réécrivant toutes les lignes", "MERGE sans comparaison des valeurs", "Mise à jour si une valeur change + reçu", "2e passage : 0 / 0"],
    ["Projet Power BI illisible après redémarrage", "6 fichiers remplis de zéros, non versionnés", "Format repris d'un projet vierge ; Git", "Page 1 récupérée"],
    ["Carte du site : un rectangle bleu", "72 éclats de côte dessinés à l'envers", "Inversion de ces seuls morceaux", "75 provinces affichées"],
    ["Settat 2024 : 243,1 mm (site) / 243,2 mm (SQL)", "Arrondi avant la somme", "Deux décimales conservées", "9 / 9 contrôles PASS"],
    ["SQL Server 2025 sans Reporting Services", "SSRS retiré après 2022", "Power BI Report Server prévu", "—"]])

STATUS = table(["Phase", "Étapes", "Statut"], [
    ["0. Environnement", "1-2 : outils, bases, journal d'exécution", "Terminé"],
    ["1. Fondations", "3-5 : provinces, recensement, calendrier", "Terminé"],
    ["2. Sources", "6-11 : cultures, météo, pluie, SPI, végétation, barrages", "Terminé"],
    ["3. Entrepôt fiable", "12 : schéma en étoile, chargements incrémentaux", "Terminé"],
    ["4. Analyse", "13 : modèle SSAS", "Terminé"],
    ["4. Analyse", "14 : rapport Power BI (6 pages)", "En cours (page 1 terminée)"],
    ["4. Analyse", "14b : site web public", "Terminé en local, mise en ligne à faire"],
    ["4. Analyse", "15 : prévision du rendement du blé", "À faire"],
    ["4. Analyse", "16 : bulletin PDF mensuel + alertes", "À faire"],
    ["5. Automatisation", "17 : package maître + job SQL Server Agent", "À faire"],
    ["5. Livraison", "18 : rapport, dépôt GitHub, soutenance", "En cours"]])

CSS = """
@page { size: A4; margin: 22mm 20mm 20mm 20mm;
  @bottom-center { content: counter(page); font: 9pt 'Segoe UI'; color: #777; }
  @top-right { content: 'Observatoire de la sécheresse au Maroc'; font: 8.5pt 'Segoe UI'; color: #999; } }
@page cover { margin: 0; @bottom-center { content: none; } @top-right { content: none; } }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1A1A1A; margin: 0; }
.cover { page: cover; height: 297mm; width: 210mm; position: relative; background: #14202E; color: #F3F1EC;
  padding: 40mm 22mm 0; break-after: page; overflow: hidden; }
.cover .school { font-size: 11pt; letter-spacing: 3px; color: #E8B86B; font-weight: 700; }
.cover h1 { font-size: 30pt; line-height: 1.15; margin: 14mm 0 6mm; }
.cover .sub { font-size: 13pt; color: #C9D1DB; }
.cover .stack { margin-top: 10mm; font-size: 10.5pt; color: #9FB0C2; }
.covermap { position: absolute; right: 18mm; bottom: 30mm; width: 120mm; height: 130mm; overflow: hidden; }
.covermap img { position: absolute; height: 100%; left: -9.6%; }
.mapcrop { position: relative; overflow: hidden; aspect-ratio: 1000 / 1080; background: #14202E; border-radius: 4px; }
.mapcrop img { position: absolute; height: 100%; width: auto !important; left: -9%; top: 0; border-radius: 0 !important; }
.cover .meta { position: absolute; left: 22mm; bottom: 14mm; font-size: 10.5pt; color: #C9D1DB; line-height: 1.6; }
h2 { font-size: 15pt; color: #14202E; border-bottom: 2px solid #E8B86B; padding-bottom: 3pt; margin: 18pt 0 8pt; break-after: avoid; }
h2.new { break-before: page; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; color: #1F4E9C; break-after: avoid; }
p { margin: 0 0 7pt; text-align: justify; }
ul, ol { margin: 0 0 8pt 16pt; padding: 0; } li { margin: 2pt 0; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #F1EFEA; padding: 0 3px; border-radius: 3px; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 10pt; font-size: 8.8pt; break-inside: auto; }
th { background: #14202E; color: #fff; text-align: left; padding: 4pt 5pt; font-weight: 600; }
td { padding: 3.5pt 5pt; border-bottom: 1px solid #DDD9D0; vertical-align: top; }
tr { break-inside: avoid; } tbody tr:nth-child(even) td { background: #FAF8F4; }
figure { margin: 8pt 0 12pt; break-inside: avoid; text-align: center; }
figure img, figure svg { width: 100%; height: auto; border-radius: 4px; }
figcaption { font-size: 8.8pt; color: #555; margin-top: 4pt; text-align: left; }
.lead { font-size: 11pt; background: #F4F1EA; border-left: 4px solid #E8B86B; padding: 8pt 12pt; margin: 6pt 0 12pt; }
.toc { list-style: none; margin: 0; padding: 0; font-size: 11pt; }
.toc li { display: flex; border-bottom: 1px dotted #BBB; padding: 5pt 0; }
.toc li span { flex: 1; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6pt; margin: 10pt 0; }
.kpi { border: 1px solid #DDD9D0; border-radius: 6px; padding: 7pt 8pt; }
.kpi b { display: block; font-size: 15pt; color: #1F4E9C; } .kpi span { font-size: 8.5pt; color: #555; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8pt; }
"""

BODY = f"""
<section class='cover'>
  <div class='school'>ISGA · PROJET MSBI · BIG DATA</div>
  <h1>Observatoire de la sécheresse<br>et de la sécurité hydrique au Maroc</h1>
  <div class='sub'>Des pixels satellites aux tableaux de bord : 75 provinces, 1991-2026, données ouvertes réelles</div>
  <div class='stack'>SQL Server 2025 · SSIS · SSAS Tabular · Power BI · Python · Google Earth Engine</div>
  <div class='covermap'><img src='img/pixels_step3.png'></div>
  <div class='meta'>Réalisé par : Abdelkrim El Ayachi<br>Année universitaire 2026-2027 · Rapport du 21 novembre 2026</div>
</section>

<h2>Sommaire</h2>
<ul class='toc'>
<li><span>Résumé</span></li><li><span>1. Contexte et objectifs</span></li><li><span>2. Données : des sources ouvertes uniquement</span></li>
<li><span>3. Architecture</span></li><li><span>4. Acquisition et transformation : du pixel au chiffre par province</span></li>
<li><span>5. Entrepôt de données : schéma en étoile et chargements SSIS</span></li><li><span>6. Modèle SSAS et restitution</span></li>
<li><span>7. Qualité : tests automatiques et rapprochements</span></li><li><span>8. Résultats : ce que montrent les données</span></li>
<li><span>9. Difficultés rencontrées et solutions</span></li><li><span>10. État d'avancement et prochaines étapes</span></li>
<li><span>11. Sources et licences</span></li>
</ul>

<h2>Résumé</h2>
<p class='lead'>Ce projet MSBI mesure la sécheresse au Maroc, province par province, uniquement à partir de données ouvertes réelles :
pluie satellitaire, météo quotidienne, végétation, surface des lacs de barrage, récoltes et recensement 2024. L'entrepôt
SQL Server contient 1,17 million de lignes de faits, le modèle SSAS 38 mesures vérifiées contre SQL, et les résultats
sont affichés dans Power BI et sur un site web public.</p>
<div class='kpis'>
<div class='kpi'><b>75</b><span>provinces, 36,8 M d'habitants</span></div>
<div class='kpi'><b>1,17 M</b><span>lignes de faits dans DWH_DB</span></div>
<div class='kpi'><b>16 / 16</b><span>mesures DAX identiques à SQL</span></div>
<div class='kpi'><b>61 / 75</b><span>provinces en sécheresse, août 2022</span></div>
</div>

<h2 class='new'>1. Contexte et objectifs</h2>
<p>Le Maroc vient de traverser six saisons de sécheresse consécutives (2019-20 à 2024-25) ; le projet mesure ce phénomène
province par province avec des données ouvertes et vérifiables. Une première idée (fréquentation du tramway de Casablanca)
a été abandonnée : seuls des totaux annuels sont publics. La sécheresse, au contraire, est observée chaque jour par satellite.</p>
<p>Le projet répond à quatre questions :</p>
<ol><li>Où et quand le Maroc est-il en sécheresse, et combien de personnes sont concernées ?</li>
<li>Comment évoluent les réserves d'eau des grands barrages ?</li>
<li>Quel est l'effet sur la végétation agricole et sur la récolte de blé ?</li>
<li>Comment ces indicateurs peuvent-ils être mis à jour chaque mois de façon fiable ?</li></ol>
<p>Contraintes : données réelles uniquement (aucune donnée générée), chaîne Microsoft BI complète, un ordinateur portable
d'étudiant (14,8 Go de RAM) et un test automatique pour chaque étape du plan (6 phases, 18 étapes).</p>

<h2>2. Données : des sources ouvertes uniquement</h2>
<p>Chaque source a été testée par un vrai téléchargement avant la conception. La pluie couvre 1991-2026, car l'indice de
sécheresse exige au moins 30 ans de référence (normale OMM 1991-2020) ; les autres sources commencent en 2000.</p>
{SOURCES}
<p>Les taux de remplissage officiels des barrages sont publiés chaque jour, mais seulement en image dans un bulletin :
ils servent uniquement à valider la mesure satellitaire.</p>

<h2 class='new'>3. Architecture</h2>
<p>Python fait le travail sur les fichiers et les images, SSIS orchestre et journalise chaque chargement, SQL Server stocke,
SSAS calcule les indicateurs, et trois sorties les affichent.</p>
{fig(1, arch_chart(), "Architecture en cinq couches. Le site web lit directement l'entrepôt (export Python), car il doit fonctionner sans le serveur SSAS local ; Power BI et le futur bulletin passent par le modèle SSAS.")}

<h2 class='new'>4. Acquisition et transformation : du pixel au chiffre par province</h2>
<p>Toutes les transformations sont écrites en Python (<code>scripts/01</code> à <code>10</code>) ou envoyées à Google Earth
Engine ; elles produisent des fichiers CSV propres que SSIS charge ensuite.</p>
<h3>Pluie (CHIRPS) et statistique zonale</h3>
<p>Chaque mois, le script télécharge l'image de l'Afrique (4,9 Mo), découpe le Maroc (0,24 Mo, -95 %) et supprime
l'original ; un manifeste trace chaque fichier. Les pixels de mer valent -9999 sans être déclarés « sans donnée » : ils sont
exclus explicitement. Une statistique zonale fait ensuite la moyenne des pixels contenus dans chaque contour : une image
devient 75 valeurs, 430 images deviennent 32 250 lignes.</p>
<div class='two'>{fig(2, mapcrop('pixels_step1.png'), "Données brutes : pluie de janvier 2026 (CHIRPS), pixels d'environ 5 km.")}
{fig(3, mapcrop('pixels_step3.png'), "Après statistique zonale : une moyenne par province (Larache : 423 mm).")}</div>
<h3>Indice de sécheresse (SPI)</h3>
<p>Le SPI compare la pluie cumulée (1, 3, 6 ou 12 mois) aux mêmes mois de la période 1991-2020 : ajustement d'une loi gamma,
puis conversion en score normal centré réduit (méthode OMM). 0 = normal, -1 = sécheresse, -2 = sécheresse extrême. Dans le
Sahara, où il ne pleut presque jamais en été, 72 valeurs sur 32 250 (SPI-1) sont laissées vides plutôt que publiées sans
validité. Contrôle : sur 1991-2020, le SPI-12 a une moyenne de -0,000 et un écart-type de 1,001. Total : 127 578 valeurs.</p>
<h3>Végétation (MODIS)</h3>
<p>Earth Engine filtre les pixels de bonne qualité (nuages et neige retirés), puis ne garde que les cellules de 250 m couvertes
à 50 % ou plus de cultures selon la carte ESA WorldCover (10 m). Résultat : le NDVI des terres agricoles par province et par
mois. Regrouper les 12 mois d'une année en une seule requête a réduit le calcul de 19 heures à 2 heures.</p>
<h3>Lacs de barrage</h3>
<p>Pour chaque réservoir (contour OpenStreetMap + 300 m), un pixel est de l'eau si NDWI = (Vert - PIR) / (Vert + PIR) > 0.
La surface = nombre de pixels d'eau × surface du pixel. Deux satellites sont joints : Landsat via JRC (2000-2016) et
Sentinel-2 (depuis 2017). Chaque mois garde le pourcentage du lac visible ; en dessous de 80 %, le mois est marqué non fiable.
Sur la période commune 2017-2021 (1 269 mois-lacs), les deux sources ont une corrélation de 0,997.</p>
<h3>Météo (Open-Meteo) et rapprochement des noms</h3>
<p>Une province coûte 374 unités d'API pour une limite gratuite de 10 000 par jour : le téléchargement, reprenable, s'est
étalé sur trois jours. Toutes les provinces sont ensuite coupées au dernier jour commun (2026-11-11). Le recensement et la
carte écrivent les provinces différemment (français, anglais, arabe) : normalisation, score de similarité et vérification
manuelle des 6 correspondances les plus faibles donnent 75 provinces sur 75.</p>

<h2>5. Entrepôt de données : schéma en étoile et chargements SSIS</h2>
<p>Les données passent par deux bases : <code>Staging_DB</code> reçoit les CSV bruts, <code>DWH_DB</code> contient le modèle
en étoile nettoyé (1 177 272 lignes de faits). Le dictionnaire de données est dans <code>docs/WAREHOUSE.md</code>.</p>
{STAR}
<h3>Chargement par SSIS</h3>
<p>Neuf packages (<code>00_Test_Logging</code> à <code>08_Reservoirs</code>), générés par un script pour rester identiques,
suivent le même schéma :</p>
<ol><li>Ouverture d'une exécution dans <code>etl.RunLog</code>.</li><li>Exécution du script Python (Execute Process Task).</li>
<li><code>BULK INSERT</code> du CSV dans la table de staging.</li><li>Procédure stockée de chargement vers l'entrepôt.</li>
<li>Clôture de l'exécution ; en cas d'erreur, l'exécution est marquée en échec avec le message.</li></ol>
<h3>Chargement incrémental et performance</h3>
<p>Les procédures utilisent un <code>MERGE</code> qui ne met à jour une ligne que si une valeur a réellement changé
(<code>EXISTS (SELECT source EXCEPT SELECT cible)</code>), et chaque chargement écrit un reçu (insérées, mises à jour,
inchangées) dans <code>etl.LoadAudit</code>. Preuve : tous les packages exécutés deux fois donnent au second passage
0 insertion et 0 mise à jour sur les 12 tables ; un nouveau mois simulé donne 75 insertions, 0 mise à jour et 32 175 lignes
inchangées. Des index columnstore non clusterisés couvrent les quatre plus grandes tables de faits, et la mémoire de SQL Server
est limitée à 4 Go pour partager le portable avec SSAS, Visual Studio et Power BI.</p>

<h2 class='new'>6. Modèle SSAS et restitution</h2>
<h3>Modèle tabulaire SSAS (DroughtModel)</h3>
<p>Le modèle (compatibilité 1700) lit les vues <code>bi</code> et contient 38 mesures DAX : provinces en sécheresse,
population concernée, pluie en % de la normale, surface d'eau des barrages (dernier mois fiable de chaque barrage), NDVI
agricole de mars, ainsi que des mesures de libellé et de couleur pour les visuels. Il est écrit sous forme de code
(<code>build_model.py</code> → <code>Model.bim</code>) et déployé par script. SSAS accède à l'entrepôt avec son compte de
service Windows, via une connexion en lecture seule. Une mesure renvoie 0, et non vide, quand les données existent mais
qu'aucune province n'est en sécheresse (cas de 2008).</p>
<h3>Power BI</h3>
<p>Le rapport est connecté en direct au modèle SSAS : tous les visuels utilisent les mêmes mesures testées. Une carte des
provinces au format TopoJSON a été générée à partir des contours du projet, car Power BI ne reconnaît pas les provinces
marocaines par leur nom. La page 1 (vue nationale) est terminée ; la page 2 est en cours.</p>
<h3>Site web public</h3>
<p>Power BI dépend du serveur SSAS local et ne peut pas être ouvert par d'autres personnes. Un script exporte l'entrepôt en
fichiers JSON et CSV (4,6 Mo) ; une page web statique dessine la carte et les graphiques dans le navigateur et propose le
téléchargement de toutes les tables. La publication sur GitHub Pages est prête et sera active après la mise en ligne du dépôt.</p>
{fig(4, img('website_2022_august.png'), "Le site web public, août 2022 : 61 provinces sur 75 (81,3 %) et 33,1 millions d'habitants en sécheresse.")}

<h2>7. Qualité : tests automatiques et rapprochements</h2>
<p>Chaque étape a un test qui compare le résultat à un fait connu ; tous les tests passent à la date du rapport.</p>
{TESTS}
<p>Exemples de rapprochement : en août 2022, 61 provinces et 33 089 522 personnes en sécheresse, identiques dans SQL, dans le
modèle et sur le site ; production de blé 2024 = 2 441 670 t. La pluie satellitaire (CHIRPS) a été comparée à une source
indépendante (modèle ERA5 d'Open-Meteo) : corrélation mensuelle nationale de 0,92.</p>
<p>La mesure satellitaire des barrages (surface) est plus élevée que le taux officiel (volume), car un réservoir a la forme
d'un bol. Elle sert d'indicateur d'évolution : elle suit le même ordre que les chiffres officiels (février 2024 &lt;
janvier 2026 &lt; mai 2026), ce qui est testé.</p>

<h2>8. Résultats : ce que montrent les données</h2>
<p>La saison 2021-22 est la plus sèche de la période : en août 2022, 61 provinces sur 75, soit 33 089 522 habitants, étaient
en sécheresse. De 2020 à 2025, cinq mois d'août sur six dépassent la moitié des provinces ; en 2026, après un hiver très
pluvieux, il n'en reste que 4.</p>
{fig(5, drought_chart(), "Provinces avec un SPI-12 ≤ -1 à la fin du mois d'août (fin de l'année hydrologique), 1992-2026. Source : DWH_DB, FactDroughtIndex.")}
{fig(6, massira_chart(), "Surface d'eau du barrage Al Massira mesurée par satellite : Landsat/JRC 2000-2016, Sentinel-2 depuis 2017 (mois visibles à 80 % ou plus). Source : DWH_DB, FactReservoirMonthly.")}
<p><b>Réserves d'eau.</b> Al Massira, deuxième barrage du pays : 90,9 km² en juin 2010 (plein), 10,9 km² en avril 2024
(12 %), 68,7 km² en avril 2026 (75 %). La surface totale des 26 lacs passe de 424 km² (moyenne 2018) à 275 km² (2024),
puis 493 km² (2026).</p>
<p><b>Température.</b> La moyenne nationale des maximales quotidiennes passe de 23,2 °C en 1991 à 26,2 °C en 2023.</p>
<p><b>Végétation et récoltes.</b> Le NDVI agricole de mars suit le rendement du blé avec une corrélation de 0,86
(2001-2024). Mars 2026 a le NDVI agricole le plus élevé depuis 2000 (0,652), après le mois de janvier le plus pluvieux
depuis 2014 (136 mm en moyenne par province).</p>

<h2 class='new'>9. Difficultés rencontrées et solutions</h2>
<p>Chaque problème a été consigné au moment où il est apparu, avec sa cause, sa solution et la preuve qu'elle fonctionne.</p>
{PROBLEMS}

<h2 class='new'>10. État d'avancement et prochaines étapes</h2>
<p>Les étapes 1 à 13 du plan (installation, sources, entrepôt, modèle SSAS) sont terminées et testées ; la restitution est en cours.</p>
{STATUS}
<p>La prévision du rendement s'appuiera sur le NDVI agricole de mars (corrélation de 0,86 avec le rendement du blé sur
2001-2024) et sera évaluée en validation croisée, une année laissée de côté à chaque fois.</p>

<h2>11. Sources et licences</h2>
<ul>
<li>CHIRPS v3, pluie mensuelle : Climate Hazards Center, UC Santa Barbara (data.chc.ucsb.edu)</li>
<li>Open-Meteo, archive météo historique (ERA5), licence CC BY 4.0 (open-meteo.com)</li>
<li>MODIS MOD13Q1 v061 (NASA), ESA WorldCover v200, JRC Global Surface Water, Copernicus Sentinel-2 : via Google Earth Engine</li>
<li>OpenStreetMap, contours des réservoirs via l'API Overpass, licence ODbL</li>
<li>FAOSTAT, production agricole (fao.org/faostat)</li>
<li>HCP, recensement général de la population 2024 (hcp.ma)</li>
<li>geoBoundaries, Maroc ADM2 (github.com/wmgeolab/geoBoundaries)</li>
<li>Méthode SPI : OMM, <i>Standardized Precipitation Index User Guide</i> (OMM-n° 1090, 2012)</li>
</ul>
<p>Documents du projet : <code>docs/JOURNAL.md</code> (journal daté), <code>docs/DATA_SOURCES.md</code>,
<code>docs/WAREHOUSE.md</code>, <code>docs/MODEL.md</code>.</p>
"""

OUT_HTML.write_text(f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Rapport - Observatoire de la sécheresse au Maroc</title>"
                    f"<style>{CSS}</style></head><body>{BODY}</body></html>", encoding="utf-8")
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={OUT_PDF}", OUT_HTML.as_uri()], check=True, capture_output=True, timeout=180)
print(f"PDF written: {OUT_PDF} ({OUT_PDF.stat().st_size / 1e6:.1f} MB)")
