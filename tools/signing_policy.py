"""Only the kernel and bootloader built from the reviewed repository may be signed."""
from pathlib import Path
import shlex
import subprocess
import tempfile
from signing_protocol import pe_content


def section(image, name):
    with tempfile.TemporaryDirectory(prefix='glf-pe-section-') as temp:
        output = Path(temp) / 'section'
        subprocess.run(['objcopy', '--dump-section', f'{name}={output}', str(image), str(Path(temp) / 'copy.efi')],
                       check=True, capture_output=True)
        if not output.is_file():
            raise ValueError(f'Section {name} absente')
        return output.read_bytes()


def validate_policy(directory, kernel, bootloader, stub, ukify):
    directory = Path(directory)
    trusted_kernel = Path(kernel).read_bytes()
    if (directory / 'kernel.efi').read_bytes() != trusted_kernel:
        raise ValueError('Noyau hors catalogue GLF approuve')
    if (directory / 'systemd-bootx64.efi').read_bytes() != Path(bootloader).read_bytes():
        raise ValueError('Chargeur hors catalogue GLF approuve')
    if section(directory / 'glf-os.efi', '.linux') != trusted_kernel:
        raise ValueError('Le noyau embarque dans l UKI differe du noyau approuve')
    cmdline = section(directory / 'glf-os.efi', '.cmdline').rstrip(b'\0').decode('utf-8')
    params = shlex.split(cmdline)
    for key, value in [('module.sig_enforce', '1'), ('lockdown', 'integrity')]:
        # Also reject duplicates, alternate spellings and parameters after --.
        matches = [p for p in params if p.split('=', 1)[0].replace('-', '_') == key.replace('-', '_')]
        if matches != [f'{key}={value}']:
            raise ValueError(f'Politique noyau invalide : {key}')
        if '--' in params and params.index(f'{key}={value}') > params.index('--'):
            raise ValueError(f'Parametre noyau apres -- : {key}')
    # Reconstituer l'image avec le stub approuve : comparer seulement .linux
    # laisserait passer un stub malveillant ou un autre point d'entree PE.
    with tempfile.TemporaryDirectory(prefix='glf-approved-uki-') as temp:
        root = Path(temp)
        for name in ('initrd', 'osrel'):
            (root / name).write_bytes(section(directory / 'glf-os.efi', '.' + name))
        uname = section(directory / 'glf-os.efi', '.uname').rstrip(b'\0').decode('utf-8')
        subprocess.run([str(ukify), 'build', '--linux', str(kernel), '--initrd', str(root / 'initrd'),
                        '--stub', str(stub), '--cmdline', cmdline,
                        '--os-release', '@' + str(root / 'osrel'), '--uname', uname,
                        '--output', str(root / 'approved.efi')], check=True)
        if pe_content(root / 'approved.efi') != pe_content(directory / 'glf-os.efi'):
            raise ValueError('UKI non canonique : stub ou sections hors politique GLF')
