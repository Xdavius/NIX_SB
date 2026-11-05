#!/usr/bin/env bash
set -euo pipefail
: "${GITHUB_REPOSITORY:?}"
: "${GITHUB_REF_NAME:?}"
: "${GITHUB_SHA:?}"
: "${GITHUB_OUTPUT:?}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Une erreur reseau/API doit echouer, pas etre confondue avec une release absente.
gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases?per_page=100" > "$work/releases.json"
python3 - "$work/releases.json" >> "$GITHUB_OUTPUT" <<'PY'
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, 'ci')
from channels import channel_info
from release_tag import release_tag
from ci.release_bundle import REQUIRED_ASSETS

tag = release_tag({
    'profile': os.environ['GLF_CHANNEL'],
    'kernelVariant': os.environ.get('GLF_KERNEL_VARIANT', 'default'),
    'branch': os.environ['GITHUB_REF_NAME'],
    'commit': os.environ['GITHUB_SHA'],
    'channels': channel_info(json.loads(Path('flake.lock').read_text()), os.environ['GLF_CHANNEL']),
})
releases = json.loads(Path(sys.argv[1]).read_text())
matches = [r for page in releases for r in page if r['tag_name'] == tag and not r['draft']]
for release in matches:
    if not REQUIRED_ASSETS <= {asset['name'] for asset in release.get('assets', [])}:
        raise SystemExit('Release publique incomplete : les deux variantes sont requises')
exists = bool(matches)
print('needed=' + ('false' if exists else 'true'))
print(f'Publication {tag}: ' + ('deja disponible' if exists else 'a construire'), file=sys.stderr)
PY
