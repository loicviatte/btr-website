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
assert share.code_from("127.0.0.1:8765/?iss=https://accounts.google.com&code=4/0AUn6Hd_x-Y&scope=https://www.googleapis.com/auth/drive.file") == "4/0AUn6Hd_x-Y"
assert share.code_from("http://127.0.0.1:8765/?code=4%2F0AbC&scope=x") == "4/0AbC"
# cover words must be said, in order
said = "And I was like, they just don't care. When you are on these shows, people care."
assert cover_hook({"small": "They just", "big": "don't", "gold": "care."}, said) == {"small": "They just", "big": "DON'T", "gold": "CARE."}
assert cover_hook({"small": "They never", "big": "DON'T", "gold": "CARE."}, said) is None
assert cover_hook({"small": "", "big": "CARE.", "gold": "THEY"}, said) is None
assert share.drive_error(Exception("Drive API has not been used in project 123 before or it is disabled. Enable it by "
                                   "visiting https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=123 then retry")
                         ).endswith("overview?project=123")
print("OK")

# ---- whole ClickUp step with a fake ClickUp: Instagram slot, Shorts-only task, change of mind both ways
import copy  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
from btrbot.config import Settings  # noqa: E402
from btrbot.pipeline import Pipeline  # noqa: E402
from btrbot.state import Episode  # noqa: E402

DB = {t["id"]: copy.deepcopy(t) for t in TASKS}
LOG = []


class FakeCU:
    def __init__(self, token):
        if not token:
            raise share.NotConnected("ClickUp")

    def tasks(self, list_id=None):
        return [copy.deepcopy(t) for t in DB.values()]

    def task(self, tid):
        if tid not in DB:
            raise RuntimeError("ClickUp 404")
        return copy.deepcopy(DB[tid])

    def update(self, tid, **f):
        LOG.append(("update", tid, f.get("status")))
        t = DB[tid]
        t["name"] = f.get("name", t["name"])
        t["status"] = {"status": f.get("status", t["status"]["status"])}
        if "markdown_content" in f:
            t["markdown_description"] = t["text_content"] = f["markdown_content"]

    def set_field(self, tid, field, value):
        pass

    def create(self, list_id=None, **f):
        tid = f"new{len(DB)}"
        DB[tid] = {"id": tid, "name": f["name"], "status": {"status": f["status"]}, "custom_fields": f["custom_fields"],
                   "markdown_description": f["markdown_content"], "text_content": f["markdown_content"],
                   "url": f"https://app.clickup.com/t/{tid}"}
        LOG.append(("create", tid, f["name"]))
        return copy.deepcopy(DB[tid])

    def delete(self, tid):
        LOG.append(("delete", tid))
        DB.pop(tid)

    def attach(self, tid, path):
        LOG.append(("attach", tid))


share.ClickUp = FakeCU
cfg = Settings()
share.Secrets(cfg.data_dir).set(clickup_token="pk_test")
p = Pipeline(cfg)
p.yt = type("Y", (), {"video": lambda self, vid: {"snippet": {"publishedAt": "2026-10-27T17:00:00Z"}}})()
ep = Episode(cfg.data_dir, "PjDZ8X_JWY0")
ep["guest_name"], ep["part"], ep["title"] = "Oti Mabuse", "2", "Oti Mabuse Part 2"
assert len(p.reel_ig_slots(ep, set())) == 2
it = {"file": "/nonexistent.mp4", "duration": 40, "captions": {"instagram": "IG", "tiktok": "TT #x"}, "title": "Alone"}
r1 = p.reel_share(ep, 1, dict(it), set(), True)
assert r1["clickup_task"] == "p2" and r1["clickup_kind"] == "slot" and DB["p2"]["status"]["status"] == "approved", r1
assert DB["p2"]["name"] == "Reel 2/3 · Oti Mabuse P2 · Alone"
r2 = p.reel_share(ep, 2, dict(it, title="Yacht"), {"p2"}, False)                       # TikTok + Shorts only
assert r2["clickup_kind"] == "short" and DB[r2["clickup_task"]]["name"].startswith("Short · Oti Mabuse P2")
assert "IG" not in DB[r2["clickup_task"]]["markdown_description"] and "TT #x" in DB[r2["clickup_task"]]["markdown_description"]
assert len(p.reel_ig_slots(ep, {"p2", r2["clickup_task"]})) == 1
# reel 1 finally not on Instagram: its slot is given back, a Shorts task is made
r1b = p.reel_share(ep, 1, dict(it, clickup_task="p2", clickup_kind="slot", clickup_orig=r1["clickup_orig"]), {r2["clickup_task"]}, False)
assert DB["p2"]["name"] == "Reel 2/3 · Oti P2" and DB["p2"]["status"]["status"] == "to generate", DB["p2"]
assert share.MARK not in DB["p2"]["markdown_description"] and r1b["clickup_kind"] == "short" and r1b.get("clickup_freed")
# reel 2 finally on Instagram: its Shorts task (made by the bot) is deleted, it takes the free slot
r2b = p.reel_share(ep, 2, dict(it, title="Yacht", clickup_task=r2["clickup_task"], clickup_kind="short"), {r1b["clickup_task"]}, True)
assert r2["clickup_task"] not in DB and r2b["clickup_task"] == "p2" and r2b["clickup_kind"] == "slot", (r2b, LOG)
assert "drive_error" in r1 and "pas encore connecté" in r1["drive_error"]
print("OK clickup")

