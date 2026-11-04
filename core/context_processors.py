from administracao import configuracao


def escola(request):
    return {"escola": configuracao.escola(), "financeiro_cfg": configuracao.financeiro()}
