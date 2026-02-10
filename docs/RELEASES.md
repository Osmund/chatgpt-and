# Release-prosess for Anda 🦆

Denne guiden beskriver hvordan du lager en ny release som alle ender med auto-update vil plukke opp.

## Forutsetninger

- Git-tilgang til `Osmund/oDuckberry` (origin)
- GitHub-konto med tilgang til å lage releases
- `gh` CLI (valgfritt, men anbefalt): `sudo apt install gh`

## Oppsett på ny and (engangs)

Repoet er privat, så hver and trenger en GitHub Personal Access Token (PAT).

### 1. Opprett token på GitHub

1. Gå til https://github.com/settings/tokens?type=beta (Fine-grained tokens)
2. **Token name**: `anda-update-<andnavn>` (f.eks. `anda-update-samantha`)
3. **Expiration**: Velg lang varighet (1 år+) eller "No expiration"
4. **Repository access**: Only select repositories → `Osmund/oDuckberry`
5. **Permissions**: Contents → Read-only
6. Trykk **Generate token** og kopier tokenet

### 2. Lagre token på Pi'en

```bash
mkdir -p ~/.config/duck
echo "ghp_DittTokenHer" > ~/.config/duck/github_token
chmod 600 ~/.config/duck/github_token
```

### 3. Aktivér auto-update

Via kontrollpanelet: **⚙️ System → 🔄 Auto-Update → Aktivér**

Eller via terminal:
```bash
sudo systemctl enable --now duck-update.timer
```

### 4. Test at det fungerer

```bash
# Tørkjør oppdateringsskriptet
sudo systemctl start duck-update.service
sudo journalctl -u duck-update.service --no-pager -n 20
```

## Steg-for-steg

### 1. Gjør ferdig endringene

Commit og push alle endringer til `main`:

```bash
cd /home/admog/Code/chatgpt-and
git add -A
git commit -m "feat: beskrivelse av endringene"
git push origin main
```

### 2. Bump versjonsnummeret

Anda bruker [Semantic Versioning](https://semver.org/):
- **MAJOR** (3.0.0): Breaking changes, stor omskriving
- **MINOR** (2.3.0): Ny funksjonalitet, nye features
- **PATCH** (2.2.1): Bugfix, små justeringer

```bash
# Oppdater VERSION-filen
echo "2.3.0" > VERSION

# Commit versjonsbump
git add VERSION
git commit -m "release: v2.3.0"
git push origin main
```

### 3. Opprett Git-tag

```bash
git tag v2.3.0
git push origin v2.3.0
```

### 4. Opprett GitHub Release

#### Alternativ A: Via `gh` CLI (anbefalt)

```bash
gh release create v2.3.0 \
  --title "v2.3.0 - Kort beskrivelse" \
  --notes "## Hva er nytt

- ✨ Ny feature
- 🐛 Bugfix
- 🔧 Forbedring

## Migrasjoner
Ingen manuelle steg nødvendig."
```

#### Alternativ B: Via GitHub web

1. Gå til https://github.com/Osmund/oDuckberry/releases/new
2. Velg tag: `v2.3.0`
3. Tittel: `v2.3.0 - Kort beskrivelse`
4. Skriv release notes (se mal nedenfor)
5. Trykk **Publish release**

### 5. Verifiser

Sjekk at release er synlig via API:

```bash
curl -s https://api.github.com/repos/Osmund/oDuckberry/releases/latest | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"Release: {d.get('tag_name', 'INGEN')}\")"
```

## Hva skjer automatisk

1. **Kl 03:00** (± 30 min tilfeldig forsinkelse): `duck-update.timer` trigger
2. Skriptet sjekker GitHub Releases API for ny versjon
3. Hvis ny versjon > installert versjon:
   - Tar backup (git stash)
   - Henter ny kode (git fetch + checkout tag)
   - Installerer nye pip-pakker
   - Kjører nye migrasjoner
   - Oppdaterer endrede service-filer
   - Verifiserer syntaks (py_compile)
   - Restarter tjenester
   - Sjekker at tjenester kjører OK
   - **Ruller automatisk tilbake** hvis noe feiler
4. Neste morgen sier anda: *"Jeg fikk en oppdatering i natt! Versjon 2.3.0."*

## Auto-update på/av

Auto-update er **av som standard**. Aktivér per and via kontrollpanelet:

**⚙️ System → 🔄 Auto-Update → Aktivér**

Eller via terminal:
```bash
# Aktivér
sudo systemctl enable --now duck-update.timer

# Deaktivér
sudo systemctl disable --now duck-update.timer

# Sjekk status
systemctl status duck-update.timer

# Kjør manuelt (for testing)
sudo systemctl start duck-update.service
```

## Logger

```bash
# Se oppdateringslogg
sudo journalctl -u duck-update.service --no-pager

# Se siste oppdateringsstatus (JSON)
cat /tmp/duck_last_update.json
```

## Migrasjoner

Hvis en release krever databasemigrasjoner:

1. Legg migrasjonen i `migrations/` med beskrivende filnavn
2. Skriptet kjører automatisk alle `.py`-filer i `migrations/` som ikke allerede er kjørt
3. Markører lagres i `/tmp/duck_migration_done_<filnavn>`

**NB:** Migrasjons-markører i `/tmp/` slettes ved reboot. For å unngå at migrasjoner kjører dobbelt, sørg for at de er idempotente (trygt å kjøre flere ganger).

## Rollback manuelt

Hvis en oppdatering har gått galt og auto-rollback ikke fungerte:

```bash
cd /home/admog/Code/chatgpt-and

# Se tilgjengelige versjoner
git tag -l

# Gå tilbake til forrige versjon
git checkout v2.2.0

# Restart tjenester
sudo systemctl restart chatgpt-duck.service duck-control.service duck-memory-worker.service

# Oppdater VERSION-filen
echo "2.2.0" > VERSION
```

## Release notes mal

```markdown
## Hva er nytt

- ✨ Feature: beskrivelse
- 🐛 Fix: beskrivelse
- 🔧 Endring: beskrivelse

## Tekniske detaljer

- Berørte filer: ...
- Nye dependencies: ingen / liste

## Migrasjoner

Ingen manuelle steg nødvendig.
```

## Push til public repo

Husk å pushe til begge repos hvis ønskelig:

```bash
git push origin main && git push public main
git push origin v2.3.0 && git push public v2.3.0
```
