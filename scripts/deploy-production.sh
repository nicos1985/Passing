#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR=/opt/passing/app
PYTHON=/opt/passing/.venv/bin/python
ENV_FILE=/etc/passing.env
BRANCH=${1:-gestion-documental}

case "$BRANCH" in
  main|gestion-documental) ;;
  *) echo 'Rama no permitida. Usá main o gestion-documental.' >&2; exit 1 ;;
esac

if (( EUID != 0 )); then
  echo 'Ejecutá este script con sudo.' >&2
  exit 1
fi
if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "$APP_DIR todavía no es un checkout Git. Completá primero la vinculación inicial." >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" || ! -x "$PYTHON" ]]; then
  echo 'Falta el entorno de producción o el Python del proyecto.' >&2
  exit 1
fi

git_app() { sudo -u passing -H git -C "$APP_DIR" "$@"; }
if [[ "$(git_app branch --show-current)" != "$BRANCH" ]]; then
  echo "El checkout de producción debe estar en la rama $BRANCH." >&2
  exit 1
fi
if [[ -n "$(git_app status --porcelain --untracked-files=no)" ]]; then
  echo 'Hay cambios locales en archivos versionados. Revisalos antes de actualizar:' >&2
  git_app status --short --untracked-files=no >&2
  exit 1
fi

git_app fetch origin "$BRANCH"
if ! git_app merge-base --is-ancestor HEAD "origin/$BRANCH"; then
  echo "La rama local y origin/$BRANCH divergieron; no se realizará una mezcla automática." >&2
  exit 1
fi

changed_files=$(git_app diff --name-only HEAD "origin/$BRANCH")
if grep -Eq '(^|/)migrations/[0-9][^/]*\.py$|^requirements[^/]*\.txt$' <<< "$changed_files"; then
  echo 'La actualización incluye migraciones o dependencias. Requiere un despliegue revisado.' >&2
  exit 1
fi

git_app merge --ff-only "origin/$BRANCH"

run_manage() {
  systemd-run --quiet --wait --pipe --collect \
    --property=User=passing \
    --property=Group=passing \
    --property="WorkingDirectory=$APP_DIR" \
    --property="EnvironmentFile=$ENV_FILE" \
    "$PYTHON" manage.py "$@"
}

run_manage migrate_schemas --check --noinput
run_manage collectstatic --noinput
systemctl restart passing-produccion.service passing-monitoring.service passing-supporthub.service
for service in passing-produccion.service passing-monitoring.service passing-supporthub.service; do
  systemctl is-active --quiet "$service" || { echo "$service no quedó activo." >&2; exit 1; }
done
echo "Passing actualizado a $(git_app rev-parse --short HEAD)."
