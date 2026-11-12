# Deploying ocrdocflow.qumaxa.com

OCRDocFlow shares the same droplet as the AR Automation Console
(`console.qumaxa.com`) and, deliberately, its **existing nginx/certbot
setup** rather than running a second nginx — see
`../../console/deploy/DEPLOY.md` for how that was originally set up.

Database is **Neon** (managed Postgres), not a container here — there's
no `db` service in this `docker-compose.yml`.

## Prerequisites

- DNS: `ocrdocflow.qumaxa.com` A record pointing at the droplet's IP
  (same registrar step as the Console's DEPLOY.md, just a different
  subdomain). Verify with `nslookup ocrdocflow.qumaxa.com` before step 4.
- `backend/.env` filled in (`DATABASE_URL` = Neon connection string,
  a real `JWT_SECRET_KEY`, `FRONTEND_URL=https://ocrdocflow.qumaxa.com`).
- Neon database already has the schema applied and Alembic stamped at
  head (done once, from a dev machine — see `../README.md`).
- Frontend built for production: `cd ../frontend && npm run build`
  (uses `.env.production`'s `VITE_API_BASE_URL=` so the built app calls
  same-origin `/api/...`, proxied by nginx — no CORS needed in prod).

## 1. Copy the project to the droplet

```bash
scp -r D:\Projects\ocrdocflow user@<vps-ip>:/opt/ocrdocflow
```

## 2. Start the API container on the Console's shared network

```bash
cd /opt/ocrdocflow/deploy
docker compose up -d --build
```

This joins the existing `deploy_default` network (created by the
Console's compose project) rather than creating its own nginx or
publishing port 8000 to the public host - only the Console's nginx
container can reach it, by container name (`ocrdocflow-api`).

## 3. Wire the Console's nginx to serve OCRDocFlow too

```bash
# HTTP-only server block (ACME challenge + redirect)
cp /opt/ocrdocflow/deploy/nginx/ocrdocflow.conf /opt/console/deploy/nginx/

# Built frontend static files, mounted into the shared nginx container
# — add this line to /opt/console/deploy/docker-compose.yml's nginx
# service `volumes:` (alongside the existing ./nginx and certbot mounts):
#   - /opt/ocrdocflow/frontend/dist:/var/www/ocrdocflow:ro

cd /opt/console/deploy
docker compose up -d nginx   # recreates nginx with the new mount + conf
```

## 4. Issue the TLS certificate

Same certbot container, same shared webroot/certs volumes as the
Console's cert - just a different `-d`:

```bash
docker run --rm \
  -v deploy_certbot-webroot:/var/www/certbot \
  -v deploy_certbot-certs:/etc/letsencrypt \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d ocrdocflow.qumaxa.com \
  --email <your-real-email> --agree-tos --no-eff-email
```

## 5. Activate HTTPS

```bash
cd /opt/console/deploy/nginx
mv ocrdocflow-ssl.conf.example ocrdocflow-ssl.conf
cd /opt/console/deploy
docker compose restart nginx
```

Confirm:

```bash
curl https://ocrdocflow.qumaxa.com/api/v1/health
# -> {"status":"ok"}
```

## Renewing the certificate

No extra cron entry needed — the Console's existing monthly `certbot
renew` job (see its DEPLOY.md) renews every certificate it manages,
`ocrdocflow.qumaxa.com` included, and already restarts nginx afterward.

## Password reset email

"Forgot password?" on the login page emails a single-use link that works
for 30 minutes. Sending goes through Resend. Add to the server's
`backend/.env`, then `docker compose up -d` in `deploy/`:

```
RESEND_API_KEY=re_...                       # sending-only key is enough
MAIL_FROM=OCRDocFlow <no-reply@qumaxa.com>  # a domain verified in Resend
FRONTEND_URL=https://ocrdocflow.qumaxa.com  # already set for Stripe
```

Without `RESEND_API_KEY` nothing is emailed; the link is written to the
API log instead, so an operator can still help a locked-out user:

```bash
docker logs --since 30m ocrdocflow-api 2>&1 | grep "Password reset link"
```

## Redeploying after a code change

One command from the dev machine (Git Bash), after committing:

```bash
bash deploy/redeploy.sh
```

It builds the frontend locally, ships the committed code and `dist/` to
`/opt/ocrdocflow`, adds any new OCR / promotion keys the server's
`backend/.env` is missing (copied from the local `.env`), rebuilds the
`ocrdocflow-api` container and checks the live health and plans
endpoints. Override the target with `DEPLOY_HOST=root@<ip>`.

Manual equivalent:

```bash
cd /opt/ocrdocflow/deploy
docker compose up -d --build   # api

cd ../frontend && npm run build   # on the droplet, or scp a fresh dist/
```

`ocrdocflow-api`'s container name is fixed (`container_name:
ocrdocflow-api` in docker-compose.yml) specifically so nginx's
`proxy_pass` target never needs to change across rebuilds.
