"""Telegram side: notifications, buttons and the conversation with Loïc."""
import asyncio
import html
import logging
import os
import re
import traceback

from telegram import InlineKeyboardButton as B
from telegram import InlineKeyboardMarkup as K
from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler,
                          MessageReactionHandler, filters)

from . import assistant, design, drive
from .agent import Agent
from .config import Settings
from .pipeline import DryRun, Pipeline, clean_quote
from .state import Reels, Registry

log = logging.getLogger("btrbot")
cfg = Settings()
reg = Registry(cfg.data_dir)
pipe = Pipeline(cfg)
from . import share as _share  # noqa: E402
_share.load_handles(cfg.data_dir)                 # guests' Instagram @ confirmed by Loïc
LOCK = asyncio.Lock()
RUNNING: dict = {}          # the heavy job running now (label, since), for « c'est fait ? »
LAST: dict = {}             # the last heavy job finished (label, at, ok)
MEMORY = assistant.Memory(reg)   # the conversation as the chat model sees it
AGENT = Agent(cfg.agent_src, cfg.github_token, cfg.anthropic_key, cfg.data_dir)
AGENT_LOCK = asyncio.Lock()
PENDING = cfg.data_dir / "pending_srt"   # SRTs (Drive folder or chat) waiting for their video
PENDING.mkdir(parents=True, exist_ok=True)


def pick_pending(title: str):
    """The waiting SRT for this video: one whose name matches the title, else the newest one (< 3 days)."""
    import time
    files = sorted(PENDING.glob("*.srt"), key=lambda p: -p.stat().st_mtime)
    for p in files:
        if drive.matches(p.name, title):
            return p
    # no name match: the newest recent one, unless it is clearly another part ("part2" vs "part 1")
    fresh = [p for p in files if time.time() - p.stat().st_mtime < 3 * 86400
             and not (drive.part_number(p.name) and drive.part_number(title)
                      and drive.part_number(p.name) != drive.part_number(title))]
    return fresh[0] if fresh else None


def esc(s) -> str:
    return html.escape(str(s or ""))


def allowed(update: Update) -> bool:
    return cfg.chat_id and update.effective_chat and update.effective_chat.id == cfg.chat_id


async def say(ctx, text, **kw):
    MEMORY.add("assistant", text)
    return await ctx.bot.send_message(cfg.chat_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, **kw)


async def run(fn, *a):
    return await asyncio.to_thread(fn, *a)


JOB_LIMIT = 45 * 60      # a heavy job never holds the queue longer than this (a stuck download, a hung ffmpeg)


async def guarded(ctx, label: str, coro, limit: int | None = None):
    """Run one heavy step at a time and report errors on Telegram instead of dying silently. A job stuck beyond
    JOB_LIMIT is abandoned (Loïc is told), so the jobs waiting behind it are never blocked for hours."""
    import time
    async with LOCK:
        RUNNING.update(label=label, since=time.time())
        WAITING.pop(label, None)
        ok = False
        try:
            r = await asyncio.wait_for(coro, timeout=limit or JOB_LIMIT)
            ok = True
            return r
        except asyncio.TimeoutError:
            log.error("job timeout: %s", label)
            await say(ctx, f"⚠️ « {esc(label)} » était bloqué depuis {(limit or JOB_LIMIT) // 60} min : je l'abandonne et je passe "
                           "à la suite. Redemande-le si besoin.")
        except DryRun as e:
            await say(ctx, f"🧪 {esc(e)}")
        except Exception as e:  # noqa: BLE001
            log.exception(label)
            await say(ctx, f"⚠️ {esc(label)} a échoué : <code>{esc(e)}</code>\n<pre>{esc(traceback.format_exc()[-800:])}</pre>")
        finally:
            RUNNING.clear()
            LAST.update(label=label, at=time.time(), ok=ok)


WAITING: dict = {}          # jobs waiting for the one running (label → since)


def bg(ctx, label: str, coro, limit: int | None = None) -> str:
    """Start a heavy job in the background (one at a time) and say so: the chat stays responsive meanwhile. When it
    has to wait for another job, Loïc is told right away which one (never a silent wait)."""
    import time
    queued = ""
    if RUNNING:
        mins = int(time.time() - RUNNING["since"]) // 60
        queued = f" (en file d'attente derrière « {RUNNING['label']} », lancé il y a {mins} min)"
        WAITING[label] = time.time()
        asyncio.create_task(say(ctx, f"⏳ « {esc(label)} » attend la fin de « {esc(RUNNING['label'])} » (en cours depuis "
                                     f"{mins} min)."))
    asyncio.create_task(guarded(ctx, label, coro, limit))
    return f"lancé en arrière-plan : {label}{queued}"


# ---------------------------------------------------------------- dev mode (Claude Code)
async def plain(ctx, text: str, **kw):
    """Long plain-text answers, split for Telegram's 4096-char limit."""
    text = text or "(vide)"
    MEMORY.add("assistant", text)
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
    for n, c in enumerate(chunks):
        await ctx.bot.send_message(cfg.chat_id, c, disable_web_page_preview=True, **(kw if n == len(chunks) - 1 else {}))


async def talk_to_agent(ctx, text: str, strong: bool = False, thumb_ep=None):
    if not text:
        return
    if thumb_ep is None and reg.active and reg.episode(reg.active).stage == "thumbs_proposed":
        thumb_ep = reg.episode(reg.active)   # any dev answer that re-rendered designs (DESIGNS: line) shows them
    if not AGENT.available():
        await say(ctx, "Je ne sais pas encore faire ça, et mon mode « dev » (Claude Code, qui me permet de me modifier "
                       "moi-même) n'est pas activé : il manque le secret <code>BOT_GITHUB_TOKEN</code> sur GitHub.")
        return
    if AGENT_LOCK.locked():
        await say(ctx, "⏳ Je suis déjà en train de travailler sur ta demande précédente, je te réponds dès que c'est fini.")
    async with AGENT_LOCK:
        await ctx.bot.send_message(cfg.chat_id, ("🧠 Mode Opus. " if strong else "🤔 ")
                                   + "Je regarde… (jusqu'à quelques minutes si je dois coder)")
        reg.data["dev_last_request"] = text[:200]
        reg.save()
        try:
            res = await run(lambda: AGENT.ask(text, strong=strong))
        except Exception as e:  # noqa: BLE001
            log.exception("agent")
            await say(ctx, f"⚠️ Le mode dev a planté : <code>{esc(str(e)[-600:])}</code>")
            return
        cost = f"\n\n(≈ {res['cost']:.2f} $)" if isinstance(res.get("cost"), (int, float)) else ""
        answer = res["text"]
        if thumb_ep is not None:   # the agent re-rendered some designs with its modified templates: show them
            m = re.search(r"^DESIGNS:\s*(.*)$", answer, re.M)
            answer = re.sub(r"^DESIGNS:.*$", "", answer, flags=re.M).strip()
            await plain(ctx, answer + cost)
            for d in [x.strip() for x in (m.group(1) if m else "").split(",") if x.strip() in THUMB_LABELS and x.strip() not in validated(thumb_ep)]:
                await send_thumb(ctx, thumb_ep, d)
        else:
            await plain(ctx, answer + cost)
        if res["files"]:
            stat = await run(AGENT.diff_summary)
            kb = [[B("🚀 Déployer", callback_data="dev:deploy"), B("❌ Annuler", callback_data="dev:discard")]]
            await say(ctx, f"🛠 <b>Changements prêts</b> (rien n'est en ligne tant que tu ne valides pas) :\n"
                           f"<pre>{esc(stat or ', '.join(res['files']))[:3000]}</pre>\n"
                           "Tu peux aussi continuer à m'écrire pour ajuster avant de déployer.", reply_markup=K(kb))


async def on_dev_button(ctx, data: str):
    if data == "dev:discard":
        await run(AGENT.discard)
        await say(ctx, "❌ Changements annulés, rien n'a bougé.")
    elif data == "dev:deploy":
        try:
            sha = await run(AGENT.deploy, reg.data.get("dev_last_request", "update"))
        except Exception as e:  # noqa: BLE001
            await say(ctx, f"⚠️ Déploiement refusé : <code>{esc(str(e)[-800:])}</code>")
            return
        await say(ctx, f"🚀 Envoyé sur GitHub (<code>{esc(sha)}</code>). Le serveur se met à jour, je redémarre dans "
                       "1 à 3 min. Si la nouvelle version plante, je reviens tout seul à l'ancienne et je te préviens.")
    elif data == "dev:fix":
        log_txt = reg.data.pop("deploy_error", "")
        reg.save()
        await talk_to_agent(ctx, "Le dernier déploiement a planté au démarrage et le serveur est revenu à la version "
                                 "d'avant. Voici la fin du journal :\n" + log_txt + "\nTrouve la cause et corrige.")


async def badge_preview(ctx, vid: str, part: str):
    """PART badge on the CURRENT YouTube thumbnail of any video (also already public): preview, then Loïc's go."""
    await ctx.bot.send_message(cfg.chat_id, f"🏷 Je pose « PART {part} » sur la miniature de {vid}…")
    jpg = await run(pipe.badge_thumbnail, vid, part)
    reg.data.setdefault("badges", {})[vid] = str(jpg)
    reg.save()
    with open(jpg, "rb") as f:
        MEMORY.add("assistant", f"[aperçu de la miniature de {vid} avec PART {part} envoyé, bouton ✅ Mettre sur YouTube]")
        await ctx.bot.send_photo(cfg.chat_id, f, caption=f"Miniature YouTube de https://youtu.be/{vid} avec PART {part}",
                                 reply_markup=K([[B("✅ Mettre sur YouTube", callback_data=f"badge:ok:{vid}"),
                                                  B("❌ Non", callback_data=f"badge:no:{vid}")]]))


async def on_badge_button(ctx, data: str):
    from pathlib import Path
    _, act, vid = data.split(":", 2)
    jpg = Path((reg.data.get("badges") or {}).get(vid, ""))
    if act == "no" or not jpg.is_file():
        await say(ctx, "OK, la miniature reste comme elle est." if act == "no" else "Aperçu introuvable, redemande-moi le badge.")
        return
    # explicit go from Loïc on this exact image: allowed even on a public video (only the thumbnail changes)
    await run(pipe.yt.set_thumbnail, vid, jpg)
    await say(ctx, f"✅ Miniature mise à jour sur https://youtu.be/{vid} (YouTube peut mettre quelques minutes à l'afficher).")


async def badge_cmd(update: Update, ctx):
    """/badge <lien ou id> <numéro>"""
    if not allowed(update):
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage : /badge <lien ou id YouTube> <numéro>, ex. /badge https://youtu.be/PjDZ8X_JWY0 2")
        return
    m = re.search(r"(?:v=|youtu\.be/|shorts/|^)([\w-]{11})", ctx.args[0])
    if not m:
        await update.message.reply_text("Je ne reconnais pas ce lien YouTube.")
        return
    await guarded(ctx, "Badge PART", badge_preview(ctx, m.group(1), re.sub(r"\D", "", ctx.args[1]) or ctx.args[1]))


async def claude_cmd(update: Update, ctx):
    if allowed(update):
        await talk_to_agent(ctx, " ".join(ctx.args))


async def claude_strong_cmd(update: Update, ctx):
    """/opus <demande>: same, with the most capable model (for hard changes)."""
    if allowed(update):
        await talk_to_agent(ctx, " ".join(ctx.args), strong=True)


async def new_conv_cmd(update: Update, ctx):
    if allowed(update):
        AGENT.reset_conversation()
        await update.message.reply_text("🆕 Nouvelle conversation avec le mode dev (il oublie la discussion précédente).")


# ---------------------------------------------------------------- jobs
async def poll_drive(ctx):
    """New SRTs in the shared Drive folder → attached to the right episode, or kept for the next video."""
    if not cfg.drive_srt_folder:
        return
    try:
        files = await run(drive.list_srt, cfg.drive_srt_folder)
    except Exception as e:  # noqa: BLE001
        log.warning("drive poll failed: %s", e)
        return
    seen = set(reg.data.setdefault("drive_seen", []))
    for fid, name in files:
        if fid in seen:
            continue
        try:
            path = await run(drive.download, fid, PENDING / name)
        except Exception as e:  # noqa: BLE001
            log.warning("drive download %s failed: %s", name, e)
            continue
        reg.data["drive_seen"].append(fid)
        reg.save()
        await handle_new_srt(ctx, path, f"📂 Nouveau SRT dans le Drive : <code>{esc(name)}</code>")


async def poll_youtube(ctx: ContextTypes.DEFAULT_TYPE):
    await poll_drive(ctx)
    try:
        await shorts_sync(ctx)
        await shorts_watch(ctx)
    except Exception as e:  # noqa: BLE001
        log.warning("shorts sync/watch failed: %s", e)
    try:
        vids = await run(pipe.yt.unlisted_ready)
    except Exception as e:  # noqa: BLE001
        log.warning("poll failed: %s", e)
        return
    first_run = not reg.data.get("initialised")
    for v in vids:
        vid = v["id"]
        if reg.seen(vid):
            continue
        reg.mark_seen(vid)
        if first_run:
            continue
        ep = reg.episode(vid)
        ep["title"] = v["snippet"]["title"]
        ep.stage = "waiting_transcript"
        ep.save()
        reg.active = vid
        srt_file = pick_pending(ep["title"])
        if srt_file:
            srt_file.replace(ep.file("captions_davinci.srt"))
            await say(ctx, f"🎬 Nouvelle vidéo non répertoriée : <b>{esc(ep['title'])}</b>\nhttps://youtu.be/{vid}\n"
                           f"J'utilise ton SRT <code>{esc(srt_file.name)}</code>, pas besoin d'attendre YouTube.")
            await guarded(ctx, "Proposition des axes", propose_axes(ctx, ep))
            continue
        await say(ctx, f"🎬 Nouvelle vidéo non répertoriée : <b>{esc(ep['title'])}</b>\n"
                       f"https://youtu.be/{vid}\nJe récupère le transcript dès que YouTube l'a généré.")
    if first_run:
        reg.data["initialised"] = True
        reg.save()
        if vids:
            await say(ctx, "Bot prêt. Les vidéos déjà non répertoriées sont ignorées ; "
                           "pour en traiter une : <code>/episode ID</code>.")
    await poll_transcripts(ctx)


async def poll_transcripts(ctx):
    for vid in list(reg.data["seen"]):
        ep = reg.episode(vid)
        if ep.stage != "waiting_transcript":
            continue
        ok = await run(pipe.fetch_transcript, ep)
        ep.save()
        if ok:
            await guarded(ctx, "Proposition des axes", propose_axes(ctx, ep))


async def propose_axes(ctx, ep):
    await say(ctx, "📝 Transcript reçu, je lis l'épisode et je cherche les meilleurs axes…")
    await run(pipe.propose_axes, ep)
    ep.stage = "axes_proposed"
    ep.save()
    reg.active = ep.video_id
    await send_axes(ctx, ep)


async def send_axes(ctx, ep, intro=None):
    lines = [intro or f"💡 <b>3 axes pour {esc(ep.get('guest_name'))}</b>"]
    for i, a in enumerate(ep.get("axes", []), 1):
        warn = "" if a.get("verified") else " ⚠️ <i>citation non retrouvée telle quelle</i>"
        lines.append(f"\n<b>{i}. {esc(a.get('angle'))}</b>\n“{esc(a.get('top'))} <b>{esc(a.get('key'))}</b> {esc(a.get('bottom'))}” "
                     f"({esc(a.get('timestamp'))}){warn}\nTitre : <i>{esc(a.get('title'))}</i>\n→ {esc(a.get('why'))}")
    lines.append("\nChoisis un axe, ou écris-moi pour en discuter (« plus provoc », « autre chose sur sa carrière »…).")
    kb = [[B(f"Axe {i}", callback_data=f"axis:{i-1}") for i in range(1, len(ep.get('axes', [])) + 1)]]
    await say(ctx, "\n".join(lines), reply_markup=K(kb))


async def propose_frames(ctx, ep, who: str, more=False):
    label = ep.get("guest_name", "le guest") if who == "guest" else "Marius"
    await say(ctx, f"🔎 Je cherche des images de <b>{esc(label)}</b>…" + (" (première fois : je télécharge et j'analyse la vidéo, ~10 min)" if not ep.file("scan.json").exists() else ""))
    shown = ep.get(f"shown_{who}", [])
    picks = await run(pipe.propose_frames, ep, who, tuple(shown) if more else ())
    if not picks:
        await say(ctx, f"Je n'ai pas trouvé de gros plan de {esc(label)}. Envoie-moi une capture (photo) en réponse et je l'utilise.")
        return
    ep[f"cand_{who}"] = picks
    ep[f"shown_{who}"] = shown + [p["t"] for p in picks]
    ep.save()
    media = []
    for i, p in enumerate(picks, 1):
        with open(p["hires"], "rb") as f:
            media.append(InputMediaPhoto(f.read(), caption=f"{label} {i} · {int(p['t'] // 60)}:{int(p['t'] % 60):02d}"))
    await ctx.bot.send_media_group(cfg.chat_id, media)
    MEMORY.add("assistant", f"[{len(media)} images de {label} envoyées, numérotées 1 à {len(media)}]")
    kb = [[B(str(i), callback_data=f"pick:{who}:{i-1}") for i in range(1, len(picks) + 1)],
          [B("🔁 Autres", callback_data=f"more:{who}")]]
    await say(ctx, f"Quelle image de <b>{esc(label)}</b> ?", reply_markup=K(kb))


