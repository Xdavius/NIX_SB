"""Check the installed NVIDIA extras without a GPU or network access."""
import argparse
import json
from pathlib import Path
import subprocess


def require(path):
    assert path.is_file(), f"Missing installed file: {path}"
    return path


def check_executable(path):
    require(path)
    assert path.stat().st_mode & 0o111, f"Not executable: {path}"
    interpreter = subprocess.check_output(
        ["patchelf", "--print-interpreter", str(path)], text=True
    ).strip()
    require(Path(interpreter))
    # Ask the ELF loader to resolve the full dependency tree without running
    # the application (which may otherwise require a GPU or perform updates).
    subprocess.run([interpreter, "--list", str(path)], check=True, timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("bin", type=Path)
    parser.add_argument("--vulkansc", action="store_true")
    args = parser.parse_args()

    inventory = require(args.bin / "share/nvidia/files.d/sandboxutils-filelist.json")
    entries = json.loads(inventory.read_text())
    assert isinstance(entries, list) and entries, "Invalid NVIDIA inventory"
    assert all(isinstance(e.get("name"), str) and e.get("type") for e in entries)

    for name in ["nvidia-ngx-updater"] + (["nvidia-pcc"] if args.vulkansc else []):
        check_executable(args.bin / "bin" / name)
        require(args.bin / "origBin" / name)

    updater = require(args.out / "lib/nvidia/wine/nvngx_update.exe")
    with updater.open("rb") as handle:
        assert handle.read(2) == b"MZ", "Invalid Wine updater executable"

    if args.vulkansc:
        descriptor = require(args.out / "share/vulkansc/icd.d/nvidia_icd.json")
        library = Path(json.loads(descriptor.read_text())["ICD"]["library_path"])
        assert library.is_absolute(), "Vulkan SC ICD must use an absolute Nix path"
        assert library.parent == args.out / "lib", "ICD targets another NVIDIA package"
        require(library)

    for root in [args.out, args.bin]:
        for path in root.rglob("*"):
            assert not path.is_symlink() or path.exists(), f"Broken symlink: {path}"
    report = json.loads(require(args.out / "nix-support/nvidia-extras.json").read_text())
    assert report["schemaVersion"] == 1
    added = set(report["addedByNixSb"])
    upstream = set(report["providedByNixpkgs"])
    required = {
        "bin/nvidia-ngx-updater", "origBin/nvidia-ngx-updater",
        "sandboxutils/inventory", "wine/ngx-updater",
    }
    if args.vulkansc:
        required |= {"bin/nvidia-pcc", "origBin/nvidia-pcc", "vulkansc/icd"}
    assert not added & upstream, "Conflicting installation provenance"
    assert required <= added | upstream, "Incomplete upstream coverage report"
    assert report["upstreamComplete"] == (not added), "Invalid retirement status"
    print("NVIDIA extras: installed files, loader dependencies and symlinks verified")
    if report["upstreamComplete"]:
        print("NIX_SB: upstream extras validated; local supplement is no longer necessary")


if __name__ == "__main__":
    main()
