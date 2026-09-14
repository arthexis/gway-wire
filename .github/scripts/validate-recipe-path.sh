#!/usr/bin/env bash
set -euo pipefail

candidate="${1:-}"
if [[ -z "${candidate}" ]]; then
  echo "recipe path is required" >&2
  exit 2
fi

case "${candidate}" in
  recipes/*.rx) ;;
  *)
    echo "recipe must be a .rx file under recipes/" >&2
    exit 2
    ;;
esac

root="$(git rev-parse --show-toplevel)"
recipes_root="$(realpath "${root}/recipes")"
resolved="$(realpath "${root}/${candidate}")"

case "${resolved}" in
  "${recipes_root}"/*.rx) ;;
  *)
    echo "recipe resolves outside recipes/" >&2
    exit 2
    ;;
esac

if ! git -C "${root}" ls-files --error-unmatch -- "${candidate}" >/dev/null 2>&1; then
  echo "recipe must be tracked by git: ${candidate}" >&2
  exit 2
fi

if [[ ! -f "${resolved}" ]]; then
  echo "recipe is not a file: ${candidate}" >&2
  exit 2
fi

printf '%s\n' "${candidate}"
