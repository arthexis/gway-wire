#!/usr/bin/env bash
set -euo pipefail

fqdn="arthexis.com"
legacy_site="/etc/nginx/sites-enabled/arthexis-preview-example.conf"
managed_site="/etc/nginx/sites-enabled/gway-${fqdn}.conf"
backup_root="/var/backups/gway-certificate-repair"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${fqdn}-${stamp}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

sudo -n true || fail "noninteractive sudo is required"
command -v certbot >/dev/null || fail "certbot is required"
command -v nginx >/dev/null || fail "nginx is required"
command -v gway >/dev/null || fail "gway is required"

# Guard the exact legacy state observed by Watchtower diagnostics. This repair is
# deliberately not a general certificate cleanup command.
sudo -n test -e "/etc/letsencrypt/live/${fqdn}" || fail "expected legacy live lineage is missing"
sudo -n test -e "${legacy_site}" || fail "expected legacy nginx site is missing"
sudo -n test ! -e "${managed_site}" || fail "GWay-managed nginx site already exists; refusing legacy repair"

mapfile -t renewal_files < <(
  sudo -n find /etc/letsencrypt/renewal -mindepth 1 -maxdepth 1 -type f \
    -name "${fqdn}*.conf" -print 2>/dev/null | sort || true
)
((${#renewal_files[@]} == 0)) || fail "matching Certbot renewal metadata now exists; refusing repair"

certbot_inventory="$(sudo -n certbot certificates 2>&1 || true)"
if grep -Eq "Certificate Name: ${fqdn//./\.}(-[0-9]+)?$" <<<"${certbot_inventory}"; then
  fail "Certbot now manages an arthexis.com lineage; refusing repair"
fi

mapfile -t nginx_refs < <(
  sudo -n grep -R -l -E \
    "server_name[^;]*${fqdn//./\.}|ssl_certificate(_key)?[^;]*${fqdn//./\.}" \
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
printf 'Live lineages:\n'; printf '  %s\n' "${live_dirs[@]}"
printf 'Archive lineages:\n'; printf '  %s\n' "${archive_dirs[@]:-}"
printf 'Legacy nginx site: %s\n' "${legacy_site}"

sudo -n install -d -m 0700 "${backup_dir}/letsencrypt/live" "${backup_dir}/letsencrypt/archive" "${backup_dir}/nginx"

# Preserve the legacy nginx entry exactly as it existed, then disable it.
sudo -n cp -a "${legacy_site}" "${backup_dir}/nginx/"
sudo -n rm -f "${legacy_site}"

# Quarantine orphaned lineages instead of deleting them. With no renewal files
# and no Certbot inventory entries, moving these paths makes the desired FQDN
# appear genuinely missing to GWay while retaining full recovery material.
for path in "${live_dirs[@]}"; do
  sudo -n mv "${path}" "${backup_dir}/letsencrypt/live/"
done
for path in "${archive_dirs[@]}"; do
  sudo -n mv "${path}" "${backup_dir}/letsencrypt/archive/"
done

# Ensure the legacy configuration is no longer active before asking the normal
# GWay exposure path to provision a fresh, managed certificate and vhost.
sudo -n nginx -t

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
sudo -n test -e "/etc/letsencrypt/renewal/${fqdn}.conf" || fail "fresh managed renewal config was not created"
sudo -n test -e "${managed_site}" || fail "GWay-managed nginx site was not created"

curl --fail --show-error --silent --max-time 15 "https://${fqdn}/health/"
echo
printf 'Repair completed successfully. Legacy state retained at %s\n' "${backup_dir}"
