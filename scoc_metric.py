# Stress-Tested Cash-on-Cash (sCoC) metric for AU residential investors
# - Reusable calculator (compute_scoc)
# - Demo dataset 



import math
import pandas as pd
import numpy as np
from pathlib import Path

# Optional plotting (comment out if you don't want charts)
import matplotlib.pyplot as plt

# ------------------
# Assumptions (tweak as needed)
# ------------------
DEFAULTS = {
    "vacancy_weeks": 4,          # assume 4 weeks vacancy p.a.
    "maintenance_rate": 0.05,    # 5% of gross rent
    "capex_rate": 0.01,          # 1% of purchase price (annual reserve)
    "purchase_cost_rate": 0.05,  # 5% of price for stamp duty, legals, LMI, etc. (rough)
    "lvr": 0.80,                 # 80% loan-to-value
    "loan_term_years": 30,       # 30-year P&I
    "stress_bps": 200            # +2.00% interest rate stress
}

# ------------------
# Amortisation helper
# ------------------
def annual_pni(loan_amount: float, annual_rate: float, years: int) -> float:
    """Return annual principal+interest repayment for a standard amortising loan."""
    if annual_rate <= 0:
        return loan_amount / years  # edge case
    r = annual_rate / 12
    n = years * 12
    payment = loan_amount * (r * (1 + r)**n) / ((1 + r)**n - 1)
    return payment * 12  # annualise

# ------------------
# Core calculator: Stress-Tested Cash-on-Cash (sCoC)
# ------------------
def compute_scoc(df: pd.DataFrame, defaults=DEFAULTS) -> pd.DataFrame:
    df = df.copy()

    # Required fields
    df["price"] = df["price"].astype(float)
    df["weekly_rent"] = df["weekly_rent"].astype(float)

    # Optional cost columns with safe defaults
    for col in ["council_rates", "strata_body_corp", "insurance", "land_tax", "other_costs"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0).astype(float)

    # Financing inputs
    if "current_interest_rate" not in df.columns:
        df["current_interest_rate"] = 0.065  # 6.5% default
    df["current_interest_rate"] = df["current_interest_rate"].astype(float)

    if "lvr" not in df.columns:
        df["lvr"] = defaults["lvr"]
    df["lvr"] = df["lvr"].astype(float)

    if "loan_term_years" not in df.columns:
        df["loan_term_years"] = defaults["loan_term_years"]
    df["loan_term_years"] = df["loan_term_years"].astype(int)

    # Income & costs
    df["annual_rent"] = df["weekly_rent"] * 52.0
    df["vacancy_loss"] = df["weekly_rent"] * defaults["vacancy_weeks"]
    df["maintenance"] = defaults["maintenance_rate"] * df["annual_rent"]
    df["capex_reserve"] = defaults["capex_rate"] * df["price"]

    df["operating_costs"] = (
        df["council_rates"]
        + df["strata_body_corp"]
        + df["insurance"]
        + df["land_tax"]
        + df["other_costs"]
        + df["maintenance"]
        + df["capex_reserve"]
    )

    df["NOI"] = df["annual_rent"] - df["vacancy_loss"] - df["operating_costs"]

    # Financing & stress
    df["loan_amount"] = df["price"] * df["lvr"]
    df["equity"] = df["price"] * (1 - df["lvr"]) + df["price"] * defaults["purchase_cost_rate"]
    df["stress_rate"] = df["current_interest_rate"] + defaults["stress_bps"] / 10000.0

    df["annual_debt_service_stress"] = df.apply(
        lambda r: annual_pni(r["loan_amount"], r["stress_rate"], int(r["loan_term_years"])),
        axis=1
    )

    df["cashflow_after_debt_stress"] = df["NOI"] - df["annual_debt_service_stress"]
    df["sCoC_percent"] = 100.0 * (df["cashflow_after_debt_stress"] / df["equity"])

    # Context metrics
    df["gross_yield_percent"] = 100.0 * (df["annual_rent"] / df["price"])
    df["net_yield_percent"] = 100.0 * (df["NOI"] / df["price"])
    df["DSCR_stress"] = df["NOI"] / df["annual_debt_service_stress"]

    # Simple signal
    def label(row):
        if row["sCoC_percent"] >= 2.0 and row["DSCR_stress"] >= 1.10:
            return "BUY (resilient)"
        if row["sCoC_percent"] >= 0.0 and row["DSCR_stress"] >= 1.0:
            return "WATCH (thin buffer)"
        return "AVOID (negative under stress)"
    df["signal"] = df.apply(label, axis=1)

    # Tidy order
    order = [
        "address", "price", "weekly_rent",
        "gross_yield_percent", "net_yield_percent",
        "NOI", "loan_amount", "equity",
        "stress_rate", "annual_debt_service_stress",
        "cashflow_after_debt_stress", "sCoC_percent",
        "DSCR_stress", "signal"
    ]
    return df[[c for c in order if c in df.columns]]

