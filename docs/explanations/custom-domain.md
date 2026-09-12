# Custom Domain and Cloudflare Tunnel

The production application is available at `https://app.merydio.co.uk`. Cloudflare terminates public
HTTPS and sends requests through an outbound `cloudflared` connector on the NAS to
`http://application:8000`. The application and PostgreSQL remain on the NAS; no router forwarding,
DMZ, Web Station, public application port, or public PostgreSQL port is required.

## Production configuration

- Cloudflare is authoritative for `merydio.co.uk`.
- The published application route is `app.merydio.co.uk` to HTTP service `application:8000`.
- `deploy/.env` uses `LEAVE_PLANNER_PUBLIC_ORIGIN=https://app.merydio.co.uk`.
- The tunnel token belongs only in `deploy/secrets/cloudflare_tunnel_token.txt` on the NAS. Never put
  it in chat, Git, screenshots, `.env`, or shell history.
- `compose.cloudflare.yml` is an overlay, so project-wide commands include both Compose files.

Cloudflare-to-browser traffic is HTTPS. HTTP on the private Docker hop is intentional: both
containers share the NAS-only edge network, and the application is not published on that network to
the internet. Cloudflare forwards the original HTTPS scheme and hostname for the application's
origin, cookie, redirect, and host checks.

## Manage the connector

Pin the tested official connector image by immutable digest in the real `deploy/.env`:

```dotenv
CLOUDFLARED_IMAGE=cloudflare/cloudflared@sha256:REPLACE_WITH_INSPECTED_DIGEST
```

Start and inspect the Compose-managed connector from NAS SSH:

```sh
cd /volume1/docker/leave-planner/deploy
sudo docker compose -f compose.yml -f compose.cloudflare.yml up -d --no-deps tunnel
sudo docker compose -f compose.yml -f compose.cloudflare.yml logs --tail=50 tunnel
```

For later full releases, retain both `-f` arguments so `tunnel` remains part of the project. A healthy
connector should register multiple Cloudflare connections and the public health endpoint should
return `status: ok` and `environment: production`.

## Root-domain holding route

Until there is a real marketing site, redirect `merydio.co.uk` and `www.merydio.co.uk` to the app.
In Cloudflare, create one Redirect Rule matching either hostname, with static destination
`https://app.merydio.co.uk`, status `302`, and query-string preservation enabled. Keep both DNS
records proxied. Use `302` while this is a holding route; change it to `301` only when the decision is
permanent. Do not remove mail records when changing website DNS.

## Retire the Tailscale proof of concept

Only after the Compose-managed connector is healthy and the application works over an external
connection:

```sh
sudo /var/packages/Tailscale/target/bin/tailscale funnel --https=443 off
sudo /var/packages/Tailscale/target/bin/tailscale funnel status
```

Disable the old daily Tailscale update task in DSM Task Scheduler. If Tailscale is not needed for
private NAS administration, uninstall the DSM package and remove the NAS machine from the Tailscale
admin console. These steps do not affect Cloudflare Tunnel or PostgreSQL.

Remove only confirmed obsolete containers. The stopped random-name `cloudflared` container and the
disposable PostgreSQL test container can be removed; do not remove volumes. The exited migration
container is normal evidence of the one-shot release step and may remain. Never use a broad Docker
volume or system prune on this NAS.

## Acceptance and rollback

- Test `/api/health`, sign-in, Consultants, Planning, Settings, and an authorised PDF download from
  a non-LAN connection.
- Confirm unauthenticated downloads are denied, session cookies are Secure/HttpOnly/SameSite, and
  the application rejects an unexpected Host or Origin.
- Confirm PostgreSQL has no published port and neither DSM nor SSH is routed through the tunnel.
- Confirm a connector restart recovers the route.

If the Cloudflare route fails, inspect the application and tunnel logs before changing DNS. Restart
the last tested application image if the failure followed a release. Re-enabling the old Funnel is an
emergency rollback only while Tailscale remains installed; none of these routing actions changes the
PostgreSQL volume.

Sources: [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/setup/) and
[Cloudflare Redirect Rules](https://developers.cloudflare.com/rules/url-forwarding/).
