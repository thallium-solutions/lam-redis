#!/bin/sh
# Copyright 2026 Thallium Solutions di Busconi Alessandro.
# SPDX-License-Identifier: Apache-2.0
set -eu

STARTED=""

usage() {
    cat <<'EOF'
Usage: sh test-services.sh

Starts disposable Redis services matching the Lammergeier language test suite:
  localhost:6380  Redis without authentication
  localhost:6379  Redis with password "Password"

Containers started by this script are stopped when it exits. Existing running
containers with the expected names are left running and are not stopped.
EOF
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    "") ;;
    *)
        usage >&2
        exit 2
        ;;
esac

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker is not installed or not on PATH" >&2
    exit 1
fi

container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

container_running() {
    [ "$(docker container inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]
}

start_container() {
    name=$1
    shift
    if container_exists "$name"; then
        if container_running "$name"; then
            echo "[test-services] $name already running; leaving it untouched"
            return
        fi
        echo "error: container $name exists but is stopped; remove or start it first" >&2
        exit 1
    fi
    echo "[test-services] starting $name"
    docker run --rm -d --name "$name" "$@" >/dev/null
    STARTED="$STARTED $name"
}

cleanup() {
    if [ -n "$STARTED" ]; then
        echo
        echo "[test-services] stopping containers:$STARTED"
        # shellcheck disable=SC2086
        docker stop $STARTED >/dev/null 2>&1 || true
        STARTED=""
    fi
}

stop() {
    cleanup
    trap - EXIT INT TERM
    exit 0
}

trap cleanup EXIT
trap stop INT TERM

start_container lam-redis-test-no-auth -p 6380:6379 redis:latest
start_container lam-redis-test-auth -p 6379:6379 redis:latest redis-server --requirepass Password

cat <<'EOF'

[test-services] Redis services are starting.
[test-services] In another terminal run:

  lamc lib run test

[test-services] Press Ctrl-C here to stop containers started by this script.
EOF

while :; do
    sleep 3600 &
    wait $!
done
