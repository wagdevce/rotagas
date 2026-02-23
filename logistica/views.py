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
from django.contrib.auth import login

# Importações dos Models locais
from .models import Visita, Cliente, Rota, Carteira, Ligacao

# --- CONSTANTES DE STATUS ---
STATUS_PENDENTE = 'PENDENTE'
STATUS_REALIZADA = 'REALIZADA'
STATUS_NAO_VENDA = 'NAO_VENDA'

def converter_valor(valor_str):
    """Converte strings monetárias para Decimal."""
    if not valor_str: return Decimal('0.00')
    try:
        valor_limpo = str(valor_str).replace('.', '').replace(',', '.')
        return Decimal(valor_limpo)
    except (InvalidOperation, ValueError):
        return Decimal('0.00')

# ==============================================================================
# FUNÇÃO DE EMERGÊNCIA: LOGIN AUTOMÁTICO NA NUVEM
# ==============================================================================
def setup_inicial_nuvem(request):
    try:
        wagner = User.objects.filter(username__iexact='wagner').first()
        if wagner:
            wagner.is_staff = True
            wagner.is_superuser = True
            wagner.save()

        admin_user, _ = User.objects.get_or_create(username='admin')
        admin_user.set_password('admin123')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        user_to_login = wagner if wagner else admin_user
        login(request, user_to_login)

        return redirect('/admin/')
    except Exception as e:
        return render(request, 'logistica/base.html', {
            'messages': [{'tags': 'danger', 'text': f"❌ Erro crítico: {str(e)}"}]
        })

# ==============================================================================
# FLUXO OPERACIONAL
# ==============================================================================
@login_required
def home(request):
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

    return render(request, 'logistica/dash_motoqueiro.html', {'visitas': visitas_pendentes})

@login_required
@transaction.atomic
def registrar_visita(request, id_visita):
    visita = get_object_or_404(Visita.objects.select_related('cliente', 'rota'), pk=id_visita)

    if visita.rota.motoqueiro != request.user and not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST':
        resultado_venda = request.POST.get('resultado_venda')

        if resultado_venda == 'SIM':
            valor = converter_valor(request.POST.get('valor_recebido'))
            visita.status = STATUS_REALIZADA
            visita.valor_recebido = valor
            visita.cliente.divida_atual -= valor
            visita.cliente.save()
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
# FLUXO COMERCIAL
# ==============================================================================
@login_required
def dash_comercial(request):
    carteiras = Carteira.objects.filter(agente_comercial=request.user)
    hoje = timezone.now().date()

    clientes_ja_ligados = Ligacao.objects.filter(
        agente=request.user,
        data_ligacao__date=hoje
    ).values_list('cliente_id', flat=True)

    clientes = Cliente.objects.filter(carteiras__in=carteiras).exclude(id__in=clientes_ja_ligados).distinct().order_by('-divida_atual')
    ligacoes_hoje = Ligacao.objects.filter(agente=request.user, data_ligacao__date=hoje)

    metricas = {
        'total_feitas': ligacoes_hoje.count(),
        'vendas_fechadas': ligacoes_hoje.filter(resultado='VENDA_FECHADA').count(),
        'recusas': ligacoes_hoje.filter(resultado='RECUSA').count(),
        'meta_diaria': 400
    }
    return render(request, 'logistica/dash_comercial.html', {'clientes': clientes, 'metricas': metricas})

@login_required
@transaction.atomic
def registrar_ligacao(request, cliente_id):
    if request.method == 'POST':
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        resultado = request.POST.get('resultado')
        obs = request.POST.get('observacao', '')

        Ligacao.objects.create(agente=request.user, cliente=cliente, resultado=resultado, observacao=obs)

        if resultado == 'VENDA_FECHADA':
            carteira = cliente.carteiras.first()
            motoqueiro = carteira.motoqueiro if carteira else None

            if motoqueiro:
                hoje = timezone.now().date()
                rota, _ = Rota.objects.get_or_create(
                    motoqueiro=motoqueiro,
                    data_criacao__date=hoje,
                    defaults={'nome': f"Rota Comercial {hoje.strftime('%d/%m')}"}
                )
                Visita.objects.create(rota=rota, cliente=cliente, status=STATUS_PENDENTE, observacao=f"Venda Telemarketing {obs}")
                messages.success(request, f"Venda fechada! {motoqueiro.username} recebeu a entrega.")
            else:
                messages.warning(request, "Venda registada, mas cliente sem motoqueiro atribuído.")
        else:
            messages.info(request, f"Contacto registado: {resultado}")

    return redirect('dash_comercial')

