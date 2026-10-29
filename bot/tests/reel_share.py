"""Validated reel → ClickUp slot + Drive, offline (ClickUp and Drive mocked). Checks the slot choice on the real
calendar shape (« Reel 2/3 · Oti P2 », « Reel 1/6 · Ep Nov 3 », teasers), the task update, the new task when the
episode has no free slot, the description block (rewritten, not stacked) and the cover hook guard.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/reel_share.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import share  # noqa: E402
from btrbot.pipeline import cover_hook  # noqa: E402

EP = share.F_EPISODE


def task(tid, name, ep, status="to generate", due=0):
    return {"id": tid, "name": name, "status": {"status": status}, "due_date": str(due), "url": f"https://app.clickup.com/t/{tid}",
            "custom_fields": [{"id": EP, "value": ep}], "markdown_description": "Where: Instagram (Reels tab)\nTime: 20:00",
            "text_content": "Where: Instagram (Reels tab)\nTime: 20:00"}


TASKS = [task("p1", "Reel 1/3 · Oti P2 · They just don’t care", "Oti Mabuse P2", "posted", 1),
         task("p2", "Reel 2/3 · Oti P2", "Oti Mabuse P2", due=2),
         task("p3", "Reel 3/3 · Oti P2", "Oti Mabuse P2", due=3),
         task("t1", "Reel teaser · Ep Nov 3", "Episode of Nov 3", due=4),
         task("n1", "Reel 1/6 · Ep Nov 3", "Episode of Nov 3", due=5),
         task("o1", "Reel 2/6 · Oti P1", "Oti Mabuse P1", due=0),
         task("c1", "Carousel · Key moment · Oti P2", "Oti Mabuse P2", due=1)]
oti = datetime(2026, 10, 27, 17, tzinfo=timezone.utc)
label = share.episode_label("Oti Mabuse", "2")
assert label == "Oti Mabuse P2"
s1 = share.pick_slot(TASKS, label, "Oti Mabuse", "2", oti, set())
s2 = share.pick_slot(TASKS, label, "Oti Mabuse", "2", oti, {"p2"})
s3 = share.pick_slot(TASKS, label, "Oti Mabuse", "2", oti, {"p2", "p3"})
assert (s1 or {}).get("id") == "p2" and (s2 or {}).get("id") == "p3" and s3 is None, (s1, s2, s3)
# the episode of Nov 3 (placeholder slots, guest unknown when the calendar was made)
nov = datetime(2026, 11, 3, 17, tzinfo=timezone.utc)
s4 = share.pick_slot(TASKS, "Kiera Brunton", "Kiera Brunton", None, nov, set())
assert (s4 or {}).get("id") == "n1", s4
assert share.slot_name("Reel 2/3 · Oti P2", label, "Alone on Strictly") == "Reel 2/3 · Oti Mabuse P2 · Alone on Strictly"
# description: the task's lines are kept, the bot block replaces itself
item = {"duration": 46.6, "captions": {"instagram": "Line 1\nLine 2", "tiktok": "Line 1\n#dancesport"}}
d1 = share.description("Where: Instagram\nTime: 20:00", {"video": "V1", "cover": "C1", "folder": "F"}, item, "T", "Y", "29.10.2026")
d2 = share.description(d1, {"video": "V2", "cover": "C2", "folder": "F"}, item, "T", "Y", "30.10.2026")
assert d2.count(share.MARK) == 1 and "V2" in d2 and "V1" not in d2 and d2.startswith("Where: Instagram\nTime: 20:00"), d2
assert "```\nLine 1\nLine 2\n```" in d2
# pasted Google address
assert share.code_from("http://127.0.0.1:8765/?code=4/0Ab_x-y&scope=https://www.googleapis.com/auth/drive.file") == "4/0Ab_x-y"
assert share.code_from("salut") is None
# cover words must be said, in order
said = "And I was like, they just don't care. When you are on these shows, people care."
assert cover_hook({"small": "They just", "big": "don't", "gold": "care."}, said) == {"small": "They just", "big": "DON'T", "gold": "CARE."}
assert cover_hook({"small": "They never", "big": "DON'T", "gold": "CARE."}, said) is None
assert cover_hook({"small": "", "big": "CARE.", "gold": "THEY"}, said) is None
assert share.drive_error(Exception("Drive API has not been used in project 123 before or it is disabled. Enable it by "
                                   "visiting https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=123 then retry")
                         ).endswith("overview?project=123")
print("OK")
