"""
Analysis: SQL queries on the SQLite database -> tables (CSV) + figures (PNG).

Run from the repo root (after src/etl.py):  python src/analysis.py
"""
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "unemployment.db"
FIG_DIR = ROOT / "outputs" / "figures"
TABLE_DIR = ROOT / "outputs" / "tables"
LOCKDOWN_DAY = pd.Timestamp("2020-03-25")

# NOTE: these averages are simple (unweighted) means of state-level rates, not an official national rate.
QUERIES = {
    "monthly_trend": """
        SELECT substr(date, 1, 7) AS month,
               ROUND(AVG(unemployment_rate), 2) AS avg_unemployment_rate
        FROM unemployment_area
        GROUP BY month ORDER BY month
    """,
    "rural_vs_urban": """
        SELECT substr(date, 1, 7) AS month, area,
               ROUND(AVG(unemployment_rate), 2) AS avg_unemployment_rate
        FROM unemployment_area
        GROUP BY month, area ORDER BY month, area
    """,
    "state_impact": """
        SELECT region,
               ROUND(AVG(CASE WHEN period = 'pre_covid' THEN unemployment_rate END), 2) AS pre_covid,
               ROUND(AVG(CASE WHEN period = 'lockdown'  THEN unemployment_rate END), 2) AS lockdown,
               ROUND(AVG(CASE WHEN period = 'lockdown'  THEN unemployment_rate END)
                   - AVG(CASE WHEN period = 'pre_covid' THEN unemployment_rate END), 2) AS increase
        FROM unemployment_area
        GROUP BY region
        HAVING increase IS NOT NULL
        ORDER BY increase DESC
    """,
    "recovery_2020": """
        SELECT substr(date, 1, 7) AS month,
               ROUND(AVG(unemployment_rate), 2) AS avg_unemployment_rate
        FROM unemployment_regional_2020
        GROUP BY month ORDER BY month
    """,
    "macro_region": """
        SELECT macro_region,
               ROUND(AVG(CASE WHEN date <  '2020-03-01' THEN unemployment_rate END), 2) AS jan_feb_2020,
               ROUND(AVG(CASE WHEN date BETWEEN '2020-04-01' AND '2020-05-31' THEN unemployment_rate END), 2) AS apr_may_2020,
               ROUND(AVG(CASE WHEN date >= '2020-10-01' THEN unemployment_rate END), 2) AS oct_2020
        FROM unemployment_regional_2020
        GROUP BY macro_region ORDER BY apr_may_2020 DESC
    """,
}


def run_queries() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        results = {name: pd.read_sql(sql, conn) for name, sql in QUERIES.items()}
    for name, df in results.items():
        df.to_csv(TABLE_DIR / f"{name}.csv", index=False)
    return results


def to_date(month_series: pd.Series) -> pd.Series:
    return pd.to_datetime(month_series + "-01")


def save(fig_name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIG_DIR / fig_name, dpi=150)
    plt.close()


def plot_monthly_trend(df: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(to_date(df["month"]), df["avg_unemployment_rate"], marker="o")
    plt.axvline(LOCKDOWN_DAY, color="red", linestyle="--", label="National lockdown (25 Mar 2020)")
    plt.title("Average State Unemployment Rate, May 2019 - Jun 2020")
    plt.ylabel("Unemployment rate (%)")
    plt.legend()
    plt.xticks(rotation=45)
    save("01_monthly_trend.png")


def plot_rural_urban(df: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 5))
    for area, grp in df.groupby("area"):
        plt.plot(to_date(grp["month"]), grp["avg_unemployment_rate"], marker="o", label=area)
    plt.axvline(LOCKDOWN_DAY, color="red", linestyle="--", alpha=0.6)
    plt.title("Rural vs Urban Unemployment Rate")
    plt.ylabel("Unemployment rate (%)")
    plt.legend()
    plt.xticks(rotation=45)
    save("02_rural_vs_urban.png")


def plot_state_impact(df: pd.DataFrame) -> None:
    top = df.head(10).sort_values("increase")
    plt.figure(figsize=(8, 5))
    plt.barh(top["region"], top["increase"], color="firebrick")
    plt.title("Top 10 States: Rise in Unemployment (Apr-May 2020 vs pre-Covid)")
    plt.xlabel("Increase (percentage points)")
    save("03_top_states_impact.png")


def plot_recovery(df: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(to_date(df["month"]), df["avg_unemployment_rate"], marker="o", color="darkgreen")
    plt.axvline(LOCKDOWN_DAY, color="red", linestyle="--", label="National lockdown (25 Mar 2020)")
    plt.title("Unemployment Rate Through 2020: Spike and Recovery (Jan - Oct)")
    plt.ylabel("Unemployment rate (%)")
    plt.legend()
    plt.xticks(rotation=45)
    save("04_recovery_2020.png")


def plot_macro_region(df: pd.DataFrame) -> None:
    ax = df.set_index("macro_region")[["jan_feb_2020", "apr_may_2020", "oct_2020"]].plot(
        kind="bar", figsize=(9, 5), color=["steelblue", "firebrick", "seagreen"]
    )
    ax.set_title("Unemployment by Macro-Region: Before, During Lockdown, and Oct 2020")
    ax.set_ylabel("Unemployment rate (%)")
    ax.set_xlabel("")
    plt.xticks(rotation=0)
    save("05_macro_region.png")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    r = run_queries()
    plot_monthly_trend(r["monthly_trend"])
    plot_rural_urban(r["rural_vs_urban"])
    plot_state_impact(r["state_impact"])
    plot_recovery(r["recovery_2020"])
    plot_macro_region(r["macro_region"])
    for name in ["monthly_trend", "recovery_2020", "macro_region"]:
        print(f"\n== {name}\n{r[name].to_string(index=False)}")
    print("\n== state_impact (top 5 / bottom 3)")
    print(r["state_impact"].head(5).to_string(index=False))
    print(r["state_impact"].tail(3).to_string(index=False))
    print("\nFigures ->", FIG_DIR, "\nTables  ->", TABLE_DIR)


if __name__ == "__main__":
    main()
