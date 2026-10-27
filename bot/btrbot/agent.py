"""Talk to Claude Code from Telegram: questions about the bot, and changes to its own code.

Claude Code runs headless in a git clone of the repo (cwd = bot/, so it can only edit the bot).
Its changes are NOT deployed by itself: the bot shows the diff, and only Loïc's button commits and
pushes to GitHub, which redeploys the server (with automatic rollback if the new version crashes).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO = "loicviatte/btr-website"

SYSTEM = """Tu es le cerveau « dev » du bot Telegram BTR Studio (podcast Break The Routine, hôte Marius Iepure).
Tu parles à Loïc, en français, court et concret, sur Telegram (texte brut, pas de Markdown lourd, pas de tableaux).
Loïc veut des solutions, pas des problèmes.

Ton répertoire de travail est le code du bot (dossier bot/ du dépôt btr-website). Lis bot/CLAUDE.md d'abord.
- Si Loïc pose une question (comment marche le bot, état d'un épisode, logs…), réponds. Les données vivantes du bot
  sont dans /opt/btr-bot/data (état des épisodes) et les logs via `journalctl -u btr-bot -n 200 --no-pager`.
- S'il demande quelque chose que le bot ne sait pas faire, MODIFIE le code ici pour l'ajouter, proprement et
  dans le style existant. Vérifie au minimum : `/opt/btr-bot/.venv/bin/python -m py_compile btrbot/*.py`.
  Ne touche jamais aux secrets, au .env, ni à quoi que ce soit hors de ce dossier. Pas de nouvelle dépendance
  lourde sans le dire. Ne déploie pas toi-même : le bot montrera tes changements à Loïc, qui validera.
- Termine toujours par 1 à 5 lignes : ce que tu as fait (ou ta réponse), et s'il y a un changement de code,
  ce qu'il changera concrètement pour lui."""

TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep", "WebSearch", "WebFetch",
    "Bash(/opt/btr-bot/.venv/bin/python:*)", "Bash(python3:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)", "Bash(find:*)", "Bash(wc:*)",
    "Bash(journalctl:*)", "Bash(systemctl status:*)",
]


class Agent:
    def __init__(self, src: Path, token: str, api_key: str, data_dir: Path):
        self.src = src                  # git clone of the whole repo
        self.token = token              # GitHub token (contents: write on the repo)
        self.api_key = api_key
        self.state_file = data_dir / "agent.json"

    # ---- state ------------------------------------------------------------
    def _state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text())
        except Exception:  # noqa: BLE001
            return {}

    def _save(self, **kw) -> None:
        st = self._state()
        st.update(kw)
        self.state_file.write_text(json.dumps(st))

    def reset_conversation(self) -> None:
        self._save(session=None)

    # ---- git ----------------------------------------------------------------
    def _git(self, *args, check=True) -> str:
        r = subprocess.run(["git", "-C", str(self.src), *args], capture_output=True, text=True, timeout=180)
        if check and r.returncode:
            raise RuntimeError(f"git {' '.join(args[:2])} : {r.stderr.strip()[-400:]}")
        return r.stdout

    def _url(self) -> str:
        return f"https://x-access-token:{self.token}@github.com/{REPO}.git"

    def sync(self) -> None:
        """Fresh copy of main, unless a change is waiting for Loïc's go."""
        if not (self.src / ".git").exists():
            self.src.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--depth", "50", self._url(), str(self.src)],
                           check=True, capture_output=True, timeout=300)
            self._git("config", "user.name", "BTR bot")
            self._git("config", "user.email", "btr-bot@users.noreply.github.com")
        self._git("remote", "set-url", "origin", self._url())
        if self.pending_files():
            return
        self._git("fetch", "-q", "origin", "main")
        self._git("reset", "-q", "--hard", "origin/main")

    def pending_files(self) -> list[str]:
        out = self._git("status", "--porcelain", "--untracked-files=all", check=False)
        return [ln[3:].strip() for ln in out.splitlines() if ln.strip()]

    def diff_summary(self) -> str:
        self._git("add", "-A", "--", "bot")
        stat = self._git("diff", "--cached", "--stat", check=False).strip()
        self._git("reset", "-q", check=False)
        return stat

    def discard(self) -> None:
        self._git("reset", "-q", "--hard", "origin/main", check=False)
        self._git("clean", "-fdq", check=False)

    def deploy(self, message: str) -> str:
        files = self.pending_files()
        outside = [f for f in files if not f.startswith("bot/")]
        if outside:  # never ship anything outside the bot (the website deploys from the same repo)
            self._git("checkout", "--", *[f for f in outside if (self.src / f).exists()], check=False)
            self._git("clean", "-fdq", "--", *outside, check=False)
        py = "/opt/btr-bot/.venv/bin/python"
        if Path(py).exists():
            r = subprocess.run([py, "-m", "compileall", "-q", str(self.src / "bot" / "btrbot")],
                               capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError("le code ne compile pas, je ne déploie pas :\n" + (r.stdout + r.stderr)[-800:])
        self._git("add", "-A", "--", "bot")
        self._git("commit", "-q", "-m", f"bot (via Telegram): {message[:70]}")
        self._git("pull", "-q", "--rebase", "origin", "main")
        self._git("push", "-q", "origin", "HEAD:main")
        return self._git("log", "-1", "--format=%h").strip()

    # ---- Claude Code ------------------------------------------------------------
    def available(self) -> bool:
        return bool(shutil.which("claude")) and bool(self.token)

    def ask(self, message: str, timeout: int = 1200) -> dict:
        """Returns {"text", "cost", "files"}; keeps the conversation (Claude Code session) across messages."""
        self.sync()
        st = self._state()
        cmd = ["claude", "-p", "--output-format", "json", "--permission-mode", "acceptEdits",
               "--append-system-prompt", SYSTEM, "--add-dir", "/opt/btr-bot/data", "--max-turns", "60"]
        if st.get("session"):
            cmd += ["--resume", st["session"]]
        cmd += ["--allowedTools", *TOOLS]
        env = {**os.environ, "ANTHROPIC_API_KEY": self.api_key, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
        r = subprocess.run(cmd, input=message, capture_output=True, text=True, cwd=str(self.src / "bot"),
                           env=env, timeout=timeout)
        try:
            out = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            if st.get("session"):  # a stale session (e.g. after a reinstall): start a fresh one once
                self.reset_conversation()
                return self.ask(message, timeout)
            raise RuntimeError((r.stderr or r.stdout or "Claude Code n'a rien répondu")[-800:])
        if out.get("session_id"):
            self._save(session=out["session_id"])
        return {"text": str(out.get("result") or "").strip() or "(pas de réponse)",
                "cost": out.get("total_cost_usd"), "error": out.get("is_error"),
                "files": [f for f in self.pending_files() if f.startswith("bot/")]}
