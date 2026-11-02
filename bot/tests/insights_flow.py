"""Offline check of « BTR Data » (Simone): week bounds, episode pages, weekly block.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/insights_flow.py
"""
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import insights as I  # noqa: E402

L = I.TZ
s, e = I.week(datetime(2026, 11, 3, 18, 30, tzinfo=L))           # Tuesday evening: the week that just closed
assert s.strftime("%d.%m %H:%M") == "27.10 00:00" and e.strftime("%d.%m") == "03.11", (s, e)
s2, _ = I.week(datetime(2026, 11, 5, 12, 0, tzinfo=L))
assert s2.strftime("%d.%m") == "03.11"
assert I.short_title("Why She Walked Away | Break the Routine with Oti Mabuse (PART 2)") == "Oti Mabuse (PART 2)"
assert I.mmss(3725) == "1:02:05" and I.mmss(65) == "01:05"
lines = [[0, "Hello"], [60, "Strictly changed everything"], [120, "Judges"]]
assert I.said_at(lines, 90) == "Strictly changed everything"
curve = [(i / 100, 1.0 - i / 200 - (0.2 if i >= 40 else 0)) for i in range(101)]
assert abs(I.drops(curve)[0][0] - 0.40) < 0.011 and I.at_share(curve, 0.5) is not None
print("OK helpers")


class Docs:
    def __init__(self):
        self.pages, self.updates = [], []

    def create(self, name, content, parent=None):
        self.pages.append((name, parent, len(content)))
        return f"p{len(self.pages)}"

    def update(self, page, content, mode="replace"):
        self.updates.append((page, mode, content))


st = I.State(Path(tempfile.mkdtemp()))
docs = Docs()
eps = [{"id": "A", "title": "T | Break the Routine with Kiera Brunton", "publishedAt": "2026-07-01T16:00:00Z", "views": 300},
       {"id": "B", "title": "X | Break the Routine with Oti Mabuse (PART 2)", "publishedAt": "2026-10-27T17:00:00Z", "views": 900},
       {"id": "C", "title": "New | Break the Routine with Flavia Cacace", "publishedAt": "2026-11-03T17:00:00Z", "views": 50}]
trans = {"A": [[i * 5, "word " * 30] for i in range(400)], "B": [[0, "hi"], [5, "Strictly"]]}
digests = []
made = I.episode_pages(st, docs, lambda t, d, x: digests.append(t) or "## Guest\nx", eps, trans,
                       local=lambda vid: [[0, "local srt"]] if vid == "C" else None)
assert made == [e["title"] for e in eps], made
names = [p[0] for p in docs.pages]
assert names[0] == "2026-07-01 · Kiera Brunton" and "Transcript (1/3)" in names and "Transcript" in names
assert st.data["episodes"] == {"A": "p1", "B": "p5", "C": "p7"}, st.data["episodes"]
assert I.episode_pages(st, docs, lambda *a: "x", eps, trans) == []                 # written once
assert any(u[1] == "append" and "## Guest" in u[2] for u in docs.updates)          # the digest goes in after the header
st.data["digested"].remove("B")                                                    # a digest that was lost: written again
n = len(docs.pages)
assert I.episode_pages(st, docs, lambda *a: "```md\n## Guest\ny\n```", eps, trans) == [eps[1]["title"]] and len(docs.pages) == n
assert docs.updates[-1] == ("p5", "append", "\n## Guest\ny")
print("OK episode pages")

now = datetime(2026, 11, 3, 18, 30, tzinfo=L)
yt_json = {"subscribers": 280, "channelViews": 50000, "episodes": eps}
prev = {"ig": {"followers": 1350}, "tt": {"followers": 10}, "yt": {"subscribers": 250, "episodes": {"B": 700}}}
ig_posts = [{"ts": (now - timedelta(days=3)).isoformat(), "type": "REELS", "kind": "VIDEO", "link": "l1", "caption": "Oti | on judges",
             "views": 5000, "reach": 4000, "likes": 200, "comments": 9, "saved": 30, "shares": 12},
            {"ts": (now - timedelta(hours=2)).isoformat(), "type": "FEED", "kind": "CAROUSEL_ALBUM", "link": "l2", "caption": "Topics",
             "views": 300, "reach": 250, "likes": 20, "comments": 1, "saved": 4, "shares": 0},
            {"ts": (now - timedelta(days=10)).isoformat(), "type": "REELS", "kind": "VIDEO", "link": "old", "caption": "old"}]
tt = {"followers": 15, "likes": 400, "videos": [["20261030", "123", 777], ["20261001", "9", 5]]}
snap = I.snapshot(yt_json, {"spotify": {"followers": 120, "asOf": "2026-11-02"}}, (1386, ig_posts), tt, now)
an = {"week": {"S1": {"views": 1200, "averageViewPercentage": 80.0, "subscribersGained": 3}, "B": {"views": 200}},
      "life": {"B": {"averageViewPercentage": 31.4, "averageViewDuration": 1500}}, "meta": {"S1": {"title": "Short one"},
      "B": {"title": "X | Break the Routine with Oti Mabuse (PART 2)", "seconds": 3600}}, "retention": {"B": curve}}
trans["B"] = [[i, f"line at {i}"] for i in range(0, 3600, 30)]
txt = I.week_block(*I.week(now), now, snap, prev, yt_json, ig_posts, tt, an, trans)
print(txt[:600])
assert "Semaine du mar. 27.10 au lun. 02.11 2026" in txt and "| Instagram | 1386 | +36 |" in txt
assert "| YouTube | 280 | +30 |" in txt and "Flavia Cacace le 2026-11-03" in txt
assert "Oti / on judges" in txt and "(nouvelle sem.)" in txt and "old" not in txt.split("### TikTok")[0].split("Instagram : posts")[1]
assert "| 30.10 | 123 | 777 |" in txt and "| Oti Mabuse (PART 2) | 2026-10-27 | 900 | +200 | 31 % | 25:00 |" in txt
assert "Short one" in txt and "chute à 24:00" in txt and "line at" in txt
txt2 = I.week_block(*I.week(now), now, snap, {}, yt_json, None, None, None, trans)
assert "(1er relevé)" in txt2 and "pas encore connecté" in txt2
print("OK week block")

ps = I.pieces("a" * 5000 + "\n" + "b" * 5000 + "\n" + "c" * 9000, 8000)
assert ps[0] == "a" * 5000 and ps[1] == "b" * 5000 and "".join(ps[2:]) == "c" * 9000 and all(len(x) <= 8000 for x in ps)
print("OK pieces")
