"""Telegram side: notifications, buttons and the conversation with Loïc."""
import asyncio
import html
import logging
import re
import traceback

from telegram import InlineKeyboardButton as B
from telegram import InlineKeyboardMarkup as K
from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler,
                          filters)

from . import drive
from .agent import Agent
from .config import Settings
from .pipeline import DryRun, Pipeline, clean_quote
from .state import Registry

log = logging.getLogger("btrbot")
cfg = Settings()
reg = Registry(cfg.data_dir)
pipe = Pipeline(cfg)
LOCK = asyncio.Lock()
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
    return await ctx.bot.send_message(cfg.chat_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, **kw)


async def run(fn, *a):
    return await asyncio.to_thread(fn, *a)


async def guarded(ctx, label: str, coro):
    """Run one heavy step at a time and report errors on Telegram instead of dying silently."""
    async with LOCK:
        try:
            return await coro
        except DryRun as e:
            await say(ctx, f"🧪 {esc(e)}")
        except Exception as e:  # noqa: BLE001
            log.exception(label)
            await say(ctx, f"⚠️ {esc(label)} a échoué : <code>{esc(e)}</code>\n<pre>{esc(traceback.format_exc()[-800:])}</pre>")


# ---------------------------------------------------------------- dev mode (Claude Code)
async def plain(ctx, text: str, **kw):
    """Long plain-text answers, split for Telegram's 4096-char limit."""
    text = text or "(vide)"
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
    for n, c in enumerate(chunks):
        await ctx.bot.send_message(cfg.chat_id, c, disable_web_page_preview=True, **(kw if n == len(chunks) - 1 else {}))


async def talk_to_agent(ctx, text: str, strong: bool = False, thumb_ep=None):
    if not text:
        return
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
            for d in [x.strip() for x in (m.group(1) if m else "").split(",") if x.strip() in THUMB_LABELS]:
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
    kb = [[B(str(i), callback_data=f"pick:{who}:{i-1}") for i in range(1, len(picks) + 1)],
          [B("🔁 Autres", callback_data=f"more:{who}")]]
    await say(ctx, f"Quelle image de <b>{esc(label)}</b> ?", reply_markup=K(kb))


THUMB_LABELS = {"youtube": "YouTube", "instagram": "Instagram vertical", "square": "carrée"}


async def send_thumb(ctx, ep, design: str):
    path = ep.file(f"render/thumb_{design}.jpg")
    with open(path, "rb") as f:
        if design == "youtube":
            await ctx.bot.send_photo(cfg.chat_id, f, caption="Miniature YouTube")
        elif design == "instagram":
            await ctx.bot.send_document(cfg.chat_id, f, filename=f"{ep.video_id}_instagram.jpg", caption="Miniature Instagram verticale (fichier HD)")
        else:
            await ctx.bot.send_document(cfg.chat_id, f, filename=f"{ep.video_id}_carre.jpg", caption="Miniature carrée 1080×1080 (fichier HD)")


async def make_thumbs(ctx, ep, only: str | None = None):
    if only:
        await say(ctx, f"🎨 Je refais uniquement la miniature {THUMB_LABELS[only]} (les autres ne changent pas)…")
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
        kb = [[B("✅ Publier sur YouTube", callback_data="publish")],
              [B("🔁 Refaire YouTube", callback_data="thumb:youtube"), B("🔁 Instagram", callback_data="thumb:instagram"),
               B("🔁 Carré", callback_data="thumb:square")]]
        await say(ctx, "Prêt à publier ?", reply_markup=K(kb))
        return
    desc = ep["description"].replace("{{CHAPTERS}}", "[chapitres ajoutés quand le SRT est prêt]").replace("{CHAPTERS}", "[chapitres]")
    await say(ctx, f"<b>Titre :</b> {esc(ep['final']['title'])}\n\n<b>Description :</b>\n{esc(desc)[:3300]}")
    kb = [[B("✅ Publier sur YouTube", callback_data="publish")],
          [B("🔁 Autre image guest", callback_data="more:guest"), B("🔁 Autre image Marius", callback_data="more:marius")],
          [B("🔁 Refaire YouTube", callback_data="thumb:youtube"), B("🔁 Instagram", callback_data="thumb:instagram"),
           B("🔁 Carré", callback_data="thumb:square")]]
    await say(ctx, "Je publie titre + description + miniature ?\nPour changer : <code>titre: …</code>, "
                   "<code>citation: haut | MOT | bas</code> ou <code>description: …</code> (tes consignes).", reply_markup=K(kb))


FB = {"images": [], "text": [], "task": None}
DESIGN_WORDS = re.compile(r"miniature|thumbnail|youtube|insta|carr[ée]|square|design|template|police|texte|taille|logo|halo|"
                          r"voile|d[ée]tour|d[ée]coup|cadr|zoom|flou|couleur|ombre|marge|align|bord|coup[ée]|trop (haut|bas|grand|petit)",
                          re.I)


