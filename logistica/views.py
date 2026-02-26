import datetime
import csv
import io
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.db import transaction
from django.contrib import messages

# Importações dos Models locais
from .models import Visita, Cliente, Rota, Carteira, Ligacao

# --- CONSTANTES DE STATUS ---
STATUS_PENDENTE = 'PENDENTE'
STATUS_REALIZADA = 'REALIZADA'
STATUS_NAO_VENDA = 'NAO_VENDA'

# ==============================================================================
# FUNÇÕES UTILITÁRIAS E INTELIGÊNCIA
# ==============================================================================

def converter_valor(valor_str):
    """Converte strings monetárias (ex: 150,00) para Decimal de forma segura."""
    if not valor_str: return Decimal('0.00')
    try:
        valor_limpo = str(valor_str).replace('.', '').replace(',', '.')
        return Decimal(valor_limpo)
    except (InvalidOperation, ValueError):
        return Decimal('0.00')

def atualizar_inteligencia_consumo(cliente):
    """
    Calcula a média de dias entre as últimas compras (CMC) 
    para prever a próxima data de fim de gás.
    """
    historico = Visita.objects.filter(
        cliente=cliente, 
        status=STATUS_REALIZADA
    ).order_by('-data_visita')[:3]

    if len(historico) >= 2:
        intervalos = []
        for i in range(len(historico) - 1):
            delta = (historico[i].data_visita.date() - historico[i+1].data_visita.date()).days
            if delta > 0: intervalos.append(delta)
        
        if intervalos:
            cliente.ciclo_consumo_dias = sum(intervalos) / len(intervalos)
    
    cliente.data_ultima_venda = timezone.now().date()
    cliente.save()

# ==============================================================================
# MÓDULO DE ACESSO E TRÁFEGO
# ==============================================================================

@login_required
def home(request):
    """Controlador de Tráfego: Redireciona o utilizador conforme o seu perfil."""
    # 1. Gerentes/Staff -> Dashboard
    if request.user.is_staff: 
        return redirect('dashboard')
    
    # 2. Agentes Comerciais (Estagiários) -> Cockpit de Ligações
    if request.user.groups.filter(name='Agentes Comerciais').exists() or Carteira.objects.filter(agente_comercial=request.user).exists():
        return redirect('dash_comercial')

    # 3. Motoqueiros -> Lista de entregas do dia e Resumo
    hoje = timezone.now().date()
    visitas_pendentes = Visita.objects.select_related('cliente').filter(
        rota__motoqueiro=request.user,
        rota__data_criacao__date=hoje,
        status=STATUS_PENDENTE
    ).order_by('cliente__bairro', 'cliente__nome')
    
    visitas_finalizadas = Visita.objects.select_related('cliente').filter(
        rota__motoqueiro=request.user,
        rota__data_criacao__date=hoje,
    ).exclude(status=STATUS_PENDENTE).order_by('-data_visita')

    resumo_dia = visitas_finalizadas.aggregate(
        total_recebido=Sum('valor_recebido'),
        qtd_sucesso=Count('id', filter=Q(status=STATUS_REALIZADA)),
        qtd_falha=Count('id', filter=Q(status=STATUS_NAO_VENDA))
    )
    
    return render(request, 'logistica/dash_motoqueiro.html', {
        'visitas': visitas_pendentes,
        'visitas_finalizadas': visitas_finalizadas,
        'resumo_dia': resumo_dia
    })

# ==============================================================================
# MÓDULO OPERACIONAL (MOTOQUEIRO)
# ==============================================================================

@login_required
@transaction.atomic
def registrar_visita(request, id_visita):
    """Ecrã de baixa de entrega com Blindagem GPS."""
    visita = get_object_or_404(Visita.objects.select_related('cliente', 'rota'), pk=id_visita)
    
    if visita.rota.motoqueiro != request.user and not request.user.is_staff: 
        return redirect('home')

    if request.method == 'POST':
        resultado_venda = request.POST.get('resultado_venda')
        
        # --- CAPTURA DE GPS (Blindagem Operacional) ---
        try:
            visita.latitude_checkin = float(request.POST.get('lat'))
            visita.longitude_checkin = float(request.POST.get('lng'))
        except (TypeError, ValueError):
            pass # Mantém nulo caso o GPS tenha falhado

        if resultado_venda == 'SIM':
            valor = converter_valor(request.POST.get('valor_recebido'))
            visita.status = STATUS_REALIZADA
            visita.valor_recebido = valor
            visita.cliente.divida_atual -= valor
            visita.cliente.save()
            
            # Atualiza o robô de previsão de compras
            atualizar_inteligencia_consumo(visita.cliente)
            
            messages.success(request, f"Venda de R$ {valor} registada com sucesso.")
        else:
            visita.status = STATUS_NAO_VENDA
            visita.motivo_nao_venda = request.POST.get('motivo_nao_venda')
            visita.concorrente_empresa = request.POST.get('concorrente_empresa')
            visita.concorrente_preco = converter_valor(request.POST.get('concorrente_preco'))
            visita.observacao = request.POST.get('observacao')
            messages.info(request, "Visita finalizada como Não Venda.")

        visita.save()
        return redirect('home')

    return render(request, 'logistica/registrar_visita.html', {'visita': visita})

