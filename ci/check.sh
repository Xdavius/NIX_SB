#!/usr/bin/env bash
# Verifications legeres : aucun build du noyau, aucune VM.
set -euo pipefail
for script in ci/*.sh; do bash -n "$script"; done
shellcheck ci/*.sh
actionlint
flake_ref=${GLF_FLAKE_REF:-.}
nix flake check "$flake_ref" --no-build --no-update-lock-file
python3 -m unittest discover -s tests -p 'test_catalogue.py'
python3 -m unittest discover -s tests -p 'test_installer_config.py'
python3 -m unittest discover -s tests -p 'test_github_sign.py'
python3 -m unittest discover -s tests -p 'test_bootstrap.py'
