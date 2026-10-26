# Break The Routine — site web

Site Next.js du podcast **Break The Routine** (Dance United × Oti Marius Dance Studio).
Le design vient du canvas Claude Design « BTR Website » ; chaque page du canvas est compilée en page React.

## Pages

| Route | Source du design |
| --- | --- |
| `/` (avec l'intro) | `design/Main.dc.html` |
| `/episodes` (+ Hall of Fame) | `design/Episodes.dc.html` |
| `/episodes/<invité>` | `design/Episode-<invité>.dc.html` |
| `/chain` | `design/Chain.dc.html` |
| `/atlas` | `design/Atlas.dc.html` |
| `/search` | `design/Search.dc.html` |
| `/about` | `design/About.dc.html` |
| `/ask` (lien Instagram uniquement, pas dans le menu) | `design/Ask.dc.html` |

## Mettre en ligne (Vercel)

1. vercel.com → **Add New… → Project** → importer `loicviatte/btr-website`.
2. Laisser les réglages par défaut (Next.js détecté automatiquement) → **Deploy**.
3. Tant que la variable `SITE_LIVE` n'est pas réglée, le site est invisible pour Google (noindex). Au lancement : ajouter `SITE_LIVE` = `1` dans *Settings → Environment Variables* puis redéployer.
4. Optionnel : variable d'environnement `SITE_URL` = l'URL finale (ex. `https://breaktheroutine.com`), puis brancher le domaine dans *Settings → Domains*.

Chaque push sur `main` redéploie le site automatiquement.

## Modifier le site

1. Modifier la page dans le canvas Claude Design (ou directement `design/*.dc.html`).
2. Copier le fichier `.dc.html` dans `design/`.
3. `npm run compile` (régénère `components/dc/`, les routes et `app/dc.generated.css`).
4. `npm run build` pour vérifier, puis commit + push.

Les images et polices sont dans `public/assets/` (nommées par leur id du canvas). `npm run compile` signale dans `lib/missing-assets.generated.json` toute image référencée qui manque.

**Polices** : PP Monument Extended est sous licence. Ce dépôt doit rester **privé**.

## Nouvel épisode

Aujourd'hui : générer la page avec `tools/episode-generator/build_eps.py` (données dans `epdata.py`, `reels.json`, `trans.json`), la copier dans `design/`, puis `npm run compile`.
Prévu : détection automatique des épisodes publics sur YouTube, page créée toute seule, reels via l'API Instagram, transcript via le SRT du Drive.

## Pas encore branché

- Le formulaire **Ask** n'envoie rien pour l'instant (à relier à un stockage, ex. Vercel KV ou un Google Sheet).
- Les moments (réponses de la Chain, tirage de l.Atlas, chapitres, transcript, reels) se lisent dans un lecteur intégré ; les boutons « Watch » ouvrent YouTube dans un nouvel onglet.
- Les reels s'affichent avec leur couverture ; la lecture vidéo viendra de l'API Instagram.
