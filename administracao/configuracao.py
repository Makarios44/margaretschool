"""Lê dados da escola: o que foi salvo na tela de Administração vale mais que o padrão de settings.py."""
from asgiref.local import Local
from django.conf import settings
from django.db import DatabaseError

CAMPOS_ESCOLA = [
    "nome", "cnpj", "inep", "mantenedora", "endereco", "cidade", "telefone",
    "ato_autorizacao", "diretor", "diretor_ato", "secretario", "secretario_ato",
    "instagram", "slogan", "apresentacao",
]

_estado = Local()  # dentro de uma requisição, a configuração é lida do banco uma vez só


def _config():
    from .models import ConfiguracaoEscola

    em_requisicao = getattr(_estado, "ativo", False)
    if em_requisicao and hasattr(_estado, "objeto"):
        return _estado.objeto
    try:
        objeto = ConfiguracaoEscola.objects.first()
    except DatabaseError:  # tabela ainda não criada (migrações em andamento)
        objeto = None
    if em_requisicao:
        _estado.objeto = objeto
    return objeto


def iniciar_requisicao():
    _estado.ativo = True
    if hasattr(_estado, "objeto"):
        del _estado.objeto


def encerrar_requisicao():
    _estado.ativo = False
    if hasattr(_estado, "objeto"):
        del _estado.objeto


def escola():
    dados = dict(settings.ESCOLA)
    cfg = _config()
    if cfg:
        for campo in CAMPOS_ESCOLA:
            valor = getattr(cfg, campo)
            if valor:
                dados[campo] = valor
    return dados


def financeiro():
    dados = dict(settings.FINANCEIRO)
    cfg = _config()
    if cfg:
        if cfg.multa_percentual is not None:
            dados["multa_percentual"] = cfg.multa_percentual
        if cfg.juros_mensal_percentual is not None:
            dados["juros_mensal_percentual"] = cfg.juros_mensal_percentual
    return dados


def calendario():
    dados = dict(settings.CALENDARIO)
    cfg = _config()
    if cfg:
        if cfg.calendario_uf:
            dados["uf"] = cfg.calendario_uf.upper()
        if cfg.calendario_municipio:
            dados["municipio"] = cfg.calendario_municipio
    return dados
