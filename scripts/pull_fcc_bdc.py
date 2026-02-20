"""
Pull FCC Broadband Data Collection (BDC) tract-level data from ArcGIS Feature Service.
June 2024 filing — the latest available on ArcGIS Living Atlas.

Layer 2 = Tracts (summary: served/underserved/unserved BSLs by technology, provider counts)
Layer 9 = BDC Records for Tracts (per-provider detail)

We only need Layer 2 for the scoring model.
"""

import requests
import pandas as pd
import time
import os

BASE_URL = (
    "https://services.arcgis.com/jIL9msH9OI208GCb/arcgis/rest/services/"
    "FCC_Broadband_Data_Collection_June_2022/FeatureServer/2/query"
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")

# State FIPS codes — used to filter by GEOID prefix
STATES = {
    "VA": "51",
    "KY": "21",
    "MD": "24",
    "PA": "42",
    "OH": "39",
    "NY": "36",
}

# Fields we want
FIELDS = [
    "GEOID",
    "CountyName",
    "StateName",
    "StateAbbr",
    "CountyGEOID",
    "TotalPop",
    "TotalBSLs",
    "UnservedBSLs",
    "UnderservedBSLs",
    "ServedBSLs",
    # By technology
    "UnservedBSLsCopper",
    "UnderservedBSLsCopper",
    "ServedBSLsCopper",
    "UnservedBSLsCable",
    "UnderservedBSLsCable",
    "ServedBSLsCable",
    "UnservedBSLsFiber",
    "UnderservedBSLsFiber",
    "ServedBSLsFiber",
    "UnservedBSLsLTFW",
    "UnderservedBSLsLTFW",
    "ServedBSLsLTFW",
    # Trend data
    "UnservedBSLs_12monthPrevious",
    "ServedBSLs_12monthPrevious",
    "ServedBSLsFiber_12monthPrevious",
    # Provider counts
    "UniqueProviders",
    "UniqueProvidersCopper",
    "UniqueProvidersCable",
    "UniqueProvidersFiber",
    "UniqueProvidersLTFW",
]


def pull_state_tracts(state_abbr, state_fips):
    """Pull all tracts for a state from the ArcGIS Feature Service."""
    all_features = []
    offset = 0
    batch_size = 2000  # max records per request

    while True:
        params = {
            "where": f"StateAbbr='{state_abbr}'",
            "outFields": ",".join(FIELDS),
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
        }

        r = requests.get(BASE_URL, params=params, timeout=30)

        if r.status_code != 200:
            print(f"  ERROR: HTTP {r.status_code}")
            break

        data = r.json()

        if "error" in data:
            print(f"  ERROR: {data['error']}")
            break

        features = data.get("features", [])
        if not features:
            break

        all_features.extend([f["attributes"] for f in features])
        offset += len(features)

        # Check if we got all records
        if len(features) < batch_size:
            break

        time.sleep(0.3)

    if all_features:
        return pd.DataFrame(all_features)
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_dfs = []

    for state_abbr, state_fips in STATES.items():
        print(f"Pulling {state_abbr}...")
        df = pull_state_tracts(state_abbr, state_fips)

        if df is not None:
            print(f"  {len(df)} tracts")
            all_dfs.append(df)
        else:
            print(f"  FAILED")

        time.sleep(0.5)

    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal tracts: {len(combined)}")
    print(f"By state:")
    print(combined["StateAbbr"].value_counts().sort_index())

    # Quick stats
    print(f"\nTotal BSLs: {combined['TotalBSLs'].sum():,.0f}")
    print(f"Unserved BSLs: {combined['UnservedBSLs'].sum():,.0f}")
    print(f"Underserved BSLs: {combined['UnderservedBSLs'].sum():,.0f}")
    print(f"Served BSLs: {combined['ServedBSLs'].sum():,.0f}")
    print(f"\nFiber served BSLs: {combined['ServedBSLsFiber'].sum():,.0f}")
    print(f"Fiber unserved BSLs: {combined['UnservedBSLsFiber'].sum():,.0f}")
    print(f"Tracts with zero fiber providers: {(combined['UniqueProvidersFiber'] == 0).sum()}")

    outpath = os.path.join(OUTPUT_DIR, "fcc_bdc_tracts_6states.csv")
    combined.to_csv(outpath, index=False)
    print(f"\nSaved to {outpath}")

    return combined


if __name__ == "__main__":
    main()
