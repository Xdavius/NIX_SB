"""Valider et signer les vrais artefacts avec une cle jetable, sans reseau."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkgs/boot-tools/src'))
from signing_protocol import prepare, validate, verify_response
from signing_policy import validate_policy

source = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='glf-real-sign-') as tmp:
    work = Path(tmp)
    unsigned = work / 'dist/unsigned'
    shutil.copytree(source, unsigned)
    expected = prepare(unsigned, 'real-build-test')
    validate(unsigned, expected)
    validate_policy(unsigned, source / 'kernel.efi', source / 'systemd-bootx64.efi',
                    os.environ['GLF_TEST_STUB'], os.environ['GLF_TEST_UKIFY'])
    key, cert = work / 'key.pem', work / 'cert.pem'
    subprocess.run(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-x509', '-days', '1',
                    '-subj', '/CN=GLF REAL BUILD DISPOSABLE TEST/', '-keyout', str(key),
                    '-out', str(cert)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fingerprint = subprocess.check_output(['openssl', 'x509', '-in', str(cert), '-noout',
                                          '-fingerprint', '-sha256'], text=True).strip().split('=')[1]
    env = dict(os.environ, GLF_SIGNING_KEY_PEM=key.read_text(),
               GLF_SIGNING_CERT_PEM=cert.read_text(), GLF_CERT_SHA256=fingerprint)
    subprocess.run(['bash', str(ROOT / 'ci/sign.sh')], cwd=work, env=env, check=True)
    verify_response(unsigned, work / 'dist/signed', cert)
    print('OK : UKI complete conforme a la politique et trois images signees/verifiees, cle jetable supprimee en sortie.')
