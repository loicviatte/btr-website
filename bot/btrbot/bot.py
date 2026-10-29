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


async def guarded(ctx, label: str, coro):
    """Run one heavy step at a time and report errors on Telegram instead of dying silently."""
    import time
    async with LOCK:
        RUNNING.update(label=label, since=time.time())
        ok = False
        try:
            r = await coro
            ok = True
            return r
        except DryRun as e:
            await say(ctx, f"🧪 {esc(e)}")
        except Exception as e:  # noqa: BLE001
            log.exception(label)
            await say(ctx, f"⚠️ {esc(label)} a échoué : <code>{esc(e)}</code>\n<pre>{esc(traceback.format_exc()[-800:])}</pre>")
        finally:
            RUNNING.clear()
            LAST.update(label=label, at=time.time(), ok=ok)


def bg(ctx, label: str, coro) -> str:
    """Start a heavy job in the background (one at a time) and say so: the chat stays responsive meanwhile."""
    import time
    queued = f" (en file d'attente derrière « {RUNNING['label']} », lancé il y a {int(time.time() - RUNNING['since'])} s)" if RUNNING else ""
    asyncio.create_task(guarded(ctx, label, coro))
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
            raise RuntimeError(f"impossible à l'étape actuelle ({ep.stage})")
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
        res = await run(pipe.reel_feedback, dict(item), str(feedback))
        fixes = [f for f in res.get("fixes") or [] if f.get("from") and f.get("to")]
        it = reel_item(ep, n)
        if fixes:
            it.setdefault("fixes", []).extend(fixes)
            it.pop("captions", None)                   # a corrected word must not stay wrong in the captions
        if res.get("relayout") and res.get("layout_note"):
            it["sub_note"] = str(res["layout_note"])[:400]
        if not fixes and not res.get("relayout"):
            RS(ep).save()
            return "rien à changer compris. Réponse à transmettre à Loïc : " + str(res.get("reply", ""))
        out = queue_reel(ctx, ep, n, "subs")
        return f"{out}. À dire à Loïc : {res.get('reply', '')}"

    async def reel_validate(n):
        ep = reels_or_fail()
        if not RS(ep).data["items"].get(str(int(n)), {}).get("file"):
            return f"le reel {n} n'est pas encore monté"
        return bg(ctx, f"Reel {n} validé", validate_reel(ctx, ep, int(n)))

    async def reel_drop(n):
        ep = reels_or_fail()
        return bg(ctx, f"Reel {n} jeté", drop_reel(ctx, ep, int(n)))

    return {"reels_propose": reels_propose, "reels_select": reels_select, "reel_adjust": reel_adjust,
            "reel_subtitles": reel_subtitles,
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
        if reply.strip():
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
    if item.get("doubts"):
        notes.append("🔎 Mots où ton SRT et l'audio ne disent pas pareil (mon choix après →) :\n"
                     + "\n".join(item["doubts"][:4]) + (f"\n(+{len(item['doubts']) - 4} autres)" if len(item["doubts"]) > 4 else ""))
    return (f"🎞️ Reel {n} · {item.get('duration')} s · {str(c.get('title'))[:80]}\n“{str(c.get('hook', ''))[:200]}”\n"
            f"Plans : {shots}" + ("\n" + "\n".join(notes) if notes else "")
            + "\nDis-moi en texte s'il faut changer quelque chose (« commence 2 s plus tôt », « coupe la dernière phrase »).")


async def send_reel(ctx, ep, n: int):
    d = RS(ep).data
    item = reel_item(ep, n)
    kb = K([[B("✅ Valider", callback_data=f"rok:{d.get('id')}:{n}"), B("🗑 Jeter", callback_data=f"rno:{d.get('id')}:{n}")]])
    with open(item["file"], "rb") as f:
        await ctx.bot.send_video(cfg.chat_id, f, caption=reel_caption(ep, n)[:1000], supports_streaming=True,
                                 width=1080, height=1920, duration=int(item["duration"]), reply_markup=kb,
                                 read_timeout=300, write_timeout=300)
    MEMORY.add("assistant", f"[vidéo envoyée : reel {n} ({item['duration']} s), {(reel_cand(ep, n) or {}).get('title')}]")


async def make_reel(ctx, ep, list_id: int, n: int) -> bool:
    """Render reel n of list `list_id` (skipped if that list was replaced or the reel dropped meanwhile)."""
    d = RS(ep).data
    item = reel_item(ep, n)
    cand = reel_cand(ep, n)
    if d.get("id") != list_id or not cand or item.get("status") != "queued":
        return False                                   # replaced list, dropped, or already taken by another chain
    item["status"] = "rendering"
    need = item.pop("need", None) or ("subs" if item.get("file") else "full")
    if need == "subs":
        res = await run(pipe.reel_subtitles, ep, dict(cand), list(item.get("fixes") or []), item.get("sub_note", ""))
    else:
        res = await run(pipe.render_reel, ep, dict(cand), list(item["shift"]), list(item["cuts"]),
                        list(item.get("fixes") or []), item.get("sub_note", ""))
    if RS(ep).data.get("id") != list_id:                  # a new list arrived during the render
        return False
    if item.get("status") == "dropped":
        return False
    item.update(res)
    item["status"] = "preview"
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
        await say(ctx, f"✅ {done} reel(s) prêt(s) sur {total}. Valide ceux qui te plaisent : je t'envoie alors le fichier "
                       "final et les légendes Instagram et TikTok.")


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


async def validate_reel(ctx, ep, n: int):
    from pathlib import Path

    from . import reels as R
    item = reel_item(ep, n)
    if not item.get("file") or not Path(item["file"]).exists():
        await say(ctx, f"Le reel {n} n'est plus disponible (liste remplacée ou fichier supprimé).")
        return
    item["status"] = "ok"
    RS(ep).save()
    with open(item["file"], "rb") as f:
        await ctx.bot.send_document(cfg.chat_id, f, filename=Path(item["file"]).name, caption=f"Reel {n} validé : le fichier final.",
                                    read_timeout=300, write_timeout=300)
    caps = item.get("captions") or {}
    await plain(ctx, f"📸 Légende Instagram (reel {n}) :\n\n{caps.get('instagram') or '(pas de légende)'}")
    await plain(ctx, f"🎵 Légende TikTok / Shorts (reel {n}) :\n\n{caps.get('tiktok') or '(pas de légende)'}")
    R.slim(Path(item["file"]).parent, keep_final=True)


async def drop_reel(ctx, ep, n: int):
    """Runs under the global lock: never while this reel's files are being written."""
    from pathlib import Path

    from . import reels as R
    item = reel_item(ep, n)
    item["status"] = "dropped"
    RS(ep).save()
    if item.get("file"):
        R.slim(Path(item["file"]).parent, keep_final=False)
    await say(ctx, f"🗑 Reel {n} jeté.")


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
    elif parts[0] == "rok" and n:
        await say(ctx, esc(bg(ctx, f"Reel {n} validé", validate_reel(ctx, ep, n))))
    elif parts[0] == "rno" and n:
        await say(ctx, esc(bg(ctx, f"Reel {n} jeté", drop_reel(ctx, ep, n))))


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
        lines.append(f"Reel {k} : {status.get(it.get('status'), 'en attente')}, {it.get('duration', '?')} s, décalages début/fin "
                     f"{it.get('shift')}, phrases coupées {it.get('cuts') or 'aucune'}. Dit : {str(it.get('said', ''))[:300]}")
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
    if q.data.startswith(("rsel:", "rok:", "rno:", "rgo", "reels:")):
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


async def on_text(update: Update, ctx):
    """Exact « titre: / citation: / part: / description: » commands stay instant; everything else is a conversation."""
    if not allowed(update):
        return
    text = update.message.text.strip()
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


async def on_boot(app):
    if cfg.chat_id:
        start_polling(app)
        try:
            await app.bot.send_message(cfg.chat_id, "🔄 BTR bot (re)démarré, je surveille YouTube.")
            ep = reel_ep()
            if ep and RS(ep):
                stuck = [k for k, it in RS(ep).data["items"].items() if it.get("status") in ("queued", "rendering")]
                for k in stuck:
                    RS(ep).data["items"][k]["status"] = "failed"
                if stuck:
                    RS(ep).save()
                    await app.bot.send_message(cfg.chat_id, f"⚠️ Redémarrage pendant le montage des reels {', '.join(sorted(stuck, key=int))} : "
                                               "ils n'ont pas été finis. Redemande-les (« remonte les reels "
                                               f"{', '.join(sorted(stuck, key=int))} »).")
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
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageReactionHandler(on_reaction))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