THUMB_LABELS = {"youtube": "YouTube", "instagram": "Instagram vertical", "square": "carrée"}
THUMB_NAMES = {"youtube": "horizontal", "instagram": "vertical", "square": "carré"}   # how Loïc calls them


def validated(ep) -> list[str]:
    return [d for d in THUMB_LABELS if d in (ep.get("validated") or [])]


def valid_status(ep) -> str:
    v = validated(ep)
    left = [THUMB_NAMES[d] for d in THUMB_LABELS if d not in v]
    return (("✅ Validées : " + ", ".join(THUMB_NAMES[d] for d in v) + ". ") if v else "") + \
           (("À valider : " + ", ".join(left) + ".") if left else "Les 3 sont validées.")


def thumb_kb(ep, first_row=None):
    v = validated(ep)
    todo = [d for d in THUMB_LABELS if d not in v]
    kb = [[B("✅ Publier sur YouTube", callback_data="publish")]] + (first_row or [])
    if todo:
        kb.append([B(f"👍 {THUMB_NAMES[d].capitalize()} validé", callback_data=f"val:{d}") for d in todo])
        kb.append([B(f"🔁 Refaire {THUMB_NAMES[d]}", callback_data=f"thumb:{d}") for d in todo])
    return K(kb)


async def send_thumb(ctx, ep, design: str):
    path = ep.file(f"render/thumb_{design}.jpg")
    with open(path, "rb") as f:
        if design == "youtube":
            msg = await ctx.bot.send_photo(cfg.chat_id, f, caption="Miniature YouTube")
        elif design == "instagram":
            msg = await ctx.bot.send_document(cfg.chat_id, f, filename=f"{ep.video_id}_instagram.jpg", caption="Miniature Instagram verticale (fichier HD)")
        else:
            msg = await ctx.bot.send_document(cfg.chat_id, f, filename=f"{ep.video_id}_carre.jpg", caption="Miniature carrée 1080×1080 (fichier HD)")
    MEMORY.add("assistant", f"[image envoyée : miniature {THUMB_NAMES[design]}]")
    ep["thumb_msgs"] = {**(ep.get("thumb_msgs") or {}), design: msg.message_id}   # to read his reactions on them
    ep.save()


OK_EMOJIS = {"✅", "✔️", "✔", "👍", "👌", "💯", "🔥", "❤", "❤️", "🏆"}


async def on_reaction(update: Update, ctx):
    """✅ (or 👍…) as a reaction on a thumbnail = validated; removing it re-opens the design."""
    r = update.message_reaction
    if not r or not cfg.chat_id or r.chat.id != cfg.chat_id or not reg.active:
        return
    ep = reg.episode(reg.active)
    design = next((d for d, mid in (ep.get("thumb_msgs") or {}).items() if mid == r.message_id), None)
    if not design or ep.stage != "thumbs_proposed":
        return
    emo = lambda rs: {getattr(x, "emoji", None) for x in rs} & OK_EMOJIS   # noqa: E731
    if emo(r.new_reaction) and design not in validated(ep):
        ep["validated"] = validated(ep) + [design]
        ep.save()
        await say(ctx, f"👍 {THUMB_NAMES[design].capitalize()} validé, je n'y touche plus. " + valid_status(ep), reply_markup=thumb_kb(ep))
    elif emo(r.old_reaction) and not emo(r.new_reaction) and design in validated(ep):
        ep["validated"] = [d for d in validated(ep) if d != design]
        ep.save()
        await say(ctx, f"↩️ {THUMB_NAMES[design].capitalize()} n'est plus validé. " + valid_status(ep), reply_markup=thumb_kb(ep))


async def make_thumbs(ctx, ep, only: str | None = None):
    if only:
        await say(ctx, f"🎨 Je refais uniquement la miniature {THUMB_LABELS[only]} (les autres ne changent pas)…")
    elif validated(ep):
        await say(ctx, "🎨 Je refais les miniatures non validées. " + valid_status(ep))
    else:
        await say(ctx, "🎨 Je fabrique les 3 miniatures : YouTube, Instagram vertical et carré (détourage, extension, voile or)… ~4 min")
    thumbs = await run(pipe.thumbnails, ep, only)
    if not ep.get("description"):
        ep["description"] = await run(pipe.description, ep)
    ep.stage = "thumbs_proposed"
    ep.save()
    for d in ("youtube", "instagram", "square"):
        if d in thumbs:
            await send_thumb(ctx, ep, d)
    if only:
        await say(ctx, "Prêt à publier ? " + valid_status(ep), reply_markup=thumb_kb(ep))
        return
    desc = ep["description"].replace("{{CHAPTERS}}", "[chapitres ajoutés quand le SRT est prêt]").replace("{CHAPTERS}", "[chapitres]")
    await say(ctx, f"<b>Titre :</b> {esc(ep['final']['title'])}\n\n<b>Description :</b>\n{esc(desc)[:3300]}")
    kb = thumb_kb(ep, [[B("🔁 Autre image guest", callback_data="more:guest"), B("🔁 Autre image Marius", callback_data="more:marius")]])
    await say(ctx, "Je publie titre + description + miniature ?\nDis « horizontal / vertical / carré validé » pour figer une miniature, "
                   "le reste de tes retours la modifie.\nPour changer : <code>titre: …</code>, "
                   "<code>citation: haut | MOT | bas</code> ou <code>description: …</code> (tes consignes).\n" + valid_status(ep),
              reply_markup=kb)




async def send_recap(ctx, ep):
    """Last check before publishing: the 3 thumbnails as they are now (nothing is re-rendered), title and description."""
    for d in THUMB_LABELS:
        await send_thumb(ctx, ep, d)
    desc = (ep.get("description") or "").replace("{{CHAPTERS}}", "[chapitres]").replace("{CHAPTERS}", "[chapitres]")
    await say(ctx, f"<b>Titre YouTube :</b>\n{esc(ep['final']['title'])}")
    await plain(ctx, "Description YouTube :\n\n" + desc)
    await say(ctx, "Dernier check : " + valid_status(ep) + "\nTout est bon ?", reply_markup=thumb_kb(ep))


CHAT_MODEL = os.environ.get("CHAT_MODEL") or os.environ.get("MODEL_CHAT") or "claude-haiku-5-5"   # Haiku talks (~20x cheaper than Sonnet)


RECENT = {"at": 0.0, "text": ""}


def recent_videos() -> str:
    """Last uploads (id, visibility, title), refreshed every 10 min: lets the chat find « les 2 dernières vidéos d'Oti »."""
    import time
    if time.time() - RECENT["at"] > 600:
        try:
            vids = pipe.yt.recent(15)
            RECENT["text"] = "\n".join(f"- {v['id']} ({v['status'].get('privacyStatus')}) {v['snippet']['title']}" for v in vids)
            RECENT["at"] = time.time()
        except Exception as e:  # noqa: BLE001
            log.warning("recent videos: %s", e)
    return RECENT["text"] or "(indisponible)"


def chat_context(ep) -> str:
    return (_ep_context(ep) + "\n\n" + design_context() + "\n\nVidéos récentes de la chaîne (id, statut, titre) :\n" + recent_videos())


def _ep_context(ep) -> str:
    if not ep:
        return "Aucun épisode en cours."
    f = ep.get("final") or {}
    return (f"Épisode {ep.video_id} « {ep.get('title', '')} » (invité : {ep.get('guest_name', '?')}). Étape : {ep.stage}.\n"
            f"Titre retenu : {f.get('title', '-')}. Citation : {f.get('top', '')} {f.get('key', '')} {f.get('bottom', '')}.\n"
            f"Miniatures validées : {', '.join(THUMB_NAMES[d] for d in validated(ep)) or 'aucune'}. "
            f"Description : {'oui' if ep.get('description') else 'non'}"
            f"{', avec chapitres' if ep.get('chapters_in_description') else ''}.")


def design_context() -> str:
    return "Réglages des miniatures (formats : youtube = horizontal, instagram = vertical, square = carré) :\n" + \
        "\n".join(design.describe(cfg.data_dir, f) for f in design.PARAMS)


async def propose_ask(ctx, ep, text: str, images: list[str]):
    """Screenshots + feedback on a thumbnail: needs Claude, but only after Loïc's yes."""
    reg.data["pending_ask"] = {"text": text, "thumbs": True, "images": images}
    reg.save()
    await say(ctx, "Je peux transmettre ton retour (et tes captures) à Claude pour reprendre la miniature concernée, "
                   "sans toucher aux miniatures validées. Demander à Claude ?",
              reply_markup=K([[B("✅ Oui, demander à Claude", callback_data="ask:yes"), B("Non", callback_data="ask:no")]]))


async def on_ask_button(ctx, data: str):
    pend = reg.data.pop("pending_ask", None)
    reg.save()
    if data == "ask:no" or not pend:
        await say(ctx, "OK, je ne change rien. On continue à discuter." if pend else "Cette demande n'est plus d'actualité.")
        return
    ep = reg.episode(reg.active) if reg.active else None
    if pend.get("thumbs") and ep and ep.get("pick_guest") and ep.get("pick_marius"):
        await thumb_feedback(ctx, ep, pend["text"], pend.get("images") or [])
    else:
        await talk_to_agent(ctx, pend["text"])


async def thumb_feedback(ctx, ep, text: str, images: list[str]):
    g, m = ep["pick_guest"], ep["pick_marius"]
    imgs = "\n".join(f"- {p}" for p in images) or "(aucune)"
    msg = f"""Retour de Loïc sur les miniatures de l'épisode {ep.video_id} ({ep.get('guest_name', '')}) :
« {text} »

Captures jointes par Loïc (à regarder avec Read) : elles MONTRENT OÙ EST LE PROBLÈME (annotations, comparaisons). Ce ne sont PAS de nouvelles images à mettre dans les miniatures : garde les images déjà choisies par le bot.
{imgs}

DÉJÀ VALIDÉES par Loïc (INTOUCHABLES : ne modifie rien qui les change, ne les re-rends pas) : {', '.join(validated(ep)) or 'aucune'}.
Loïc les appelle : horizontal = youtube, vertical = instagram, carré = square.

Miniatures actuelles : {ep.dir}/render/thumb_youtube.jpg, thumb_instagram.jpg, thumb_square.jpg (regarde-les avec Read).
Images choisies (inchangées) : guest {g.get('hires')}, Marius {m.get('hires')}.

À faire :
1. Comprends de QUELLE miniature il parle (youtube = 1920x1080, instagram = vertical 1080x1920, square = 1080x1080) ; s'il ne précise pas, déduis-le des captures ou du contexte. Si c'est vraiment impossible, pose UNE question courte et NE MODIFIE RIEN (pas de ligne DESIGNS).
2. Corrige uniquement ce qui concerne cette/ces miniature(s) (btrbot/templates/*.html ou btrbot/render.py). Les autres designs doivent rester identiques ; si une règle de marque est en jeu (voir CLAUDE.md), respecte-la.
3. Re-rends SEULEMENT les designs concernés avec le code modifié : `/opt/btr-bot/.venv/bin/python -m btrbot.rerender {ep.video_id} <youtube|instagram|square>` (depuis le dossier courant), regarde le résultat avec Read et itère jusqu'à ce que ce soit bon.
4. Dernière ligne de ta réponse, exactement : DESIGNS: <liste séparée par des virgules des designs re-rendus>"""
    await say(ctx, "🧠 Je regarde ton retour et je reprends seulement la/les miniature(s) concernée(s), avec les mêmes images…")
    await talk_to_agent(ctx, msg, thumb_ep=ep)


async def show_chapters(ctx, ep, intro: str = "Chapitres actuels"):
    ch = ep.get("chapters") or []
    body = "\n".join(f"{esc(t)} {esc(title)}" for t, title in ch)
    kb = [[B("✅ Mettre à jour sur YouTube", callback_data="chapters_ok"), B("🔁 Recalculer depuis le SRT", callback_data="chapters_retime")]]
    ep.stage = "chapters_proposed"
    ep.save()
    await say(ctx, f"📑 <b>{esc(intro)}</b>\n<pre>{body}</pre>", reply_markup=K(kb))


async def retime_chapters(ctx, ep):
    await say(ctx, "⏱ Je recale chaque chapitre sur ton SRT (mêmes titres, timecodes relus un par un)…")
    await run(pipe.retime_chapters, ep)
    await show_chapters(ctx, ep, "Chapitres recalés sur le SRT")




async def propose_chapters(ctx, ep, source: str):
    ch = await run(pipe.chapters, ep)
    ep["chapters"] = ch
    ep.stage = "chapters_proposed"
    ep.save()
    body = "\n".join(f"{esc(t)} {esc(title)}" for t, title in ch)
    kb = [[B("✅ Ajouter à la description", callback_data="chapters_ok"), B("🔁 Refaire", callback_data="chapters_redo")]]
    await say(ctx, f"📑 <b>Chapitrage</b> (depuis {esc(source)})\n<pre>{body}</pre>", reply_markup=K(kb))


# ---------------------------------------------------------------- the assistant (Haiku + tools)
SHOTS: list = []   # screenshots waiting for his explanation (thumbnail feedback)


def assistant_context(ep) -> str:
    import time
    lines = [_ep_context(ep)]
    if ep and ep.stage == "axes_proposed":
        lines.append("Axes proposés : " + " | ".join(f"{i}. {a.get('top')} {a.get('key')} {a.get('bottom')} → titre « {a.get('title')} »"
                                                   for i, a in enumerate(ep.get("axes", []), 1)))
    if ep:
        from .pipeline import part_number
        p = part_number(ep)
        if p:
            lines.append(f"Badge PART {p} sur les miniatures de cet épisode.")
    if RUNNING:
        lines.append(f"EN COURS : {RUNNING['label']} (depuis {int(time.time() - RUNNING['since'])} s).")
    if WAITING:
        lines.append("EN ATTENTE derrière lui : " + ", ".join(WAITING) + ".")
    if LAST:
        lines.append(f"Dernier travail terminé : {LAST['label']} ({'ok' if LAST['ok'] else 'ÉCHEC'}, il y a {int(time.time() - LAST['at'])} s).")
    if AGENT_LOCK.locked():
        lines.append("Claude Code (mode dev) est en train de travailler sur une demande.")
    if reg.data.get("pending_ask"):
        lines.append("Bouton « Demander à Claude ? » en attente de sa réponse : " + str(reg.data["pending_ask"].get("text", ""))[:200])
    if list(PENDING.glob("*.srt")):
        lines.append("SRT en attente de leur vidéo : " + ", ".join(p.name for p in PENDING.glob("*.srt")))
    if SHOTS:
        lines.append(f"{len(SHOTS)} capture(s) d'écran reçue(s) en attente d'explication.")
    lines.append(design_context())
    lines.append("Vidéos récentes de la chaîne (id, statut, titre) :\n" + recent_videos())
    return "\n".join(lines)


