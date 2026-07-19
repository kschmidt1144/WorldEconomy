"""Chapter 9 — Who Owns the Land: the US stack, the world's forests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..model import connect
from ..viz import PALETTE, new_fig, save, source_note

FOREST_COUNTRIES = ["RUS", "COD", "CAN", "IDN", "PER", "AUS", "CHN", "BRA",
                    "DEU", "USA", "JPN", "FIN", "FRA", "SWE", "MEX"]


def us_stack() -> dict[str, float]:
    with connect() as con:
        g = lambda k: con.execute(  # noqa: E731
            f"SELECT value FROM obs WHERE series_id='usland/{k}' AND entity='USA'"
        ).fetchone()[0]
        return {"Federal": g("share_federal"), "State & local": g("share_state_local"),
                "Tribal trust": g("share_tribal"), "Private": g("share_private")}


def us_uses() -> pd.Series:
    with connect() as con:
        rows = con.execute(
            "SELECT series_id, value FROM obs WHERE series_id LIKE 'usland/acres_%'"
        ).df()
    rows["k"] = rows.series_id.str.split("acres_").str[-1]
    return rows.set_index("k")["value"]


def forest_ownership() -> pd.DataFrame:
    """% of forest area by ownership class, 2015, selected countries + world."""
    with connect() as con:
        df = con.execute(
            """
            SELECT f.entity,
                   any_value(f.value) AS forest,
                   max(CASE WHEN o.series_id='fra/4a_pub_own' THEN o.value END) AS pub,
                   max(CASE WHEN o.series_id='fra/4a_priv_own' THEN o.value END) AS priv,
                   max(CASE WHEN o.series_id='fra/4a_indigenous_fo' THEN o.value END) AS indig,
                   max(CASE WHEN o.series_id='fra/4a_fo_unknown' THEN o.value END) AS unk
            FROM obs f JOIN obs o ON o.entity=f.entity AND o.year=2015
            WHERE f.series_id='fra/1a_forestArea' AND f.year=2015
              AND o.series_id LIKE 'fra/4a_%'
            GROUP BY 1
            """
        ).df().set_index("entity")
    world = df.sum(numeric_only=True)
    df.loc["WORLD"] = world
    out = pd.DataFrame(index=df.index)
    out["Public"] = 100 * df.pub / df.forest
    out["Indigenous & community"] = 100 * df.indig.fillna(0) / df.forest
    out["Other private"] = 100 * (df.priv.fillna(0) - df.indig.fillna(0)) / df.forest
    out["Unknown/unreported"] = (100 - out.sum(axis=1)).clip(lower=0)
    return out.loc[FOREST_COUNTRIES + ["WORLD"]]


def fig_us_land() -> None:
    import matplotlib.pyplot as plt

    stack = us_stack()
    uses = us_uses()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Who owns America's 2.27 billion acres", x=0.01, ha="left",
                 fontweight="bold", fontsize=13)

    left = 0.0
    colors = {"Federal": PALETTE[0], "State & local": PALETTE[7],
              "Tribal trust": PALETTE[3], "Private": PALETTE[2]}
    for k, v in stack.items():
        ax1.barh([0], [v], left=left, color=colors[k], height=0.5)
        ax1.text(left + v / 2, 0.45, f"{k}\n{v:.1f}%", ha="center", fontsize=9)
        left += v
    ax1.set_xlim(0, 100)
    ax1.set_ylim(-0.6, 1.0)
    ax1.set_yticks([])
    ax1.set_title("Ownership shares (federal = BLM 244M + USFS 193M + FWS 89M + NPS 80M acres…)",
                  fontsize=9.5, loc="left")
    ax1.text(1, -0.42,
             "Foreign persons: 3.6% of private ag land · largest private owner "
             "(Kroenke, 2.7M acres) = 0.12% of the US · the whole Land Report 100 = 1.9%",
             fontsize=8.5, color="#57606a")

    names = {"cropland": "Cropland", "grassland_pasture": "Pasture & range",
             "forest_use": "Forest-use", "urban": "Urban"}
    ks = list(names)
    ax2.barh([names[k] for k in ks][::-1], [uses[k] / 1e6 for k in ks][::-1],
             color=PALETTE[1])
    for i, k in enumerate(ks[::-1]):
        ax2.text(uses[k] / 1e6 + 8, i, f"{uses[k]/1e6:.0f}M", va="center", fontsize=9)
    ax2.set_title("What the land does (all ownership, M acres) — cities are 3%",
                  fontsize=9.5, loc="left")
    ax2.set_xlabel("million acres")

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax2.grid(alpha=0.25, axis="x")
    fig.text(0.01, -0.02,
             "Source: curated CRS R42346, USDA ERS/AFIDA, BIA, Land Report (econlab warehouse; citations in catalog)",
             fontsize=8, color="#57606a")
    fig.tight_layout()
    save(fig, "09_us_land")


def fig_world_forest() -> None:
    fo = forest_ownership()
    fig, ax = new_fig(
        "Who owns the world's forests (2015, FAO FRA)",
        subtitle="Share of forest area. World: 73% public. Mexico's ejidos put 58% in Indigenous & community hands; Nordic forests are private; Russia's are entirely state.",
        ylabel=None,
    )
    order = fo.drop("WORLD").sort_values("Public").index.tolist() + ["WORLD"]
    fo = fo.loc[order]
    left = np.zeros(len(fo))
    colors = {"Public": PALETTE[0], "Indigenous & community": PALETTE[3],
              "Other private": PALETTE[2], "Unknown/unreported": "#d0d7de"}
    for col, c in colors.items():
        ax.barh(fo.index, fo[col], left=left, color=c, label=col, height=0.72)
        left += fo[col].fillna(0).values
    ax.axhline(len(fo) - 1.5, color="#57606a", lw=0.8, ls=":")
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of forest area")
    ax.legend(fontsize=8.5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    source_note(ax, "Source: computed from FAO FRA 2020 bulk data (econlab warehouse)")
    save(fig, "09_world_forest")


def main() -> None:
    fig_us_land()
    fig_world_forest()


if __name__ == "__main__":
    main()
