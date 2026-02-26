from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# ==============================================================================
# NÚCLEO DE ORGANIZAÇÃO
# ==============================================================================

class Carteira(models.Model):
    """Agrupamento lógico de clientes atribuídos a responsáveis específicos."""
    nome = models.CharField(max_length=100)
    cor_etiqueta = models.CharField(max_length=7, default='#F26522', help_text="Código HEX da cor")
    
    # Responsáveis
    motoqueiro = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='carteiras_moto', help_text="Responsável pela entrega física"
    )
    agente_comercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='carteiras_venda', help_text="Responsável pelas ligações"
    )

    def __str__(self):
        return self.nome


# ==============================================================================
# NÚCLEO DE CLIENTES (INTELIGÊNCIA)
# ==============================================================================

class Cliente(models.Model):
    """Entidade principal com inteligência de consumo e histórico financeiro."""
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=255)
    bairro = models.CharField(max_length=100, default='Centro')
    telefone = models.CharField(max_length=20)
    divida_atual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Campos de Inteligência Comercial (CMC - Ciclo Médio de Consumo)
    ciclo_consumo_dias = models.IntegerField(default=30, help_text="Média de dias que o gás dura neste cliente")
    data_ultima_venda = models.DateField(null=True, blank=True)
    
    # Geocoding (Opcional/Futuro)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    
    carteiras = models.ManyToManyField(Carteira, related_name='clientes', blank=True)

    def __str__(self):
        return self.nome

    # --- PROPRIEDADES DE INTELIGÊNCIA ---

    @property
    def dias_desde_ultima_compra(self):
        if not self.data_ultima_venda:
            return 999
        return (timezone.now().date() - self.data_ultima_venda).days

    @property
    def is_atrasado(self):
        """Identifica se o cliente já passou do tempo médio de compra."""
        return self.dias_desde_ultima_compra > self.ciclo_consumo_dias

    @property
    def is_virado(self):
        """Identifica clientes perdidos (não compram há mais de 3 ciclos)."""
        return self.dias_desde_ultima_compra > (self.ciclo_consumo_dias * 3)

    @property
    def data_proxima_compra(self):
        if self.data_ultima_venda:
            return self.data_ultima_venda + timedelta(days=self.ciclo_consumo_dias)
        return None

    @property
    def tags_visuais(self):
        """Gera as etiquetas para a Mesa de Planeamento."""
        tags = []
        if self.is_virado:
            tags.append({'texto': 'VIRADO', 'cor': 'danger', 'icone': 'fa-skull-crossbones'})
        elif self.is_atrasado:
            tags.append({'texto': 'ATRASADO', 'cor': 'warning', 'icone': 'fa-clock'})
        
        if self.divida_atual > 0:
            tags.append({'texto': 'DÉBITO', 'cor': 'dark', 'icone': 'fa-hand-holding-dollar'})
        return tags


# ==============================================================================
# NÚCLEO LOGÍSTICO (MUNDO FÍSICO)
# ==============================================================================

class Rota(models.Model):
    """Agrupador diário de entregas para um motoqueiro."""
    nome = models.CharField(max_length=50)
    motoqueiro = models.ForeignKey(User, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.motoqueiro.username}"

class Visita(models.Model):
    """Ação física de visita ao cliente com captura de GPS para auditoria."""
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('REALIZADA', 'Venda Realizada'),
        ('NAO_VENDA', 'Não Vendeu'),
    ]

    rota = models.ForeignKey(Rota, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    
    # Financeiro
    valor_recebido = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    data_visita = models.DateTimeField(auto_now=True)
    observacao = models.TextField(blank=True, null=True)

    # --- BLINDAGEM OPERACIONAL (GPS) ---
    latitude_checkin = models.FloatField(blank=True, null=True)
    longitude_checkin = models.FloatField(blank=True, null=True)
    
    # Inteligência de Mercado (Recusa)
    motivo_nao_venda = models.CharField(max_length=50, blank=True, null=True)
    concorrente_empresa = models.CharField(max_length=50, blank=True, null=True)
    concorrente_preco = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0.00)

    def __str__(self):
        return f"{self.cliente.nome} - {self.status}"


# ==============================================================================
# NÚCLEO COMERCIAL (MUNDO VIRTUAL)
# ==============================================================================

class Ligacao(models.Model):
    """Registo de prospecção ativa do telemarketing."""
    RESULTADO_CHOICES = [
        ('VENDA_FECHADA', 'Venda Fechada'),
        ('RECUSA', 'Recusa'),
        ('CAIXA_POSTAL', 'Caixa Postal'),
        ('REAGENDADO', 'Ligar Depois'),
    ]
    
    agente = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    data_ligacao = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True, null=True)
    
    # Fila de Reagendamento (Follow-up)
    data_retorno = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.cliente.nome} - {self.resultado}"