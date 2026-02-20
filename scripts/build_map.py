"""
Build interactive Folium map of fiber opportunity scores.

Choropleth at the tract level colored by opportunity score.
Click a tract to see score breakdown and key metrics.

Uses Census tract geometries via the Census TIGERweb API.
"""

import pandas as pd
import geopandas as gpd
import folium
from folium.features import GeoJsonPopup, GeoJsonTooltip
import json
import os
import requests
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROC_DIR = os.path.join(DATA_DIR, "processed")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

STATES = {
    "VA": "51",
    "KY": "21",
    "MD": "24",
    "PA": "42",
    "OH": "39",
    "NY": "36",
}


def get_tract_geometries():
    """Download tract geometries from Census cartographic boundary shapefiles."""
    cache_path = os.path.join(DATA_DIR, "raw", "tract_geometries.geojson")

    if os.path.exists(cache_path):
        print("Loading cached tract geometries...")
        return gpd.read_file(cache_path)

    print("Downloading tract geometries from Census boundary files...")
    all_gdf = []

    for state_abbr, state_fips in STATES.items():
        print(f"  {state_abbr}...")
        # Census cartographic boundary files — 500k resolution (good balance of detail/size)
        url = (
            f"https://www2.census.gov/geo/tiger/GENZ2020/shp/"
            f"cb_2020_us_tract_500k.zip"
        )
        # This is a national file — download once, filter by state
        break  # Only need to download once

    # Download national tract boundaries
    zip_path = os.path.join(DATA_DIR, "raw", "cb_2020_us_tract_500k.zip")
    if not os.path.exists(zip_path):
        print("  Downloading national tract boundaries (this may take a minute)...")
        r = requests.get(url, timeout=300, stream=True)
        if r.status_code == 200:
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  Downloaded {os.path.getsize(zip_path) / 1024 / 1024:.1f} MB")
        else:
            print(f"  ERROR: {r.status_code}")
            return None

    # Read and filter to our states
    print("  Reading shapefile...")
    gdf = gpd.read_file(f"zip://{zip_path}")
    state_fips_list = list(STATES.values())
    gdf = gdf[gdf["STATEFP"].isin(state_fips_list)].copy()
    gdf = gdf.rename(columns={"GEOID": "GEOID"})
    print(f"  Filtered to {len(gdf)} tracts in our 6 states")

    # Save filtered cache
    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"  Cached to {cache_path}")

    return gdf


