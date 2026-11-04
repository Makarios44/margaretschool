from django.contrib import admin

from .models import Album, Anuncio, Foto

admin.site.register(Anuncio)
admin.site.register(Album)
admin.site.register(Foto)
