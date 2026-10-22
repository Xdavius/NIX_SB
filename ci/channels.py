"""Controle et trace les pins channels sans modifier ni rafraichir aucun lock."""
import argparse
import json
import re
from pathlib import Path


def channel_info(lock, profile="current"):
    if profile not in ("current", "testing"):
        raise ValueError("Profil attendu : current ou testing")
    channel_name = "glf-channels" if profile == "current" else "testing-channels"
    prefix = "" if profile == "current" else "testing-"
    nodes = lock['nodes']
    root = nodes[lock['root']]['inputs']
    channel = nodes[root[channel_name]]
    result = {'source': channel['locked']['url'],
              'ref': channel['locked'].get('ref'),
              'commit': channel['locked']['rev'],
              'narHash': channel['locked']['narHash'],
              'buildInput': 'nixpkgs'}
    for name in ('nixpkgs', 'nixpkgs-unstable'):
        if root[prefix + name] != [channel_name, name]:
            raise ValueError(f'{prefix + name} doit suivre {channel_name}/{name}')
        node = nodes[channel['inputs'][name]]
        revision = node['locked']['rev']
        if not re.fullmatch(r'[a-f0-9]{40}', revision):
            raise ValueError(f'Le lock doit epingler {name} par commit')
        result[name] = {'rev': revision, 'narHash': node['locked']['narHash']}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('current', 'testing'), default='current')
    parser.add_argument('--lock', type=Path, default=Path('flake.lock'))
    parser.add_argument('--glfos-lock', type=Path)
    args = parser.parse_args()
    info = channel_info(json.loads(args.lock.read_text()), args.profile)
    if args.glfos_lock:
        other = channel_info(json.loads(args.glfos_lock.read_text()))
        if info != other:
            raise SystemExit('Les pins channels different du lock GLF-OS fourni')
    print(json.dumps(info, indent=2))
