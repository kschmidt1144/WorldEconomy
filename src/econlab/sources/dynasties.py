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

# Fugger firm capital, Rhenish gulden (Ehrenberg 1896 / Häberlein 2006 —
# the standard published inventory figures)
FUGGER = {1494: 54_385, 1511: 196_791, 1527: 2_021_202, 1546: 5_100_000}
FUGGER_CITATION = (
    "Ehrenberg, Das Zeitalter der Fugger (1896); Häberlein, Die Fugger (2006). "
    "1527 = net capital from the inventory after Jakob's death; 1546 = capital "
    "under Anton (gross assets exceeded 7M gulden)."
)

# Medici Bank, gold florins (de Roover 1963, from the libri segreti)
MEDICI = {
    "capital": {1397: 10_000, 1427: 25_000, 1451: 72_000},
    "profit_period": {1420: 151_820, 1450: 290_791},  # value at period END year
    "curia_deposits": {1427: 100_000},
    "conversion_spend": {1471: 663_755},  # Cosimo 1434-71: buildings, charity, taxes
}
MEDICI_CITATION = (
    "de Roover, The Rise and Decline of the Medici Bank 1397-1494 (1963), from "
    "the libri segreti: profits 1397-1420 = 151,820 fl; 1420-1450 = 290,791 fl "
    "(Rome branch ~62%, Venice 13%); capitalization c.1427 ~25,000 fl against "
    "~100,000 fl of Papal Curia deposits; total corpo c.1451 ~72,000 fl. "
    "Cosimo's 663,755 fl spending (1434-71) from Lorenzo's ricordi. London "
    "liquidation lost 51,533 fl; Bruges+London ~70,000 fl."
)

# Deep-time survivors: documented (not legendary) continuity spans.
# start/end years; end None = continuing. documentation: solid | semi-legendary.
DEEP_SURVIVORS = [
    ("Kong family (Confucius line)", -551, None, "sacred office", "solid",
     "~80 generations; hereditary Duke Yansheng until 1935; line continues (Taiwan)"),
    ("Japanese Imperial House", 539, None, "crown", "solid",
     "reliably documented from Kimmei; legendary to 660 BC; oldest reigning dynasty"),
    ("Kongo Gumi (temple builders)", 578, 2006, "family firm", "solid",
     "oldest family firm ever recorded; 40 generations; absorbed 2006"),
    ("Nishiyama Onsen Keiunkan (hotel)", 705, None, "family firm", "solid",
     "world's oldest hotel, 52+ generations"),
    ("Bagrationi (Georgia)", 780, None, "crown", "solid", "royal house, documented 8th-9th c."),
    ("Staffelter Hof (Mosel wine)", 862, None, "family firm", "solid", "German estate since 862"),
    ("Capetians", 866, None, "crown", "solid",
     "Robert the Strong; male line still reigning (Spain) - oldest documented Western dynasty"),
    ("O'Neill (Ui Neill)", 500, None, "noble house", "semi-legendary",
     "kings documented from 6th c.; descent from Niall (5th c.) semi-legendary"),
    ("Massimo (Rome)", 1000, None, "noble house", "solid",
     "claims Fabius Maximus - unprovable; documented ~1000; the thousand-year maybe"),
    ("Colonna (Rome)", 1078, None, "noble house", "solid",
     "documented from Pietro Colonna; Pope Martin V; still in Palazzo Colonna"),
    ("Orsini (Rome)", 1100, None, "noble house", "solid", "three popes; documented ~11th c."),
    ("Ricasoli (wine)", 1141, None, "family firm", "solid", "oldest Italian family firm"),
    ("Frescobaldi", 1300, None, "family firm", "solid",
     "medieval bankers ruined by English royal default c.1311; wine ever since - 26 generations"),
    ("Fugger", 1367, None, "banking dynasty", "solid",
     "firm dead 1657; family, Fuggerei, and a small bank endure"),
    ("Rothschild", 1760, None, "banking dynasty", "solid", "see Part I"),
    ("Roman senatorial aristocracy", -300, 610, "wealth class", "solid",
     "the Anicii last attested early 600s; the richest private class in history, erased in ~5 generations"),
    # --- the Eastern mirror ---
    ("Ecumenical Patriarchate", 381, None, "sacred office", "solid",
     "the office survives Byzantium AND the Ottomans; still seated in Istanbul"),
    ("St Catherine's, Sinai", 548, None, "sacred office", "solid",
     "founded under Justinian; continuously operating, property-holding, through both empires"),
    ("Great Lavra, Mt Athos", 963, None, "sacred office", "solid",
     "Athonite monastic corporations held estates through Byzantium and the Ottomans"),
    ("Kantakouzenos -> Cantacuzino", 1100, None, "noble house", "solid",
     "emperor 1347; 'Seytanoglu' strangled + fortune seized 1578 (musadere); Phanariot princes of Wallachia; extant"),
    ("House of Osman", 1299, None, "crown", "solid",
     "726 years of documented male line; sultans to 1922; the Osmanoglu family continues in exile"),
]

