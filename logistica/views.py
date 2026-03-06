import datetime
import csv
import io
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.db import transaction, connection
from django.contrib import messages
from django.core.management import call_command
from django.contrib.auth import login

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
        # Limpa pontos de milhar e troca vírgula por ponto decimal
        valor_limpo = str(valor_str).replace('.', '').replace(',', '.')
        return Decimal(valor_limpo)
    except (InvalidOperation, ValueError):
        return Decimal('0.00')

def atualizar_inteligencia_consumo(cliente):
    """Calcula a média de dias entre compras para inteligência de IA."""
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
# FUNÇÃO DE EMERGÊNCIA: CRIAR TABELAS E FORÇAR LOGIN
# ==============================================================================

def setup_inicial_nuvem(request):
    """
    Mantido conforme a versão antiga do usuário para segurança de acesso.
    """
    try:
        call_command('migrate', interactive=False)
        wagner, _ = User.objects.get_or_create(username__iexact='wagner', defaults={'username': 'Wagner'})
        wagner.set_password('admin123')
        wagner.is_staff = True
        wagner.is_superuser = True
        wagner.save()

        admin_user, _ = User.objects.get_or_create(username='admin')
        admin_user.set_password('admin123')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        login(request, wagner)
        return redirect('/admin/')
    except Exception as e:
        return render(request, 'logistica/base.html', {
            'messages': [{'tags': 'danger', 'text': f"❌ Erro Crítico: {str(e)}"}]
        })

# ==============================================================================
# MÓDULO DE ACESSO E TRÁFEGO
# ==============================================================================

@login_required
def home(request):
    """Controlador de Tráfego: Redireciona o utilizador conforme o seu perfil."""
    if request.user.is_staff: 
        return redirect('dashboard')
    
    if request.user.groups.filter(name='Agentes Comerciais').exists() or Carteira.objects.filter(agente_comercial=request.user).exists():
        return redirect('dash_comercial')

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
    visita = get_object_or_404(Visita.objects.select_related('cliente', 'rota'), pk=id_visita)
    
    if visita.rota.motoqueiro != request.user and not request.user.is_staff: 
        return redirect('home')

    if request.method == 'POST':
        resultado_venda = request.POST.get('resultado_venda')
        
        try:
            visita.latitude_checkin = float(request.POST.get('lat'))
            visita.longitude_checkin = float(request.POST.get('lng'))
        except (TypeError, ValueError):
            pass

        if resultado_venda == 'SIM':
            valor = converter_valor(request.POST.get('valor_recebido'))
            visita.status = STATUS_REALIZADA
            visita.valor_recebido = valor
            visita.cliente.save()
            atualizar_inteligencia_consumo(visita.cliente)
            messages.success(request, f"Venda de R$ {valor} registada para {visita.cliente.nome}.")
        else:
            visita.status = STATUS_NAO_VENDA
            visita.motivo_nao_venda = request.POST.get('motivo_nao_venda')
            visita.concorrente_empresa = request.POST.get('concorrente_empresa')
            visita.concorrente_preco = converter_valor(request.POST.get('concorrente_preco'))
            visita.observacao = request.POST.get('observacao')
            messages.info(request, "Visita finalizada sem venda.")

        visita.save()
        return redirect('home')

    return render(request, 'logistica/registrar_visita.html', {'visita': visita})

# ==============================================================================
# MÓDULO COMERCIAL (ESTAGIÁRIO / CALL CENTER)
# ==============================================================================

