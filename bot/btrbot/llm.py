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


