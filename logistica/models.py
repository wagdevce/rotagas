from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

# --- CARTEIRA ---
class Carteira(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    cor_etiqueta = models.CharField(max_length=7, default="#6c757d")
    # Responsável de Rua
    motoqueiro = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='carteiras_fixas')
    # NOVO: Responsável de Escritório (Inside Sales / Estagiário)
    agente_comercial = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='carteiras_comerciais')

    def __str__(self):
        dono = f" ({self.motoqueiro.username})" if self.motoqueiro else ""
        return f"{self.nome}{dono}"

# --- CLIENTE ---
class Cliente(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=255)
    bairro = models.CharField(max_length=50, default="Centro")
    telefone = models.CharField(max_length=20)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    divida_atual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Suporte a múltiplas carteiras
    carteiras = models.ManyToManyField(Carteira, blank=True, related_name='clientes')

    def __str__(self):
        return f"{self.nome} - {self.bairro}"

    # --- INTELIGÊNCIA DE NEGÓCIO (PROPRIEDADES COMPUTADAS) ---

    @property
    def ultima_visita(self):
        """Retorna a visita mais recente registrada para este cliente."""
        return self.visita_set.order_by('-data_visita').first()

    @property
    def historico_vendas(self):
        """Retorna apenas visitas com venda realizada (Dinheiro entrou)."""
        return self.visita_set.filter(status='REALIZADA').order_by('-data_visita')

    @property
    def dias_desde_ultima_compra(self):
        """Dias corridos desde a última vez que comprou."""
        ultima_venda = self.historico_vendas.first()
        if ultima_venda:
            return (timezone.now() - ultima_venda.data_visita).days
        return None # Nunca comprou

    @property
    def media_consumo_dias(self):
        """
        Calcula o ciclo médio de compra do cliente.
        Se ele compra dia 1 e dia 13, a média é 12 dias.
        """
        vendas = list(self.historico_vendas[:5]) # Analisa as últimas 5 compras
        
        # Se tiver menos de 2 compras, não dá para calcular média real.
        # Assumimos 30 dias (padrão de gás de cozinha) ou 0 para indicar 'dados insuficientes'.
        if len(vendas) < 2:
            return 30 
        
        intervalos = []
        for i in range(len(vendas) - 1):
            # Diferença entre a venda atual e a anterior
            delta = (vendas[i].data_visita - vendas[i+1].data_visita).days
            intervalos.append(delta)
        
        if not intervalos: return 30
        
        # Retorna a média aritmética simples dos intervalos
        return sum(intervalos) / len(intervalos)

    @property
    def is_atrasado(self):
        """
        Regra: Passou da estimativa média?
        Ex: Média 12 dias. Se faz 13 dias que comprou, está atrasado.
        """
        dias_sem_comprar = self.dias_desde_ultima_compra
        if dias_sem_comprar is None: 
            return False # Nunca comprou, não tem como estar atrasado na recorrência
        
        estimativa = self.media_consumo_dias
        
        # Lógica estrita: Se passou 1 dia da média, já marca como atrasado.
        return dias_sem_comprar > estimativa

    @property
    def is_virado(self):
        """
        Regra: A última interação foi perda para concorrência?
        Se o motoqueiro foi lá hoje e marcou 'Comprou da Concorrência', ele é Virado.
        Se amanhã o motoqueiro for lá e vender, ele deixa de ser Virado.
        """
        ultima = self.ultima_visita
        # Verifica se existe visita e se o motivo registrado foi concorrência
        if ultima and ultima.motivo_nao_venda == 'CONCORRENCIA':
            return True
        return False

    @property
    def tags_visuais(self):
        """Gera as etiquetas visuais para o Frontend (HTML)."""
        tags = []
        
        # 1. Tag de Concorrência (Prioridade Alta)
        if self.is_virado:
            # Tenta pegar qual foi a marca que ele comprou para mostrar na tag
            ultima = self.ultima_visita
            marca = f" ({ultima.concorrente_empresa})" if ultima and ultima.concorrente_empresa else ""
            tags.append({'texto': f'VIRADO{marca}', 'cor': 'danger', 'icone': 'fa-exchange-alt'})
        
        # 2. Tag de Previsão de Consumo
        if self.is_atrasado:
            dias = self.dias_desde_ultima_compra
            tags.append({'texto': f'ATRASADO ({dias}d sem comprar)', 'cor': 'warning text-dark', 'icone': 'fa-history'})
        
        # 3. Tag de Recência (Cliente Ativo/Fiel)
        elif self.dias_desde_ultima_compra is not None and self.dias_desde_ultima_compra < 5:
            tags.append({'texto': 'COMPRA RECENTE', 'cor': 'success', 'icone': 'fa-check-circle'})
            
        return tags

# --- ROTA ---
class Rota(models.Model):
    nome = models.CharField(max_length=50)
    motoqueiro = models.ForeignKey(User, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.motoqueiro.username}"

# --- VISITA ---
class Visita(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('REALIZADA', 'Venda Realizada'),
        ('NAO_VENDA', 'Não Comprou / Outros'),
    ]

    MOTIVO_CHOICES = [
        ('NAO_PRECISA', 'Não precisa de gás no momento'),
        ('CONCORRENCIA', 'Comprou da Concorrência'),
        ('OUTROS', 'Outros / Ausente'),
    ]

    rota = models.ForeignKey(Rota, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    valor_recebido = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    observacao = models.TextField(blank=True, null=True)
    data_visita = models.DateTimeField(auto_now=True)
    
    # Dados de GPS
    latitude_checkin = models.FloatField(blank=True, null=True)
    longitude_checkin = models.FloatField(blank=True, null=True)
    
    # Inteligência de Mercado
    motivo_nao_venda = models.CharField(max_length=20, choices=MOTIVO_CHOICES, blank=True, null=True)
    data_agendamento = models.DateField(blank=True, null=True)
    concorrente_empresa = models.CharField(max_length=50, blank=True, null=True)
    concorrente_preco = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.cliente.nome} - {self.status}"

# ==============================================================================
# NOVO: MÓDULO COMERCIAL (TELEMARKETING)
# ==============================================================================

class Ligacao(models.Model):
    """
    Registro de interações ativas feitas pela equipe de Inside Sales (Estagiários).
    Isolado do modelo 'Visita' para garantir métricas limpas (Rua vs Escritório).
    """
    RESULTADO_CHOICES = [
        ('VENDA_FECHADA', 'Venda Fechada (Gerar Entrega)'),
        ('RECUSA', 'Não Quis / Concorrência / Acha Caro'),
        ('CAIXA_POSTAL', 'Caixa Postal / Não Atende / Número Errado'),
        ('REAGENDADO', 'Pediu para ligar mais tarde'),
    ]

    agente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ligacoes_realizadas')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='historico_ligacoes')
    
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    observacao = models.TextField(blank=True, null=True)
    
    # Audit tracking
    data_ligacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_resultado_display()}] {self.cliente.nome} (Por: {self.agente.username})"