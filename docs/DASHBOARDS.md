# Power BI dashboards (Step 14)

Power BI Desktop, **live connection** to the SSAS model `DroughtModel`: the report holds no data of its own;
every number comes from the model (and therefore from the same measures checked against SQL).

Files:
| File | Role |
|---|---|
| `powerbi/morocco_provinces.topojson` | Map of the 75 provinces for the Shape map visual (keys = `ProvinceShort`) |
| `powerbi/drought_theme.json` | Report colours (drought red → wet blue) |
| `powerbi/DroughtObservatory.pbip` | The report, saved as a Power BI **project** (text files, versioned in Git) |

---

## 0. One-time setup (step by step, with the reason for each step)

Power BI Desktop version used: 2.159 (Microsoft Store, November 2026), French interface.
**Before starting:** in `services.msc`, check that **SQL Server (MSSQLSERVER)** and
**SQL Server Analysis Services (MSSQLSERVER)** are running (SQL Server is on Manual startup).

### A1. The province map visual ("Carte de formes" / Shape map)
**Do:** nothing to switch on in this version. In older versions it was under
*Fichier → Options et paramètres → Options → Fonctionnalités en préversion → Visuel de carte de formes*,
followed by a restart of Power BI. In version 2.159 it is **not in the preview list** (checked 2026-11-19):
the visual is expected directly in the *Visualisations* pane (step B7).
If it is missing there, fallbacks: **Azure Maps** with the TopoJSON/GeoJSON as a reference layer, or a free
custom visual from AppSource that draws custom shapes.
**Why:** this visual colours **our own province shapes**. Normal maps look up place names through an online
service that doesn't reliably know Moroccan provinces ("Rehamna", "Fahs-Anjra"...).

### A2. Connect to the model (live connection)
**Do:**
1. **Accueil → Obtenir des données → Plus…** → **Base de données → Analysis Services → Se connecter**
2. **Serveur:** `localhost` · **Base de données:** `DroughtModel` · **Connexion active** ✅ → **OK**
3. The **Données** pane shows: Crop, Dam, Date, Drought, Drought Category, Province, Rainfall, Reservoir,
   Vegetation, Weather (measures grouped in folders).

**Why "Connexion active" and not "Importer":** the report keeps **no copy of the data** and cannot redefine the
calculations; every number is computed by the model, i.e. the 37 measures checked against SQL
(`ssas/tests/reconcile_model.ps1`). One definition of each number, used by every report.

### A3. Colour theme
**Do:** **Conception** tab → **Thèmes** gallery → arrow **▼** at its bottom right → **Rechercher des thèmes**
(or *Parcourir les thèmes*) → `D:\DroughtProject\powerbi\drought_theme.json` → **Ouvrir**.
(In Power BI 2.159 the themes are under **Conception**; older versions and tutorials put them under
*Affichage*, where they no longer are.)
**Why:** same palette on every page (**red = drought, blue = wet**, matching the drought categories),
so the report reads consistently.