def tool_handlers(ctx, images: list) -> dict:
    """The bot's functions, as the chat model can call them. Each returns a short French text for the model."""
    def cur():
        return reg.episode(reg.active) if reg.active else None

    def need(stages=None):
        ep = cur()
        if not ep:
            raise RuntimeError("aucun épisode en cours")
        if stages and ep.stage not in stages:
            hint = ""
            rep = reel_ep()
            if rep and RS(rep):
                hint = (" — ces outils ne servent qu'aux miniatures YouTube de l'épisode. Si Loïc parle des covers / "
                        "miniatures / screenshots / photos des REELS, utilise reels_cover_search (nums, want) ou reel_cover.")
            raise RuntimeError(f"impossible à l'étape actuelle ({ep.stage}){hint}")
        return ep

    async def get_status():
        ep = cur()
        extra = ""
        if ep and ep.get("chapters"):
            extra = "\nChapitres actuels :\n" + "\n".join(f"{t} {x}" for t, x in ep["chapters"])
        return await run(assistant_context, ep) + "\n" + reels_context() + extra

    async def title_chat(message):
        ep = need(("axes_proposed", "frames_proposed", "thumbs_proposed"))
        await title_discussion(ctx, ep, message)
        return "fait : la réponse sur le titre a déjà été envoyée à Loïc (ne la répète pas, réponds en un mot ou rien)."

    async def choose_axis(n):
        ep = need(("axes_proposed", "frames_proposed", "thumbs_proposed"))
        axes = ep.get("axes") or []
        if not 1 <= int(n) <= len(axes):
            return f"il n'y a que {len(axes)} axes"
        await pick_axis(ctx, ep, int(n) - 1)
        return f"axe {n} retenu, recherche d'images lancée"

    async def other_frames(who):
        ep = need(("frames_proposed", "thumbs_proposed"))
        return bg(ctx, "Recherche d'images", propose_frames(ctx, ep, who, more=True))

    async def validate(formats):
        ep = need(("thumbs_proposed",))
        ep["validated"] = validated(ep) + [f for f in dict.fromkeys(formats) if f not in validated(ep)]
        ep.save()
        return valid_status(ep)

    async def reopen(formats):
        ep = need(("thumbs_proposed",))
        ep["validated"] = [d for d in validated(ep) if d not in formats]
        ep.save()
        return valid_status(ep)

    async def redo_thumbnails(formats):
        ep = need(("thumbs_proposed",))
        if not (ep.get("pick_guest") and ep.get("pick_marius")):
            return "pas encore d'images choisies"
        fmts = list(dict.fromkeys(formats)) or list(THUMB_LABELS)
        ep["validated"] = [d for d in validated(ep) if d not in fmts]
        ep.save()
        if len(fmts) == 3:
            return bg(ctx, "Miniatures", make_thumbs(ctx, ep))

        async def seq():
            for f in fmts:
                await make_thumbs(ctx, ep, f)
        return bg(ctx, "Miniature " + ", ".join(THUMB_NAMES[f] for f in fmts), seq())

    async def set_design(format, set=None, reset=False, show=False):   # noqa: A002
        notes = []
        if reset:
            design.reset(cfg.data_dir, format)
            notes.append("réglages remis par défaut")
        for name, val in (set or {}).items():
            try:
                notes.append(f"{name} → {design.set_value(cfg.data_dir, format, name, val)}")
            except (KeyError, ValueError, TypeError):
                notes.append(f"réglage inconnu ou valeur invalide : {name}")
        out = " · ".join(notes) or "aucun changement"
        if show or not notes:
            out += "\n" + design.describe(cfg.data_dir, format)
        return out + "\n(pas encore re-rendu : redo_thumbnails pour voir le résultat)"

    async def set_title(title):
        ep = need(("frames_proposed", "thumbs_proposed"))
        ep["final"]["title"] = title.strip()[:100]
        ep.save()
        return "titre mis à jour : " + ep["final"]["title"]

    async def set_quote(top, key, bottom):
        ep = need(("thumbs_proposed",))
        ep["final"].update({"top": top, "key": key, "bottom": bottom})
        ep.data.pop("validated", None)
        ep.save()
        return bg(ctx, "Miniatures (nouvelle citation)", make_thumbs(ctx, ep))

    async def set_part(part):
        ep = need()
        ep["part"] = re.sub(r"\D", "", str(part or ""))
        ep.save()
        return (f"badge PART {ep['part']}" if ep["part"] else "pas de badge") + " pour cet épisode (redo_thumbnails pour l'appliquer)"

    async def edit_description(instruction):
        ep = need(("thumbs_proposed", "published", "chapters_proposed"))
        prompt = ("Rewrite this YouTube description following this instruction: " + instruction + "\n"
                  "Keep the same structure and keep the {CHAPTERS} line as is. Return only the description.\n\n" + ep["description"])
        ep["description"] = await run(lambda: pipe.llm._ask(prompt, task="description (retouche)"))
        ep.save()
        await plain(ctx, "Nouvelle description :\n\n" + ep["description"])
        return "nouvelle description envoyée à Loïc"

    async def send_recap_t():
        ep = need(("thumbs_proposed",))
        return bg(ctx, "Récap", send_recap(ctx, ep))

    async def publish():
        ep = need(("thumbs_proposed",))
        await say(ctx, f"Je publie sur YouTube le titre « {esc(ep['final']['title'])} », la description et la miniature horizontale ? "
                       + valid_status(ep), reply_markup=K([[B("✅ Publier sur YouTube", callback_data="publish")]]))
        return "bouton de publication affiché : Loïc doit cliquer"

    async def chapters(action):
        ep = need()
        if action == "show":
            if not ep.get("chapters"):
                return "pas encore de chapitres (regenerate pour les créer)"
            await show_chapters(ctx, ep)
            return "chapitres affichés avec le bouton YouTube"
        if action == "retime":
            return bg(ctx, "Chapitres (recalage)", retime_chapters(ctx, ep))
        if action == "regenerate":
            return bg(ctx, "Chapitrage", propose_chapters(ctx, ep, "nouvel essai"))

        async def into():
            await say(ctx, "⏱ Je génère les chapitres avec timecodes et je les mets dans la description…")
            await plain(ctx, await run(pipe.description_with_chapters, ep))
            await say(ctx, "Voilà la description avec les timecodes (elle sera publiée telle quelle).", reply_markup=thumb_kb(ep))
        return bg(ctx, "Chapitres dans la description", into())

    async def badge(video_id, part):
        m = re.search(r"([\w-]{11})", video_id or "")
        if not m:
            return "id de vidéo invalide"
        return bg(ctx, f"Badge PART {part}", badge_preview(ctx, m.group(1), re.sub(r"\D", "", str(part)) or str(part)))

    async def thumbnail_feedback(feedback):
        ep = need(("thumbs_proposed",))
        await propose_ask(ctx, ep, feedback, [str(p) for p in images] + [str(p) for p in SHOTS])
        SHOTS.clear()
        return "bouton « Demander à Claude ? » affiché avec ses captures : Loïc doit dire oui"

    async def propose_claude_code(request):
        reg.data["pending_ask"] = {"text": request, "thumbs": False, "images": [str(p) for p in images]}
        reg.save()
        await say(ctx, "🧠 Je fais coder ça par Claude ?\n<i>" + esc(request[:600]) + "</i>",
                  reply_markup=K([[B("✅ Oui, demander à Claude", callback_data="ask:yes"), B("Non", callback_data="ask:no")]]))
        return "bouton affiché : rien ne part sans son oui"

    async def start_episode(video):
        m = re.search(r"(?:v=|youtu\.be/|shorts/|^)([\w-]{11})", video.strip())
        if not m:
            return "lien ou id YouTube invalide"
        return bg(ctx, "Nouvel épisode", start_video(ctx, m.group(1)))

    async def scan_youtube():
        return bg(ctx, "Scan YouTube + Drive", poll_youtube(ctx))

    async def costs(days=1):
        return pipe.llm.ledger.summary(float(days or 1)) if pipe.llm.ledger else "pas de suivi"

    async def health_check():
        async def go():
            out = await run(run_check)
            await plain(ctx, out[-3800:] or "(rien)")
        return bg(ctx, "Test complet", go())

    def reels_or_fail():
        ep = reel_ep()
        if not ep or not RS(ep):
            raise RuntimeError("aucune liste de reels en cours (reels_propose d'abord)")
        return ep

    async def reels_propose(video=None):
        vid = None
        if video:
            m = re.search(r"(?:v=|youtu\.be/|shorts/|^)([\w-]{11})", str(video).strip())
            vid = m.group(1) if m else None
        return bg(ctx, "Moments pour les reels", propose_reels(ctx, vid))

    async def reels_select(numbers):
        ep = reels_or_fail()
        valid = {c["n"] for c in RS(ep).data["cands"]}
        nums = sorted({int(n) for n in numbers if int(n) in valid})
        if not nums:
            return f"numéros invalides (1 à {len(valid)})"
        RS(ep).data["sel"] = nums
        RS(ep).save()
        return start_reels(ctx, ep, nums)

    async def reel_adjust(n, start_shift=0, end_shift=0, cut=None, uncut=False):
        ep = reels_or_fail()
        n = int(n)
        if not reel_cand(ep, n) or not RS(ep).data["items"].get(str(n), {}).get("file"):
            return f"le reel {n} n'est pas encore monté"
        item = reel_item(ep, n)
        sh = item["shift"]
        sh[0] = round(sh[0] + float(start_shift or 0), 2)
        sh[1] = round(sh[1] + float(end_shift or 0), 2)
        if uncut:
            item["cuts"] = []
        if cut:
            item["cuts"].append(str(cut)[:200])
        if cut or uncut or start_shift or end_shift:
            item.pop("captions", None)                 # the words changed: the captions are written again
        return queue_reel(ctx, ep, n, "full")

    async def reel_subtitles(n, feedback):
        ep = reels_or_fail()
        n = int(n)
        item = RS(ep).data["items"].get(str(n)) or {}
        if not item.get("file"):
            return f"le reel {n} n'est pas encore monté"
        res = await run(pipe.reel_feedback, ep, n, dict(item), str(feedback))
        fixes = [{**f, "ok": 1} for f in res.get("fixes") or [] if f.get("from") and f.get("to")]
        it = reel_item(ep, n)
        if fixes:
            it.setdefault("fixes", []).extend(fixes)
            it.pop("captions", None)                   # a corrected word must not stay wrong in the captions
        if res.get("relayout") and res.get("layout_note"):    # notes add up: an earlier ask is not forgotten
            notes = [x for x in str(it.get("sub_note", "")).split(" | ") if x] + [str(res["layout_note"])[:300]]
            it["sub_note"] = " | ".join(dict.fromkeys(notes))[-900:]
        together = [str(x) for x in res.get("together") or [] if len(str(x).split()) >= 2]
        if together:
            it["together"] = list(dict.fromkeys((it.get("together") or []) + together))
        if not fixes and not res.get("relayout") and not together:
            RS(ep).save()
            return "rien à changer compris. Réponse à transmettre à Loïc : " + str(res.get("reply", ""))
        out = queue_reel(ctx, ep, n, "subs")
        return f"{out}. À dire à Loïc : {res.get('reply', '')}"

    async def reel_validate(n, instagram=None):
        ep = reels_or_fail()
        n = int(n)
        item = RS(ep).data["items"].get(str(n)) or {}
        if not item.get("file"):
            return f"le reel {n} n'est pas encore monté"
        ig = None if instagram is None else instagram not in (False, "false", "non", 0)
        if item.get("filed") and ig is not None:           # already filed: move it to / from the feed
            reel_item(ep, n)["instagram"] = ig
            RS(ep).save()
            return bg(ctx, f"Reel {n} → {'feed' if ig else 'TikTok + Shorts'}", share_reel(ctx, ep, n))
        if ig is not None:                                  # a feed choice given early: kept for the filing step
            feed = RS(ep).data.setdefault("feed", [])
            if ig and n not in feed:
                feed.append(n)
            if not ig and n in feed:
                feed.remove(n)
            RS(ep).save()
        if item.get("status") == "ok":
            return f"reel {n} déjà validé" + ("" if ig is None else " ; choix feed noté pour le rangement")
        return bg(ctx, f"Reel {n} validé", validate_reel(ctx, ep, n))

    async def reels_show(nums=None):
        ep = reels_or_fail()
        nums = [int(x) for x in nums or []] or sorted(int(k) for k, it in RS(ep).data["items"].items()
                                                       if it.get("status") in ("ok", "preview"))
        asyncio.create_task(show_reels(ctx, ep, nums))     # just sending files: no need to wait for the heavy queue
        return f"j'envoie les reels {', '.join(map(str, nums))} tels quels (sans rien refaire)"

    async def reels_stop():
        ep = reels_or_fail()
        stopped = stop_reels(ep)
        busy = f" ; « {RUNNING['label']} » en cours se termine (quelques secondes à 1 min)" if RUNNING else ""
        return (f"annulé pour les reels {', '.join(map(str, stopped))} : ils gardent leur version actuelle{busy}"
                if stopped else f"rien en attente{busy}")

    async def reels_cover_search(nums=None, want=""):
        ep = reels_or_fail()
        nums = [int(x) for x in nums or [] if str(x).isdigit() or isinstance(x, int)]
        if not nums:                                       # « les covers » = every reel already filed / validated
            nums = sorted(int(k) for k, it in RS(ep).data["items"].items() if it.get("status") == "ok")
        if not nums:
            return "dis-moi quels reels"
        if want:                                           # his taste for the photo, kept for every future cover
            prefs = [x for x in str(reg.data.get("cover_want", "")).split(" | ") if x] + [str(want)[:200]]
            reg.data["cover_want"] = " | ".join(dict.fromkeys(prefs))[-600:]
            reg.save()
        return bg(ctx, f"Nouvelles covers (reels {', '.join(map(str, nums))})", better_covers(ctx, ep, nums),
                  limit=6 * 60 * len(nums))

    async def reel_undrop(n):
        ep = reels_or_fail()
        return bg(ctx, f"Reel {n} récupéré", undrop_reel(ctx, ep, int(n)))

    async def reels_file(feed=None):
        ep = reels_or_fail()
        if not reels_unfiled(ep):
            return "aucun reel validé à ranger"
        nums = [int(x) for x in feed or []]
        return bg(ctx, "Rangement des reels", file_reels(ctx, ep, nums if feed is not None else None))

    async def reel_drop(n):
        ep = reels_or_fail()
        return bg(ctx, f"Reel {n} jeté", drop_reel(ctx, ep, int(n)))

    async def reel_cover(n, photo=None, small=None, big=None, gold=None, zoom=None):
        ep = reels_or_fail()
        n = int(n)
        item = RS(ep).data["items"].get(str(n)) or {}
        if not item.get("file"):
            return f"le reel {n} n'est pas encore monté"
        text = {"small": small or "", "big": big or "", "gold": gold or ""} if (big or gold or small) else None
        if photo == "next":
            photo = (int(item.get("cover_pick") or 1) % max(1, int(item.get("cover_count") or 1))) + 1
        if zoom and not photo:                             # zoom alone = closer on the photo already chosen
            photo = item.get("cover_pick")
        return bg(ctx, f"Cover du reel {n}", redo_cover(ctx, ep, n, text, int(photo) if photo else None,
                                                          float(zoom) if zoom else None), limit=5 * 60)

    async def reels_resend(nums=None):
        ep = reels_or_fail()
        return resend_reels(ctx, ep, [int(x) for x in nums or []] or None)

    async def guest_instagram(handle, guest=None):
        from . import share
        ep = reel_ep()
        g = guest or (reg.data.get("handle_ask") or {}).get("guest") or (ep.get("guest_name") if ep else "")
        if not g:
            return "quel guest ?"
        await set_guest_handle(ctx, g, "" if str(handle).lower() in ("", "none", "aucun") else str(handle))
        return "fait (message envoyé)"

    async def covers_ok_t(nums=None):
        ep = reels_or_fail()
        await covers_ok(ctx, ep, [int(x) for x in nums or []] or None)
        return "fait (message envoyé)"

    async def shorts_plan_t():
        return await shorts_show(ctx)

    async def shorts_schedule(dates=None):
        from datetime import datetime, timezone
        from . import shorts
        if dates:
            ep = reels_or_fail()
            now = datetime.now(timezone.utc)
            for k, v in dates.items():
                item = RS(ep).data["items"].get(str(int(k)))
                if not item or not item.get("filed"):
                    return f"le reel {k} n'est pas rangé : pas de Short"
                if (item.get("yt_short") or {}).get("posted"):
                    return f"le Short du reel {k} est déjà en ligne : je n'y touche plus"
                try:
                    item["short_at"] = shorts.iso(shorts.parse_choice(str(v), now))
                except ValueError as e:
                    return str(e)
            RS(ep).save()
        await shorts_watch(ctx)
        return "lancé (seuls les reels en « ready » dans ClickUp, cover validée, sont programmés)"

    return {"reels_propose": reels_propose, "reels_select": reels_select, "reel_adjust": reel_adjust,
            "reel_subtitles": reel_subtitles, "reels_resend": reels_resend, "reel_cover": reel_cover,
            "reels_file": reels_file, "reel_undrop": reel_undrop, "reels_cover_search": reels_cover_search,
            "reels_show": reels_show, "reels_stop": reels_stop,
            "shorts_plan": shorts_plan_t, "shorts_schedule": shorts_schedule, "covers_ok": covers_ok_t, "guest_instagram": guest_instagram,
            "reel_validate": reel_validate, "reel_drop": reel_drop,
            "get_status": get_status, "title_chat": title_chat, "choose_axis": choose_axis, "other_frames": other_frames,
            "validate": validate, "reopen": reopen, "redo_thumbnails": redo_thumbnails, "set_design": set_design,
            "set_title": set_title, "set_quote": set_quote, "set_part": set_part, "edit_description": edit_description,
            "send_recap": send_recap_t, "publish": publish, "chapters": chapters, "badge": badge,
            "thumbnail_feedback": thumbnail_feedback, "propose_claude_code": propose_claude_code,
            "start_episode": start_episode, "scan_youtube": scan_youtube, "costs": costs, "health_check": health_check}


ASSIST_LOCK = asyncio.Lock()


async def ask_assistant(ctx, text: str, images: list | None = None):
    """One message from Loïc → the chat model acts with its tools → one short answer."""
    import base64
    images = list(images or [])
    MEMORY.add("user", text + (f" [+{len(images)} capture(s)]" if images else ""))
    async with ASSIST_LOCK:   # one conversation turn at a time (heavy jobs run in the background)
        try:
            await ctx.bot.send_chat_action(cfg.chat_id, "typing")
        except Exception:  # noqa: BLE001
            pass
        ep = reg.episode(reg.active) if reg.active else None
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                "data": base64.standard_b64encode(open(p, "rb").read()).decode()}}
                   for p in images[:4]] + [{"type": "text", "text": text or "(capture sans texte)"}]
        try:
            ctx_text = await run(assistant_context, ep) + "\n" + reels_context()
            hist = MEMORY.history()
            reply, actions = await assistant.converse(pipe.llm, CHAT_MODEL, ctx_text, hist, content, tool_handlers(ctx, images))
        except Exception as e:  # noqa: BLE001
            log.exception("assistant")
            await say(ctx, f"⚠️ Je n'arrive pas à te répondre : <code>{esc(str(e)[-300:])}</code>")
            return
        if actions:
            log.info("assistant actions: %s", actions)
            MEMORY.add("assistant", "[actions : " + " ; ".join(a.split(" → ")[0] for a in actions) + "]")
        reply = "\n".join(x for x in reply.splitlines() if not x.strip().startswith("[actions")).strip()
        if reply:
            await say(ctx, esc(reply))


def run_check() -> str:
    import contextlib
    import io

    from . import check
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check.main()
    return buf.getvalue()