def build_map():
    """Build the Folium choropleth map."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load scores
    scores = pd.read_csv(
        os.path.join(PROC_DIR, "tract_scores.csv"),
        dtype={"GEOID": str, "county_geoid": str},
    )
    print(f"Loaded {len(scores)} scored tracts")

    # Get geometries
    geo = get_tract_geometries()

    # Merge scores with geometries
    merged = geo.merge(scores, on="GEOID", how="inner")
    print(f"Merged: {len(merged)} tracts with geometry")

    # Focus on high-opportunity tracts for performance
    # Include Moderate and above (score > 50), plus a sample of below average
    high_opp = merged[merged["opportunity_score"] >= 50].copy()
    below_avg = merged[merged["opportunity_score"] < 50].sample(
        n=min(2000, len(merged[merged["opportunity_score"] < 50])),
        random_state=42,
    ).copy()
    map_data = pd.concat([high_opp, below_avg], ignore_index=True)
    map_data = gpd.GeoDataFrame(map_data, geometry="geometry", crs="EPSG:4326")
    print(f"Map tracts: {len(map_data)} ({len(high_opp)} high-opp + {len(below_avg)} sample)")

    # Simplify geometries for performance
    map_data["geometry"] = map_data["geometry"].simplify(0.002, preserve_topology=True)

    # Round scores for display
    score_cols = [
        "opportunity_score", "score_supply_gap", "score_demand_signal",
        "score_funding_tailwind", "score_build_feasibility",
    ]
    for col in score_cols:
        map_data[col] = map_data[col].round(1)

    # Round other display fields
    map_data["median_hh_income"] = map_data["median_hh_income"].round(0)
    map_data["pct_no_fiber"] = map_data["pct_no_fiber"].round(1)
    map_data["pct_unserved_underserved"] = map_data["pct_unserved_underserved"].round(1)
    map_data["pct_cellular_only"] = map_data["pct_cellular_only"].round(1)
    map_data["pct_no_internet"] = map_data["pct_no_internet"].round(1)

    # Fill NaN for display
    map_data["median_hh_income"] = map_data["median_hh_income"].fillna(0)
    map_data["rucc_code"] = map_data["rucc_code"].fillna(0).astype(int)

    # Create map centered on the region
    center_lat = 38.5  # roughly center of our 6 states
    center_lon = -79.5
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles="CartoDB positron",
    )

    # Color scale
    colormap = folium.LinearColormap(
        colors=["#2166ac", "#67a9cf", "#d1e5f0", "#fddbc7", "#ef8a62", "#b2182b"],
        vmin=20,
        vmax=80,
        caption="Fiber Opportunity Score",
    )
    colormap.add_to(m)

    # Style function
    def style_function(feature):
        score = feature["properties"].get("opportunity_score", 0)
        return {
            "fillColor": colormap(score),
            "color": "#333",
            "weight": 0.3,
            "fillOpacity": 0.7,
        }

    # Tooltip fields
    tooltip_fields = [
        "GEOID",
        "StateAbbr",
        "CountyName",
        "opportunity_score",
        "TotalBSLs",
        "UniqueProvidersFiber",
        "pct_no_fiber",
    ]
    tooltip_aliases = [
        "Tract GEOID:",
        "State:",
        "County:",
        "Opportunity Score:",
        "Total BSLs:",
        "Fiber Providers:",
        "% No Fiber:",
    ]

    # Popup fields (detailed)
    popup_fields = [
        "GEOID", "StateAbbr", "CountyName",
        "opportunity_score", "score_supply_gap", "score_demand_signal",
        "score_funding_tailwind", "score_build_feasibility",
        "total_population", "TotalBSLs", "median_hh_income",
        "UniqueProviders", "UniqueProvidersFiber",
        "pct_no_fiber", "pct_unserved_underserved",
        "pct_cellular_only", "pct_no_internet",
        "rucc_code",
    ]
    popup_aliases = [
        "Tract:", "State:", "County:",
        "OPPORTUNITY SCORE:", "Supply Gap:", "Demand Signal:",
        "Funding Tailwind:", "Build Feasibility:",
        "Population:", "Total BSLs:", "Median HH Income:",
        "Total Providers:", "Fiber Providers:",
        "% No Fiber:", "% Unserved+Underserved:",
        "% Cellular Only:", "% No Internet:",
        "RUCC Code:",
    ]

    # Convert to JSON-safe format
    map_json = json.loads(map_data[
        ["geometry"] + list(set(tooltip_fields + popup_fields))
    ].to_json())

    # Add GeoJson layer
    folium.GeoJson(
        map_json,
        name="Fiber Opportunity",
        style_function=style_function,
        tooltip=GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
            sticky=True,
            style="font-size: 12px;",
        ),
        popup=GeoJsonPopup(
            fields=popup_fields,
            aliases=popup_aliases,
            localize=True,
            style="font-size: 11px; max-width: 400px;",
        ),
    ).add_to(m)

    # Add layer control
    folium.LayerControl().add_to(m)

    # Add info legend / methodology panel
    legend_html = """
    <div id="info-panel" style="
        position: fixed;
        bottom: 30px;
        left: 10px;
        width: 340px;
        max-height: 85vh;
        overflow-y: auto;
        background: white;
        border: 2px solid #666;
        border-radius: 8px;
        padding: 16px;
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 12px;
        line-height: 1.5;
        z-index: 9999;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #333;">
                Fiber Opportunity Map
            </h3>
            <button onclick="
                var p = document.getElementById('info-panel-body');
                var b = this;
                if (p.style.display === 'none') {
                    p.style.display = 'block';
                    b.textContent = '−';
                } else {
                    p.style.display = 'none';
                    b.textContent = '+';
                }
            " style="
                background: #eee; border: 1px solid #ccc; border-radius: 4px;
                cursor: pointer; font-size: 16px; width: 26px; height: 26px;
                line-height: 1;
            ">−</button>
        </div>
        <div id="info-panel-body">
            <p style="margin: 0 0 10px 0; color: #555;">
                Identifies census tracts across VA, KY, MD, PA, OH, and NY
                that are strong candidates for new fiber broadband builds.
            </p>

            <h4 style="margin: 12px 0 4px 0; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 2px;">
                Key Terms
            </h4>
            <p style="margin: 0 0 4px 0;">
                <strong>BSL</strong> (Broadband Serviceable Location) — An FCC-designated
                address (home or small business) where fixed broadband can be installed.
                The unit of measurement for broadband availability.
            </p>
            <p style="margin: 0 0 4px 0;">
                <strong>Unserved</strong> — No provider offers at least 25/3 Mbps.
            </p>
            <p style="margin: 0 0 4px 0;">
                <strong>Underserved</strong> — Service available between 25/3 and 100/20 Mbps,
                but below the modern standard.
            </p>
            <p style="margin: 0 0 4px 0;">
                <strong>RUCC</strong> — USDA Rural-Urban Continuum Code (1=large metro, 9=very rural).
            </p>

            <h4 style="margin: 12px 0 4px 0; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 2px;">
                Opportunity Score (0–100)
            </h4>
            <p style="margin: 0 0 8px 0; color: #555;">
                Composite of four weighted components:
            </p>

            <div style="margin-bottom: 6px;">
                <strong style="color: #b2182b;">Supply Gap — 40%</strong><br>
                <span style="color: #555;">
                    Few/no fiber providers, high % of BSLs without fiber,
                    heavy copper/DSL dependency, unserved + underserved concentration.
                </span>
            </div>
            <div style="margin-bottom: 6px;">
                <strong style="color: #ef8a62;">Demand Signal — 30%</strong><br>
                <span style="color: #555;">
                    Median household income, household density (BSL count),
                    cellular-only rate (want service but can't get wired),
                    adoption gap, population.
                </span>
            </div>
            <div style="margin-bottom: 6px;">
                <strong style="color: #67a9cf;">Funding Tailwind — 15%</strong><br>
                <span style="color: #555;">
                    Count and concentration of BEAD-eligible unserved and
                    underserved BSLs — federal funding potential.
                </span>
            </div>
            <div style="margin-bottom: 6px;">
                <strong style="color: #2166ac;">Build Feasibility — 15%</strong><br>
                <span style="color: #555;">
                    RUCC-based rural/suburban sweet spot scoring, BSL density
                    (not too sparse, not too urban), low existing competition.
                </span>
            </div>

            <h4 style="margin: 12px 0 4px 0; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 2px;">
                Color Scale
            </h4>
            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                <div style="width: 60px; height: 14px; background: linear-gradient(to right, #2166ac, #67a9cf, #d1e5f0, #fddbc7, #ef8a62, #b2182b); border: 1px solid #ccc; margin-right: 8px;"></div>
                <span>Low (20) → High (80)</span>
            </div>

            <h4 style="margin: 12px 0 4px 0; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 2px;">
                Data Sources
            </h4>
            <p style="margin: 0; font-size: 11px; color: #777;">
                FCC Broadband Data Collection (June 2024) •
                Census ACS 5-Year 2020–2024 •
                USDA Rural-Urban Continuum Codes 2023
            </p>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Save
    outpath = os.path.join(OUTPUT_DIR, "fiber_opportunity_map.html")
    m.save(outpath)
    file_size_mb = os.path.getsize(outpath) / (1024 * 1024)
    print(f"\nSaved map to {outpath}")
    print(f"File size: {file_size_mb:.1f} MB")

    return m


if __name__ == "__main__":
    build_map()
