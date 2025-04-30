# -----------------------------------------------------------
# Section-1: Import the necessary libraries
# -----------------------------------------------------------
from __future__ import annotations

from pathlib import Path
from datetime import date
from calendar import monthrange
import pandas as pd
from agents import function_tool

# -----------------------------------------------------------
# Section-2: Defining constants and file paths
# -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
HIST_CSV = BASE_DIR / "Csv_files/historical_transactions.csv"
CURR_CSV = BASE_DIR / "Csv_files/current_month_transactions.csv"

DATE_COL   = "transaction_date"
VENDOR_COL = "vendor_id"
AMOUNT_COL = "amount"

WINDOW_MONTHS  = 12
MIN_MONTHS     = 8
MAX_MISSED     = 2
TOLERANCE_DAYS = 3          # still used internally for cadence detection
STD_DAY_MAX    = 2.0

OUT_PATH = "/Users/dipeshchandiramani/accounting_agents/monthly_billers.csv"

# -----------------------------------------------------------
# Section-3: Defining helper functions
# -----------------------------------------------------------
def _normalise(series: pd.Series) -> pd.Series:
    """
    Normalises vendor names by stripping whitespace, converting to lowercase,
    """
    return (series.astype(str)
            .str.strip()
            .str.lower()
            .str.replace(r"[^\w\s]", "", regex=True))


def analyse_historical(path: str) -> pd.DataFrame:
    """
    Analyses historical transactions to determine vendor billing patterns.
    """
    df = pd.read_csv(path, parse_dates=[DATE_COL])
    df[VENDOR_COL] = _normalise(df[VENDOR_COL])

    df["year_month"] = df[DATE_COL].dt.to_period("M")
    df["day"]        = df[DATE_COL].dt.day

    if WINDOW_MONTHS:
        cutoff = df[DATE_COL].max() - pd.DateOffset(months=WINDOW_MONTHS)
        df = df[df[DATE_COL] >= cutoff]

    full_months = pd.period_range(df["year_month"].min(),
                                  df["year_month"].max(), freq="M")
    n_full = len(full_months)

    rows = []
    for vid, g in df.groupby(VENDOR_COL, sort=False):
        n_months = g["year_month"].nunique()
        missing  = n_full - n_months
        if (n_months < MIN_MONTHS) or (missing > MAX_MISSED):
            continue

        mode_day  = g["day"].mode().iat[0]
        centred   = g.loc[abs(g["day"] - mode_day) <= TOLERANCE_DAYS, "day"]
        billing_d = int(centred.mode().iat[0] if not centred.empty else mode_day)

        sigma     = round(g["day"].std(ddof=0), 2)
        drift     = sigma > STD_DAY_MAX
        conf      = round((n_months / n_full) * (0.7 if drift else 1.0), 2)

        rows.append(dict(
            vendor_id      = vid,
            billing_day    = billing_d,
            months_covered = n_months,
            missing_months = missing,
            std_day        = sigma,
            drift_flag     = drift,
            confidence     = conf,
            median_amount  = round(g[AMOUNT_COL].median(), 2),
        ))

    return pd.DataFrame(rows).sort_values("vendor_id").reset_index(drop=True)


def flag_missing_current(hist_df: pd.DataFrame, current_csv: str) -> pd.DataFrame:
    """
    Analyses the current month transactions and flags vendors that are regular but missing in the current month.
    """
    cur = pd.read_csv(current_csv, parse_dates=[DATE_COL])
    cur[VENDOR_COL] = _normalise(cur[VENDOR_COL])
    cur_vendors = cur[VENDOR_COL].unique().tolist()

    today         = date.today()
    month_label   = today.strftime("%B %Y")     # e.g. "April 2025"
    last_dom      = monthrange(today.year, today.month)[1]

    # ----------------------------------------------------------
    # Determine which vendors are missing invoices this month
    # ----------------------------------------------------------
    def _compute_row(r: pd.Series) -> pd.Series:
        # window width = max(1, round(std_day))  → at least ±1 for non-zero drift
        width = max(1, int(round(r.std_day))) if r.std_day >= 0.5 else 0

        if width == 0:                     # exact-day vendor
            low = high = r.billing_day
            r["billing_window"] = f"{low}th of each month"
        else:
            low  = max(1, r.billing_day - width)
            high = min(r.billing_day + width, last_dom)
            r["billing_window"] = f"{low}th to {high}th each month"

        # determine “missing-now”
        exp_high_date = date(today.year, today.month, high)
        days_past     = max(0, (today - exp_high_date).days)
        r["days_past_window"] = days_past
        r["missing_now"]      = (r.vendor_id not in cur_vendors) and (days_past > 0)

        r["suggested_accrual"] = r.median_amount
        return r

    flagged = hist_df.apply(_compute_row, axis=1)

    # ----------------------------------------------------------
    # Narrative reason for accrual
    # ----------------------------------------------------------
    def _build_reason(row: pd.Series) -> str:
        confidence_pct = int(round(row.confidence * 100))
        has_invoice    = not row.missing_now

        base = (
            f"Vendor {row.vendor_id} has consistently sent invoices of around "
            f"${row.median_amount:,.2f} on the {row.billing_window} "
            f"for the past {row.months_covered} months."
        )

        if has_invoice:
            tail = (f"An invoice was received for {month_label}, so no accrual is "
                    f"proposed. I’m {confidence_pct}% confident that no additional "
                    f"accrual amount is required.")
        else:
            tail = (f"No invoice has been recorded for {month_label}, and we are now "
                    f"past the typical billing window for this vendor. "
                    f"I’m {confidence_pct}% confident that "
                    f"${row.suggested_accrual:,.2f} is the appropriate accrual amount.")

        return f"{base} {tail}"

    flagged["reason"] = flagged.apply(_build_reason, axis=1)
    return flagged


# ------------------------------------------------------------
# Section-4: Defining the main function (tool for the AI agent)
# ------------------------------------------------------------

# This function will be called by the agent to determine the current month accrual
@function_tool
def determine_current_month_accrual() -> str:
    """
    Description:
        Determines which vendors are missing invoices for the current month
        and suggests accrual amounts based on historical billing patterns.

    Args:
        None

    Returns:
        A Markdown table with the vendors who should be part of current month
        transactions.
    """
    # cadence + flags
    hist_df  = analyse_historical(HIST_CSV)
    full_df  = flag_missing_current(hist_df, CURR_CSV)

    # filter to vendors that still need an accrual
    final_df = full_df.loc[full_df["missing_now"]].copy()

    # remove diagnostic columns no longer needed downstream
    final_df.drop(columns=["months_covered", "missing_months", "drift_flag"],
                  inplace=True)

    # save / print
    if OUT_PATH:
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        final_df.to_csv(OUT_PATH, index=False)
        print(f"✓ {len(final_df)} vendors → {OUT_PATH}")
    else:
        print(final_df.to_string(index=False))

    # return in Markdown for easy embedding
    return final_df.to_markdown(index=False, tablefmt="pipe")