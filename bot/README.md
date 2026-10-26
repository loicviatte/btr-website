# BTR bot

Ce bot surveille la chaîne YouTube Break The Routine. Dès qu'une vidéo passe en **non répertorié**, il :

1. récupère le transcript (sous-titres YouTube) ;
2. t'envoie sur **Telegram 3 axes de titre et de citation**, en se basant sur les anciens titres de la chaîne. Tu en discutes avec lui jusqu'à trouver le bon ;
3. cherche dans la vidéo des **gros plans du guest et de Marius** qui collent à la phrase, et te les envoie. Tu en choisis un ou tu demandes d'autres ;
4. fabrique la **miniature YouTube 1920×1080** et la **miniature Instagram 1080×1920** avec les templates validés (détourage, extension IA, voile or) ;
5. après ta validation, met **le titre, la description (structure actuelle de la chaîne) et la miniature** sur YouTube ;
6. fait le **chapitrage** (règles BTR : anglais, 3 à 8 mots, sans tiret) avec les sous-titres YouTube, ou avec ton SRT DaVinci si tu l'envoies dans le chat, puis l'ajoute à la description.

Commandes Telegram : `/status`, `/scan` (vérifier YouTube tout de suite) et `/episode <lien ou ID>` (traiter une vidéo précise).
Dans le chat, à l'étape des miniatures : `titre: …`, `citation: haut | MOT | bas`, `description: <consigne>`. Tout autre message relance la discussion sur l'axe.

---

## Installation (environ 30 min, une seule fois)

Toute la config est dans les **secrets GitHub** du dépôt `btr-website`, à côté de ceux du site. Il n'y a pas de `.env` à remplir : à chaque push qui touche `bot/`, la GitHub Action **Deploy bot** copie le code sur le serveur, y écrit la config à partir des secrets, installe ce qui manque, redémarre le bot et lance le check.

### 1. Le bot Telegram (2 min)
Dans Telegram, écris à **@BotFather** et envoie `/newbot`. Choisis un nom (*BTR Studio*) et un identifiant (`btr_studio_bot`), puis copie le **token** qu'il te donne.

### 2. La clé Anthropic
Sur **console.anthropic.com** : *API Keys* → *Create key*. Compte environ 0,50 à 1,50 $ par épisode.

### 3. Le serveur (10 min)
1. Sur ton Mac, crée une clé SSH réservée au déploiement :
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/btr_bot -C btr-bot-deploy && cat ~/.ssh/btr_bot.pub
   ```
2. Sur **Hetzner Cloud**, clique sur *Add Server* et choisis **Ubuntu 24.04**, x86, **8 Go de RAM** (~7–8 €/mois). Dans *SSH keys*, colle la ligne `ssh-ed25519 …` affichée juste avant.
3. Note l'**IP** du serveur.

### 4. Les secrets GitHub (5 min)
Va dans **btr-website → Settings → Secrets and variables → Actions → New repository secret** :

| Secret | Valeur |
|---|---|
| `BOT_SERVER_HOST` | l'IP du serveur |
| `BOT_SERVER_SSH_KEY` | le contenu de `~/.ssh/btr_bot` (la clé **privée** : `cat ~/.ssh/btr_bot \| pbcopy`) |
| `TELEGRAM_BOT_TOKEN` | le token de BotFather |
| `ANTHROPIC_API_KEY_BOT` | ta clé Anthropic dédiée au bot |
| `BOT_YT_COOKIES` | *(optionnel)* le contenu du `cookies.txt` YouTube, voir plus bas |

`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` et `YT_CHANNEL_ID` y sont **déjà** pour le site : le bot les réutilise tels quels (même app Google « BTR Website », scope `youtube.force-ssl`).

### 5. Lancer
Dans **Actions → Deploy bot → Run workflow**. La première fois, comptez 10 à 15 min (installation). Ensuite, chaque mise à jour prend environ 1 min.
Puis envoie **/start** à ton bot sur Telegram : ce chat en devient le propriétaire, et personne d'autre ne peut lui parler. Pour imposer un chat précis, ajoute plutôt le secret `TELEGRAM_CHAT_ID`.

Le résultat du check est en bas du log de l'Action, avec une ligne ✅/❌ par élément.

### Si « Video download » est ❌ (YouTube bloque l'IP du serveur)
1. Installe l'extension Chrome **« Get cookies.txt LOCALLY »**.
2. Va sur youtube.com en étant connecté (un compte secondaire suffit), puis exporte les cookies.
3. Colle tout le contenu du fichier dans le secret `BOT_YT_COOKIES`.
4. Relance *Run workflow*.

Si ça ne suffit pas : proxy résidentiel, ou bot sur un Raspberry Pi chez toi (même workflow, il suffit de changer l'IP).

Pour voir les logs en direct (facultatif) : `ssh -i ~/.ssh/btr_bot root@IP journalctl -u btr-bot -f`.

## Notes
- **Premier lancement :** les vidéos déjà non répertoriées sont ignorées. Pour en traiter une : `/episode <ID>`.
- **Police :** les titres sont en Monument Extended **Heavy**. Pour l'Ultrabold, dépose `PPMonumentExtended-Ultrabold.woff2` dans `btrbot/assets/` et dis-le-moi, je le branche.
- **Rendus :** chaque épisode est rangé dans `data/episodes/<ID>/` (frames, miniatures, transcript, état).
- **Sécurité :** le bot ne répond qu'à ton chat Telegram.
