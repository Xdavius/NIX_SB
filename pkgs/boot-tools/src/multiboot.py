"""Menu rEFInd GLF, generations installees et entrees UEFI existantes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from boot_menu import menu_header

REFIND = r'\EFI\refind\shimx64.efi'
LEGACY_REFIND = r'\EFI\refind\refind_x64.efi'
SYSTEMD = r'\EFI\GLF\shimx64.efi'
DIRECT_SYSTEMD = r'\EFI\systemd\systemd-bootx64.efi'


def settings(config):
    cfg = {'enable': False, 'makeDefault': True, 'configurationLimit': 10,
           **config.get('multiboot', {})}
    for name in ('enable', 'makeDefault'):
        if type(cfg[name]) is not bool:
            raise ValueError(f'multiboot.{name} doit etre un booleen')
    if type(cfg['configurationLimit']) is not int or cfg['configurationLimit'] < 1:
        raise ValueError('multiboot.configurationLimit doit etre positif')
    return cfg


def quoted(value):
    if any(ord(c) < 32 for c in value):
        raise ValueError('Caractere de controle interdit dans la configuration rEFInd')
    return '"' + value.replace('"', '""') + '"'


def managed(directory):
    directory = Path(directory)
    if not directory.exists() and not directory.is_symlink():
        return False
    if directory.is_symlink() or not directory.is_dir() or not (directory / '.glf-managed').is_file():
        raise ValueError(f'Installation non geree par GLF : {directory}')
    return True


def parse_firmware(text):
    entries = []
    for line in text.splitlines():
        match = re.match(r'^Boot([0-9A-Fa-f]{4})\*?\s+(.*)', line)
        if not match:
            continue
        label = re.split(r'\s+(?:HD|VenHw|BBS|PciRoot)\(', match[2], maxsplit=1)[0]
        path = re.search(r'File\(([^)]*)\)', line, re.I)
        if path is None:
            path = re.search(r'HD\([^)]*\)/(\\[^\s]+)', line, re.I)
        partition = re.search(r'HD\(\d+,(?:GPT|MBR),([^,]+),', line, re.I)
        entries.append({'number': match[1].upper(), 'active': line[8:9] == '*', 'label': ' '.join(label.split()),
                        'path': path[1].replace('/', '\\').lower() if path else '',
                        'partition': partition[1].lower() if partition else ''})
    order = re.search(r'^BootOrder:\s*([0-9A-Fa-f,]+)', text, re.M)
    return entries, order[1].upper().split(',') if order else []


def own_entry(entry, partition, paths):
    return entry['partition'] == partition.lower() and entry['path'] in [p.lower() for p in paths]


def firmware_state(esp):
    source = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', '--mountpoint', str(esp)], text=True).strip()
    block = json.loads(subprocess.check_output(
        ['lsblk', '--json', '--output', 'PKNAME,PARTN,PARTUUID', os.path.realpath(source)], text=True))['blockdevices'][0]
    if not all(block.get(k) for k in ('pkname', 'partn', 'partuuid')):
        raise ValueError('Impossible de determiner le disque/partition ESP')
    text = subprocess.check_output(['efibootmgr', '--verbose'], text=True)
    entries, order = parse_firmware(text)
    boot_next = re.search(r'^BootNext:\s*([0-9A-Fa-f]{4})\s*$', text, re.M)
    return {**block, 'entries': entries, 'order': order,
            'boot_next': boot_next[1].upper() if boot_next else None}


def configure_firmware(state, enabled, make_default, remove_refind=False):
    """Ne modifie que les entrees GLF de cette ESP, jamais celles d'un autre disque."""
    path, label = (REFIND, 'GLF-OS Multiboot') if enabled else (SYSTEMD, 'GLF-OS shim')
    matches = [e for e in state['entries'] if own_entry(e, state['partuuid'], [path])]
    if not matches:
        subprocess.run(['efibootmgr', '--create-only', '--disk', '/dev/' + state['pkname'],
                        '--part', str(state['partn']), '--label', label, '--loader', path], check=True)
        entries, _ = parse_firmware(subprocess.check_output(['efibootmgr', '--verbose'], text=True))
        matches = [e for e in entries if own_entry(e, state['partuuid'], [path])]
    if not matches:
        raise ValueError('Nouvelle entree UEFI GLF introuvable')
    # Prefer the existing entry already selected in BootOrder, including
    # inactive entries: activate it rather than creating a duplicate.
    selected = next((entry for number in state['order'] for entry in matches
                     if entry['number'] == number), matches[0])
    number = selected['number']
    if not selected['active']:
        subprocess.run(['efibootmgr', '--bootnum', number, '--active'], check=True)
    obsolete_paths = [LEGACY_REFIND] if enabled else ([REFIND, LEGACY_REFIND] if remove_refind else [])
    obsolete = {e['number'] for e in state['entries'] if own_entry(e, state['partuuid'], obsolete_paths)}
    order = [n for n in state['order'] if n not in obsolete]
    if make_default:
        order = [number] + [n for n in order if n != number]
    elif number not in order:
        order.append(number)
    if order != state['order']:
        subprocess.run(['efibootmgr', '--bootorder', ','.join(order)], check=True)
    # Redirect only a direct loader on this ESP, or an entry we are removing.
    # A one-shot Windows/recovery/other-disk selection remains the user's choice.
    pending = next((entry for entry in state['entries']
                    if entry['number'] == state.get('boot_next')), None)
    if pending and (own_entry(pending, state['partuuid'], [DIRECT_SYSTEMD])
                    or pending['number'] in obsolete):
        subprocess.run(['efibootmgr', '--bootnext', number], check=True)
    for old in sorted(obsolete):
        subprocess.run(['efibootmgr', '--delete-bootnum', '--bootnum', old], check=True)