def queue_feedback(ctx, ep, text: str | None = None, image=None):
    """Feedback on the thumbnails = text and/or screenshots showing the problem. Grouped for a few seconds, then
    handed to dev mode with the CURRENT picked frames (the screenshots are not new frames)."""
    if text:
        FB["text"].append(text)
    if image:
        FB["images"].append(str(image))
    if FB["task"]:
        FB["task"].cancel()
    if not FB["text"]:
        return   # screenshots only: wait for his explanation

    async def later():
        await asyncio.sleep(4)
        txt, imgs = "\n".join(FB["text"]), list(FB["images"])
        FB.update(text=[], images=[], task=None)
        await guarded(ctx, "Retour miniatures", thumb_feedback(ctx, ep, txt, imgs))
    FB["task"] = asyncio.create_task(later())


async def thumb_feedback(ctx, ep, text: str, images: list[str]):
    g, m = ep["pick_guest"], ep["pick_marius"]
    imgs = "\n".join(f"- {p}" for p in images) or "(aucune)"
    msg = f"""Retour de Loïc sur les miniatures de l'épisode {ep.video_id} ({ep.get('guest_name', '')}) :
« {text} »

Captures jointes par Loïc (à regarder avec Read) : elles MONTRENT OÙ EST LE PROBLÈME (annotations, comparaisons). Ce ne sont PAS de nouvelles images à mettre dans les miniatures : garde les images déjà choisies par le bot.
{imgs}

Miniatures actuelles : {ep.dir}/render/thumb_youtube.jpg, thumb_instagram.jpg, thumb_square.jpg (regarde-les avec Read).
Images choisies (inchangées) : guest {g.get('hires')}, Marius {m.get('hires')}.

À faire :
1. Comprends de QUELLE miniature il parle (youtube = 1920x1080, instagram = vertical 1080x1920, square = 1080x1080) ; s'il ne précise pas, déduis-le des captures, sinon de ce qui est visiblement faux.
2. Corrige uniquement ce qui concerne cette/ces miniature(s) (btrbot/templates/*.html ou btrbot/render.py). Les autres designs doivent rester identiques ; si une règle de marque est en jeu (voir CLAUDE.md), respecte-la.
3. Re-rends SEULEMENT les designs concernés avec le code modifié : `/opt/btr-bot/.venv/bin/python -m btrbot.rerender {ep.video_id} <youtube|instagram|square>` (depuis le dossier courant), regarde le résultat avec Read et itère jusqu'à ce que ce soit bon.
4. Dernière ligne de ta réponse, exactement : DESIGNS: <liste séparée par des virgules des designs re-rendus>"""
    await say(ctx, "🧠 Je regarde ton retour et je reprends seulement la/les miniature(s) concernée(s), avec les mêmes images…")
    await talk_to_agent(ctx, msg, thumb_ep=ep)


async def propose_chapters(ctx, ep, source: str):
    ch = await run(pipe.chapters, ep)
    ep["chapters"] = ch
    ep.stage = "chapters_proposed"
    ep.save()
    body = "\n".join(f"{esc(t)} {esc(title)}" for t, title in ch)
    kb = [[B("✅ Ajouter à la description", callback_data="chapters_ok"), B("🔁 Refaire", callback_data="chapters_redo")]]
    await say(ctx, f"📑 <b>Chapitrage</b> (depuis {esc(source)})\n<pre>{body}</pre>", reply_markup=K(kb))


# ---------------------------------------------------------------- handlers
async def start(update: Update, ctx):
    cid = update.effective_chat.id
    if not cfg.chat_id:
        # first /start: this chat becomes the owner, nobody else can talk to the bot afterwards
        cfg.chat_id = cid
        cfg.chat_file.write_text(str(cid))
        start_polling(ctx.application)
        await update.message.reply_text("C'est noté, ce chat est le tien ✅ Je surveille YouTube toutes les "
                                        f"{cfg.poll_minutes} min.\n/status · /scan · /check · /episode <id> · /claude <demande> · /opus <demande> · /nouveau")
        return
    if not allowed(update):
        return
    await update.message.reply_text("BTR bot en ligne ✅\n/status · /scan · /check · /episode <id> · /claude <demande> · /opus <demande> · /nouveau")


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

    def run_check():
        import contextlib
        import io

        from . import check
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            check.main()
        return buf.getvalue()
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
    v = await run(pipe.yt.video, vid)
    reg.mark_seen(vid)
    ep = reg.episode(vid)
    ep["title"] = v["snippet"]["title"]
    ep.stage = "waiting_transcript"
    ep.save()
    reg.active = vid
    await say(ctx, f"OK, je prends <b>{esc(ep['title'])}</b>.")
    await poll_transcripts(ctx)


