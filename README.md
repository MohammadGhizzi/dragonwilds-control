# Palworld Control

Static GitHub Pages frontend for the self-hosted Palworld dedicated server on `moha-eos`.

The frontend stores no secrets in git. It asks for:

- API URL: `https://moha-eos.tailb7a05f.ts.net`
- Bearer token: stored on the server at `/home/moha/palworld-api/token`

Backend services on `moha-eos`:

- `palworld.service` - Docker Compose wrapper for the official Palworld dedicated server image.
- `palworld-api.service` - local control API bound to `127.0.0.1:8765`.
- `palworld-backup.timer` - daily backup of `/home/moha/palworld/Saved`.

The public API URL is exposed through Tailscale Funnel and protected by the API token.
