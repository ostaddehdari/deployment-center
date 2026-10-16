#!/usr/bin/env bash
# Read-only local inventory. No credentials, environment values or git remote URLs.
set -Eeuo pipefail
printf 'HOST: '; hostname
printf 'DATE (UTC): '; date -u '+%Y-%m-%dT%H:%M:%SZ'
echo
echo '=== Application roots (direct children) ==='
for base in /var/www /opt /srv; do
  if [[ -d "$base" ]]; then
    printf '%s\n' "[$base]"
    find "$base" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort || true
  fi
done
echo
echo '=== Service names (active) ==='
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --type=service --state=running --no-legend --plain --no-pager 2>/dev/null | awk '{print $1}' || true
fi
echo
echo '=== Running containers (name, image only) ==='
if command -v docker >/dev/null 2>&1; then
  docker ps --format '{{.Names}} | {{.Image}}' 2>/dev/null || true
fi
echo
echo '=== Git working tree locations (no remotes) ==='
for base in /var/www /opt /srv; do
  if [[ -d "$base" ]]; then
    find "$base" -maxdepth 5 -name .git \( -type d -o -type f \) -print 2>/dev/null || true
  fi
done
echo
echo 'Review before sharing: even service names and paths may be sensitive.'
