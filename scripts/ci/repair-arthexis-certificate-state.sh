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

legacy_present=false
if sudo -n test -e "${legacy_site}" || sudo -n test -e "/etc/letsencrypt/live/${fqdn}"; then
  legacy_present=true
fi

if [[ "${legacy_present}" == true ]]; then
  # Guard the exact legacy state observed by Watchtower diagnostics. This repair
  # is deliberately not a general certificate cleanup command.
  sudo -n test -e "/etc/letsencrypt/live/${fqdn}" || fail "legacy nginx state exists but expected live lineage is missing"
  sudo -n test -e "${legacy_site}" || fail "legacy live lineage exists but expected nginx site is missing"
  sudo -n test ! -e "${managed_site}" || fail "legacy and GWay-managed nginx sites coexist; refusing repair"

  mapfile -t renewal_files < <(
    sudo -n find /etc/letsencrypt/renewal -mindepth 1 -maxdepth 1 -type f \
      -name "${fqdn}*.conf" -print 2>/dev/null | sort || true
  )
  ((${#renewal_files[@]} == 0)) || fail "matching Certbot renewal metadata now exists while legacy state remains; refusing repair"

  certbot_inventory="$(sudo -n certbot certificates 2>&1 || true)"
  if grep -Eq "Certificate Name: ${fqdn//./\.}(-[0-9]+)?$" <<<"${certbot_inventory}"; then
    fail "Certbot now manages an arthexis.com lineage while legacy state remains; refusing repair"
  fi

  # Only treat the apex hostname as a reference. Subdomains such as
  # logs.arthexis.com and repo.arthexis.com are unrelated managed sites.
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
  printf 'Live lineages:\n'; printf '  %s\n' "${live_dirs[@]}"
  printf 'Archive lineages:\n'; printf '  %s\n' "${archive_dirs[@]:-}"
  printf 'Legacy nginx site: %s\n' "${legacy_site}"

  sudo -n install -d -m 0700 "${backup_dir}/letsencrypt/live" "${backup_dir}/letsencrypt/archive" "${backup_dir}/nginx"
  sudo -n cp -a "${legacy_site}" "${backup_dir}/nginx/"
  sudo -n rm -f "${legacy_site}"

  for path in "${live_dirs[@]}"; do
    sudo -n mv "${path}" "${backup_dir}/letsencrypt/live/"
  done
  for path in "${archive_dirs[@]}"; do
    sudo -n mv "${path}" "${backup_dir}/letsencrypt/archive/"
  done
else
  # A prior attempt may already have quarantined the legacy material and then
  # failed during public health validation. Allow that exact partial state to
  # resume through the normal GWay exposure path instead of requiring rollback.
  latest_backup="$(sudo -n find "${backup_root}" -mindepth 1 -maxdepth 1 -type d \
    -name "${fqdn}-*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  [[ -n "${latest_backup}" ]] || fail "legacy state is absent and no quarantine backup exists; refusing ambiguous repair"
  echo "Legacy state already quarantined; resuming from ${latest_backup}"
fi

sudo -n nginx -t

# The normal GWay path is intentionally used for both first-run and resume. If
# certificate/nginx provisioning already happened before a failed health check,
# ensure() should reuse that managed state and retry the public health check.
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
printf 'Repair completed successfully.\n'
