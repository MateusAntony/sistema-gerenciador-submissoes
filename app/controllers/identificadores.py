import uuid


def parse_uuid(valor):
    """Converte um id vindo do corpo ou da query string em uuid.UUID.

    Devolve None para vazio/None e levanta ValueError para formato inválido.
    """
    if valor is None or valor == '':
        return None
    if isinstance(valor, uuid.UUID):
        return valor
    return uuid.UUID(str(valor))
