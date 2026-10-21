import os
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from signing_protocol import IMAGES, validate
from signing_policy import validate_policy
from approved_source import approved_source

tag = os.environ["REQUEST_TAG"]
if not re.fullmatch(r"glf-sign-[a-f0-9]{32}", tag):
    raise ValueError("Identifiant de demande invalide")
Path("dist/unsigned").mkdir(parents=True, exist_ok=False)
for name in (*IMAGES, "request.json"):
    subprocess.run(["gh", "release", "download", tag, "--repo", os.environ["GITHUB_REPOSITORY"],
                    "--pattern", name, "--dir", "dist/unsigned"], check=True)
validate("dist/unsigned", os.environ["REQUEST_SHA256"])
# Le checkout main protege approuve une revision GLF-OS immuable.
# Cette reference ne vient jamais des images ni des parametres de la demande.
source = approved_source()

def approved(attribute):
    return Path(subprocess.check_output([
        "nix", "build", "--no-update-lock-file", "--no-link", "--print-out-paths", source + "#" + attribute + ".out"
    ], text=True).strip())

validate_policy("dist/unsigned", approved("kernel") / "bzImage",
                approved("systemd-boot") / "systemd-bootx64.efi",
                approved("signing-stub") / "linuxx64.efi.stub",
                approved("signing-ukify") / "lib/systemd/ukify")
