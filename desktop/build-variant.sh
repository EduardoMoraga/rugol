#!/bin/bash
# Empaqueta una variante (rugol|crm|hro): ensambla el payload con sus agentes +
# marca, y construye el .dmg. Reusa el python relocatable y el dashboard (branded
# en runtime por env vía /api/health), así que solo cambian templates + marca.
set -e
cd "$(dirname "$0")"
V="${1:?uso: build-variant.sh rugol|crm|hro}"
VDIR="variants/$V"
[ -d "$VDIR" ] || { echo "variante desconocida: $V"; exit 1; }
PAY=build-payload
[ -d "$PAY/python" ] || { echo "falta build-payload/python (arma el payload primero)"; exit 1; }

# marca
cp "$VDIR/brand.json" "$PAY/brand.json"
# agentes (cada variante define su flota completa)
rm -rf "$PAY/rugol-src/agents-templates"
cp -R "$VDIR/agents-templates" "$PAY/rugol-src/agents-templates"
# skills opcionales de la variante (se suman a las de plataforma)
if [ -d "$VDIR/skills-templates" ] && [ -n "$(ls -A "$VDIR/skills-templates" 2>/dev/null)" ]; then
  cp -R "$VDIR/skills-templates/." "$PAY/rugol-src/skills-templates/"
fi

case "$V" in
  rugol) PN="Rugol";     AID="com.eduardomoraga.rugol";;
  crm)   PN="Rugol CRM"; AID="com.eduardomoraga.rugol.crm";;
  hro)   PN="Rugol HRO"; AID="com.eduardomoraga.rugol.hro";;
esac
# Ícono propio por variante (generarlo si falta).
[ -f "assets/icon-$V.icns" ] || ./node_modules/.bin/electron make-icon.cjs "$V"
echo "== build variante $V → '$PN' (icono: assets/icon-$V.icns) =="
npx electron-builder --mac dmg \
  --config.productName="$PN" \
  --config.appId="$AID" \
  --config.mac.icon="assets/icon-$V.icns" \
  --config.directories.output="release-$V"
