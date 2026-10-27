"""Re-render one thumbnail of an episode with the CURRENT code (used by dev mode to preview a template change).

    python -m btrbot.rerender <video_id> <youtube|instagram|square>

Same picked frames and quote as the episode state; prints the path of the new JPEG. Never touches YouTube.
"""
import os
import sys
from pathlib import Path

from .pipeline import render_thumbs
from .state import Episode


def main() -> None:
    vid, design = sys.argv[1], sys.argv[2]
    if design not in ("youtube", "instagram", "square"):
        raise SystemExit("design: youtube | instagram | square")
    data = Path(os.environ.get("DATA_DIR", "/opt/btr-bot/data"))
    models = Path(os.environ.get("MODELS_DIR", "/opt/btr-bot/models"))
    ep = Episode(data, vid)
    if not (ep.get("pick_guest") and ep.get("pick_marius") and ep.get("final")):
        raise SystemExit("this episode has no picked frames / quote yet")
    print(render_thumbs(ep, models, design)[design])


if __name__ == "__main__":
    main()
