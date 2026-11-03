#!/usr/bin/env bash
# The CI key's forced command (installed as /usr/local/bin/anaksor-site-deploy): only
# `deploy <full sha>` and `status`. It builds the website image from a commit on master, read from the
# public repo, checks it, and runs it as the anaksor-web container. Nothing sent over SSH is used but the sha.
set -euo pipefail
umask 022
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C

CONF=/etc/anaksor-site-deploy.conf
REPO_URL=https://github.com/SokhengDin/anaksor-ocr.git  # public: read over HTTPS, no key on the server
BRANCH=master
STATE_DIR=/var/lib/anaksor-site-deploy                   # repo mirror, build contexts, logs, lock
DEPLOY_USER=anaksor-deploy
COMPOSE_FILE=/etc/anaksor-web/docker-compose.yml         # root-owned copy; never taken from a commit
IMAGE=anaksor-web                                        # tagged with the full commit sha
KEEP=5                                                   # images kept for rollback, the live one included
BIND_ADDRESS=127.0.0.1                                   # where the container's port is published
WEB_PORT=8088
API_URL=                                                 # empty: the site's default (https://ocr-api.sokhengdin.dev)
SITE_URL=                                                # empty: the site's default (https://ocr.sokhengdin.dev)
if [[ -f $CONF ]]; then
  [[ $(stat -c '%u %a' "$CONF") =~ ^0\ [0-7][0-4][0-4]$ ]] || { echo "refused: $CONF must be root-owned, not writable by others" >&2; exit 1; }
  # shellcheck source=/dev/null
  . "$CONF"
fi

SELF=/usr/local/bin/anaksor-site-deploy
REPO=$STATE_DIR/repo.git
LOG_DIR=$STATE_DIR/logs
export GIT_TERMINAL_PROMPT=0 COMPOSE_PROJECT_NAME=anaksor-web BIND_ADDRESS WEB_PORT

die() { echo "error: $*" >&2; exit 1; }
step() { printf '\n== %s  %s\n' "$(date -u +%H:%M:%S)" "$*"; }
# Server-only additions (e.g. joining the tunnel's network) go in docker-compose.override.yml next to the
# compose file: root-owned, never touched by install.sh, applied on every deploy.
compose() {
  local files=(-f "$COMPOSE_FILE") override=${COMPOSE_FILE%.yml}.override.yml
  if [[ -f $override ]]; then
    [[ $(stat -c '%u %a' "$override") =~ ^0\ [0-7][0-4][0-4]$ ]] || die "refused: $override must be root-owned, not writable by others"
    files+=(-f "$override")
  fi
  docker compose "${files[@]}" "$@"
}

[[ $(id -un) == "$DEPLOY_USER" ]] || die "must run as $DEPLOY_USER"

worker() {
  local sha=$1 build image
  exec 9>"$STATE_DIR/lock"
  flock -w 1800 9 || die "another deploy still holds the lock"

  step "fetch $BRANCH"
  git --git-dir="$REPO" fetch --quiet --prune --no-tags "$REPO_URL" "+refs/heads/$BRANCH:refs/heads/$BRANCH"
  git --git-dir="$REPO" cat-file -e "$sha^{commit}" 2>/dev/null || die "commit $sha not found on GitHub"
  git --git-dir="$REPO" merge-base --is-ancestor "$sha" "$BRANCH" || die "commit $sha is not on $BRANCH"

  image=$IMAGE:$sha
  if docker image inspect "$image" >/dev/null 2>&1; then
    step "image $image is already built"
  else
    build=$STATE_DIR/build/$sha
    rm -rf "$build"
    mkdir -p "$build"
    step "export web/ at $sha"
    git --git-dir="$REPO" archive "$sha" web | tar -x -C "$build"

    # The build runs inside BuildKit's sandbox: package code never runs on the host.
    step "build $image"
    docker build --pull \
      --build-arg API_URL="$API_URL" --build-arg SITE_URL="$SITE_URL" \
      --label org.opencontainers.image.revision="$sha" \
      --label org.opencontainers.image.source="$REPO_URL" \
      -t "$image" "$build/web"
    rm -rf "$build"
  fi

  local prev
  prev=$(cat "$STATE_DIR/deployed" 2>/dev/null || true)
  step "run anaksor-web ($image) on $BIND_ADDRESS:$WEB_PORT"
  if ! TAG=$sha compose up -d --wait --wait-timeout 120 --remove-orphans; then
    if [[ -n $prev && $prev != "$sha" ]] && docker image inspect "$IMAGE:$prev" >/dev/null 2>&1; then
      step "not healthy: back to $prev"
      TAG=$prev compose up -d --wait --wait-timeout 120 || true
    fi
    die "anaksor-web ($image) did not become healthy"
  fi
  echo "$sha" >"$STATE_DIR/deployed"

  # Keep the newest KEEP images; never the live one.
  local live tag
  live=$(docker inspect anaksor-web --format '{{.Config.Image}}' 2>/dev/null || true)
  docker image ls "$IMAGE" --format '{{.CreatedAt}}\t{{.Tag}}' | sort -r | tail -n +"$((KEEP + 1))" | cut -f2 |
    while read -r tag; do
      [[ $tag =~ ^[0-9a-f]{40}$ && "$IMAGE:$tag" != "$live" ]] && docker image rm "$IMAGE:$tag" >/dev/null
    done
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
    echo "deployed:  $(cat "$STATE_DIR/deployed" 2>/dev/null || echo none)"
    echo "container: $(docker inspect anaksor-web --format '{{.Config.Image}}  {{.State.Status}} ({{if .State.Health}}{{.State.Health.Status}}{{else}}no health check{{end}})' 2>/dev/null || echo none)"
    echo "images:"
    docker image ls "$IMAGE" --format '  {{.Tag}}  {{.CreatedSince}}'
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
