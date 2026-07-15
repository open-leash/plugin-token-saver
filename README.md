# plugin-token-saver

Token Saver is OpenLeash's first container plugin. It embeds Headroom as a compression engine; Headroom never receives provider credentials and never acts as the network proxy. OpenLeash `local-proxy` owns provider transport, `client-api` owns plugin ordering and policy, and this container receives signed requests and returns constrained JSON patches.

The versioned response can also request host-mediated `logs`, `usage`, and `signals`. `client-api` checks the installed manifest and effective account setting, enforces each declared permission, sanitizes the payload, and writes through the normal OpenLeash capability implementation. The container never receives Postgres, cloud, provider, or OpenLeash credentials. Stateful CCR content remains in the plugin-scoped `/data` volume and is exposed only through the correlated signed tool API.

## Runtime

- `GET /healthz`
- `POST /v1/transform` using `openleash-container-plugin.v1`
- `POST /v1/tools/execute` for tenant/session-scoped CCR retrieval

The desktop starts the image when the effective account state enables Token Saver. It runs non-root with a read-only root filesystem, dropped capabilities, bounded resources, loopback-only exposure, and a plugin-scoped `/data` volume. OpenLeash Cloud runs the same image as a warm shared first-party worker pool; tenant-dedicated placement remains available for higher-isolation deployments.

## Build

```bash
npm install
npm run typecheck
docker build -t ghcr.io/open-leash/plugin-token-saver:1.1.1 .
docker run --rm -p 127.0.0.1:9331:8080 ghcr.io/open-leash/plugin-token-saver:1.1.1
curl http://127.0.0.1:9331/healthz
```

Production releases must record and deploy the registry digest rather than relying on the human-readable tag.
