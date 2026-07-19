"""Dynasty balance sheets — starting with the Rothschild archival series.

Combined capital of the five Rothschild houses, 1818-1904, transcribed
digit-for-digit from Ferguson, *The House of Rothschild* vol. 2, Appendix 2
Table c (compiled from the Rothschild Archive partnership accounts; £
thousand in the source, normalized to £). Business capital only — personal
estates, houses, and collections are NOT included (Ferguson's caveat).
"""

from __future__ import annotations

import json

import pandas as pd

from ..catalog import Series
from ..fetch import save_bytes

SOURCE = "dynasties"
TITLE = "Dynasty capital series (curated, cited)"

# year -> (frankfurt, paris, london, vienna, naples, total) in £ thousand
ROTHSCHILD = {
    1818: (680, 350, 742, None, None, 1772),
    1825: (1450, 1490, 1142, None, None, 4082),
    1828: (1534, 1466, 1183, 25, 130, 4338),
    1836: (2121, 1774, 1733, 110, 268, 6008),
    1844: (2750, 2311, 2005, 250, 463, 7778),
    1852: (2746, 3542, 2500, 83, 661, 9532),
    1862: (6694, 8479, 5355, 457, 1328, 22313),
    1874: (4533, 20088, 6509, 3229, None, 34359),
    1879: (4225, 16815, 6102, 3115, None, 30258),
    1882: (4735, 23589, 5922, 4137, None, 38384),
    1887: (4407, 22974, 6149, 4507, None, 38038),
    1888: (3173, 18878, 5674, 4154, None, 31880),
    1896: (2600, 23793, 7296, 6443, None, 40131),
    1898: (2327, 24254, 7545, 6382, None, 40507),
    1899: (2294, 24947, 7704, 6507, None, 41452),
    1900: (None, 22328, 7779, 6845, None, 36953),
    1901: (None, 22665, 7641, 7021, None, 37327),
    1902: (None, 23136, 8057, 7196, None, 38388),
    1903: (None, 23736, 7196, 7367, None, 38298),
    1904: (None, 21086, 8429, 7621, None, 37136),
}
HOUSES = ["frankfurt", "paris", "london", "vienna", "naples", "total"]

CITATION = (
    "Ferguson, The House of Rothschild: The World's Banker 1849-1998, Appendix 2 "
    "Table c ('Combined Rothschild capital, 1818-1904, £ thousand'), from the "
    "Rothschild Archive partnership accounts."
)


def fetch(force: bool = False) -> None:
    save_bytes(SOURCE, "rothschild_capital.json",
               json.dumps({"table": ROTHSCHILD, "citation": CITATION}, indent=1).encode(),
               "curated: Ferguson Appendix 2 (transcribed from table image)")


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    rows = []
    for year, vals in ROTHSCHILD.items():
        for house, v in zip(HOUSES, vals):
            if v is not None:
                rows.append((f"dynasties/rothschild_capital_{house}", "ROTHSCHILD",
                             year, None, float(v) * 1_000))
    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])

    series_list = [
        Series(
            series_id=f"dynasties/rothschild_capital_{house}",
            source=SOURCE,
            name=(
                "Rothschild combined capital (five houses)" if house == "total"
                else f"Rothschild capital: {house.title()} house"
            ),
            unit="nominal £ (normalized from £ thousand)",
            unit_type="lcu",
            frequency="A",
            description=(
                f"{CITATION} Business capital only — excludes personal estates, "
                "houses, and collections. Naples closed 1863; Frankfurt wound up "
                "1901 (no male heirs); Vienna seized by the Nazis 1938; Paris "
                "nationalized 1981."
            ),
            license="Curated from published scholarship (Ferguson 1999), cited",
            url="https://www.rothschildarchive.org/",
        )
        for house in HOUSES
    ]
    ents = pd.DataFrame(
        [("ROTHSCHILD", "Rothschild family (five-house partnership)", "other")],
        columns=["entity", "name", "kind"],
    )
    return series_list, obs, ents
