"""Jordà-Schularick-Taylor Macrohistory Database — 18 economies, 1870->.

Credit, money, rates, asset returns ("Rate of Return on Everything"), public
debt, and systemic-crisis flags. We ingest EVERY numeric variable, using the
Stata variable labels as names, and curate units for the key ones.
License: free for research with citation.
"""

from __future__ import annotations

import re

import pandas as pd

from ..catalog import Series
from ..config import RAW
from ..fetch import download, download_first, get_text

SOURCE = "jst"
TITLE = "Jorda-Schularick-Taylor Macrohistory Database"
FILENAME = "JSTdataset.dta"

CANDIDATES = [
    "https://data.macrohistory.net/JST/JSTdatasetR6.dta",
    "https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.dta",
]
LANDING = "https://www.macrohistory.net/database/"

ID_COLS = {"year", "country", "iso", "ifs"}

# curated units for headline variables (everything else lands as 'unknown')
CURATED: dict[str, tuple[str, str]] = {
    "rgdpmad": ("2011 int'l $ per person", "ppp_usd"),
    "gdp": ("local currency, nominal", "lcu"),
    "cpi": ("index", "index"),
    "stir": ("% per year (short-term rate)", "percent"),
    "ltrate": ("% per year (long-term rate)", "percent"),
    "debtgdp": ("public debt / GDP (fraction)", "ratio"),
    "crisisJST": ("systemic financial crisis flag (0/1)", "count"),
    "eq_tr": ("equity total return (fraction/yr)", "ratio"),
    "housing_tr": ("housing total return (fraction/yr)", "ratio"),
    "bond_tr": ("gov bond total return (fraction/yr)", "ratio"),
    "bill_rate": ("bill rate (fraction/yr)", "ratio"),
    "safe_tr": ("safe assets total return (fraction/yr)", "ratio"),
    "risky_tr": ("risky assets total return (fraction/yr)", "ratio"),
    "tloans": ("local currency, nominal (total loans)", "lcu"),
    "money": ("local currency, nominal (broad money)", "lcu"),
    "narrowm": ("local currency, nominal (narrow money)", "lcu"),
    "ca": ("local currency, nominal (current account)", "lcu"),
    "xrusd": ("LCU per USD", "ratio"),
    "unemp": ("% of labor force", "percent"),
    "pop": ("thousands", "count"),
    "iy": ("investment / GDP (fraction)", "ratio"),
}


def fetch(force: bool = False) -> None:
    try:
        download_first(SOURCE, CANDIDATES, FILENAME, force=force)
        return
    except Exception:
        pass
    html = get_text(LANDING)
    links = re.findall(r'href="([^"]+\.dta[^"]*)"', html)
    if not links:
        raise RuntimeError("jst: no .dta link found on macrohistory.net/database/")
    url = links[0]
    if url.startswith("/"):
        url = "https://www.macrohistory.net" + url
    download(SOURCE, url.replace("&amp;", "&"), FILENAME, force=True)


def parse() -> tuple[list[Series], pd.DataFrame]:
    path = RAW / SOURCE / FILENAME
    with pd.io.stata.StataReader(path) as reader:
        labels = reader.variable_labels()
    df = pd.read_stata(path)

    num_cols = [
        c for c in df.columns
        if c not in ID_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]

    series_list = []
    for c in num_cols:
        unit, unit_type = CURATED.get(c, ("", "unknown"))
        series_list.append(
            Series(
                series_id=f"jst/{c}",
                source=SOURCE,
                name=labels.get(c) or c,
                unit=unit,
                unit_type=unit_type,
                frequency="A",
                per_capita=c in {"rgdpmad"},
                description=f"JST Macrohistory variable `{c}`: {labels.get(c) or ''}".strip(),
                license="Free for research with citation (JST)",
                url="https://www.macrohistory.net/database/",
            )
        )

    obs = df.melt(
        id_vars=["iso", "year"], value_vars=num_cols, var_name="key", value_name="value"
    ).dropna(subset=["value"])
    obs["series_id"] = "jst/" + obs["key"]
    obs = obs.rename(columns={"iso": "entity"})
    obs["year"] = obs["year"].astype(int)
    obs["date"] = None
    return series_list, obs[["series_id", "entity", "year", "date", "value"]]
