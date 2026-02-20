"""
Pull Census ACS 2020-2024 5-year data for fiber opportunity scoring model.
Six states: VA, KY, MD, PA, OH, NY
Tract-level data for: broadband subscriptions, income, education, employment,
race/ethnicity, population/housing density.
"""

import requests
import pandas as pd
import time
import json
import os

BASE_URL = "https://api.census.gov/data/2024/acs/acs5"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")

# State FIPS codes
STATES = {
    "VA": "51",
    "KY": "21",
    "MD": "24",
    "PA": "42",
    "OH": "39",
    "NY": "36",
}

# Variables to pull — grouped by topic
# Each tuple: (variable_code, friendly_name)
VARIABLES = {
    # Internet subscriptions (B28002)
    "B28002_001E": "hh_total",           # Total households
    "B28002_002E": "hh_internet_sub",    # With an Internet subscription
    "B28002_004E": "hh_broadband_any",   # Broadband of any type
    "B28002_006E": "hh_cellular_only",   # Cellular data plan with no other type
    "B28002_007E": "hh_cable_fiber_dsl", # Cable, fiber optic, or DSL
    "B28002_012E": "hh_internet_nosub",  # Internet access without subscription
    "B28002_013E": "hh_no_internet",     # No Internet access

    # Income (B19013)
    "B19013_001E": "median_hh_income",

    # Education — population 25+ (B15003)
    "B15003_001E": "edu_total_25plus",
    "B15003_017E": "edu_hs_diploma",
    "B15003_022E": "edu_bachelors",
    "B15003_023E": "edu_masters",
    "B15003_024E": "edu_professional",
    "B15003_025E": "edu_doctorate",

    # Employment (B23025)
    "B23025_001E": "emp_total_16plus",
    "B23025_003E": "emp_civilian_labor",
    "B23025_005E": "emp_unemployed",

    # Race/Ethnicity (B03002) — Hispanic origin by race
    "B03002_001E": "race_total",
    "B03002_003E": "race_nh_white",
    "B03002_004E": "race_nh_black",
    "B03002_006E": "race_nh_asian",
    "B03002_012E": "race_hispanic",

    # Total population and housing units
    "B01003_001E": "total_population",
    "B25001_001E": "total_housing_units",

    # Median age
    "B01002_001E": "median_age",

    # Computer ownership (B28001)
    "B28001_001E": "comp_total_hh",
    "B28001_011E": "comp_no_computer",
}


def pull_state_tracts(state_abbr, state_fips):
    """Pull all variables for all tracts in a state."""
    var_codes = list(VARIABLES.keys())

    # Census API limit is ~50 variables per request — we're under that
    var_string = ",".join(var_codes)

    params = {
        "get": f"NAME,{var_string}",
        "for": "tract:*",
        "in": f"state:{state_fips}",
    }

    r = requests.get(BASE_URL, params=params)

    if r.status_code != 200:
        print(f"  ERROR {state_abbr}: {r.status_code} - {r.text[:200]}")
        return None

    data = r.json()
    header = data[0]
    rows = data[1:]

    df = pd.DataFrame(rows, columns=header)

    # Build GEOID from state + county + tract
    df["GEOID"] = df["state"] + df["county"] + df["tract"]
    df["state_abbr"] = state_abbr

    # Convert numeric columns
    for var_code in var_codes:
        df[var_code] = pd.to_numeric(df[var_code], errors="coerce")

    # Rename to friendly names
    df = df.rename(columns=VARIABLES)

    return df


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_dfs = []

    for state_abbr, state_fips in STATES.items():
        print(f"Pulling {state_abbr} (FIPS {state_fips})...")
        df = pull_state_tracts(state_abbr, state_fips)

        if df is not None:
            print(f"  {len(df)} tracts")
            all_dfs.append(df)

        time.sleep(0.5)  # Be nice to the API

    # Combine all states
    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal tracts: {len(combined)}")
    print(f"By state:")
    print(combined["state_abbr"].value_counts().sort_index())

    # Save
    outpath = os.path.join(OUTPUT_DIR, "acs_2024_tracts_6states.csv")
    combined.to_csv(outpath, index=False)
    print(f"\nSaved to {outpath}")

    # Quick sanity check
    print(f"\nSanity check:")
    print(f"  Median HH income range: ${combined['median_hh_income'].min():,.0f} - ${combined['median_hh_income'].max():,.0f}")
    print(f"  Tracts with no internet data: {combined['hh_total'].isna().sum()}")
    print(f"  Total population: {combined['total_population'].sum():,.0f}")

    return combined


if __name__ == "__main__":
    main()
