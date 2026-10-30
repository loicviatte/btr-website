"""The bot's conversational brain: a small, fast model (Haiku) with tools.

Every free-text message (and screenshot) from Loïc lands here. The model understands what he wants, calls the
bot's own functions as tools (validate a thumbnail, change a setting, redo a design, show the chapters…), and
answers in a couple of lines. Heavy jobs (renders, frame search) are started in the background and announced.
Only a real code change goes to Claude Code, and only after Loïc's yes on a button.
"""
import asyncio
import json
import re
import time

SYSTEM = """Tu es BTR Studio, l'assistant Telegram du podcast Break The Routine (DanceSport, hôte Marius Iepure). Tu parles
avec Loïc (producteur) : français, tutoiement, 1 à 4 phrases, texte brut (pas de Markdown, pas de listes à rallonge).
Il veut des solutions, pas des problèmes, et de l'action plutôt que des questions.

Comment tu travailles :
- Tu AGIS avec tes outils. Si sa demande correspond à un outil, appelle-le directement au lieu d'expliquer quoi dire.
  Plusieurs outils d'affilée si besoin (ex. « vertical validé, et le carré texte un peu plus haut puis refais-le »
  = validate + set_design + redo_thumbnails).
- N'affirme jamais qu'une chose est faite si l'outil ne l'a pas confirmé. Un travail lancé en arrière-plan : dis-le
  (« je refais le vertical, ~1 min »). S'il demande « c'est fait ? / j'ai rien reçu », regarde get_status (travaux en
  cours, dernière action) avant de répondre.
- Ce qui part sur YouTube (publier, chapitres, badge) passe par un bouton que l'outil affiche : dis-lui de cliquer.
- Discussion du titre / de la citation de l'épisode en cours (« plus provoc », « le 2 mais plus court », « autre angle ») :
  outil title_chat avec son message tel quel.
- Une demande que les outils ne couvrent pas (nouvelle fonction, nouveau format, bug, retouche de mise en page qui
  n'est pas un réglage) : outil propose_claude_code avec une demande complète et autonome. Ça affiche un bouton ; rien
  ne part sans son oui. Ne dis jamais « c'est transmis » avant son clic.
- Retour visuel sur une miniature (souvent avec captures) : d'abord un RÉGLAGE si ça suffit (set_design : position,
  taille, interligne, devant/derrière…), sinon thumbnail_feedback (Claude Code reprend la miniature avec ses captures).
- Les miniatures : horizontal = youtube, vertical = instagram, carré = square. Une miniature validée est figée.
  « tout validé sauf X » / « c'est bon sauf X » = valide tous les autres formats (et rouvre X s'il était validé), sans
  poser de question.
- Badge PART : épisode EN COURS (pas encore publié par le bot) → set_part puis redo_thumbnails ; vidéo déjà en ligne
  (liste des vidéos récentes) → badge.
- Reels (extraits verticaux du dernier épisode) : reels_propose pour une nouvelle liste de 10 moments ; « prends 1, 3 et 7 »
  = reels_select ; reel_validate / reel_drop. Les reels ne sont jamais publiés par le bot : Loïc publie lui-même.
  Ses retours arrivent souvent en vrac, sur plusieurs reels d'un coup (« réel 2 : fin trop sèche ; réel 3 : sous-titre faux
  à “why are you here”, et il manque “me” à “give me” ; réel 6 good »). Traite CHAQUE point, un outil par point :
  · début / fin (« fin abrupte », « coupe trop tôt », « il manque le dernier mot », « commence plus tôt ») = reel_adjust :
    end_shift / start_shift en secondes (1 image = 0,04 s ; « 5-15 images » ≈ 0,4 s ; fin abrupte ≈ +0,4 ; dernier mot
    manquant ≈ +0,6 ; positif = plus tard, négatif = plus tôt) ; cut = une phrase EXACTE à enlever, prise dans ce qui est dit.
  · tout ce qui touche au TEXTE des sous-titres (mot faux, nom mal écrit, « Muti c'est Motsi », « problème de sous-titre à
    tel endroit », mise en page) = reel_subtitles avec son retour tel quel pour ce reel (il comprend et ne refait que les
    sous-titres). Un doute sur un nom (« je suis pas sûr, c'est peut-être Motsi ») : passe-le aussi, avec ses mots.
  · « good », « parfait », « ok » sur un reel = rien à faire (ne le valide pas sans qu'il le dise).
  · Déroulé : 1) il valide ou jette chaque reel ; 2) quand tout est décidé, le bot lui demande lesquels vont en feed
    Instagram (boutons) ; 3) « Ranger » : covers + Drive + ClickUp. « le 2 et le 5 en feed » = reels_file(feed=[2, 5]) ;
    sur un reel déjà rangé, « le 3 finalement en feed / pas en feed » = reel_validate avec instagram true / false.
    Si le contexte dit que TOUS les reels sont rangés, n'annonce ni boutons ni question de feed : « je valide les covers »
    = c'est fini, réponds en une ligne avec le récap (où va chaque reel), sans lancer d'outil.
  · « garde X et Y ensemble », « le time est séparé de good » = reel_subtitles avec son message tel quel (il force ces
    mots sur le même bloc). « j'ai jeté par erreur », « reviens en arrière » sur un reel jeté = reel_undrop.
  · « renvoie-moi / remontre-moi les reels » = reels_show (aucun travail refait). « refais / remonte avec les nouvelles
    règles » = reels_resend. « non refais pas », « annule » = reels_stop.
  · Quand on parle des reels, « miniatures », « covers », « screenshots » = les COVERS des reels (reel_cover pour un
    changement précis, reels_cover_search pour de meilleures photos), JAMAIS les miniatures de l'épisode YouTube.
  · la COVER / miniature d'un reel (« autre photo », « mets la 3 », « texte : they just / DON'T / CARE ») = reel_cover.
  · Les reels rangés vont sur Drive (dossier du guest) et dans ClickUp (lien, légendes, cover). Si Drive ou ClickUp ne
    sont pas connectés, dis-lui d'envoyer /connect.
  · Une règle pour TOUS les futurs reels (« toujours laisser plus de temps à la fin ») : propose_claude_code.
  Termine par un récap court de ce qui est lancé, reel par reel.
- Si c'est vraiment ambigu, pose UNE question courte. Sinon décide.

État actuel :
{context}"""

