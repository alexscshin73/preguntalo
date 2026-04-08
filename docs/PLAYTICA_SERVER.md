# Playtica Server Deployment

This flow moves `preguntalo.carroamix.com` off the local Mac and onto the Playtica server.

## Target Runtime

- API: user-space `uvicorn` on `127.0.0.1:8010`
- Web: Next.js production server on `127.0.0.1:3000`
- Public hostname: `https://preguntalo.carroamix.com`
- Tunnel: Cloudflare named tunnel terminating at `http://127.0.0.1:3000`
- Persistence: `crontab @reboot` + `preguntalo_playtica_public_supervisor.sh`

## Server Assumptions

- repo path: `/home/scshin/projects/preguntalo`
- user: `scshin`
- SSH alias: `playtica`
- tunnel token file: `/home/scshin/.config/preguntalo/cloudflare.token`
- database file: `/home/scshin/projects/preguntalo/apps/api/preguntalo-dev.db`
- file storage root: `/home/scshin/projects/preguntalo/apps/api/data/storage`

## Install Runtime

From the repo root on Playtica:

```bash
bash scripts/install_playtica_runtime.sh
```

This installs:

- API Python packages into the user site-packages
- Node.js into `~/.local/bin`
- npm workspace dependencies for the web app
- `cloudflared` into `~/.local/bin`

## Copy Current Mac Data

Sync the current Mac runtime state before cutover:

```bash
rsync -av apps/api/preguntalo-dev.db playtica:~/projects/preguntalo/apps/api/
rsync -av apps/api/data/storage/ playtica:~/projects/preguntalo/apps/api/data/storage/
```

## Prepare Env And Tunnel Token

```bash
cp .env.playtica.example .env.playtica
mkdir -p ~/.config/preguntalo
chmod 700 ~/.config/preguntalo
printf '%s' 'YOUR_CLOUDFLARE_TUNNEL_TOKEN' > ~/.config/preguntalo/cloudflare.token
chmod 600 ~/.config/preguntalo/cloudflare.token
```

## Start Public Service

```bash
bash scripts/preguntalo_playtica_public_start.sh
```

## Keep It Running Across Reboots

```bash
bash scripts/install_playtica_cron.sh
nohup bash scripts/preguntalo_playtica_public_supervisor.sh >> run/supervisor.log 2>&1 &
```

## Verify Cutover

1. `curl -s https://preguntalo.carroamix.com/api/proxy/api/v1/health`
2. `curl -s https://preguntalo.carroamix.com/api/proxy/api/v1/manuals`
3. stop the Mac-side `preguntalo` launch agent
4. verify the public site still responds
