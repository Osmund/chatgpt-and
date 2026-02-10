#!/bin/bash
# =============================================================================
# Anda Auto-Update Script
# Sjekker GitHub Releases for ny versjon og oppdaterer automatisk.
# Kjøres av systemd timer (duck-update.timer), typisk kl 03:00.
# =============================================================================

set -euo pipefail

# ── Konfigurasjon ─────────────────────────────────────────────────────
INSTALL_DIR="/home/admog/Code/chatgpt-and"
VENV_DIR="${INSTALL_DIR}/.venv"
VERSION_FILE="${INSTALL_DIR}/VERSION"
UPDATE_LOG="/tmp/duck_last_update.json"
LOCK_FILE="/tmp/duck_update.lock"
GITHUB_REPO="Osmund/oDuckberry"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"

# Tjenester som skal restartes etter oppdatering
SERVICES=(
    "chatgpt-duck.service"
    "duck-control.service"
    "duck-memory-worker.service"
)

# ── Logging ───────────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_json() {
    # Skriv oppdateringsstatus til JSON-fil som anda kan lese
    cat > "$UPDATE_LOG" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "status": "$1",
    "from_version": "${CURRENT_VERSION:-unknown}",
    "to_version": "${LATEST_VERSION:-unknown}",
    "message": "$2"
}
EOF
}

# ── Låsemekanisme (unngå samtidige oppdateringer) ─────────────────────
cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))
    if [ "$LOCK_AGE" -lt 600 ]; then
        log "⚠️  Oppdatering allerede i gang (lock: ${LOCK_AGE}s gammel). Avbryter."
        exit 0
    fi
    log "⚠️  Gammel lock-fil fjernet (${LOCK_AGE}s gammel)"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"

# ── Sjekk forutsetninger ──────────────────────────────────────────────
if [ ! -d "$INSTALL_DIR/.git" ]; then
    log "❌ Ikke et git-repository: $INSTALL_DIR"
    exit 1
fi

cd "$INSTALL_DIR"

# Les nåværende versjon
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
else
    CURRENT_VERSION="0.0.0"
    log "⚠️  Ingen VERSION-fil funnet, antar $CURRENT_VERSION"
fi

log "🦆 Anda Auto-Update startet (nåværende: v${CURRENT_VERSION})"

# ── Sjekk om anda er opptatt ──────────────────────────────────────────
# Ikke oppdater midt i en samtale
if [ -f "/tmp/duck_conversation_active.txt" ]; then
    log "💬 Samtale pågår - utsetter oppdatering"
    log_json "deferred" "Samtale pågår"
    exit 0
fi

# ── Hent siste release fra GitHub ─────────────────────────────────────
log "🔍 Sjekker GitHub for ny release..."

RELEASE_JSON=$(curl -s --max-time 30 "$GITHUB_API" 2>/dev/null) || {
    log "❌ Kunne ikke nå GitHub API"
    log_json "error" "Kunne ikke nå GitHub API"
    exit 1
}

# Parse release info
LATEST_VERSION=$(echo "$RELEASE_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tag = data.get('tag_name', '')
# Fjern 'v' prefix hvis det finnes
print(tag.lstrip('v'))
" 2>/dev/null) || {
    log "❌ Kunne ikke parse release-info"
    log_json "error" "Kunne ikke parse release-info fra GitHub"
    exit 1
}

if [ -z "$LATEST_VERSION" ]; then
    log "❌ Ingen release funnet"
    log_json "error" "Ingen release funnet på GitHub"
    exit 1
fi

