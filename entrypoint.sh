#!/bin/sh
# Boot do container: o banco precisa responder e as migrations precisam estar
# aplicadas antes de a API aceitar a primeira requisicao (API-02 AC1).
set -e

echo "Aguardando o Postgres responder..."
python - <<'PY'
import os
import time

import psycopg2

url = os.environ["DATABASE_URL"]
for _ in range(30):
    try:
        psycopg2.connect(url).close()
        break
    except psycopg2.OperationalError:
        time.sleep(1)
else:
    raise SystemExit("O Postgres nao respondeu a tempo.")
PY

echo "Aplicando migrations..."
flask --app run db upgrade

exec "$@"