FORMATS = {"type": "array", "items": {"type": "string", "enum": ["youtube", "instagram", "square"]},
           "description": "youtube = horizontal, instagram = vertical, square = carré"}

TOOLS = [
    {"name": "get_status", "description": "État détaillé : épisode en cours (étape, axes, titre, citation, miniatures validées, "
     "chapitres), travaux en cours, dernière action, demande à Claude en attente.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "title_chat", "description": "Discussion du titre YouTube / de la citation de miniature de l'épisode en cours (nouvelles "
     "propositions, ajustements, choix). Passe le message de Loïc tel quel.",
     "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
    {"name": "choose_axis", "description": "Retenir l'axe n (1, 2, 3…) proposé : lance la recherche d'images.",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}},
    {"name": "other_frames", "description": "MINIATURES YOUTUBE DE L'ÉPISODE seulement (pendant leur préparation) : "
                                          "proposer d'autres images du guest ou de Marius. Pour les covers / photos des "
                                          "REELS : reels_cover_search.",
     "input_schema": {"type": "object", "properties": {"who": {"type": "string", "enum": ["guest", "marius"]}}, "required": ["who"]}},
    {"name": "validate", "description": "Valider (figer) des miniatures.", "input_schema": {"type": "object", "properties": {"formats": FORMATS}, "required": ["formats"]}},
    {"name": "reopen", "description": "Dé-valider des miniatures pour pouvoir les modifier.", "input_schema": {"type": "object", "properties": {"formats": FORMATS}, "required": ["formats"]}},
    {"name": "redo_thumbnails", "description": "Refaire des miniatures (arrière-plan, ~1-4 min), avec les réglages et images actuels. Rouvre celles qui étaient validées.",
     "input_schema": {"type": "object", "properties": {"formats": FORMATS}, "required": ["formats"]}},
    {"name": "set_design", "description": "Montrer ou changer les RÉGLAGES d'une miniature (noms exacts dans get_status / show). "
     "Valeurs relatives : une chaîne signée (\"+20\", \"-15\", \"x1.1\") s'ajoute à la valeur ACTUELLE (voir l'état). « Un peu » ≈ 15-20 px, "
     "« beaucoup » ≈ 50. UN SEUL appel par réglage, ne te corrige pas après coup. Ne refait pas la miniature : enchaîne avec "
     "redo_thumbnails (sauf si la miniature est validée et que Loïc ne veut pas la rouvrir).",
     "input_schema": {"type": "object", "properties": {"format": {"type": "string", "enum": ["youtube", "instagram", "square"]},
                                                       "set": {"type": "object", "description": "{nom_du_réglage: valeur}"},
                                                       "reset": {"type": "boolean"}, "show": {"type": "boolean"}},
                      "required": ["format"]}},
    {"name": "set_title", "description": "Remplacer le titre YouTube de l'épisode en cours par ce texte exact.",
     "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}},
    {"name": "set_quote", "description": "Remplacer la citation des miniatures (haut / MOT / bas) et refaire les miniatures non validées.",
     "input_schema": {"type": "object", "properties": {"top": {"type": "string"}, "key": {"type": "string"}, "bottom": {"type": "string"}},
                      "required": ["top", "key", "bottom"]}},
    {"name": "set_part", "description": "Badge « PART n » en haut à droite des 3 miniatures de l'épisode en cours (part vide = enlever).",
     "input_schema": {"type": "object", "properties": {"part": {"type": "string"}}, "required": ["part"]}},
    {"name": "edit_description", "description": "Réécrire la description YouTube selon une consigne (garde la structure).",
     "input_schema": {"type": "object", "properties": {"instruction": {"type": "string"}}, "required": ["instruction"]}},
    {"name": "send_recap", "description": "Renvoyer les 3 miniatures actuelles + titre + description (dernier check avant publication).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "publish", "description": "Proposer la publication (titre, description, miniature) : affiche le bouton de confirmation.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "chapters", "description": "Chapitres : show = les afficher (avec bouton YouTube), retime = recaler les timecodes sur le SRT, "
     "regenerate = refaire le chapitrage, into_description = les mettre dans la description avant publication.",
     "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["show", "retime", "regenerate", "into_description"]}},
                      "required": ["action"]}},
    {"name": "badge", "description": "Poser le badge « PART n » sur la miniature YouTube ACTUELLE d'une vidéo DÉJÀ EN LIGNE (pas l'épisode en cours de préparation : set_part) : "
     "aperçu + bouton de validation. Trouve l'id dans la liste des vidéos récentes.",
     "input_schema": {"type": "object", "properties": {"video_id": {"type": "string"}, "part": {"type": "string"}}, "required": ["video_id", "part"]}},
    {"name": "thumbnail_feedback", "description": "Retour de mise en page sur une miniature qui demande de retoucher le template (pas un simple "
     "réglage) : prépare la demande pour Claude Code avec ses captures, et affiche le bouton de confirmation.",
     "input_schema": {"type": "object", "properties": {"feedback": {"type": "string", "description": "le retour complet de Loïc, reformulé clairement"}},
                      "required": ["feedback"]}},
    {"name": "propose_claude_code", "description": "Proposer de faire coder par Claude Code (nouvelle fonction, bug, comportement différent). "
     "Affiche un bouton ; rien ne part sans le oui de Loïc.",
     "input_schema": {"type": "object", "properties": {"request": {"type": "string", "description": "demande complète, autonome, précise"}},
                      "required": ["request"]}},
    {"name": "reels_propose", "description": "Proposer 10 moments pour des reels (dernier épisode, ou la vidéo donnée).",
     "input_schema": {"type": "object", "properties": {"video": {"type": "string", "description": "lien ou id YouTube (facultatif)"}}}},
    {"name": "reels_select", "description": "Monter les moments choisis (numéros de la liste des reels).",
     "input_schema": {"type": "object", "properties": {"numbers": {"type": "array", "items": {"type": "integer"}}}, "required": ["numbers"]}},
    {"name": "reel_adjust", "description": "Retoucher un reel déjà monté puis le refaire : décaler le début / la fin (secondes, "
     "cumulé avec les retouches d'avant), enlever une phrase exacte, ou remettre les phrases enlevées (uncut).",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}, "start_shift": {"type": "number"},
                                                       "end_shift": {"type": "number"}, "cut": {"type": "string"},
                                                       "uncut": {"type": "boolean"}}, "required": ["n"]}},
    {"name": "reel_subtitles", "description": "Retour de Loïc sur les SOUS-TITRES d'un reel monté (mot ou nom faux, sous-titre "
     "bizarre à un endroit, mise en page) : Claude relit le reel, corrige les mots visés, et seuls les sous-titres sont refaits.",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}, "feedback": {"type": "string",
                      "description": "son retour sur ce reel, tel quel"}}, "required": ["n", "feedback"]}},
    {"name": "reel_validate", "description": "Valider le reel n (étape 1 ; rien n'est rangé avant que tous les reels "
                                         "soient validés ou jetés). instagram = true / false : en feed Instagram ou "
                                         "seulement TikTok + Shorts ; sur un reel déjà rangé, le déplace.",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}, "instagram": {"type": "boolean"}},
                      "required": ["n"]}},
    {"name": "reels_cover_search", "description": "Chercher de meilleures photos pour les COVERS (miniatures) des reels "
                                                 "(« trouve de meilleurs screenshots pour les miniatures, garde la 8 ») : "
                                                 "nums = les reels à refaire (pas ceux qu'il garde). Différent des "
                                                 "miniatures de l'épisode YouTube.",
     "input_schema": {"type": "object", "properties": {"nums": {"type": "array", "items": {"type": "integer"}},
                                                       "want": {"type": "string", "description": "ce que Loïc veut sur "
                                                                "la photo, ses mots (« bouche fermée », « qu'elle sourie »)"}}}},
    {"name": "reel_undrop", "description": "Annuler « jeter » sur le reel n (jeté par erreur, « reviens en arrière ») : "
                                          "il revient à valider, avec le même fichier.",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}},
    {"name": "reels_file", "description": "Ranger les reels validés (covers, Drive, ClickUp). feed = numéros qui vont "
                                         "aussi sur Instagram, dans l'ordre de publication (« le 2 et le 5 en feed, "
                                         "range »). Les autres vont sur TikTok + Shorts seulement.",
     "input_schema": {"type": "object", "properties": {"feed": {"type": "array", "items": {"type": "integer"}}}}},
    {"name": "reel_drop", "description": "Jeter le reel n.",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}},
    {"name": "reel_cover", "description": "Refaire la cover (miniature) du reel n : autre photo (photo = numéro, ou "
                                          "« next » pour la suivante) et/ou autre accroche (small = petits mots, big = "
                                          "mot(s) en très gros, gold = dernier(s) mot(s) en or italique ; uniquement des "
                                          "mots dits dans le reel, dans l'ordre) et/ou zoom sur la tête (zoom = facteur, "
                                          "1.05 à 1.5, ex. « zoom x1.25 » ; 1 = sans zoom ; gardé pour cette photo). "
                                          "Si le reel est validé, Drive et ClickUp sont mis à jour.",
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}, "photo": {"type": ["integer", "string"]},
                                                       "small": {"type": "string"}, "big": {"type": "string"},
                                                       "gold": {"type": "string"}, "zoom": {"type": "number"}},
                     "required": ["n"]}},
    {"name": "reels_show", "description": "RENVOYER / REMONTRER / RÉAFFICHER des reels tels quels, sans rien refaire "
                                         "(« renvoie-moi les reels », « remontre-moi le 1, 2, 3 », « je veux les revoir »). "
                                         "Sans liste = tous les reels validés ou à valider. Instantané.",
     "input_schema": {"type": "object", "properties": {"nums": {"type": "array", "items": {"type": "integer"}}}}},
    {"name": "reels_stop", "description": "Annuler les reels en attente d'être refaits (« non refais pas », « arrête », "
                                         "« annule ») : ils gardent leur version actuelle.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "reels_resend", "description": "REFAIRE (remonter à nouveau) des reels avec les règles actuelles, seulement si "
                                            "Loïc demande de les REFAIRE / remonter / appliquer les nouvelles règles. Pour "
                                            "juste les revoir : reels_show. Sans liste = tous les reels cochés.",
     "input_schema": {"type": "object", "properties": {"nums": {"type": "array", "items": {"type": "integer"}}}}},
    {"name": "start_episode", "description": "Traiter une vidéo précise (lien ou id YouTube) comme nouvel épisode.",
     "input_schema": {"type": "object", "properties": {"video": {"type": "string"}}, "required": ["video"]}},
    {"name": "scan_youtube", "description": "Vérifier tout de suite YouTube (nouvelles vidéos non répertoriées) et le dossier Drive des SRT.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "costs", "description": "Dépenses estimées de l'IA (par tâche et par modèle).",
     "input_schema": {"type": "object", "properties": {"days": {"type": "number", "description": "1 = dernières 24 h, 7, 30…"}}}},
    {"name": "health_check", "description": "Lancer le test complet de l'installation (YouTube, téléchargement, Drive, IA…). Résultat envoyé à la fin.",
     "input_schema": {"type": "object", "properties": {}}},
]


