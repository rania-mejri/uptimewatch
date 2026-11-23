# Journal de bord - UptimeWatch

## Phase 1 - Environnement

### Docker ne pouvait pas télécharger d'images
- Symptôme : `docker run hello-world` restait bloqué, puis erreur `no such host` et timeout vers une adresse IPv6.
- Cause : connexion instable + IPv6 qui ne fonctionne pas sur mon réseau ; Docker Desktop essayait l'IPv6.
- Solution : installation du moteur Docker directement dans Ubuntu (`docker.io`), apt forcé en IPv4.
- Leçon : diagnostiquer couche par couche (DNS, puis connectivité, puis application).

### permission denied sur docker.sock
- Cause : mon utilisateur n'était pas dans le groupe `docker`.
- Solution : `sudo usermod -aG docker $USER` puis `wsl --shutdown`.

### docker compose : unknown command
- Cause : `~/.docker/config.json` laissé par Docker Desktop.
- Solution : renommer ce fichier.

## Phase 2 - Application

### SyntaxError après copier-coller depuis le PDF
- Cause : le PDF coupe les lignes longues et supprime l'indentation.
- Solution : copier depuis le document en ligne ; vérifier avec `python -m py_compile app/*.py`.

### python3 -m venv échoue
- Cause : paquet `python3.14-venv` absent.
- Solution : `sudo apt install python3.14-venv`.

### ruff signale B008 sur Depends()
- Cause : faux positif connu avec FastAPI.
- Solution : configuration dans `pyproject.toml` (`extend-immutable-calls`).
