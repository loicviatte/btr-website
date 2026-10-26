"""Telegram side: notifications, buttons and the conversation with Loïc."""
import asyncio
import html
import logging
import traceback

from telegram import InlineKeyboardButton as B
from telegram import InlineKeyboardMarkup as K
from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler,
                          filters)

from .config import Settings
from .pipeline import Pipeline, clean_quote
from .state import Registry

log = logging.getLogger("btrbot")
cfg = Settings()
reg = Registry(cfg.data_dir)
pipe = Pipeline(cfg)
LOCK = asyncio.Lock()


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
        except Exception as e:  # noqa: BLE001
            log.exception(label)
            await say(ctx, f"⚠️ {esc(label)} a échoué : <code>{esc(e)}</code>\n<pre>{esc(traceback.format_exc()[-800:])}</pre>")


# ---------------------------------------------------------------- jobs
async def poll_youtube(ctx: ContextTypes.DEFAULT_TYPE):
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


async def make_thumbs(ctx, ep):
    await say(ctx, "🎨 Je fabrique les deux miniatures (détourage, extension, voile or)… ~3 min")
    yt, ig = await run(pipe.thumbnails, ep)
    if not ep.get("description"):
        ep["description"] = await run(pipe.description, ep)
    ep.stage = "thumbs_proposed"
    ep.save()
    with open(yt, "rb") as f:
        await ctx.bot.send_photo(cfg.chat_id, f, caption="Miniature YouTube")
    with open(ig, "rb") as f:
        await ctx.bot.send_document(cfg.chat_id, f, filename=f"{ep.video_id}_instagram.jpg", caption="Miniature Instagram (fichier HD)")
    desc = ep["description"].replace("{{CHAPTERS}}", "[chapitres ajoutés quand le SRT est prêt]").replace("{CHAPTERS}", "[chapitres]")
    await say(ctx, f"<b>Titre :</b> {esc(ep['final']['title'])}\n\n<b>Description :</b>\n{esc(desc)[:3300]}")
    kb = [[B("✅ Publier sur YouTube", callback_data="publish")],
          [B("🔁 Autre image guest", callback_data="more:guest"), B("🔁 Autre image Marius", callback_data="more:marius")]]
    await say(ctx, "Je publie titre + description + miniature ?\nPour changer : <code>titre: …</code>, "
                   "<code>citation: haut | MOT | bas</code> ou <code>description: …</code> (tes consignes).", reply_markup=K(kb))


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
                                        f"{cfg.poll_minutes} min.\n/status · /scan · /check · /episode <id>")
        return
    if not allowed(update):
        return
    await update.message.reply_text("BTR bot en ligne ✅\n/status · /scan · /check · /episode <id>")


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
    elif d == "publish":
        async def go():
            await run(pipe.publish, ep)
            ep.stage = "published"
            ep.save()
            await say(ctx, f"🚀 Publié sur https://youtu.be/{ep.video_id} (titre, description, miniature).")
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
    if not allowed(update) or not reg.active:
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
    if ep.stage in ("axes_proposed", "frames_proposed", "thumbs_proposed"):
        async def go():
            res = await run(pipe.refine, ep, text)
            ep.save()
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
    """An .srt sent in the chat = the DaVinci SRT for the active episode."""
    if not allowed(update) or not reg.active:
        return
    doc = update.message.document
    if not doc.file_name.lower().endswith(".srt"):
        return
    ep = reg.episode(reg.active)
    f = await doc.get_file()
    await f.download_to_drive(str(ep.file("captions_davinci.srt")))
    await say(ctx, "📥 SRT reçu, je m'en sers pour le chapitrage.")
    if ep.stage in ("published", "chapters_proposed", "done"):
        await guarded(ctx, "Chapitrage", propose_chapters(ctx, ep, "ton SRT"))
    elif ep.stage == "waiting_transcript":
        await guarded(ctx, "Proposition des axes", propose_axes(ctx, ep))


async def on_photo(update: Update, ctx):
    """Fallback: Loïc sends his own still when the scan found nothing."""
    if not allowed(update) or not reg.active:
        return
    ep = reg.episode(reg.active)
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
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
