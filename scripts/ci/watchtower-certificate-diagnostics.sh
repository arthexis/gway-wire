#!/usr/bin/env bash
set -u

fqdn="${1:-arthexis.com}"

if ! sudo -n true 2>/dev/null; then
  echo "Noninteractive sudo is required for certificate diagnostics." >&2
  exit 1
fi

section() {
  printf '\n===== %s =====\n' "$1"
}

section "DNS"
getent ahostsv4 "${fqdn}" || true

section "Certbot inventory"
sudo -n certbot certificates 2>&1 || true

section "Matching live certificate directories"
mapfile -t live_dirs < <(
  sudo -n find /etc/letsencrypt/live -mindepth 1 -maxdepth 1 -printf '%p\n' 2>/dev/null |
    grep -E "/${fqdn//./\.}(-[0-9]+)?$" |
    sort || true
)
if ((${#live_dirs[@]} == 0)); then
  echo "No matching /etc/letsencrypt/live directory found."
fi
for live_dir in "${live_dirs[@]}"; do
  echo "--- ${live_dir}"
  sudo -n ls -la "${live_dir}" || true
  for item in fullchain.pem privkey.pem cert.pem chain.pem; do
    path="${live_dir}/${item}"
    if sudo -n test -e "${path}"; then
      resolved="$(sudo -n readlink -f "${path}" 2>/dev/null || true)"
      printf '%s -> %s\n' "${path}" "${resolved}"
    fi
  done
  if sudo -n test -e "${live_dir}/fullchain.pem"; then
    sudo -n openssl x509 \
      -in "${live_dir}/fullchain.pem" \
      -noout -subject -issuer -dates -ext subjectAltName 2>&1 || true
  fi
done

section "Matching renewal configurations"
mapfile -t renewal_files < <(
  sudo -n find /etc/letsencrypt/renewal -mindepth 1 -maxdepth 1 -type f \
    -name "${fqdn}*.conf" -print 2>/dev/null | sort || true
)
if ((${#renewal_files[@]} == 0)); then
  echo "No matching /etc/letsencrypt/renewal configuration found."
fi
for renewal in "${renewal_files[@]}"; do
  echo "--- ${renewal}"
  sudo -n awk -F ' = ' '
    /^(archive_dir|cert|privkey|chain|fullchain|authenticator) = / { print }
  ' "${renewal}" 2>/dev/null || true
done

section "Nginx references"
sudo -n grep -R -n -E \
  "server_name[^;]*${fqdn//./\.}|ssl_certificate(_key)?[^;]*${fqdn//./\.}" \
  /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null || true

section "Publicly served certificate"
echo | timeout 10s openssl s_client -connect "${fqdn}:443" -servername "${fqdn}" 2>/dev/null |
  openssl x509 -noout -subject -issuer -dates -ext subjectAltName 2>&1 || true

section "Public health"
curl --show-error --silent --location --max-time 10 \
  --write-out '\nHTTP %{http_code}\n' \
  "https://${fqdn}/health/" || true
