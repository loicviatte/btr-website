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
        kw = dict(model=self.model, max_tokens=max_tokens, system=prompts.SYSTEM,
                  messages=[{"role": "user", "content": content}])
        try:
            msg = self.client.messages.create(**kw)
        except anthropic.BadRequestError as e:
            if "ttl" not in str(e) or not isinstance(content, list):
                raise
            for block in content:  # API without the 1-hour cache: fall back to the default 5-minute one
                if "cache_control" in block:
                    block["cache_control"] = {"type": "ephemeral"}
            msg = self.client.messages.create(**kw)
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()

    def _json(self, content, max_tokens: int = 4000) -> dict:
        text = self._ask(content, max_tokens)
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
            ref_titles="\n".join(f"- {t}" for t in ref_titles) or "- (none yet)")))

    def refine(self, video_title: str, guest_name: str, axes: list, transcript: str, message: str,
               history: list | None = None) -> dict:
        hist = "\n".join(f"{h['who']}: {h['text']}" for h in (history or [])[-20:]) or "(nothing yet)"
        return self._json(self._with_transcript(transcript, prompts.REFINE.format(
            video_title=video_title, guest_name=guest_name, axes=json.dumps(axes, ensure_ascii=False),
            message=message, history=hist)))

    def pick_frames(self, sheet: Path, who: str, quote: str, n: int = 4) -> dict:
        img = base64.standard_b64encode(sheet.read_bytes()).decode()
        return self._json([
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
            {"type": "text", "text": prompts.PICK_FRAMES.format(who=who, quote=quote, n=n)},
        ], max_tokens=800)

    def open_eyes(self, sheet: Path) -> list[int]:
        img = base64.standard_b64encode(sheet.read_bytes()).decode()
        r = self._json([
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
            {"type": "text", "text": prompts.EYES_OPEN},
        ], max_tokens=300)
        return [int(i) for i in r.get("open", [])]

    def retime_chapters(self, timed: str, chapters: list[list[str]]) -> list[list[str]]:
        lines = "\n".join(f"{t} {title}" for t, title in chapters)
        return self._json(prompts.RETIME.format(chapters=lines, transcript=timed[:180_000]), 4000)["chapters"]

    def chat(self, model: str, system: str, history: list[dict], message: str, images: list[Path] | None = None) -> dict:
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                "data": base64.standard_b64encode(p.read_bytes()).decode()}}
                   for p in (images or [])] + [{"type": "text", "text": message}]
        # The answer comes back through a forced tool call: always a clean object, never JSON mixed into the text
        # (a reply that printed its own JSON, or got cut by max_tokens, used to lose the "ask Claude" request).
        msg = self.client.messages.create(model=model, max_tokens=3000, system=system,
                                          messages=history + [{"role": "user", "content": content}],
                                          tools=[prompts.CHAT_TOOL], tool_choice={"type": "auto"})
        # (a forced tool_choice is refused by some models: "auto" + the system prompt asking for the tool, and
        #  parse_reply() below as a safety net if it ever answers in plain text)
        for b in msg.content:
            if getattr(b, "type", "") == "tool_use" and isinstance(b.input, dict):
                return b.input
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        return parse_reply(text)

    def description(self, title: str, guest_name: str, refs: list[dict], transcript: str) -> str:
        ref_txt = "\n\n".join(f"--- {r['title']} ---\n{r['description']}" for r in refs[:3]) or "(none)"
        return self._ask(prompts.DESCRIPTION.format(
            title=title, guest_name=guest_name, refs=ref_txt, transcript=transcript[:60_000]), 3000)

    def chapters(self, timed_transcript: str) -> list[list[str]]:
        return self._json(prompts.CHAPTERS.format(transcript=timed_transcript[:180_000]))["chapters"]


def parse_reply(text: str) -> dict:
    """Fallback for a plain-text answer: keep the JSON object if there is one, never show raw JSON to Loïc."""
    i = text.find('{"reply"')
    if i < 0:
        i = text.find("{")
    if i >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict) and "reply" in obj:
                return obj
        except ValueError:
            m = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)', text[i:], re.S)
            if m:
                return {"reply": json.loads('"' + m.group(1) + '"'), "truncated": True}
        text = text[:i].strip() or text
    text = re.sub(r"```(json)?", "", text).strip()
    return {"reply": text}
