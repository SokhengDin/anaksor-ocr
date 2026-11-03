#!/usr/bin/env bash
# sudo ./install.sh --ci-key ci_deploy.pub [--user anaksor-deploy] [--port 8088] [--sshd]
# Run again after changing deploy.sh or docker-compose.yml: a commit cannot change the installed copies.
set -euo pipefail
umask 022

STATE_DIR=/var/lib/anaksor-site-deploy
DEPLOY_USER=anaksor-deploy
BRANCH=main
REPO_URL=https://github.com/SokhengDin/anaksor-ocr.git
WEB_PORT=8088
PORT_SET=0
CI_KEY=
SSHD=0
HERE=$(cd "$(dirname "$0")" && pwd)
CONF=/etc/anaksor-site-deploy.conf

die() { echo "error: $*" >&2; exit 1; }
say() { printf '\n-- %s\n' "$*"; }

while (($#)); do
  case $1 in
    --user) DEPLOY_USER=$2; shift 2 ;;
    --port) WEB_PORT=$2; PORT_SET=1; shift 2 ;;
    --ci-key) CI_KEY=$2; shift 2 ;;
    --sshd) SSHD=1; shift ;;
    *) die "unknown option $1" ;;
  esac
done

((EUID == 0)) || die "run as root (sudo)"
for c in git docker flock setsid ssh-keygen stat tar find; do command -v "$c" >/dev/null || die "$c is not installed"; done
docker compose version >/dev/null 2>&1 || die "docker compose v2 is not installed"
docker buildx version >/dev/null 2>&1 || die "docker buildx (BuildKit) is not installed"
[[ $DEPLOY_USER =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "bad user name"
[[ $WEB_PORT =~ ^[0-9]{2,5}$ ]] || die "bad --port"
[[ -f $HERE/../docker-compose.yml ]] || die "run this from web/deploy in a checkout (needs ../docker-compose.yml)"

# Keep settings someone already changed in the conf (API_URL, SITE_URL, BIND_ADDRESS, WEB_PORT, KEEP).
API_URL=''
SITE_URL=''
BIND_ADDRESS=127.0.0.1
KEEP=5
if [[ -f $CONF ]]; then
  for k in API_URL SITE_URL BIND_ADDRESS KEEP; do
    v=$(sed -n "s/^$k=//p" "$CONF" | tail -1)
    [[ -n $v ]] && printf -v "$k" '%s' "$v"
  done
  ((PORT_SET)) || { v=$(sed -n 's/^WEB_PORT=//p' "$CONF" | tail -1); [[ -n $v ]] && WEB_PORT=$v; }
fi

say "user $DEPLOY_USER (no password, no sudo; in the docker group to build and run anaksor-web)"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "$DEPLOY_USER"
fi
passwd -l "$DEPLOY_USER" >/dev/null
id -nG "$DEPLOY_USER" | grep -qwE 'sudo|wheel|adm' && die "$DEPLOY_USER is in an admin group; use a fresh user"
usermod -aG docker "$DEPLOY_USER"
HOME_DIR=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)

say "state $STATE_DIR"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0750 "$STATE_DIR" "$STATE_DIR/logs" "$STATE_DIR/build"
if [[ ! -d $STATE_DIR/repo.git ]]; then
  runuser -u "$DEPLOY_USER" -- env GIT_TERMINAL_PROMPT=0 git clone --quiet --bare --single-branch --branch "$BRANCH" "$REPO_URL" "$STATE_DIR/repo.git"
fi
rm -rf "${STATE_DIR:?}/home" "${STATE_DIR:?}/bun-cache"   # left over from the Bun-on-the-host version

say "gate /usr/local/bin/anaksor-site-deploy, compose file /etc/anaksor-web/docker-compose.yml"
install -o root -g root -m 0755 "$HERE/deploy.sh" /usr/local/bin/anaksor-site-deploy
install -d -o root -g root -m 0755 /etc/anaksor-web
install -o root -g root -m 0644 "$HERE/../docker-compose.yml" /etc/anaksor-web/docker-compose.yml
install -o root -g root -m 0644 /dev/null "$CONF"
cat >"$CONF" <<EOF
REPO_URL=$REPO_URL
BRANCH=$BRANCH
STATE_DIR=$STATE_DIR
DEPLOY_USER=$DEPLOY_USER
COMPOSE_FILE=/etc/anaksor-web/docker-compose.yml
KEEP=$KEEP
BIND_ADDRESS=$BIND_ADDRESS
WEB_PORT=$WEB_PORT
API_URL=$API_URL
SITE_URL=$SITE_URL
EOF

if [[ -n $CI_KEY ]]; then
  say "CI key -> $HOME_DIR/.ssh/authorized_keys"
  ssh-keygen -l -f "$CI_KEY" >/dev/null || die "$CI_KEY is not a public key"
  [[ $(wc -l <"$CI_KEY") -le 1 ]] || die "$CI_KEY must hold a single key"
  # Root-owned, so the deploy user cannot add an unrestricted key.
  install -d -o root -g "$DEPLOY_USER" -m 0750 "$HOME_DIR/.ssh"
  install -o root -g "$DEPLOY_USER" -m 0640 /dev/null "$HOME_DIR/.ssh/authorized_keys"
  printf 'restrict,command="/usr/local/bin/anaksor-site-deploy" %s\n' "$(cut -d' ' -f1,2 "$CI_KEY") github-actions-site-deploy" >"$HOME_DIR/.ssh/authorized_keys"
fi

if ((SSHD)); then
  say "sshd drop-in"
  grep -qiE '^\s*Include\s+/etc/ssh/sshd_config\.d/\*\.conf' /etc/ssh/sshd_config || die "sshd_config does not include sshd_config.d/*.conf"
  conf=/etc/ssh/sshd_config.d/90-anaksor-site-deploy.conf
  cat >"$conf" <<EOF
Match User $DEPLOY_USER
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    ForceCommand /usr/local/bin/anaksor-site-deploy
    PermitTTY no
    AllowTcpForwarding no
    AllowAgentForwarding no
    AllowStreamLocalForwarding no
    PermitTunnel no
    X11Forwarding no
Match all
EOF
  chmod 0644 "$conf"
  if ! sshd -t; then rm -f "$conf"; die "sshd rejected the drop-in; removed it"; fi
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
fi

say "next"
if [[ -e /etc/nginx/sites-enabled/anaksor-site ]]; then
  echo "* The host nginx site from the earlier setup still holds the port. Remove it (the container serves the site now):"
  echo "    rm /etc/nginx/sites-enabled/anaksor-site /etc/nginx/sites-available/anaksor-site && nginx -t && systemctl reload nginx"
  echo "    rm -rf /srv/anaksor-site"
fi
[[ -n $CI_KEY ]] || echo "* Run again with --ci-key <file.pub> to authorise the GitHub Actions key."
echo "* GitHub > anaksor-ocr > Settings > Environments > production, secret DEPLOY_KNOWN_HOSTS:"
for k in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ecdsa_key.pub; do
  [[ -f $k ]] && echo "    <your host or IP> $(cut -d' ' -f1,2 "$k")" && break
done
echo "  (for a port other than 22 write [<host>]:<port> instead of <host>)"
echo "* Cloudflare tunnel route: ocr.sokhengdin.dev -> http://localhost:$WEB_PORT"
echo "* First deploy:  sudo -u $DEPLOY_USER SSH_ORIGINAL_COMMAND=\"deploy \$(git ls-remote $REPO_URL refs/heads/$BRANCH | cut -f1)\" /usr/local/bin/anaksor-site-deploy"
echo "* Check:         sudo -u $DEPLOY_USER SSH_ORIGINAL_COMMAND=status /usr/local/bin/anaksor-site-deploy"
