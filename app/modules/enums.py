"""Tipos enumerados do banco, com os nomes da secao Data Models do design.

Os valores acompanham os tipos de dominio do front (`features/*/tipos.ts`), que sao a
fonte dos nomes do contrato.
"""

from app.extensions import db

papel_enum = db.Enum(
    "chair", "avaliador", "responsavel_etapa", name="papel_enum"
)

email_situacao_enum = db.Enum("enviado", "falha", name="email_situacao_enum")

solicitacao_situacao_enum = db.Enum(
    "pendente", "aprovada", "recusada", name="solicitacao_situacao_enum"
)

evento_situacao_enum = db.Enum(
    "pendente_aprovacao",
    "aprovado",
    "publicado",
    "encerrado",
    name="evento_situacao_enum",
)

evento_tipo_enum = db.Enum(
    "conferencia", "periodico", "chamada_interna", "outro", name="evento_tipo_enum"
)

modelo_avaliacao_enum = db.Enum(
    "aberta", "simples_cega", "duplo_cega", name="modelo_avaliacao_enum"
)

convite_tipo_enum = db.Enum("avaliacao", "participacao", name="convite_tipo_enum")

convite_situacao_enum = db.Enum(
    "pendente", "aceito", "expirado", name="convite_situacao_enum"
)