# ---- Drive: one folder per guest, calendar names, same file (id) when re-filed
from datetime import datetime as _dt  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

assert share.file_base(_dt(2026, 10, 31, tzinfo=ZoneInfo("Europe/London")), 13, "Oti Mabuse", True,
                       "Alone on Strictly: “why not?”") == "1031_EP13_OTI-MABUSE_FEED_ALONE-ON-STRICTLY-WHY-NOT"
assert share.file_base(_dt(2026, 11, 2), 13, "Oti Mabuse", False, "Yacht").endswith("_SHORTS_YACHT")
assert share.post_date({"due_date": "1793476800000"}).strftime("%m%d") == "10" + "31"
assert share.file_id("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/view?usp=drivesdk") == "1AbCdEfGhIjKlMnOpQrStUv"
FILES, FOLDERS = {}, {}


class FakeDrive:
    def __init__(self, secrets, client):
        pass

    def folder(self, name, parent=None):
        return FOLDERS.setdefault((name, parent), f"fold{len(FOLDERS)}")

    def folder_link(self, fid):
        return f"https://drive.google.com/drive/folders/{fid}"

    def put(self, path, folder_id, name, mime, fid=None):
        fid = fid if fid in FILES else f"1file{len(FILES):020d}"
        FILES[fid] = (folder_id, name)
        return {"id": fid, "webViewLink": f"https://drive.google.com/file/d/{fid}/view"}

    def drop_empty_folders(self, root, keep):
        pass


share.Drive = FakeDrive
DB.clear()
DB.update({t["id"]: copy.deepcopy(t) for t in TASKS})
DB["p2"]["due_date"], DB["p3"]["due_date"] = "1793476800000", "1793563200000"   # 31 Oct / 1 Nov, 20:00 London
assert p.ep_number(ep) == 13
it2 = dict(it, file=__file__, title="Alone on Strictly")
a = p.reel_share(ep, 1, dict(it2), set(), True)
assert a["file_base"] == "1031_EP13_OTI-MABUSE_FEED_ALONE-ON-STRICTLY", a["file_base"]
assert a["clickup_task"] == "p2", a
vid = a["drive_ids"]["video"]
assert FILES[vid] == (FOLDERS[("Oti Mabuse", "fold0")], a["file_base"] + ".mp4"), (FILES, FOLDERS)
assert a["file_base"] + ".mp4" in DB["p2"]["markdown_description"]
b = p.reel_share(ep, 1, dict(it2, **{k: a[k] for k in ("clickup_task", "clickup_kind", "clickup_orig", "drive_ids", "links")}),
                 set(), False)                                       # now TikTok + Shorts only: same file, renamed
assert b["drive_ids"]["video"] == vid and FILES[vid][1].split("_")[3] == "SHORTS", FILES[vid]
ep2 = Episode(cfg.data_dir, "NEWGUEST001")
ep2["guest_name"] = "Kiera Brunton"
assert p.ep_number(ep2) == 1
ep3 = Episode(cfg.data_dir, "NEWGUEST002")
ep3["guest_name"] = "Someone New"
assert p.ep_number(ep3) == 14 and p.ep_number(ep3) == 14
print("OK drive")
