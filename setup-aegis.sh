#!/usr/bin/env bash
# Descarga la imagen Docker de Aegis desde los releases de GitHub y la carga
# localmente como  aegis:local  (el compose la usa con ese tag).
#
# La imagen NO está publicada en ghcr, así que no sirve 'docker pull'.
# El release trae un tarball que se carga con 'docker load'.
#
# Uso:
#   ./setup-aegis.sh              # usa el release 'latest'
#   ./setup-aegis.sh v1.0.1       # fija una versión
set -euo pipefail

REPO="divinelabio/aegis"
VERSION="${1:-latest}"

# Detectar arquitectura
case "$(uname -m)" in
  x86_64|amd64)  ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Arquitectura no soportada: $(uname -m)"; exit 1 ;;
esac

ASSET="aegis-docker-linux-${ARCH}.tar.gz"
if [ "$VERSION" = "latest" ]; then
  URL="https://github.com/${REPO}/releases/latest/download/${ASSET}"
else
  URL="https://github.com/${REPO}/releases/download/${VERSION}/${ASSET}"
fi

echo "==> Descargando imagen de Aegis (${ARCH}, ${VERSION})"
echo "    ${URL}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fSL "$URL" -o "${TMP}/${ASSET}"

echo "==> Cargando la imagen en Docker (docker load)"
# Capturamos la salida para descubrir con qué nombre quedó cargada.
LOAD_OUT="$(docker load -i "${TMP}/${ASSET}")"
echo "$LOAD_OUT"

# 'docker load' imprime algo como: "Loaded image: <nombre>:<tag>"
LOADED_IMG="$(echo "$LOAD_OUT" | sed -n 's/^Loaded image: //p' | head -1)"
if [ -z "$LOADED_IMG" ]; then
  LOADED_IMG="$(echo "$LOAD_OUT" | sed -n 's/^Loaded image ID: //p' | head -1)"
fi

if [ -z "$LOADED_IMG" ]; then
  echo "No pude detectar el nombre de la imagen cargada. Revisá 'docker images'."
  exit 1
fi

echo "==> Etiquetando ${LOADED_IMG}  ->  aegis:local"
docker tag "$LOADED_IMG" aegis:local

echo ""
echo "Listo. Imagen disponible como 'aegis:local'. Ahora:"
echo "    docker compose up -d"
