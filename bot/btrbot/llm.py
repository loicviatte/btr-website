"""Claude calls (Anthropic API)."""
import base64
import json
import re
from pathlib import Path

import anthropic

from . import prompts


class LLM:
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def _ask(self, content, max_tokens: int = 4000) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=prompts.SYSTEM,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()

    def _json(self, content, max_tokens: int = 4000) -> dict:
        text = self._ask(content, max_tokens)
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError(f"No JSON in model answer: {text[:300]}")
        return json.loads(m.group(0))

    # -------------------------------------------------------------------
    def propose_axes(self, video_title: str, guest_hint: str, ref_titles: list[str], transcript: str) -> dict:
        return self._json(prompts.AXES.format(
            video_title=video_title, guest_hint=guest_hint or "unknown",
            ref_titles="\n".join(f"- {t}" for t in ref_titles) or "- (none yet)",
            transcript=transcript[:180_000]))

    def refine(self, video_title: str, guest_name: str, axes: list, transcript: str, message: str) -> dict:
        return self._json(prompts.REFINE.format(
            video_title=video_title, guest_name=guest_name, axes=json.dumps(axes, ensure_ascii=False),
            transcript=transcript[:180_000], message=message))

    def pick_frames(self, sheet: Path, who: str, quote: str, n: int = 4) -> dict:
        img = base64.standard_b64encode(sheet.read_bytes()).decode()
        return self._json([
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
            {"type": "text", "text": prompts.PICK_FRAMES.format(who=who, quote=quote, n=n)},
        ], max_tokens=800)

    def description(self, title: str, guest_name: str, refs: list[dict], transcript: str) -> str:
        ref_txt = "\n\n".join(f"--- {r['title']} ---\n{r['description']}" for r in refs[:3]) or "(none)"
        return self._ask(prompts.DESCRIPTION.format(
            title=title, guest_name=guest_name, refs=ref_txt, transcript=transcript[:60_000]), 3000)

    def chapters(self, timed_transcript: str) -> list[list[str]]:
        return self._json(prompts.CHAPTERS.format(transcript=timed_transcript[:180_000]))["chapters"]
