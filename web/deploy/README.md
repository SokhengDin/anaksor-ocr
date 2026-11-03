# Deploying the website

A push to `master` that touches `web/` runs the `web` workflow: lint, typecheck, the browser smoke test, a
production build and a dependency scan. When they pass, the `deploy` job SSHes into the server with a key that
can run only `/usr/local/bin/anaksor-site-deploy` (`deploy.sh`). That script:

1. fetches `master` from the public repo and checks the commit is on it;
2. builds the image `anaksor-web:<sha>` from a clean export of `web/` at that commit (`Dockerfile`: Bun builds
   the static site, the unprivileged nginx image serves it);
3. checks the new image (`nginx -t`, `index.html` present) before touching the live site;
4. swaps the `anaksor-web` container to it (`docker compose up --wait`) and waits for its health check. If the
   new one doesn't become healthy, it goes back to the previous image by itself.

The container publishes `127.0.0.1:8088`, and the Cloudflare tunnel publishes that as ocr.sokhengdin.dev. To
roll back, re-run an older workflow run: the last 5 images are kept, so it needs no rebuild.

## Setup (once)

1. The CI key: the existing `ci_deploy` key (as for my-website) or a new one
   (`ssh-keygen -t ed25519 -N '' -C github-actions-site-deploy -f ci_site_deploy`).
2. On the server: Docker with the compose and buildx plugins, and `systemctl enable docker` (so the container
   comes back after a reboot).
3. From `web/deploy` in a checkout of the repo, with the **public** half of the key:
   `sudo ./install.sh --ci-key ci_deploy.pub --sshd`
   It makes the `anaksor-deploy` user, a bare mirror of the repo, the gate, a root-owned copy of
   `docker-compose.yml` in `/etc/anaksor-web/`, and prints the host key line for step 5. `--port 8089` publishes
   another port than 8088.
4. In the Cloudflare dashboard, add a route to the tunnel: `ocr.sokhengdin.dev` → `http://localhost:8088`.
5. GitHub > anaksor-ocr > Settings > Environments: create `production`, deployment branches: `master` only
   (a required reviewer is optional). Add these **environment** secrets (not repository secrets):

   | Secret | Value |
   | --- | --- |
   | `DEPLOY_SSH_KEY` | the private key (`gh secret set DEPLOY_SSH_KEY --env production < ~/.ssh/ci_deploy`) |
   | `DEPLOY_HOST` | the server's SSH address, as for my-website (not the Cloudflare-proxied name) |
   | `DEPLOY_PORT` | SSH port (empty = 22) |
   | `DEPLOY_USER` | `anaksor-deploy` |
   | `DEPLOY_KNOWN_HOSTS` | the host key line `install.sh` printed, with your host in front (`[host]:port` if not 22) |

6. The first deploy: push to `master`, re-run the latest `web` run, or on the server
   `sudo -u anaksor-deploy SSH_ORIGINAL_COMMAND="deploy <sha on master>" /usr/local/bin/anaksor-site-deploy`.

Moving from the earlier Bun-on-the-host setup: run `install.sh` again (it says so if the old host nginx site is
still there), then remove that site (`/etc/nginx/sites-enabled/anaksor-site`, `sites-available/anaksor-site`,
reload nginx) and `/srv/anaksor-site`. The port and the Cloudflare route stay the same.

## Because the repository is public

- **Fork pull requests run the checks only.** They get a read-only token and no secrets, and the deploy job
  requires a push to `master` in the `production` environment. Never add `pull_request_target` workflows.
- In Settings > Actions > General: *Fork pull request workflows*: require approval for all outside
  collaborators; *Workflow permissions*: read repository contents only.
- Protect `master` (no force pushes, PRs before merging): whoever can push to `master` can deploy.
- Actions are pinned to commit SHAs, the osv-scanner download is checked against its published SHA-256, and
  the base images are pinned by digest.

## What keeps the server safe

- The CI key is `restrict,command=…` in a root-owned `authorized_keys`: no shell, no TTY, no forwarding. With
  `--sshd`, sshd also forces the same command for that user and allows keys only.
- The gate accepts only `deploy <40-hex sha>` or `status`, and deploys only commits on `master`, fetched by the
  server itself. CI can't send files or commands, only name a commit.
- The repo is read over HTTPS: there is no GitHub key on the server to steal.
- `anaksor-deploy` is in the `docker` group (like my-website's deploy user), which is root-equivalent, so the
  only way in is the gate above. It has no password and no sudo.
- The build runs inside BuildKit's sandbox, not on the host: `bun install --frozen-lockfile --ignore-scripts`
  (exact locked versions, no install scripts) and `next build` can't see the host, its files or other containers.
- How the container runs comes from `/etc/anaksor-web/docker-compose.yml`, installed by root, never from a
  commit: a commit can change what the site serves, not its ports, mounts or privileges.
- The container: nginx as user 101, read-only filesystem (only a small `/tmp` tmpfs), all capabilities dropped,
  `no-new-privileges`, 128 MB and 64 processes at most, published on localhost only. nginx answers GET and HEAD
  only and sends the security headers (CSP allowing only its own files and `https://ocr-api.sokhengdin.dev`).
  Nothing here accepts uploads: those go to the OCR API.
- Deploys hold a lock and run detached: a cancelled job or a dropped connection never stops one halfway, and the
  live container is only replaced by an image that passed its checks.

## Server commands

- Status: `sudo -u anaksor-deploy SSH_ORIGINAL_COMMAND=status /usr/local/bin/anaksor-site-deploy`
- Container: `docker ps --filter name=anaksor-web`, logs: `docker logs anaksor-web`
- Deploy logs: `/var/lib/anaksor-site-deploy/logs/` (kept 30 days).
- Other API or site address, port, or images kept: `API_URL=`, `SITE_URL=`, `WEB_PORT=`, `KEEP=` in
  `/etc/anaksor-site-deploy.conf` (root-owned; `install.sh` keeps them when run again).
- Server-only changes to the container go in `/etc/anaksor-web/docker-compose.override.yml` (root-owned,
  mode 644): every deploy applies it and `install.sh` never touches it. To join the network cloudflared runs
  on, so the tunnel can use `http://anaksor-web:8080`:
  ```yaml
  services:
    web:
      networks: [default, alpha_network]
  networks:
    alpha_network:
      external: true
  ```
- After editing `deploy.sh` or `docker-compose.yml`, run `install.sh` again: a commit can't change the
  installed copies.
