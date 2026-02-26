from django.contrib import admin
from django.urls import path, include

# Importando todas as funções, EXCETO a de emergência que foi apagada
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
    cadastrar_cliente
)

urlpatterns = [
    # Painel Administrativo Oficial
    path('admin/', admin.site.urls),
    
    # Autenticação Segura
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Rota Principal (Direcionamento por Perfil)
    path('', home, name='home'),

    # --- MÓDULO OPERACIONAL (MOTOQUEIRO) ---
    path('visita/<int:id_visita>/', registrar_visita, name='registrar_visita'),
    
    # --- MÓDULO COMERCIAL (ESTAGIÁRIO) ---
    path('comercial/', dash_comercial, name='dash_comercial'),
    path('comercial/ligar/<int:cliente_id>/', registrar_ligacao, name='registrar_ligacao'),
    
    # --- MÓDULO GERENCIAL (DONO/GERENTE) ---
    path('dashboard/', dashboard, name='dashboard'),
    path('auditoria/', relatorio_auditoria, name='relatorio_auditoria'),
    path('planejamento/', distribuir_rotas, name='distribuir_rotas'),
    
    # --- CADASTROS E GESTÃO DE CARTEIRAS ---
    path('cliente/novo/', cadastrar_cliente, name='cadastrar_cliente'),
    path('carteiras/', gerenciar_carteiras, name='gerenciar_carteiras'),
    path('carteiras/<int:id_carteira>/', detalhes_carteira, name='detalhes_carteira'),
]