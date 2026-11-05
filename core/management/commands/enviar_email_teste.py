from django.core.management.base import BaseCommand, CommandError

from core.emails import enviar


class Command(BaseCommand):
    help = "Envia um e-mail de teste para conferir a configuração (RESEND_API_KEY / EMAIL_HOST)."

    def add_arguments(self, parser):
        parser.add_argument("destino")

    def handle(self, *args, destino, **opcoes):
        try:
            enviar("Teste de e-mail – Margaret School", "Envio de e-mails funcionando.", None, [destino])
        except Exception as erro:
            raise CommandError(f"Falhou: {erro}")
        self.stdout.write(self.style.SUCCESS(f"Enviado para {destino}."))
