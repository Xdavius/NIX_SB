"""Verifier les certificats reellement construits des drivers dans le bundle."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
bundle = (root / 'modules.cer').read_bytes()
assert hashlib.sha256(bundle).hexdigest() == (root / 'bundle.sha256').read_text().strip()
manifest = json.loads((root / 'approved-modules.json').read_text())
total = 0
for name, source in sorted(manifest['modules'].items()):
    certificates = list(Path(source).rglob('*.ko.cer'))
    assert certificates, f'{name}: aucun certificat de module'
    for certificate in certificates:
        data = certificate.read_bytes()
        assert data and data in bundle, f'{name}: certificat absent du bundle: {certificate}'
    total += len(certificates)
    print(f'{name}: {len(certificates)} certificats presents')
print(f'OK : {total} certificats pour {len(manifest["modules"])} drivers, empreinte du bundle valide.')
