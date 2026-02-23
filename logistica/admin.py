from django.contrib import admin
from .models import Cliente, Rota, Visita

# Configuração opcional para deixar a lista mais bonita
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone', 'divida_atual')
    search_fields = ('nome',)

class RotaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'motoqueiro', 'data_criacao')
    list_filter = ('motoqueiro',)

class VisitaAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'rota', 'status', 'valor_recebido')
    list_filter = ('status', 'rota')

# Registrando as tabelas
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(Rota, RotaAdmin)
admin.site.register(Visita, VisitaAdmin)
