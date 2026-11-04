from django.contrib import admin

from .models import AnoLetivo, DocumentoMatricula, Matricula, Turma


@admin.register(AnoLetivo)
class AnoLetivoAdmin(admin.ModelAdmin):
    list_display = ("ano", "atual")


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome", "etapa", "turno", "ano_letivo", "vagas", "ocupacao")
    list_filter = ("ano_letivo", "turno", "etapa")


class DocumentoInline(admin.TabularInline):
    model = DocumentoMatricula
    extra = 0


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "ano_letivo", "turma", "situacao")
    list_filter = ("ano_letivo", "situacao")
    search_fields = ("aluno__nome",)
    inlines = [DocumentoInline]