# ==============================================================================
# MÓDULO COMERCIAL (ESTAGIÁRIO / CALL CENTER)
# ==============================================================================

@login_required
def dash_comercial(request):
    """Cockpit de Alta Produtividade para o Agente Comercial."""
    carteiras = Carteira.objects.filter(agente_comercial=request.user)
    hoje = timezone.now().date()
    
    # Exclui clientes que já receberam ligação hoje para não repetir
    clientes_ja_ligados = Ligacao.objects.filter(
        agente=request.user, 
        data_ligacao__date=hoje
    ).values_list('cliente_id', flat=True)

    # Exibe clientes ordenados pelos que mais devem
    clientes = Cliente.objects.filter(
        carteiras__in=carteiras
    ).exclude(
        id__in=clientes_ja_ligados
    ).distinct().order_by('-divida_atual')

    ligacoes_hoje = Ligacao.objects.filter(agente=request.user, data_ligacao__date=hoje)
    
    metricas = {
        'total_feitas': ligacoes_hoje.count(),
        'vendas_fechadas': ligacoes_hoje.filter(resultado='VENDA_FECHADA').count(),
        'recusas': ligacoes_hoje.filter(resultado='RECUSA').count(),
        'meta_diaria': 400
    }

    return render(request, 'logistica/dash_comercial.html', {
        'clientes': clientes,
        'metricas': metricas
    })