def os_identity(entry):
    match = (entry['label'] + ' ' + entry['path']).lower()
    for patterns, icon, title in (
        (('endeavouros',), 'endeavouros', 'EndeavourOS'),
        (('archlinux', '\\efi\\arch\\', 'arch linux'), 'arch', 'Arch Linux'),
        (('fedora',), 'fedora', 'Fedora'), (('debian',), 'debian', 'Debian'),
        (('kubuntu',), 'kubuntu', 'Kubuntu'), (('lubuntu',), 'lubuntu', 'Lubuntu'),
        (('xubuntu',), 'xubuntu', 'Xubuntu'), (('ubuntu',), 'ubuntu', 'Ubuntu'),
        (('linuxmint', 'linux mint'), 'linuxmint', 'Linux Mint'),
        (('manjaro',), 'manjaro', 'Manjaro'), (('opensuse',), 'opensuse', 'openSUSE'),
        (('gentoo',), 'gentoo', 'Gentoo'), (('void',), 'void', 'Void Linux'),
        (('freebsd',), 'freebsd', 'FreeBSD'), (('netbsd',), 'netbsd', 'NetBSD'),
        (('windows', 'microsoft'), 'win', 'Windows'),
    ):
        if any(p in match for p in patterns):
            return f'os_{icon}.png', title
    return 'os_unknown.png', entry['label'] or f"UEFI {entry['number']}"


def generations(esp, selected, limit):
    """Reutilise les entrees installees ; masque celles dont la closure a disparu."""
    found = []
    for record in (esp / 'EFI/GLF/generations').glob('*/generation.json'):
        identifier = record.parent.name
        if not re.fullmatch('[a-f0-9]{32}', identifier):
            continue
        try:
            data = json.loads(record.read_text())
            target = Path(data['system'])
            if not target.is_absolute() or not (target / 'init').is_file():
                continue
            if hashlib.sha256(str(target).encode()).hexdigest()[:32] != identifier:
                continue
            content = (esp / 'loader/entries' / f'glf-{identifier}.conf').read_text()
            fields = dict(line.split(' ', 1) for line in content.splitlines() if ' ' in line)
            prefix = f'/EFI/GLF/generations/{identifier}'
            if fields.get('linux') != prefix + '/kernel.efi' or fields.get('initrd') != prefix + '/initrd':
                continue
            if not all((record.parent / file).is_file() for file in ('kernel.efi', 'initrd')):
                continue
            label = next(line[8:] for line in menu_header(target).splitlines() if line.startswith('version '))
            number = re.match(r'Generation (\d+) ', label)
            found.append({'id': identifier, 'kernel': fields['linux'], 'initrd': fields['initrd'],
                          'options': fields['options'], 'label': label,
                          'rank': (1, int(number[1])) if number else (0, record.stat().st_mtime)})
        except (OSError, ValueError, KeyError, StopIteration):
            continue
    current = next((g for g in found if g['id'] == selected), None)
    if current is None:
        raise ValueError('Generation selectionnee absente du menu')
    others = sorted((g for g in found if g is not current), key=lambda g: g['rank'], reverse=True)
    return [current, *others[:limit - 1]]


