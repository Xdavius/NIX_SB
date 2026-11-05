"""Vérifier les deux variantes avant de rendre leur release commune publique."""
import base64
import hashlib
import json
from pathlib import Path
import sys

from ci.release_tag import release_tag

VARIANTS = ('default', 'latest')
REQUIRED_ASSETS = frozenset(
    filename
    for variant in VARIANTS
    for filename in (f'glf-secureboot-{variant}.tar.gz',
                     f'release-{variant}.json', f'build-{variant}.json')
)


def validate_bundle(directory):
    directory = Path(directory)
    common = None
    for variant in VARIANTS:
        build = json.loads((directory / f'build-{variant}.json').read_text())
        descriptor = json.loads((directory / f'release-{variant}.json').read_text())
        identity = {key: build[key] for key in ('profile', 'branch', 'commit', 'channels')}
        if common is not None and identity != common:
            raise ValueError('Les deux noyaux doivent partager commit, branche, profil et channels')
        common = identity
        if build.get('kernelVariant', 'default') != variant or descriptor.get('kernelVariant') != variant:
            raise ValueError('Variante incoherente')
        if descriptor['version'] != 2 or any(descriptor[key] != build[key]
                                            for key in ('profile', 'branch', 'commit')):
            raise ValueError('Descripteur incompatible avec le build')
        archive = directory / f'glf-secureboot-{variant}.tar.gz'
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').digest()
        if descriptor['archiveHash'] != 'sha256-' + base64.b64encode(digest).decode():
            raise ValueError('Hash archive incorrect')
        tag = release_tag(build)
        if not descriptor['url'].endswith(f'/releases/download/{tag}/{archive.name}'):
            raise ValueError('URL incompatible avec la release commune')
        if (directory / 'tag.txt').read_text().strip() != tag:
            raise ValueError('Tag incompatible')
    return tag


if __name__ == '__main__':
    print(validate_bundle(sys.argv[1]))
