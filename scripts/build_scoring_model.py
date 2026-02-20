"""
Fiber Opportunity Scoring Model

Merges FCC BDC, Census ACS, and USDA RUCC data at the tract level.
Scores each tract on how ripe it is for a new fiber build.

Score components (0-100 each, weighted):
1. Supply Gap (40%) — No/few fiber providers, heavy DSL/copper, unserved/underserved BSLs
2. Demand Signal (30%) — Income, household density, cellular-only rate, adoption gap
3. Funding Tailwind (15%) — BEAD-eligible unserved/underserved concentrations
4. Build Feasibility (15%) — Density sweet spot, not too rural, not too urban

Final score = weighted composite, 0-100.
"""

import pandas as pd
import numpy as np
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROC_DIR = os.path.join(DATA_DIR, "processed")


def load_and_merge():
    """Load all three datasets and merge on tract GEOID."""
    # ACS data
    acs = pd.read_csv(os.path.join(RAW_DIR, "acs_2024_tracts_6states.csv"), dtype={"GEOID": str})
    print(f"ACS: {len(acs)} tracts")

    # FCC BDC data
    fcc = pd.read_csv(os.path.join(RAW_DIR, "fcc_bdc_tracts_6states.csv"), dtype={"GEOID": str})
    print(f"FCC: {len(fcc)} tracts")

    # RUCC data (county level — join via county GEOID)
    rucc = pd.read_csv(os.path.join(RAW_DIR, "rucc_2023_6states.csv"))
    rucc["county_geoid"] = rucc["FIPS"].astype(str).str.zfill(5)
    rucc = rucc[["county_geoid", "RUCC_2023", "Population_2020", "Description"]].copy()
    rucc.columns = ["county_geoid", "rucc_code", "county_pop_2020", "rucc_description"]
    print(f"RUCC: {len(rucc)} counties")

    # Merge ACS + FCC on GEOID
    merged = acs.merge(fcc, on="GEOID", how="inner", suffixes=("_acs", "_fcc"))
    print(f"After ACS+FCC merge: {len(merged)} tracts")

    # Add county GEOID for RUCC join (first 5 chars of tract GEOID)
    merged["county_geoid"] = merged["GEOID"].str[:5]

    # Merge RUCC
    merged = merged.merge(rucc, on="county_geoid", how="left")
    print(f"After RUCC merge: {len(merged)} tracts")

    # Filter out zero-population / zero-household tracts
    merged = merged[
        (merged["total_population"] > 0) & (merged["hh_total"] > 0) & (merged["TotalBSLs"] > 0)
    ].copy()
    print(f"After filtering zero-pop/hh/BSL tracts: {len(merged)} tracts")

    # Clean Census NA codes
    merged["median_hh_income"] = merged["median_hh_income"].replace(-666666666, np.nan)

    return merged


