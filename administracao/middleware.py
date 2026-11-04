from . import configuracao


class ConfiguracaoMiddleware:
    """Faz a configuração da escola ser lida só uma vez por requisição."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        configuracao.iniciar_requisicao()
        try:
            return self.get_response(request)
        finally:
            configuracao.encerrar_requisicao()
