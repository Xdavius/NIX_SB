#!/usr/bin/env bash
# Verifications legeres : aucun build du noyau, aucune VM.
set -euo pipefail
for script in ci/*.sh; do bash -n "$script"; done
shellcheck ci/*.sh
actionlint
profile=${GLF_CHANNEL:-current}
case "$profile" in current) prefix="" ;; testing) prefix="testing-" ;; *) exit 1 ;; esac
python3 ci/channels.py --profile "$profile"
flake_ref=${GLF_FLAKE_REF:-.}
nix eval "$flake_ref#checks.x86_64-linux.${prefix}packages.drvPath" --no-update-lock-file
python3 -m unittest discover -s tests -p 'test_catalogue.py'
python3 -m unittest discover -s tests -p 'test_installer_config.py'
python3 -m unittest discover -s tests -p 'test_boot_menu.py'
python3 -m unittest discover -s tests -p 'test_bootstrap.py'
# Petites fixtures PE seulement : aucun build noyau ni acces EFI/reseau de signature.
python3 tests/test_boot.py
python3 ci/test-signing.py "$GLF_TEST_STUB"