async def start_video(ctx, vid: str):
    v = await run(pipe.yt.video, vid)
    reg.mark_seen(vid)
    ep = reg.episode(vid)
    ep["title"] = v["snippet"]["title"]
    ep.stage = "waiting_transcript"
    ep.save()
    reg.active = vid
    await say(ctx, f"OK, je prends <b>{esc(ep['title'])}</b>.")
    await poll_transcripts(ctx)


async def pick_axis(ctx, ep, i: int):
    a = ep["axes"][i]
    ep["final"] = {**a, "guest_name": ep.get("guest_name")}
    for k in ("pick_guest", "pick_marius", "shown_guest", "shown_marius", "validated"):
        ep.data.pop(k, None)
    ep.stage = "frames_proposed"
    ep.save()
    await say(ctx, f"👍 Axe retenu : “{esc(a['top'])} <b>{esc(a['key'])}</b> {esc(a['bottom'])}”")
    asyncio.create_task(guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, "guest")))


async def title_discussion(ctx, ep, text: str):
    """The hook discussion itself stays on the creative model (with the cached transcript)."""
    res = await run(pipe.refine, ep, text)
    ep.save()
    if res.get("final"):
        ep.stage = "frames_proposed"
        for k in ("pick_guest", "pick_marius", "validated"):
            ep.data.pop(k, None)
        ep.save()
        f = clean_quote(res["final"])
        await say(ctx, f"{esc(res.get('reply'))}\n\n👍 Retenu : “{esc(f['top'])} <b>{esc(f['key'])}</b> {esc(f['bottom'])}”")
        asyncio.create_task(guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, "guest")))
    elif res.get("axes"):
        ep.stage = "axes_proposed"
        ep.save()
        await send_axes(ctx, ep, intro=esc(res.get("reply")))
    else:
        await say(ctx, esc(res.get("reply") or "…"))


async def couts_cmd(update: Update, ctx):
    if allowed(update):
        days = float(ctx.args[0]) if ctx.args and ctx.args[0].replace(".", "").isdigit() else 1
        await update.message.reply_text(pipe.llm.ledger.summary(days) + "\n\n(estimation ; la Console Anthropic fait foi)")


# ---------------------------------------------------------------- reels (claude/btr-reels-workflow.md)
# The reels store (state.Reels) is only changed here, on the event loop; the render runs in a worker thread and
# returns its results. Buttons carry the list id, so a button from an older list can never act on a newer one.
SHOT_NAMES = {"guest": "guest", "marius": "Marius", "unsure": "guest", "split": "écran scindé", "center": "plan centré"}


def RS(ep) -> Reels:
    return Reels.of(ep)


def reel_ep():
    vid = reg.data.get("reels_vid")
    return reg.episode(vid) if vid else None


def reel_cand(ep, n: int) -> dict | None:
    return next((c for c in RS(ep).data["cands"] if c["n"] == n), None)


def reel_item(ep, n: int) -> dict:
    it = RS(ep).data["items"].setdefault(str(n), {})
    it.setdefault("shift", [0.0, 0.0])
    it.setdefault("cuts", [])
    return it


def reel_kb(ep):
    d = RS(ep).data
    sel = set(d.get("sel") or [])
    nums = [c["n"] for c in d["cands"]]
    rows = [[B(("✅ " if n in sel else "") + str(n), callback_data=f"rsel:{d.get('id')}:{n}") for n in nums[i:i + 5]]
            for i in range(0, len(nums), 5)]
    rows.append([B(f"🎬 Monter la sélection ({len(sel)})", callback_data=f"rgo:{d.get('id')}")])
    return K(rows)


def reel_list_parts(ep) -> list[str]:
    """The list as Telegram messages under 4096 characters, split between moments, never inside a tag."""
    from .srt import fmt
    cands = RS(ep).data["cands"]
    head = (f"🎞️ <b>{len(cands)} moments pour les reels</b> · {esc(str(pipe.reel_title(ep))[:120])}\n"
            "Coche ceux que tu veux (6 par semaine), puis « Monter la sélection ».\n")
    parts, cur = [], head
    for c in cands:
        d = int(c["end_s"] - c["start_s"])
        warn = "" if c.get("verified") else " ⚠️ début pas retrouvé mot pour mot dans le transcript"
        entry = (f"\n<b>{c['n']}.</b> {fmt(c['start_s'])} · {d} s · <b>{esc(str(c.get('title'))[:80])}</b>\n"
                 f"“{esc(str(c.get('hook', ''))[:200])}”\n<i>{esc(str(c.get('why'))[:200])}</i>{warn}\n")
        if len(cur) + len(entry) > 3900:
            parts.append(cur)
            cur = ""
        cur += entry
    parts.append(cur)
    return parts


async def propose_reels(ctx, vid: str | None = None):
    active = reg.episode(reg.active) if reg.active else None
    ep = await run(pipe.reel_episode, vid, active)
    await say(ctx, f"🎞️ Je relis « {esc(pipe.reel_title(ep))} » et je cherche les 10 meilleurs moments pour des reels…")
    data = await run(pipe.reel_candidates, ep)
    if not data["cands"]:
        await say(ctx, "Je n'ai trouvé aucun moment exploitable dans ce transcript.")
        return
    RS(ep).data = data
    RS(ep).save()
    reg.data["reels_vid"] = ep.video_id
    reg.save()
    parts = reel_list_parts(ep)
    for i, part in enumerate(parts):
        await say(ctx, part, **({"reply_markup": reel_kb(ep)} if i == len(parts) - 1 else {}))


def reel_caption(ep, n: int) -> str:
    c, item = reel_cand(ep, n) or {}, reel_item(ep, n)
    shots = ", ".join(f"{SHOT_NAMES.get(k, k)} ×{v}" for k, v in (item.get("shots") or {}).items())
    notes = []
    if (item.get("confidence") or 100) < 85:
        notes.append("⚠️ début ou fin repérés avec un doute")
    if item.get("missing_cuts"):
        notes.append("⚠️ pas trouvé, donc pas coupé : " + " / ".join(f"« {x} »" for x in item["missing_cuts"]))
    if item.get("fixes_not_found"):
        notes.append("⚠️ correction pas trouvée dans le texte : " + " / ".join(f"« {x} »" for x in item["fixes_not_found"]))
    if item.get("names"):
        notes.append("🔎 Noms vérifiés (texte de l'épisode + web) : " + " / ".join(item["names"][:6]))
    vis = item.get("visibility") or {}
    if vis.get("short"):
        notes.append("⚠️ mots affichés trop brièvement : " + ", ".join(f"« {w} » {s} s" for w, s in vis["short"][:5]))
    if item.get("doubts"):
        notes.append("🔎 Mots où ton SRT et l'audio ne disent pas pareil (mon choix après →) :\n"
                     + "\n".join(item["doubts"][:4]) + (f"\n(+{len(item['doubts']) - 4} autres)" if len(item["doubts"]) > 4 else ""))
    return (f"🎞️ Reel {n} · {item.get('duration')} s · {str(c.get('title'))[:80]}\n“{str(c.get('hook', ''))[:200]}”\n"
            f"Plans : {shots}" + ("\n" + "\n".join(notes) if notes else "")
            + "\nDis-moi en texte s'il faut changer quelque chose (« commence 2 s plus tôt », « coupe la dernière phrase »).")


def reel_tasks_taken(ep, n: int) -> set:
    return {it.get("clickup_task") for k, it in RS(ep).data["items"].items() if k != str(n) and it.get("clickup_task")}


async def send_reel(ctx, ep, n: int):
    d = RS(ep).data
    item = reel_item(ep, n)
    kb = K([[B("✅ Valider", callback_data=f"rok:{d.get('id')}:{n}"), B("🗑 Jeter", callback_data=f"rno:{d.get('id')}:{n}")]])
    slots = ""
    with open(item["file"], "rb") as f:
        await ctx.bot.send_video(cfg.chat_id, f, caption=(reel_caption(ep, n)[:960 - len(slots)] + slots), supports_streaming=True,
                                 width=1080, height=1920, duration=int(item["duration"]), reply_markup=kb,
                                 read_timeout=300, write_timeout=300)
    MEMORY.add("assistant", f"[vidéo envoyée : reel {n} ({item['duration']} s), {(reel_cand(ep, n) or {}).get('title')}]")


# bump the id when the reel rules change: after the deploy, Loïc gets one button to get his chosen reels again
REELS_RULES = ("2026-10-29-names", "chaque mot reste au moins 0,5 s à l'écran (fini les mots de fin de phrase qui "
                                   "flashent), la fin d'une phrase n'est plus collée au début de la suivante sur une "
                                   "page, et les noms propres sont vérifiés avec le texte de l'épisode et le web. Les "
                                   "reels déjà validés le restent.")


REELS_FILES = "captions-2"   # bump when the Drive layout / file names change: validated reels are re-filed at boot


def loic_wrote(words: str) -> bool:
    """Every word of a correction appears in one of Loïc's own messages (old fixes made before the guard)."""
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())            # noqa: E731
    his = {norm(t) for m in MEMORY._list() if m["role"] == "user" for t in m["content"].split()}
    new = {norm(t) for t in str(words).split()} - {""}
    return bool(new) and new <= his


async def make_reel(ctx, ep, list_id: int, n: int) -> bool:
    """Render reel n of list `list_id` (skipped if that list was replaced or the reel dropped meanwhile)."""
    d = RS(ep).data
    item = reel_item(ep, n)
    cand = reel_cand(ep, n)
    if d.get("id") != list_id or not cand or item.get("status") != "queued":
        return False                                   # replaced list, dropped, or already taken by another chain
    item["status"] = "rendering"
    need = item.pop("need", None) or ("subs" if item.get("file") else "full")
    if need == "subs" and not pipe.reel_edit_kept(ep, n):
        need = "full"                                  # edit made before the subtitles-only redo, or cleaned up
    item["fixes"] = [f for f in item.get("fixes") or [] if f.get("ok") or loic_wrote(f.get("to", ""))]
    cand = dict(cand, together=list(item.get("together") or []))
    if need == "subs":
        res = await run(pipe.reel_subtitles, ep, dict(cand), list(item.get("fixes") or []), item.get("sub_note", ""))
    else:
        res = await run(pipe.render_reel, ep, dict(cand), list(item["shift"]), list(item["cuts"]),
                        list(item.get("fixes") or []), item.get("sub_note", ""))
    if RS(ep).data.get("id") != list_id:                  # a new list arrived during the render
        return False
    if item.get("status") == "dropped":
        return False
    if need != "subs":
        for k in ("cover", "cover_pick", "cover_count"):          # new stills: the cover is made again
            item.pop(k, None)
    if item.get("said") and res.get("said") != item.get("said"):
        item.pop("captions", None)                        # words changed (names fixed): captions written again
    item.update(res)
    item["status"] = "ok" if item.pop("keep_ok", False) else "preview"
    if not item.get("captions"):
        item["captions"] = await run(pipe.reel_captions, ep, res["said"])
    if item.pop("redo", False):                           # Loïc asked for another change during this render
        item["status"] = "queued"
        RS(ep).save()
        bg(ctx, f"Reel {n} (retouche)", reel_chain(ctx, ep, list_id, [n]))
        await say(ctx, f"Reel {n} : je refais tout de suite avec ta dernière demande.")
        return True
    RS(ep).save()
    await send_reel(ctx, ep, n)
    if item.get("filed") and item["status"] == "ok":    # already on Drive / ClickUp: the new version replaces it
        await say(ctx, await share_reel(ctx, ep, n, quiet=True))
    return True


def queue_reel(ctx, ep, n: int, need: str) -> str:
    """(Re)make reel n: the whole edit ("full") or only its subtitles ("subs"). Never two jobs for one reel:
    a change asked while it is being made is done right after."""
    it = reel_item(ep, n)
    want = "full" if "full" in (need, it.get("need")) else "subs"
    if it.get("status") == "rendering":
        it["redo"], it["need"] = True, want
        RS(ep).save()
        return f"reel {n} en cours de montage : je prends ta demande juste après"
    it["need"] = want
    if it.get("status") == "queued":
        RS(ep).save()
        return f"reel {n} déjà en file d'attente : ta demande est prise en compte"
    it["status"] = "queued"
    RS(ep).save()
    what = "les sous-titres (quelques secondes)" if want == "subs" else "le montage (quelques minutes)"
    return bg(ctx, f"Reel {n} (retouche)", reel_chain(ctx, ep, RS(ep).data.get("id"), [n])) + f" · je refais {what}"


async def reel_chain(ctx, ep, list_id: int, nums: list[int], done: int = 0, total: int | None = None):
    """One reel per heavy job: a new episode's thumbnails (or a click on Valider) can slot in between two reels."""
    total = total or len(nums)
    n, rest = nums[0], nums[1:]
    ok = False
    try:
        ok = await make_reel(ctx, ep, list_id, n)
    except Exception as e:  # noqa: BLE001
        log.exception("reel %s", n)
        it = reel_item(ep, n)
        if it.get("status") == "rendering":
            it["status"] = "failed"
        RS(ep).save()
        await say(ctx, f"⚠️ Reel {n} : échec (<code>{esc(str(e)[-300:])}</code>)." + (" Je passe au suivant." if rest else ""))
    done += 1 if ok else 0
    if rest and RS(ep).data.get("id") == list_id:
        bg(ctx, f"Reel {rest[0]}", reel_chain(ctx, ep, list_id, rest, done, total))
    elif not rest:
        if not reels_pending(ep):                         # all decided already (validated reels redone)
            await maybe_dispatch(ctx, ep)
            return
        await say(ctx, f"✅ {done} reel(s) prêt(s) sur {total}. Valide ou jette chacun : quand tout est décidé, je te "
                       "demande lesquels vont en feed Instagram, puis je fais les covers et je range tout sur Drive et ClickUp.")


def start_reels(ctx, ep, nums: list[int]) -> str:
    """Queue the reels not made yet (or failed / dropped): a double tap, or ticking one more moment and pressing
    again, never renders a reel twice. A reel already made is changed with reel_adjust."""
    d = RS(ep).data
    todo = []
    for n in nums:
        it = reel_item(ep, n)
        if it.get("status") in ("queued", "rendering", "preview", "ok"):
            continue
        it["status"], it["need"] = "queued", "full"
        todo.append(n)
    RS(ep).save()
    if not todo:
        return "ces reels sont déjà montés ou en cours (pour en changer un : dis-moi quoi changer)"
    asyncio.create_task(say(ctx, f"🎬 Je monte {len(todo)} reel(s) : {', '.join(map(str, todo))}. Compte quelques minutes "
                                 "par reel, je t'envoie chacun dès qu'il est prêt."))
    return bg(ctx, f"Reel {todo[0]}", reel_chain(ctx, ep, d.get("id"), todo))


def resend_reels(ctx, ep, nums: list[int] | None = None) -> str:
    """Make again the chosen reels (all ticked ones by default, never the dropped ones) with the current rules: the
    subtitles only when the edit is still here, the whole edit otherwise (failed, interrupted, cleaned up)."""
    d = RS(ep).data
    todo = []
    for n in nums or sorted(d.get("sel") or []):
        it = reel_item(ep, n)
        if it.get("status") in ("dropped", "queued", "rendering") or not reel_cand(ep, n):
            continue
        it["need"] = "subs" if it.get("status") in ("preview", "ok") and pipe.reel_edit_kept(ep, n) else "full"
        if it.get("status") == "ok":
            it["keep_ok"] = True                          # already validated: stays validated with the new version
        it["status"] = "queued"
        it.pop("redo", None)
        todo.append(n)
    RS(ep).save()
    if not todo:
        return "aucun reel à renvoyer (déjà en cours, ou jetés)"
    asyncio.create_task(say(ctx, f"🎬 Je refais les reels {', '.join(map(str, todo))} avec les règles actuelles et je te "
                                 "les renvoie un par un."))
    return bg(ctx, f"Reel {todo[0]}", reel_chain(ctx, ep, d.get("id"), todo))


async def validate_reel(ctx, ep, n: int):
    """Step 1: Loïc validates (or drops) each reel. Nothing is filed yet: once every chosen reel is decided, he picks
    which ones also go on Instagram (feed), and only then are the covers made and the files put on Drive / ClickUp."""
    from pathlib import Path

    from . import reels as R
    item = reel_item(ep, n)
    if not item.get("file") or not Path(item["file"]).exists():
        await say(ctx, f"Le reel {n} n'est plus disponible (liste remplacée ou fichier supprimé).")
        return
    item["status"] = "ok"
    RS(ep).save()
    R.slim(Path(item["file"]).parent, keep_final=True)
    if item.get("filed"):                                 # already filed: refile the new version in place
        await say(ctx, f"✅ Reel {n} validé à nouveau : je mets à jour Drive et ClickUp.")
        await say(ctx, await share_reel(ctx, ep, n, quiet=True))
        return
    left = reels_pending(ep)
    await say(ctx, f"✅ Reel {n} validé." + (f" Encore à valider ou jeter : {', '.join(map(str, left))}." if left else ""))
    await maybe_dispatch(ctx, ep)


def reels_pending(ep) -> list[int]:
    """Chosen reels not decided yet (being made, waiting for his ✅ / 🗑, or failed)."""
    d = RS(ep).data
    return sorted(n for n in d.get("sel") or [] if (d["items"].get(str(n)) or {}).get("status") not in ("ok", "dropped"))


def reels_unfiled(ep) -> list[int]:
    d = RS(ep).data
    return sorted(int(k) for k, it in d["items"].items() if it.get("status") == "ok" and not it.get("filed"))


