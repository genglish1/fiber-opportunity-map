# Fiber Opportunity Scoring Model

An interactive map and data pipeline that identifies census tracts ripe for new fiber broadband builds across six states: **Virginia, Kentucky, Maryland, Pennsylvania, Ohio, and New York**.

**[View the Interactive Map](https://genglish1.github.io/fiber-opportunity-map/fiber_opportunity_map.html)**

## Overview

This project merges three federal datasets at the census tract level to score each tract on how attractive it is for a greenfield fiber deployment. The output is a self-contained interactive HTML map where you can hover over any tract to see its opportunity score breakdown.

### Key Findings

- **16,711 census tracts** scored across 6 states (63.9M people, 20.7M broadband serviceable locations)
- **838,000 BSLs** classified as unserved (no provider offers 25/3 Mbps)
- **693 tracts** with zero fiber providers
- **1,536 tracts** rated High or Very High opportunity
- Pennsylvania leads with 511 High-tier tracts, followed by Virginia (299) and Kentucky (201)

## Methodology

Each tract receives a composite **Opportunity Score (0–100)** built from four weighted components:

### Supply Gap (40%)
How much room exists for a new fiber entrant?
- Number of existing fiber providers (fewer = better)
- Percentage of BSLs without fiber service
- Concentration of unserved + underserved BSLs
- Copper/DSL dependency (aging infrastructure ripe for replacement)
- Total provider count (less competition = more opportunity)

### Demand Signal (30%)
Will people subscribe if you build it?
- Median household income (can residents afford $60–80/mo service?)
- Household density / BSL count (enough rooftops to justify the build)
- Cellular-only rate (people want connectivity but lack wired options)
- Adoption gap (broadband available but not subscribed — marketing opportunity)
- Total population

### Funding Tailwind (15%)
Is federal funding available to offset build costs?
- Count of BEAD-eligible unserved BSLs (BEAD's first priority)
- Unserved BSLs as percentage of total (funding concentration)
- Count and concentration of underserved BSLs (BEAD's second priority)

### Build Feasibility (15%)
Can you actually build profitably here?
- RUCC-based sweet spot scoring (suburban/small-town areas score highest; dense metros have incumbents, very rural areas are cost-prohibitive)
- BSL density sweet spot (40th–70th percentile is ideal)
- Fewer existing providers = easier market entry

All sub-scores are percentile-ranked (0–100) within the dataset and combined using the weights above.

## Key Terms

| Term | Definition |
|------|-----------|
| **BSL** | Broadband Serviceable Location — an FCC-designated address (home or small business) where fixed broadband can be installed. The standard unit of measurement for broadband availability. |
| **Unserved** | A BSL where no provider offers at least 25/3 Mbps low-latency service. |
| **Underserved** | A BSL with service between 25/3 and 100/20 Mbps — below the modern broadband standard. |
| **Served** | A BSL with at least 100/20 Mbps low-latency service from fiber, cable, or licensed fixed wireless. |
| **BEAD** | Broadband Equity, Access, and Deployment Program — a $42.5B federal program funding broadband infrastructure in unserved and underserved areas. |
| **RUCC** | USDA Rural-Urban Continuum Code (1 = large metro, 9 = very rural). Codes 4–7 represent the "sweet spot" for fiber builds. |

## Data Sources

| Dataset | Source | Vintage | Geographic Level | Access |
|---------|--------|---------|-----------------|--------|
| **Broadband Availability** | [FCC Broadband Data Collection (BDC)](https://broadbandmap.fcc.gov/) via [ArcGIS Living Atlas](https://www.arcgis.com/home/item.html?id=22ca3a8bb2ff46c1983fb45414157b08) | June 2024 filing | Census tract | Public Feature Service API |
| **Socioeconomic Data** | [U.S. Census Bureau American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs) | 2020–2024 5-Year Estimates | Census tract | [Census API](https://api.census.gov/) |
| **Rural-Urban Classification** | [USDA Economic Research Service](https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/) | 2023 | County | CSV download |

### Census ACS Tables Used

| Table | Description | Key Variables |
|-------|-------------|---------------|
| B28002 | Internet Subscriptions | Broadband any type, cable/fiber/DSL, cellular-only, no internet |
| B28001 | Computer Ownership | Households with no computer |
| B19013 | Median Household Income | Inflation-adjusted dollars |
| B15003 | Educational Attainment | Population 25+ by degree level |
| B23025 | Employment Status | Civilian labor force, unemployed |
| B03002 | Hispanic Origin by Race | Non-Hispanic White, Black, Asian, Hispanic |
| B01003 | Total Population | — |
| B01002 | Median Age | — |
| B25001 | Housing Units | Total housing unit count |

### FCC BDC Fields Used

Tract-level summary data from the BDC includes: total BSLs, served/underserved/unserved BSLs (overall and by technology type: fiber, cable, copper, licensed fixed wireless), unique provider counts by technology, and 6/12-month trend data.

## Project Structure

```
Broadband-Equity/
├── README.md
├── METHODOLOGY.md              # Detailed scoring methodology
├── requirements.txt
├── scripts/
│   ├── pull_acs_data.py        # Census ACS data pipeline
│   ├── pull_fcc_bdc.py         # FCC BDC data pipeline (ArcGIS Feature Service)
│   ├── build_scoring_model.py  # Four-component scoring model
│   └── build_map.py            # Interactive Folium map generator
├── data/
│   ├── raw/                    # Source data (not in repo — regenerate via scripts)
│   └── processed/
│       ├── tract_scores.csv    # All 16,711 scored tracts
│       └── county_scores.csv   # County-level aggregated scores
└── output/
    └── fiber_opportunity_map.html  # Interactive map (self-contained)
```

## Reproducing the Analysis

### Requirements

- Python 3.9+
- Dependencies: `pandas`, `numpy`, `requests`, `geopandas`, `folium`, `pyarrow`

```bash
python -m venv venv
source venv/bin/activate
pip install pandas numpy requests geopandas folium pyarrow
```

### Run the Pipeline

```bash
# 1. Pull Census ACS data (tract-level, 6 states)
python scripts/pull_acs_data.py

# 2. Pull FCC BDC broadband availability data
python scripts/pull_fcc_bdc.py

# 3. Build the scoring model
python scripts/build_scoring_model.py

# 4. Generate the interactive map
python scripts/build_map.py
```

The USDA RUCC data is downloaded automatically by `pull_acs_data.py`. No API keys are required for the volumes used here, though a [free Census API key](https://api.census.gov/data/key_signup.html) is recommended for heavier usage.

## Limitations

- **FCC BDC data reflects provider-reported availability** (June 2024), not verified service. Providers may overstate coverage areas. The BDC challenge process corrects some of this, but gaps remain.
- **Census ACS adoption data** is survey-based with margins of error, particularly in low-population tracts. The 5-year estimates smooth this but still carry uncertainty.
- **The scoring model uses percentile ranking**, which means scores are relative within this 6-state dataset. Adding or removing states would shift all scores.
- **Build cost estimation is absent.** Terrain, pole access, permitting complexity, and make-ready costs are not captured in these datasets. RUCC codes and density are rough proxies at best.
- **BEAD allocations and timelines vary by state.** Virginia's BEAD program is further along than others. State-level regulatory environments also affect opportunity.
- **Tract-level analysis may mask sub-tract variation.** A tract scored "moderate" may contain pockets of excellent opportunity alongside well-served areas.

## License

This project uses publicly available federal data. The analysis, code, and visualizations are released under the [MIT License](LICENSE).

## Author

Gene English — [github.com/genglish1](https://github.com/genglish1)

Built with data from the FCC, U.S. Census Bureau, and USDA Economic Research Service.
