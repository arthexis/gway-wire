#!/usr/bin/env bash
set -euo pipefail

domain="dev.gelectriic.com"
backup_root="/var/backups/gway-certificate-repair"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${domain}-${stamp}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

sudo -n true || fail "noninteractive sudo is required"

mapfile -t nginx_refs < <(
  sudo -n grep -R -l -E \
    "server_name[^;]*(^|[[:space:]])${domain//./\.}([[:space:];]|$)|ssl_certificate(_key)?[[:space:]]+/etc/letsencrypt/live/${domain//./\.}/" \
    /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | sort -u || true
)

for ref in "${nginx_refs[@]}"; do
  mapfile -t server_names < <(
    sudo -n awk '/server_name[[:space:]]+/ {for (i=2;i<=NF;i++) {gsub(/;/,"",$i); print $i}}' "${ref}" |
      sed '/^$/d' | sort -u
  )
  for name in "${server_names[@]}"; do
    [[ "${name}" == "${domain}" ]] || fail "refusing to retire mixed nginx file ${ref}; it also serves ${name}"
  done
done

mapfile -t live_dirs < <(
  sudo -n find /etc/letsencrypt/live -mindepth 1 -maxdepth 1 -printf '%p\n' 2>/dev/null |
    grep -E "/${domain//./\.}(-[0-9]+)?$" | sort || true
)
mapfile -t archive_dirs < <(
  sudo -n find /etc/letsencrypt/archive -mindepth 1 -maxdepth 1 -printf '%p\n' 2>/dev/null |
    grep -E "/${domain//./\.}(-[0-9]+)?$" | sort || true
)
mapfile -t renewal_files < <(
  sudo -n find /etc/letsencrypt/renewal -mindepth 1 -maxdepth 1 -type f \
    -name "${domain}*.conf" -print 2>/dev/null | sort || true
)

if ((${#nginx_refs[@]} == 0 && ${#live_dirs[@]} == 0 && ${#archive_dirs[@]} == 0 && ${#renewal_files[@]} == 0)); then
  echo "No active ${domain} nginx or Certbot state remains."
  exit 0
fi

sudo -n install -d -m 0700 \
  "${backup_dir}/nginx" \
  "${backup_dir}/letsencrypt/live" \
  "${backup_dir}/letsencrypt/archive" \
  "${backup_dir}/letsencrypt/renewal"

for ref in "${nginx_refs[@]}"; do
  echo "Quarantining nginx config: ${ref}"
  sudo -n cp -a "${ref}" "${backup_dir}/nginx/"
  sudo -n rm -f "${ref}"
done
for path in "${live_dirs[@]}"; do
  echo "Quarantining live lineage: ${path}"
  sudo -n mv "${path}" "${backup_dir}/letsencrypt/live/"
done
for path in "${archive_dirs[@]}"; do
  echo "Quarantining archive lineage: ${path}"
  sudo -n mv "${path}" "${backup_dir}/letsencrypt/archive/"
done
for path in "${renewal_files[@]}"; do
  echo "Quarantining renewal config: ${path}"
  sudo -n mv "${path}" "${backup_dir}/letsencrypt/renewal/"
done

sudo -n nginx -t
sudo -n systemctl reload nginx

echo "Retired ${domain}; preserved prior state at ${backup_dir}"