def compute_derived_metrics(df):
    """Compute derived metrics needed for scoring."""
    # --- Supply side (FCC) ---
    df["pct_unserved"] = df["UnservedBSLs"] / df["TotalBSLs"] * 100
    df["pct_underserved"] = df["UnderservedBSLs"] / df["TotalBSLs"] * 100
    df["pct_unserved_underserved"] = (df["UnservedBSLs"] + df["UnderservedBSLs"]) / df["TotalBSLs"] * 100
    df["pct_fiber_unserved"] = df["UnservedBSLsFiber"] / df["TotalBSLs"] * 100
    df["pct_no_fiber"] = (df["TotalBSLs"] - df["ServedBSLsFiber"]) / df["TotalBSLs"] * 100
    df["pct_copper_served"] = df["ServedBSLsCopper"] / df["TotalBSLs"] * 100
    df["has_fiber"] = (df["UniqueProvidersFiber"] > 0).astype(int)

    # --- Demand side (ACS) ---
    df["pct_no_internet"] = df["hh_no_internet"] / df["hh_total"] * 100
    df["pct_cellular_only"] = df["hh_cellular_only"] / df["hh_total"] * 100
    df["pct_broadband"] = df["hh_broadband_any"] / df["hh_total"] * 100
    df["pct_cable_fiber_dsl"] = df["hh_cable_fiber_dsl"] / df["hh_total"] * 100

    # Adoption gap: broadband is available but people aren't subscribing
    # (served BSLs as % of total) - (% of households with broadband)
    df["pct_served"] = df["ServedBSLs"] / df["TotalBSLs"] * 100
    df["adoption_gap"] = df["pct_served"] - df["pct_broadband"]

    # Education
    df["pct_bachelors_plus"] = (
        (df["edu_bachelors"] + df["edu_masters"] + df["edu_professional"] + df["edu_doctorate"])
        / df["edu_total_25plus"].replace(0, np.nan)
        * 100
    )

    # Employment
    df["unemployment_rate"] = (
        df["emp_unemployed"] / df["emp_civilian_labor"].replace(0, np.nan) * 100
    )

    # Demographics
    df["pct_minority"] = (
        (df["race_total"] - df["race_nh_white"]) / df["race_total"].replace(0, np.nan) * 100
    )

    # Density — households per BSL (proxy for housing density)
    df["hh_per_bsl"] = df["hh_total"] / df["TotalBSLs"]

    # No computer
    df["pct_no_computer"] = df["comp_no_computer"] / df["comp_total_hh"].replace(0, np.nan) * 100

    return df


def percentile_score(series, ascending=True):
    """Convert a series to 0-100 percentile scores.
    ascending=True means higher values get higher scores.
    ascending=False means lower values get higher scores (inverted).
    """
    ranks = series.rank(pct=True, na_option="bottom")
    if not ascending:
        ranks = 1 - ranks
    return ranks * 100


def score_supply_gap(df):
    """
    Supply Gap Score (0-100): How much room is there for fiber?
    Higher = more opportunity (less fiber, more unserved, more copper dependency).
    """
    # No fiber providers = big opportunity
    s1 = percentile_score(df["UniqueProvidersFiber"], ascending=False)

    # High % of BSLs without fiber service
    s2 = percentile_score(df["pct_no_fiber"], ascending=True)

    # High % unserved + underserved
    s3 = percentile_score(df["pct_unserved_underserved"], ascending=True)

    # Heavy copper/DSL dependency (aging infrastructure)
    s4 = percentile_score(df["pct_copper_served"], ascending=True)

    # Few total providers (less competition)
    s5 = percentile_score(df["UniqueProviders"], ascending=False)

    # Weighted combination
    supply_score = (s1 * 0.30 + s2 * 0.25 + s3 * 0.20 + s4 * 0.15 + s5 * 0.10)
    return supply_score


def score_demand_signal(df):
    """
    Demand Signal Score (0-100): Will people buy fiber if you build it?
    Higher = stronger demand signals.
    """
    # Income — need enough to afford $60-80/mo service
    # Sweet spot is middle-to-upper income, not too low (can't afford), not too high (already served)
    # Use percentile but cap the very low end
    income_filled = df["median_hh_income"].fillna(df["median_hh_income"].median())
    s1 = percentile_score(income_filled, ascending=True)
    # Penalize very low income (below $30k) — harder to sustain subscriptions
    low_income_penalty = np.where(income_filled < 30000, 0.5, 1.0)
    s1 = s1 * low_income_penalty

    # Household density — enough rooftops (BSLs) to justify the build
    s2 = percentile_score(df["TotalBSLs"], ascending=True)

    # Cellular-only rate — people WANT internet but can't get wired service
    s3 = percentile_score(df["pct_cellular_only"], ascending=True)

    # Adoption gap — broadband exists but people aren't on it (marketing opportunity)
    s4 = percentile_score(df["adoption_gap"].clip(lower=0), ascending=True)

    # Population
    s5 = percentile_score(df["total_population"], ascending=True)

    demand_score = (s1 * 0.30 + s2 * 0.25 + s3 * 0.20 + s4 * 0.15 + s5 * 0.10)
    return demand_score