# ==============================================================================
# GESTÃO E PLANEJAMENTO
# ==============================================================================
@login_required
def dashboard(request):
    if not request.user.is_staff: return redirect('home')

    data_url = request.GET.get('data')
    try:
        data_filtro = datetime.datetime.strptime(data_url, '%Y-%m-%d').date() if data_url else timezone.now().date()
    except ValueError:
        data_filtro = timezone.now().date()

    visitas_hoje = Visita.objects.filter(rota__data_criacao__date=data_filtro)

    resumo = visitas_hoje.aggregate(
        total_recebido=Sum('valor_recebido'),
        pendentes=Count('id', filter=Q(status=STATUS_PENDENTE)),
        vendas=Count('id', filter=Q(status=STATUS_REALIZADA)),
        concorrencia=Count('id', filter=Q(motivo_nao_venda='CONCORRENCIA')),
        estoque=Count('id', filter=Q(motivo_nao_venda='NAO_PRECISA'))
    )

    historico = visitas_hoje.select_related('cliente', 'rota__motoqueiro').order_by('-data_visita')
    qtd_ligacoes = Ligacao.objects.filter(data_ligacao__date=data_filtro).count()

    return render(request, 'logistica/dashboard.html', {
        'total_dinheiro': resumo['total_recebido'] or 0,
        'pendentes': resumo['pendentes'],
        'realizadas': (resumo['vendas'] or 0) + (resumo['concorrencia'] or 0) + (resumo['estoque'] or 0),
        'qtd_vendas': resumo['vendas'],
        'qtd_perdas': (resumo['concorrencia'] or 0) + (resumo['estoque'] or 0),
        'motivo_concorrencia': resumo['concorrencia'],
        'motivo_estoque': resumo['estoque'],
        'qtd_ligacoes': qtd_ligacoes,
        'historico': historico,
        'data_atual': data_filtro,
    })

@login_required
def relatorio_auditoria(request):
    if not request.user.is_staff: return redirect('home')

    data_str = request.GET.get('data')
    data_obj = datetime.datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else timezone.now().date()

    ligacoes = Ligacao.objects.filter(data_ligacao__date=data_obj).select_related('agente', 'cliente').order_by('data_ligacao')

    ranking = Ligacao.objects.filter(data_ligacao__date=data_obj).values('agente__username').annotate(
        total=Count('id'),
        vendas=Count('id', filter=Q(resultado='VENDA_FECHADA'))
    ).order_by('-total')

    visitas_rua = Visita.objects.filter(data_visita__date=data_obj, status__in=[STATUS_REALIZADA, STATUS_NAO_VENDA]).select_related('cliente', 'rota__motoqueiro').order_by('data_visita')

    return render(request, 'logistica/relatorio_auditoria.html', {
        'data_selecionada': data_obj,
        'ligacoes': ligacoes,
        'ranking_comercial': ranking,
        'visitas_rua': visitas_rua
    })

@login_required
def distribuir_rotas(request):
    if not request.user.is_staff: return redirect('home')

    # Filtros restaurados!
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

    if request.method == 'POST':
        motoqueiro = get_object_or_404(User, id=request.POST.get('motoqueiro_id'))
        c_ids = request.POST.getlist('clientes_ids')
        if c_ids:
            rota = Rota.objects.create(nome=f"Rota {timezone.now().strftime('%d/%m')}", motoqueiro=motoqueiro)
            Visita.objects.bulk_create([Visita(rota=rota, cliente_id=cid) for cid in c_ids])
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
# CADASTRO E IMPORTAÇÃO
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
            carteira.motoqueiro_id = request.POST.get('motoqueiro_id')
        elif acao == 'remover_motoqueiro':
            carteira.motoqueiro = None
        elif acao == 'definir_agente':
            carteira.agente_comercial_id = request.POST.get('agente_id')
        elif acao == 'remover_agente':
            carteira.agente_comercial = None
        elif acao == 'remover_cliente':
            carteira.clientes.remove(request.POST.get('remover_id'))
        elif acao == 'adicionar_clientes':
            ids = request.POST.getlist('clientes_ids')
            if ids: carteira.clientes.add(*ids)
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

        carteira.save()
        return redirect('detalhes_carteira', id_carteira=id_carteira)

    context = {
        'carteira': carteira,
        'clientes': carteira.clientes.all().order_by('bairro', 'nome'),
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
        'clientes_livres': Cliente.objects.filter(carteiras__isnull=True).order_by('bairro', 'nome')
    }
    return render(request, 'logistica/detalhes_carteira.html', context)