# ------------------
# Demo / CLI usage
# ------------------
if __name__ == "__main__":
    out_dir = Path("./real_estate_metric_outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Try to read user input; fall back to demo data
    input_csv = Path("./input.csv")
    if input_csv.exists():
        df_in = pd.read_csv(input_csv)
    else:
        # Demo dataset (fictional but realistic)
        df_in = pd.DataFrame([
            {
                "address": "12 Park St, Box Hill VIC",
                "price": 900_000, "weekly_rent": 720,
                "council_rates": 2200, "strata_body_corp": 0,
                "insurance": 1200, "land_tax": 800, "other_costs": 500,
                "current_interest_rate": 0.065,
            },
            {
                "address": "4/18 Beach Rd, St Kilda VIC",
                "price": 650_000, "weekly_rent": 620,
                "council_rates": 1500, "strata_body_corp": 2400,
                "insurance": 900, "land_tax": 0, "other_costs": 600,
                "current_interest_rate": 0.065,
            },
            {
                "address": "7 River Gums Dr, Werribee VIC",
                "price": 680_000, "weekly_rent": 520,
                "council_rates": 1900, "strata_body_corp": 0,
                "insurance": 1100, "land_tax": 300, "other_costs": 500,
                "current_interest_rate": 0.065,
            },
            {
                "address": "22 King St, Newcastle NSW",
                "price": 850_000, "weekly_rent": 780,
                "council_rates": 2100, "strata_body_corp": 0,
                "insurance": 1200, "land_tax": 700, "other_costs": 600,
                "current_interest_rate": 0.065,
            },
            {
                "address": "3/55 James St, Fortitude Valley QLD",
                "price": 580_000, "weekly_rent": 600,
                "council_rates": 1400, "strata_body_corp": 2800,
                "insurance": 800, "land_tax": 0, "other_costs": 700,
                "current_interest_rate": 0.065,
            },
        ])

    # Compute metric
    results = compute_scoc(df_in, DEFAULTS).sort_values("sCoC_percent", ascending=False)

    # Save
    csv_path = out_dir / "scoc_results.csv"
    xlsx_path = out_dir / "scoc_results.xlsx"
    results.to_csv(csv_path, index=False)
    results.to_excel(xlsx_path, index=False)

    # Also emit a blank template for future use
    template_cols = [
        "address","price","weekly_rent","council_rates","strata_body_corp",
        "insurance","land_tax","other_costs","current_interest_rate","lvr","loan_term_years"
    ]
    pd.DataFrame(columns=template_cols).to_csv(out_dir / "input_template.csv", index=False)

    # Print a quick summary
    print("\nTop 5 (by sCoC %):")
    print(results.head(5).to_string(index=False))

    # Optional: quick bar chart (comment out if running headless)ß
    try:
        plt.figure()
        plt.bar(results["address"], results["sCoC_percent"])
        plt.xticks(rotation=25, ha="right")
        plt.ylabel("sCoC (%)  —  +2% rate, 4wk vacancy")
        plt.title("Stress-Tested Cash-on-Cash by Property")
        plt.tight_layout()
        plt.show()
    except Exception as e:
        # If running without a display backend
        print(f"(Chart skipped: {e})")