RELEASE_NOTES=$(echo "$RELEASE_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
body = data.get('body', 'Ingen release notes')
# Første linje eller maks 200 tegn
first_line = body.split('\n')[0][:200] if body else 'Ingen beskrivelse'
print(first_line)
" 2>/dev/null || echo "")

log "📦 Siste release: v${LATEST_VERSION} (installert: v${CURRENT_VERSION})"

# ── Sammenlign versjoner ──────────────────────────────────────────────
version_gt() {
    # Returnerer 0 (true) hvis $1 > $2 (semantic versioning)
    python3 -c "
import sys
def parse_ver(v):
    return tuple(int(x) for x in v.strip().split('.'))
try:
    sys.exit(0 if parse_ver('$1') > parse_ver('$2') else 1)
except:
    sys.exit(1)
" 2>/dev/null
}

if ! version_gt "$LATEST_VERSION" "$CURRENT_VERSION"; then
    log "✅ Allerede oppdatert (v${CURRENT_VERSION})"
    log_json "up_to_date" "Allerede på nyeste versjon"
    exit 0
fi

log "🆕 Ny versjon tilgjengelig: v${CURRENT_VERSION} → v${LATEST_VERSION}"

# ── Backup før oppdatering ────────────────────────────────────────────
log "💾 Tar backup før oppdatering..."
BACKUP_TAG="pre-update-$(date +%Y%m%d-%H%M%S)"
git stash push -m "$BACKUP_TAG" --include-untracked 2>/dev/null || true
ROLLBACK_COMMIT=$(git rev-parse HEAD)
log "   Rollback-punkt: ${ROLLBACK_COMMIT:0:8}"

# ── Hent ny kode ──────────────────────────────────────────────────────
log "📥 Henter ny kode..."

# Fetch og checkout til release-taggen
git fetch origin --tags 2>&1 | head -5
git checkout "v${LATEST_VERSION}" 2>&1 || {
    # Hvis tag ikke finnes som checkout-target, prøv å pulle main
    log "⚠️  Tag v${LATEST_VERSION} ikke funnet, prøver git pull..."
    git checkout main 2>/dev/null || git checkout master 2>/dev/null
    git pull origin main 2>&1 || git pull origin master 2>&1 || {
        log "❌ git pull feilet"
        log_json "error" "git pull feilet"
        exit 1
    }
}

# ── Installer nye dependencies ────────────────────────────────────────
if [ -f "${INSTALL_DIR}/requirements.txt" ]; then
    log "📦 Installerer dependencies..."
    "${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" --quiet 2>&1 | tail -3 || {
        log "⚠️  pip install hadde feil (fortsetter likevel)"
    }
fi

# ── Kjør migrasjoner hvis de finnes ───────────────────────────────────
if [ -d "${INSTALL_DIR}/migrations" ]; then
    for migration in "${INSTALL_DIR}"/migrations/*.py; do
        [ -f "$migration" ] || continue
        migration_name=$(basename "$migration")
        marker="/tmp/duck_migration_done_${migration_name}"
        if [ ! -f "$marker" ]; then
            log "🔄 Kjører migrasjon: ${migration_name}"
            "${VENV_DIR}/bin/python" "$migration" 2>&1 | tail -5 || {
                log "⚠️  Migrasjon feilet: ${migration_name} (fortsetter)"
            }
            touch "$marker"
        fi
    done
fi

# ── Oppdater service-filer hvis endret ────────────────────────────────
SERVICES_CHANGED=false
for svc_file in "${INSTALL_DIR}"/services/*.service "${INSTALL_DIR}"/services/*.timer; do
    [ -f "$svc_file" ] || continue
    svc_name=$(basename "$svc_file")
    installed="/etc/systemd/system/${svc_name}"
    if [ -f "$installed" ]; then
        if ! diff -q "$svc_file" "$installed" > /dev/null 2>&1; then
            log "📋 Oppdaterer service: ${svc_name}"
            sudo cp "$svc_file" "$installed"
            SERVICES_CHANGED=true
        fi
    fi
done

if [ "$SERVICES_CHANGED" = true ]; then
    sudo systemctl daemon-reload
    log "🔄 systemd daemon-reload utført"
fi

# ── Verifiser at koden fungerer (basic sanity check) ──────────────────
log "🧪 Verifiserer oppdatering..."
VERIFY_OK=true

# Sjekk at Python-filene kan importeres uten syntaksfeil
"${VENV_DIR}/bin/python" -c "
import py_compile, sys
files = ['chatgpt_voice.py', 'duck-control.py']
for f in files:
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        print(f'❌ Syntaksfeil i {f}: {e}')
        sys.exit(1)
print('✅ Syntakssjekk OK')
" 2>&1 || {
    VERIFY_OK=false
    log "❌ Syntaksfeil oppdaget! Ruller tilbake..."
}

# ── Rollback ved feil ─────────────────────────────────────────────────
if [ "$VERIFY_OK" = false ]; then
    log "⏪ Ruller tilbake til ${ROLLBACK_COMMIT:0:8}..."
    git checkout "$ROLLBACK_COMMIT" 2>&1
    git stash pop 2>/dev/null || true
    log_json "rollback" "Oppdatering feilet - rullet tilbake"
    exit 1
fi

# ── Restart tjenester ─────────────────────────────────────────────────
log "🔄 Restarter tjenester..."
for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        log "   Restarter ${svc}..."
        sudo systemctl restart "$svc" 2>&1 || {
            log "⚠️  Kunne ikke restarte ${svc}"
        }
    fi
done

# Vent og sjekk at tjenestene startet OK
sleep 5
ALL_OK=true
for svc in "${SERVICES[@]}"; do
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        if ! systemctl is-active --quiet "$svc" 2>/dev/null; then
            log "❌ ${svc} startet ikke etter oppdatering!"
            ALL_OK=false
        fi
    fi
done

if [ "$ALL_OK" = false ]; then
    log "⏪ Tjenester feilet! Ruller tilbake..."
    git checkout "$ROLLBACK_COMMIT" 2>&1
    for svc in "${SERVICES[@]}"; do
        sudo systemctl restart "$svc" 2>/dev/null || true
    done
    log_json "rollback" "Tjenester feilet etter oppdatering - rullet tilbake"
    exit 1
fi

# ── Oppdater versjonsfil ──────────────────────────────────────────────
echo "$LATEST_VERSION" > "$VERSION_FILE"

# ── Skriv status ──────────────────────────────────────────────────────
log "✅ Oppdatering fullført: v${CURRENT_VERSION} → v${LATEST_VERSION}"
log_json "updated" "Oppdatert fra v${CURRENT_VERSION} til v${LATEST_VERSION}. ${RELEASE_NOTES}"

# Pop stash hvis vi lagret noe
git stash pop 2>/dev/null || true

log "🦆 Kvakk! Anda er oppdatert!"
