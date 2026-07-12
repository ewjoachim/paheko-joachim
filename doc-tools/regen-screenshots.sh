#!/usr/bin/env bash
#
# Regenerates all the guide screenshots (doc/suivi_cheques/screenshots/*.png).
#
# Principle: we DO NOT touch the working data. The working database is backed
# up, a deterministic demo fixture is seeded in its place, screenshots are
# taken, then the working database is restored (even on error, via `trap`).
#
# Requirements:
#   - the Paheko test instance is running (podman, see paheko-test/), served on $BASE_URL
#   - uv (Playwright is pulled on the fly via `uv run --with playwright`)
#
# Usage:
#   cd doc-tools && ./regen-screenshots.sh
#
# Optional variables: CONTAINER (default paheko-test), BASE_URL (default http://localhost:8080)

set -euo pipefail
cd "$(dirname "$0")"

CONTAINER="${CONTAINER:-paheko-test}"
export BASE_URL="${BASE_URL:-http://localhost:8080}"

DB=/var/www/paheko/data/association.sqlite
BK=/var/www/paheko/data/association.regen-backup.sqlite
CACHE=/var/www/paheko/data/cache

echo "==> Backing up the working database"
podman exec "$CONTAINER" cp "$DB" "$BK"

restore() {
	echo "==> Restoring the working database"
	podman exec "$CONTAINER" sh -c "cp '$BK' '$DB' && rm -f '$BK' && rm -rf '$CACHE'/* 2>/dev/null || true"
}
trap restore EXIT

echo "==> Installing the Playwright browser if needed"
uv run playwright install chromium >/dev/null

echo "==> Seeding the demo fixture"
SEED_OUT="$(podman exec -i "$CONTAINER" php < seed-demo.php)"
echo "$SEED_OUT" | tail -1
podman exec "$CONTAINER" sh -c "rm -rf '$CACHE'/* 2>/dev/null || true"

# Pick up the credentials / ids produced by the seed
# (declare then export separately so a failing command substitution isn't masked
# by export's own exit status — shellcheck SC2155)
ADMIN_EMAIL="$(printf '%s\n' "$SEED_OUT" | sed -n 's/^ADMIN_EMAIL=//p')"
ADMIN_PASSWORD="$(printf '%s\n' "$SEED_OUT" | sed -n 's/^ADMIN_PASSWORD=//p')"
CAMILLE_ID="$(printf '%s\n' "$SEED_OUT" | sed -n 's/^CAMILLE_ID=//p')"
PAY_EDIT="$(printf '%s\n' "$SEED_OUT" | sed -n 's/^PAY_EDIT=//p')"
export ADMIN_EMAIL ADMIN_PASSWORD CAMILLE_ID PAY_EDIT

echo "==> Screenshots (Playwright)"
uv run python screenshots.py

echo "==> Done. Screenshots in doc/suivi_cheques/screenshots/"