### A4. Save as a Power BI project
**Do:** **Fichier → Enregistrer sous → Parcourir cet appareil** → `D:\DroughtProject\powerbi\` →
name **DroughtObservatory** → type **Projet Power BI (*.pbip)** if listed, otherwise `.pbix`.
**Why:** a `.pbip` is a folder of text files that Git can track (the option *"Détectez les modifications PBIP
externes et rechargez-les"* is already enabled in this installation). `.gitignore` excludes the local cache.

### Map settings (NOT a setup step: do it each time you add a province map, e.g. step B7)
The settings belong to the map visual, so they can only be done once the visual exists on a page.
1. Select the **Carte de formes** visual and put **Province → ProvinceShort** in **Emplacement**
   (*Générer un visuel* icon of the Visualisations pane).
2. Paintbrush (**Mettre en forme votre visuel**) → **Visuel** → **Paramètres de carte** →
   **Type de carte: Carte personnalisée** → **Ajouter un type de carte** →
   `D:\DroughtProject\powerbi\morocco_provinces.topojson` → **Ouvrir**: the 75 provinces appear.
3. Optional check: **Afficher les clés de la carte** lists the names in the file (Settat, Rehamna...);
   any province left grey would mean a name mismatch.
**Why:** the shape names in this file are exactly the model's `ProvinceShort` values (generated from
`DimGeography` by `scripts/tools/make_topojson.py`), so every province matches one-to-one.

---

## Page 1 · Vue d'ensemble — "Where is the drought now, and who is affected?"

**Audience:** decision makers (ministry, regions). **Tip:** click an empty area of the page before adding
each new visual, otherwise Power BI modifies the selected visual instead of creating one.

### Step by step
| Step | Do | Why |
|---|---|---|
| B1 Year slicer | *Visualisations* → **Segment** → drag **Date → Year** → Format → *Paramètres du segment → Style: Liste déroulante* → choose **2022** | filters the whole page to one year; a dropdown saves space |
| B2 Month slicer | **Segment** → **Date → MonthNameFr** → *Liste déroulante* → **Août** | drought and dam measures show the **last month selected**: "2022 / Août" = end of the 2021-22 farming season |
| B3 Card | **Carte** → **Drought → Drought index → % Provinces in Drought** → title *Provinces en sécheresse* | how much of Morocco is in drought (SPI-12 ≤ −1) |
| B4 Card | **Carte** → **People in Drought** in **Valeur** → title *Population en sécheresse* (keep the card's automatic units, e.g. "K"; the new card in 2.159 has no obvious *Unités d'affichage* option) | the human impact (HCP 2024 population of those provinces) |
| B5 Card | **Carte** → **Rainfall → Rain % of Normal** → title *Pluie vs normale* | the cause: 100 % = normal year |
| B6 Card | **Carte** → **Reservoir → Fill Index** → title *Remplissage des barrages (surface)* | the effect on water reserves (26 largest dams, from space) |
| B7 Map | **Carte de formes** → *Emplacement* **Province → ProvinceShort**; *Saturation des couleurs* **SPI-12 Latest Month**; *Info-bulles* **Drought Category (latest)**, **Rain % of Normal**, **Population 2024**; map settings as above; *Couleurs de remplissage → Divergent*: min **−2** `#B3261E`, centre **0** `#F2F2F2`, max **2** `#1F4E9C` | the colour *is* the drought level; −2 / 0 / +2 follow the official SPI scale (extreme drought / normal / extremely wet) |
| B8 Save | **Ctrl+S** | |

**Extra visuals** (in the list below, not in B1-B8; add them after the core works):
| Step | Do | Why |
|---|---|---|
| B9 Title | **Accueil** tab → group **Insérer** → **Zone de texte** (the "A" in a box) → *Observatoire de la sécheresse au Maroc*, size 20-24, top of page | every page says what it is |
| B10 Card | **Carte** → **Drought → Labels → Data Up To** in **Valeur**, small, top right (turn off its label if shown) | shows how recent the data is ("Données jusqu'à octobre 2026") |
| B11 Card | **Carte** → **Vegetation → NDVI Farmland Anomaly** → title *Verdure des cultures vs normale* | vegetation effect: negative = crops less green than usual |
| B12 Table | **Table** → columns **ProvinceShort**, **RegionName**, **SPI-12 Latest Month**, **Drought Category (latest)**, **Population 2024**; click the SPI header to sort driest first; arrow ▼ on *Drought Category (latest)* → **Mise en forme conditionnelle → Couleur d'arrière-plan → Style: Valeur du champ → Drought Color (latest)** | exact values next to the map, readable without relying on colours |

Notes learned while building: the map's colour numbers must be typed (−2 / 0 / 2), otherwise Power BI uses
the min/max of the selected year and blue no longer means "wet"; centre = 0 because SPI 0 = normal
(−1 is the drought threshold used by the cards and categories). *People in Drought* uses the 2024 population
for every year: title the card *Population en sécheresse (pop. 2024)*.

### Full list of visuals on the page

| Visual           | Fields                                                                                                                                                                          | Settings                                                                                                                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Text box (title) | "Observatoire de la sécheresse au Maroc"                                                                                                                                        |                                                                                                                                                                                                       |
| Card             | Drought → Labels → **Data Up To**                                                                                                                                               | small, top right                                                                                                                                                                                      |
| Slicer           | Date → **Year**                                                                                                                                                                 | style *Dropdown*; optional "Sélectionner tout" option                                                                                                                                                 |
| Slicer           | Date → **MonthNameFr**                                                                                                                                                          | style *Dropdown*; nothing selected = "Tout" = situation at the last month of the year                                                                                                                 |
| Card             | Drought → **% Provinces in Drought**                                                                                                                                            | title "Provinces en sécheresse"                                                                                                                                                                       |
| Card             | Drought → **People in Drought**                                                                                                                                                 | title "Population en sécheresse (pop. 2024)"; automatic units (K / M)                                                                                                                                 |
| Card             | Rainfall → **Rain % of Normal**                                                                                                                                                 | title "Pluie vs normale (période)"                                                                                                                                                                    |
| Card             | Reservoir → **Fill Index**                                                                                                                                                      | title "Remplissage des barrages (surface)"                                                                                                                                                            |
| Card             | Vegetation → **NDVI Farmland Anomaly**                                                                                                                                          | title "Verdure des cultures vs normale"                                                                                                                                                               |
| **Shape map**    | Location: Province → **ProvinceShort**; Color saturation: Drought → **SPI-12 Latest Month**; Tooltips: **Drought Category (latest)**, **Rain % of Normal**, **Population 2024** | *Saturation de la couleur* → *Ajouter une couleur intermédiaire* On; colours `#B3261E` / `#F2F2F2` / `#1F4E9C`; **type the values** Min −2, Centre 0, Max 2; title "Sécheresse par province (SPI-12)" |
| Table            | Province → **ProvinceShort**, **RegionName**, Drought → **SPI-12 Latest Month**, **Drought Category (latest)**, Province → **Population 2024**                                  | sort by SPI ascending; conditional formatting on *Drought Category (latest)* → Background color → **Field value** = **Drought Color (latest)**                                                        |

