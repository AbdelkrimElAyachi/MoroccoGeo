# Analytical model (SSAS Tabular)

Database **`DroughtModel`** on the local Analysis Services server (Tabular mode, compatibility level 1700).
It reads the `bi` views of `DWH_DB` (`sql/11_bi_views.sql`) and defines every business calculation
**once**, so Power BI, Excel and the reports all show the same numbers.

| File | Role |
|---|---|
| `scripts/tools/build_model.py` | Defines the model (tables, relationships, measures) and writes `ssas/Model.bim` |
| `ssas/Model.bim` | The model definition (JSON) |
| `ssas/deploy_model.ps1` | Deploys `Model.bim` to SSAS and processes it (loads the data) |
| `ssas/tests/reconcile_model.ps1` | Checks the model against SQL (13 checks) |

Rebuild: `venv\Scripts\python.exe scripts\tools\build_model.py`, then `ssas\deploy_model.ps1`.
SSAS reads the warehouse with its service account `NT Service\MSSQLServerOLAPService`
(read-only, `db_datareader` on `DWH_DB`).

## Tables and relationships

```
                 Date ─────────────┬──────────┬───────────┬────────────┬─────────────┐
                  │                │          │           │            │             │
   Rainfall   Drought ── Drought Category  Vegetation  Weather   Crop Production ── Crop
      │           │                          │           │            │
      └───────────┴──────── Province ────────┴───────────┴────────────┘
                               │
                              Dam ── Reservoir ── Date
```

Hierarchies: **Calendar** (Year → Month), **Agricultural season** (Season → Month),
**Region - Province**. Province has latitude/longitude columns for maps.

## Measures (32)

| Folder | Measure | Meaning |
|---|---|---|
| Population | Population 2024 | HCP 2024 population of the selected provinces |
| | Provinces | number of provinces selected |
| Rainfall | Rain (mm) | rain over the period, averaged over the provinces |
| | Normal Rain (mm) | same months, 1991-2020 average |
| | Rain % of Normal | 100 % = normal |
| Drought index | SPI-1 / SPI-3 / SPI-6 / SPI-12 | average SPI at each time scale |
| | SPI-12 Latest Month | SPI-12 at the last month of the period |
| | Provinces in Drought | provinces with SPI-12 ≤ -1 at the last month |
| | % Provinces in Drought | share of provinces in drought |
| | People in Drought | 2024 population of those provinces |
| | % Population in Drought | share of the population |
| Vegetation | NDVI Farmland | greenness of farmland |
| | NDVI Farmland Normal | 2001-2020 average for the same months |
| | NDVI Farmland Anomaly | difference from normal (negative = less green) |
| | NDVI All Land | greenness of all land |
| Reservoirs | Water Surface (km2) | water surface of the selected dams at the last month |
| | Max Water Surface (km2) | largest surface ever observed |
| | Fill Index | surface / largest surface (surface, not volume) |
| Crops | Production (t), Area Harvested (ha), Yield (kg/ha) | FAOSTAT, national |
| | Wheat Production (t), Wheat Yield (kg/ha) | wheat only |
| | Production vs Previous Year | % change vs the year before |
| Weather | Avg Max / Min Temperature (C) | daily temperatures averaged |
| | Evapotranspiration (mm) | water demand of the air over the period |
| | Hot Days (Tmax >= 35C) per Province | heat days per province |

**"Latest month" logic:** drought and reservoir measures look at the **last month of the selected
period** (e.g. selecting the year 2022 shows the situation in December 2022, or in August with a month
filter). This answers "where are we now?" instead of mixing all months.

## Reconciliation (Step 13 test), all PASS

| Check | Model | SQL |
|---|---|---|
| Rows in each fact table | identical | identical |
| Population 2024 | 36,828,330 | 36,828,330 |
| Wheat production 2024 | 2,441,670 t | 2,441,670 t |
| Provinces in drought, Aug 2022 | 61 | 61 |
| People in drought, Aug 2022 | 33,089,522 | 33,089,522 |
| Settat rain 2024 / % of normal | 243.2 mm / 57.9 % | 243.2 mm / 57.9 % |
| Al Massira fill index, Apr 2024 | 14.6 % | 14.6 % |
| Settat NDVI farmland, Mar 2021 | 0.686 | 0.686 |

## Using the model

- **Excel:** Données → Obtenir des données → À partir d'une base de données → À partir d'Analysis Services →
  server `localhost` → database `DroughtModel` → pivot table.
- **Power BI Desktop:** Obtenir des données → Analysis Services → `localhost`, database `DroughtModel`,
  mode **Connexion active** (Live connection).
- **Visual Studio:** New project → *Import from Server (Tabular)* → `localhost` / `DroughtModel`
  (to browse the model; the source of truth stays `build_model.py`).
