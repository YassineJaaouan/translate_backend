# Déployer sur Render (offre gratuite) — premier client

> Non testé depuis mon environnement. Dis-moi ce qui coince.

## Limites du plan gratuit à connaître
- **Mise en veille après ~15 min sans activité** ; le réveil prend environ 1 minute. Démarre le backend
  (ouvre `/health`) quelques minutes avant un direct.
- **Disque non persistant** : `usage.json` (compteur de coût) est **remis à zéro à chaque veille/redémarrage**.
  La limite de 5 $ n'est donc PAS fiable sur Render gratuit. Pour te protéger vraiment, fixe aussi
  une limite de dépense directement chez Deepgram et Google AI Studio (leurs consoles).
- Convient pour un test, pas pour un client payant.

## 1. Mettre le backend sur GitHub (dépôt PRIVÉ)
Le dossier `backend` contient un `.gitignore` qui exclut `.env` : tes clés ne partent jamais sur GitHub.
```powershell
cd C:\Users\yassi\Downloads\arabic-subs-backend\arabic-subs\backend
git init
git add .
git status          # vérifie que .env n'apparaît PAS dans la liste
git commit -m "backend"
```
Crée un dépôt **privé** vide sur github.com (ex. `subs-backend`), puis :
```powershell
git remote add origin https://github.com/TON_COMPTE/subs-backend.git
git branch -M main
git push -u origin main
```

## 2. Créer le service sur Render
1. https://render.com → connexion avec GitHub.
2. **New +** → **Web Service** → choisis le dépôt `subs-backend`.
3. Language : **Docker** (il détecte le `Dockerfile`). Instance type : **Free**. Région : Frankfurt.
4. **Environment Variables** (ce sont tes secrets, saisis-les ici) :
   - `DEEPGRAM_API_KEY`, `GEMINI_API_KEY` (nouvelles clés, les anciennes sont à révoquer)
   - `ACCESS_TOKEN` et `ADMIN_TOKEN` (deux chaînes aléatoires : PowerShell `[guid]::NewGuid().ToString("N")`)
   - `TRANSLATION_PROVIDER` = `gemini`, `BUDGET_USD` = `5`, `MIN_WORDS_INTERIM` = `8`
5. **Create Web Service**. Attends « Live », puis ouvre `https://TON-SERVICE.onrender.com/health`
   → `{"state":"idle"}`.

## 3. Brancher l'app
Dans « Backend Python » : URL `wss://TON-SERVICE.onrender.com/control`, jeton d'accès = `ACCESS_TOKEN`
(jeton admin seulement sur ton PC). Démarrer la traduction. Copie l'URL OBS depuis l'app.

## Passer plus tard à un VPS
Le même `Dockerfile` fonctionne tel quel ; seul le lieu change.