def render_menu(items, timeout, state=None):
    def loader(g, indent):
        return '\n'.join(indent + key + ' ' + quoted(g[field].replace('/', '\\') if field != 'options' else g[field]) for key, field in
                         (('loader', 'kernel'), ('initrd', 'initrd'), ('options', 'options')))
    lines = [f'timeout {timeout}', r'banner \EFI\refind\themes\glfos\glf-bootloader.png', 'banner_scale fillscreen',
             r'icons_dir \EFI\refind\icons',
             'scanfor manual', 'scan_all_linux_kernels false', 'use_nvram false',
             'default_selection GLF-OS', 'menuentry "GLF-OS" {',
             r'  icon \EFI\refind\themes\glfos\glfos.png', loader(items[0], '  '), '  submenu_on_select true']
    for item in items:
        lines += ['  submenuentry ' + quoted(item['label']) + ' {', loader(item, '    '), '  }']
    lines.append('}')
    if state:
        for entry in state['entries']:
            if own_entry(entry, state['partuuid'], [REFIND, LEGACY_REFIND, SYSTEMD,
                                                   r'\EFI\systemd\systemd-bootx64.efi',
                                                   r'\EFI\BOOT\BOOTX64.EFI']):
                continue
            icon, title = os_identity(entry)
            lines += ['menuentry ' + quoted(title) + ' {', '  icon \\EFI\\refind\\icons\\' + icon,
                      f"  firmware_bootnum {entry['number']}", '}']
    return '\n'.join(lines) + '\n'


def install_menu(esp, bundle, config, selected, state, copy):
    cfg = settings(config)
    directory = esp / 'EFI/refind'
    managed(directory)  # Also refuses an existing unmanaged installation.
    assets = Path(os.environ['GLF_MULTIBOOT_ASSETS'])
    content = render_menu(generations(esp, selected, cfg['configurationLimit']), config['timeout'], state)
    directory.mkdir(parents=True, exist_ok=True)
    for source in assets.rglob('*'):
        if source.is_file():
            copy(source, directory / source.relative_to(assets))
    copy(bundle / 'refind_x64.efi', directory / 'grubx64.efi')
    copy(bundle / 'shimx64.efi', directory / 'shimx64.efi')
    copy(bundle / 'mmx64.efi', directory / 'mmx64.efi')
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / 'refind.conf'
        path.write_text(content)
        copy(path, directory / 'refind.conf')
        path.write_text('Managed by GLF-OS. glf-multiboot / glf.multiboot.enable\n')
        copy(path, directory / '.glf-managed')


def remove_menu(esp):
    directory = esp / 'EFI/refind'
    if managed(directory):
        shutil.rmtree(directory)


def cleanup(esp, lanzaboote=False):
    if lanzaboote and not (esp / 'EFI/GLF/.glf-managed').is_file():
        raise ValueError('Installer et verifier le nouveau demarrage GLF avant le nettoyage Lanzaboote')
    for path in (esp / 'loader/entries').glob('glf-other-*.conf'):
        path.unlink()
    if lanzaboote:
        for directory, patterns in (('EFI/Linux', ['nixos-generation-*.efi']),
                                    ('EFI/nixos', ['kernel-*.efi', 'initrd-*.efi']),
                                    ('loader/keys/auto', ['PK.auth', 'KEK.auth', 'db.auth'])):
            for pattern in patterns:
                for path in (esp / directory).glob(pattern):
                    if path.is_file() or path.is_symlink():
                        path.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='/etc/secureboot/install.json')
    parser.add_argument('--allow-unmounted', action='store_true')
    parser.add_argument('action', choices=['install', 'remove', 'cleanup-legacy-entries', 'cleanup-lanzaboote'])
    parser.add_argument('target', nargs='?', default='/run/current-system')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    from install_boot import install, validate_esp
    if args.allow_unmounted and config['canTouchEfiVariables']:
        parser.error('Pas de modifications EFI avec --allow-unmounted')
    if args.action in ('install', 'remove'):
        if args.action == 'remove' and not (Path(config['esp']) / 'EFI/refind/.glf-managed').is_file():
            return  # Aucun multiboot GLF installe : laisser le demarrage intact.
        config['multiboot'] = {**config.get('multiboot', {}), 'enable': args.action == 'install'}
        install(config, args.target, args.allow_unmounted)
    else:
        import fcntl
        esp = validate_esp(config, args.allow_unmounted)
        with open(esp / '.glf-install.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            cleanup(esp, args.action == 'cleanup-lanzaboote')


if __name__ == '__main__':
    main()
