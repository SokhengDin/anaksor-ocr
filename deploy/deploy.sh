#!/usr/bin/env bash
# The CI key's forced command: only `deploy <sha>` and `status`.
set -euo pipefail
# Checked-out files must stay world-readable: the image build copies them.
umask 022
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C

CONF=/etc/anaksor-deploy.conf
APP_DIR=/srv/anaksor-ocr
BRANCH=master
REPO_URL=git@github.com:SokhengDin/anaksor-ocr.git
STATE_DIR=/var/lib/anaksor-deploy
DEPLOY_USER=deploy
COMPOSE_PROJECT=anaksor-web
if [[ -f $CONF ]]; then
  [[ $(stat -c '%u %a' "$CONF") =~ ^0\ [0-7][0-4][0-4]$ ]] || { echo "refused: $CONF must be root-owned, not writable by others" >&2; exit 1; }
  # shellcheck source=/dev/null
  . "$CONF"
fi

SELF=/usr/local/bin/anaksor-deploy
LOG_DIR=$STATE_DIR/logs
export COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT
export GIT_SSH_COMMAND="ssh -i $STATE_DIR/github_ro -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$STATE_DIR/github_known_hosts"
export GIT_TERMINAL_PROMPT=0

die() { echo "error: $*" >&2; exit 1; }
step() { printf '\n== %s  %s\n' "$(date -u +%H:%M:%S)" "$*"; }

[[ $(id -un) == "$DEPLOY_USER" ]] || die "must run as $DEPLOY_USER"

worker() {
  local sha=$1 prev
  exec 9>"$STATE_DIR/lock"
  flock -w 1800 9 || die "another deploy still holds the lock"
  cd "$APP_DIR"

  step "fetch $BRANCH"
  git fetch --quiet --prune "$REPO_URL" "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
  git cat-file -e "$sha^{commit}" 2>/dev/null || die "commit $sha not found on GitHub"
  git merge-base --is-ancestor "$sha" "origin/$BRANCH" || die "commit $sha is not on $BRANCH"

  prev=$(git rev-parse HEAD)
  step "checkout $sha (was $prev)"
  git -c advice.detachedHead=false checkout --quiet --force --detach "$sha"

  cd web
  docker network inspect proxy_network >/dev/null 2>&1 || die "docker network proxy_network is missing: docker network create proxy_network"
  step "build image"
  docker compose build --pull
  step "web"
  docker compose up -d --wait --wait-timeout 300 web

  echo "$sha" >"$STATE_DIR/deployed"
  find "$LOG_DIR" -name '*.log' -mtime +30 -delete
  step "deployed $sha"
}

if [[ ${1:-} == --worker ]]; then
  worker "$2"
  exit
fi

cmd=${SSH_ORIGINAL_COMMAND:-}
case $cmd in
  status)
    echo "deployed: $(cat "$STATE_DIR/deployed" 2>/dev/null || echo none)"
    git -C "$APP_DIR" log -1 --format='checkout: %H %s'
    cd "$APP_DIR/web" && docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    ;;
  deploy\ *)
    sha=${cmd#deploy }
    [[ $sha =~ ^[0-9a-f]{40}$ ]] || die "refused: expected a full commit sha"
    mkdir -p "$LOG_DIR"
    log=$LOG_DIR/$(date -u +%Y%m%dT%H%M%SZ)-${sha:0:12}.log
    : >"$log"
    # Detached, so a dropped connection or a cancelled job never stops a deploy halfway.
    setsid "$SELF" --worker "$sha" </dev/null >>"$log" 2>&1 &
    pid=$!
    tail -n +1 -f --pid="$pid" "$log" || true
    wait "$pid" || die "deploy failed, log: $log"
    ;;
  *)
    die "refused: only 'deploy <sha>' and 'status' are allowed"
    ;;
esac