def score_funding_tailwind(df):
    """
    Funding Tailwind Score (0-100): Is there BEAD money available?
    Higher = more BEAD-eligible locations (unserved/underserved).
    """
    # Raw count of unserved BSLs (BEAD targets these first)
    s1 = percentile_score(df["UnservedBSLs"], ascending=True)

    # Unserved as % of total (concentration)
    s2 = percentile_score(df["pct_unserved"], ascending=True)

    # Underserved count (BEAD second priority)
    s3 = percentile_score(df["UnderservedBSLs"], ascending=True)

    # Combined unserved + underserved percentage
    s4 = percentile_score(df["pct_unserved_underserved"], ascending=True)

    funding_score = (s1 * 0.30 + s2 * 0.30 + s3 * 0.20 + s4 * 0.20)
    return funding_score


def score_build_feasibility(df):
    """
    Build Feasibility Score (0-100): Can you actually build here profitably?
    Sweet spot: not too sparse (unprofitable), not too dense (incumbents own it).

    RUCC codes:
    1-3 = Metro (dense, competitive — lower score)
    4-6 = Suburban/small town (sweet spot — higher score)
    7-9 = Very rural (sparse, expensive — moderate score)
    """
    # RUCC sweet spot scoring
    rucc_map = {
        1: 20,   # Big metro — Comcast/Verizon territory
        2: 35,   # Medium metro — still competitive
        3: 55,   # Small metro — some opportunity
        4: 85,   # Adjacent to metro, 20k+ pop — sweet spot
        5: 75,   # Not adjacent, 20k+ pop — good
        6: 90,   # Adjacent to metro, 5-20k pop — best sweet spot
        7: 70,   # Not adjacent, 5-20k pop — decent
        8: 60,   # Adjacent, <5k pop — getting sparse
        9: 40,   # Not adjacent, <5k pop — very rural, expensive
    }
    s1 = df["rucc_code"].map(rucc_map).fillna(50)

    # BSL density — sweet spot is moderate
    # Too few BSLs = unprofitable, too many = already served
    bsl_count = df["TotalBSLs"]
    # Score peaks around the 40th-70th percentile
    bsl_pctile = bsl_count.rank(pct=True)
    s2 = np.where(
        bsl_pctile < 0.1, 20,       # Very sparse
        np.where(
            bsl_pctile < 0.3, 50,    # Sparse
            np.where(
                bsl_pctile < 0.7, 85, # Sweet spot
                np.where(
                    bsl_pctile < 0.9, 60,  # Dense
                    30                      # Very dense (urban core)
                )
            )
        )
    )

    # Fewer existing providers = easier market entry
    s3 = percentile_score(df["UniqueProviders"], ascending=False)

    feasibility_score = (s1 * 0.40 + s2 * 0.35 + s3 * 0.25)
    return feasibility_score


def build_composite_score(df):
    """Build the final composite opportunity score."""
    df["score_supply_gap"] = score_supply_gap(df)
    df["score_demand_signal"] = score_demand_signal(df)
    df["score_funding_tailwind"] = score_funding_tailwind(df)
    df["score_build_feasibility"] = score_build_feasibility(df)

    # Weighted composite
    df["opportunity_score"] = (
        df["score_supply_gap"] * 0.40
        + df["score_demand_signal"] * 0.30
        + df["score_funding_tailwind"] * 0.15
        + df["score_build_feasibility"] * 0.15
    )

    # Rank
    df["opportunity_rank"] = df["opportunity_score"].rank(ascending=False).astype(int)

    # Tier labels
    df["opportunity_tier"] = pd.cut(
        df["opportunity_score"],
        bins=[0, 30, 50, 65, 80, 100],
        labels=["Low", "Below Average", "Moderate", "High", "Very High"],
    )

    return df