**Check:** Year 2022, month Août → *Provinces en sécheresse* ≈ 81 % (61 / 75), *People in Drought* ≈ 33.1 M,
the map mostly orange/red. Year 2026, month Octobre → mostly grey/blue.
**Why these values:** they are already known from SQL (61 of 75 provinces, 33,089,522 people, the same numbers
as the model reconciliation). If the page shows them, the report is connected and set up correctly.

## Page 2 · Pluie et sécheresse — "Is this drought exceptional compared with 35 years?"

**Audience:** everyone, especially researchers and journalists. Shows the long history (1991-2026).

### Step by step
| Step                  | Do                                                                                                                                                                                                                                                                                                                                                                                                       | Why                                                                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| P2.1 New page         | **+** next to the page tabs at the bottom → double-click the new tab → rename *Pluie et sécheresse*                                                                                                                                                                                                                                                                                                      | one question per page                                                                                                                            |
| P2.2 Title            | **Accueil → (group Insérer) Zone de texte** → *Pluie et sécheresse depuis 1991*                                                                                                                                                                                                                                                                                                                          |                                                                                                                                                  |
| P2.3 Region slicer    | **Segment** → **Province → RegionName** → Format → *Style: Liste verticale*; Ctrl+click to select several                                                                                                                                                                                                                                                                                                | look at one region or compare regions                                                                                                            |
| P2.4 Line chart       | **Graphique en courbes** (row 1, line icon) → *Axe X* **Date → Year**; *Axe Y* **Rain (mm)** and **Normal Rain (mm)**; *Filtres sur ce visuel* → **Year** → *Filtrage avancé* "est inférieur ou égal à" **2026** → title *Pluie annuelle vs normale 1991-2020*                                                                                                                                           | years below the normal line are dry years; the gap shows how dry. 2026 only has Jan-Oct, so it ends lower                                        |
| P2.5 SPI column chart | **Histogramme groupé** → *Axe X* **Date → MonthStart**; *Axe Y* **SPI-12**; Format → *Axe X → Type: Continu*; Format → *Colonnes → Couleur → fx* → *Style du format: Règles* based on **SPI-12**: `< -1` red `#B3261E`, `>= -1 and <= 1` grey `#BFBFBF`, `> 1` blue `#1F4E9C` → title *SPI-12 mensuel (≤ -1 = sécheresse)*                                                                               | each bar is one month; red runs = drought periods (1992-95, 1999-2001, 2005, 2007, 2016, 2019-2025), blue = wet periods (1996-97, 2009-11, 2026) |
| P2.6 Matrix           | **Matrice** → *Lignes* **RegionName**; *Colonnes* **Year**; *Valeurs* **Rain % of Normal**; *Filtres sur ce visuel* → **Year** ≥ **2015**; arrow ▼ on *Rain % of Normal* in *Valeurs* → **Mise en forme conditionnelle → Couleur d'arrière-plan** → *Style: Dégradé*, tick *Ajouter une couleur intermédiaire*: Minimum *Nombre* **0.4** red, Centre *Nombre* **1** white, Maximum *Nombre* **1.6** blue | one cell per region and year: red = drier than normal; shows which regions suffered most and for how long                                        |
| P2.7 Card             | **Carte** → **Rain % of Normal** → title *Pluie vs normale (sélection)*                                                                                                                                                                                                                                                                                                                                  | summary for the selected region(s)                                                                                                               |
| P2.8 Save             | **Ctrl+S**                                                                                                                                                                                                                                                                                                                                                                                               |                                                                                                                                                  |