def dispatch_kb(ep):
    d = RS(ep).data
    feed = d.setdefault("feed", [])
    rows = []
    for n in reels_unfiled(ep):
        t = str((reel_cand(ep, n) or {}).get("title") or "")[:28]
        mark = f"📸 {feed.index(n) + 1}" if n in feed else "▫️"
        rows.append([B(f"{mark} · Reel {n} · {t}", callback_data=f"rfeed:{d.get('id')}:{n}")])
    k = len([n for n in feed if n in reels_unfiled(ep)])
    rows.append([B(f"➡️ Ranger ({k} en feed, {len(reels_unfiled(ep)) - k} TikTok + Shorts)",
                   callback_data=f"rfile:{d.get('id')}")])
    return K(rows)


async def maybe_dispatch(ctx, ep, force: bool = False):
    """Step 2, once every chosen reel is validated or dropped: which ones go on the Instagram feed?"""
    if reels_pending(ep) and not force:
        return
    todo = reels_unfiled(ep)
    if not todo:
        return
    d = RS(ep).data
    d["feed"] = [n for n in d.get("feed") or [] if n in todo]
    RS(ep).save()
    try:
        free = await run(pipe.reel_ig_slots, ep, reel_tasks_taken(ep, 0))
    except Exception:  # noqa: BLE001
        log.exception("ig slots")
        free = None
    if free is None:
        slots = "(ClickUp pas connecté : /connect)"
    elif free:
        slots = f"{len(free)} case(s) Instagram libre(s) pour cet épisode : {', '.join(free)}."
    else:
        slots = "Plus de case Instagram libre pour cet épisode (un reel en feed créera une tâche sans date)."
    await say(ctx, f"🎬 {len(todo)} reels validés, pas encore rangés. Lesquels vont aussi sur Instagram (feed) ?\n"
                   f"{slots}\nCoche dans l'ordre de publication (le 1er coché prend la 1re date). Les autres vont "
                   "sur TikTok + YouTube Shorts seulement. Ensuite « Ranger » : je fais les covers et je range tout "
                   "sur Drive et ClickUp.", reply_markup=dispatch_kb(ep))


async def file_reels(ctx, ep, feed: list[int] | None = None):
    """Step 3: covers, then Drive (named for the calendar) and ClickUp, feed reels first so they take the slots in the
    order he ticked them."""
    d = RS(ep).data
    todo = reels_unfiled(ep)
    if not todo:
        await say(ctx, "Aucun reel validé à ranger.")
        return
    feed = [n for n in (feed if feed is not None else d.get("feed") or []) if n in todo]
    order = feed + [n for n in todo if n not in feed]
    await say(ctx, f"🗂 Je range {len(order)} reels ({len(feed)} en feed) : covers, Drive, ClickUp…")
    if feed:
        try:
            await ask_handle(ctx, ep)
        except Exception:  # noqa: BLE001
            log.exception("ask handle")
    lines = []
    for n in order:
        item = reel_item(ep, n)
        item["instagram"] = n in feed
        try:
            lines.append(await share_reel(ctx, ep, n, quiet=True))
            item["filed"] = True
        except Exception as e:  # noqa: BLE001
            log.exception("file reel")
            lines.append(f"Reel {n} : ⚠️ <code>{esc(str(e)[-200:])}</code>")
        RS(ep).save()
    d["feed"] = []
    RS(ep).save()
    await say(ctx, "\n\n".join(lines) + "\n\nLes légendes sont dans chaque tâche ClickUp (blocs à copier). "
                   "Pour changer : « le 3 finalement en feed », « cover reel 2 : autre photo ».")
    await say(ctx, "Dernière étape : valide chaque cover (« ✅ Cover OK », ou écris « je valide les covers »). La tâche "
                   "ClickUp passe en « ready » et je programme le Short YouTube tout seul.")


async def redo_cover(ctx, ep, n: int, text: dict | None, photo: int | None, zoom: float | None = None):
    item = reel_item(ep, n)
    await say(ctx, f"🖼 Reel {n} : je refais la cover" + (f" avec la photo {photo}" if photo else "")
              + (f", zoom x{zoom:g} sur la tête" if zoom and zoom > 1 else "") + "…")
    try:
        res = await run(pipe.reel_cover, ep, n, dict(item), text, photo, zoom)
    except Exception as e:  # noqa: BLE001
        await say(ctx, f"⚠️ Cover du reel {n} : <code>{esc(str(e)[-200:])}</code>")
        return
    if text and not res.get("cover_text") == pipe_cover_text(text):
        await say(ctx, "Ces mots ne sont pas dits tels quels dans le reel : je garde l'accroche d'avant. "
                       "Donne-moi des mots exacts, dans l'ordre.")
    item.update(res)
    if item.pop("cover_ok", None):
        try:
            await run(pipe.reel_status, dict(item), "approved", ("ready",))   # validate the new cover again
        except Exception:  # noqa: BLE001
            log.exception("clickup approved")
    RS(ep).save()
    if item.get("filed"):
        await share_reel(ctx, ep, n)                      # sends the cover; same Drive link, new cover on ClickUp
    else:
        await send_cover(ctx, ep, n)


def pipe_cover_text(text: dict) -> dict:
    return {k: (v.upper() if k != "small" else v) for k, v in text.items()}


async def show_reels(ctx, ep, nums: list[int]):
    """« Remontre-moi les reels » : the files as they are (video + cover), nothing made again."""
    from pathlib import Path
    sent = []
    for n in nums:
        item = reel_item(ep, n)
        if not item.get("file") or not Path(item["file"]).exists():
            await say(ctx, f"Reel {n} : plus de fichier sur le serveur.")
            continue
        where = {"ok": "validé", "preview": "à valider", "dropped": "jeté"}.get(item.get("status"), item.get("status", ""))
        if item.get("filed"):
            where += " · " + ("feed + TikTok + Shorts" if item.get("instagram", True) else "TikTok + Shorts")
        title = str((reel_cand(ep, n) or {}).get("title") or "")
        cap = f"🎞️ Reel {n} · {title} · {where}" + (f"\n{item['file_base']}.mp4" if item.get("file_base") else "")
        with open(item["file"], "rb") as f:
            await ctx.bot.send_video(cfg.chat_id, f, caption=cap[:1000], supports_streaming=True, width=1080, height=1920,
                                     duration=int(item.get("duration") or 0), read_timeout=300, write_timeout=300)
        await send_cover(ctx, ep, n)
        sent.append(n)
    MEMORY.add("assistant", f"[reels remontrés tels quels : {', '.join(map(str, sent))}]")


async def restore_validated(ctx, ep, since: str):
    """Put back the version Loïc validated for every filed reel that was made again after `since` (UTC): the Drive
    revision from before, on Drive (same link) and on the server."""
    from pathlib import Path

    from . import share
    sec = share.Secrets(cfg.data_dir)
    done, kept = [], []
    for k, it in sorted(RS(ep).data["items"].items(), key=lambda x: int(x[0])):
        fid = (it.get("drive_ids") or {}).get("video")
        if not it.get("filed") or not fid or not it.get("file"):
            continue
        try:
            r = await run(share.restore_before, sec, cfg.youtube_client[:2], fid, since, Path(it["file"]))
        except Exception as e:  # noqa: BLE001
            log.exception("restore")
            await say(ctx, f"⚠️ Reel {k} : retour impossible (<code>{esc(str(e)[-150:])}</code>)")
            continue
        st = Path(it["file"]).stat()
        it.setdefault("drive_ids", {})["video_sig"] = f"{st.st_size}-{int(st.st_mtime)}"   # = what Drive holds
        if r == "restored":
            done.append(int(k))
        else:
            kept.append(int(k))
    RS(ep).save()
    if done:
        await say(ctx, f"↩️ Reels {', '.join(map(str, done))} : la version que tu avais validée est remise (Drive, même "
                       "lien, et serveur). " + (f"Pas touchés : {', '.join(map(str, kept))}." if kept else ""))
    elif kept:
        await say(ctx, f"✅ Reels {', '.join(map(str, kept))} : aucun n'avait été refait, ils sont tels que validés.")


def stop_reels(ep) -> list[int]:
    """Cancel the reels waiting to be made again: they keep their current version (the one in progress finishes)."""
    stopped = []
    for k, it in RS(ep).data["items"].items():
        if it.get("status") == "queued":
            it["status"] = "ok" if it.get("keep_ok") else ("preview" if it.get("file") else "failed")
            for x in ("keep_ok", "need", "redo"):
                it.pop(x, None)
            stopped.append(int(k))
    RS(ep).save()
    return sorted(stopped)


async def better_covers(ctx, ep, nums: list[int]):
    """« Trouve de meilleurs screenshots » : for each reel, a wider search of sharp 4K stills, the cover chosen again
    (photo compared with the approved cover), sent with the other candidates; Drive / ClickUp updated if filed."""
    from pathlib import Path
    for n in nums:
        item = reel_item(ep, n)
        await say(ctx, f"🔎 Reel {n} : je cherche de nouvelles photos (environ 1 min)…")
        try:
            count = await run(pipe.reel_cover_search, ep, n)
            item.update(await run(pipe.reel_cover, ep, n, dict(item)))
            RS(ep).save()
        except Exception as e:  # noqa: BLE001
            log.exception("cover search")
            await say(ctx, f"⚠️ Reel {n} : <code>{esc(str(e)[-200:])}</code>")
            continue
        sheet = Path(item["cover"]).parent / "cover" / "sheet.jpg"
        if sheet.exists():
            with open(sheet, "rb") as f:
                await ctx.bot.send_photo(cfg.chat_id, f, caption=f"Reel {n} : {count} nouvelles photos nettes (moitié "
                                                                  "bouche ouverte, moitié fermée, jamais celles déjà "
                                                                  f"vues). Pour en prendre une : « cover reel {n} : photo 5 ».")
        if item.get("filed"):
            await share_reel(ctx, ep, n)                  # sends the cover, then Drive / ClickUp
        else:
            await send_cover(ctx, ep, n)


async def send_cover(ctx, ep, n: int):
    from pathlib import Path
    item = reel_item(ep, n)
    if not item.get("cover") or not Path(item["cover"]).exists():
        return
    t = item.get("cover_text") or {}
    words = " / ".join(x for x in (t.get("small"), t.get("big"), t.get("gold")) if x)
    kb = K([[B("✅ Cover OK", callback_data=f"rcov:{RS(ep).data.get('id')}:{n}")]]) \
        if item.get("status") == "ok" and not item.get("cover_ok") else None
    with open(item["cover"], "rb") as f:
        await ctx.bot.send_document(cfg.chat_id, f, filename=Path(item["cover"]).name, reply_markup=kb,
                                    caption=f"🖼 Cover du reel {n} : « {words} », photo {item.get('cover_pick', 1)}/"
                                            f"{item.get('cover_count', 1)}. Pour changer : « cover reel {n} : autre photo » "
                                            "ou « cover reel {n} : texte … ».".replace("{n}", str(n))[:1000])
    grid = item.get("cover_grid")
    if grid and Path(grid).exists():
        issues = item.get("cover_issues") or []
        verdict = ("✅ visage et texte entiers dans la grille Instagram (3:4, centre et haut)" if not issues
                   else "⚠️ " + " ; ".join(issues) + f". Essaie « cover reel {n} : autre photo ».")
        with open(grid, "rb") as f:
            await ctx.bot.send_photo(cfg.chat_id, f, caption=f"Reel {n} · aperçu grille : {verdict}"[:1000])
    MEMORY.add("assistant", f"[cover du reel {n} envoyée : « {words} », photo {item.get('cover_pick', 1)} sur "
                            f"{item.get('cover_count', 1)}]")


async def share_reel(ctx, ep, n: int, quiet: bool = False, cover: bool = True) -> str:
    """Cover (if missing), Drive + ClickUp for a validated reel. quiet: return the summary line instead of saying it."""
    from pathlib import Path
    item = reel_item(ep, n)
    if not item.get("cover") or not Path(item["cover"]).exists():
        try:
            item.update(await run(pipe.reel_cover, ep, n, dict(item)))
            RS(ep).save()
        except Exception:  # noqa: BLE001
            log.exception("cover")
    if cover:
        await send_cover(ctx, ep, n)
    from .pipeline import CAPTIONS_V
    if (item.get("captions") or {}).get("v") != CAPTIONS_V and item.get("said"):
        caps = await run(pipe.reel_captions, ep, item["said"])        # captions in the current approved format
        if caps:
            item["captions"] = caps
            RS(ep).save()
    taken = reel_tasks_taken(ep, n)
    cand = reel_cand(ep, n) or {}
    res = await run(pipe.reel_share, ep, n, dict(item, title=cand.get("title") or f"Reel {n}"), taken,
                    item.get("instagram", True))
    item["links"] = res.get("links") or item.get("links") or {}
    for k in ("clickup_task", "clickup_url", "cover_sent", "clickup_kind", "clickup_orig", "drive_ids", "file_base", "clickup_name"):
        if res.get(k):
            item[k] = res[k]
    RS(ep).save()
    where = "📸 feed + TikTok + Shorts" if item.get("instagram", True) else "🎵 TikTok + Shorts"
    lines = [f"<b>Reel {n}</b> · {where}"]
    if item["links"].get("video") and not res.get("drive_error"):
        lines.append(f"📁 <a href=\"{item['links'].get('folder', item['links']['video'])}\">Drive</a> : "
                     f"{esc(res.get('file_base', ''))}.mp4")
    elif res.get("drive_error"):
        lines.append(f"📁 Drive : {esc(res['drive_error'])}")
    if res.get("clickup_url"):
        if res.get("clickup_kind") == "short":
            what = "tâche TikTok + Shorts, sans date"
        elif res.get("clickup_new"):
            what = "nouvelle tâche feed sans date (plus de case libre)"
        else:
            what = "case du calendrier"
        if res.get("clickup_freed"):
            what += f" ; « {esc(res['clickup_freed'])} » est libérée"
        lines.append(f"✅ <a href=\"{res['clickup_url']}\">{esc(res.get('clickup_name') or 'ClickUp')}</a> ({what})")
    elif res.get("clickup_error"):
        lines.append(f"ClickUp : {esc(res['clickup_error'])}")
    if res.get("drive_error", "").endswith("pas encore connecté") or res.get("clickup_error", "").endswith("pas encore connecté"):
        lines.append("→ /connect pour brancher Drive et ClickUp.")
    text = "\n".join(lines)
    if not quiet:
        await say(ctx, text)
    return text


async def drop_reel(ctx, ep, n: int):
    """Runs under the global lock: never while this reel's files are being written."""
    from pathlib import Path

    from . import reels as R
    item = reel_item(ep, n)
    item["status"] = "dropped"
    RS(ep).save()
    if item.get("file"):
        R.slim(Path(item["file"]).parent, keep_final=True)   # files kept (cleaned after 3 weeks): « Annuler » works
    await say(ctx, f"🗑 Reel {n} jeté.", reply_markup=K([[B("↩️ Annuler", callback_data=f"rund:{RS(ep).data.get('id')}:{n}")]]))
    await maybe_dispatch(ctx, ep)


async def undrop_reel(ctx, ep, n: int):
    """Dropped by mistake: back to « à valider » with the same file, or made again if its files are gone."""
    from pathlib import Path
    item = reel_item(ep, n)
    if item.get("status") != "dropped":
        await say(ctx, f"Le reel {n} n'est pas jeté.")
        return
    if item.get("file") and Path(item["file"]).exists():
        item["status"] = "preview"
        RS(ep).save()
        await say(ctx, f"↩️ Reel {n} récupéré.")
        await send_reel(ctx, ep, n)
    else:
        item["status"] = "failed"
        RS(ep).save()
        await say(ctx, esc(start_reels(ctx, ep, [n])))


async def on_reel_button(ctx, q, d: str):
    if d == "reels:propose":
        await say(ctx, esc(bg(ctx, "Moments pour les reels", propose_reels(ctx, reg.active))))
        return
    ep = reel_ep()
    parts = d.split(":")
    if not ep or not RS(ep) or len(parts) < 2 or not parts[1].isdigit() or int(parts[1]) != RS(ep).data.get("id"):
        await say(ctx, "Ce bouton vient d'une ancienne liste de reels : demande-moi la liste actuelle ou une nouvelle.")
        return
    rs = RS(ep).data
    n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    if parts[0] == "rsel" and n:
        sel = rs.setdefault("sel", [])
        sel.remove(n) if n in sel else sel.append(n)
        RS(ep).save()
        try:
            await q.edit_message_reply_markup(reel_kb(ep))
        except Exception:  # noqa: BLE001
            pass
    elif parts[0] == "rgo":
        nums = sorted(rs.get("sel") or [])
        if not nums:
            await say(ctx, "Coche d'abord au moins un moment.")
            return
        await say(ctx, esc(start_reels(ctx, ep, nums)))
    elif parts[0] == "rall":
        await say(ctx, esc(resend_reels(ctx, ep)))
    elif parts[0] in ("rok", "rsh") and n:                # rsh: button of the previous version
        await say(ctx, esc(bg(ctx, f"Reel {n} validé", validate_reel(ctx, ep, n))))
    elif parts[0] == "rund" and n:
        await say(ctx, esc(bg(ctx, f"Reel {n} récupéré", undrop_reel(ctx, ep, n))))
    elif parts[0] == "rfeed" and n:
        feed = rs.setdefault("feed", [])
        feed.remove(n) if n in feed else feed.append(n)
        RS(ep).save()
        try:
            await q.edit_message_reply_markup(dispatch_kb(ep))
        except Exception:  # noqa: BLE001
            pass
    elif parts[0] == "rcov" and n:
        try:
            await q.edit_message_reply_markup(None)
        except Exception:  # noqa: BLE001
            pass
        await covers_ok(ctx, ep, [n])
    elif parts[0] == "rfile":
        await say(ctx, esc(bg(ctx, "Rangement des reels", file_reels(ctx, ep))))
    elif parts[0] == "rno" and n:
        await say(ctx, esc(bg(ctx, f"Reel {n} jeté", drop_reel(ctx, ep, n))))


