#!/usr/bin/env bash
# Run the isolated OpenSearch 2.11 security demonstration from any directory.
set -euo pipefail

SECURITY_DEMO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SECURITY_DEMO_ACTION="${1:-help}"
if [[ $# -gt 0 ]]; then shift; fi
cd "$SECURITY_DEMO_DIR"

case "$SECURITY_DEMO_ACTION" in
  start|stop|status|permissions|showcase|native-start|native-stop)
    exec uv run --with-requirements requirements.txt python demo.py "$SECURITY_DEMO_ACTION" "$@"
    ;;
  verify)
    exec uv run --with-requirements requirements.txt python verify.py "${1:-all}"
    ;;
  help|-h|--help)
    cat <<'USAGE'
OpenSearch 2.11 / KalDB security demo

  security_demo.sh start --kaldb-home /path/to/kaldb
  security_demo.sh verify [all|native|api|ui]
  security_demo.sh showcase
  security_demo.sh permissions --user user1 --access none
  security_demo.sh permissions --user user1 --access own --tenant-access own
  security_demo.sh status
  security_demo.sh stop

Use the KalDB permissions review branch. Login values are generated in .state/credentials.json.
USAGE
    ;;
  *) echo "Unknown action: $SECURITY_DEMO_ACTION" >&2; exit 2 ;;
esac
