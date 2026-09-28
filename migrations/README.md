# Migrações

`init-scripts/` monta um banco novo (o contêiner do Postgres os executa na
criação do volume). Para um banco que já existe, aplique aqui, em ordem, os
arquivos de número maior que o último já aplicado:

```
docker exec -i sgs_postgres psql -U sgs -d <banco> -v ON_ERROR_STOP=1 < migrations/13-submissoes-codigo-por-id.sql
```

Todas são idempotentes: aplicar de novo não muda nada.
