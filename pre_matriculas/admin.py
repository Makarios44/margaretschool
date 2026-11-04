from django.contrib import admin

from .models import LinkPreMatricula, SolicitacaoPreMatricula


@admin.register(LinkPreMatricula)
class LinkPreMatriculaAdmin(admin.ModelAdmin):
    list_display = ("ano_letivo", "criado_por", "criado_em", "expira_em", "ativo", "usado_em")
    list_filter = ("ativo", "ano_letivo")
    readonly_fields = ("token", "criado_em", "usado_em")


@admin.register(SolicitacaoPreMatricula)
class SolicitacaoPreMatriculaAdmin(admin.ModelAdmin):
    list_display = ("nome_crianca", "nome_responsavel", "telefone", "status", "enviada_em")
    list_filter = ("status", "link__ano_letivo")
    search_fields = ("nome_crianca", "nome_responsavel", "telefone", "email")
    readonly_fields = ("link", "enviada_em", "aluno_criado", "matricula_criada")
