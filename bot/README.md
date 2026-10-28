# BTR bot

Ce bot surveille la chaîne YouTube Break The Routine. Dès qu'une vidéo passe en **non répertorié**, il :

1. récupère le transcript (sous-titres YouTube) ;
2. t'envoie sur **Telegram 3 axes de titre et de citation**, en se basant sur les anciens titres de la chaîne. Tu en discutes avec lui jusqu'à trouver le bon ;
3. cherche dans la vidéo des **gros plans du guest et de Marius** qui collent à la phrase, et te les envoie. Tu en choisis un ou tu demandes d'autres ;
4. fabrique la **miniature YouTube 1920×1080**, la **miniature Instagram 1080×1920** et la **version carrée 1080×1080** avec les templates validés (détourage, extension IA, voile or) ;
5. après ta validation, met **le titre, la description (structure actuelle de la chaîne) et la miniature** sur YouTube ;
6. fait le **chapitrage** (règles BTR : anglais, 3 à 8 mots, sans tiret) avec les sous-titres YouTube, ou avec ton SRT DaVinci si tu l'envoies dans le chat, puis l'ajoute à la description.

Commandes Telegram : `/status`, `/scan` (vérifier YouTube tout de suite), `/check` (tester toute l'installation) et `/episode <lien ou ID>` (traiter une vidéo précise).
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

## Parler au bot
Écris-lui comme à une personne : « vertical validé, et le carré texte un peu plus haut puis refais-le », « les yeux de Marius sont fermés », « c'est fait ? », « mets PART 2 sur la vidéo d'Oti », « combien j'ai dépensé ? ». Il comprend avec Haiku (rapide, ~0,1 ¢ par message), agit lui-même avec ses outils, et lance les travaux lourds en arrière-plan : tu peux continuer à lui parler pendant un rendu. `/couts` affiche les dépenses estimées.

## Le faire évoluer (mode dev)
Écris-lui normalement. Hors discussion d'épisode (ou si ta demande ne concerne pas le titre en cours), ton message part à **Claude Code**, installé sur le serveur, qui travaille sur une copie du code du bot. Il répond à tes questions (état d'un épisode, logs, fonctionnement). Si tu demandes quelque chose que le bot ne sait pas faire, il **modifie son propre code**, puis te montre les changements avec deux boutons, **🚀 Déployer** ou **❌ Annuler**. Rien n'est mis en ligne sans ton clic.
Au déploiement, il pousse sur GitHub, la GitHub Action met le serveur à jour, et si la nouvelle version plante au démarrage, l'ancienne revient toute seule et le bot te propose **🔧 Corrige**.
`/claude <demande>` force le mode dev. Il tourne sur **Sonnet** (économique) ; `/opus <demande>` passe sur Opus pour les changements difficiles. `/nouveau` lui fait oublier la conversation. Il a besoin du secret `BOT_GITHUB_TOKEN` : un token GitHub *fine-grained* limité au dépôt btr-website, avec *Contents: Read and write*. Le coût réel s'affiche sous chaque réponse.

## Badge PART 1 / PART 2
Pour un épisode en plusieurs parties, le badge « PART 2 » (en haut à droite, comme sur les miniatures de Peter Nash) s'ajoute tout seul sur les 3 miniatures si le titre contient « part 2 ». `part: 2` le force, `part: aucun` l'enlève. Sur une vidéo déjà en ligne : `/badge <lien> 2`, ou demande-le simplement (« mets PART 1 et PART 2 sur les deux dernières d'Oti »). Le bot montre l'aperçu, puis tu valides avec ✅ avant que la miniature change sur YouTube.

## Notes
- **SRT DaVinci :** dépose-le dans le dossier Drive « SRT » (partagé par lien ; dossier modifiable avec `DRIVE_SRT_FOLDER`) ou envoie-le dans le chat. Le bot le relève toutes les 15 min, l'associe à la vidéo dont le titre contient un mot du nom du fichier (`oti_Subtitle_part2.srt` → « Oti … part 2 »), sinon le garde pour la prochaine vidéo. Avec un SRT, il démarre sans attendre les sous-titres YouTube.
- **Premier lancement :** les vidéos déjà non répertoriées sont ignorées. Pour en traiter une : `/episode <ID>`.
- **Police :** les titres sont en Monument Extended **Heavy**. Pour l'Ultrabold, dépose `PPMonumentExtended-Ultrabold.woff2` dans `btrbot/assets/` et dis-le-moi, je le branche.
- **Rendus :** chaque épisode est rangé dans `data/episodes/<ID>/` (frames, miniatures, transcript, état).
- **Sécurité :** le bot ne répond qu'à ton chat Telegram.
