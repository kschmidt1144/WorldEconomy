"""Treasury TIC — Major Foreign Holders of US Treasury securities.

The canonical mfh.txt table: which governments/jurisdictions own the US
federal debt, monthly, ~last 13 months per file (levels in $bn -> base $).
Country names mapped to ISO3; custodial centers (Cayman, Belgium/Euroclear,
Luxembourg) are flagged in the description — beneficial owners hide behind
them. Public domain.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download
from ..model import month_end

SOURCE = "tic"
TITLE = "Treasury TIC major foreign holders"
# NOTE: the classic Publish/mfh.txt froze in Mar-2023; the live SLT-based
# table (tab-delimited, ~13 months, updated monthly) is slt_table5.txt.
URL = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
FILENAME = "slt_table5.txt"

NAME_TO_ISO3 = {
    "japan": "JPN", "china, mainland": "CHN", "china mainland": "CHN",
    "united kingdom": "GBR", "cayman islands": "CYM", "luxembourg": "LUX",
    "canada": "CAN", "belgium": "BEL", "ireland": "IRL", "france": "FRA",
    "switzerland": "CHE", "taiwan": "TWN", "hong kong": "HKG",
    "singapore": "SGP", "india": "IND", "brazil": "BRA", "norway": "NOR",
    "saudi arabia": "SAU", "korea": "KOR", "korea, south": "KOR",
    "germany": "DEU", "mexico": "MEX", "netherlands": "NLD",
    "united arab emirates": "ARE", "australia": "AUS", "kuwait": "KWT",
    "philippines": "PHL", "sweden": "SWE", "thailand": "THA", "israel": "ISR",
    "spain": "ESP", "italy": "ITA", "poland": "POL", "chile": "CHL",
    "colombia": "COL", "vietnam": "VNM", "peru": "PER", "iraq": "IRQ",
    "bahamas": "BHS", "bermuda": "BMU",
}
CUSTODIAL = {"CYM", "BEL", "LUX", "IRL", "CHE", "GBR", "BHS", "BMU"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


def fetch(force: bool = False) -> None:
    download(SOURCE, URL, FILENAME, force=force)


def parse() -> tuple[list[Series], pd.DataFrame]:
    text = (RAW / SOURCE / FILENAME).read_text(errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]

    header_idx = next(
        (i for i, ln in enumerate(lines) if ln.split("\t")[0].strip() == "Country"), None
    )
    if header_idx is None:
        raise ValueError("tic: no 'Country' header row in slt_table5.txt")
    cols = lines[header_idx].split("\t")[1:]
    dates = []
    for c in cols:
        m = re.match(r"(20\d\d)-(\d\d)", c.strip())
        if m:
            dates.append(month_end(int(m.group(1)), int(m.group(2))))
    if len(dates) < 6:
        raise ValueError(f"tic: unexpected header columns {cols[:4]}")

    rows = []
    for ln in lines[header_idx + 1:]:
        parts = ln.split("\t")
        name = parts[0].strip().lower().rstrip("*").strip()
        if not name:
            continue
        entity = "WLD" if name == "grand total" else NAME_TO_ISO3.get(name)
        if entity is None:
            continue
        for d, raw in zip(dates, parts[1:]):
            raw = raw.strip().replace(",", "")
            if raw and raw not in ("n/a", "-"):
                try:
                    rows.append((entity, d.year, d, float(raw) * 1e9))
                except ValueError:
                    continue
        if name == "grand total":
            break  # memo/of-which rows follow — stop here

    if not rows:
        raise ValueError("tic: no holder rows parsed — layout changed?")

    obs = pd.DataFrame(rows, columns=["entity", "year", "date", "value"])
    obs = obs.drop_duplicates(subset=["entity", "date"])
    obs["series_id"] = "tic/us_treasury_holdings"

    series_list = [
        Series(
            series_id="tic/us_treasury_holdings",
            source=SOURCE,
            name="Holdings of US Treasury securities (major foreign holders)",
            unit="US$ (normalized from billions)",
            unit_type="nominal_usd",
            frequency="M",
            description=(
                "Treasury TIC mfh.txt: US Treasury securities held per foreign "
                "jurisdiction; WLD = grand total foreign holdings. Custodial centers "
                f"({', '.join(sorted(CUSTODIAL))}) mask beneficial owners."
            ),
            license="Public domain (US Treasury)",
            url="https://ticdata.treasury.gov/Publish/mfh.txt",
        )
    ]
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
