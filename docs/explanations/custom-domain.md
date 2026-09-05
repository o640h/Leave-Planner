# Custom Domain Cutover

Preparation only: no domain has been selected. The working Tailscale Funnel remains unchanged.
The NAS continues hosting both the application and database; Cloudflare supplies the public HTTPS
entry point through an outbound connector. No router forwarding, DMZ, Web Station or public
PostgreSQL port is needed.

## Operator checkpoints

1. Choose and purchase the domain. Add it to your existing Cloudflare account on the Free plan and
   complete the assigned nameserver setup if purchased elsewhere. Wait for an Active zone. Keep
   existing email/DNS records if this is not a brand-new domain. Enable account MFA. Tell the
   developer the exact app hostname (for example `app.example.com`), not credentials.
2. Create a remotely managed Cloudflare Tunnel in the dashboard (Networking / Tunnels, or Zero
   Trust / Networks / Connectors). Give it a descriptive name. The Docker installation command
   contains a secret token: do not paste it into chat, Git, `.env.example`, or shell history.
   Save only the token in `deploy/secrets/cloudflare_tunnel_token.txt` on the NAS. Restrict the
   parent secrets directory to administrators; the bind-mounted token must remain readable by
   container UID 65532. Do not recursively change permissions of existing database secrets.
3. Select and pin the connector image on the NAS. Pull the current official image, inspect its
   immutable digest, and put that value in the real `deploy/.env`:

```sh
sudo docker pull cloudflare/cloudflared:latest
sudo docker image inspect cloudflare/cloudflared:latest --format '{{index .RepoDigests 0}}'
```

```dotenv
CLOUDFLARED_IMAGE=cloudflare/cloudflared@sha256:REPLACE_WITH_INSPECTED_DIGEST
```

The token-file option requires cloudflared 2025.4.0 or later. Retain the tested digest for rollback.
This inspection step intentionally avoids guessing a future image tag or silently updating on restart.
4. Add a published application route for your chosen hostname, service **HTTP**, URL
   **application:8000**. Leave the HTTP Host Header override unset so the real public hostname
   reaches the application's host/origin validation. Do not route DSM, SSH, the database, or other
   NAS services. Ensure no cache-everything rule applies; bypass caching for `/api/*` and do not
   enable HTML/script transformations during initial acceptance.
5. At a planned short cutover, change only the real `.env` public origin to the exact new HTTPS
   origin, with no path or trailing slash. Keep the loopback bind address. The application derives
   allowed host and CSRF origin from this setting; do not weaken those checks for two public hosts.
   Existing login cookies do not transfer to the new hostname: sign in again.

```sh
# NAS SSH, in /volume1/docker/leave-planner/deploy
sudo docker compose up -d --no-deps application
sudo docker compose -f compose.yml -f compose.cloudflare.yml up -d --no-deps tunnel
sudo docker compose -f compose.yml -f compose.cloudflare.yml logs --tail=50 tunnel
```

## Acceptance before retiring Funnel

- Confirm the tunnel reports healthy in Cloudflare and the public certificate is trusted.
- Open `https://YOUR-HOST/api/health` from an external network/checker; expect production/ok.
- Sign in through the browser, navigate Consultants, Planning and Settings, and test an authorised
  PDF download. Confirm unauthenticated downloads remain denied.
- Check security headers, Secure/HttpOnly/SameSite session cookies and exact-origin rejection.
  Check that two independent clients do not share a proxy-wide login rate-limit identity.
- Check the origin cannot be reached publicly on 8000/8080 and PostgreSQL is still unpublished.
- Confirm an ordinary connector/container restart recovers the public route; no NAS reboot needed.

Only then disable the public Funnel on the NAS:

```sh
sudo /var/packages/Tailscale/target/bin/tailscale funnel --https=443 off
```

Keep private Tailscale administration if useful. For subsequent project-wide Compose operations,
include both `-f` files so the connector is managed with the application. A health check alone does
not provide alerts: configure tunnel availability notifications/monitoring and test delivery.

Rollback: stop the tunnel service, restore the previous exact public origin in `.env`, recreate
the application, and re-enable `tailscale funnel --bg 8080`. Verify the original URL before changing
DNS further. None of these routing commands changes the PostgreSQL volume.

Sources: [Cloudflare setup](https://developers.cloudflare.com/tunnel/setup/) and
[token-file parameters](https://developers.cloudflare.com/tunnel/advanced/run-parameters/).
