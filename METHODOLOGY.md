# Scoring Methodology — Fiber Opportunity Model

## Approach

The model scores each census tract on a 0–100 scale representing how attractive it is for a greenfield fiber broadband deployment. The score is a weighted composite of four dimensions, each capturing a different aspect of market opportunity.

All component scores are computed using **percentile ranking** within the dataset. This means a score of 75 indicates the tract ranks in the 75th percentile for that metric relative to all other tracts in the six-state study area. This approach normalizes across metrics with very different scales (dollar amounts, percentages, counts) without imposing arbitrary thresholds.

## Component Details

### 1. Supply Gap (40% weight)

Measures the absence of existing fiber infrastructure — the core opportunity signal.

| Metric | Weight | Direction | Rationale |
|--------|--------|-----------|-----------|
| Fiber provider count | 30% | Fewer = higher | Zero fiber providers means no incumbent to compete with |
| % BSLs without fiber service | 25% | Higher = higher | Large fiber gap = large addressable market |
| % BSLs unserved + underserved | 20% | Higher = higher | Regulatory and funding priority areas |
| % BSLs served by copper | 15% | Higher = higher | Aging DSL/copper = customers ready to switch |
| Total provider count (all tech) | 10% | Fewer = higher | Less competition across all technologies |

### 2. Demand Signal (30% weight)

Measures whether residents will subscribe to fiber service if it becomes available.

| Metric | Weight | Direction | Rationale |
|--------|--------|-----------|-----------|
| Median household income | 30% | Higher = higher | Ability to pay for service (~$60–80/mo). A penalty factor of 0.5x is applied to tracts below $30K median income. |
| Total BSLs (household density) | 25% | More = higher | More potential subscribers per mile of fiber |
| Cellular-only internet rate | 20% | Higher = higher | These households want connectivity but lack wired options — immediate conversion candidates |
| Adoption gap (availability – subscription) | 15% | Higher = higher | Broadband exists but people aren't subscribing — may indicate price/quality issues solvable by a new entrant |
| Total population | 10% | Higher = higher | Larger addressable market |

### 3. Funding Tailwind (15% weight)

Measures eligibility for BEAD (Broadband Equity, Access, and Deployment) federal funding, which subsidizes builds in unserved/underserved areas.

| Metric | Weight | Direction | Rationale |
|--------|--------|-----------|-----------|
| Unserved BSL count | 30% | More = higher | BEAD's primary funding target (< 25/3 Mbps) |
| % BSLs unserved | 30% | Higher = higher | Concentrated unserved areas are more fundable |
| Underserved BSL count | 20% | More = higher | BEAD's secondary funding target (25/3 to 100/20 Mbps) |
| % BSLs unserved + underserved | 20% | Higher = higher | Overall funding eligibility concentration |

### 4. Build Feasibility (15% weight)

Estimates whether a profitable fiber network can be constructed based on density and market structure.

| Metric | Weight | Direction | Rationale |
|--------|--------|-----------|-----------|
| RUCC sweet spot score | 40% | See table | Suburban/small-town areas balance density with lack of competition |
| BSL density percentile band | 35% | See table | Too sparse = unprofitable; too dense = incumbents dominate |
| Total provider count | 25% | Fewer = higher | Easier market entry with less competition |

**RUCC Score Mapping:**

| RUCC Code | Description | Score | Rationale |
|-----------|-------------|-------|-----------|
| 1 | Metro, 1M+ pop | 20 | Incumbent-dominated (Comcast, Verizon FiOS, etc.) |
| 2 | Metro, 250K–1M | 35 | Still competitive |
| 3 | Metro, <250K | 55 | Some opportunity, smaller incumbents |
| 4 | Nonmetro, 20K+ pop, adjacent to metro | 85 | Sweet spot — density + underservice |
| 5 | Nonmetro, 20K+ pop, not adjacent | 75 | Good opportunity |
| 6 | Nonmetro, 5K–20K pop, adjacent to metro | 90 | Best sweet spot — reachable, underserved |
| 7 | Nonmetro, 5K–20K pop, not adjacent | 70 | Decent but more isolated |
| 8 | Nonmetro, <5K pop, adjacent to metro | 60 | Getting sparse |
| 9 | Nonmetro, <5K pop, not adjacent | 40 | Very rural, high per-BSL cost |

**BSL Density Bands:**

| Percentile Range | Score | Rationale |
|-----------------|-------|-----------|
| < 10th | 20 | Very sparse — high cost per passing |
| 10th – 30th | 50 | Sparse but potentially viable |
| 30th – 70th | 85 | Sweet spot — moderate density |
| 70th – 90th | 60 | Dense — some incumbent presence |
| > 90th | 30 | Very dense — urban core, well-served |

## Final Score Composition

```
Opportunity Score = (Supply Gap × 0.40) + (Demand Signal × 0.30)
                  + (Funding Tailwind × 0.15) + (Build Feasibility × 0.15)
```

## Tier Classification

| Tier | Score Range | Tracts |
|------|------------|--------|
| Very High | 80–100 | 1 |
| High | 65–80 | 1,535 |
| Moderate | 50–65 | 6,137 |
| Below Average | 30–50 | 8,577 |
| Low | 0–30 | 461 |

## What This Model Does NOT Capture

- **Construction cost estimates** — terrain, rock, permitting, pole attachment fees, make-ready
- **State-level regulatory environment** — right-of-way access, permitting timelines, one-touch make-ready rules
- **BEAD program timeline by state** — application windows, subgrantee selection status
- **Incumbent response risk** — likelihood of competitive overbuild by existing providers
- **Political and community factors** — local government broadband-friendliness, community anchor institutions
- **Existing grant awards** — areas already funded by VATI, ReConnect, CAF II, or other programs
