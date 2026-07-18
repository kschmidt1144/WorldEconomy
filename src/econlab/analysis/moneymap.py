"""Generate a MapMaker scene of world money flows from the trade table.

Emits ~/Repos/MapMaker/scenes/world-money-flows-2024.map.json: the top
bilateral goods-trade corridors (BACI 2024, undirected pair totals) as
great-circle arcs on an Arctic-centered globe — the one projection where all
three engines (North America, Europe, East Asia) share the frame.

Render: cd ~/Repos/MapMaker && npm run mapmaker -- render scenes/world-money-flows-2024.map.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ..model import connect

SCENE_PATH = Path.home() / "Repos/MapMaker/scenes/world-money-flows-2024.map.json"

# schematic national anchor points (economic centers, not geometric centroids)
ANCHORS: dict[str, tuple[float, float]] = {
    "USA": (-95.0, 38.5), "CAN": (-79.5, 43.7), "MEX": (-99.1, 19.4),
    "BRA": (-46.6, -23.5), "GBR": (-0.1, 51.5), "IRL": (-6.3, 53.3),
    "FRA": (2.3, 48.8), "DEU": (10.0, 51.0), "NLD": (4.9, 52.4),
    "BEL": (4.4, 50.8), "ITA": (12.5, 41.9), "ESP": (-3.7, 40.4),
    "CHE": (8.5, 47.2), "AUT": (16.4, 48.2), "POL": (19.9, 52.2),
    "CZE": (14.4, 50.1), "HUN": (19.0, 47.5), "SVK": (17.1, 48.1),
    "SWE": (18.1, 59.3), "NOR": (10.7, 59.9), "DNK": (12.6, 55.7),
    "RUS": (37.6, 55.7), "TUR": (32.9, 39.9), "SAU": (46.7, 24.6),
    "ARE": (55.3, 25.2), "QAT": (51.5, 25.3), "IND": (77.2, 28.6),
    "CHN": (114.0, 32.0), "JPN": (139.7, 35.7), "KOR": (127.0, 37.5),
    "TWN": (121.0, 24.5), "HKG": (114.2, 22.3), "VNM": (105.8, 21.0),
    "THA": (100.5, 13.8), "MYS": (101.7, 3.1), "SGP": (103.85, 1.3),
    "IDN": (106.8, -6.2), "PHL": (121.0, 14.6), "AUS": (151.2, -33.9),
}

NA = {"USA", "CAN", "MEX"}
EU = {"GBR", "IRL", "FRA", "DEU", "NLD", "BEL", "ITA", "ESP", "CHE", "AUT",
      "POL", "CZE", "HUN", "SVK", "SWE", "NOR", "DNK"}
ASIA = {"CHN", "JPN", "KOR", "TWN", "HKG", "VNM", "THA", "MYS", "SGP", "IDN",
        "PHL", "IND"}
GULF = {"SAU", "ARE", "QAT", "RUS", "TUR"}

CORRIDOR_COLORS = {
    "transpacific": "#d1242f",   # Asia <-> North America
    "intra-asia": "#9a6700",
    "intra-europe": "#1a7f37",
    "eurasia": "#8250df",        # Europe <-> Asia
    "transatlantic": "#0969da",
    "north-america": "#1f6feb",
    "energy-gulf": "#57606a",
    "other": "#6e7781",
}

HUB_LABELS = {  # thinned to avoid the European pileup; markers still show all hubs
    "USA": "UNITED STATES", "CHN": "CHINA", "DEU": "GERMANY", "JPN": "JAPAN",
    "KOR": "KOREA", "MEX": "MEXICO", "CAN": "CANADA", "GBR": "BRITAIN",
    "IND": "INDIA", "VNM": "VIETNAM", "TWN": "TAIWAN", "RUS": "RUSSIA",
}


# beyond the Arctic-centered visible cap (far side / extreme limb): labels and
# arcs to these bleed through the globe — excluded, and said so in meta.notes
HIDDEN = {"AUS", "BRA", "IDN", "PHL", "SGP", "MYS", "THA"}


def _corridor(a: str, b: str) -> str:
    s = {a, b}
    if s & ASIA and s & NA:
        return "transpacific"
    if s <= ASIA:
        return "intra-asia"
    if s <= EU:
        return "intra-europe"
    if s & EU and s & ASIA:
        return "eurasia"
    if s & EU and s & NA:
        return "transatlantic"
    if s <= NA:
        return "north-america"
    if s & GULF:
        return "energy-gulf"
    return "other"


def build_scene(year: int = 2024, top_n: int = 27) -> dict:  # 27 + 3 support = 30-layer cap
    with connect() as con:
        pairs = con.execute(
            """
            SELECT least(exporter, importer) AS a, greatest(exporter, importer) AS b,
                   sum(value_usd) AS v
            FROM trade WHERE year = ?
            GROUP BY 1, 2 ORDER BY v DESC LIMIT 120
            """, [year],
        ).df()

    pairs = pairs[
        pairs.a.isin(ANCHORS) & pairs.b.isin(ANCHORS)
        & ~pairs.a.isin(HIDDEN) & ~pairs.b.isin(HIDDEN)
    ].head(top_n)
    vmax = float(pairs.v.max())

    route_layers, used = [], set()
    for i, r in enumerate(pairs.itertuples()):
        a, b = ANCHORS[r.a], ANCHORS[r.b]
        corridor = _corridor(r.a, r.b)
        width = round(1.2 + 7.0 * math.sqrt(r.v / vmax), 2)
        layer = {
            "id": f"flow-{r.a.lower()}-{r.b.lower()}",
            "type": "route",
            "path": {"kind": "greatCircle",
                     "from": {"lon": a[0], "lat": a[1]},
                     "to": {"lon": b[0], "lat": b[1]}},
            "style": {"width": width, "color": CORRIDOR_COLORS[corridor],
                      "glow": bool(i < 12)},
        }
        if i < 3:
            layer["label"] = {"text": f"${r.v/1e9:,.0f}B", "at": "midpoint"}
        route_layers.append(layer)
        used |= {r.a, r.b}

    labels = [
        {"text": HUB_LABELS[c], "lon": ANCHORS[c][0], "lat": ANCHORS[c][1],
         "rank": "country"}
        for c in HUB_LABELS if c in used
    ]
    markers = [
        {"kind": "dot", "lon": ANCHORS[c][0], "lat": ANCHORS[c][1]} for c in sorted(used)
    ]

    total = float(pairs.v.sum())
    return {
        "specVersion": "0.1",
        "meta": {
            "id": "world-money-flows-2024",
            "title": f"How money moves: the world's {top_n} largest goods-trade corridors, {year}",
            "notes": (
                f"Arcs = top {top_n} bilateral goods-trade corridors of {year} "
                f"(undirected pair totals, ${total/1e12:.1f}T combined), computed from "
                "CEPII BACI HS92 V202601 in the econlab warehouse (WorldEconomy repo). "
                "Width ~ sqrt(value); color = corridor class (transpacific red, intra-Asia "
                "amber, intra-Europe green, Europe-Asia purple, transatlantic light blue, "
                "North America blue, Gulf/energy gray). Endpoints are schematic national "
                "anchor points (economic centers), not precise geography. Arctic-centered "
                "framing so North America, Europe, and East Asia share the frame; southern-"
                "hemisphere corridors below the visible cap are excluded from the count "
                "shown. Data: CEPII BACI (free with citation)."
            ),
        },
        "time": {"date": f"{year}-07-01"},
        "theme": {"name": "slate-dark", "overrides": {"labelScale": 0.9}},
        "basemap": {"relief": True, "terrain": False},
        "lighting": "flat",
        "camera": {
            "shots": [
                {"type": "hold",
                 "at": {"lon": -40, "lat": 78, "height": 23_000_000,
                        "heading": 0, "pitch": -90, "roll": 0},
                 "duration": 0}
            ]
        },
        "layers": (
            [{"id": "borders", "type": "borders",
              "source": {"pack": "naturalearth-admin0-modern"},
              "style": {"fillOpacity": 0.06}}]
            + route_layers
            + [{"id": "hub-markers", "type": "markers", "items": markers},
               {"id": "hub-labels", "type": "labels", "items": labels}]
        ),
        "output": {"kind": "still", "width": 3840, "height": 2160,
                   "fileName": "world-money-flows-2024.png"},
        "seed": 42,
    }


def main() -> None:
    scene = build_scene()
    SCENE_PATH.write_text(json.dumps(scene, indent=2))
    n_routes = sum(1 for l in scene["layers"] if l["type"] == "route")
    print(f"scene written: {SCENE_PATH} ({n_routes} corridors)")


if __name__ == "__main__":
    main()
