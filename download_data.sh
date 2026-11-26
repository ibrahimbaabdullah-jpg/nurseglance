#!/usr/bin/env bash
# Download the two open MIMIC-IV demo datasets from PhysioNet into data/raw/
# and check them against PhysioNet's SHA-256 checksums.
#   - MIMIC-IV Clinical Database Demo on FHIR v2.1.0 (about 50 MB)
#   - MIMIC-IV Clinical Database Demo v2.2, CSV (about 16 MB)
# Needs wget (macOS: brew install wget). Windows: use Git Bash or WSL, or
# download the ZIP files from each dataset's PhysioNet page instead.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/raw
cd data/raw

for dataset in mimic-iv-fhir-demo/2.1.0 mimic-iv-demo/2.2; do
  echo "== Downloading ${dataset}"
  wget -r -N -c -np "https://physionet.org/files/${dataset}/"
  folder="physionet.org/files/${dataset}"
  if [ -f "${folder}/SHA256SUMS.txt" ]; then
    echo "== Checking ${dataset}"
    if command -v sha256sum >/dev/null; then
      (cd "${folder}" && sha256sum -c --quiet SHA256SUMS.txt) || echo "!! Some files in ${dataset} did not match SHA256SUMS.txt"
    else
      (cd "${folder}" && shasum -a 256 -c --quiet SHA256SUMS.txt) || echo "!! Some files in ${dataset} did not match SHA256SUMS.txt"
    fi
  fi
done
echo "Done. FHIR files: data/raw/physionet.org/files/mimic-iv-fhir-demo/2.1.0/fhir"
echo "      CSV files:  data/raw/physionet.org/files/mimic-iv-demo/2.2"