# ---------------------------------------------------------------- YouTube Shorts (btrbot/shorts.py)
# Every filed reel becomes a Short, sent private with a publishing time: YouTube makes it public by itself. Nothing is
# sent without Loïc's go (button « Programmer » or his message); a Short already public is never touched again.
def shorts_items() -> list:
    """Filed reels of every episode whose Short is not online yet, in publishing order (episode, feed first, number)."""
    out = []
    for f in sorted((reg.root / "episodes").glob("*/reels.json")):
        ep = reg.episode(f.parent.name)
        for k, it in RS(ep).data.get("items", {}).items():
            if it.get("status") == "ok" and it.get("filed") and it.get("file") and not (it.get("yt_short") or {}).get("posted"):
                out.append((ep, int(k), it))
    return sorted(out, key=lambda x: (x[0].video_id, not x[2].get("instagram", True), x[1]))


async def shorts_plan(ready_only: bool = False) -> list:
    from datetime import datetime, timezone
    from . import shorts
    items = shorts_items()
    rows = [(f"{ep.video_id}:{n}", dict(it)) for ep, n, it in items]
    look = await run(pipe.shorts_lookup, rows) if rows else {}
    entries = []
    for ep, n, it in items:
        key = f"{ep.video_id}:{n}"
        info = look.get(key) or {}
        ys = it.get("yt_short") or {}
        if ys.get("id") and info.get("checked"):
            st = info.get("status")
            if st is None:                                   # deleted on YouTube: will be sent again
                it.pop("yt_short", None)
                it.get("links", {}).pop("short", None)
                RS(ep).save()
                ys = {}
            elif st.get("privacyStatus") != "private" or not st.get("publishAt"):
                continue                                     # already public: shorts_sync marks it, never touched
        if ready_only and not ys.get("id") and info.get("cu_status") != "ready":
            continue                                         # waits for « ready » (cover validated)
        entries.append({"key": key, "ep": ep, "n": n, "item": it, "vid": ys.get("id"), "cur_at": shorts.parse(ys.get("at")),
                        "task_at": info.get("task_at"), "chosen": shorts.parse(it.get("short_at")),
                        "cu_status": info.get("cu_status")})
    return shorts.plan(entries, datetime.now(timezone.utc))


def short_name(p) -> str:
    cand = reel_cand(p["ep"], p["n"]) or {}
    return f"Reel {p['n']} · {esc(cand.get('title') or '')}"


async def shorts_show(ctx) -> str:
    from . import shorts
    plan = await shorts_plan()
    if not plan:
        await say(ctx, "▶️ Aucun reel rangé en attente de Short YouTube.")
        return "rien à programmer"
    lines = ["▶️ <b>YouTube Shorts</b> : envoyés en privé, YouTube les publie tout seul à l'heure dite (heure de Londres)."]
    eps = {p["ep"].video_id for p in plan}
    for p in plan:
        who = f"{esc(pipe.reel_title(p['ep']))} · " if len(eps) > 1 else ""
        state = {"upload": "", "move": " · à déplacer", None: " · ✅ déjà programmé"}[p["action"]]
        if not p.get("vid") and p.get("cu_status") != "ready":
            state = " · ⏳ attend « ✅ Cover OK »"
        lines.append(f"• {who}{short_name(p)} → <b>{shorts.label(p['at'])}</b> ({p['why']}){state}")
    todo = [p for p in plan if p["action"] and (p.get("vid") or p.get("cu_status") == "ready")]
    lines.append("\nC'est automatique : « ready » dans ClickUp = programmé (vérifié toutes les 15 min). Pour changer : "
                 "change la date dans ClickUp, ou écris « short 2 le 4.11 à 19h ».")
    kb = K([[B(f"▶️ Programmer maintenant ({len(todo)})", callback_data="ysch")]]) if todo else None
    await say(ctx, "\n".join(lines), reply_markup=kb)
    return f"plan envoyé ({len(todo)} à programmer)"


async def shorts_go(ctx, ready_only: bool = False, quiet: bool = False):
    from . import shorts
    full = await shorts_plan(ready_only)
    for p in full:                                   # sent earlier but still « ready » in ClickUp
        if not p["action"] and p.get("vid") and p.get("cu_status") == "ready":
            try:
                await run(pipe.reel_status, dict(p["item"]), "scheduled", ("ready",))
            except Exception:  # noqa: BLE001
                log.exception("clickup scheduled")
    plan = [p for p in full if p["action"]]
    if not plan:
        if not quiet:
            await say(ctx, "▶️ Rien à programmer : tous les Shorts sont déjà programmés.")
        return
    await say(ctx, f"▶️ J'envoie {len(plan)} Short{'s' if len(plan) > 1 else ''} sur YouTube (privés jusqu'à l'heure dite)…")
    lines, warn = [], ""
    for p in plan:
        ep, n, it = p["ep"], p["n"], p["item"]
        try:
            res = await run(pipe.short_upload, ep, n, dict(it), shorts.iso(p["at"]))
        except Exception as e:  # noqa: BLE001
            log.exception("short upload")
            msg = str(e)
            if "quota" in msg.lower() or "uploadLimitExceeded" in msg:
                lines.append(f"{short_name(p)} : ⚠️ limite d'envois YouTube du jour atteinte. Redemande /shorts demain.")
                break
            lines.append(f"{short_name(p)} : ⚠️ <code>{esc(msg[-200:])}</code>")
            continue
        it["yt_short"] = {"id": res["id"], "at": res["at"]}
        if it.get("clickup_kind") == "short" and not res.get("clickup_error"):
            it.pop("short_at", None)                 # the ClickUp date holds it now: changing it there moves the Short
        it.setdefault("links", {})["short"] = res["url"]
        RS(ep).save()
        if res.get("locked"):
            warn = ("\n\n⚠️ YouTube a gardé la vidéo en privé sans programmation : l'app Google n'est sans doute pas "
                    "encore vérifiée par YouTube. Regarde dans YouTube Studio et dis-moi ce que tu vois.")
        try:
            await share_reel(ctx, ep, n, quiet=True, cover=False)   # link in ClickUp, Drive file named for the date
        except Exception:  # noqa: BLE001
            log.exception("share after short")
        verb = "déplacé" if p["action"] == "move" else "programmé"
        extra = f" · ClickUp : {esc(res['clickup_error'])}" if res.get("clickup_error") else ""
        lines.append(f"{short_name(p)} : {verb} <b>{shorts.label(p['at'])}</b> · <a href=\"{res['url']}\">lien</a>{extra}")
    await say(ctx, "\n".join(lines) + warn + "\n\nClickUp : « scheduled ». Changer une date = la changer dans ClickUp, je "
                   "suis. À faire dans YouTube Studio si tu veux : « Vidéo associée » = l'épisode (pas possible par l'API).")


SHORTS_BUSY: dict = {}


async def shorts_watch(ctx):
    """ClickUp is the trigger: a reel task in « ready » (cover validated) gets its Short scheduled; a date changed in
    ClickUp moves a Short that is still waiting. Runs with every poll and right after « cover OK »."""
    if SHORTS_BUSY or RUNNING.get("label") == "Shorts YouTube" or "Shorts YouTube" in WAITING:
        return
    plan = await shorts_plan(ready_only=True)
    if not any(p["action"] or (p.get("vid") and p.get("cu_status") == "ready") for p in plan):
        return
    SHORTS_BUSY["on"] = True

    async def go():
        try:
            await shorts_go(ctx, ready_only=True, quiet=True)
        finally:
            SHORTS_BUSY.clear()
    bg(ctx, "Shorts YouTube", go(), limit=60 * 60)


# ---------------------------------------------------------------- Instagram (btrbot/instagram.py)
# A feed reel whose Short is scheduled is also posted on Instagram by the bot at the same time: upload ~45 min before
# (container, 24 h validity), publish at the time (checked every minute). Not connected = Loïc is told to post it.
IG_BUSY: dict = {}


def cover_sig(it: dict) -> str:
    from pathlib import Path
    try:
        st = Path(it["cover"]).stat()
        return f"{st.st_size}-{int(st.st_mtime)}"
    except Exception:  # noqa: BLE001
        return ""


def ig_items() -> list:
    out = []
    for f in sorted((reg.root / "episodes").glob("*/reels.json")):
        ep = reg.episode(f.parent.name)
        for k, it in RS(ep).data.get("items", {}).items():
            ig = it.get("ig_post") or {}
            if (it.get("status") == "ok" and it.get("filed") and it.get("instagram", True) and it.get("file")
                    and (it.get("yt_short") or {}).get("at") and not ig.get("posted") and not ig.get("failed")):
                out.append((ep, int(k), it))
    return out


async def ig_tick(ctx):
    from datetime import datetime, timedelta, timezone
    from . import share, shorts
    if IG_BUSY:
        return
    now = datetime.now(timezone.utc)
    sec = share.Secrets(cfg.data_dir)
    connected = bool(sec.get("ig_token"))
    exp = shorts.parse(sec.get("ig_expires"))
    if connected and exp and exp - now < timedelta(days=7) and reg.data.get("ig_expiry_warned") != now.date().isoformat():
        reg.data["ig_expiry_warned"] = now.date().isoformat()
        reg.save()
        await say(ctx, f"📸 L'accès Instagram expire {shorts.label(exp)} : refais un token dans l'Explorateur de l'API "
                       "Graph (app BTR - Short) et colle « ID clé_secrète token » ici. /connect pour les étapes.")
        if exp <= now:
            connected = False
    items = sorted(ig_items(), key=lambda x: x[2]["yt_short"]["at"])
    for ep, n, it in items:                                # ClickUp: Instagram « Scheduled » (the bot holds it)
        ig = it.setdefault("ig_post", {})
        if connected and not ig.get("marked"):
            ig["marked"] = True
            RS(ep).save()
            try:
                await run(pipe.ig_mark, dict(it), share.IG_SCHEDULED)
            except Exception:  # noqa: BLE001
                log.exception("clickup ig scheduled")
    for ep, n, it in items:
        at = shorts.parse(it["yt_short"]["at"])
        ig = it["ig_post"]
        if not at or at - now > timedelta(minutes=45):
            continue
        if not connected:
            if not ig.get("warned"):
                ig["warned"] = True
                RS(ep).save()
                await say(ctx, f"📸 Instagram n'est pas connecté : publie toi-même {short_name({'ep': ep, 'n': n})} à "
                               f"{shorts.label(at)} (Londres), légende dans ClickUp. /connect pour que je le fasse.")
            continue
        if now - at > timedelta(hours=12):                 # bot down for too long: Loïc decides
            ig["failed"] = "trop tard"
            RS(ep).save()
            await say(ctx, f"📸 {short_name({'ep': ep, 'n': n})} devait sortir sur Instagram {shorts.label(at)} : "
                           "je ne l'ai pas publié (trop tard). Publie-le toi-même quand tu veux.")
            continue
        made = shorts.parse(ig.get("made"))
        need = not ig.get("container") or (made and now - made > timedelta(hours=22))
        if need or now >= at:
            IG_BUSY["on"] = True
            asyncio.create_task(ig_job(ctx, ep, n, it, "prepare" if need else "publish"))
            return


async def ig_job(ctx, ep, n: int, it: dict, step: str):
    ig = it["ig_post"]
    name = short_name({"ep": ep, "n": n})
    try:
        if step == "prepare":
            res = await run(pipe.ig_prepare, ep, n, dict(it))
            ig.update(container=res["container"], made=res["made"], grid=res["grid"], cover_sig=cover_sig(it))
            ig.pop("tries", None)
            if res.get("note"):
                await say(ctx, f"📸 {name} : {esc(res['note'])}")
        else:
            if (await run(pipe.ig_grid, dict(it)) != bool(ig.get("grid"))      # placement changed in ClickUp meanwhile
                    or ig.get("cover_sig", "") != cover_sig(it)):                # or a new cover
                res = await run(pipe.ig_prepare, ep, n, dict(it))
                ig.update(container=res["container"], made=res["made"], grid=res["grid"], cover_sig=cover_sig(it))
                RS(ep).save()
            res = await run(pipe.ig_publish, dict(it))
            ig.update(posted=True, id=res["id"], permalink=res.get("permalink", ""))
            it.setdefault("links", {})["instagram"] = res.get("permalink") or ""
            RS(ep).save()
            collab = " et ".join("@" + h for h in (it.get("captions") or {}).get("collab") or [])
            where = "grille + onglet Reels" if ig.get("grid") else "onglet Reels (pas dans la grille)"
            await say(ctx, f"📸 {name} est en ligne sur Instagram ({where}) · <a href=\"{res.get('permalink', '')}\">voir</a>"
                           + (f" · invitations collab envoyées à {collab}" if collab else "") + ". ClickUp : Posted.")
            try:
                await share_reel(ctx, ep, n, quiet=True, cover=False)         # Instagram link in the task
            except Exception:  # noqa: BLE001
                log.exception("share after instagram")
    except Exception as e:  # noqa: BLE001
        log.exception("instagram %s", step)
        msg = str(e)
        if "EXPIRED" in msg or step == "publish" and "container" in msg.lower():
            ig.pop("container", None)
        ig["tries"] = ig.get("tries", 0) + 1
        if ig["tries"] >= 3:
            ig["failed"] = msg[-200:]
            await say(ctx, f"⚠️ {name} : Instagram refuse ({esc(msg[-200:])}). Publie-le toi-même (légende dans ClickUp).")
    finally:
        RS(ep).save()
        IG_BUSY.clear()


# ---------------------------------------------------------------- guest's Instagram @ (caption @ + collab invite)
async def ask_handle(ctx, ep):
    """Unknown @ for this guest: the bot looks it up on the web and asks Loïc to confirm (once per guest)."""
    from . import share
    guest = ep.get("guest_name") or ""
    if not guest or share.guest_handle(guest) is not None or (reg.data.get("handle_ask") or {}).get("guest") == guest:
        return
    reg.data["handle_ask"] = {"guest": guest, "vid": ep.video_id, "cand": ""}
    reg.save()
    try:
        found = await run(pipe.guest_instagram, ep)
    except Exception:  # noqa: BLE001
        log.exception("guest instagram")
        found = {}
    h = found.get("handle") or ""
    reg.data["handle_ask"]["cand"] = h
    reg.save()
    rows = [[B(f"✅ @{h}", callback_data="igh:ok")]] if h else []
    rows.append([B("Pas d'Instagram", callback_data="igh:none")])
    text = (f"📸 Instagram de <b>{esc(guest)}</b> (le @ dans la légende + l'invitation collab) : je pense que c'est "
            f"<b>@{esc(h)}</b>" + (f" ({esc(found.get('evidence', ''))})" if found.get("evidence") else "")
            + ("" if found.get("sure") else ", pas sûr") + ". Confirme, ou écris le bon @." if h else
            f"📸 Je n'ai pas trouvé l'Instagram de <b>{esc(guest)}</b> (pour le @ dans la légende et l'invitation collab). "
            "Écris son @ ici.")
    await say(ctx, text, reply_markup=K(rows))


async def set_guest_handle(ctx, guest: str, handle: str):
    """Saved for good (data/handles.json); the captions of this guest's reels get the @ (ClickUp text refreshed);
    Instagram posts not yet out use it with the collab invite."""
    from . import share
    handle = handle.lstrip("@").strip()
    share.set_handle(cfg.data_dir, guest, handle)
    if (reg.data.get("handle_ask") or {}).get("guest") == guest:
        reg.data.pop("handle_ask", None)
        reg.save()
    todo = []
    for f in sorted((reg.root / "episodes").glob("*/reels.json")):
        ep = reg.episode(f.parent.name)
        if share.guest_key(ep.get("guest_name") or "") != share.guest_key(guest):
            continue
        for k, it in RS(ep).data.get("items", {}).items():
            if it.get("captions") and not (it.get("ig_post") or {}).get("posted"):
                it["captions"] = share.apply_handle(it["captions"], guest, handle or None)
                if it.get("filed"):
                    todo.append((ep, int(k)))
        RS(ep).save()
    await say(ctx, (f"✅ @{esc(handle)} enregistré pour {esc(guest)} : @ dans les légendes Instagram + invitation collab "
                    f"(avec @mariusiepure) au moment du post." if handle else
                    f"✅ Noté : {esc(guest)} n'a pas d'Instagram, seul @mariusiepure sera invité en collab.")
              + (" Je mets à jour les légendes dans ClickUp." if todo else ""))

    async def refresh():
        for ep, n in todo:
            await share_reel(ctx, ep, n, quiet=True, cover=False)
    if todo:
        bg(ctx, "Légendes ClickUp (@ du guest)", refresh())


