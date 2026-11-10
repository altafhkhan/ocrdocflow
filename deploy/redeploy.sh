#!/usr/bin/env bash
# Redeploy OCRDocFlow to the droplet: current git HEAD + a fresh frontend
# build. Run from a Git Bash / WSL shell on the dev machine:
#
#     bash deploy/redeploy.sh
#
# What it does (see DEPLOY.md for the one-time setup it assumes):
#   1. builds the frontend locally (frontend/dist, using .env.production)
#   2. ships the committed code to /opt/ocrdocflow with `git archive`
#      (untracked files such as backend/.env and uploads are NOT touched)
#   3. ships frontend/dist, which the shared nginx serves from that path
#   4. appends to the SERVER's backend/.env any OCR/promotion settings it
#      does not have yet, copied from the local backend/.env; existing
#      server values (DATABASE_URL, Stripe keys, ...) are never changed
#   5. rebuilds + restarts the ocrdocflow-api container
#   6. checks the health endpoint and the plans endpoint on the live site
#
# No database migration step: the schema is managed outside this script
# (see DEPLOY.md); this release needs no schema change.
set -euo pipefail

HOST="${DEPLOY_HOST:-root@165.22.240.27}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/ocrdocflow}"
SITE_HOST="ocrdocflow.qumaxa.com"
SITE_IP="${HOST##*@}"

SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST")

cd "$(dirname "$0")/.."

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "!! You have uncommitted changes. Only COMMITTED code (HEAD) is deployed." >&2
fi
echo "Deploying $(git rev-parse --short HEAD) ($(git log -1 --pretty=%s)) to $HOST:$REMOTE_DIR"

echo "== 1/6 building frontend"
(cd frontend && npm run build)

echo "== 2/6 shipping code"
git archive --format=tar HEAD | "${SSH[@]}" "mkdir -p '$REMOTE_DIR' && tar -x -C '$REMOTE_DIR' -f -"

echo "== 3/6 shipping frontend/dist"
# The shared nginx bind-mounts $REMOTE_DIR/frontend/dist. Deleting and
# recreating that directory breaks the mount (nginx then serves 500s until
# restarted), so replace its CONTENTS in place instead, and give the files
# to root (tar would keep the Windows uid they were built under).
tar -C frontend -cf - dist | "${SSH[@]}" "
  set -e
  mkdir -p '$REMOTE_DIR/frontend/dist'
  tmp=\$(mktemp -d)
  tar -x -C \"\$tmp\" -f -
  find '$REMOTE_DIR/frontend/dist' -mindepth 1 -delete
  cp -a \"\$tmp/dist/.\" '$REMOTE_DIR/frontend/dist/'
  chown -R root:root '$REMOTE_DIR/frontend/dist'
  rm -rf \"\$tmp\"
"

echo "== 4/6 settings"
# Keys the new code needs. Values come from the local backend/.env; only
# keys MISSING on the server are appended (sent over the SSH channel, not
# on a command line).
WANTED=(OCR_PROVIDER OCR_FALLBACK_TO_PADDLE GEMINI_API_KEY GEMINI_MODEL GEMINI_FALLBACK_MODELS
        PROMO_ENABLED PROMO_NAME PROMO_PERCENT_OFF PROMO_MAX_REDEMPTIONS PROMO_DURATION)
existing=$("${SSH[@]}" "cut -d= -f1 '$REMOTE_DIR/backend/.env'")
missing_lines=""
for k in "${WANTED[@]}"; do
  if ! grep -qx "$k" <<<"$existing"; then
    line=$(grep -E "^$k=" backend/.env | head -1 || true)
    if [ -n "$line" ]; then
      missing_lines+="$line"$'\n'
      echo "   adding $k"
    fi
  fi
done
if [ -n "$missing_lines" ]; then
  printf '\n# --- added by deploy/redeploy.sh %s ---\n%s' "$(date -u +%Y-%m-%d)" "$missing_lines" \
    | "${SSH[@]}" "cat >> '$REMOTE_DIR/backend/.env'"
else
  echo "   server .env already has every key"
fi

echo "== 5/6 rebuilding API container"
"${SSH[@]}" "cd '$REMOTE_DIR/deploy' && docker compose up -d --build && docker image prune -f >/dev/null && sleep 5 && docker ps --format '{{.Names}}  {{.Status}}' | grep ocrdocflow && docker logs --tail 5 ocrdocflow-api 2>&1 | tail -5"

echo "== 6/6 verifying live site (via $SITE_IP, in case DNS caches are stale)"
# Informational only: a failed check must not abort the script (set -e).
curl -sS --resolve "$SITE_HOST:443:$SITE_IP" "https://$SITE_HOST/api/v1/health" || true; echo
curl -sS --resolve "$SITE_HOST:443:$SITE_IP" "https://$SITE_HOST/api/v1/billing/plans" | head -c 300 || true; echo
curl -sS --resolve "$SITE_HOST:443:$SITE_IP" "https://$SITE_HOST/" | grep -o 'src="[^"]*\.js"' | head -1 || true
echo "Done. Open https://$SITE_HOST and check: language dropdown (11 entries), Billing page offer, review split view."
