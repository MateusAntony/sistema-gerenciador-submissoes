"""Ids vindos do corpo das requisições.

O front manda todos os ids como string (AD-030). Aceita-se inteiro ou texto
só com dígitos ASCII, positivo e dentro do bigint do Postgres.
"""
import re

MAIOR_ID = 2 ** 63 - 1


def id_numerico(valor):
    """O id como int, ou None se o valor não for um id válido."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        # [0-9], não str.isdigit(): este aceita dígitos Unicode ('²', '١') que int() recusa.
        valor = int(texto) if re.fullmatch(r'[0-9]+', texto) else None
    if not isinstance(valor, int) or not 0 < valor <= MAIOR_ID:
        return None
    return valor
