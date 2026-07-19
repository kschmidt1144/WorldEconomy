"""The cross-checking panel: ask several AI models the same thing, measure agreement.

Two verbs:
  run_panel(question)   — each model answers; we extract a comparable ANSWER +
                          CONFIDENCE and score consensus (numeric spread if the
                          answers are numbers, else text similarity).
  run_crosscheck(claim) — each model votes agree / disagree / uncertain on a
                          stated claim; we tally the verdict.

Nothing here trusts a single model — divergence between models is itself a
finding (it flags a contested or under-determined claim). Runs are appended to
data/panel/runs.jsonl for reproducibility.
"""

from __future__ import annotations

import json
import re
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field

from ..config import DATA
from .providers import Provider, ask, available_providers

PANEL_SYSTEM = (
    "You are one member of a panel of AI models, each asked the same question "
    "independently so a researcher can measure how much frontier models agree. "
    "Reason briefly (2-4 sentences) from your own knowledge, then end with EXACTLY "
    "these two lines:\nANSWER: <a single number with its unit, or one short phrase>\n"
    "CONFIDENCE: <a decimal 0.0-1.0>\nGive your best point estimate even if uncertain; "
    "do not refuse or hedge into a range."
)
CROSSCHECK_SYSTEM = (
    "You are one member of a panel independently fact-checking a claim. Reason "
    "briefly, then end with EXACTLY these two lines:\nVERDICT: <agree|disagree|uncertain>\n"
    "CONFIDENCE: <a decimal 0.0-1.0>"
)
_STOP = {"the", "and", "for", "with", "that", "this", "are", "was", "from", "has",
         "about", "into", "than", "over", "per", "its", "not", "but", "have"}


@dataclass
class Answer:
    name: str
    label: str
    tier: str
    text: str = ""
    answer: str = ""          # extracted ANSWER/VERDICT line
    confidence: float | None = None
    number: float | None = None
    latency_s: float | None = None
    error: str | None = None


@dataclass
class PanelResult:
    question: str
    kind: str                 # "panel" | "crosscheck"
    answers: list[Answer] = field(default_factory=list)
    mode: str = ""            # "numeric" | "text" | "verdict"
    consensus: float | None = None      # 0-100
    summary: dict = field(default_factory=dict)


def _field(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{key}\s*[:\-]\s*(.+)$", text, flags=re.I | re.M)
    return m.group(1).strip() if m else None


def extract_answer(text: str) -> str:
    return (_field(text, "ANSWER") or _field(text, "VERDICT")
            or (text.strip().splitlines() or [""])[-1].strip())


def extract_confidence(text: str) -> float | None:
    raw = _field(text, "CONFIDENCE")
    if raw:
        m = re.search(r"[-+]?\d*\.?\d+", raw)
        if m:
            return max(0.0, min(1.0, float(m.group())))
    return None


def parse_number(s: str) -> float | None:
    """First numeric value in `s`, scaled by any trillion/billion/million word."""
    s2 = s.replace(",", "")
    m = re.search(r"[-+]?\d*\.?\d+", s2)
    if not m:
        return None
    x = float(m.group())
    low = s2.lower()
    tail = low[m.end():m.end() + 12]
    for kw, mult in [("trillion", 1e12), ("billion", 1e9), ("million", 1e6)]:
        if kw in low:
            return x * mult
    for suf, mult in [("t", 1e12), ("b", 1e9), ("m", 1e6)]:
        if re.match(rf"\s*{suf}\b", tail):
            return x * mult
    return x


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) >= 3 and t not in _STOP}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _ask_one(p: Provider, prompt: str, system: str) -> Answer:
    import time as _t  # local: Date/time is fine outside the workflow sandbox

    a = Answer(p.name, p.label, p.tier)
    t0 = _t.monotonic()
    try:
        a.text = ask(p, prompt, system)
        a.latency_s = round(_t.monotonic() - t0, 1)
        a.answer = extract_answer(a.text)
        a.confidence = extract_confidence(a.text)
        a.number = parse_number(a.answer)
    except Exception as e:  # one provider failing must not sink the panel
        a.error = f"{type(e).__name__}: {str(e)[:160]}"
    return a