async def on_button(update: Update, ctx):
    if not allowed(update):
        return
    q = update.callback_query
    await q.answer()
    if q.data.startswith("dev:"):
        await on_dev_button(ctx, q.data)
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
        a = ep["axes"][int(d.split(":")[1])]
        ep["final"] = {**a, "guest_name": ep.get("guest_name")}
        for k in ("pick_guest", "pick_marius", "shown_guest", "shown_marius"):
            ep.data.pop(k, None)
        ep.stage = "frames_proposed"
        ep.save()
        await say(ctx, f"👍 Axe retenu : “{esc(a['top'])} <b>{esc(a['key'])}</b> {esc(a['bottom'])}”")
        await guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, "guest"))
    elif d.startswith("more:"):
        await guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, d.split(":")[1], more=True))
    elif d.startswith("pick:"):
        _, who, i = d.split(":")
        ep[f"pick_{who}"] = ep[f"cand_{who}"][int(i)]
        ep.save()
        if who == "guest" and not ep.get("pick_marius"):
            await guarded(ctx, "Recherche d'images", propose_frames(ctx, ep, "marius"))
        else:
            await guarded(ctx, "Miniatures", make_thumbs(ctx, ep))
    elif d.startswith("thumb:"):
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
        await guarded(ctx, "Chapitrage", go())
    elif d == "chapters_redo":
        await guarded(ctx, "Chapitrage", propose_chapters(ctx, ep, "nouvel essai"))


async def on_text(update: Update, ctx):
    if not allowed(update):
        return
    if not reg.active or reg.episode(reg.active).stage not in ("axes_proposed", "frames_proposed", "thumbs_proposed"):
        await talk_to_agent(ctx, update.message.text.strip())
        return
    ep = reg.episode(reg.active)
    text = update.message.text.strip()
    low = text.lower()
    if ep.stage == "thumbs_proposed" and low.startswith("titre:"):
        ep["final"]["title"] = text.split(":", 1)[1].strip()
        ep.save()
        await say(ctx, f"Titre mis à jour : <b>{esc(ep['final']['title'])}</b>", reply_markup=K([[B("✅ Publier sur YouTube", callback_data="publish")]]))
        return
    if ep.stage == "thumbs_proposed" and low.startswith("citation:"):
        parts = [p.strip() for p in text.split(":", 1)[1].split("|")]
        if len(parts) == 3:
            ep["final"].update({"top": parts[0], "key": parts[1], "bottom": parts[2]})
            ep.save()
            await guarded(ctx, "Miniatures", make_thumbs(ctx, ep))
        else:
            await say(ctx, "Format : <code>citation: haut | MOT | bas</code>")
        return
    if ep.stage == "thumbs_proposed" and low.startswith("description:"):
        async def go():
            prompt = ("Rewrite this YouTube description following this instruction: " + text.split(":", 1)[1].strip() + "\n"
                      "Keep the same structure and keep the {CHAPTERS} line as is. Return only the description.\n\n" + ep["description"])
            ep["description"] = await run(pipe.llm._ask, prompt)
            ep.save()
            await say(ctx, f"<b>Nouvelle description :</b>\n{esc(ep['description'])[:3500]}", reply_markup=K([[B("✅ Publier sur YouTube", callback_data="publish")]]))
        await guarded(ctx, "Description", go())
        return
    if ep.stage == "thumbs_proposed" and (FB["images"] or DESIGN_WORDS.search(low)):
        queue_feedback(ctx, ep, text=text)
        return
    if ep.stage in ("axes_proposed", "frames_proposed", "thumbs_proposed"):
        async def go():
            res = await run(pipe.refine, ep, text)
            ep.save()
            if res.get("route") == "agent":
                asyncio.create_task(talk_to_agent(ctx, text))
                return
            if res.get("final"):
                ep.stage = "frames_proposed"
                for k in ("pick_guest", "pick_marius"):
                    ep.data.pop(k, None)
                ep.save()
                f = clean_quote(res["final"])
                await say(ctx, f"{esc(res.get('reply'))}\n\n👍 Retenu : “{esc(f['top'])} <b>{esc(f['key'])}</b> {esc(f['bottom'])}”")
                await propose_frames(ctx, ep, "guest")
            elif res.get("axes"):
                ep.stage = "axes_proposed"
                ep.save()
                await send_axes(ctx, ep, intro=esc(res.get("reply")))
            else:
                await say(ctx, esc(res.get("reply")))
        await guarded(ctx, "Discussion", go())


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
    if not allowed(update) or not reg.active:
        return
    ep = reg.episode(reg.active)
    if ep.stage == "thumbs_proposed" and ep.get("pick_guest") and ep.get("pick_marius"):
        # a screenshot with feedback: it shows the problem, it does not replace the picked frames
        path = ep.file(f"feedback/{update.message.message_id}.jpg")
        path.parent.mkdir(exist_ok=True)
        await (await update.message.photo[-1].get_file()).download_to_drive(str(path))
        if not FB["text"] and not update.message.caption:
            await say(ctx, "📎 Capture reçue. Dis-moi ce qui ne va pas dessus (tu peux en envoyer d'autres) et je reprends la miniature concernée.")
        queue_feedback(ctx, ep, text=update.message.caption, image=path)
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
    app = Application.builder().token(cfg.telegram_token).post_init(on_boot).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("episode", episode_cmd))
    app.add_handler(CommandHandler("claude", claude_cmd))
    app.add_handler(CommandHandler("opus", claude_strong_cmd))
    app.add_handler(CommandHandler("nouveau", new_conv_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
