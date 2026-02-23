from django.contrib import admin
from django.urls import path, include

# Importação de todas as funções da lógica (views)
from logistica.views import (
    home, 
    registrar_visita, 
    dashboard, 
    relatorio_auditoria,  # <--- NOVA IMPORTAÇÃO
    distribuir_rotas, 
    gerenciar_carteiras, 
    detalhes_carteira,
    dash_comercial,
    registrar_ligacao
)

urlpatterns = [
    # 1. Painel Administrativo Nativo do Django
    path('admin/', admin.site.urls),
    
    # 2. Sistema de Autenticação (Login/Logout)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # 3. Rota Principal (Redirecionador Automático)
    path('', home, name='home'),
    
    # ==========================================================================
    # MÓDULO OPERACIONAL (MOTOQUEIRO)
    # ==========================================================================
    path('visita/<int:id_visita>/', registrar_visita, name='registrar_visita'),
    
    # ==========================================================================
    # MÓDULO COMERCIAL (ESTAGIÁRIO)
    # ==========================================================================
    path('comercial/', dash_comercial, name='dash_comercial'),
    path('comercial/ligar/<int:cliente_id>/', registrar_ligacao, name='registrar_ligacao'),
    
    # ==========================================================================
    # MÓDULO GERENCIAL (AUDITORIA E PLANEAMENTO)
    # ==========================================================================
    
    # Painel Financeiro e KPIs
    path('dashboard/', dashboard, name='dashboard'),
    
    # NOVO: Relatório de Auditoria e Fiscalização
    path('auditoria/', relatorio_auditoria, name='relatorio_auditoria'),
    
    # Mesa de Planeamento (Criação de Rotas de Rua)
    path('planejamento/', distribuir_rotas, name='distribuir_rotas'),
    
    # Gestão de Grupos de Clientes
    path('carteiras/', gerenciar_carteiras, name='gerenciar_carteiras'),
    path('carteiras/<int:id_carteira>/', detalhes_carteira, name='detalhes_carteira'),
]