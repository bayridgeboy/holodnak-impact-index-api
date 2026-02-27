# Human Impact Index (HII)

HII is a quick, playful impact index that estimates a person’s domain influence from public signals.

The app supports:
- Side-by-side comparison (up to 3 people)
- Evidence-backed score cards
- Industry impact score (`0-100`)
- Totem, Hot Take, Defense bullets, confidence, sources, and alternate matches

## Feedback & Contributions

- Issues: https://github.com/bayridgeboy/holodnak-impact-index-api/issues
- Pull requests: https://github.com/bayridgeboy/holodnak-impact-index-api/pulls

## Tech Stack

- FastAPI backend
- Static frontend (`app/static/index.html`)
- OpenAI Responses API (with web search)
- Docker + Docker Compose
- Nginx + Certbot for HTTPS in production

## Project Structure

- `app/main.py` — API and static app serving
- `app/backends/openai_backend.py` — LLM scoring backend
- `app/prompts_ui.py` — UI scoring prompt/schema
- `app/static/index.html` — frontend UI
- `app/static/seed_people.json` — seed/sample cards
- `docker-compose.yml` — container runtime config
- `deploy/nginx/humanimpactindex.com.conf` — Nginx reverse-proxy config

## Run Locally (Docker)

1. Create `.env` in repo root:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o
```

2. Start service:

```bash
docker-compose up -d --build
```

3. Open:

- `http://localhost` (if port mapping is host `80`)
- or `http://<host>:8000` if you run custom mapping

## Environment Variables

Core:
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default `gpt-4o`)
- `OPENAI_WEB_SEARCH` (default `true`)
- `OPENAI_WEB_SEARCH_REQUIRED` (default `true`)

Security/abuse controls:
- `HII_MAX_REQUEST_BYTES` (default `32768`)
- `HII_RATE_LIMIT_WINDOW_SECONDS` (default `60`)
- `HII_RATE_LIMIT_REQUESTS` (default `30`)

## Production (EC2) with Nginx + Certbot

This repo is set up for Nginx TLS termination in front of Docker.

### 1) Start app on localhost only

`docker-compose.yml` publishes API as:
- `127.0.0.1:8000:8000`

Bring containers up:

```bash
docker-compose up -d --build --force-recreate
```

### 2) Install Nginx + Certbot (Amazon Linux 2023)

```bash
sudo dnf install -y nginx certbot python3-certbot-nginx
```

Enable Nginx on boot:

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 3) Install site config

```bash
sudo cp deploy/nginx/humanimpactindex.com.conf /etc/nginx/conf.d/humanimpactindex.com.conf
sudo nginx -t
sudo systemctl reload nginx
```

### 4) Issue TLS cert and force HTTPS redirect

```bash
sudo certbot --nginx \
  -d humanimpactindex.com \
  -d www.humanimpactindex.com \
  --redirect \
  -m stasholodnak@gmail.com \
  --agree-tos \
  --no-eff-email
```

### 5) Verify

```bash
sudo systemctl is-enabled docker
sudo systemctl is-active docker
sudo systemctl is-enabled nginx
sudo systemctl is-active nginx
```

Open:
- `https://humanimpactindex.com`

### 6) Cert renewal

Check renewal mechanism:

```bash
sudo systemctl status certbot-renew.timer
```

If timer unit is not present on your AMI, use cron fallback:

```bash
( crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'" ) | crontab -
```

## Reboot Behavior

After EC2 reboot, service should recover automatically if:
- Docker is enabled at boot (`systemctl is-enabled docker` = `enabled`)
- Nginx is enabled at boot (`systemctl is-enabled nginx` = `enabled`)
- Containers were created with `restart: unless-stopped`

## Troubleshooting

### Nginx fails with `bind() ... :80 failed (98: Address already in use)`

Port `80` is already used by another process (often Docker host port mapping).

Fix:
1. Ensure Compose binds app to localhost (`127.0.0.1:8000:8000`)
2. Recreate containers:

```bash
docker-compose up -d --build --force-recreate
```

3. Start/restart Nginx:

```bash
sudo systemctl restart nginx
```

### Check who owns ports 80/443/8000

```bash
sudo ss -ltnp | grep ':80\|:443\|:8000' || true
```

## Notes

- Seed/sample cards are in `app/static/seed_people.json`
- Frontend text and styles are in `app/static/index.html`
- Debug panel is hidden in production and can be enabled with `?debug=1`
