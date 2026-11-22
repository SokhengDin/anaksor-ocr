#!/usr/bin/env bash
# sudo ./install.sh --ci-key ci_deploy.pub [--dir /srv/anaksor-ocr] [--user deploy] [--sshd]
set -euo pipefail
umask 022

APP_DIR=/srv/anaksor-ocr
DEPLOY_USER=deploy
BRANCH=master
REPO_URL=git@github.com:SokhengDin/anaksor-ocr.git
STATE_DIR=/var/lib/anaksor-deploy
GATE=/usr/local/bin/anaksor-deploy
CONF=/etc/anaksor-deploy.conf
CONTAINER=anaksor-web
CI_KEY=
SSHD=0
HERE=$(cd "$(dirname "$0")" && pwd)
GITHUB_HOST_KEY='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'

die() { echo "error: $*" >&2; exit 1; }
say() { printf '\n-- %s\n' "$*"; }

while (($#)); do
  case $1 in
    --dir) APP_DIR=$2; shift 2 ;;
    --user) DEPLOY_USER=$2; shift 2 ;;
    --ci-key) CI_KEY=$2; shift 2 ;;
    --sshd) SSHD=1; shift ;;
    *) die "unknown option $1" ;;
  esac
done

((EUID == 0)) || die "run as root (sudo)"
cd /
for c in git docker flock setsid ssh-keygen stat runuser; do command -v "$c" >/dev/null || die "$c is not installed"; done
docker compose version >/dev/null 2>&1 || die "docker compose v2 is not installed"
[[ $DEPLOY_USER =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "bad user name"
APP_DIR=${APP_DIR%/}
[[ $APP_DIR =~ ^/[A-Za-z0-9._/-]+$ ]] || die "--dir must be an absolute path of letters, digits, . _ - /"

# Reuse the live container's compose project: the container name is fixed.
PROJECT=$(docker inspect "$CONTAINER" --format '{{ index .Config.Labels "com.docker.compose.project" }}' 2>/dev/null || true)
PROJECT=${PROJECT:-anaksor-web}
[[ $PROJECT =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "bad compose project name: $PROJECT"

# One user, one forced command: never take over a user another gate already uses.
if id "$DEPLOY_USER" >/dev/null 2>&1; then
  ak="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)/.ssh/authorized_keys"
  if [[ -f $ak ]] && grep -q 'command="' "$ak" && ! grep -q "command=\"$GATE\"" "$ak"; then
    die "$DEPLOY_USER already has a key for another forced command ($ak); pick another user with --user"
  fi
  for f in /etc/ssh/sshd_config.d/*.conf; do
    [[ -f $f && $f != */90-anaksor-deploy.conf ]] || continue
    grep -qiE "^\s*Match\s+User\s+$DEPLOY_USER\s*$" "$f" && die "$f already has a Match User $DEPLOY_USER block; pick another user with --user"
  done
fi

say "user $DEPLOY_USER"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$STATE_DIR" --no-create-home --shell /bin/bash "$DEPLOY_USER"
fi
passwd -l "$DEPLOY_USER" >/dev/null
usermod -aG docker "$DEPLOY_USER"
HOME_DIR=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)

say "state $STATE_DIR"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0750 "$STATE_DIR" "$STATE_DIR/logs"
install -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0640 /dev/null "$STATE_DIR/github_known_hosts"
echo "$GITHUB_HOST_KEY" >"$STATE_DIR/github_known_hosts"
if [[ ! -f $STATE_DIR/github_ro ]]; then
  runuser -u "$DEPLOY_USER" -- ssh-keygen -q -t ed25519 -N '' -C "anaksor-server-readonly" -f "$STATE_DIR/github_ro"
fi
chmod 0600 "$STATE_DIR/github_ro"

say "gate $GATE"
install -o root -g root -m 0755 "$HERE/deploy.sh" "$GATE"
install -o root -g root -m 0644 /dev/null "$CONF"
cat >"$CONF" <<EOF
APP_DIR=$APP_DIR
BRANCH=$BRANCH
REPO_URL=$REPO_URL
STATE_DIR=$STATE_DIR
DEPLOY_USER=$DEPLOY_USER
COMPOSE_PROJECT=$PROJECT
EOF

if [[ -n $CI_KEY ]]; then
  say "CI key -> $HOME_DIR/.ssh/authorized_keys"
  ssh-keygen -l -f "$CI_KEY" >/dev/null || die "$CI_KEY is not a public key"
  [[ $(wc -l <"$CI_KEY") -le 1 ]] || die "$CI_KEY must hold a single key"
  # Root-owned, so the deploy user cannot add an unrestricted key.
  install -d -o root -g "$DEPLOY_USER" -m 0750 "$HOME_DIR/.ssh"
  install -o root -g "$DEPLOY_USER" -m 0640 /dev/null "$HOME_DIR/.ssh/authorized_keys"
  printf 'restrict,command="%s" %s\n' "$GATE" "$(cut -d' ' -f1,2 "$CI_KEY") github-actions-anaksor-deploy" >"$HOME_DIR/.ssh/authorized_keys"
fi

if ((SSHD)); then
  say "sshd drop-in"
  grep -qiE '^\s*Include\s+/etc/ssh/sshd_config\.d/\*\.conf' /etc/ssh/sshd_config || die "sshd_config does not include sshd_config.d/*.conf"
  conf=/etc/ssh/sshd_config.d/90-anaksor-deploy.conf
  cat >"$conf" <<EOF
Match User $DEPLOY_USER
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    ForceCommand $GATE
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

say "checkout $APP_DIR (compose project: $PROJECT)"
gitssh="ssh -i $STATE_DIR/github_ro -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$STATE_DIR/github_known_hosts"
readable=0
runuser -u "$DEPLOY_USER" -- env GIT_SSH_COMMAND="$gitssh" git ls-remote "$REPO_URL" HEAD >/dev/null 2>&1 && readable=1
problems=()
if [[ -d $APP_DIR/.git ]]; then
  if [[ $(stat -c %U "$APP_DIR") != "$DEPLOY_USER" ]]; then
    problems+=("$APP_DIR is not owned by $DEPLOY_USER: sudo chown -R $DEPLOY_USER: $APP_DIR")
  elif ! runuser -u "$DEPLOY_USER" -- test -w "$APP_DIR/.git"; then
    problems+=("$DEPLOY_USER cannot reach $APP_DIR (a parent directory blocks it): sudo setfacl -m u:$DEPLOY_USER:x $(dirname "$APP_DIR")")
  fi
elif ((readable)); then
  install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 0750 "$APP_DIR"
  runuser -u "$DEPLOY_USER" -- env GIT_SSH_COMMAND="$gitssh" git clone --quiet --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
if ((${#problems[@]} == 0)) && [[ -f $APP_DIR/web/.env ]]; then
  chown "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR/web/.env"
  chmod 0600 "$APP_DIR/web/.env"
fi
docker network inspect proxy_network >/dev/null 2>&1 || problems+=("docker network proxy_network is missing: docker network create proxy_network")

say "next"
if ((!readable)); then
  echo "* GitHub cannot be read yet. Add this READ-ONLY deploy key (Allow write access: off) in"
  echo "  github.com/SokhengDin/anaksor-ocr > Settings > Deploy keys, then run this script again:"
  echo "    $(cat "$STATE_DIR/github_ro.pub")"
fi
[[ -n $CI_KEY ]] || echo "* Run again with --ci-key <file.pub> to authorise the GitHub Actions key."
echo "* GitHub secret DEPLOY_KNOWN_HOSTS: ssh-keyscan -t ed25519 against exactly the DEPLOY_HOST value. It must match:"
if [[ -f /etc/ssh/ssh_host_ed25519_key.pub ]]; then echo "    $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"; fi
if ((${#problems[@]})); then
  for p in "${problems[@]}"; do echo "error: $p" >&2; done
  exit 1
fi
