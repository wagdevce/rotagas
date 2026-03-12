from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

# ==============================================================================
# NÚCLEO BASE (ENTIDADES PRINCIPAIS)
# ==============================================================================

class Cliente(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=255)
    bairro = models.CharField(max_length=100, default="Não Informado")
    telefone = models.CharField(max_length=20)
    
    # --- NOVOS CAMPOS DE CADASTRO ESTENDIDO ---
    documento = models.CharField(max_length=20, blank=True, null=True, help_text="CPF ou CNPJ")
    email = models.EmailField(max_length=255, blank=True, null=True)
    observacoes_gerais = models.TextField(blank=True, null=True)
    # ------------------------------------------
    
    # GPS
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    
    # Financeiro
    divida_atual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Inteligência Comercial (CMC)
    ciclo_consumo_dias = models.IntegerField(default=30, help_text="Média de dias entre as compras")
    data_ultima_venda = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.nome} - {self.bairro}"

    @property
    def dias_desde_ultima_compra(self):
        if not self.data_ultima_venda:
            return None
        return (timezone.now().date() - self.data_ultima_venda).days

    @property
    def is_atrasado(self):
        if not self.data_ultima_venda:
            return False 
        return self.dias_desde_ultima_compra > self.ciclo_consumo_dias

    @property
    def is_virado(self):
        if not self.data_ultima_venda:
            return False
        return self.dias_desde_ultima_compra > (self.ciclo_consumo_dias * 3)

    @property
    def data_proxima_compra(self):
        if self.data_ultima_venda:
            return self.data_ultima_venda + timedelta(days=self.ciclo_consumo_dias)
        return None

    @property
    def tags_visuais(self):
        tags = []
        if self.data_ultima_venda is None:
            tags.append({'texto': 'SEM HISTÓRICO', 'cor': 'info', 'icone': 'fa-asterisk'})
        elif self.is_virado:
            tags.append({'texto': 'VIRADO', 'cor': 'danger', 'icone': 'fa-skull-crossbones'})
        elif self.is_atrasado:
            tags.append({'texto': 'ATRASADO', 'cor': 'warning', 'icone': 'fa-clock'})
        return tags

class Carteira(models.Model):
    nome = models.CharField(max_length=50)
    cor_etiqueta = models.CharField(max_length=7, default="#F26522")
    motoqueiro = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='carteiras_logistica')
    agente_comercial = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='carteiras_comerciais')
    clientes = models.ManyToManyField(Cliente, blank=True, related_name='carteiras')

    def __str__(self):
        return self.nome

# ==============================================================================
# NÚCLEO LOGÍSTICO (MUNDO FÍSICO)
# ==============================================================================

class Rota(models.Model):
    nome = models.CharField(max_length=50)
    motoqueiro = models.ForeignKey(User, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.motoqueiro.username}"

class Visita(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('REALIZADA', 'Realizada'),
        ('NAO_VENDA', 'Não Venda / Recusa'),
    ]

    rota = models.ForeignKey(Rota, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    
    # ----------------------------------------------------
    # NOVOS DADOS DA VENDA (Preenchidos pelo Call Center)
    # ----------------------------------------------------
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    forma_pagamento = models.CharField(max_length=50, blank=True, null=True)
    tipo_botijao = models.CharField(max_length=50, blank=True, null=True)
    
    # Execução (Motoqueiro)
    valor_recebido = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    latitude_checkin = models.FloatField(blank=True, null=True)
    longitude_checkin = models.FloatField(blank=True, null=True)
    
    # Recusa e Obs
    motivo_nao_venda = models.CharField(max_length=50, blank=True, null=True)
    concorrente_empresa = models.CharField(max_length=50, blank=True, null=True)
    concorrente_preco = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    observacao = models.TextField(blank=True, null=True)
    data_visita = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cliente.nome} - {self.status}"

# ==============================================================================
# NÚCLEO COMERCIAL (MUNDO VIRTUAL)
# ==============================================================================

class Ligacao(models.Model):
    RESULTADO_CHOICES = [
        ('VENDA_FECHADA', 'Venda Fechada'),
        ('RECUSA', 'Recusa / Concorrência'),
        ('CAIXA_POSTAL', 'Sem Atender / Caixa Postal'),
        ('REAGENDADO', 'Retornar Depois'),
    ]

    agente = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    observacao = models.TextField(blank=True, null=True)
    data_ligacao = models.DateTimeField(auto_now_add=True)
    data_retorno = models.DateField(blank=True, null=True)
    
    # --- NOVOS CAMPOS DE INTELIGÊNCIA COMERCIAL ---
    motivo_nao_venda = models.CharField(max_length=50, blank=True, null=True)
    concorrente_empresa = models.CharField(max_length=50, blank=True, null=True)
    concorrente_preco = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Ligação para {self.cliente.nome} - {self.get_resultado_display()}"