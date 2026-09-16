#!/usr/bin/env bash
set -u

fqdn="arthexis.com"
service="gway-arthexis-web-local.service"
managed_site="/etc/nginx/sites-enabled/gway-${fqdn}.conf"

section() {
  printf '\n===== %s =====\n' "$1"
}

section "Arthexis service state"
sudo -n systemctl is-active "${service}" 2>&1 || true
sudo -n systemctl is-enabled "${service}" 2>&1 || true

section "Port 8888 listeners"
sudo -n ss -ltnp '( sport = :8888 )' 2>&1 || true

section "Local health"
curl --show-error --silent --max-time 10 \
  --write-out '\nHTTP %{http_code}\n' \
  http://127.0.0.1:8888/health/ 2>&1 || true

section "Managed nginx site"
if sudo -n test -f "${managed_site}"; then
  sudo -n cat "${managed_site}" 2>&1 || true
else
  echo "Managed site not present: ${managed_site}"
fi

section "Nginx configuration check"
sudo -n nginx -t 2>&1 || true

section "Recent nginx errors"
sudo -n tail -n 80 /var/log/nginx/error.log 2>&1 || true

section "Recent Arthexis web service log"
sudo -n journalctl -u "${service}" --since '-5 minutes' --no-pager -n 120 2>&1 || true

section "Certbot arthexis.com state"
sudo -n certbot certificates 2>&1 | awk '
  /Certificate Name: arthexis\.com$/ {show=1}
  show {print}
  show && /^  Certificate Name:/ && $0 !~ /arthexis\.com$/ {exit}
' || true

section "Public certificate"
printf '' | timeout 8 openssl s_client -connect "${fqdn}:443" -servername "${fqdn}" 2>/dev/null |
  openssl x509 -noout -subject -issuer -dates -ext subjectAltName 2>&1 || true

section "Public health"
curl --show-error --silent --location --max-time 10 \
  --write-out '\nHTTP %{http_code}\n' \
  "https://${fqdn}/health/" 2>&1 || true
