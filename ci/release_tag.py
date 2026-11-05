"""Identite immuable d'une publication : code, branche, profil et channels."""
import hashlib
import json
import re
import sys
from pathlib import Path


def release_tag(metadata):
    profile = metadata['profile']
    commit = metadata['commit']
    if profile not in ('current', 'testing') or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Profil ou commit invalide')
    variant = metadata.get('kernelVariant', 'default')
    if variant not in ('default', 'latest'):
        raise ValueError('Variante noyau invalide')
    suffix = '-latest' if variant == 'latest' else ''
    branch = hashlib.sha256(metadata['branch'].encode()).hexdigest()[:12]
    channels = hashlib.sha256(json.dumps(
        metadata['channels'], sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()
    return f'secureboot-{profile}{suffix}-{branch}-{commit}-{channels}'


if __name__ == '__main__':
    print(release_tag(json.loads(Path(sys.argv[1]).read_text())))
