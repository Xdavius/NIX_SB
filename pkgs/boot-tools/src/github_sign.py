#!/usr/bin/env python3
"""Request signatures without sending any private signing key to the machine."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
from signing_protocol import IMAGES, prepare, verify_response


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", required=True, help="Branche de version GLF-OS, par exemple Rising")
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--token-file")
    parser.add_argument("--allow-public-artifacts", action="store_true")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--system", required=True)
    parser.add_argument("unsigned", type=Path)
    parser.add_argument("signed", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        parser.error("Depot GitHub invalide")
    if args.token_file:
        os.environ["GH_TOKEN"] = Path(args.token_file).read_text().strip()
    visibility = json.loads(gh("repo", "view", args.repo, "--json", "visibility"))["visibility"]
    if visibility == "PUBLIC" and not args.allow_public_artifacts:
        parser.error("Depot public : les artefacts signes seront telechargeables. Utiliser un depot prive ou autoriser explicitement --allow-public-artifacts.")
    expected = prepare(args.unsigned, args.system)
    tag = "glf-sign-" + uuid.uuid4().hex
    notes = args.unsigned / "review.txt"
    notes.write_text(f"Demande de signature Secure Boot\nSysteme : {args.system}\nSHA256 request.json : {expected}\nVerifier les images avant d'approuver glf-signing.\n")
    gh("release", "create", tag, "--repo", args.repo, "--target", args.ref,
       "--draft", "--title", tag, "--notes-file", str(notes))
    print(f"Demande {tag}. Examiner la release draft dans https://github.com/{args.repo}/releases puis approuver le job glf-signing.", flush=True)
    gh("release", "upload", tag, "--repo", args.repo,
       *[str(args.unsigned / name) for name in (*IMAGES, "request.json")])
    gh("workflow", "run", "sign-request.yml", "--repo", args.repo, "--ref", args.ref,
       "-f", f"request_tag={tag}", "-f", f"request_sha256={expected}")
    deadline = time.monotonic() + args.timeout
    run_id = None
    while time.monotonic() < deadline:
        if run_id is None:
            runs = json.loads(gh("run", "list", "--repo", args.repo, "--workflow", "sign-request.yml",
                                "--event", "workflow_dispatch", "--branch", args.ref, "--limit", "100", "--json", "databaseId,displayTitle"))
            run_id = next((r["databaseId"] for r in runs if r["displayTitle"] == tag), None)
        if run_id:
            run = json.loads(gh("run", "view", str(run_id), "--repo", args.repo, "--json", "status,conclusion"))
            if run["status"] == "completed":
                if run["conclusion"] != "success":
                    raise RuntimeError(f"Signature refusee ou echouee : run {run_id}")
                break
        time.sleep(10)
    else:
        raise TimeoutError(f"Signature en attente : {tag}. Aucun fichier de demarrage installe.")
    args.signed.mkdir(parents=True, exist_ok=False)
    gh("run", "download", str(run_id), "--repo", args.repo, "--name", tag, "--dir", str(args.signed))
    if (args.signed / "request.json").read_bytes() != (args.unsigned / "request.json").read_bytes():
        raise ValueError("La reponse ne correspond pas a la demande")
    verify_response(args.unsigned, args.signed, args.certificate)
    # The draft is retained as an audit record; never publish it automatically.
    print(f"Signatures verifiees pour {args.system}. Demande conservee : {tag}")


if __name__ == "__main__":
    main()
