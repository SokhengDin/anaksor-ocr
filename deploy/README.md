# Deploy

A push to `master` runs CI (`.github/workflows/ci.yml`). When every job passes, the `deploy` job SSHes into the
server with a key that can run only `/usr/local/bin/anaksor-deploy` (`deploy.sh`). That script fetches the
commit with a read-only GitHub deploy key, checks it is on `master`, checks it out, builds the website image and
runs `docker compose up -d --wait` in `web/`. There are no migrations. To roll back, re-run an older workflow run.

The `anaksor-web` container joins the external Docker network `proxy_network`; the reverse proxy on that network
reaches it as `http://anaksor-web:8080`. It also publishes `127.0.0.1:8088` (`BIND_ADDRESS`, `WEB_PORT` in
`web/.env`). The browser calls the OCR API at its public address (`NEXT_PUBLIC_API_URL`); the site makes no
server-side calls to other containers.

## Setup (once)

1. On the server: Docker with the compose plugin, `systemctl enable docker`, and the network:
   `docker network create proxy_network` (once per server).
2. On your machine, the CI key's public half: `ssh-keygen -y -f ~/.ssh/ci_deploy > ci_deploy.pub`
   (or a new key: `ssh-keygen -t ed25519 -N '' -C github-actions-deploy -f ci_deploy`). Copy it to the server.
3. From `deploy/` in the checkout, run:
   `sudo ./install.sh --ci-key ci_deploy.pub --dir <checkout> --sshd`
   - It prints a read-only key. Add it in GitHub > anaksor-ocr > Settings > Deploy keys, with write access off.
     Then run the same command again.
   - An existing checkout must be owned by the deploy user: `sudo chown -R deploy: <checkout>`. Under a home
     directory, the deploy user also needs to pass through it: `sudo setfacl -m u:deploy:x /home/<user>`.
   - It keeps the compose project of the running `anaksor-web` container, so the first deploy replaces it.
   - It refuses a user that already serves another gate (e.g. my-website's `deploy` on the same server): use
     `--user anaksor-deploy` there.
   - The production settings go in `<checkout>/web/.env` (optional; owner deploy, mode 600).
4. In GitHub > Settings > Environments, create `production`. Restrict it to `master`. Add these secrets:

   | Secret | Value |
   | --- | --- |
   | `DEPLOY_SSH_KEY` | the private CI key (`gh secret set DEPLOY_SSH_KEY --env production < ~/.ssh/ci_deploy`) |
   | `DEPLOY_HOST` | the server's real IP or hostname (not the Cloudflare-proxied one) |
   | `DEPLOY_PORT` | SSH port (empty = 22) |
   | `DEPLOY_USER` | `deploy` (or the `--user` you chose) |
   | `DEPLOY_KNOWN_HOSTS` | `ssh-keyscan -t ed25519 -p <port> <DEPLOY_HOST>`, exactly that host; `[host]:port` if not 22 |

5. Protect `master` (no force pushes): whoever can push there can deploy.

## Server commands

- `sudo -u deploy SSH_ORIGINAL_COMMAND=status /usr/local/bin/anaksor-deploy`
- `sudo -u deploy SSH_ORIGINAL_COMMAND="deploy <sha on master>" /usr/local/bin/anaksor-deploy`
- Logs: `/var/lib/anaksor-deploy/logs/` (kept 30 days). Container: `docker logs anaksor-web`.
- After editing `deploy.sh`, run `install.sh` again. A commit cannot change the installed copy.

## What keeps it safe

- The CI key is `restrict,command=…` in a root-owned `authorized_keys`: no shell, no TTY, no forwarding. With
  `--sshd`, sshd also forces the same command for that user.
- The gate accepts only `deploy <40-hex sha>` or `status`. It deploys only commits on `master`, never anything
  sent over SSH.
- The server reads GitHub with its own key: read-only, this repo only, GitHub's host key pinned.
- The deploy user has no password. It is in the `docker` group, which is root-equivalent, so it must never get
  any other key.
- Deploys hold a lock and run detached: a cancelled job or a dropped connection never stops one halfway.
- Fork pull requests run the checks only: no secrets, read-only token. Never add `pull_request_target` workflows.