@login_required
@transaction.atomic
def registrar_ligacao(request, cliente_id):
    """Processa o clique rápido de prospeção."""
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        resultado = request.POST.get('resultado')
        obs = request.POST.get('observacao', '')

        # Se houver data de reagendamento enviada (Follow-up)
        data_retorno_str = request.POST.get('data_agendamento')
        data_retorno = None
        if data_retorno_str:
            try:
                data_retorno = datetime.datetime.strptime(data_retorno_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        Ligacao.objects.create(
            agente=request.user, 
            cliente=cliente, 
            resultado=resultado, 
            observacao=obs,
            data_retorno=data_retorno
        )

        if resultado == 'VENDA_FECHADA':
            # Mágica de Automação: Envia a rota para o motoqueiro
            carteira = cliente.carteiras.first()
            motoqueiro = carteira.motoqueiro if carteira else None
            
            if motoqueiro:
                hoje = timezone.now().date()
                rota, _ = Rota.objects.get_or_create(
                    motoqueiro=motoqueiro, 
                    data_criacao__date=hoje,
                    defaults={'nome': f"Rota Comercial {hoje.strftime('%d/%m')}"}
                )
                Visita.objects.create(
                    rota=rota, 
                    cliente=cliente, 
                    status=STATUS_PENDENTE,
                    observacao=f"Venda Telemarketing ({request.user.username}): {obs}"
                )
                messages.success(request, f"Venda fechada! {motoqueiro.username} recebeu a entrega no app.")
            else:
                messages.warning(request, "Venda registada, mas cliente sem motoqueiro atribuído na carteira.")
        else:
            messages.info(request, f"Contacto registado: {resultado.replace('_', ' ')}")

    return redirect('dash_comercial')

# ==============================================================================
# MÓDULO GERENCIAL (DASHBOARD E AUDITORIA)
# ==============================================================================

@login_required
def dashboard(request):
    """Painel de Receitas e Desempenho com Filtro de Período."""
    if not request.user.is_staff: return redirect('home')
    
    # Captura as datas do GET
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    hoje = timezone.now().date()
    
    try:
        data_inicio = datetime.datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje
        data_fim = datetime.datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        data_inicio = hoje
        data_fim = hoje

    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio

    visitas_periodo = Visita.objects.filter(rota__data_criacao__date__gte=data_inicio, rota__data_criacao__date__lte=data_fim)
    
    resumo = visitas_periodo.aggregate(
        total_recebido=Sum('valor_recebido'),
        pendentes=Count('id', filter=Q(status=STATUS_PENDENTE)),
        vendas=Count('id', filter=Q(status=STATUS_REALIZADA)),
        concorrencia=Count('id', filter=Q(motivo_nao_venda='CONCORRENCIA')),
        estoque=Count('id', filter=Q(motivo_nao_venda='NAO_PRECISA'))
    )

    historico = visitas_periodo.select_related('cliente', 'rota__motoqueiro').order_by('-data_visita')
    qtd_ligacoes = Ligacao.objects.filter(data_ligacao__date__gte=data_inicio, data_ligacao__date__lte=data_fim).count()

    # Base Inativa para KPIs
    limite_inativo = hoje - datetime.timedelta(days=15)
    qtd_inativos = Cliente.objects.filter(
        Q(data_ultima_venda__lt=limite_inativo) | Q(data_ultima_venda__isnull=True)
    ).count()

    return render(request, 'logistica/dashboard.html', {
        'total_dinheiro': resumo['total_recebido'] or 0,
        'pendentes': resumo['pendentes'],
        'realizadas': (resumo['vendas'] or 0) + (resumo['concorrencia'] or 0) + (resumo['estoque'] or 0),
        'qtd_vendas': resumo['vendas'],
        'qtd_perdas': (resumo['concorrencia'] or 0) + (resumo['estoque'] or 0),
        'motivo_concorrencia': resumo['concorrencia'],
        'motivo_estoque': resumo['estoque'],
        'qtd_ligacoes': qtd_ligacoes,
        'qtd_inativos': qtd_inativos,
        'historico': historico,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    })

@login_required
def relatorio_auditoria(request):
    """O 'Dedo Duro' - Linha do tempo com lupa GPS e filtro de período."""
    if not request.user.is_staff: return redirect('home')
    
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    hoje = timezone.now().date()
    
    try:
        data_inicio = datetime.datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else hoje
        data_fim = datetime.datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else hoje
    except ValueError:
        data_inicio = hoje
        data_fim = hoje

    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio
    
    ligacoes = Ligacao.objects.filter(data_ligacao__date__gte=data_inicio, data_ligacao__date__lte=data_fim).select_related('agente', 'cliente').order_by('-data_ligacao')
    
    ranking = Ligacao.objects.filter(data_ligacao__date__gte=data_inicio, data_ligacao__date__lte=data_fim).values('agente__username').annotate(
        total=Count('id'),
        vendas=Count('id', filter=Q(resultado='VENDA_FECHADA'))
    ).order_by('-total')

    visitas_rua = Visita.objects.filter(
        data_visita__date__gte=data_inicio,
        data_visita__date__lte=data_fim
    ).exclude(status=STATUS_PENDENTE).select_related('cliente', 'rota__motoqueiro').order_by('-data_visita')

    return render(request, 'logistica/relatorio_auditoria.html', {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'ligacoes': ligacoes,
        'ranking_comercial': ranking,
        'visitas_rua': visitas_rua
    })

# ==============================================================================
# MESA DE PLANEAMENTO (DISTRIBUIÇÃO E IMPORTAÇÃO MASSIVA)
# ==============================================================================

@login_required
@transaction.atomic
def distribuir_rotas(request):
    """Gestão central de alocação e importação de clientes."""
    if not request.user.is_staff: return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        # --- IMPORTAÇÃO MASSIVA GLOBAL ---
        if acao == 'importar_csv':
            arquivo = request.FILES.get('arquivo_csv')
            if arquivo:
                try:
                    decoded = arquivo.read().decode('utf-8', errors='replace')
                    io_string = io.StringIO(decoded)
                    primeira_linha = io_string.readline()
                    delimiter = ';' if ';' in primeira_linha else ','
                    io_string.seek(0)
                    
                    reader = csv.reader(io_string, delimiter=delimiter)
                    header, col_map, contagem = [], {}, 0
                    
                    for row in reader:
                        row_clean = [str(c).strip() for c in row if c]
                        if not row_clean: continue
                        
                        if not header:
                            row_lower = [c.lower() for c in row_clean]
                            header = row_lower
                            for i, col in enumerate(header):
                                if 'nome resp' in col or ('nome' in col and 'nome' not in col_map): col_map['nome'] = i
                                elif 'endere' in col: col_map['endereco'] = i
                                elif 'número' in col or 'numero' in col: col_map['numero'] = i
                                elif 'bairro' in col: col_map['bairro'] = i
                                elif 'telefone' in col: col_map['telefone'] = i
                            continue

                        if header and 'nome' in col_map:
                            try:
                                raw_nome = row_clean[col_map['nome']]
                                if not raw_nome or raw_nome.isdigit(): continue
                                
                                end = row_clean[col_map.get('endereco', 0)] if 'endereco' in col_map else ""
                                num = row_clean[col_map.get('numero', 0)] if 'numero' in col_map else ""
                                bairro = row_clean[col_map.get('bairro', 0)] if 'bairro' in col_map else "Bairro não informado"
                                tel = row_clean[col_map.get('telefone', 0)] if 'telefone' in col_map else ""
                                
                                Cliente.objects.get_or_create(
                                    nome=raw_nome[:100],
                                    defaults={
                                        'endereco': f"{end}, {num}".strip(' ,-'),
                                        'bairro': bairro[:50],
                                        'telefone': tel.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')[:20]
                                    }
                                )
                                contagem += 1
                            except Exception: continue
                    messages.success(request, f"Sucesso! {contagem} novos clientes adicionados à base geral.")
                except Exception as e:
                    messages.error(request, f"Erro na leitura do ficheiro: {str(e)}")
            return redirect('distribuir_rotas')

        # --- DISTRIBUIÇÃO MANUAL DE ROTAS ---
        else:
            motoqueiro_id = request.POST.get('motoqueiro_id')
            c_ids = request.POST.getlist('clientes_ids')
            if motoqueiro_id and c_ids:
                motoqueiro = get_object_or_404(User, id=motoqueiro_id)
                rota = Rota.objects.create(nome=f"Rota {timezone.now().strftime('%d/%m')}", motoqueiro=motoqueiro)
                Visita.objects.bulk_create([Visita(rota=rota, cliente_id=int(cid)) for cid in c_ids])
                messages.success(request, f"Rota enviada para o telemóvel do {motoqueiro.username}.")
                return redirect('distribuir_rotas')

    bairro = request.GET.get('bairro')
    carteira_id = request.GET.get('carteira')
    status_filter = request.GET.get('status')
    
    clientes = Cliente.objects.all().order_by('bairro', 'nome')
    if bairro: clientes = clientes.filter(bairro=bairro)
    if carteira_id: clientes = clientes.filter(carteiras__id=carteira_id)
    
    # Filtros calculados dinamicamente (Inteligência)
    if status_filter == 'VIRADOS': 
        clientes = [c for c in clientes if c.is_virado]
    elif status_filter == 'ATRASADOS': 
        clientes = [c for c in clientes if c.is_atrasado]
    elif status_filter == 'SEM_HISTORICO': 
        clientes = [c for c in clientes if c.data_ultima_venda is None] # <-- O novo filtro para recém-importados

    context = {
        'clientes': clientes,
        'bairros': Cliente.objects.values_list('bairro', flat=True).distinct().order_by('bairro'),
        'carteiras': Carteira.objects.all(),
        'motoqueiros': User.objects.filter(is_staff=False),
        'filtro_bairro': bairro, 
        'filtro_carteira': int(carteira_id) if carteira_id else None, 
        'filtro_status': status_filter
    }
    return render(request, 'logistica/distribuir_rotas.html', context)

# ==============================================================================
# GESTÃO DE CARTEIRAS, CADASTROS E IMPORTAÇÃO DE ABA
# ==============================================================================

@login_required
def cadastrar_cliente(request):
    """Permite ao Gerente cadastrar um cliente rapidamente via Pop-up."""
    if not request.user.is_staff: return redirect('home')
    
    if request.method == 'POST':
        nome = request.POST.get('nome')
        telefone = request.POST.get('telefone', '')
        endereco = request.POST.get('endereco', '')
        bairro = request.POST.get('bairro', 'Não Informado')
        
        if nome:
            Cliente.objects.create(
                nome=nome,
                telefone=telefone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')[:20],
                endereco=endereco,
                bairro=bairro
            )
            messages.success(request, f"Cliente {nome} registado com sucesso!")
        else:
            messages.error(request, "O nome do cliente é obrigatório.")
            
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@login_required
def gerenciar_carteiras(request):
    """Lista e permite a criação/eliminação de grupos de clientes."""
    if not request.user.is_staff: return redirect('home')
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'criar':
            Carteira.objects.create(nome=request.POST.get('nome'), cor_etiqueta=request.POST.get('cor'))
        elif acao == 'excluir_carteira':
            Carteira.objects.filter(id=request.POST.get('id_carteira')).delete()
        return redirect('gerenciar_carteiras')
    return render(request, 'logistica/carteiras.html', {'carteiras': Carteira.objects.all().order_by('nome')})

@login_required
@transaction.atomic
def detalhes_carteira(request, id_carteira):
    """Gestão fina de uma carteira específica e o seu motor de importação."""
    if not request.user.is_staff: return redirect('home')
    carteira = get_object_or_404(Carteira, pk=id_carteira)
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        # Atribuições de Responsáveis
        if acao == 'definir_motoqueiro':
            carteira.motoqueiro_id = request.POST.get('motoqueiro_id')
            carteira.save()
        elif acao == 'remover_motoqueiro':
            carteira.motoqueiro = None
            carteira.save()
        elif acao == 'definir_agente':
            carteira.agente_comercial_id = request.POST.get('agente_id')
            carteira.save()
        elif acao == 'remover_agente':
            carteira.agente_comercial = None
            carteira.save()
        
        # Movimentação de Clientes Manuais
        elif acao == 'remover_cliente':
            carteira.clientes.remove(request.POST.get('remover_id'))
        elif acao == 'adicionar_clientes':
            ids = request.POST.getlist('clientes_ids')
            if ids: carteira.clientes.add(*ids)
        
        # MOTOR DE IMPORTAÇÃO RESILIENTE
        elif acao == 'importar_csv':
            arquivo = request.FILES.get('arquivo_csv')
            if arquivo:
                try:
                    decoded = arquivo.read().decode('utf-8', errors='replace')
                    io_string = io.StringIO(decoded)
                    primeira_linha = io_string.readline()
                    delimiter = ';' if ';' in primeira_linha else ','
                    io_string.seek(0)
                    
                    reader = csv.reader(io_string, delimiter=delimiter)
                    header, col_map, contagem = [], {}, 0
                    
                    for row in reader:
                        row_clean = [str(c).strip() for c in row if c]
                        if not row_clean: continue
                        
                        if not header:
                            row_lower = [c.lower() for c in row_clean]
                            header = row_lower
                            for i, col in enumerate(header):
                                if 'nome resp' in col or ('nome' in col and 'nome' not in col_map): col_map['nome'] = i
                                elif 'endere' in col: col_map['endereco'] = i
                                elif 'número' in col or 'numero' in col: col_map['numero'] = i
                                elif 'bairro' in col: col_map['bairro'] = i
                                elif 'telefone' in col: col_map['telefone'] = i
                            continue

                        if header and 'nome' in col_map:
                            try:
                                raw_nome = row_clean[col_map['nome']]
                                if not raw_nome or raw_nome.isdigit(): continue
                                
                                end = row_clean[col_map.get('endereco', 0)] if 'endereco' in col_map else ""
                                num = row_clean[col_map.get('numero', 0)] if 'numero' in col_map else ""
                                bairro = row_clean[col_map.get('bairro', 0)] if 'bairro' in col_map else "Bairro não informado"
                                tel = row_clean[col_map.get('telefone', 0)] if 'telefone' in col_map else ""
                                
                                cli_obj, _ = Cliente.objects.get_or_create(
                                    nome=raw_nome[:100],
                                    defaults={
                                        'endereco': f"{end}, {num}".strip(' ,-'),
                                        'bairro': bairro[:50],
                                        'telefone': tel.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')[:20]
                                    }
                                )
                                cli_obj.carteiras.add(carteira)
                                contagem += 1
                            except Exception: continue
                            
                    messages.success(request, f"Sucesso! {contagem} clientes incorporados nesta carteira.")
                except Exception as e:
                    messages.error(request, f"Erro na leitura: {str(e)}")
                    
        return redirect('detalhes_carteira', id_carteira=id_carteira)

    context = {
        'carteira': carteira, 
        'clientes': carteira.clientes.all().order_by('bairro', 'nome'),
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
        'clientes_livres': Cliente.objects.filter(carteiras__isnull=True).order_by('bairro', 'nome')
    }
    return render(request, 'logistica/detalhes_carteira.html', context)