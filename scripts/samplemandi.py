"""
samplemandi.py

Minimal runnable scaffold for the Mandi sample script.
Run: python samplemandi.py --message "Hello"
"""

from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample Mandi runner. Extend this script with your logic.",
    )
    parser.add_argument(
        "--message",
        default="samplemandi.py is running",
        help="Message to print when the script runs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    print(args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import requests
import pandas as pd
from datetime import datetime, timedelta

API_KEY = "579b464db66ec23bdd000001d96f710fb70b4957513fb25cfca63806"
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"  # Daily market prices dataset
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

def fetch_odisha_prices():
    # Start with today, fallback to yesterday
    for delta in [0, 1]:
        date = (datetime.today() - timedelta(days=delta)).strftime("%Y-%m-%d")
        print(f"Trying date: {date}")
        
        params = {
            "api-key": API_KEY,
            "format": "json",
            "limit": 1000,
            "filters[state]": "Odisha",
            "filters[arrival_date]": date
        }
        
        resp = requests.get(BASE_URL, params=params)
        if resp.status_code != 200:
            raise Exception(f"API Error {resp.status_code}: {resp.text}")
        
        records = resp.json().get("records", [])
        if records:         # Found data
            print(f"✅ Found {len(records)} records for {date}")
            return pd.DataFrame(records), date
    
    # If nothing found for both
    print("⚠️ No data for today or yesterday.")
    return pd.DataFrame(), None

# Fetch and save
df, used_date = fetch_odisha_prices()
if not df.empty:
    filename = f"odisha_mandi_{used_date}.csv"
    df.to_csv(filename, index=False)
    print(f"Saved to {filename}")