def main():
    os.makedirs(PROC_DIR, exist_ok=True)

    print("=" * 60)
    print("FIBER OPPORTUNITY SCORING MODEL")
    print("=" * 60)

    # Load and merge
    print("\n--- Loading data ---")
    df = load_and_merge()

    # Compute derived metrics
    print("\n--- Computing derived metrics ---")
    df = compute_derived_metrics(df)

    # Build scores
    print("\n--- Building composite scores ---")
    df = build_composite_score(df)

    # Summary stats
    print("\n--- Results Summary ---")
    print(f"Total scored tracts: {len(df)}")
    print(f"\nOpportunity Score Distribution:")
    print(df["opportunity_score"].describe().round(1))
    print(f"\nTier Counts:")
    print(df["opportunity_tier"].value_counts().sort_index())
    print(f"\nTier Counts by State:")
    tier_by_state = df.groupby(["StateAbbr", "opportunity_tier"]).size().unstack(fill_value=0)
    print(tier_by_state)

    # Top 20 tracts
    print(f"\n--- Top 20 Opportunity Tracts ---")
    top20 = df.nlargest(20, "opportunity_score")[
        [
            "GEOID", "StateAbbr", "CountyName",
            "total_population", "TotalBSLs", "median_hh_income",
            "UniqueProvidersFiber", "pct_no_fiber",
            "pct_unserved_underserved", "pct_cellular_only",
            "rucc_code", "opportunity_score", "opportunity_rank",
        ]
    ]
    for _, row in top20.iterrows():
        print(
            f"  #{row['opportunity_rank']:>5d} | {row['StateAbbr']} {row['CountyName']:>25s} | "
            f"Pop {row['total_population']:>6,.0f} | BSLs {row['TotalBSLs']:>5,d} | "
            f"Income ${row['median_hh_income']:>7,.0f} | Fiber provs {row['UniqueProvidersFiber']:>2.0f} | "
            f"No fiber {row['pct_no_fiber']:>5.1f}% | Unsrv+Undrsrv {row['pct_unserved_underserved']:>5.1f}% | "
            f"Score {row['opportunity_score']:.1f}"
        )

    # Top counties (aggregate)
    print(f"\n--- Top 20 Opportunity Counties (avg tract score) ---")
    county_scores = (
        df.groupby(["StateAbbr", "CountyName", "county_geoid", "rucc_code"])
        .agg(
            avg_score=("opportunity_score", "mean"),
            max_score=("opportunity_score", "max"),
            tract_count=("GEOID", "count"),
            total_bsls=("TotalBSLs", "sum"),
            total_unserved=("UnservedBSLs", "sum"),
            avg_income=("median_hh_income", "mean"),
            avg_no_fiber_pct=("pct_no_fiber", "mean"),
        )
        .reset_index()
        .sort_values("avg_score", ascending=False)
    )
    for _, row in county_scores.head(20).iterrows():
        print(
            f"  {row['StateAbbr']} {row['CountyName']:>25s} (RUCC {row['rucc_code']:.0f}) | "
            f"Tracts {row['tract_count']:>3d} | BSLs {row['total_bsls']:>7,d} | "
            f"Unserved {row['total_unserved']:>5,d} | "
            f"Avg income ${row['avg_income']:>7,.0f} | "
            f"No fiber {row['avg_no_fiber_pct']:>5.1f}% | "
            f"Avg score {row['avg_score']:.1f}"
        )

    # Save scored data
    outpath = os.path.join(PROC_DIR, "tract_scores.csv")
    df.to_csv(outpath, index=False)
    print(f"\nSaved tract scores to {outpath}")

    county_outpath = os.path.join(PROC_DIR, "county_scores.csv")
    county_scores.to_csv(county_outpath, index=False)
    print(f"Saved county scores to {county_outpath}")

    return df, county_scores


if __name__ == "__main__":
    main()