@login_required
def dash_comercial(request):
    """Cockpit de Alta Produtividade. Corrigido o envio de motoqueiros para o modal."""
    carteiras = Carteira.objects.filter(agente_comercial=request.user)
    hoje = timezone.now().date()
    
    clientes_ja_ligados_ids = Ligacao.objects.filter(
        agente=request.user, 
        data_ligacao__date=hoje
    ).values_list('cliente_id', flat=True)

    # 1. Fila de Retornos (Agendados)
    ligacoes_retorno_brutas = Ligacao.objects.filter(
        agente=request.user,
        resultado='REAGENDADO',
        data_retorno__lte=hoje
    ).exclude(
        cliente_id__in=clientes_ja_ligados_ids
    ).select_related('cliente').order_by('data_retorno', '-data_ligacao')

    retornos_unicos = {}
    for lig in ligacoes_retorno_brutas:
        if lig.cliente_id not in retornos_unicos:
            retornos_unicos[lig.cliente_id] = lig
            
    lista_retornos = list(retornos_unicos.values())
    ids_clientes_retorno = [lig.cliente_id for lig in lista_retornos]

    # 2. Mailing Principal
    clientes_principais = Cliente.objects.filter(
        carteiras__in=carteiras
    ).exclude(
        id__in=clientes_ja_ligados_ids
    ).exclude(
        id__in=ids_clientes_retorno
    ).distinct().order_by('nome')

    ligacoes_hoje = Ligacao.objects.filter(agente=request.user, data_ligacao__date=hoje)
    
    metricas = {
        'total_feitas': ligacoes_hoje.count(),
        'vendas_fechadas': ligacoes_hoje.filter(resultado='VENDA_FECHADA').count(),
        'recusas': ligacoes_hoje.filter(resultado='RECUSA').count(),
        'meta_diaria': 400
    }

    # FIX: Povoa o dropdown de motoqueiros no modal de despacho!
    motoqueiros = User.objects.filter(is_staff=False, is_superuser=False, is_active=True).order_by('username')

    return render(request, 'logistica/dash_comercial.html', {
        'clientes_principais': clientes_principais,
        'lista_retornos': lista_retornos,
        'metricas': metricas,
        'motoqueiros': motoqueiros
    })

@login_required
@transaction.atomic
def registrar_ligacao(request, cliente_id):
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        resultado = request.POST.get('resultado')
        obs = request.POST.get('observacao', '')

        data_retorno_str = request.POST.get('data_agendamento')
        data_retorno = None
        if data_retorno_str:
            try:
                data_retorno = datetime.datetime.strptime(data_retorno_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        Ligacao.objects.create(agente=request.user, cliente=cliente, resultado=resultado, observacao=obs, data_retorno=data_retorno)

        if resultado == 'VENDA_FECHADA':
            # FIX: Agora o sistema captura do Modal o Motoqueiro, o Valor e a Forma de Pagamento
            motoqueiro_id = request.POST.get('motoqueiro_id')
            if motoqueiro_id:
                motoqueiro = get_object_or_404(User, id=motoqueiro_id)
                valor_venda = converter_valor(request.POST.get('valor_venda'))
                forma_pagamento = request.POST.get('forma_pagamento', '')
                tipo_botijao = request.POST.get('tipo_botijao', '')
                
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
                    valor_venda=valor_venda,
                    forma_pagamento=forma_pagamento,
                    tipo_botijao=tipo_botijao,
                    observacao=f"Venda Telemarketing ({request.user.username}): {obs}"
                )
                messages.success(request, f"Venda despachada para o motoqueiro {motoqueiro.username}!")
            else:
                messages.error(request, "Erro: Tem de selecionar o Motoqueiro para despachar.")
        else:
            messages.info(request, f"Contacto registado: {resultado.replace('_', ' ')}")

    return redirect('dash_comercial')

# ==============================================================================
# MÓDULO GERENCIAL (DASHBOARD E AUDITORIA)
# ==============================================================================

@login_required
def dashboard(request):
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

@login_required
def distribuir_rotas(request):
    if not request.user.is_staff: return redirect('home')
    
    bairro = request.GET.get('bairro')
    carteira_id = request.GET.get('carteira')
    status_filter = request.GET.get('status')
    
    clientes = Cliente.objects.all().order_by('bairro', 'nome')
    if bairro: clientes = clientes.filter(bairro=bairro)
    if carteira_id: clientes = clientes.filter(carteiras__id=carteira_id)
    
    if status_filter == 'VIRADOS': 
        clientes = [c for c in clientes if c.is_virado]
    elif status_filter == 'ATRASADOS': 
        clientes = [c for c in clientes if c.is_atrasado]
    elif status_filter == 'SEM_HISTORICO': 
        clientes = [c for c in clientes if c.data_ultima_venda is None]

    if request.method == 'POST':
        acao = request.POST.get('acao')
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
                    messages.error(request, f"Erro na leitura: {str(e)}")
            return redirect('distribuir_rotas')
        else:
            motoqueiro_id = request.POST.get('motoqueiro_id')
            c_ids = request.POST.getlist('clientes_ids')
            if motoqueiro_id and c_ids:
                motoqueiro = get_object_or_404(User, id=motoqueiro_id)
                rota = Rota.objects.create(nome=f"Rota {timezone.now().strftime('%d/%m')}", motoqueiro=motoqueiro)
                Visita.objects.bulk_create([Visita(rota=rota, cliente_id=int(cid)) for cid in c_ids])
                messages.success(request, f"Rota enviada para {motoqueiro.username}.")
                return redirect('distribuir_rotas')

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
# GESTÃO DE CARTEIRAS E CADASTRO
# ==============================================================================

