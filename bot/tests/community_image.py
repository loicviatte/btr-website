"""YouTube Community poll image (Loïc 03.11): square render with a real episode's guest photo.
python tests/community_image.py [/opt/btr-bot/data/episodes/O_ZdYlKrdwU] [out_dir] → community-poll.jpg"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import community, posts  # noqa: E402

src = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/btr-bot/data/episodes/O_ZdYlKrdwU")
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.mkdtemp())
pj = json.loads((src / "posts.json").read_text())
cj = json.loads((src / "community.json").read_text())
shot = pj["shots"].get("poll:face") or next(v for k, v in pj["shots"].items() if v.get("who") == "guest")
q = (cj["items"].get("poll") or {}).get("question") or "Who should be at the top of UK DanceSport governance?"
pg = posts.pages("ycpoll", {"question": q}, {"face": shot}, {"guest": "Hannah Trever", "part": None})
assert pg[0]["H"] == 1080 and pg[0]["question"] == q
res = posts.render_pages(pg, out)
print(res)
assert not res[0]["overflow"], res[0]["overflow"]
it = {"text": "Intro.", "question": q, "options": ["A", "B"]}
print(community.image_caption(it))
assert q in community.image_caption(it) and "http" not in community.image_caption(it)
print("ok", res[0]["file"])