def _block(b) -> dict:
    """An assistant content block, as it must be sent back in the next request."""
    t = getattr(b, "type", "")
    if t == "text":
        return {"type": "text", "text": b.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return b.model_dump(exclude_none=True)   # thinking / redacted_thinking: passed back untouched


CLAIMS = re.compile(r"arrière-plan|je (re)?lance|je mets|je refais|je cherche|je renvoie|je range|je te renvoie|"
                    r"c'est lancé|je m'en occupe|je passe à", re.I)


async def converse(llm, model: str, context: str, history: list[dict], user_content, handlers: dict,
                   max_steps: int = 12) -> tuple[str, list[str]]:
    """Runs the tool loop. Returns (final text for Loïc, list of actions done)."""
    system = SYSTEM.format(context=context)
    messages = list(history) + [{"role": "user", "content": user_content}]
    actions: list[str] = []
    text = ""
    nudged = False
    for _ in range(max_steps):
        msg = await asyncio.to_thread(lambda: llm.create("discussion", model=model, max_tokens=1200, system=system,
                                                         tools=TOOLS, messages=messages))
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        uses = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
        if not uses and not actions and not nudged and CLAIMS.search(text):
            # it says it launched something but called no tool (it copied an earlier answer): make it act for real
            nudged = True
            messages.append({"role": "assistant", "content": text or "…"})
            messages.append({"role": "user", "content": "(note du système, pas de Loïc) Tu viens d'annoncer une action "
                             "sans appeler aucun outil : rien n'est lancé. Appelle maintenant l'outil qui la fait, puis "
                             "réponds. Si aucun outil ne peut la faire, dis-le honnêtement."})
            continue
        if not uses:
            return text, actions
        messages.append({"role": "assistant", "content": [_block(b) for b in msg.content]})
        results = []
        for u in uses:
            fn = handlers.get(u.name)
            try:
                out = await fn(**(u.input or {})) if fn else f"outil inconnu : {u.name}"
            except Exception as e:  # noqa: BLE001
                out = f"ERREUR : {e}"
            actions.append(f"{u.name}({json.dumps(u.input, ensure_ascii=False)[:150]}) → {str(out)[:150]}")
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": str(out)[:6000]})
        messages.append({"role": "user", "content": results})
    return text or "C'est lancé.", actions


# ---------------------------------------------------------------- conversation memory
def clean(text: str) -> str:
    """Bot messages are Telegram HTML: keep the words only."""
    t = re.sub(r"<[^>]+>", "", text or "")
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"), ("&quot;", '"'), ("&#x27;", "'")):
        t = t.replace(a, b)
    return t.strip()


class Memory:
    """The whole chat as the model sees it: Loïc's messages, and everything the bot posted (merged per turn)."""

    def __init__(self, reg, key: str = "convo", keep: int = 30):
        self.reg, self.key, self.keep = reg, key, keep

    def _list(self) -> list[dict]:
        return self.reg.data.setdefault(self.key, [])

    def add(self, role: str, text: str) -> None:
        text = clean(text)[:1500]
        if not text:
            return
        lst = self._list()
        if lst and lst[-1]["role"] == role:
            lst[-1]["content"] = (lst[-1]["content"] + "\n" + text)[-3000:]
        else:
            lst.append({"role": role, "content": text, "t": round(time.time())})
        del lst[:-self.keep]
        self.reg.save()

    def history(self) -> list[dict]:
        """Valid API history: starts with a user turn, ends with an assistant turn (the new message follows)."""
        h = [{"role": m["role"], "content": m["content"]} for m in self._list()]
        while h and h[0]["role"] != "user":
            h.pop(0)
        if h and h[-1]["role"] == "user":
            h.pop()
        return h
