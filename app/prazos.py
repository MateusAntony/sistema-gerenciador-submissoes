"""Prazos da chamada no fuso do evento.

dataAbertura/dataLimite são gravadas como strings locais "YYYY-MM-DDTHH:MM"
no fuso do evento (ex.: "2026-10-30T23:59" em America/Bahia). Toda
comparação com o relógio converte a string para um instante UTC aware.
"""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def agora_utc():
    return datetime.now(timezone.utc)


def _zona(fuso):
    try:
        return ZoneInfo(fuso) if fuso else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def instante_utc(texto, fuso, fim_do_dia=False):
    """Converte a string local para UTC aware. Só a data ("YYYY-MM-DD") vale
    00:00, ou 23:59:59 com fim_do_dia. Vazio ou inválido → None."""
    if not texto:
        return None
    try:
        local = datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        return None
    if fim_do_dia and len(texto) == 10:
        local = datetime.combine(local.date(), time(23, 59, 59))
    if local.tzinfo is None:
        local = local.replace(tzinfo=_zona(fuso))
    return local.astimezone(timezone.utc)


def chamada_encerrada(chamada, evento):
    """Encerrada manualmente ou com o prazo local já vencido."""
    if chamada.encerrada_manualmente:
        return True
    limite = instante_utc(chamada.data_limite, evento.fuso if evento else None, fim_do_dia=True)
    return limite is not None and agora_utc() > limite


def limite_posterior(limite, referencia, fuso, referencia_e_limite=False):
    """O instante de `limite` (só data = fim do dia) é posterior ao de
    `referencia` (uma abertura, ou outro limite com referencia_e_limite)?
    Sem como interpretar alguma das datas, compara as strings."""
    instante_limite = instante_utc(limite, fuso, fim_do_dia=True)
    instante_referencia = instante_utc(referencia, fuso, fim_do_dia=referencia_e_limite)
    if instante_limite is None or instante_referencia is None:
        return limite > referencia
    return instante_limite > instante_referencia