# Ten dynasties, cross-era: peak scale vs home economy where measurable.
# basis: computed = from this warehouse; curated = literature/historical GDP;
# na = not GDP-comparable (political conversion / corporate control).
DYNASTY_PEAKS = [
    (1, "Fugger", "1487-1657", 1546, "firm capital 5.1M gulden", "curated", 2.0,
     "vs German-lands product: scholarly band ~1.5-2.5% (Steinmetz-style estimate)"),
    (2, "Medici", "1397-1737", 1450, "corpo ~72k fl; profits 1397-1450 = 442.6k fl", "na", None,
     "small capital, papal deposits, 62% of profit from Rome; converted to POWER: two popes, Tuscany, the Uffizi"),
    (3, "Rothschild", "1810-", 1882, "five-house capital £38.4M", "computed", None,
     "3.0% of UK GDP computed in this warehouse (Ferguson x BoE)"),
    (4, "Vanderbilt", "1810-1970s", 1877, "Cornelius estate ~$100M", "curated", 1.17,
     "vs US nominal GDP 1877 ~$8.6B (MeasuringWorth); famously dissipated by heirs"),
    (5, "Rockefeller", "1870-", 1913, "JDR fortune ~$900M", "curated", 2.30,
     "vs US nominal GDP 1913 ~$39.1B; today ~$10B across 200+ heirs"),
    (6, "Mitsui", "1673-1946", 1945, "largest zaibatsu", "na", None,
     "~10% of Japanese corporate paid-in capital; dissolved by US occupation 1946"),
    (7, "Walton", "1962-", 2026, "family net worth (Forbes)", "computed", None,
     "sum of listed members from this warehouse's billionaires table"),
    (8, "Koch", "1940-", 2026, "family net worth (Forbes)", "computed", None,
     "incl. Marshall stake; sum from billionaires table"),
    (9, "Ambani", "1957-", 2026, "Mukesh Ambani & family (Forbes)", "computed", None,
     "single Forbes entry vs Indian GDP — Rothschild-scale at home"),
    (10, "Boehringer", "1885-", 2026, "family net worth (Forbes)", "computed", None,
     "15 listed heirs (Boehringer/von Baumbach), Germany's quietest dynasty"),
]


def fetch(force: bool = False) -> None:
    save_bytes(SOURCE, "rothschild_capital.json",
               json.dumps({"rothschild": ROTHSCHILD, "citation": CITATION,
                           "fugger": FUGGER, "fugger_citation": FUGGER_CITATION,
                           "peaks": DYNASTY_PEAKS}, indent=1).encode(),
               "curated: Ferguson App.2; Ehrenberg/Häberlein; dynasty peak notes")


def parse() -> tuple[list[Series], pd.DataFrame, pd.DataFrame]:
    from ..config import TIDY

    rows = []
    for year, vals in ROTHSCHILD.items():
        for house, v in zip(HOUSES, vals):
            if v is not None:
                rows.append((f"dynasties/rothschild_capital_{house}", "ROTHSCHILD",
                             year, None, float(v) * 1_000))
    for year, v in FUGGER.items():
        rows.append(("dynasties/fugger_capital", "FUGGER", year, None, float(v)))
    for key, table in MEDICI.items():
        for year, v in table.items():
            rows.append((f"dynasties/medici_{key}", "MEDICI", year, None, float(v)))
    obs = pd.DataFrame(rows, columns=["series_id", "entity", "year", "date", "value"])

    peaks = pd.DataFrame(
        DYNASTY_PEAKS,
        columns=["rank", "family", "era", "peak_year", "peak_metric", "basis",
                 "pct_home_gdp", "note"],
    )
    out = TIDY / SOURCE
    out.mkdir(parents=True, exist_ok=True)
    peaks.to_parquet(out / "peaks.parquet", index=False)

    survivors = pd.DataFrame(
        DEEP_SURVIVORS,
        columns=["name", "start_year", "end_year", "kind", "documentation", "note"],
    )
    survivors.to_parquet(out / "survivors.parquet", index=False)

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
    series_list.append(
        Series(
            series_id="dynasties/fugger_capital",
            source=SOURCE,
            name="Fugger firm capital",
            unit="Rhenish gulden",
            unit_type="lcu",
            frequency="A",
            description=(
                f"{FUGGER_CITATION} The 1519 imperial election of Charles V cost "
                "852k gulden in payments, of which the Fuggers financed 543,585. "
                "Firm destroyed by the Spanish state bankruptcies of 1557/1575/"
                "1596/1607 (~8M gulden lost); wound up by 1657."
            ),
            license="Curated from published scholarship, cited",
            url="https://www.fugger.de/en/history",
        )
    )
    medici_names = {
        "capital": "Medici Bank capital (corpo)",
        "profit_period": "Medici Bank profits (period total, at period-end year)",
        "curia_deposits": "Papal Curia deposits at the Rome branch",
        "conversion_spend": "Cosimo's spending on buildings, charity, taxes (1434-71)",
    }
    for key, name in medici_names.items():
        series_list.append(
            Series(
                series_id=f"dynasties/medici_{key}",
                source=SOURCE,
                name=name,
                unit="gold florins",
                unit_type="lcu",
                frequency="A",
                description=MEDICI_CITATION,
                license="Curated from published scholarship (de Roover 1963), cited",
                url="https://en.wikipedia.org/wiki/Medici_Bank",
            )
        )
    ents = pd.DataFrame(
        [("ROTHSCHILD", "Rothschild family (five-house partnership)", "other"),
         ("FUGGER", "Fugger firm (Augsburg)", "other"),
         ("MEDICI", "Medici Bank (Florence)", "other")],
        columns=["entity", "name", "kind"],
    )
    return series_list, obs, ents
