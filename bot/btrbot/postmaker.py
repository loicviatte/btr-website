"""Makes an episode's carousels and stories (posts.py = the pure parts): ClickUp plan, content, shots, render, filing,
publishing. Called from bot.py in the background (one heavy job at a time)."""
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

from . import frames, posts, prompts, share, srt
from .faces import MATCH, NOT_MATCH, sharpness
from .pipeline import part_number, said_exactly

log = logging.getLogger("btrbot.postmaker")
EXACT = {"moment": ["hook", "quote"], "rapid": ["question", "answer"], "chain": ["question"], "qa": ["question", "answer"],
         "quote": ["quote"]}


class Maker:
    def __init__(self, pipe, data_dir: Path):
        self.pipe, self.cfg, self.data_dir = pipe, pipe.cfg, data_dir

    # ------------------------------------------------------------ plan
    def clickup(self):
        sec = share.Secrets(self.data_dir)
        return share.ClickUp(sec.get("clickup_token"))

    def episode_tasks(self, ep, tasks: list | None = None) -> dict:
        """kind → the episode's ClickUp task (any status), earliest first."""
        guest = ep.get("guest_name") or ""
        part = part_number(ep)
        if tasks is None:
            tasks = self.clickup().tasks()
        ep_date = None
        if ep.get("release_at"):
            try:
                ep_date = datetime.fromisoformat(ep["release_at"])
            except ValueError:
                ep_date = None
        if ep_date is None:
            try:
                ep_date = share.episode_date(self.pipe.yt.video(ep.video_id))
                ep["release_at"] = ep_date.isoformat() if ep_date else ""
                ep.save()
            except Exception:  # noqa: BLE001
                pass
        label = share.episode_label(guest, part)
        out = {}
        for t in sorted(tasks, key=lambda t: int(t.get("due_date") or 9e15)):
            k = posts.task_kind(t.get("name", ""))
            if k and k not in out and guest and share.matches_episode(t, label, guest, part, ep_date):
                out[k] = t
        return out

    def plan(self, ep, st: posts.PostState, only: list[str] | None = None) -> dict:
        """The episode's carousels / stories = its ClickUp tasks: made when « to generate » (or the bot's own); a task
        made by hand or already posted is left alone. The default rotation only when the episode has NO such task."""
        try:
            all_t = self.episode_tasks(ep)
        except Exception as e:  # noqa: BLE001
            log.warning("clickup plan: %s", e)
            all_t = {}
        mine_ids = {i.get("task") for i in st.items.values()}

        def mine(t):
            status = (t.get("status") or {}).get("status", "").lower()
            text = t.get("text_content") or t.get("description") or ""
            return status == "to generate" or (status == "generated" and (share.MARK in text or t["id"] in mine_ids))
        items = {k: {"kind": k, "task": t["id"], "name": t.get("name", "")} for k, t in all_t.items() if mine(t)}
        st.data["from_clickup"] = bool(all_t)
        if not all_t:
            items = posts.default_items(self.pipe.ep_number(ep))
        if only:                                       # asked by Loïc: made even if done by hand, linked to its task
            items = {k: {"kind": k, "task": (all_t.get(k) or {}).get("id"), "name": (all_t.get(k) or {}).get("name")
                         or posts.LABEL[k]} for k in only if k in posts.LABEL}
        for k, v in items.items():
            cur = st.items.setdefault(k, {})
            if cur.get("status") in ("ok", "posted"):
                continue
            cur.update(kind=v["kind"], task=v.get("task") or cur.get("task"), name=v["name"])
        for k, cur in st.items.items():                # link what was made before the task was found
            t = all_t.get(cur.get("kind", k))
            if t and not cur.get("task") and (t.get("status") or {}).get("status", "").lower() != "posted":
                cur["task"] = t["id"]
        st.save()
        return items

    # ------------------------------------------------------------ content
    def _avoid(self, ep) -> str:
        from .state import Reels
        try:
            rs = Reels.of(ep)
            cands = {c["n"]: c for c in rs.data.get("cands", [])}
            out = []
            for k, it in rs.data.get("items", {}).items():
                c = cands.get(int(k)) or {}
                if it.get("status") == "ok" or it.get("filed"):
                    out.append(f"- {c.get('title', '')}: {c.get('start', c.get('start_s', ''))} → {c.get('end', c.get('end_s', ''))}")
            return "\n".join(out) or "(none)"
        except Exception:  # noqa: BLE001
            return "(none)"

    def content(self, ep, st: posts.PostState, keys: list[str], feedback: str = "") -> list[str]:
        """Opus writes the texts; every EXACT field is checked against the transcript (one retry). Returns warnings."""
        cues = self.pipe.cues(ep)
        if not cues:
            raise RuntimeError("pas de transcription pour cet épisode (SRT DaVinci ou sous-titres YouTube)")
        said = srt.plain_text(cues)
        timed = srt.timed_text(cues, 20)
        guest = ep.get("guest_name") or "the guest"
        part = part_number(ep)
        chapters = ep.get("chapters") or []
        kinds = [st.items[k]["kind"] for k in keys]
        blocks = ",\n".join(prompts.POSTS_BLOCKS[k] for k in kinds if prompts.POSTS_BLOCKS.get(k))
        text = prompts.POSTS.format(
            title=(ep.get("final") or {}).get("title") or ep.get("title", ""), guest=guest,
            part_line=f" This is Part {part}." if part else "",
            chapters="\n".join(f"{i}: {t} {n}" for i, (t, n) in enumerate(chapters)) or "(no chapters)",
            avoid=self._avoid(ep), feedback=f"Loïc's feedback to apply: {feedback}\n" if feedback else "", blocks=blocks)
        res = self.pipe.llm.posts_content(timed, text) if blocks else {}
        errs = self._check(res, kinds, said, chapters)
        if errs:
            fix = text + "\n\nYour first answer:\n" + json.dumps(res, ensure_ascii=False) + "\n\n" + \
                prompts.POSTS_FIX.format(errors="\n".join(f"- {e}" for e in errs))
            try:
                res2 = self.pipe.llm.posts_content(timed, fix)
                if len(self._check(res2, kinds, said, chapters)) < len(errs):
                    res = res2
            except Exception:  # noqa: BLE001
                log.exception("posts fix")
        warnings = self._clean(res, kinds, said, cues, chapters)
        c = st.data.setdefault("content", {})
        c["guest_title"] = posts.clean(res.get("guest_title")) or c.get("guest_title") or ""
        c["pronoun"] = res.get("pronoun") if res.get("pronoun") in ("she", "he", "they") else c.get("pronoun", "they")
        for k in keys:
            kind = st.items[k]["kind"]
            if kind in res and not res.get(kind) and kind != "teaser":
                st.items[k]["skip"] = "rien dans l'épisode pour ce format"
                continue
            if kind in res or kind == "teaser":
                st.items[k].pop("skip", None)
                c[k] = res.get(kind) or {}
                st.items[k]["warn"] = [w for w in warnings if w.startswith(kind + ":")]
                if kind in posts.B_OK and isinstance(c[k], dict) and "b" in c[k] and "b" not in st.items[k]:
                    st.items[k]["b"] = bool(c[k].get("b"))
        st.save()
        return warnings

    @staticmethod
    def _check(res: dict, kinds: list[str], said: str, chapters: list) -> list[str]:
        errs = []
        for kind in kinds:
            c = res.get(kind)
            if not isinstance(c, dict):
                continue
            if kind == "moment":
                for i, s in enumerate(c.get("sentences") or []):
                    if not said_exactly(s.get("text", ""), said):
                        errs.append(f'moment.sentences[{i}].text: "{s.get("text", "")}"')
            if kind == "topics":
                for i, it in enumerate(c.get("items") or []):
                    if not said_exactly(it.get("quote", ""), said):
                        errs.append(f'topics.items[{i}].quote: "{it.get("quote", "")}"')
            for f in EXACT.get(kind, []):
                v = posts.clean(c.get(f))
                if v and not said_exactly(v, said):
                    errs.append(f'{kind}.{f}: "{v}"')
        return errs

    @staticmethod
    def _clean(res: dict, kinds: list[str], said: str, cues, chapters: list) -> list[str]:
        """Drops what is still not exact, pins the times from the captions, fills « WATCH AT » from the chapters."""
        warn = []
        for kind in kinds:
            c = res.get(kind)
            if not isinstance(c, dict):
                if kind not in ("teaser",) and kind in res:
                    warn.append(f"{kind}: rien de trouvé dans l'épisode")
                continue
            if kind == "moment":
                ok = []
                for s in c.get("sentences") or []:
                    if said_exactly(s.get("text", ""), said):
                        t = posts.find_time(cues, s["text"])
                        s["t"] = t if t is not None else posts.secs(s.get("t"))
                        ok.append(s)
                if len(ok) < len(c.get("sentences") or []):
                    warn.append(f"moment: {len(c['sentences']) - len(ok)} phrase(s) non exacte(s) retirée(s)")
                c["sentences"] = ok[:8] if len(ok) >= 8 else ok[: len(ok) // 2 * 2]
            if kind == "topics":
                ok = []
                for it in c.get("items") or []:
                    if not said_exactly(it.get("quote", ""), said):
                        continue
                    it["qt"] = posts.find_time(cues, it["quote"])
                    try:
                        ch = chapters[int(it.get("chapter"))]
                        it["watch"], it["start"] = ch[0], posts.secs(ch[0])
                    except (TypeError, ValueError, IndexError):
                        t = it["qt"] if it["qt"] is not None else posts.secs(it.get("t")) or 0
                        it["watch"], it["start"] = posts.tc(t), t
                    ok.append(it)
                if len(ok) < len(c.get("items") or []):
                    warn.append(f"topics: {len(c['items']) - len(ok)} sujet(s) sans citation exacte retiré(s)")
                c["items"] = ok[:6]
            for f in EXACT.get(kind, []):
                v = posts.clean(c.get(f))
                if v and not said_exactly(v, said):
                    warn.append(f"{kind}: « {v} » n'est pas exact, retiré")
                    c[f] = ""
                elif v:
                    c[f] = v
            for f, tf in (("quote", "t"), ("question", "t_q" if kind == "qa" else "t"), ("answer", "t_a")):
                if f in EXACT.get(kind, []) and c.get(f):
                    t = posts.find_time(cues, c[f])
                    if t is not None and (tf != "t" or kind in ("quote", "rapid", "chain")):
                        c[tf] = t
        return warn

    # ------------------------------------------------------------ shots
    def _scan(self, ep) -> list[tuple[float, Path]]:
        video = frames.download_scan_copy(ep.video_id, ep.file("scan.mp4"), self.cfg.ytdlp_cookies)
        return frames.sample(video, ep.dir / "frames", 2.0)

    def _classify(self, ep, fr: list[tuple[float, Path]], times: set[float]) -> list[dict]:
        import cv2
        cache_f = ep.file("posts_scan.json")
        try:
            cache = json.loads(cache_f.read_text())
        except (OSError, ValueError):
            cache = {}
        faces = self.pipe.faces
        out = []
        for t, p in fr:
            if t not in times:
                continue
            key = f"{t:.1f}"
            if key not in cache:
                img = cv2.imread(str(p))
                if img is None:
                    continue
                H, W = img.shape[:2]
                fs = faces.analyse(img)
                info = posts.classify(fs, W, H, MATCH, 0.2)
                if info["kind"] in ("guest", "marius") and fs:
                    f = max(fs, key=lambda f: f.box[3])
                    info["sharp"] = sharpness(img, f.box)
                else:
                    g = cv2.cvtColor(cv2.resize(img, (640, 360)), cv2.COLOR_BGR2GRAY)
                    info["sharp"] = float(cv2.Laplacian(g, cv2.CV_64F).var())
                    if info["kind"] == "noface" and float(g.mean()) < 25:
                        info["kind"] = None                    # black / fade frame
                cache[key] = info
            if cache[key].get("kind"):
                out.append({"t": t, "file": str(p), **cache[key]})
        cache_f.write_text(json.dumps(cache))
        return out

    def shots(self, ep, st: posts.PostState, keys: list[str], again: set[str] | None = None,
              redo: set[str] | None = None, want: dict | None = None) -> list[str]:
        """Chooses and grabs in 4K every photo the items need. `again`: item keys whose photos all change; `redo`: only
        these photos (« moment:m3 », « topics:t2 ») change, the others stay; `want`: sid → {"t": seconds, "who": …}
        when Loïc says which moment or which kind of shot."""
        fr = self._scan(ep)
        if not fr:
            raise RuntimeError("pas d'images de l'épisode")
        c_all = st.data.get("content", {})
        shots = st.data.setdefault("shots", {})
        again, redo, want = again or set(), redo or set(), want or {}
        reqs = []
        for k in keys:
            kind = st.items[k]["kind"]
            for nd in posts.needs(kind, c_all.get(k) or {}):
                nd = dict(nd, key=k, sid=f"{k}:{nd['id']}")
                if nd["sid"] in shots and k not in again and nd["sid"] not in redo:
                    continue
                w = want.get(nd["sid"]) or {}
                if w.get("t") is not None:
                    nd.update(t=float(w["t"]), win=20, after=False)
                if w.get("who") in ("guest", "marius", "both", "wide", "noface"):
                    nd["who"] = w["who"]
                old = (shots.get(nd["sid"]) or {}).get("face") or {}
                if w.get("size") in ("smaller", "bigger") and old.get("fh"):
                    nd["fh"] = old["fh"] * (0.72 if w["size"] == "smaller" else 1.35)
                    if nd.get("t") is None and (shots.get(nd["sid"]) or {}).get("t") is not None:
                        nd["t"] = shots[nd["sid"]]["t"]
                reqs.append(nd)
        warn = []
        if not reqs:
            return warn
        times = {t for i, (t, _) in enumerate(fr) if i % 5 == 0}          # the whole episode, every ~10 s
        for nd in reqs:
            t, win = nd.get("t"), nd.get("win")
            if t is not None and win:
                lo, hi = t - 3 * win, t + 3 * win
                times |= {x for x, _ in fr if lo <= x <= hi}
        cands = self._classify(ep, fr, times)
        sdir = ep.dir / "posts" / "shots"
        sdir.mkdir(parents=True, exist_ok=True)
        for nd in [r for r in reqs if r["who"] == "prev"]:      # the previous guest first: Oti is matched to Leila
            sid = nd["sid"]
            try:
                shots[sid] = self.refine(self.prev_shot(ep, (c_all.get(nd["key"]) or {}).get("prev_guest") or "", sdir))
                if shots[sid].get("name") and not (c_all.get(nd["key"]) or {}).get("prev_guest"):
                    c_all.setdefault(nd["key"], {})["prev_guest"] = shots[sid]["name"]
            except Exception as e:  # noqa: BLE001
                log.exception("prev shot")
                warn.append(f"{nd['key']}: photo du guest précédent introuvable ({str(e)[:80]})")
        for nd in reqs:
            if st.items[nd["key"]]["kind"] == "chain" and nd["who"] == "guest" and not nd.get("fh"):
                pf = (shots.get(f"{nd['key']}:prev") or {}).get("face") or {}
                if pf.get("fh"):
                    nd["fh"] = pf["fh"]
        changing = {r["sid"] for r in reqs}
        used = [s["t"] for sid, s in shots.items() if s.get("t") is not None and sid not in changing]
        rejected = st.data.setdefault("rejected", {})         # Loïc 02.11: a photo turned down never comes back
        for sid in changing:
            old_shot = shots.get(sid) or {}
            if old_shot.get("t") is None or old_shot.get("who") == "prev":
                continue
            if (want.get(sid) or {}).get("size"):            # same moment, smaller / bigger face: only this frame goes
                used.append(old_shot["t"])
            else:
                self.reject(st, sid, old_shot)
        chosen = {}
        eyes_q = []
        for nd in reqs:
            if nd["who"] == "prev":
                continue
            avoid = rejected.get(nd["sid"]) or []
            wt = (want.get(nd["sid"]) or {}).get("t")
            if wt is not None:                                # a moment Loïc names himself wins over his old refusals
                avoid = [r for r in avoid if abs(r - wt) > posts.REJECT_GAP]
            ranked = posts.pick(cands, nd, used, avoid)
            if not ranked and avoid:
                warn.append(f"{nd['key']}: plus d'autre photo de ce type, toutes les autres ont été refusées")
            if not ranked:
                warn.append(f"{nd['key']}: pas de plan « {nd['who']} » trouvé")
                continue
            top = ranked[:4]
            chosen[nd["sid"]] = top
            if nd["who"] in ("guest", "marius"):
                eyes_q.append(nd["sid"])
            used.append(top[0]["t"])
        # eyes open (12 faces per sheet)
        flat = [(sid, c) for sid in eyes_q for c in chosen[sid]]
        okset = set()
        try:
            for j in range(0, len(flat), 12):
                chunk = flat[j:j + 12]
                sheet = frames.face_sheet([c for _, c in chunk], ep.file("posts_eyes.jpg"))
                for i in self.pipe.llm.open_eyes(sheet):
                    if 1 <= i <= len(chunk):
                        okset.add((chunk[i - 1][0], chunk[i - 1][1]["t"]))
        except Exception:  # noqa: BLE001
            log.exception("eyes")
            okset = {(sid, c["t"]) for sid, c in flat}
        url = None
        for nd in reqs:
            sid = nd["sid"]
            if nd["who"] == "prev" or sid not in chosen:
                continue
            opts = chosen[sid]
            if nd["who"] in ("guest", "marius"):
                opts = [c for c in opts if (sid, c["t"]) in okset] + [c for c in opts if (sid, c["t"]) not in okset]
            for c in opts[:4]:
                out = sdir / f"{sid.replace(':', '_')}_{int(c['t'])}.jpg"
                if not out.exists():
                    try:
                        url = url or frames.full_res_url(ep.video_id, self.cfg.ytdlp_cookies)
                        frames.grab(url, c["t"], out)
                    except Exception:  # noqa: BLE001
                        frames.grab(str(ep.file("scan.mp4")), c["t"], out)
                size = Image.open(out).size
                shot = {"file": str(out), "t": c["t"], "size": list(size), "who": nd["who"],
                        "face": {x: c[x] for x in ("cx", "cy", "fh", "fw", "top") if x in c}}
                try:
                    self.refine(shot)
                    if not self.right_person(shot):          # Marius taken for the guest (or the reverse): next one
                        log.info("posts: %s at %s is not the %s", sid, c["t"], nd["who"])
                        continue
                except Exception:  # noqa: BLE001
                    log.exception("refine face")
                if sid in shots and shots[sid].get("t") not in (rejected.get(sid) or []):   # (« reprends la photo d'avant »)
                    hist = st.data.setdefault("history", {}).setdefault(sid, [])
                    hist.append({k_: v for k_, v in shots[sid].items() if k_ != "ext"})
                    del hist[:-6]
                shots[sid] = shot
                break
        for k in {r["key"] for r in reqs}:
            st.items[k]["warn"] = [w for w in warn if w.startswith(k + ":")]
        st.save()
        return warn

    @staticmethod
    def reject(st: posts.PostState, sid: str, shot: dict) -> None:
        """A photo Loïc turned down (« autres photos »): its moment is never offered again for this slide (± REJECT_GAP s,
        the same camera shot), its files are deleted and it leaves the « photo d'avant » history."""
        t = shot.get("t")
        rej = st.data.setdefault("rejected", {}).setdefault(sid, [])
        if t is not None and all(abs(t - x) > 0.5 for x in rej):
            rej.append(t)
        for f in [shot.get("file")] + list((shot.get("ext") or {}).values()):
            if f:
                try:
                    Path(f).unlink(missing_ok=True)
                except OSError:
                    pass
        hist = (st.data.get("history") or {}).get(sid)
        if hist:
            hist[:] = [h for h in hist if h.get("t") is None or abs(h["t"] - t) > posts.REJECT_GAP]

    def right_person(self, shot: dict) -> bool:
        """On the 4K photo, the face is Marius when Marius is wanted, and not Marius when the guest is wanted."""
        import cv2
        if shot.get("who") not in ("guest", "marius", "prev"):
            return True
        img = cv2.imread(shot["file"])
        if img is None:
            return True
        H, W = img.shape[:2]
        small = cv2.resize(img, (1280, int(H * 1280 / W)))
        fs = self.pipe.faces.analyse(small)
        if not fs:
            return True
        want = (shot.get("face") or {}).get("cx", 0.5)
        f = min(fs, key=lambda f: abs((f.box[0] + f.box[2] / 2) / 1280 - want))
        return f.sim_marius >= MATCH if shot["who"] == "marius" else f.sim_marius < 0.3

    def uploads(self, n: int = 250) -> list[dict]:
        """The channel's uploads, newest first, past the last 50 (lots of Shorts in between the episodes)."""
        yt = self.pipe.yt
        ids, tok = [], None
        while len(ids) < n:
            r = yt.svc.playlistItems().list(part="contentDetails", playlistId=yt.uploads_playlist(), maxResults=50,
                                            pageToken=tok).execute()
            ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
            tok = r.get("nextPageToken")
            if not tok:
                break
        out = []
        for j in range(0, len(ids), 50):
            out += yt.svc.videos().list(part="snippet,status,contentDetails", id=",".join(ids[j:j + 50]),
                                        maxResults=50).execute().get("items", [])
        return out

    def refine(self, shot: dict) -> dict:
        """The face measured again on the 4K photo itself (the 720p scan is only a guide): size and eye height exact,
        so two faces side by side can be matched (The Chain, Question / answer)."""
        import cv2
        img = cv2.imread(shot["file"])
        if img is None or shot.get("who") not in ("guest", "marius", "prev"):
            return shot
        H, W = img.shape[:2]
        k = 1280 / W
        small = cv2.resize(img, (1280, int(H * k)))
        fs = [f for f in self.pipe.faces.detect(small) if f[14] > 0.8]
        if not fs:
            return shot
        want = (shot.get("face") or {}).get("cx", 0.5)
        h0 = small.shape[0]
        f = min(fs, key=lambda f: abs((f[0] + f[2] / 2) / 1280 - want) - 0.5 * f[3] / h0)
        x, y, w, h = (float(v) for v in f[:4])
        eyes = (float(f[5]) + float(f[7])) / 2 / h0                     # YuNet landmarks: right eye y, left eye y
        shot["face"] = {"cx": (x + w / 2) / 1280, "cy": (y + h / 2) / h0, "fw": w / 1280, "fh": h / h0, "top": y / h0,
                        "eyes": eyes}
        return shot

    def prev_shot(self, ep, name: str, sdir: Path) -> dict:
        """The previous guest (The Chain): a close-up from the end of their episode (where they leave the question)."""
        from . import reels
        import cv2
        vid = None
        longs = [v for v in self.uploads(250) if v["status"].get("privacyStatus") == "public"
                 and ("H" in v["contentDetails"].get("duration", "") or re.search(r"(\d+)M", v["contentDetails"].get("duration", ""))
                      and int(re.search(r"(\d+)M", v["contentDetails"]["duration"]).group(1)) >= 15)]
        if name:
            last = name.split()[-1].lower()
            vid = next((v["id"] for v in longs if v["id"] != ep.video_id and last in v["snippet"]["title"].lower()), None)
        if not vid:                    # the Chain = the guest of the episode just before this guest's first one
            me = (ep.get("guest_name") or "").lower()
            mine = [v for v in longs if me and me in v["snippet"]["title"].lower()] or \
                   [v for v in longs if v["id"] == ep.video_id]
            olds = sorted(longs, key=lambda v: v["snippet"].get("publishedAt", ""))
            first = min((v["snippet"].get("publishedAt", "") for v in mine), default="9999")
            before = [v for v in olds if v["snippet"].get("publishedAt", "") < first and v not in mine]
            if not before:
                raise RuntimeError("épisode du guest précédent introuvable")
            prev = before[-1]
            vid = prev["id"]
            from .state import Episode
            name = Episode(self.data_dir, vid).get("guest_name") or ""
            if not name:
                try:
                    name = str(self.pipe.llm._json(
                        "Podcast episode title: " + prev["snippet"]["title"] + "\nWho is the guest (full name, not Marius "
                        "Iepure, the host)? Return ONLY JSON: {\"guest\": \"...\"}", 200, tier="chat",
                        task="guest précédent").get("guest") or "")
                except Exception:  # noqa: BLE001
                    name = ""
        self._prev_name = name
        info = self.pipe.yt.video(vid)
        d = info["contentDetails"]["duration"]
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
        dur = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
        a, b = max(0, dur - 900), max(60, dur - 30)
        clip = reels.download_section(vid, a, b, sdir / f"prev_{vid}.mp4", self.cfg.ytdlp_cookies, height=720)
        fr = frames.sample(clip, sdir / f"prev_{vid}", 2.0)
        best = None
        for t, p in fr:
            img = cv2.imread(str(p))
            if img is None:
                continue
            H, W = img.shape[:2]
            fs = self.pipe.faces.analyse(img)
            info_c = posts.classify(fs, W, H, MATCH, 0.2)
            if info_c["kind"] != "guest":
                continue
            f = max(fs, key=lambda f: f.box[3])
            c = {"t": t, **info_c, "sharp": sharpness(img, f.box)}
            if best is None or posts.score(c) > posts.score(best):
                best = c
        if not best:
            raise RuntimeError("pas de gros plan du guest précédent")
        out = sdir / f"prev_{vid}_{int(a + best['t'])}.jpg"
        try:
            frames.grab(frames.full_res_url(vid, self.cfg.ytdlp_cookies), a + best["t"], out)
        except Exception:  # noqa: BLE001
            frames.grab(str(clip), best["t"], out)
        return {"file": str(out), "t": None, "size": list(Image.open(out).size), "who": "prev", "video": vid, "name": name,
                "face": {x: best[x] for x in ("cx", "cy", "fh", "fw", "top") if x in best}}

    # ------------------------------------------------------------ render
    def render(self, ep, st: posts.PostState, keys: list[str]) -> dict:
        guest = ep.get("guest_name") or "Guest"
        ctx = {"guest": guest, "part": part_number(ep), "guest_title": st.data.get("content", {}).get("guest_title"),
               "pronoun": st.data.get("content", {}).get("pronoun")}
        out = {}
        for k in keys:
            it = st.items[k]
            kind = it["kind"]
            c = st.data.get("content", {}).get(k) or {}
            sh = {sid.split(":", 1)[1]: v for sid, v in st.data.get("shots", {}).items() if sid.startswith(k + ":")}
            b = bool(it.get("b")) and kind in posts.B_OK
            pg = posts.pages(kind, c, sh, ctx, b)
            if self.fill_gaps(pg, sh):                       # a photo pulled back: the set around it generated
                st.save()
                pg = posts.pages(kind, c, sh, ctx, b)
            work = ep.dir / "posts" / k
            for old in work.glob("*.jpg"):
                old.unlink()
            res = posts.render_pages(pg, work)
            it["files"] = [r["file"] for r in res]
            it["overflow"] = [o for r in res for o in r["overflow"]]
            if kind not in posts.CAROUSELS:
                it["preview"] = str(posts.zones_preview(Path(res[0]["file"]), kind, b, work / "preview.jpg"))
                it["sticker"] = self.sticker(kind, c, b, ep)
            else:
                handle = share.guest_handle(guest)
                it["captions"] = posts.captions(kind, c, guest, handle, part_number(ep))
                it["collab"] = [h for h in (handle, "mariusiepure") if h]
            it.update(status="draft", v=posts.V, made=posts.stamp())
            it.pop("sent", None)
            out[k] = it
        st.save()
        return out

    def fill_gaps(self, pg: list[dict], sh: dict) -> bool:
        """Every photo placed wider than its frame allows gets the missing set generated (LaMa), once per framing."""
        from . import imaging
        made = False
        for page in pg:
            for p in [v for v in page.values() if isinstance(v, dict) and v.get("gap_key")]:
                shot = sh.get(p.get("sid") or "")
                if not shot:
                    continue
                img = Image.open(shot["file"]).convert("RGB")
                region = posts.gap_region(p, img.size)
                out = Path(shot["file"]).with_name(f"{Path(shot['file']).stem}_ext{abs(hash(p['gap_key'])) % 10 ** 8}.jpg")
                imaging.fill_out(self.cfg.models_dir, img, region).resize(
                    (p["box"][2] * 2, p["box"][3] * 2), Image.LANCZOS).save(out, quality=93)
                shot.setdefault("ext", {})[p["gap_key"]] = str(out)
                made = True
        return made

    @staticmethod
    def sticker(kind: str, c: dict, b: bool, ep) -> dict:
        link = f"https://youtu.be/{ep.video_id}"
        if b or kind in ("link", "teaser"):
            s = {"type": "lien", "url": link}
            if kind == "teaser":
                s["note"] = "Partage d'abord le reel teaser en story (avion en papier → Ajouter à la story), puis pose ce fond."
            return s
        if kind == "poll":
            return {"type": "sondage", "question": c.get("question", ""), "options": c.get("options") or ["Yes", "No"]}
        if kind in ("rapid", "chain", "atlas"):
            opts = list(c.get("options") or [])
            right = c.get("answer") if kind != "atlas" else c.get("country")
            return {"type": "quiz", "question": "Guess the answer" if kind != "atlas" else "Where did they land?",
                    "options": opts, "right": opts[0] if opts else right}
        if kind == "ask":
            return {"type": "question", "question": "Ask the next guest anything"}
        return {}

    # ------------------------------------------------------------ filing (Drive + ClickUp)
    def file(self, ep, st: posts.PostState, key: str) -> dict:
        it = st.items[key]
        sec = share.Secrets(self.data_dir)
        guest = ep.get("guest_name") or "Guest"
        links = []
        try:
            d = share.Drive(sec, self.cfg.youtube_client[:2])
            root = d.folder("BTR Posts")
            folder = d.folder(guest, root)
            old = it.get("drive") or []
            day = posts.due(self._task(it)) or datetime.now(posts.TZ)
            for i, f in enumerate(it.get("files") or []):
                name = f"{day.strftime('%m%d')}_{share._slug(guest, 30)}_{key.upper()}_{i + 1:02d}.jpg"
                r = d.put(Path(f), folder, name, "image/jpeg", old[i]["id"] if i < len(old) else None)
                links.append({"id": r["id"], "url": r.get("webViewLink", "")})
            it["drive"] = links
            it["folder"] = d.folder_link(folder)
        except share.NotConnected:
            raise
        if not it.get("task"):                           # validated before it was linked: its task in the calendar
            try:
                t0 = self.episode_tasks(ep).get(it["kind"])
                if t0 and (t0.get("status") or {}).get("status", "").lower() != "posted":
                    it["task"] = t0["id"]
            except Exception:  # noqa: BLE001
                log.exception("posts task lookup")
        tid = it.get("task")
        if tid:
            cu = self.clickup()
            t = cu.task(tid)
            cu.update(tid, markdown_content=self.description(t, it, ep),          # the bot takes it from here
                      status="scheduled" if posts.due(t) else "ready")
            try:
                cu.set_field(tid, share.F_IG, share.IG_SCHEDULED)
                if it["kind"] in posts.CAROUSELS:
                    cu.set_field(tid, share.F_TT, share.TT_SCHEDULED)
            except Exception:  # noqa: BLE001
                pass
            sig = "|".join(f"{Path(f).name}:{Path(f).stat().st_mtime:.0f}" for f in it.get("files") or [])
            if it.get("attached") != sig:                  # the images in the task too (like the reel covers)
                try:
                    for f in it.get("files") or []:
                        cu.attach(tid, Path(f))
                    it["attached"] = sig
                except Exception:  # noqa: BLE001
                    log.exception("posts attach")
            it["at"] = (posts.due(t) or datetime.now(posts.TZ)).isoformat()
            tt = posts.tiktok_time(t, posts.due(t)) if it["kind"] in posts.CAROUSELS else None
            it["tt_at"] = tt.isoformat() if tt else None
        it["status"] = "ok"
        st.save()
        return it

    def _task(self, it: dict) -> dict | None:
        if not it.get("task"):
            return None
        try:
            return self.clickup().task(it["task"])
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def description(task: dict, it: dict, ep) -> str:
        keep = (task.get("markdown_description") or task.get("text_content") or "").split(share.MARK)[0].rstrip()
        lines = [share.MARK, "", f"**{posts.LABEL[it['kind']]} validé le {share.today_str()}** · épisode https://youtu.be/{ep.video_id}", ""]
        for i, d in enumerate(it.get("drive") or []):
            lines.append(f"- Image {i + 1} : {d['url']}")
        if it.get("folder"):
            lines.append(f"- Dossier Drive : {it['folder']}")
        lines.append("")
        caps = it.get("captions") or {}
        if caps:
            collab = " et ".join("@" + h for h in it.get("collab") or [])
            lines += ["---", "", "**📸 Instagram** (sans hashtags)" + (f" · collaboration : inviter {collab}" if collab else ""),
                      "", caps.get("instagram", ""), "", "---", "", "**🎵 TikTok** (avec hashtags)", "", caps.get("tiktok", ""), ""]
        s = it.get("sticker") or {}
        if s:
            lines += ["---", "", f"**Sticker à poser dans Instagram : {s.get('type')}**", ""]
            if s.get("question"):
                lines.append(f"Question : {s['question']}")
            if s.get("options"):
                lines.append("Réponses : " + " / ".join(s["options"]) + (f" (bonne : {s['right']})" if s.get("right") else ""))
            if s.get("url"):
                lines.append(f"Lien : {s['url']}")
            if s.get("note"):
                lines.append(s["note"])
        return (keep + "\n\n" if keep else "") + "\n".join(lines)

    # ------------------------------------------------------------ ClickUp after posting
    def mark(self, it: dict, ig: bool = False, tt: bool = False, link: str = "") -> None:
        tid = it.get("task")
        if not tid:
            return
        try:
            cu = self.clickup()
            if ig:
                cu.set_field(tid, share.F_IG, share.IG_POSTED)
            if tt:
                cu.set_field(tid, share.F_TT, share.TT_POSTED)
            if ig or tt:
                share.close_if_posted(cu, tid)
            if link:
                t = cu.task(tid)
                desc = (t.get("markdown_description") or "")
                if link not in desc:
                    cu.update(tid, markdown_content=desc.rstrip() + f"\n\n- Instagram : {link}")
        except Exception:  # noqa: BLE001
            log.exception("posts mark")


# ---------------------------------------------------------------- World Atlas catch-up carousels (images ready in btr-media)
MEDIA = "https://raw.githubusercontent.com/loicviatte/btr-media/main/"


def atlas_task(t: dict) -> dict | None:
    """« Carousel · World Atlas 09 Japan · catch-up » with « Images: btr-media/world-atlas/09-japan » → its parts."""
    name = t.get("name", "")
    if not re.match(r"carou?sel\s+·\s+world atlas", name, re.I):
        return None
    desc = t.get("text_content") or t.get("markdown_description") or t.get("description") or ""
    m = re.search(r"btr-media/(world-atlas/[\w-]+)", desc)
    if not m:
        return None
    folder = m.group(1)
    slug = folder.split("/")[-1]
    key = "".join(w.capitalize() for w in re.sub(r"^\d+-", "", slug).split("-"))
    music = re.search(r"Music:\s*(.+)", desc)
    return {"folder": folder, "key": {"SaoTome": "SaoTome", "PapuaNewGuinea": "PapuaNewGuinea"}.get(key, key),
            "music": music.group(1).strip() if music else "", "images": [f"{MEDIA}{folder}/{i:02d}.jpg" for i in range(1, 9)]}


def atlas_caption(key: str) -> dict:
    import requests
    r = requests.get(MEDIA + "pipeline/captions.json", timeout=30)
    r.raise_for_status()
    c = r.json().get(key) or {}
    return c if isinstance(c, dict) else {"instagram": c, "tiktok": c}


def until(at: str | None) -> timedelta | None:
    if not at:
        return None
    try:
        return datetime.fromisoformat(at) - posts.now()
    except ValueError:
        return None
