"""Claude calls (Anthropic API)."""
import base64
import json
import re
from pathlib import Path

import anthropic

import os

from . import prompts
from .usage import Ledger

# One model per kind of job (see usage.py): Haiku talks, Sonnet works, Opus writes the hook and the code.
MODELS = {
    "chat": os.environ.get("MODEL_CHAT", "claude-haiku-5-5"),
    "creative": os.environ.get("MODEL_CREATIVE", "claude-opus-5-5"),
    "work": os.environ.get("MODEL_WORK", "claude-sonnet-5-5"),
    "vision_cheap": os.environ.get("MODEL_VISION_CHEAP", "claude-haiku-5-5"),
}


class LLM:
    def __init__(self, api_key: str, model: str, data_dir=None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model                      # kept for compatibility: the "creative" default
        self.ledger = Ledger(data_dir) if data_dir else None

    def create(self, task: str, **kw):
        """Every API call goes through here, so its cost is logged (/couts)."""
        msg = self.client.messages.create(**kw)
        if self.ledger:
            self.ledger.record(task, kw.get("model", ""), msg)
        return msg

    def _ask(self, content, max_tokens: int = 4000, tier: str = "creative", task: str = "") -> str:
        kw = dict(model=MODELS.get(tier, self.model), max_tokens=max_tokens, system=prompts.SYSTEM,
                  messages=[{"role": "user", "content": content}])
        try:
            msg = self.create(task or tier, **kw)
        except anthropic.BadRequestError as e:
            if "ttl" not in str(e) or not isinstance(content, list):
                raise
            for block in content:  # API without the 1-hour cache: fall back to the default 5-minute one
                if "cache_control" in block:
                    block["cache_control"] = {"type": "ephemeral"}
            msg = self.create(task or tier, **kw)
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()

    def _json(self, content, max_tokens: int = 4000, tier: str = "creative", task: str = "") -> dict:
        text = self._ask(content, max_tokens, tier, task)
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError(f"No JSON in model answer: {text[:300]}")
        return json.loads(m.group(0))

    @staticmethod
    def _with_transcript(transcript: str, text: str) -> list[dict]:
        """The transcript goes first and is cached: the axes, then every message of the discussion about
        them, reuse it at ~10% of the price instead of paying for the whole episode each time."""
        return [{"type": "text", "text": prompts.TRANSCRIPT.format(transcript=transcript[:180_000]),
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": text}]

    # -------------------------------------------------------------------
    def propose_axes(self, video_title: str, guest_hint: str, ref_titles: list[str], transcript: str) -> dict:
        return self._json(self._with_transcript(transcript, prompts.AXES.format(
            video_title=video_title, guest_hint=guest_hint or "unknown",
            ref_titles="\n".join(f"- {t}" for t in ref_titles) or "- (none yet)")), task="axes")

    def refine(self, video_title: str, guest_name: str, axes: list, transcript: str, message: str,
               history: list | None = None) -> dict:
        hist = "\n".join(f"{h['who']}: {h['text']}" for h in (history or [])[-20:]) or "(nothing yet)"
        return self._json(self._with_transcript(transcript, prompts.REFINE.format(
            video_title=video_title, guest_name=guest_name, axes=json.dumps(axes, ensure_ascii=False),
            message=message, history=hist)), task="titre (discussion)")

    def pick_frames(self, sheet: Path, who: str, quote: str, n: int = 4) -> dict:
        img = base64.standard_b64encode(sheet.read_bytes()).decode()
        return self._json([
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
            {"type": "text", "text": prompts.PICK_FRAMES.format(who=who, quote=quote, n=n)},
        ], max_tokens=800, tier="work", task="choix des images")

    def open_eyes(self, sheet: Path) -> list[int]:
        img = base64.standard_b64encode(sheet.read_bytes()).decode()
        r = self._json([
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
            {"type": "text", "text": prompts.EYES_OPEN},
        ], max_tokens=300, tier="vision_cheap", task="yeux ouverts")
        return [int(i) for i in r.get("open", [])]

    def retime_chapters(self, timed: str, chapters: list[list[str]]) -> list[list[str]]:
        lines = "\n".join(f"{t} {title}" for t, title in chapters)
        return self._json(prompts.RETIME.format(chapters=lines, transcript=timed[:180_000]), 4000,
                          tier="work", task="chapitres (recalage)")["chapters"]

    def description(self, title: str, guest_name: str, refs: list[dict], transcript: str) -> str:
        ref_txt = "\n\n".join(f"--- {r['title']} ---\n{r['description']}" for r in refs[:3]) or "(none)"
        return self._ask(prompts.DESCRIPTION.format(
            title=title, guest_name=guest_name, refs=ref_txt, transcript=transcript[:60_000]), 3000, task="description")

    def chapters(self, timed_transcript: str) -> list[list[str]]:
        return self._json(prompts.CHAPTERS.format(transcript=timed_transcript[:180_000]), tier="work",
                          task="chapitres")["chapters"]

    # ---- reels -------------------------------------------------------------
    def reel_candidates(self, video_title: str, guest_name: str, avoid: str, transcript: str, n: int = 10) -> list[dict]:
        r = self._json(self._with_transcript(transcript, prompts.REEL_CANDIDATES.format(
            video_title=video_title, guest_name=guest_name or "the guest", avoid=avoid or "(nothing)", n=n)),
            6000, task="reels (moments)")
        return r.get("candidates", [])

    def reel_blocks(self, words: list[str], note: str = "") -> list[dict]:
        listing = " ".join(f"{i}:{w}" for i, w in enumerate(words))
        prompt = prompts.REEL_BLOCKS.format(words=listing)
        if note:
            prompt += f"\nThe producer asked for this change to the previous layout: {note}"
        return self._json(prompt, 4000, tier="work", task="reels (sous-titres)").get("blocks", [])

    def reel_arbitrate(self, guest_name: str, title: str, diffs: list[dict]) -> dict:
        """{index: "audio" | "srt"} for each disagreement between the speech model and the SRT."""
        items = "\n".join(f'{k}. context: "…{d["context"]}…" → audio: "{d["audio"] or "(nothing)"}" / srt: "{d["srt"]}"'
                          for k, d in enumerate(diffs))
        r = self._json(prompts.REEL_ARBITRATE.format(guest_name=guest_name or "the guest", title=title, items=items),
                       1500, tier="work", task="reels (arbitrage mots)")
        return {int(p["id"]): p.get("pick") for p in r.get("picks", []) if str(p.get("id", "")).isdigit()
                and p.get("pick") in ("audio", "srt")}

    def reel_sub_feedback(self, words: list[str], blocks: list[str], feedback: str) -> dict:
        return self._json(prompts.REEL_SUB_FEEDBACK.format(words=" ".join(words), blocks="\n".join(blocks),
                                                           feedback=feedback), 1500, tier="work",
                          task="reels (retour sous-titres)")

    def reel_cover_pick(self, sheet: Path, ref: Path | None = None) -> list[int]:
        content = []
        if ref and Path(ref).exists():
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                        "data": base64.standard_b64encode(Path(ref).read_bytes()).decode()}})
        content += [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(sheet.read_bytes()).decode()}},
            {"type": "text", "text": prompts.REEL_COVER_PICK},
        ]
        r = self._json(content, max_tokens=300, tier="work", task="reels (cover)")
        return [int(i) for i in r.get("best", []) if str(i).isdigit()]

    def reel_names(self, guest: str, title: str, text: str, context: str) -> dict:
        """Proper nouns of a reel checked against the episode's own texts and the web (server-side web search)."""
        kw = dict(model=MODELS["work"], max_tokens=4000, system=prompts.SYSTEM,
                  tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
                  messages=[{"role": "user", "content": prompts.REEL_NAMES.format(
                      guest=guest or "the guest", title=title, text=text[:3000], context=context[:6000])}])
        try:
            msg = self.create("reels (noms propres)", **kw)
        except anthropic.BadRequestError:                    # web search not enabled for the API key: context only
            kw.pop("tools")
            msg = self.create("reels (noms propres)", **kw)
        for _ in range(3):                                   # long searches pause; the API resumes where it stopped
            if getattr(msg, "stop_reason", "") != "pause_turn":
                break
            kw["messages"] = kw["messages"][:1] + [{"role": "assistant", "content": msg.content}]
            msg = self.create("reels (noms propres)", **kw)
        text_out = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        found = re.findall(r"\{[^{}]*\"fixes\"\s*:\s*\[.*?\]\s*\}", text_out, re.S)
        return json.loads(found[-1]) if found else {"fixes": []}

    def reel_captions(self, guest_name: str, video_title: str, text: str) -> dict:
        return self._json(prompts.REEL_CAPTIONS.format(guest_name=guest_name or "the guest", video_title=video_title,
                                                       text=text[:4000]), 1500, task="reels (légendes)")
