"""Conserver les sept dernieres publications Secure Boot du depot."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime


TAG = re.compile(r'secureboot-(?:current|testing)-[a-f0-9]{12}-[a-f0-9]{40}(?:-[a-f0-9]{64})?')


def obsolete_releases(releases, published_tag):
    candidates = [r for r in releases
                  if not r['draft'] and TAG.fullmatch(r['tag_name'])]
    if not any(r['tag_name'] == published_tag for r in candidates):
        raise ValueError('La nouvelle release publique est absente : nettoyage refuse')
    candidates.sort(key=lambda r: (datetime.fromisoformat(r['published_at'].replace('Z', '+00:00')),
                                   r['id']), reverse=True)
    # Garder la publication de ce run, meme en cas de publication concurrente.
    keep = {published_tag}
    for release in candidates:
        if len(keep) < 7:
            keep.add(release['tag_name'])
    return [r['tag_name'] for r in candidates if r['tag_name'] not in keep]


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    result = subprocess.run(
        ['gh', 'api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'],
        check=True, capture_output=True, text=True,
    )
    releases = [r for page in json.loads(result.stdout) for r in page]
    for tag in obsolete_releases(releases, sys.argv[1]):
        print(f'Suppression de la release et du tag : {tag}', flush=True)
        subprocess.run(['gh', 'release', 'delete', tag, '--repo', repo,
                        '--yes', '--cleanup-tag'], check=True)


if __name__ == '__main__':
    main()
