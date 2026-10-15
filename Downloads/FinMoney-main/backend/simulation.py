"""
Monte Carlo personal finance simulation engine.

Core idea (same one Finlaxmi builds their product around): instead of giving
a single guessed number for "how much will I have at retirement", simulate
many possible market futures and show the *range* of outcomes.

We use the "Common Random Numbers" technique: the same simulated sequence of
annual market returns is reused across every allocation mix we compare. That
way, if allocation A looks better than allocation B, it's because A really is
better under identical conditions -- not because A got luckier draws.
"""

import numpy as np

# --- Illustrative long-run assumptions for Indian asset classes -----------
# These are simplified, illustrative figures for a demo project, not
# investment advice. A production version would calibrate these from real
# historical index data (Nifty 500 TRI, AA corporate bond indices, gold ETFs)
# and would let a user override them.
ASSET_ASSUMPTIONS = {
    "equity": {"mean": 0.12, "std": 0.20},   # broad equity / equity mutual funds
    "debt":   {"mean": 0.07, "std": 0.03},   # FDs / debt funds
    "gold":   {"mean": 0.08, "std": 0.15},   # gold ETF / SGB
}

# Three preset allocation mixes. Finlaxmi compares 11 -- we start with 3
# and it's built to extend to more (see README "Phase 2").
ALLOCATIONS = {
    "conservative": {"equity": 0.30, "debt": 0.60, "gold": 0.10},
    "balanced":     {"equity": 0.60, "debt": 0.30, "gold": 0.10},
    "aggressive":   {"equity": 0.80, "debt": 0.10, "gold": 0.10},
}

PERCENTILES = [5, 25, 50, 75, 95]
NUM_SIMULATIONS = 2000


def run_simulation(
    current_age: int,
    retirement_age: int,
    monthly_income: float,
    monthly_expenses: float,
    current_savings: float,
    monthly_sip: float,
    num_simulations: int = NUM_SIMULATIONS,
    custom_allocation: dict | None = None,
):
    """
    Runs the Monte Carlo simulation for every allocation mix using the same
    underlying random market draws (common random numbers), and returns:
      - a year-by-year percentile "band" for each allocation (for a fan chart)
      - the final corpus percentiles at retirement, for each allocation
      - a simple monthly surplus/deficit check on the inputs given

    If `custom_allocation` is given (a dict with "equity"/"debt"/"gold"
    weights summing to 1), it is run through the SAME simulated market
    draws as the presets and included in the results as "custom" -- so a
    user-defined mix is directly comparable to conservative/balanced/
    aggressive, not just eyeballed against them.
    """
    num_years = max(retirement_age - current_age, 1)
    annual_contribution = max(monthly_sip, 0) * 12

    rng = np.random.default_rng()

    # Draw ONE set of annual returns per asset class, shared across every
    # allocation mix -- this is what makes the comparison across allocations
    # fair (common random numbers).
    equity_returns = rng.normal(
        ASSET_ASSUMPTIONS["equity"]["mean"],
        ASSET_ASSUMPTIONS["equity"]["std"],
        size=(num_simulations, num_years),
    )
    debt_returns = rng.normal(
        ASSET_ASSUMPTIONS["debt"]["mean"],
        ASSET_ASSUMPTIONS["debt"]["std"],
        size=(num_simulations, num_years),
    )
    gold_returns = rng.normal(
        ASSET_ASSUMPTIONS["gold"]["mean"],
        ASSET_ASSUMPTIONS["gold"]["std"],
        size=(num_simulations, num_years),
    )

    results = {}

    allocations_to_run = dict(ALLOCATIONS)
    if custom_allocation:
        allocations_to_run["custom"] = custom_allocation

    for name, weights in allocations_to_run.items():
        blended_returns = (
            weights["equity"] * equity_returns
            + weights["debt"] * debt_returns
            + weights["gold"] * gold_returns
        )  # shape: (num_simulations, num_years)

        # Track portfolio value at the START of each year (year 0 = today),
        # so we can plot a full path, not just the final number.
        path = np.zeros((num_simulations, num_years + 1))
        path[:, 0] = current_savings

        v = np.full(num_simulations, float(current_savings))
        for year in range(num_years):
            v = v * (1 + blended_returns[:, year]) + annual_contribution
            path[:, year + 1] = v

        path_percentiles = {
            f"p{p}": np.percentile(path, p, axis=0).round(0).tolist()
            for p in PERCENTILES
        }
        final_percentiles = {
            f"p{p}": round(float(np.percentile(v, p)), 0) for p in PERCENTILES
        }

        results[name] = {
            "weights": weights,
            "path_percentiles": path_percentiles,
            "final_corpus_percentiles": final_percentiles,
        }

    monthly_surplus = round(monthly_income - monthly_expenses - monthly_sip, 0)

    return {
        "years": list(range(current_age, current_age + num_years + 1)),
        "num_simulations": num_simulations,
        "monthly_surplus": monthly_surplus,
        "allocations": results,
    }


def run_lever_analysis(
    current_age: int,
    retirement_age: int,
    current_savings: float,
    base_monthly_sip: float,
    allocation_name: str = "balanced",
    extra_steps=(0, 5000, 10000, 20000, 40000),
):
    """
    Answers the 'one lever' question: how does the median outcome change as
    we add extra monthly investment on top of the base SIP, holding the
    market path fixed (common random numbers again) so the comparison across
    steps is apples-to-apples.
    """
    num_years = max(retirement_age - current_age, 1)
    weights = ALLOCATIONS[allocation_name]

    rng = np.random.default_rng(42)  # fixed seed: same market path per step
    equity_returns = rng.normal(
        ASSET_ASSUMPTIONS["equity"]["mean"], ASSET_ASSUMPTIONS["equity"]["std"],
        size=(NUM_SIMULATIONS, num_years),
    )
    debt_returns = rng.normal(
        ASSET_ASSUMPTIONS["debt"]["mean"], ASSET_ASSUMPTIONS["debt"]["std"],
        size=(NUM_SIMULATIONS, num_years),
    )
    gold_returns = rng.normal(
        ASSET_ASSUMPTIONS["gold"]["mean"], ASSET_ASSUMPTIONS["gold"]["std"],
        size=(NUM_SIMULATIONS, num_years),
    )
    blended_returns = (
        weights["equity"] * equity_returns
        + weights["debt"] * debt_returns
        + weights["gold"] * gold_returns
    )

    points = []
    for extra in extra_steps:
        annual_contribution = (base_monthly_sip + extra) * 12
        v = np.full(NUM_SIMULATIONS, float(current_savings))
        for year in range(num_years):
            v = v * (1 + blended_returns[:, year]) + annual_contribution
        points.append({
            "extra_monthly": extra,
            "median_final_corpus": round(float(np.percentile(v, 50)), 0),
        })

    return {"allocation": allocation_name, "points": points}