async def handle_reply(ctx, text: str) -> bool:
    """Answer to ask_handle typed in the chat: « @kierabrunton », « kierabrunton », « pas d'instagram »."""
    ask = reg.data.get("handle_ask") or {}
    if not ask.get("guest"):
        return False
    low = text.strip().lower()
    if re.fullmatch(r"(pas|aucun|no|none)\b.{0,25}", low) and ("insta" in low or low in ("pas", "aucun", "none", "no")):
        await set_guest_handle(ctx, ask["guest"], "")
        return True
    m = re.fullmatch(r"(?:c['’]est\s+)?@([A-Za-z0-9._]{2,30})", text.strip()) or \
        re.fullmatch(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{2,30})/?(?:\?\S*)?", text.strip())
    if not m:
        return False
    MEMORY.add("user", text)
    await set_guest_handle(ctx, ask["guest"], m.group(1))
    return True


async def covers_ok(ctx, ep, nums: list[int] | None = None):
    """Loïc validates covers: ClickUp « ready », which schedules the Shorts (shorts_watch)."""
    items = RS(ep).data.get("items", {})
    nums = nums or sorted(int(k) for k, it in items.items() if it.get("filed") and not it.get("cover_ok"))
    done, skip = [], []
    for n in nums:
        it = items.get(str(n)) or {}
        if not it.get("filed"):
            skip.append(n)
            continue
        it["cover_ok"] = True
        try:
            await run(pipe.reel_status, dict(it), "ready", ("to generate", "generated", "approved"))
        except Exception as e:  # noqa: BLE001
            log.exception("clickup ready")
            await say(ctx, f"⚠️ Reel {n} : ClickUp <code>{esc(str(e)[-150:])}</code>")
        done.append(n)
    RS(ep).save()
    if not done:
        await say(ctx, "Aucun reel rangé avec une cover à valider" + (f" ({', '.join(map(str, skip))} pas rangé)" if skip else "") + ".")
        return
    try:
        await ask_handle(ctx, ep)
    except Exception:  # noqa: BLE001
        log.exception("ask handle")
    await say(ctx, f"✅ Cover{'s' if len(done) > 1 else ''} {', '.join(map(str, done))} validée{'s' if len(done) > 1 else ''} "
                   "→ ClickUp « ready ». Je programme les Shorts YouTube.")
    await shorts_watch(ctx)


async def shorts_sync(ctx):
    """Every poll: Shorts whose time has passed and that YouTube made public → ClickUp « Posted » + a message."""
    from datetime import datetime, timezone
    from . import shorts
    now = datetime.now(timezone.utc)
    due = [(ep, n, it) for ep, n, it in shorts_items()
           if (it.get("yt_short") or {}).get("id") and (shorts.parse(it["yt_short"].get("at")) or now) <= now]
    if not due:
        return
    st = await run(pipe.yt.statuses, [it["yt_short"]["id"] for _, _, it in due])
    for ep, n, it in due:
        s = st.get(it["yt_short"]["id"])
        if not s or s.get("privacyStatus") != "public":
            continue
        it["yt_short"]["posted"] = True
        RS(ep).save()
        try:
            await run(pipe.short_posted, dict(it))
        except Exception:  # noqa: BLE001
            log.exception("clickup posted")
        await say(ctx, f"▶️ Short en ligne : {short_name({'ep': ep, 'n': n})} · "
                       f"<a href=\"{it['links'].get('short')}\">YouTube</a> (ClickUp : Posted)")


def reels_context() -> str:
    """For the chat model. Called on the event loop only (the store is never read from another thread)."""
    ep = reel_ep()
    if not ep or not RS(ep):
        return "Reels : aucune liste en cours."
    rs = RS(ep).data
    status = {"preview": "envoyé, en attente de son avis", "ok": "validé", "dropped": "jeté", "rendering": "en cours de montage",
              "queued": "en file d'attente", "failed": "échec"}
    lines = [f"Reels de « {pipe.reel_title(ep)} » ({ep.video_id}) : moments proposés "
             + " | ".join(f"{c['n']}. {c.get('title')} ({int(c['end_s'] - c['start_s'])} s)" for c in rs["cands"]),
             "Cochés : " + (", ".join(map(str, sorted(rs.get("sel") or []))) or "aucun")]
    for k, it in sorted(rs.get("items", {}).items(), key=lambda kv: int(kv[0])):
        filed = ""
        if it.get("filed"):
            filed = (f" RANGÉ ({'feed + TikTok + Shorts' if it.get('instagram', True) else 'TikTok + Shorts'}) : Drive "
                     f"{it.get('file_base', '')}.mp4 + cover, tâche ClickUp « {it.get('clickup_name') or it.get('clickup_task')} » "
                     f"(approved, légendes dedans).")
            filed += " Cover validée (ClickUp ready)." if it.get("cover_ok") else " Cover PAS encore validée."
            ig = it.get("ig_post") or {}
            if it.get("instagram", True):
                filed += (" Instagram EN LIGNE." if ig.get("posted") else " Instagram : échec, à publier à la main."
                          if ig.get("failed") else " Instagram : le bot le publiera à l'heure du Short (si connecté)."
                          if (it.get("yt_short") or {}).get("at") else "")
            ys = it.get("yt_short") or {}
            if ys.get("posted"):
                filed += " Short YouTube EN LIGNE."
            elif ys.get("id"):
                from . import shorts
                filed += f" Short YouTube programmé {shorts.label(shorts.parse(ys['at']))} (Londres)."
            else:
                filed += " Short YouTube pas encore programmé (/shorts)."
        lines.append(f"Reel {k} : {status.get(it.get('status'), 'en attente')},{filed} {it.get('duration', '?')} s, décalages "
                     f"début/fin {it.get('shift')}, phrases coupées {it.get('cuts') or 'aucune'}. Dit : {str(it.get('said', ''))[:300]}")
    unfiled = reels_unfiled(ep)
    to_ok = sorted(int(k) for k, it in rs.get("items", {}).items() if it.get("filed") and not it.get("cover_ok"))
    lines.append("Rangement : " + (f"reels validés pas encore rangés : {', '.join(map(str, unfiled))} (question du feed à venir)"
                                   if unfiled else "TOUS les reels validés sont rangés (Drive + ClickUp) : plus de question "
                                   "de feed ni de bouton de feed à attendre. Une cover se change avec reel_cover. "
                                   + (f"Covers à valider : {', '.join(map(str, to_ok))} (« je valide les covers » = covers_ok, "
                                      "→ ClickUp ready → Shorts programmés)." if to_ok else
                                      "Covers toutes validées : les Shorts se programment tout seuls.")))
    return "\n".join(lines)


async def reels_cmd(update: Update, ctx):
    if not allowed(update):
        return
    vid = None
    if ctx.args:
        m = re.search(r"(?:v=|youtu\.be/|shorts/|^)([\w-]{11})", ctx.args[0])
        vid = m.group(1) if m else None
    await update.message.reply_text(bg(ctx, "Moments pour les reels", propose_reels(ctx, vid)))


# ---------------------------------------------------------------- handlers
async def start(update: Update, ctx):
    cid = update.effective_chat.id
    if not cfg.chat_id:
        # first /start: this chat becomes the owner, nobody else can talk to the bot afterwards
        cfg.chat_id = cid
        cfg.chat_file.write_text(str(cid))
        start_polling(ctx.application)
        await update.message.reply_text("C'est noté, ce chat est le tien ✅ Je surveille YouTube toutes les "
                                        f"{cfg.poll_minutes} min.\nParle-moi normalement. Commandes : /status · /scan · /check · /couts · /episode <id> · /badge <lien> <n> · /reels [lien] · /claude <demande> · /nouveau")
        return
    if not allowed(update):
        return
    await update.message.reply_text("BTR bot en ligne ✅\nParle-moi normalement. Commandes : /status · /scan · /check · /couts · /episode <id> · /badge <lien> <n> · /reels [lien] · /claude <demande> · /nouveau")


async def status(update: Update, ctx):
    if not allowed(update):
        return
    vid = reg.active
    if not vid:
        await update.message.reply_text("Aucun épisode en cours.")
        return
    ep = reg.episode(vid)
    await update.message.reply_text(f"Épisode actif : {ep.get('title')} ({vid})\nÉtape : {ep.stage}")


async def check_cmd(update: Update, ctx):
    if not allowed(update):
        return
    await update.message.reply_text("🩺 Je teste tout (YouTube, téléchargement, Claude, modèles)… ~1 min")
    out = await run(run_check)
    await update.message.reply_text(out[-3800:] or "(rien)")


async def scan_cmd(update: Update, ctx):
    if allowed(update):
        await update.message.reply_text("Je regarde YouTube…")
        await poll_youtube(ctx)


async def episode_cmd(update: Update, ctx):
    if not allowed(update) or not ctx.args:
        return
    vid = ctx.args[0].split("v=")[-1].split("/")[-1][:11]
    await guarded(ctx, "Nouvel épisode", start_video(ctx, vid))


async def on_button(update: Update, ctx):
    if not allowed(update):
        return
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("axis:"):
        MEMORY.add("user", f"[bouton : {q.data}]")
    if q.data.startswith("dev:"):
        await on_dev_button(ctx, q.data)
        return
    if q.data.startswith("ask:"):
        await guarded(ctx, "Demande à Claude", on_ask_button(ctx, q.data))
        return
    if q.data.startswith("badge:"):
        await guarded(ctx, "Badge PART", on_badge_button(ctx, q.data))
        return
    if q.data in ("igh:ok", "igh:none"):
        ask = reg.data.get("handle_ask") or {}
        if not ask.get("guest"):
            await say(ctx, "C'est déjà noté.")
            return
        await set_guest_handle(ctx, ask["guest"], ask.get("cand", "") if q.data == "igh:ok" else "")
        return
    if q.data == "ysch":
        await shorts_watch(ctx)
        return
    if q.data.startswith(("rsel:", "rok:", "rsh:", "rno:", "rund:", "rgo", "reels:", "rfeed:", "rfile:", "rcov:")):
        await on_reel_button(ctx, q, q.data)
        return
    if q.data == "part:redo":
        if reg.active:
            await guarded(ctx, "Miniatures", make_thumbs(ctx, reg.episode(reg.active)))
        return
    if q.data == "srt:next":
        await say(ctx, "OK, je le garde pour la prochaine vidéo non répertoriée.")
        return
    if q.data == "srt:active":
        from pathlib import Path
        last = Path(reg.data.get("last_srt", ""))
        if reg.active and last.is_file():
            await use_srt_for(ctx, reg.episode(reg.active), last)
        return
    ep = reg.episode(reg.active) if reg.active else None
    if not ep:
        return
    d = q.data
    if d.startswith("axis:"):
        MEMORY.add("user", f"[bouton : axe {int(d.split(':')[1]) + 1}]")
        await pick_axis(ctx, ep, int(d.split(":")[1]))
    elif d.startswith("more:"):
        await guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, d.split(":")[1], more=True))
    elif d.startswith("pick:"):
        _, who, i = d.split(":")
        ep[f"pick_{who}"] = ep[f"cand_{who}"][int(i)]
        ep.data.pop("validated", None)
        ep.save()
        if who == "guest" and not ep.get("pick_marius"):
            await guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, "marius"))
        else:
            await guarded(ctx, "Miniatures", make_thumbs(ctx, ep))
    elif d.startswith("val:"):
        ep["validated"] = validated(ep) + [d.split(":")[1]]
        ep.save()
        await say(ctx, f"👍 {THUMB_NAMES[d.split(':')[1]].capitalize()} validé, je n'y touche plus. " + valid_status(ep), reply_markup=thumb_kb(ep))
    elif d.startswith("thumb:"):
        ep["validated"] = [x for x in validated(ep) if x != d.split(":")[1]]   # asking to redo it re-opens it
        ep.save()
        await guarded(ctx, "Miniature", make_thumbs(ctx, ep, d.split(":")[1]))
    elif d == "publish":
        async def go():
            try:
                await run(pipe.publish, ep)
                await say(ctx, f"🚀 Publié sur https://youtu.be/{ep.video_id} (titre, description, miniature).")
            except DryRun as e:
                await say(ctx, f"🧪 {esc(e)}\nVoici quand même la description prévue :\n<pre>{esc(ep.get('description', ''))[:3000]}</pre>")
            ep.stage = "published"
            ep.save()
            await propose_chapters(ctx, ep, "sous-titres YouTube" if not ep.file("captions_davinci.srt").exists() else "ton SRT")
        await guarded(ctx, "Publication YouTube", go())
    elif d == "chapters_ok":
        async def go():
            await run(pipe.publish_chapters, ep, ep["chapters"])
            ep.stage = "done"
            ep.save()
            await say(ctx, "✅ Chapitres ajoutés à la description. Si tu m'envoies ton SRT DaVinci plus tard, je refais un chapitrage plus précis.")
            await say(ctx, "Quand tu veux, je te propose les moments de cet épisode pour les reels.",
                      reply_markup=K([[B("🎞️ Proposer les reels", callback_data="reels:propose")]]))
        await guarded(ctx, "Chapitrage", go())
    elif d == "chapters_retime":
        await guarded(ctx, "Chapitrage", retime_chapters(ctx, ep))
    elif d == "chapters_redo":
        await guarded(ctx, "Chapitrage", propose_chapters(ctx, ep, "nouvel essai"))


async def reel_fast_path(ctx, text: str) -> bool:
    """« reel 5 photo 13 », « reel 5 photo 11 zoom 1.25 », « cover 5 zoom x1.25 », « cover 5 d'autres photos » : done
    at once, without the chat model (which sometimes only said it did it)."""
    low = text.lower().strip()
    zoom = r"(?:\s*[:,-]?\s*zoom\s*(?:de\s+)?x?\s*(\d+(?:[.,]\d+)?))"
    m = re.match(r"^(?:la\s+)?(?:cover\s+)?(?:du\s+)?r[ée]el\s*(\d+)\s*[:,-]?\s*(?:cover\s*)?(?:la\s+)?photo\s*(?:n°|numéro)?\s*(\d+)"
                 + zoom + r"?\s*$", low)
    m2 = re.match(r"^(?:cover|r[ée]el)\s*(?:du\s+)?(?:r[ée]el\s*)?(\d+)\s*[:,-]?\s*(?:trouve\s+)?(?:d['’]\s*)?autres?\s+photos?\s*$", low)
    m3 = re.match(r"^(?:la\s+)?(?:cover\s+)?(?:du\s+)?r[ée]el\s*(\d+)" + zoom + r"\s*$", low) or \
        re.match(r"^cover\s*(\d+)" + zoom + r"\s*$", low)
    if not (m or m2 or m3):
        return False
    MEMORY.add("user", text)
    h = tool_handlers(ctx, [])
    try:
        if m or m3:
            z = (m or m3).group(3 if m else 2)
            out = await h["reel_cover"](int((m or m3).group(1)), photo=int(m.group(2)) if m else None,
                                        zoom=float(z.replace(",", ".")) if z else None)
        else:
            out = await h["reels_cover_search"]([int(m2.group(1))])
    except Exception as e:  # noqa: BLE001
        out = f"⚠️ {e}"
    await say(ctx, "👍 " + esc(out))
    return True


async def igtest_cmd(update: Update, ctx):
    """Dry run for the next Instagram reel: upload + processing at Meta (container), never published. The container is
    kept for the real post if it is still fresh then."""
    if not allowed(update):
        return
    from . import shorts
    items = sorted(ig_items(), key=lambda x: x[2]["yt_short"]["at"])
    if not items:
        await say(ctx, "📸 Aucun reel Instagram en attente.")
        return
    if IG_BUSY:
        await say(ctx, "📸 Un envoi Instagram est déjà en cours, réessaie dans quelques minutes.")
        return
    ep, n, it = items[0]
    name = short_name({"ep": ep, "n": n})
    await say(ctx, f"📸 Test sur {name} (prévu {shorts.label(shorts.parse(it['yt_short']['at']))}) : j'envoie la vidéo à "
                   "Instagram sans publier…")
    IG_BUSY["on"] = True
    try:
        res = await run(pipe.ig_prepare, ep, n, dict(it))
        ig = it.setdefault("ig_post", {})
        ig.update(container=res["container"], made=res["made"], grid=res["grid"], cover_sig=cover_sig(it))
        RS(ep).save()
        collab = " et ".join("@" + h for h in (it.get("captions") or {}).get("collab") or [])
        await say(ctx, f"✅ Test OK : vidéo acceptée et traitée par Instagram"
                       + (f", {esc(res['note'])}" if res.get("note") else ", cover et invitations collab acceptées")
                       + f" ({'grille + onglet Reels' if res['grid'] else 'onglet Reels seulement'}"
                       + (f", collab {collab}" if collab else "") + "). Rien n'est publié : il sortira à son heure.")
    except Exception as e:  # noqa: BLE001
        log.exception("igtest")
        await say(ctx, f"⚠️ Test Instagram : <code>{esc(str(e)[-300:])}</code>")
    finally:
        IG_BUSY.clear()


async def shorts_cmd(update: Update, ctx):
    if not allowed(update):
        return
    await guarded(ctx, "Plan des Shorts", shorts_show(ctx))


