#!/usr/bin/env bash
# Construit toutes les régions de métropole, une par une.
#
# Les sources nationales (ADMIN EXPRESS, Filosofi, Cerema, ODRÉ) restent en
# cache ; les fichiers régionaux (RPG, réponses WFS) sont supprimés après chaque
# région pour limiter l'espace disque. Usage :
#   scripts/build_all.sh            # toutes les régions
#   scripts/build_all.sh 11 53      # seulement celles-ci
set -euo pipefail
cd "$(dirname "$0")/.."

REGIONS=("$@")
if [ ${#REGIONS[@]} -eq 0 ]; then
  REGIONS=($(python -c "import yaml;print(' '.join(yaml.safe_load(open('../registry/regions.yaml'))['regions']))"))
fi

for r in "${REGIONS[@]}"; do
  echo "=== Région $r ==="
  python -m atlas_pipeline build --region "$r" 2>&1 | tee "cache/build_$r.log"
  # Nettoyage des sources régionales
  rm -rf cache/raw/rpg/*R${r}_* cache/raw/natura2000/*_${r}.geojson cache/raw/znieff1/*_${r}.geojson cache/raw/eaip_cours_eau/*_${r}* 2>/dev/null || true
  df -h . | tail -1
done
python -m atlas_pipeline index
