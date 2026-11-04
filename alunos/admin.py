from django.contrib import admin

from .models import Aluno, ContatoEmergencia, Responsavel


class ResponsavelInline(admin.TabularInline):
    model = Responsavel
    extra = 0


class ContatoInline(admin.TabularInline):
    model = ContatoEmergencia
    extra = 0


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("nome", "data_nascimento")
    search_fields = ("nome",)
    inlines = [ResponsavelInline, ContatoInline]
