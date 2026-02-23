from django.contrib import admin
from django.urls import path, include
from logistica.views import (
    home, 
    registrar_visita, 
    dash_comercial, 
    registrar_ligacao,
    dashboard, 
    relatorio_auditoria, 
    distribuir_rotas, 
    gerenciar_carteiras, 
    detalhes_carteira,
    setup_inicial_nuvem  # Função de promoção de superuser
)

urlpatterns = [
    # Painel Administrativo Nativo do Django
    path('admin/', admin.site.urls),
    
    # Sistema de Autenticação (Login/Logout)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Rota Principal (Controlador de Tráfego)
    path('', home, name='home'),
    
    # URL DE EMERGÊNCIA: Aceda a esta rota para libertar o acesso total do Wagner
    path('setup-emergencia/', setup_inicial_nuvem, name='setup_emergencia'),

    # --- MÓDULO OPERACIONAL (MOTOQUEIRO) ---
    path('visita/<int:id_visita>/', registrar_visita, name='registrar_visita'),
    
    # --- MÓDULO COMERCIAL (ESTAGIÁRIO) ---
    path('comercial/', dash_comercial, name='dash_comercial'),
    path('comercial/ligar/<int:cliente_id>/', registrar_ligacao, name='registrar_ligacao'),
    
    # --- MÓDULO GERENCIAL (DONO/GERENTE) ---
    path('dashboard/', dashboard, name='dashboard'),
    path('auditoria/', relatorio_auditoria, name='relatorio_auditoria'),
    path('planejamento/', distribuir_rotas, name='distribuir_rotas'),
    
    # --- GESTÃO DE CARTEIRAS E IMPORTAÇÃO ---
    path('carteiras/', gerenciar_carteiras, name='gerenciar_carteiras'),
    path('carteiras/<int:id_carteira>/', detalhes_carteira, name='detalhes_carteira'),
]