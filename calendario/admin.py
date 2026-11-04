from django.contrib import admin

from .models import Evento, PeriodoLetivo


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "data_inicio", "data_fim", "sem_aula", "publico", "origem")
    list_filter = ("categoria", "sem_aula", "publico", "origem")
    search_fields = ("titulo",)
    date_hierarchy = "data_inicio"


@admin.register(PeriodoLetivo)
class PeriodoLetivoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ano_letivo", "inicio", "fim")
