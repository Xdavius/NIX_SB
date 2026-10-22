"""Validation locale d'une demande contre des composants approuves par l'operateur.

Aucun telechargement, build ou transport distant implicite.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'pkgs/boot-tools/src'))
from signing_protocol import validate
from signing_policy import validate_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('--sha256', required=True)
    for name in ('kernel', 'bootloader', 'stub', 'ukify'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    validate(args.directory, args.sha256)
    validate_policy(args.directory, args.kernel, args.bootloader, args.stub, args.ukify)


if __name__ == '__main__':
    main()
