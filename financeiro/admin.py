from django.contrib import admin

from .models import Cobranca


@admin.register(Cobranca)
class CobrancaAdmin(admin.ModelAdmin):
    list_display = ("descricao", "matricula", "vencimento", "valor", "desconto", "situacao")
    list_filter = ("situacao", "tipo", "forma_pagamento")
    search_fields = ("matricula__aluno__nome", "descricao")
