# Morocco Drought & Water Security Observatory

An end-to-end MSBI (Microsoft BI) project that tracks rainfall, drought, vegetation,
dam water surface and crop production across Morocco's 75 provinces, using only
real open data (satellite and official statistics), from 1981 to today.

## Architecture

```
Sources (CHIRPS, Open-Meteo, MODIS, JRC/Sentinel-2, FAOSTAT, HCP, geoBoundaries)
   -> SSIS (download, clean, load)  +  Python (satellite images, SPI)
   -> SQL Server: Staging_DB (raw) -> DWH_DB (star schema)
   -> SSAS Tabular (DAX measures)
   -> Power BI dashboards  +  Power BI Report Server (monthly PDF bulletin)
   -> SQL Server Agent (monthly automatic run)
```

## Folder structure

| Folder | Content |
|---|---|
| `docs/` | Project journal, plan with test status, data sources |
| `sql/` | SQL scripts, numbered in the order they must be run |
| `sql/tests/` | Test scripts that check each SQL step |
| `scripts/` | Python scripts (called by SSIS) |
| `ssis/` | Visual Studio SSIS / SSAS / report projects |
| `raw/` | Downloaded source files (not versioned, can be re-downloaded) |
| `clean/` | CSV files produced for SSIS (not versioned, can be regenerated) |
| `venv/` | Python environment (not versioned) |

## How to rebuild from scratch

1. Install the environment (see `docs/JOURNAL.md`, Phase 0)
2. Run the scripts in `sql/` in number order, in SSMS
3. Create the Python environment:
   `python -m venv venv` then
   `venv\Scripts\python.exe -m pip install -r requirements.txt`
4. Open `ssis/DroughtETL/DroughtETL.slnx` in Visual Studio and run the packages in number order
   (or run `ssis/tests/run_phase1.ps1`)

## Documents

- [Project journal](docs/JOURNAL.md): what was done, when, and why
- [Plan and test status](docs/PLAN.md): the 6 phases / 18 steps and their checks
- [Data sources](docs/DATA_SOURCES.md): verified sources, links and known limits
- [Challenges](docs/CHALLENGES.md): problems met and how they were solved (for the presentation)
- [Warehouse](docs/WAREHOUSE.md): star schema diagram, design decisions and data dictionary