Values in the matrix: `Rain % of Normal` is a ratio, so 1 = 100 %, 0.4 = 40 %, 1.6 = 160 %.
**Check:** red bars almost continuously from 2019 to 2025; blue in 2009-2010 and 1996; matrix mostly red for
2019-2025, 2022 around 80 % nationally.

### Full list of visuals on the page

| Visual | Fields | Settings |
|---|---|---|
| Slicer | Province → **RegionName** | list, multi-select |
| Line chart | X: Date → **Year**; Y: **Rain (mm)** and **Normal Rain (mm)** | title "Pluie annuelle vs normale 1991-2020" |
| Column chart | X: Date → **MonthStart** (continuous); Y: **SPI-12** | conditional formatting on columns: rules < -1 red, -1..1 grey, > 1 blue; title "SPI-12 mensuel" |
| Matrix | Rows: **RegionName**; Columns: **Year** (filter 2015-2026); Values: **Rain % of Normal** | background color scale red (low) → white (100 %) → blue (high) |
| Card | **Rain % of Normal** | for the selection |

**Check:** the SPI-12 columns are mostly red from 2019 to 2025, blue in 2009-2010 and 2026.

## Page 3 · Agriculture — "What did the drought do to crops? Can we see the harvest coming?"

| Visual | Fields | Settings |
|---|---|---|
| Line + column chart | X: **Year** (2000-2024); Columns: **Wheat Production (t)**; Line: **NDVI Farmland (March)** | secondary axis for NDVI |
| Scatter chart | X: **NDVI Farmland (March)**; Y: **Wheat Yield (kg/ha)**; Values/Details: Date → **Year** | Analytics → *Trend line* on; filter Year 2001-2024 |
| Line chart | X: Date → **MonthStart** (2023-2026); Y: **NDVI Farmland** and **NDVI Farmland Normal** | shows this season vs a normal season |
| Table | Crop → **CropNameFr** (filter *IsKeyCrop* = True); **Production (t)**, **Production vs Previous Year** | Year slicer |

**Check:** the scatter shows the clear upward link (r ≈ 0.86): green Marches → big harvests.

## Page 4 · Barrages — "How much water is left, and how fast does it come back?"

| Visual | Fields | Settings |
|---|---|---|
| Slicer | Dam → **DamName** | dropdown, multi-select |
| Line chart | X: Date → **MonthStart** (2017-2026); Y: **Water Surface (km2)** | title "Surface d'eau des 26 grands barrages" |
| Bar chart | Y: **DamName**; X: **Fill Index** | sort ascending; Year/Month slicers set the "as of" month |
| Map (bubble) or Azure map | Latitude: Dam → **Lat**; Longitude: **Lon**; Size: **Max Water Surface (km2)**; Tooltip: **Fill Index** | |
| Text box | "Indicateur de surface (pas de volume) : un barrage à 50 % de surface contient souvent moins de 50 % de son volume." | |

**Check:** Al Massira in April 2024 ≈ 15 %, April 2026 ≈ 90 %.

## Page 5 · Climat et chaleur — "Is it getting hotter, and does the air dry the soil faster?"
*(fills in when the weather data is loaded)*

| Visual | Fields |
|---|---|
| Line chart | X: **Year**; Y: **Avg Max Temperature (C)** |
| Column chart | X: **RegionName**; Y: **Hot Days (Tmax >= 35C) per Province** |
| Line chart | X: **Year**; Y: **Evapotranspiration (mm)** and **Rain (mm)** (water balance) |

## Page 6 · Fiche province (drill-through) — "Everything about one province"

1. Add a page, in the *Visualizations* pane under **Drill through** put Province → **ProvinceShort**.
2. Visuals: title card with **ProvinceShort**, cards **Population 2024**, **SPI-12 Latest Month**,
   **Drought Category (latest)**, **Rain % of Normal**; line chart Year × **Rain (mm)** / **Normal Rain (mm)**;
   line chart MonthStart × **NDVI Farmland** / **NDVI Farmland Normal**.
3. On page 1, right-click a province on the map or table → **Drill through → Fiche province**.

## Page 7 · Prévision (Step 15)
Added with the harvest forecast.

---

## Checklist before moving on
- [ ] Each page answers its question (written in the page title)
- [ ] The map shows all 75 provinces (no grey holes) and colours follow the SPI
- [ ] Slicers change every visual on the page
- [ ] Each page opens in a few seconds
- [ ] Someone else can read it without help
