# Dragonwilds Control

Static control panel for a self-hosted RuneScape: Dragonwilds dedicated server.

The page is **just a frontend** — it talks to a small Python API running on the
home server, exposed over HTTPS via Tailscale Funnel. All state stays on the home
server; this site is purely a UI.

## How it's wired

```
[GitHub Pages: this repo] ──HTTPS+token──► [Tailscale Funnel] ──► [API @ localhost:8765] ──► systemctl
```

## Security

- The page contains **no secrets**. The API URL and bearer token are entered at
  login and stored in your browser's `localStorage` (per-device).
- The API requires `Authorization: Bearer <token>` on every endpoint.
- The API binds to `127.0.0.1` only and is reached over HTTPS via Tailscale Funnel.
- The server-side `sudo` rules are locked to **only**
  `systemctl start|stop|restart dragonwilds.service`, nothing else.
- Rate-limited at 60 req/min per source IP.
- CORS allows only the GitHub Pages origin.

## Setup (server-side, already done)

```
/home/moha/dragonwilds-api/api.py        # the API
/home/moha/dragonwilds-api/token         # 256-bit random token (chmod 600)
/etc/sudoers.d/dragonwilds-api           # passwordless sudo, locked to specific commands
/etc/systemd/system/dragonwilds-api.service
tailscale funnel --bg 8765               # public HTTPS on moha-eos.<tailnet>.ts.net
```

## Local development

```
cd dragonwilds-control
python -m http.server 5500
# open http://localhost:5500
```
