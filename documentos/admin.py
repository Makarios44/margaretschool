from django.contrib import admin

from .models import ComponenteRegistro, DocumentoEmitido, RegistroEscolar


class ComponenteInline(admin.TabularInline):
    model = ComponenteRegistro
    extra = 0


@admin.register(RegistroEscolar)
class RegistroEscolarAdmin(admin.ModelAdmin):
    list_display = ("matricula", "resultado", "dias_letivos", "faltas")
    inlines = [ComponenteInline]


@admin.register(DocumentoEmitido)
class DocumentoEmitidoAdmin(admin.ModelAdmin):
    list_display = ("numero", "tipo", "aluno", "emitido_em", "anulado")
    list_filter = ("tipo", "anulado", "ano")
    search_fields = ("aluno__nome",)
    readonly_fields = ("conteudo",)