def _score_numeric(nums: list[float]) -> tuple[float, dict]:
    mean = statistics.fmean(nums)
    if len(nums) < 2 or mean == 0:
        return (100.0 if len(nums) >= 2 else 0.0), {"mean": mean, "min": min(nums), "max": max(nums)}
    cv = statistics.stdev(nums) / abs(mean)
    return round(100 * (1 - min(cv, 1.0)), 1), {
        "mean": round(mean, 4), "min": min(nums), "max": max(nums), "cv": round(cv, 3), "n": len(nums)}


def _score_text(answers: list[str]) -> tuple[float, dict]:
    pairs = [(i, j) for i in range(len(answers)) for j in range(i + 1, len(answers))]
    if not pairs:
        return 0.0, {}
    sims = [_jaccard(answers[i], answers[j]) for i, j in pairs]
    return round(100 * statistics.fmean(sims), 1), {"mean_pairwise_jaccard": round(statistics.fmean(sims), 3)}


def run_panel(question: str, providers: list[Provider] | None = None,
              system: str = PANEL_SYSTEM, kind: str = "panel") -> PanelResult:
    provs = providers if providers is not None else available_providers()
    res = PanelResult(question=question, kind=kind)
    if not provs:
        res.summary = {"note": "no providers configured — add an API key (see `econ panel-models`)"}
        return res

    with ThreadPoolExecutor(max_workers=min(8, len(provs))) as ex:
        futs = {ex.submit(_ask_one, p, question, system): p for p in provs}
        res.answers = [f.result() for f in as_completed(futs)]
    res.answers.sort(key=lambda a: a.name)

    ok = [a for a in res.answers if a.error is None and a.answer]
    if kind == "crosscheck":
        verdicts = [re.sub(r"[^a-z]", "", a.answer.lower())[:9] for a in ok]
        tally = {v: verdicts.count(v) for v in ("agree", "disagree", "uncertain")}
        res.mode = "verdict"
        res.consensus = round(100 * max(tally.values()) / len(ok), 1) if ok else None
        res.summary = {"tally": tally, "n": len(ok)}
        return res

    nums = [a.number for a in ok if a.number is not None]
    if len(nums) >= 2 and len(nums) >= 0.6 * len(ok):
        res.mode = "numeric"
        res.consensus, res.summary = _score_numeric(nums)
    else:
        res.mode = "text"
        res.consensus, res.summary = _score_text([a.answer for a in ok])
    return res


def run_crosscheck(claim: str, providers: list[Provider] | None = None) -> PanelResult:
    return run_panel(f"Claim to fact-check: {claim}", providers,
                     system=CROSSCHECK_SYSTEM, kind="crosscheck")


def log_run(res: PanelResult, stamp: str) -> None:
    out = DATA / "panel"
    out.mkdir(parents=True, exist_ok=True)
    rec = {"ts": stamp, "kind": res.kind, "question": res.question, "mode": res.mode,
           "consensus": res.consensus, "summary": res.summary,
           "answers": [asdict(a) for a in res.answers]}
    with (out / "runs.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")


def format_result(res: PanelResult) -> str:
    lines = [f"Question: {res.question}", ""]
    if not res.answers:
        return "\n".join(lines + [str(res.summary.get("note", "no answers"))])
    for a in res.answers:
        if a.error:
            lines.append(f"  ✗ {a.label:<34} {a.error}")
        else:
            conf = f"  conf {a.confidence:.2f}" if a.confidence is not None else ""
            lines.append(f"  • {a.label:<34} {a.answer[:70]}{conf}  [{a.latency_s}s]")
    lines.append("")
    if res.mode == "numeric":
        s = res.summary
        lines.append(f"CONSENSUS {res.consensus}/100 (numeric) — mean {s.get('mean')}, "
                     f"range {s.get('min')}–{s.get('max')}, CV {s.get('cv')} over {s.get('n')} models")
    elif res.mode == "verdict":
        t = res.summary.get("tally", {})
        lines.append(f"CONSENSUS {res.consensus}/100 — agree {t.get('agree', 0)}, "
                     f"disagree {t.get('disagree', 0)}, uncertain {t.get('uncertain', 0)}")
    elif res.mode == "text":
        lines.append(f"CONSENSUS {res.consensus}/100 (text similarity — the models phrase it "
                     f"differently; read the answers, not just the score)")
    return "\n".join(lines)
