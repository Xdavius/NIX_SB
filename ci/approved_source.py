"""Read the GLF-OS revision reviewed with the signing workflow."""
import json
from pathlib import Path
import re


def approved_source():
    source = json.loads(Path(__file__).with_name('approved-source.json').read_text())['flake']
    if not re.fullmatch(r'git\+https://framagit\.org/xdavius/glf-os\.git\?ref=feature/secureboot-uki&rev=[0-9a-f]{40}&dir=secureboot', source):
        raise ValueError('Source GLF-OS approuvee absente ou non verrouillee')
    return source


if __name__ == '__main__':
    print(approved_source())
