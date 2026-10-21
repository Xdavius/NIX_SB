import os
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from signing_protocol import IMAGES, validate

tag = os.environ["REQUEST_TAG"]
if not re.fullmatch(r"glf-sign-[a-f0-9]{32}", tag):
    raise ValueError("Identifiant de demande invalide")
Path("dist/unsigned").mkdir(parents=True, exist_ok=False)
for name in (*IMAGES, "request.json"):
    subprocess.run(["gh", "release", "download", tag, "--repo", os.environ["GITHUB_REPOSITORY"],
                    "--pattern", name, "--dir", "dist/unsigned"], check=True)
validate("dist/unsigned", os.environ["REQUEST_SHA256"])
