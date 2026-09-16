#!/usr/bin/env bash
set -euo pipefail

fqdn="arthexis.com"
legacy_site="/etc/nginx/sites-enabled/arthexis-preview-example.conf"
managed_site="/etc/nginx/sites-enabled/gway-${fqdn}.conf"
backup_root="/var/backups/gway-certificate-repair"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${fqdn}-${stamp}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

diagnostics_on_error() {
  status=$?
  echo "Repair failed with exit status ${status}; capturing upstream diagnostics." >&2
  bash "${script_dir}/watchtower-arthexis-upstream-diagnostics.sh" || true
  return "${status}"
}
trap diagnostics_on_error ERR

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

sudo -n true || fail "noninteractive sudo is required"
command -v certbot >/dev/null || fail "certbot is required"
command -v nginx >/dev/null || fail "nginx is required"
command -v gway >/dev/null || fail "gway is required"

live_present=false
renewal_present=false
legacy_site_present=false
managed_site_present=false
certbot_managed=false

sudo -n test -e "/etc/letsencrypt/live/${fqdn}" && live_present=true
sudo -n test -e "/etc/letsencrypt/renewal/${fqdn}.conf" && renewal_present=true
sudo -n test -e "${legacy_site}" && legacy_site_present=true
sudo -n test -e "${managed_site}" && managed_site_present=true

certbot_inventory="$(sudo -n certbot certificates 2>&1 || true)"
if grep -Eq "Certificate Name: ${fqdn//./\.}$" <<<"${certbot_inventory}"; then
  certbot_managed=true
fi

if [[ "${legacy_site_present}" == true ]]; then
  [[ "${live_present}" == true ]] || fail "legacy nginx state exists but expected live lineage is missing"
  [[ "${renewal_present}" == false ]] || fail "legacy nginx state coexists with renewal metadata; refusing ambiguous repair"
  [[ "${certbot_managed}" == false ]] || fail "legacy nginx state coexists with a managed Certbot lineage; refusing ambiguous repair"
  [[ "${managed_site_present}" == false ]] || fail "legacy and GWay-managed nginx sites coexist; refusing repair"

  mapfile -t nginx_refs < <(
    sudo -n grep -R -l -E \
      "server_name[^;]*(^|[[:space:]])${fqdn//./\.}([[:space:];]|$)|ssl_certificate(_key)?[[:space:]]+/etc/letsencrypt/live/${fqdn//./\.}/" \
      /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | sort -u || true
  )
  ((${#nginx_refs[@]} > 0)) || fail "no nginx references for ${fqdn} were found"
  for ref in "${nginx_refs[@]}"; do
    [[ "${ref}" == "${legacy_site}" ]] || fail "unexpected nginx reference: ${ref}"
  done

  mapfile -t live_dirs < <(
    sudo -n find /etc/letsencrypt/live -mindepth 1 -maxdepth 1 -printf '%p\n' 2>/dev/null |
      grep -E "/${fqdn//./\.}(-[0-9]+)?$" | sort || true
  )
  mapfile -t archive_dirs < <(
    sudo -n find /etc/letsencrypt/archive -mindepth 1 -maxdepth 1 -printf '%p\n' 2>/dev/null |
      grep -E "/${fqdn//./\.}(-[0-9]+)?$" | sort || true
  )
  ((${#live_dirs[@]} > 0)) || fail "no matching live lineages found"

  printf 'Repairing legacy certificate state for %s\n' "${fqdn}"
  printf 'Backup directory: %s\n' "${backup_dir}"
  sudo -n install -d -m 0700 "${backup_dir}/letsencrypt/live" "${backup_dir}/letsencrypt/archive" "${backup_dir}/nginx"
  sudo -n cp -a "${legacy_site}" "${backup_dir}/nginx/"
  sudo -n rm -f "${legacy_site}"

  for path in "${live_dirs[@]}"; do
    sudo -n mv "${path}" "${backup_dir}/letsencrypt/live/"
  done
  for path in "${archive_dirs[@]}"; do
    sudo -n mv "${path}" "${backup_dir}/letsencrypt/archive/"
  done
elif [[ "${live_present}" == true && "${renewal_present}" == true && "${certbot_managed}" == true ]]; then
  echo "Fresh Certbot-managed ${fqdn} lineage already exists; resuming at nginx exposure reconciliation."
elif [[ "${live_present}" == false && "${renewal_present}" == false && "${certbot_managed}" == false ]]; then
  latest_backup="$(sudo -n find "${backup_root}" -mindepth 1 -maxdepth 1 -type d \
    -name "${fqdn}-*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  [[ -n "${latest_backup}" ]] || fail "apex certificate state is absent and no quarantine backup exists; refusing ambiguous repair"
  echo "Legacy state already quarantined; resuming from ${latest_backup}"
else
  fail "inconsistent ${fqdn} certificate state: live=${live_present} renewal=${renewal_present} certbot_managed=${certbot_managed} legacy_site=${legacy_site_present}"
fi

# The development hostname is retired. Remove exact-domain server and Certbot
# residue before rebuilding the apex vhost so it cannot remain nginx's fallback
# certificate. The retirement helper fails closed on mixed nginx files.
bash "${script_dir}/retire-dev-gelectriic-state.sh"

sudo -n nginx -t

# Prove the application upstream is locally healthy before asking GWay to make
# it public. A failure here triggers the upstream diagnostic bundle.
curl --fail --show-error --silent --max-time 15 "http://127.0.0.1:8888/health/"
echo

exposure="$(sudo -n gway --json wire server public expose \
  --fqdn "${fqdn}" \
  --upstream http://127.0.0.1:8888 \
  --health-path /health/ \
  --dns-provider godaddy \
  --no-dns-rollback \
  --cert-email tecnologia@gelectriic.com)"
printf '%s\n' "${exposure}"
python3 -c 'import json, sys; data=json.loads(sys.argv[1]); sys.exit(0 if data.get("success") is True else 1)' "${exposure}"

sudo -n nginx -t
sudo -n test -e "/etc/letsencrypt/renewal/${fqdn}.conf" || fail "fresh managed renewal config is missing"
sudo -n test -e "${managed_site}" || fail "GWay-managed nginx site was not created"

curl --fail --show-error --silent --max-time 15 "https://${fqdn}/health/"
echo
trap - ERR
printf 'Repair completed successfully.\n'
