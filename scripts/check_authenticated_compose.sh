#!/usr/bin/env bash
set -euo pipefail

project="aeroforge-auth-e2e-$(openssl rand -hex 6)"
certs=$(mktemp -d)
compose=(docker compose --project-name "$project" -f docker-compose.yml -f compose.authenticated.yml)

cleanup() {
  local result=$?
  if [[ $result -ne 0 ]]; then
    "${compose[@]}" logs --no-color || true
  fi
  "${compose[@]}" down --volumes || true
  rm -f -- "$certs/cert.pem" "$certs/key.pem" "$certs/htpasswd" "$certs/config.json" "$certs/headers"
  rmdir -- "$certs"
}
trap cleanup EXIT

export AEROFORGE_TLS_CERT_FILE="$certs/cert.pem"
export AEROFORGE_TLS_KEY_FILE="$certs/key.pem"
export AEROFORGE_HTPASSWD_FILE="$certs/htpasswd"
export AEROFORGE_HTTPS_BIND_ADDRESS=127.0.0.1
export AEROFORGE_HTTPS_PORT=5443

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -keyout "$AEROFORGE_TLS_KEY_FILE" \
  -out "$AEROFORGE_TLS_CERT_FILE" -subj /CN=127.0.0.1 -addext subjectAltName=IP:127.0.0.1 2>/dev/null
password=$(openssl rand -hex 24)
printf '%s\n' "$password" | htpasswd -n -i -B -C 10 test-editor > "$AEROFORGE_HTPASSWD_FILE"
chmod 0444 "$AEROFORGE_HTPASSWD_FILE"

"${compose[@]}" --profile postgres config --format json > "$certs/config.json"
python - "$certs/config.json" <<'PY'
import json
import sys
from pathlib import Path

services = json.loads(Path(sys.argv[1]).read_text())["services"]
assert not services["api"].get("ports")
assert not services["db"].get("ports")
ports = services["web"]["ports"]
assert len(ports) == 1 and ports[0]["target"] == 443
assert ports[0]["host_ip"] == "127.0.0.1"
PY
"${compose[@]}" up --build --wait --wait-timeout 90

url=https://127.0.0.1:${AEROFORGE_HTTPS_PORT}
curl_https=(curl --silent --show-error --max-time 10 --cacert "$AEROFORGE_TLS_CERT_FILE")
for path in / /api/health /api/designs; do
  status=$("${curl_https[@]}" -D "$certs/headers" -o /dev/null -w '%{http_code}' "$url$path")
  if [[ "$status" != 401 ]]; then
    printf 'Expected 401 without credentials on %s, received %s\n' "$path" "$status" >&2
    exit 1
  fi
  grep -qi '^www-authenticate: basic ' "$certs/headers"
done
status=$("${curl_https[@]}" --user 'test-editor:invalid' -o /dev/null -w '%{http_code}' "$url/api/health")
[[ "$status" = 401 ]]
"${curl_https[@]}" --fail --user "test-editor:$password" "$url/" | grep -qi 'aeroforge'
"${curl_https[@]}" --fail --user "test-editor:$password" "$url/api/health" | python -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"'
"${curl_https[@]}" --fail --user "test-editor:$password" -o /dev/null "$url/api/designs"
