#!/usr/bin/env bash
# Ejecutado por el workflow como calco-github-actions. No ejecuta SQL.
set -Eeuo pipefail
umask 077

release_id=${1:?Falta release_id}
registry_user=${2:?Falta usuario de GHCR}
domain=${3:?Falta dominio}
[[ "$release_id" =~ ^[a-f0-9]{40}-[0-9]+-[0-9]+$ ]] || exit 2
registry_user_pattern='^[a-zA-Z0-9_-]+(\[bot\])?$'
[[ "$registry_user" =~ $registry_user_pattern ]] || exit 2
[[ "$domain" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$ ]] || exit 2

base="$HOME/event-attendance-app"
release="$base/releases/$release_id"
[[ -d "$release" && -f "$release/.env.production" && -f "$release/compose.env" ]] || exit 2
if [[ -e "$base/current" && ! -L "$base/current" ]]; then
  echo 'La ruta current existe y no es un enlace de despliegue.' >&2
  exit 2
fi

for command in docker curl flock; do
  command -v "$command" >/dev/null || { echo "Falta instalar $command en la VM." >&2; exit 2; }
done
docker info >/dev/null
compose_version=$(docker compose version --short)
compose_version=${compose_version#v}
if [[ "$(printf '%s\n' 2.30.0 "$compose_version" | sort -V | head -n1)" != 2.30.0 ]]; then
  echo 'Se requiere Docker Compose >= 2.30.0.' >&2
  exit 2
fi

# También evita solapamientos con una ejecución manual en la VM.
exec 9>"$base/deploy.lock"
flock -w 600 9
previous=$(readlink -f "$base/current" || true)
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf -- "$DOCKER_CONFIG"' EXIT
IFS= read -r registry_token
printf '%s' "$registry_token" | docker login ghcr.io --username "$registry_user" --password-stdin >/dev/null
unset registry_token

compose() {
  local directory=$1
  shift
  docker compose --project-name event-attendance-app \
    --env-file "$directory/compose.env" -f "$directory/docker-compose.yml" "$@"
}

# --quiet evita que las credenciales resueltas aparezcan en los logs.
compose "$release" config --quiet
compose "$release" pull

rollback() {
  echo 'El despliegue no quedó saludable; intentando restaurar la versión anterior.' >&2
  if [[ -n "$previous" && "$previous" == "$base/releases/"* && -f "$previous/compose.env" ]]; then
    compose "$previous" up -d --no-build --pull never --wait --wait-timeout 180
  else
    compose "$release" stop
  fi
}

if ! compose "$release" up -d --no-build --pull never --wait --wait-timeout 180; then
  rollback
  exit 1
fi

# Verifica DNS, certificado válido, Caddy y conexión del backend a MySQL.
if ! curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors \
  --connect-timeout 5 --max-time 10 "https://$domain/healthz" >/dev/null; then
  rollback
  exit 1
fi

ln -sfn "$release" "$base/current"
echo "Despliegue saludable: https://$domain (release $release_id)"
