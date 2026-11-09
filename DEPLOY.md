# Déployer une instance (un client) sur Fly.io

> Non testé depuis mon environnement : suis les étapes et dis-moi ce qui coince.
> Chaque client = une application Fly.io + un volume (pour `usage.json`) + ses propres secrets.

## 0. Une seule fois
1. Crée un compte sur https://fly.io (une carte bancaire est demandée).
2. Installe flyctl (PowerShell) : `pwsh -c "iwr https://fly.io/install.ps1 -useb | iex"`
3. `fly auth login`

## 1. Créer l'instance du client 1 (depuis le dossier `backend`)
```powershell
fly apps create subs-client1
fly volumes create data --size 1 --region cdg -a subs-client1
```
Modifie `app = "subs-client1"` dans `fly.toml` si tu as choisi un autre nom.

## 2. Secrets (clés + jetons) — à générer pour CE client
Génère deux jetons aléatoires (garde-les) :
```powershell
[guid]::NewGuid().ToString("N")   # -> ACCESS_TOKEN (à donner au client)
[guid]::NewGuid().ToString("N")   # -> ADMIN_TOKEN  (pour toi seul)
```
Puis (remplace les valeurs) :
```powershell
fly secrets set -a subs-client1 `
  DEEPGRAM_API_KEY=xxxx GEMINI_API_KEY=xxxx `
  ACCESS_TOKEN=le_jeton_client ADMIN_TOKEN=ton_jeton_admin
```
Sans `ACCESS_TOKEN`, n'importe qui pourrait utiliser (et facturer) ton instance : ne l'oublie jamais.

## 3. Déployer
```powershell
fly deploy -a subs-client1 --ha=false
fly logs -a subs-client1
```
Test : ouvre `https://subs-client1.fly.dev/health` → `{"state":"idle"}`.

## 4. Brancher l'application Flutter
Dans l'app → « Backend Python » :
- URL WebSocket : `wss://subs-client1.fly.dev/control`
- Jeton d'accès : le `ACCESS_TOKEN` (le jeton admin seulement sur ton PC)
Puis « Démarrer la traduction » : le micro de ton PC est envoyé au serveur.
URL OBS : copie-la depuis l'app (elle contient déjà le jeton).

## Limite de dépense
`BUDGET_USD` dans `fly.toml` (5 $ par défaut). Pour la changer sans redéployer :
dans l'app avec le jeton admin, section « Coût & limite ». Le dashboard admin (étape suivante)
fera la même chose pour tous les clients.
