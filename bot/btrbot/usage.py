"""What the bot spends: every Claude API call (and every Claude Code run) is logged with its estimated cost.

Prices in $ per million tokens (public list prices, Oct 2026; Haiku doubles past 100K input tokens per call):
input, output, cache write 5 min, cache write 1 h, cache read. The Console stays the source of truth.
"""
import json
import time
from pathlib import Path

PRICES = {
    "haiku": (0.10, 0.50, 0.125, 0.20, 0.01),
    "haiku_long": (0.50, 2.50, 0.625, 1.00, 0.05),
    "sonnet": (2.00, 10.00, 2.50, 4.00, 0.10),
    "opus": (4.00, 20.00, 5.00, 8.00, 0.20),
}

# Which model does what (env overrides: MODEL_CHAT, MODEL_CREATIVE, MODEL_WORK, MODEL_VISION_CHEAP, DEV_MODEL)
#   chat      → Haiku : talks with Loïc, understands what he wants, drives the bot through tools (~0.1-0.3 ¢/message)
#   creative  → Opus  : the hook (3 axes, title discussion, description): the product itself, a few cents per episode
#   work      → Sonnet: chapters, re-timing, picking the best frames
#   vision_cheap → Haiku: eyes open/closed check on the frame sheets
#   dev (Claude Code) → Opus by default: writes code, fewer broken attempts


def family(model: str) -> str:
    m = (model or "").lower()
    return "haiku" if "haiku" in m else "opus" if "opus" in m else "sonnet"


def cost(model: str, u) -> float:
    """u: the `usage` of an API response."""
    g = lambda k: int(getattr(u, k, 0) or 0)  # noqa: E731
    inp, out, cr = g("input_tokens"), g("output_tokens"), g("cache_read_input_tokens")
    cw = g("cache_creation_input_tokens")
    cc = getattr(u, "cache_creation", None)
    cw1h = int(getattr(cc, "ephemeral_1h_input_tokens", 0) or 0) if cc else 0
    cw5 = cw - cw1h
    fam = family(model)
    if fam == "haiku" and inp + cr + cw > 100_000:
        fam = "haiku_long"
    p = PRICES[fam]
    return (inp * p[0] + out * p[1] + cw5 * p[2] + cw1h * p[3] + cr * p[4]) / 1e6


class Ledger:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "usage.jsonl"

    def add(self, task: str, model: str, usd: float, **extra) -> None:
        try:
            with self.path.open("a") as f:
                f.write(json.dumps({"t": round(time.time()), "task": task, "model": model, "usd": round(usd, 5), **extra}) + "\n")
        except OSError:
            pass

    def record(self, task: str, model: str, resp) -> float:
        usd = cost(model, getattr(resp, "usage", None))
        u = getattr(resp, "usage", None)
        self.add(task, model, usd, inp=int(getattr(u, "input_tokens", 0) or 0), out=int(getattr(u, "output_tokens", 0) or 0),
                 cache_read=int(getattr(u, "cache_read_input_tokens", 0) or 0))
        return usd

    def summary(self, days: float = 1.0) -> str:
        since = time.time() - days * 86400
        by_task: dict[str, list] = {}
        total = 0.0
        try:
            lines = self.path.read_text().splitlines()
        except OSError:
            lines = []
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("t", 0) < since:
                continue
            k = f"{r.get('task')} ({family(r.get('model', ''))})"
            n, s = by_task.get(k, [0, 0.0])
            by_task[k] = [n + 1, s + float(r.get("usd", 0))]
            total += float(r.get("usd", 0))
        if not by_task:
            return "Aucune dépense enregistrée sur la période."
        rows = sorted(by_task.items(), key=lambda kv: -kv[1][1])
        head = "dernières 24 h" if days <= 1 else f"{int(days)} derniers jours"
        return f"Dépenses estimées ({head}) : {total:.2f} $\n" + "\n".join(f"- {k} : {s:.3f} $ ({n} appels)" for k, (n, s) in rows[:12])