async def connect_cmd(update: Update, ctx):
    """Drive + ClickUp for the validated reels: status and the two steps, all from the phone."""
    if not allowed(update):
        return
    from . import share
    sec = share.Secrets(cfg.data_dir)
    drive_ok, cu_ok = bool(sec.get("drive_refresh")), bool(sec.get("clickup_token"))
    url = share.drive_auth_url(cfg.youtube_client[0]) if cfg.youtube_client[0] else ""
    msg = [f"<b>Drive</b> {'✅ connecté' if drive_ok else '❌'}"]
    if url:
        msg.append(f"1. Ouvre <a href=\"{esc(url)}\">ce lien Google</a>, choisis ton compte Google (celui de ton Drive), "
                   "accepte (si Google dit « appli non validée » : Paramètres avancés → Accéder). Le bot ne voit que les "
                   "fichiers qu'il crée lui-même (dossier « BTR Reels »).")
        msg.append("2. Tu arrives sur une page qui ne charge pas (127.0.0.1…) : c'est normal. Copie son adresse et "
                   "colle-la ici.")
    msg.append(f"\n<b>ClickUp</b> {'✅ connecté' if cu_ok else '❌'}")
    msg.append("Sur app.clickup.com : ton avatar → Settings → Apps → API Token → Generate, copie le code « pk_… » et "
               "colle-le ici (j'efface ton message tout de suite).")
    from . import instagram
    ig_ok = sec.get("ig_username")
    msg.append(f"\n<b>Instagram</b> {'✅ @' + esc(ig_ok) if ig_ok else '❌'}")
    if not ig_ok:
        msg.append("Sur ordinateur, une seule fois (API officielle de Meta, app « BTR - Short ») :\n"
                   "1. developers.facebook.com → app BTR - Short → Paramètres → Général : copie l'<b>ID de l'app</b> et "
                   "la <b>clé secrète</b>.\n"
                   "2. <a href=\"https://developers.facebook.com/tools/explorer/\">Explorateur de l'API Graph</a> : app "
                   "BTR - Short, « Get User Access Token », permissions <code>" + esc(instagram.SCOPES) + "</code>, "
                   "« Generate Access Token », coche la page Facebook BTR et le compte Instagram BTR. Copie le token (EAA…).\n"
                   "3. Colle ici en un seul message : <code>ID clé_secrète token</code>. J'efface ton message tout de suite.")
    await say(ctx, "\n".join(msg))


async def on_secret(update: Update, ctx, text: str) -> bool:
    """A pasted Google address (?code=…) or ClickUp token: stored on the server, never sent to the chat model."""
    from . import share
    sec = share.Secrets(cfg.data_dir)
    code = share.code_from(text)
    token = re.search(r"\bpk_[A-Za-z0-9_]{20,}\b", text)
    meta = re.search(r"\bEAA[A-Za-z0-9]{40,}\b", text)
    if meta:
        for m in MEMORY._list():
            c = re.sub(r"\bEAA[A-Za-z0-9]{40,}", "EAA[effacé]", m.get("content", ""))
            m["content"] = re.sub(r"\b[0-9a-f]{32}\b", "[effacé]", c)
        reg.save()
        try:
            await ctx.bot.delete_message(cfg.chat_id, update.message.message_id)
        except Exception:  # noqa: BLE001
            pass
        app_id = re.search(r"\b\d{12,20}\b", text)
        secret = re.search(r"\b[0-9a-f]{32}\b", text)
        if not app_id or not secret:
            await say(ctx, "J'ai effacé ton message. Il me faut les trois ensemble : <code>ID_app clé_secrète token</code> "
                           "(/connect pour les étapes).")
            return True
        from . import instagram
        try:
            user = await run(instagram.connect, sec, app_id.group(0), secret.group(0), meta.group(0))
            kind = sec.get("ig_kind")
            await say(ctx, f"✅ Instagram connecté (@{esc(user)}). J'ai effacé ton message. Les reels feed en « ready » "
                           "seront publiés par moi à leur heure, avec la cover et les invitations collab."
                      + (" Accès valable 60 jours : je te préviens une semaine avant pour le renouveler (même manip)."
                         if kind == "user" else " Accès sans expiration." if kind == "system" else ""))
        except Exception as e:  # noqa: BLE001
            await say(ctx, f"⚠️ Connexion Instagram refusée : {esc(str(e)[-250:])}")
        return True
    if not code and not token:
        return False
    for m in MEMORY._list():                       # never keep a code / token in the chat history (old pastes too)
        c = re.sub(r"(code=)[^&\s]+", r"\1[effacé]", m.get("content", ""))
        m["content"] = re.sub(r"\bpk_[A-Za-z0-9_]{20,}", "pk_[effacé]", c)
    reg.save()
    try:
        await ctx.bot.delete_message(cfg.chat_id, update.message.message_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        if code:
            await run(share.drive_connect, sec, cfg.youtube_client[:2], code)
            d = await run(share.Drive, sec, cfg.youtube_client[:2])
            root = await run(d.folder, share.FOLDER)
            sec.set(drive_root=root)
            await say(ctx, f"✅ Drive connecté. Les reels validés iront dans <a href=\"{d.folder_link(root)}\">BTR Reels</a>.")
        else:
            me = await run(lambda: share.ClickUp(token.group(0)).me())
            sec.set(clickup_token=token.group(0))
            await say(ctx, f"✅ ClickUp connecté ({esc(me.get('username') or 'compte')}). J'ai effacé ton message.")
    except Exception as e:  # noqa: BLE001
        await say(ctx, f"⚠️ Connexion refusée : {esc(share.drive_error(e) if code else str(e)[-200:])}")
    if sec.get("drive_refresh") and sec.get("clickup_token"):
        ep = reel_ep()
        if ep and RS(ep):
            await maybe_dispatch(ctx, ep)
    return True


async def on_text(update: Update, ctx):
    """Exact « titre: / citation: / part: / description: » commands stay instant; everything else is a conversation."""
    if not allowed(update):
        return
    text = update.message.text.strip()
    if await on_secret(update, ctx, text):
        return
    if await reel_fast_path(ctx, text):
        return
    if await handle_reply(ctx, text):
        return
    low = text.lower()
    ep = reg.episode(reg.active) if reg.active else None
    if ep and ep.stage == "thumbs_proposed" and re.match(r"(titre|citation|part|description)\s*:", low):
        h = tool_handlers(ctx, [])
        MEMORY.add("user", text)
        arg = text.split(":", 1)[1].strip()
        try:
            if low.startswith("titre"):
                out = await h["set_title"](arg)
            elif low.startswith("citation"):
                parts = [x.strip() for x in arg.split("|")]
                out = await h["set_quote"](*parts) if len(parts) == 3 else "Format : citation: haut | MOT | bas"
            elif low.startswith("part"):
                out = await h["set_part"]("" if arg.lower() in ("aucun", "aucune", "non", "0", "none") else arg)
                out += " — " + await h["redo_thumbnails"](list(THUMB_LABELS))
            else:
                out = await h["edit_description"](arg)
        except Exception as e:  # noqa: BLE001
            out = f"⚠️ {e}"
        await say(ctx, "👍 " + esc(out))
        return
    images = list(SHOTS)
    SHOTS.clear()
    await ask_assistant(ctx, text, images)


async def on_document(update: Update, ctx):
    """An .srt sent in the chat = a DaVinci SRT, for the current episode or the next video."""
    if not allowed(update):
        return
    doc = update.message.document
    if not doc.file_name.lower().endswith(".srt"):
        return
    path = PENDING / doc.file_name
    await (await doc.get_file()).download_to_drive(str(path))
    await handle_new_srt(ctx, path, "📥 SRT reçu")


async def handle_new_srt(ctx, path, intro: str):
    ep = reg.episode(reg.active) if reg.active else None
    reg.data["last_srt"] = str(path)
    reg.save()
    if not ep or ep.stage == "done":
        await say(ctx, f"{intro}. Je le garde pour la <b>prochaine vidéo non répertoriée</b>, et je pourrai démarrer "
                       "sans attendre les sous-titres YouTube.")
    elif ep.stage == "waiting_transcript" or drive.matches(path.name, ep.get("title", "")):
        await say(ctx, intro + ".")
        await use_srt_for(ctx, ep, path)
    else:
        kb = [[B("Cet épisode", callback_data="srt:active"), B("La prochaine vidéo", callback_data="srt:next")]]
        await say(ctx, f"{intro}. C'est pour <b>{esc(ep.get('title'))}</b> ou pour la prochaine vidéo ?", reply_markup=K(kb))


async def use_srt_for(ctx, ep, path):
    path.replace(ep.file("captions_davinci.srt"))
    await say(ctx, f"🔗 SRT associé à <b>{esc(ep.get('title'))}</b>.")
    if ep.stage in ("published", "chapters_proposed", "done"):
        await guarded(ctx, "Chapitrage", propose_chapters(ctx, ep, "ton SRT"))
    elif ep.stage == "waiting_transcript":
        await guarded(ctx, "Proposition des axes", propose_axes(ctx, ep))
    else:
        await say(ctx, "Je m'en servirai pour le chapitrage, après la publication.")


async def on_photo(update: Update, ctx):
    """Fallback: Loïc sends his own still when the scan found nothing."""
    if not allowed(update):
        return
    if not reg.active:
        path = cfg.data_dir / "feedback" / f"{update.message.message_id}.jpg"
        path.parent.mkdir(exist_ok=True)
        await (await update.message.photo[-1].get_file()).download_to_drive(str(path))
        await ask_assistant(ctx, update.message.caption or "(capture d'écran sans texte)", [path])
        return
    ep = reg.episode(reg.active)
    if ep.stage != "frames_proposed":
        # not waiting for a frame: a screenshot he shows me (feedback), never a replacement of the picked frames
        path = ep.file(f"feedback/{update.message.message_id}.jpg")
        path.parent.mkdir(exist_ok=True)
        await (await update.message.photo[-1].get_file()).download_to_drive(str(path))
        if update.message.caption:
            images = list(SHOTS) + [path]
            SHOTS.clear()
            await ask_assistant(ctx, update.message.caption, images)
        else:
            SHOTS.append(path)
            if len(SHOTS) == 1:
                await say(ctx, "📎 Capture reçue. Dis-moi ce qui ne va pas (tu peux en envoyer d'autres).")
        return
    who = "guest" if not ep.get("pick_guest") else "marius"
    ph = update.message.photo[-1]
    path = ep.file(f"{who}_manual.jpg")
    await (await ph.get_file()).download_to_drive(str(path))
    import cv2
    img = cv2.imread(str(path))
    fs = pipe.faces.analyse(img)
    if not fs:
        await say(ctx, "Je ne vois pas de visage sur cette image.")
        return
    f = max(fs, key=lambda x: x.box[3])
    H, W = img.shape[:2]
    x, y, w, h = f.box
    ep[f"pick_{who}"] = {"t": -1, "hires": str(path), "cx": (x + w / 2) / W, "top": y / H, "fh": h / H}
    ep.save()
    if who == "guest":
        await guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, "marius"))
    else:
        await guarded(ctx, "Miniatures", make_thumbs(ctx, ep))


def start_polling(app):
    if not app.job_queue.get_jobs_by_name("poll"):
        app.job_queue.run_repeating(poll_youtube, interval=cfg.poll_minutes * 60, first=15, name="poll")
    if not app.job_queue.get_jobs_by_name("ig"):
        app.job_queue.run_repeating(ig_tick, interval=60, first=30, name="ig")


async def on_boot(app):
    if cfg.chat_id:
        start_polling(app)
        try:
            await app.bot.send_message(cfg.chat_id, "🔄 BTR bot (re)démarré, je surveille YouTube.")
            ep = reel_ep()
            if ep and RS(ep):
                rs = RS(ep).data
                for k, it in rs["items"].items():               # a redo of a validated reel is never resumed:
                    if it.get("status") in ("queued", "rendering") and it.get("keep_ok"):   # it stays as validated
                        it["status"] = "ok"
                        for x in ("keep_ok", "need", "redo"):
                            it.pop(x, None)
                if not reg.data.get("restored_1030"):           # 30.10.2026: redo of validated reels by mistake
                    reg.data["restored_1030"] = True
                    reg.save()
                    bg(app, "Retour des reels validés", restore_validated(app, ep, "2026-10-30T14:05:00Z"))
                stuck = sorted((int(k) for k, it in rs["items"].items() if it.get("status") in ("queued", "rendering")))
                for k in stuck:                                 # a restart (deploy) stopped them: start again
                    it = rs["items"][str(k)]
                    it["status"], it["need"] = "queued", ("full" if it.get("need") == "full" or it.get("redo") else
                                                          it.get("need") or "full")
                    it.pop("redo", None)
                if stuck:
                    RS(ep).save()
                    await say(app, f"🔄 Le redémarrage a interrompu les reels {', '.join(map(str, stuck))} : je les reprends.")
                    bg(app, f"Reel {stuck[0]}", reel_chain(app, ep, rs.get("id"), stuck))
                if not reg.data.get("covers_zoom2_shorts_1030"):  # same new framing for the TikTok + Shorts covers
                    reg.data["covers_zoom2_shorts_1030"] = True
                    reg.save()
                    redo = [int(k) for k, it in sorted(rs["items"].items(), key=lambda kv: int(kv[0]))
                            if it.get("filed") and not it.get("instagram", True) and it.get("cover")]
                    if redo:
                        await say(app, f"🖼 Covers TikTok + Shorts {', '.join(map(str, redo))} : je les refais aussi avec le "
                                       "nouveau cadrage (2x plus serré, texte juste sous le visage), même photo. "
                                       "Valide-les ensuite (✅ Cover OK).")
                        for k in redo:
                            it = rs["items"][str(k)]
                            bg(app, f"Cover du reel {k}", redo_cover(app, ep, k, None, it.get("cover_pick"),
                                                                       it.get("cover_zoom")), limit=8 * 60)
                if not reg.data.get("covers_zoom2_1030"):        # 30.10.2026: 2x closer, hook right under the chin
                    reg.data["covers_zoom2_1030"] = True
                    reg.save()
                    redo = [int(k) for k, it in sorted(rs["items"].items(), key=lambda kv: int(kv[0]))
                            if it.get("filed") and it.get("instagram", True) and it.get("cover")
                            and not (it.get("ig_post") or {}).get("posted")]
                    if redo:
                        await say(app, f"🖼 Covers feed {', '.join(map(str, redo))} : je les refais 2x plus serrées sur la tête, "
                                       "le texte juste sous le visage, tête entière avec un peu d'air dans la grille "
                                       "Instagram, même photo. Valide-les ensuite (✅ Cover OK).")
                        for k in redo:
                            it = rs["items"][str(k)]
                            bg(app, f"Cover du reel {k}", redo_cover(app, ep, k, None, it.get("cover_pick"),
                                                                       it.get("cover_zoom")), limit=8 * 60)
                if not reg.data.get("covers_ok_1030"):          # 30.10.2026: « Je valide toutes les covers »
                    reg.data["covers_ok_1030"] = True
                    reg.save()
                    if any(it.get("filed") and not it.get("cover_ok") for it in rs["items"].values()):
                        await covers_ok(app, ep)
                if not stuck:
                    await maybe_dispatch(app, ep)                     # all decided before the restart: next step
                if reg.data.get("reels_files") != REELS_FILES:            # one folder per guest, calendar file names
                    reg.data["reels_files"] = REELS_FILES
                    reg.save()
                    done = sorted(int(k) for k, it in rs["items"].items() if it.get("status") == "ok" and it.get("links"))
                    if done:
                        await say(app, f"📁 Je mets à jour les reels rangés ({', '.join(map(str, done))}) : légendes au "
                                       "format validé (comme le premier reel d'Oti), Drive et ClickUp.")
                        for k in done:
                            bg(app, f"Reel {k} → Drive + ClickUp", share_reel(app, ep, k))
                if reg.data.get("reels_rules") != REELS_RULES[0] and rs.get("sel"):
                    reg.data["reels_rules"] = REELS_RULES[0]
                    reg.save()
                    sel = [n for n in sorted(rs["sel"]) if n not in stuck
                           and (rs["items"].get(str(n)) or {}).get("status") != "dropped"]
                    if sel:
                        await say(app, f"✨ Reels : {REELS_RULES[1]}", reply_markup=K([[B(
                            f"🎬 Renvoyer les reels {', '.join(map(str, sel))}", callback_data=f"rall:{rs.get('id')}")]]))
            err = cfg.data_dir / "last_deploy_error.txt"
            if err.exists():
                reg.data["deploy_error"] = err.read_text()[-3000:]
                reg.save()
                err.unlink()
                await app.bot.send_message(
                    cfg.chat_id, "⚠️ La dernière mise à jour plantait au démarrage : je suis revenu tout seul à la version "
                    "d'avant. Je corrige ?", reply_markup=K([[B("🔧 Corrige", callback_data="dev:fix")]]))
        except Exception:  # noqa: BLE001
            log.exception("boot message")


def main():
    import socket
    socket.setdefaulttimeout(120)        # Google APIs (httplib2) have no timeout of their own: never hang a job forever
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # concurrent updates: he can keep talking while a render or a frame search runs (heavy jobs share LOCK)
    app = Application.builder().token(cfg.telegram_token).post_init(on_boot).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("episode", episode_cmd))
    app.add_handler(CommandHandler("claude", claude_cmd))
    app.add_handler(CommandHandler("badge", badge_cmd))
    app.add_handler(CommandHandler("opus", claude_strong_cmd))
    app.add_handler(CommandHandler("nouveau", new_conv_cmd))
    app.add_handler(CommandHandler("couts", couts_cmd))
    app.add_handler(CommandHandler("reels", reels_cmd))
    app.add_handler(CommandHandler("connect", connect_cmd))
    app.add_handler(CommandHandler("shorts", shorts_cmd))
    app.add_handler(CommandHandler("igtest", igtest_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageReactionHandler(on_reaction))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
