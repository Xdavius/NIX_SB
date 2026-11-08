# shellcheck shell=bash
# Complete only missing files after the upstream installation. Existing files,
# including symlinks, belong to upstream and are validated by postInstallCheck.

extras_status="$out/nix-support/nvidia-extras.json"
extras_previous='{"addedByNixSb": []}'
if [ -f "$extras_status" ]; then
    extras_previous=$(cat "$extras_status")
    jq -e --arg version "$version" \
        '.schemaVersion == 1 and .driverVersion == $version and
         (.addedByNixSb | type == "array")' <<< "$extras_previous" >/dev/null
fi
extras_report=$(jq -n --arg version "$version" \
    '{schemaVersion: 1, driverVersion: $version, addedByNixSb: [], providedByNixpkgs: []}')

extras_record() {
    local origin="$1" component="$2"
    # A second invocation must not mistake our previous additions for native
    # nixpkgs support, or the retirement report would become a false positive.
    if jq -e --arg component "$component" \
        '.addedByNixSb | index($component) != null' <<< "$extras_previous" >/dev/null; then
        origin=addedByNixSb
    fi
    extras_report=$(jq --arg origin "$origin" --arg component "$component" \
        '.[$origin] += [$component]' <<< "$extras_report")
}

extras_missing() {
    local component="$1" destination="$2"
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        extras_record providedByNixpkgs "$component"
        return 1
    fi
    extras_record addedByNixSb "$component"
    return 0
}

for program in nvidia-ngx-updater nvidia-pcc; do
    if [ -f "$program" ] || [ -e "$bin/bin/$program" ] || [ -L "$bin/bin/$program" ]; then
        if extras_missing "bin/$program" "$bin/bin/$program"; then
            install -Dm755 "$program" "$bin/bin/$program"
            # Separate invocations: nixpkgs issue #576412.
            patchelf --set-rpath "$out/lib:$libPath" "$bin/bin/$program"
            patchelf --set-interpreter "$(cat "$NIX_CC/nix-support/dynamic-linker")" "$bin/bin/$program"
        fi
        if extras_missing "origBin/$program" "$bin/origBin/$program"; then
            install -Dm755 "$program" "$bin/origBin/$program"
        fi
    fi
done

if [ -f nvidia_icd_vksc.json ] || [ -e "$out/share/vulkansc/icd.d/nvidia_icd.json" ] || [ -L "$out/share/vulkansc/icd.d/nvidia_icd.json" ]; then
    if extras_missing vulkansc/icd "$out/share/vulkansc/icd.d/nvidia_icd.json"; then
        jq --arg library "$out/lib/libnvidia-vksc-core.so.1" \
            '.ICD.library_path = $library' nvidia_icd_vksc.json > nvidia_icd_vksc.fixed.json
        install -Dm644 nvidia_icd_vksc.fixed.json "$out/share/vulkansc/icd.d/nvidia_icd.json"
    fi
fi

# Preserve the vendor inventory schema; this is not a Nix closure manifest.
if extras_missing sandboxutils/inventory "$bin/share/nvidia/files.d/sandboxutils-filelist.json"; then
    install -Dm644 sandboxutils-filelist.json "$bin/share/nvidia/files.d/sandboxutils-filelist.json"
fi

# No activation of network updates or writable model directory from packaging.
if extras_missing wine/ngx-updater "$out/lib/nvidia/wine/nvngx_update.exe"; then
    install -Dm755 nvngx_update.exe "$out/lib/nvidia/wine/nvngx_update.exe"
fi

mkdir -p "$out/nix-support"
jq '.upstreamComplete = (.addedByNixSb | length == 0)' \
    <<< "$extras_report" > "$extras_status"
echo "NIX_SB NVIDIA extras: $(jq -c . "$extras_status")"
if jq -e .upstreamComplete "$extras_status" >/dev/null; then
    echo "NIX_SB: nixpkgs provides all checked extras; the local NVIDIA supplement can be retired after validation."
fi