@login_required
def cadastrar_cliente(request):
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
            messages.success(request, f"Cliente {nome} cadastrado com sucesso!")
        else:
            messages.error(request, "O nome do cliente é obrigatório.")
            
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@login_required
def gerenciar_carteiras(request):
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
    if not request.user.is_staff: return redirect('home')
    carteira = get_object_or_404(Carteira, pk=id_carteira)
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'definir_motoqueiro':
            motoqueiro_id = request.POST.get('motoqueiro_id')
            if motoqueiro_id:
                carteira.motoqueiro = get_object_or_404(User, id=motoqueiro_id)
                carteira.save()
                messages.success(request, f"Motoqueiro {carteira.motoqueiro.username} definido!")
        
        elif acao == 'remover_motoqueiro':
            carteira.motoqueiro = None
            carteira.save()
            messages.info(request, "Motoqueiro removido da carteira.")
            
        elif acao == 'definir_agente':
            agente_id = request.POST.get('agente_id')
            if agente_id:
                carteira.agente_comercial = get_object_or_404(User, id=agente_id)
                carteira.save()
                messages.success(request, f"Comercial {carteira.agente_comercial.username} definido!")
                
        elif acao == 'remover_agente':
            carteira.agente_comercial = None
            carteira.save()
            messages.info(request, "Agente Comercial removido da carteira.")
        
        elif acao == 'remover_cliente':
            carteira.clientes.remove(request.POST.get('remover_id'))
            messages.info(request, "Cliente removido da carteira.")
            
        elif acao == 'adicionar_clientes':
            ids = request.POST.getlist('clientes_ids')
            if ids: 
                carteira.clientes.add(*ids)
                messages.success(request, f"{len(ids)} clientes adicionados à carteira!")
        
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
                            
                    messages.success(request, f"Sucesso! {contagem} clientes incorporados.")
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


# ==============================================================================
# PERFIL E CRM (GERENCIAMENTO INDIVIDUAL DO CLIENTE)
# ==============================================================================

@login_required
def detalhes_cliente(request, id_cliente):
    """NOVO: Ecrã de CRM - Perfil individual, edição e histórico do cliente."""
    if not request.user.is_staff: return redirect('home')
    cliente = get_object_or_404(Cliente, pk=id_cliente)

    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'editar':
            cliente.nome = request.POST.get('nome', cliente.nome)
            cliente.telefone = request.POST.get('telefone', cliente.telefone).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')[:20]
            cliente.endereco = request.POST.get('endereco', cliente.endereco)
            cliente.bairro = request.POST.get('bairro', cliente.bairro)
            cliente.documento = request.POST.get('documento', '')
            cliente.email = request.POST.get('email', '')
            cliente.observacoes_gerais = request.POST.get('observacoes_gerais', '')
            cliente.save()
            messages.success(request, f"Ficha de {cliente.nome} atualizada com sucesso!")
            return redirect('detalhes_cliente', id_cliente=cliente.id)
            
        elif acao == 'excluir':
            nome_apagado = cliente.nome
            cliente.delete()
            messages.success(request, f"O cliente '{nome_apagado}' foi excluído permanentemente.")
            return redirect('distribuir_rotas')

    # Histórico para mostrar na tela do perfil
    historico_visitas = Visita.objects.filter(cliente=cliente).order_by('-data_visita')[:15]
    historico_ligacoes = Ligacao.objects.filter(cliente=cliente).order_by('-data_ligacao')[:15]

    context = {
        'cliente': cliente,
        'historico_visitas': historico_visitas,
        'historico_ligacoes': historico_ligacoes
    }
    return render(request, 'logistica/detalhes_cliente.html', context)