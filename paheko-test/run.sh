#!/bin/sh
# Compose wrapper for the Paheko test instance.
#   ./run.sh up      -> build (if needed) + start
#   ./run.sh down    -> stop
#   ./run.sh rebuild -> rebuild the image
#   ./run.sh logs    -> logs
set -e
cd "$(dirname "$0")"
case "${1:-up}" in
  up)      podman compose up -d --build ;;
  down)    podman compose down ;;
  rebuild) podman compose build --no-cache ;;
  logs)    podman compose logs -f ;;
  *)       echo "usage: $0 {up|down|rebuild|logs}"; exit 1 ;;
esac
echo "Paheko -> http://localhost:8080"
