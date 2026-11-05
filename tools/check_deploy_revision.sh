#!/usr/bin/env bash
# Local binding first; recheck remote main immediately before the upload.
set -euo pipefail

test "${GITHUB_REF:-}" = refs/heads/main || { echo "Refusing non-main deployment" >&2; exit 1; }
case "${GITHUB_EVENT_NAME:-}" in
  push)
    test "${CHECKED_SHA:-}" = "${GITHUB_SHA:?}" || { echo "Missing exact CI revision" >&2; exit 1; }
    ;;
  workflow_dispatch) ;; # Standalone workflow performs its own full repository gate.
  *) echo "Refusing unsupported deployment event" >&2; exit 1 ;;
esac
test "$(git rev-parse HEAD)" = "${GITHUB_SHA:?}" || { echo "Checkout differs from checked revision" >&2; exit 1; }

case "${1:-}" in
  "") ;;
  --before-upload)
    current_main="$(git ls-remote origin refs/heads/main | cut -f1)"
    test "$current_main" = "$GITHUB_SHA" || { echo "Refusing stale main deployment" >&2; exit 1; }
    ;;
  *) echo "Unknown guard option" >&2; exit 1 ;;
esac
