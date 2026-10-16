#!/usr/bin/env bash
# TelTest-only deployctl launcher; deployment installer installed separately.
set -Eeuo pipefail
[[ "$(hostname)" == VMID-20571 ]] || { echo ERROR_WRONG_HOST; exit 2; }
case "${1:-}" in
  status)
    for s in teltest.service teltest-eitaa-gateway.service teltest-delivery.timer teltest-scheduler.timer; do printf "%s=" "$s";systemctl is-active "$s" || true;done
    curl -fLsS --max-time 7 http://127.0.0.1:18870/teltest/health
    ;;
  install)
    [[ "${2:-}" == teltest ]] || { echo "USAGE: deployctl install teltest TAG --check|--apply";exit 2;}
    [[ -x /usr/local/lib/deployctl/teltest-install.sh ]] || { echo "ERROR_INSTALLER_NOT_BOOTSTRAPPED";exit 3;}
    exec /usr/local/lib/deployctl/teltest-install.sh "${3:-}" "${4:---check}"
    ;;
  history)
    find /opt/teltest/backups/deployment-center -name installed-tag.txt -type f -print 2>/dev/null | sort -r | head -20 || true
    ;;
  *) echo "Usage: deployctl status | install teltest TAG --check|--apply | history"; exit 2;;
esac
