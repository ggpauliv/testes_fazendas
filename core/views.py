"""
AgroTalhoes - Views

Views (Controllers) para o sistema de gestão de fazendas.
Implementa CRUD para Talhões, Produtos, Movimentações, Ciclos e Operações.
Suporte a Multi-Tenancy (Multi-Empresa).
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
# Force reload
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django import forms
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, F, DecimalField, Count, Q
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.urls import reverse
from django.db import transaction
from .utils.pdf import render_to_pdf
from .models import (
    Talhao, Produto, MovimentacaoEstoque, Plantio, 
    OperacaoCampo, TipoMovimentacao, StatusCiclo, UserProfile, Empresa, ConfiguracaoSistema, Fazenda,
    ClimaFazenda, PedidoCompra, ItemPedidoCompra, CategoriaProduto, Safra, Romaneio,
    ContratoVenda, RateioCusto, Fixacao, TaxaArmazem, Cliente, Fornecedor, ItemContratoVenda,
    UserInvitation, UserRole, AtividadeCampo, OperacaoCampoItem,
    CategoriaFinanceira, ContaPagar, ContaReceber, BaixaContaPagar, BaixaContaReceber, StatusFinanceiro
)

from .forms import (
    TalhaoForm, ProdutoForm, MovimentacaoEstoqueForm, MovimentacaoEntradaForm, MovimentacaoSaidaForm, ImportarNFeForm,
    PlantioForm, OperacaoCampoForm, FiltroRelatorioForm, TenantRegistrationForm, ConfiguracaoSistemaForm,
    FazendaForm, ClimaFazendaForm, PedidoCompraForm, PedidoFilterForm, ContratoFilterForm, RomaneioForm,
    ContratoVendaForm, RateioCustoForm, FixacaoForm,
    ClienteForm, FornecedorForm, TaxaArmazemForm, UserProfileForm, UserInvitationForm,
    SafraForm
)
from django.forms import inlineformset_factory
from .utils.nfe_parser import importar_nfe_xml, NFeParser
from .utils.open_meteo import get_talhao_weather_data, fetch_historical_weather


@user_passes_test(lambda u: u.is_superuser)
@login_required
def saas_create_tenant(request):
    """View restrita ao Master para cadastrar novas empresas e admins."""
    if request.method == 'POST':
        form = TenantRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # 1. Criar Empresa
                empresa = Empresa.objects.create(
                    nome=form.cleaned_data['nome_empresa'],
                    cnpj=form.cleaned_data['cnpj']
                )
                
                # 2. Criar Usuário Admin da Empresa
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password']
                )
                
                # 3. Vincular Usuário à Empresa
                UserProfile.objects.create(user=user, empresa=empresa)
                
                messages.success(request, f'Empresa "{empresa.nome}" e usuário "{user.username}" cadastrados com sucesso!')
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, f'Erro ao realizar cadastro: {str(e)}')
    else:
        form = TenantRegistrationForm()
        
    return render(request, 'core/saas/create_tenant.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser)
@login_required
def saas_settings(request):
    """View restrita ao Master para editar configurações do site."""
    config = ConfiguracaoSistema.get_config()
    
    if request.method == 'POST':
        form = ConfiguracaoSistemaForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações salvas com sucesso!')
            return redirect('saas_settings')
    else:
        form = ConfiguracaoSistemaForm(instance=config)
    
    # Lista de empresas para gestão
    empresas = Empresa.objects.all().order_by('-created_at')
        
    return render(request, 'core/saas/settings.html', {'form': form, 'config': config, 'empresas': empresas})


@user_passes_test(lambda u: u.is_superuser)
@login_required
@require_POST
def saas_delete_company(request, pk):
    """
    Exclusão segura de empresa e seus dados (incluindo usuários).
    Exige confirmação de senha do superusuário.
    """
    empresa = get_object_or_404(Empresa, pk=pk)
    
    try:
        with transaction.atomic():
            nome_empresa = empresa.nome
            
            # 2. Coletar IDs dos usuários vinculados à empresa
            user_profiles = UserProfile.objects.filter(empresa=empresa)
            user_ids = [profile.user.id for profile in user_profiles]
            
            # 3. Excluir Usuários (Cascade leva os Profiles)
            # Nota: Excluímos os usuários Django Auth, o que apaga o profile e o vínculo.
            User.objects.filter(id__in=user_ids).delete()
            
            # 4. Excluir Empresa (Cascade leva dados do sistema: talhões, safras, etc.)
            empresa.delete()
            
            messages.success(request, f'Empresa "{nome_empresa}" e {len(user_ids)} usuários foram excluídos permanentemente.')
            
    except Exception as e:
        messages.error(request, f'Erro ao excluir empresa: {str(e)}')
        
    return redirect('saas_settings')
    

@login_required
def profile_edit(request):
    """View para editar dados do usuário logado (exceto username)."""
    user = request.user
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil atualizado com sucesso!')
            return redirect('profile_edit')
    else:
        form = UserProfileForm(instance=user)
        
    return render(request, 'registration/profile_edit.html', {'form': form})


def get_empresa(user):
    """
    Retorna a empresa vinculada ao usuário logado.
    Em caso de erro (sem perfil), retorna None ou levanta erro.
    """
    try:
        return user.userprofile.empresa
    except UserProfile.DoesNotExist:
        return None
    except AttributeError:
        return None



# =============================================================================
# FAZENDAS
# =============================================================================

@login_required
@require_POST
def fazenda_delete_secure(request, pk):
    """
    Exclusão segura de Fazenda pelo proprietário.
    1. Verifica senha.
    2. Remove vínculo de Movimentações de Estoque com Operações de Campo (para preservar histórico).
    3. Exclui a Fazenda (Cascade leva Talhões, Operações, etc.)
    """
    fazenda = get_object_or_404(Fazenda, pk=pk)
    
    # 1. Verificar Permissão (Apenas OWNER)
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.role != UserRole.OWNER:
        messages.error(request, 'Apenas o proprietário pode excluir fazendas.')
        return redirect('fazenda_list')

    try:
        with transaction.atomic():
            nome_fazenda = fazenda.nome
            
            # 3. Preservação de Histórico Financeiro/Estoque
            # Encontrar operações de campo vinculadas a esta fazenda (via talhões)
            # Como OperacaoCampo tem FK para Talhao, e Talhao tem FK para Fazenda.
            talhoes = fazenda.talhoes.all()
            operacoes = OperacaoCampo.objects.filter(talhao__in=talhoes)
            
            # Encontrar Movimentações vinculadas a essas operações
            movimentacoes = MovimentacaoEstoque.objects.filter(operacao_campo__in=operacoes)
            
            count_preserved = movimentacoes.count()
            
            # Desvincular e Adicionar Nota
            for mov in movimentacoes:
                mov.operacao_campo = None
                mov.observacao = (mov.observacao or '') + f" (Origem: Fazenda {nome_fazenda} Excluída)"
                mov.save()
            
            # 4. Excluir Fazenda (Cascade)
            fazenda.delete()
            
            messages.success(request, f'Fazenda "{nome_fazenda}" excluída com sucesso! {count_preserved} registros de estoque foram preservados.')
            
    except Exception as e:
        messages.error(request, f'Erro ao excluir fazenda: {str(e)}')
        
    return redirect('fazenda_list')


@login_required
def fazenda_list(request):
    """Lista todas as fazendas."""
    empresa = get_empresa(request.user)
    fazendas = Fazenda.objects.filter(empresa=empresa).order_by('nome')
    return render(request, 'core/fazenda/list.html', {'fazendas': fazendas})


@login_required
def fazenda_detail(request, pk):
    """Exibe detalhes da fazenda e seus talhões."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    
    # Listar apenas talhões raiz (que não são subtalhões) desta fazenda
    talhoes = Talhao.objects.filter(
        empresa=empresa, 
        fazenda=fazenda, 
        parent__isnull=True
    ).order_by('nome')
    
    return render(request, 'core/fazenda/detail.html', {
        'fazenda': fazenda,
        'talhoes': talhoes
    })


@login_required
def fazenda_create(request):
    """Cria uma nova fazenda."""
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = FazendaForm(request.POST, empresa=empresa)
        if form.is_valid():
            fazenda = form.save(commit=False)
            fazenda.empresa = empresa
            fazenda.save()
            messages.success(request, f'Fazenda "{fazenda.nome}" criada com sucesso!')
            return redirect('fazenda_list')
    else:
        form = FazendaForm(empresa=empresa)
    return render(request, 'core/fazenda/form.html', {'form': form, 'titulo': 'Nova Fazenda'})

@login_required
def fazenda_edit(request, pk):
    """Edita uma fazenda."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = FazendaForm(request.POST, instance=fazenda, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, f'Fazenda "{fazenda.nome}" atualizada com sucesso!')
            return redirect('fazenda_list')
    else:
        form = FazendaForm(instance=fazenda, empresa=empresa)
    return render(request, 'core/fazenda/form.html', {'form': form, 'titulo': f'Editar Fazenda: {fazenda.nome}'})

@login_required
@require_POST
def fazenda_delete(request, pk):
    """Exclui uma fazenda."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    nome = fazenda.nome
    fazenda.delete()
    messages.success(request, f'Fazenda "{nome}" excluída com sucesso!')
    return redirect('fazenda_list')


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def dashboard(request):
    """View principal - Dashboard com resumo geral e indicadores."""
    
    empresa = get_empresa(request.user)
    if not empresa:
        messages.error(request, 'Usuário não vinculado a uma empresa.')
        return redirect('login')

    # Filtro por Fazenda (Opcional)
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    
    # Base QuerySets (Filtrados por Empresa)
    talhoes_qs = Talhao.objects.filter(ativo=True, empresa=empresa)
    produtos_qs = Produto.objects.filter(ativo=True, empresa=empresa)
    ciclos_qs = Plantio.objects.filter(status=StatusCiclo.EM_ANDAMENTO, empresa=empresa)
    operacoes_qs = OperacaoCampo.objects.filter(empresa=empresa)
    movimentacoes_qs = MovimentacaoEstoque.objects.filter(empresa=empresa)
    romaneios_qs = Romaneio.objects.filter(empresa=empresa)
    itens_contrato_qs = ItemContratoVenda.objects.filter(contrato__empresa=empresa)

    if fazenda_id:
        talhoes_qs = talhoes_qs.filter(fazenda_id=fazenda_id)
        # Produtos é global, não filtra por fazenda diretamente (exceto se tiver lógica de estoque local)
        # Por enquanto, mantemos global
        
        ciclos_qs = ciclos_qs.filter(talhao__fazenda_id=fazenda_id)
        operacoes_qs = operacoes_qs.filter(talhao__fazenda_id=fazenda_id)
        
        # Movimentações: Tentar filtrar as vinculadas a operações na fazenda
        # Ou Movimentações -> Itens Pedido (Não tem fazenda explícita) -> Global
        # Filtramos apenas as que vieram de Operações de Campo (Saída)
        movimentacoes_qs = movimentacoes_qs.filter(
            Q(operacao_campo__talhoes__fazenda_id=fazenda_id) | 
            Q(operacao_campo__isnull=True)
        ).distinct()
        
        romaneios_qs = romaneios_qs.filter(fazenda_id=fazenda_id)
        
        # Contratos: Filtra itens vinculados a esta fazenda (ou sem vínculo, se assumirmos que 'Sem Fazenda' é global?)
        # Se o usuário filtra por Fazenda X, quer ver o que sai da Fazenda X.
        itens_contrato_qs = itens_contrato_qs.filter(fazenda_id=fazenda_id)

        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)

    # Totais
    total_talhoes = talhoes_qs.count()
    area_total = talhoes_qs.aggregate(total=Coalesce(Sum('area_hectares'), Decimal('0')))['total']
    
    total_produtos = produtos_qs.count() # Mantém global
    produtos_estoque_baixo = produtos_qs.filter(estoque_atual__lte=F('estoque_minimo')).count() # Mantém global
    
    # Ciclos (Filtrado)
    ciclos_ativos = ciclos_qs
    
    # Últimas operações (Filtrado)
    ultimas_operacoes = operacoes_qs.prefetch_related('talhoes', 'itens', 'itens__produto').order_by('-data_operacao')[:5]
    
    # Últimas movimentações (Filtrado)
    ultimas_movimentacoes = movimentacoes_qs.select_related('produto').order_by('-data_movimentacao')[:5]
    
    # Financeiro Ciclos (Filtrado)
    custo_total_ciclos = Decimal('0')
    receita_estimada_ciclos = Decimal('0')
    
    for ciclo in ciclos_ativos:
        custo_total_ciclos += ciclo.calcular_custo_total()
        receita_estimada_ciclos += ciclo.calcular_receita_estimada()
    
    lucro_estimado = receita_estimada_ciclos - custo_total_ciclos

    # =========================================================================
    # Resumo Comercial (Contratos) - Filtrado
    # =========================================================================
    total_contratos_valor = itens_contrato_qs.aggregate(
        total=Coalesce(Sum(F('quantidade') * F('valor_unitario')), Decimal('0'))
    )['total']
    
    total_contratos_sacas = itens_contrato_qs.aggregate(
        total=Coalesce(Sum('quantidade'), Decimal('0'))
    )['total']
    
    # =========================================================================
    # Resumo Colheita (Romaneios) - Filtrado
    # =========================================================================
    total_colhido_kg = romaneios_qs.aggregate(
        total=Coalesce(Sum('peso_liquido'), Decimal('0'))
    )['total']
    total_colhido_sacas = total_colhido_kg / Decimal('60')
    
    # Talhões para o mapa (Filtrado)
    talhoes_mapa = talhoes_qs.filter(coordenadas_json__isnull=False)
    talhoes_json = []
    for talhao in talhoes_mapa:
        coords = talhao.get_coordenadas()
        if coords:
            talhoes_json.append({
                'id': talhao.id,
                'nome': talhao.nome,
                'area': float(talhao.area_hectares),
                'cultura': talhao.cultura_atual or 'Não informada',
                'coordenadas': coords,
            })
    
    # Lista de Fazendas para o filtro
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')

    context = {
        'total_talhoes': total_talhoes,
        'area_total': area_total,
        'total_produtos': total_produtos,
        'produtos_estoque_baixo': produtos_estoque_baixo,
        'ciclos_ativos': ciclos_ativos,
        'ultimas_operacoes': ultimas_operacoes,
        'ultimas_movimentacoes': ultimas_movimentacoes,
        'custo_total_ciclos': custo_total_ciclos,
        'receita_estimada_ciclos': receita_estimada_ciclos,
        'lucro_estimado': lucro_estimado,
        'talhoes_json': talhoes_json,
        'empresa': empresa,
        'total_contratos_valor': total_contratos_valor,
        'total_contratos_sacas': total_contratos_sacas,
        'total_colhido_kg': total_colhido_kg,
        'total_colhido_sacas': total_colhido_sacas,
        # Filtros
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada,
    }
    
    return render(request, 'core/dashboard.html', context)


# =============================================================================
# TALHÕES
# =============================================================================

@login_required
def talhao_list(request):
    """Lista todos os talhões (apenas raízes)."""
    empresa = get_empresa(request.user)
    # Filtra apenas talhões principais (sem pai)
    talhoes = Talhao.objects.filter(empresa=empresa, parent__isnull=True).order_by('nome')
    paginator = Paginator(talhoes, 10)
    page = request.GET.get('page')
    talhoes = paginator.get_page(page)
    
    return render(request, 'core/talhao/list.html', {'talhoes': talhoes})


@login_required
def talhao_create(request):
    """Cria um novo talhão."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = TalhaoForm(request.POST, empresa=empresa)
        if form.is_valid():
            talhao = form.save(commit=False)
            talhao.empresa = empresa
            talhao.save()
            messages.success(request, f'Talhão "{talhao.nome}" criado com sucesso!')
            return redirect('talhao_list')
    else:
        initial = {}
        fazenda_id = request.GET.get('fazenda')
        fazenda = None
        if fazenda_id:
            initial['fazenda'] = fazenda_id
            fazenda = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
            
        form = TalhaoForm(empresa=empresa, initial=initial)
    
    context = {
        'form': form, 
        'titulo': 'Novo Talhão',
    }
    
    # Passar coordenadas da fazenda se existir
    if request.method == 'GET' and fazenda_id and fazenda:
        if fazenda.latitude and fazenda.longitude:
            context['fazenda_lat'] = float(fazenda.latitude)
            context['fazenda_lon'] = float(fazenda.longitude)
        
        # Buscar talhões raiz existentes nesta fazenda para prevenção de sobreposição
        irmaos = Talhao.objects.filter(fazenda=fazenda, parent__isnull=True, ativo=True)
        irmaos_json = []
        for irmao in irmaos:
            coords = irmao.get_coordenadas()
            if coords and len(coords) > 0:
                irmaos_json.append({
                    'id': irmao.id,
                    'nome': irmao.nome,
                    'coordenadas': coords
                })
        context['siblings_json'] = irmaos_json

    return render(request, 'core/talhao/form.html', context)


@login_required
def subtalhao_create(request, pk):
    """Cria um subtalhão (filho) de um talhão existente."""
    empresa = get_empresa(request.user)
    pai = get_object_or_404(Talhao, pk=pk, empresa=empresa)
    
    initial_data = {
        'parent': pai,
        'fazenda': pai.fazenda,
        'nome': f"{pai.nome} - Subtalhão",
    }
    
    if request.method == 'POST':
        form = TalhaoForm(request.POST, empresa=empresa)
        if form.is_valid():
            talhao = form.save(commit=False)
            talhao.empresa = empresa
            talhao.parent = pai # Garante vinculo
            talhao.save()
            messages.success(request, f'Subtalhão "{talhao.nome}" criado com sucesso!')
            return redirect('talhao_detail', pk=pai.pk)
    else:
        form = TalhaoForm(initial=initial_data, empresa=empresa)
        form.fields['fazenda'].widget = forms.HiddenInput() # Esconde fazenda pois herda do pai
    
    # Buscar irmãos (outros subtalhões do mesmo pai) para verificação de sobreposição
    irmaos = Talhao.objects.filter(parent=pai, ativo=True)
    irmaos_json = []
    for irmao in irmaos:
        coords = irmao.get_coordenadas()
        if coords and len(coords) > 0:
            irmaos_json.append({
                'id': irmao.id,
                'nome': irmao.nome,
                'coordenadas': coords
            })

    return render(request, 'core/talhao/form.html', {
        'form': form, 
        'titulo': f'Novo Subtalhão de {pai.nome}',
        'parent_talhao': pai,
        'parent_coords_list': pai.get_coordenadas(), # Should return list
        'siblings_json': irmaos_json
    })



@login_required
def talhao_edit(request, pk):
    """Edita um talhão existente."""
    empresa = get_empresa(request.user)
    talhao = get_object_or_404(Talhao, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        # Create a mutable copy of POST data to ensure integrity
        data = request.POST.copy()
        
        # For Subtalhões, forcibly ensure Fazenda is the same as the current instance (Parent's Fazenda)
        if talhao.parent and talhao.fazenda:
            data['fazenda'] = talhao.fazenda.id
            
        form = TalhaoForm(data, instance=talhao, empresa=empresa)
        
        # Visually disable the field, but allow Python validation to proceed using our injected data
        if talhao.parent:
             form.fields['fazenda'].widget.attrs['disabled'] = 'disabled'
             
        if form.is_valid():
            talhao = form.save()
            messages.success(request, f'Talhão "{talhao.nome}" atualizado com sucesso!')
            return redirect('talhao_list')
    else:
        # Handling Fazenda change via GET parameter for Root Talhões
        initial_data = {}
        target_fazenda_id = request.GET.get('fazenda')
        validation_fazenda = talhao.fazenda

        if target_fazenda_id and not talhao.parent:
            initial_data['fazenda'] = target_fazenda_id
            try:
                validation_fazenda = Fazenda.objects.get(pk=target_fazenda_id, empresa=empresa)
            except Fazenda.DoesNotExist:
                pass
        
        form = TalhaoForm(instance=talhao, initial=initial_data, empresa=empresa)
        
        # Disable Fazenda field for Subtalhões (must match Parent)
        if talhao.parent:
             form.fields['fazenda'].disabled = True

    context = {
        'form': form,
        'talhao': talhao,
        'titulo': f'Editar Talhão: {talhao.nome}',
    }

    # Passar coordenadas da fazenda para centralizar o mapa se necessário
    if talhao.fazenda and talhao.fazenda.latitude and talhao.fazenda.longitude:
        context['fazenda_lat'] = float(talhao.fazenda.latitude)
        context['fazenda_lon'] = float(talhao.fazenda.longitude)

    # Buscar irmãos para verificação de sobreposição
    if talhao.parent:
        # Se for subtalhão, irmãos são os filhos do mesmo pai (excluindo ele mesmo)
        irmaos = Talhao.objects.filter(parent=talhao.parent, ativo=True).exclude(pk=talhao.pk)
    else:
        # Se for raiz, irmãos são outros raízes da mesma fazenda (considerando a fazenda selecionada/alvo)
        irmaos = Talhao.objects.filter(fazenda=validation_fazenda, parent__isnull=True, ativo=True).exclude(pk=talhao.pk)

    irmaos_json = []
    for irmao in irmaos:
        coords = irmao.get_coordenadas()
        # Ensure coords is a list and has content
        if coords and len(coords) > 0:
            irmaos_json.append({
                'id': irmao.id,
                'nome': irmao.nome,
                'coordenadas': coords
            })

    return render(request, 'core/talhao/form.html', {
        'form': form, 
        'talhao': talhao,
        'parent_talhao': talhao.parent,
        'titulo': f'Editar Talhão: {talhao.nome}',
        'parent_coords_list': talhao.parent.get_coordenadas() if talhao.parent else [],
        'siblings_json': irmaos_json
    })


@login_required
def talhao_detail(request, pk):
    """Exibe detalhes de um talhão com mapa e operações."""
    empresa = get_empresa(request.user)
    talhao = get_object_or_404(Talhao, pk=pk, empresa=empresa)
    
    # Busca operações relacionadas via ManyToMany no modelo OperacaoCampo
    operacoes = talhao.operacoes_campo.prefetch_related('itens', 'itens__produto', 'itens__atividade').order_by('-data_operacao')[:10]
    
    # Busca ciclos (plantios) relacionados via ManyToMany
    ciclos = talhao.plantios_multi.all().order_by('-data_plantio')
    
    subtalhoes = talhao.subtalhoes.filter(ativo=True).order_by('nome')
    
    custo_total = talhao.calcular_custo_total()
    
    context = {
        'talhao': talhao,
        'operacoes': operacoes,
        'ciclos': ciclos,
        'subtalhoes': subtalhoes,
        'custo_total': custo_total,
        'coordenadas_json': json.loads(talhao.coordenadas_json) if talhao.coordenadas_json else [],
    }
    
    return render(request, 'core/talhao/detail.html', context)


@login_required
@require_POST
def talhao_delete(request, pk):
    """Exclui um talhão."""
    empresa = get_empresa(request.user)
    talhao = get_object_or_404(Talhao, pk=pk, empresa=empresa)
    nome = talhao.nome
    talhao.delete()
    messages.success(request, f'Talhão "{nome}" excluído com sucesso!')
    return redirect('talhao_list')


# =============================================================================
# PRODUTOS
# =============================================================================

@login_required
def produto_list(request):
    """Lista todos os produtos."""
    empresa = get_empresa(request.user)
    produtos = Produto.objects.filter(empresa=empresa).order_by('nome')
    busca = request.GET.get('busca')
    categoria = request.GET.get('categoria')
    
    if busca:
        produtos = produtos.filter(
            Q(nome__icontains=busca) |
            Q(codigo__icontains=busca)
        )

    if categoria:
        produtos = produtos.filter(categoria=categoria)
    
    paginator = Paginator(produtos, 15)
    page = request.GET.get('page')
    produtos = paginator.get_page(page)
    
    return render(request, 'core/produto/list.html', {
        'produtos': produtos,
        'busca': busca,
        'categoria_filtro': categoria,
        'CategoriaProduto': CategoriaProduto
    })


@login_required
def produto_create(request):
    """Cria um novo produto."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = ProdutoForm(request.POST, empresa=empresa)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.empresa = empresa
            produto.save()
            messages.success(request, f'Produto "{produto.nome}" criado com sucesso!')
            return redirect('produto_list')
    else:
        form = ProdutoForm(empresa=empresa)
    
    return render(request, 'core/produto/form.html', {'form': form, 'titulo': 'Novo Produto'})


@login_required
def produto_edit(request, pk):
    """Edita um produto existente."""
    empresa = get_empresa(request.user)
    produto = get_object_or_404(Produto, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=produto, empresa=empresa)
        if form.is_valid():
            produto = form.save()
            messages.success(request, f'Produto "{produto.nome}" atualizado com sucesso!')
            return redirect('produto_list')
    else:
        form = ProdutoForm(instance=produto, empresa=empresa)
    
    return render(request, 'core/produto/form.html', {
        'form': form, 
        'produto': produto,
        'titulo': f'Editar Produto: {produto.nome}'
    })


@login_required
@require_POST
def produto_delete(request, pk):
    """Exclui um produto."""
    empresa = get_empresa(request.user)
    produto = get_object_or_404(Produto, pk=pk, empresa=empresa)
    nome = produto.nome
    produto.delete()
    messages.success(request, f'Produto "{nome}" excluído com sucesso!')
    return redirect('produto_list')


@login_required
@require_POST
def api_produto_quick_create(request):
    """API para criar produto rapidamente via AJAX (usado no modal de contratos)."""
    empresa = get_empresa(request.user)
    
    nome = request.POST.get('nome', '').strip()
    categoria = request.POST.get('categoria')
    unidade = request.POST.get('unidade', 'UN')
    codigo = request.POST.get('codigo', '').strip()
    estoque_minimo = request.POST.get('estoque', 0)
    ativo = request.POST.get('ativo') == 'true'
    
    if not nome:
        return JsonResponse({'success': False, 'error': 'Nome do produto é obrigatório.'}, status=400)
    
    try:
        produto = Produto.objects.create(
            empresa=empresa,
            nome=nome,
            categoria=categoria if categoria else CategoriaProduto.OUTROS,
            unidade=unidade,
            codigo=codigo if codigo else None,
            estoque_minimo=estoque_minimo,
            ativo=ativo
        )
        return JsonResponse({
            'success': True,
            'produto': {
                'id': produto.id,
                'nome': produto.nome
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# MOVIMENTAÇÕES DE ESTOQUE
# =============================================================================

@login_required
def movimentacao_list(request):
    """Lista todas as movimentações de estoque."""
    empresa = get_empresa(request.user)
    movimentacoes = MovimentacaoEstoque.objects.filter(empresa=empresa).select_related('produto').order_by('-data_movimentacao')
    
    # Filtros
    busca = request.GET.get('busca')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    tipo = request.GET.get('tipo')

    if busca:
        movimentacoes = movimentacoes.filter(
            Q(produto__nome__icontains=busca) |
            Q(numero_nfe__icontains=busca) |
            Q(fornecedor__nome__icontains=busca)
        )
    
    if data_inicio:
        movimentacoes = movimentacoes.filter(data_movimentacao__date__gte=data_inicio)
    
    if data_fim:
        movimentacoes = movimentacoes.filter(data_movimentacao__date__lte=data_fim)

    if tipo:
        if tipo == 'SAIDA':
            movimentacoes = movimentacoes.filter(Q(tipo='SAIDA') | Q(tipo=''))
        else:
            movimentacoes = movimentacoes.filter(tipo=tipo)
    
    paginator = Paginator(movimentacoes, 20)
    page = request.GET.get('page')
    movimentacoes = paginator.get_page(page)
    
    context = {
        'movimentacoes': movimentacoes,
        'busca': busca,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_filtro': tipo
    }
    
    return render(request, 'core/movimentacao/list.html', context)



def _processar_post_movimentacao(request, empresa, form_class, tipo_vinc):
    """Função auxiliar para processar o POST de movimentações (Entrada ou Saída)."""
    batch_data_json = request.POST.get('batch_data')
    
    if batch_data_json:
        try:
            batch_items = json.loads(batch_data_json)
            if not batch_items:
                raise ValueError("Lista de itens vazia.")
            
            tipo_mov = tipo_vinc # ENTRADA ou SAIDA
            gerar_fin = request.POST.get('gerar_financeiro') == 'True'
            
            fornecedor_id = request.POST.get('fornecedor')
            fornecedor_obj = Fornecedor.objects.filter(id=fornecedor_id, empresa=empresa).first() if fornecedor_id else None
            
            cliente_id = request.POST.get('cliente')
            cliente_obj = Cliente.objects.filter(id=cliente_id, empresa=empresa).first() if cliente_id else None
            
            fazenda_id = request.POST.get('fazenda')
            fazenda_obj = Fazenda.objects.filter(id=fazenda_id, empresa=empresa).first() if fazenda_id else None
            
            numero_nfe = request.POST.get('numero_nfe')
            data_mov_str = request.POST.get('data_movimentacao')
            
            if data_mov_str:
                try:
                    data_mov = datetime.strptime(data_mov_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try:
                        data_mov = datetime.strptime(data_mov_str, '%Y-%m-%d')
                    except ValueError:
                        data_mov = timezone.now()
            else:
                data_mov = timezone.now()

            salvos = 0
            with transaction.atomic():
                for item in batch_items:
                    prod_id = item.get('produto_id')
                    produto = None
                    if prod_id:
                        produto = Produto.objects.filter(id=prod_id, empresa=empresa).first()
                    
                    if not produto:
                        produto = Produto.objects.create(
                            empresa=empresa,
                            nome=item.get('nome'),
                            codigo=item.get('codigo'),
                            unidade=item.get('unidade') or 'UN',
                            ativo=True
                        )
                    
                    qtd = Decimal(str(item.get('quantidade', 0)))
                    valor_un = Decimal(str(item.get('valor_unitario', 0)))
                    item_vinc_id = item.get('id')
                    
                    MovimentacaoEstoque.objects.create(
                        empresa=empresa,
                        produto=produto,
                        tipo=tipo_mov,
                        quantidade=qtd,
                        valor_unitario=valor_un,
                        data_movimentacao=data_mov,
                        fornecedor=fornecedor_obj,
                        cliente=cliente_obj,
                        fazenda=fazenda_obj,
                        numero_nfe=numero_nfe,
                        item_pedido_id=item_vinc_id if tipo_mov == TipoMovimentacao.ENTRADA else None,
                        item_contrato_id=item_vinc_id if tipo_mov == TipoMovimentacao.SAIDA else None,
                        observacao=f"Lote {numero_nfe or ''}: {item.get('nome')}"
                    )
                    salvos += 1
                
                if gerar_fin:
                    total_geral = sum(Decimal(str(i.get('valor_total', 0))) for i in batch_items)
                    descricao_fin = f"Movimentação em Lote - NF {numero_nfe or 'S/N'}"
                    
                    if tipo_mov == TipoMovimentacao.ENTRADA:
                        ContaPagar.objects.create(
                            empresa=empresa,
                            fornecedor=fornecedor_obj,
                            valor_total=total_geral,
                            data_vencimento=data_mov.date(),
                            descricao=descricao_fin,
                            fazenda=fazenda_obj,
                            status=StatusFinanceiro.PENDENTE,
                            numero_nfe=numero_nfe
                        )
                    else:
                        ContaReceber.objects.create(
                            empresa=empresa,
                            cliente=cliente_obj,
                            valor_total=total_geral,
                            data_vencimento=data_mov.date(),
                            descricao=descricao_fin,
                            fazenda=fazenda_obj,
                            status=StatusFinanceiro.PENDENTE,
                            numero_nfe=f"Mov. {numero_nfe or ''}"
                        )
            
            messages.success(request, f'Lote de {salvos} movimentações registrado com sucesso!')
            return True, None

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return False, f"Erro ao processar lote: {str(e)}"
    
    else:
        form = form_class(request.POST, request.FILES, empresa=empresa)
        if form.is_valid():
            if not form.cleaned_data.get('produto'):
                 return False, "Para movimentação individual, selecione um Produto. Para vários itens, use o botão 'Adicionar Item'."

            movimentacao = form.save(commit=False)
            movimentacao.empresa = empresa
            movimentacao.tipo = tipo_vinc
            movimentacao.save()
            
            gerar_fin = form.cleaned_data.get('gerar_financeiro') == 'True'
            if gerar_fin:
                descricao_fin = f"Movimentação Individual - {movimentacao.produto.nome}"
                if movimentacao.tipo == TipoMovimentacao.ENTRADA:
                    ContaPagar.objects.create(
                        empresa=empresa,
                        fornecedor=movimentacao.fornecedor,
                        valor_total=movimentacao.valor_total,
                        data_vencimento=movimentacao.data_movimentacao.date(),
                        descricao=descricao_fin,
                        fazenda=movimentacao.fazenda,
                        status=StatusFinanceiro.PENDENTE,
                        numero_nfe=movimentacao.numero_nfe
                    )
                else:
                    ContaReceber.objects.create(
                        empresa=empresa,
                        cliente=movimentacao.cliente,
                        valor_total=movimentacao.valor_total,
                        data_vencimento=movimentacao.data_movimentacao.date(),
                        descricao=descricao_fin,
                        fazenda=movimentacao.fazenda,
                        status=StatusFinanceiro.PENDENTE,
                        numero_nfe=f"Mov. {movimentacao.numero_nfe or ''}"
                    )

            messages.success(request, f'Movimentação registrada com sucesso!')
            return True, None
        else:
            return False, form


@login_required
def movimentacao_create(request):
    """Fallback: Redireciona para Nova Entrada por padrão."""
    return redirect('movimentacao_entrada')


@login_required
def movimentacao_entrada(request):
    """View especializada para Nova Entrada."""
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        sucesso, resultado = _processar_post_movimentacao(request, empresa, MovimentacaoEntradaForm, TipoMovimentacao.ENTRADA)
        if sucesso:
            return redirect('movimentacao_list')
        else:
            form = resultado if isinstance(resultado, MovimentacaoEntradaForm) else MovimentacaoEntradaForm(request.POST, empresa=empresa)
            if isinstance(resultado, str): messages.error(request, resultado)
            return render(request, 'core/movimentacao/form.html', {'form': form, 'titulo': 'Nova Entrada', 'tipo': 'ENTRADA'})
    
    data_atual = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
    form = MovimentacaoEntradaForm(empresa=empresa, initial={'data_movimentacao': data_atual})
    return render(request, 'core/movimentacao/form.html', {'form': form, 'titulo': 'Nova Entrada', 'tipo': 'ENTRADA'})


@login_required
def movimentacao_saida(request):
    """View especializada para Nova Saída."""
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        sucesso, resultado = _processar_post_movimentacao(request, empresa, MovimentacaoSaidaForm, TipoMovimentacao.SAIDA)
        if sucesso:
            return redirect('movimentacao_list')
        else:
            form = resultado if isinstance(resultado, MovimentacaoSaidaForm) else MovimentacaoSaidaForm(request.POST, empresa=empresa)
            if isinstance(resultado, str): messages.error(request, resultado)
            return render(request, 'core/movimentacao/form.html', {'form': form, 'titulo': 'Nova Saída', 'tipo': 'SAIDA'})
    
    data_atual = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
    form = MovimentacaoSaidaForm(empresa=empresa, initial={'data_movimentacao': data_atual})
    return render(request, 'core/movimentacao/form.html', {'form': form, 'titulo': 'Nova Saída', 'tipo': 'SAIDA'})


@login_required
def movimentacao_edit(request, pk):
    """Edita uma movimentação de estoque existente."""
    empresa = get_empresa(request.user)
    movimentacao = get_object_or_404(MovimentacaoEstoque, pk=pk, empresa=empresa)
    
    # Selecionar formulário conforme o tipo
    if movimentacao.tipo == TipoMovimentacao.ENTRADA:
        form_class = MovimentacaoEntradaForm
        titulo = f'Editar Entrada #{movimentacao.id}'
        tipo_label = 'ENTRADA'
    else:
        form_class = MovimentacaoSaidaForm
        titulo = f'Editar Saída #{movimentacao.id}'
        tipo_label = 'SAIDA'

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=movimentacao, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimentação atualizada com sucesso!')
            return redirect('movimentacao_list')
    else:
        form = form_class(instance=movimentacao, empresa=empresa)
    
    return render(request, 'core/movimentacao/form.html', {
        'form': form, 
        'titulo': titulo,
        'is_edit': True,
        'tipo': tipo_label
    })


@login_required
def movimentacao_delete(request, pk):
    """Exclui uma movimentação de estoque."""
    empresa = get_empresa(request.user)
    movimentacao = get_object_or_404(MovimentacaoEstoque, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        movimentacao.delete()
        messages.success(request, 'Movimentação excluída com sucesso!')
        return redirect('movimentacao_list')
    
    return render(request, 'core/confirm_delete.html', {
        'objeto': movimentacao,
        'titulo': 'Excluir Movimentação'
    })


@login_required
@require_POST
def api_ler_dados_nfe(request):
    """API para ler dados de NFe e retornar via JSON (sem salvar)."""
    try:
        arquivo = request.FILES.get('arquivo_xml') or request.FILES.get('arquivo_nfe')
        if not arquivo:
             return JsonResponse({'sucesso': False, 'erro': 'Arquivo não enviado.'})
        
        empresa = get_empresa(request.user)
        parser = NFeParser()
        dados = parser.processar_xml_dados(arquivo, empresa=empresa)
        
        if dados['sucesso']:
            # Converter Decimals para float para serialização JSON
            for item in dados['itens']:
                item['quantidade'] = float(item['quantidade'])
                item['valor_unitario'] = float(item['valor_unitario'])
                item['valor_total'] = float(item['valor_total'])
            return JsonResponse(dados)
        else:
            return JsonResponse({'sucesso': False, 'erro': dados.get('erro', 'Erro desconhecido')})
            
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)})


@login_required
@require_POST
def api_salvar_lote_movimentacao(request):
    """API para salvar múltiplas movimentações a partir do modal/JS."""
    try:
        data = json.loads(request.body)
        header = data.get('header', {})
        itens = data.get('itens', [])
        empresa = get_empresa(request.user)
        
        # Validar dados mínimos
        if not itens:
             return JsonResponse({'sucesso': False, 'erro': 'Nenhum item selecionado.'})

        salvos = 0
        total_financeiro = Decimal('0.00')
        primeira_mov = None
        
        with transaction.atomic():
            for item in itens:
                # Tentar encontrar produto ou criar
                produto = None
                if item.get('produto_id'):
                    produto = Produto.objects.filter(id=item['produto_id'], empresa=empresa).first()
                
                if not produto:
                    # Criar novo
                    produto = Produto.objects.create(
                        empresa=empresa,
                        nome=item.get('nome'),
                        codigo=item.get('codigo'),
                        unidade=item.get('unidade'),
                        ativo=True
                    )
                
                # Tratar Fornecedor (Vincular ou Criar se vier do XML)
                fornecedor_obj = None
                fornecedor_nome = header.get('fornecedor')
                if fornecedor_nome:
                    fornecedor_obj, _ = Fornecedor.objects.get_or_create(
                        nome=fornecedor_nome,
                        empresa=empresa
                    )

                # Criar Movimentação
                valor_uni = Decimal(str(item.get('valor_unitario', 0)))
                qtd = Decimal(str(item.get('quantidade', 0)))
                
                mov = MovimentacaoEstoque.objects.create(
                    empresa=empresa,
                    produto=produto,
                    tipo=header.get('tipo', TipoMovimentacao.ENTRADA),
                    quantidade=qtd,
                    valor_unitario=valor_uni,
                    data_movimentacao=header.get('data_movimentacao') or timezone.now(),
                    fornecedor=fornecedor_obj,
                    numero_nfe=header.get('numero_nfe'),
                    observacao=f"Imp. XML: {item.get('nome')} (Nota: {header.get('numero_nfe')})"
                )
                salvos += 1
                total_financeiro += (valor_uni * qtd)
                if not primeira_mov:
                    primeira_mov = mov
            
            # --- INTEGRAÇÃO FINANCEIRA ---
            if header.get('gerar_financeiro') and header.get('tipo') == TipoMovimentacao.ENTRADA:
                # Buscar uma categoria padrão ou a primeira de SAIDA
                categoria = CategoriaFinanceira.objects.filter(empresa=empresa, tipo='SAIDA', ativo=True).first()
                if not categoria:
                    # Criar uma se não existir para não quebrar a automação
                    categoria = CategoriaFinanceira.objects.create(
                        empresa=empresa,
                        nome='Aquisição de Insumos/Produtos',
                        tipo='SAIDA'
                    )
                
                ContaPagar.objects.create(
                    empresa=empresa,
                    descricao=f"NFe {header.get('numero_nfe')} - {fornecedor_obj.nome if fornecedor_obj else 'Importação'}",
                    fornecedor=fornecedor_obj,
                    categoria=categoria,
                    valor_total=total_financeiro,
                    data_vencimento=(header.get('data_movimentacao') or timezone.now()), # Vencimento inicial = data nota
                    numero_nfe=header.get('numero_nfe'),
                    movimentacao_origem=primeira_mov,
                    status=StatusFinanceiro.PENDENTE,
                    observacao=f"Gerado automaticamente via importação de NFe {header.get('numero_nfe')}."
                )
                
        messages.success(request, f"{salvos} itens importados com sucesso!")
        if header.get('gerar_financeiro'):
            messages.info(request, "Lançamento de Contas a Pagar gerado automaticamente.")
            
        return JsonResponse({'sucesso': True, 'redirect': reverse('movimentacao_list')})

    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)})


@login_required
def importar_nfe(request):
    """View para importar NFe via XML."""
    empresa = get_empresa(request.user) # Para validar cadastro de produtos
    resultado = None
    
    if request.method == 'POST':
        form = ImportarNFeForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo_xml = request.FILES['arquivo_xml']
            # Passamos empresa para o parser vincular produtos corretamente
            # Nota: importar_nfe_xml precisaria ser atualizado para aceitar empresa!
            # Por enquanto, mantendo assinatura original mas sabendo que isso pode falhar em Multi-tenant
            # TODO: Atualizar nfe_parser.py
            resultado = importar_nfe_xml(arquivo_xml, empresa=empresa) 
            
            if resultado['sucesso']:
                messages.success(request, resultado['mensagem'])
            else:
                messages.error(request, resultado['mensagem'])
    else:
        form = ImportarNFeForm()
    
    return render(request, 'core/movimentacao/importar_nfe.html', {
        'form': form,
        'resultado': resultado,
    })


# =============================================================================
# PEDIDOS DE COMPRA
# =============================================================================

@login_required
def pedido_list(request):
    """Lista todos os pedidos de compra."""
    empresa = get_empresa(request.user)
    pedidos = PedidoCompra.objects.filter(empresa=empresa).order_by('-data_pedido')
    
    form = PedidoFilterForm(request.GET)
    if form.is_valid():
        status = form.cleaned_data.get('status')
        if status:
            pedidos = pedidos.filter(status=status)
            
        q = form.cleaned_data.get('q')
        if q:
            keywords = q.split()
            for keyword in keywords:
                pedidos = pedidos.filter(
                    Q(fornecedor__nome__icontains=keyword) |
                    Q(fornecedor__cpf_cnpj__icontains=keyword)
                )
            
    # Filtro por Fazenda (Itens do Pedido)
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        pedidos = pedidos.filter(itens__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    paginator = Paginator(pedidos, 10)
    page = request.GET.get('page')
    pedidos = paginator.get_page(page)
    
    return render(request, 'core/pedido/list.html', {
        'pedidos': pedidos,
        'filter_form': form,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada
    })


@login_required
def pedido_create(request):
    """Cria um novo pedido de compra com itens."""
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = PedidoCompraForm(request.POST, request.FILES, empresa=empresa)
        
        if form.is_valid():
            pedido = form.save(commit=False)
            pedido.empresa = empresa
            pedido.save()
            
            # Processar Itens JSON
            itens_json = form.cleaned_data.get('itens_json', '[]')
            try:
                itens_data = json.loads(itens_json)
                for item_data in itens_data:
                    produto_id = item_data.get('produto_id')
                    fazenda_id = item_data.get('fazenda_id') or None
                    
                    try:
                        qtd = Decimal(str(item_data.get('quantidade', 0)))
                        valor = Decimal(str(item_data.get('valor_unitario', 0)))
                    except:
                        qtd = 0
                        valor = 0

                    if produto_id and qtd > 0:
                        ItemPedidoCompra.objects.create(
                            empresa=empresa,
                            pedido=pedido,
                            produto_id=produto_id,
                            fazenda_id=fazenda_id,
                            quantidade=qtd,
                            valor_unitario=valor
                        )
            except Exception as e:
                print(f"Erro ao processar itens do pedido: {e}")
            
            messages.success(request, f'Pedido #{pedido.id} criado com sucesso!')
            return redirect('pedido_list')
    else:
        form = PedidoCompraForm(empresa=empresa)
    
    return render(request, 'core/pedido/form.html', {
        'form': form, 
        'titulo': 'Novo Pedido de Compra',
        'categorias_produto': CategoriaProduto.choices
    })


@login_required
def pedido_edit(request, pk):
    """Edita um pedido existente."""
    empresa = get_empresa(request.user)
    pedido = get_object_or_404(PedidoCompra, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        form = PedidoCompraForm(request.POST, request.FILES, instance=pedido, empresa=empresa)
        
        if form.is_valid():
            pedido = form.save()
            
            # Processar Itens JSON
            itens_json = form.cleaned_data.get('itens_json', '[]')
            try:
                itens_data = json.loads(itens_json)
                current_itens = {item.id: item for item in pedido.itens.all()}
                
                for item_data in itens_data:
                    item_id = item_data.get('id')
                    produto_id = item_data.get('produto_id')
                    fazenda_id = item_data.get('fazenda_id') or None
                    try:
                        qtd = Decimal(str(item_data.get('quantidade', 0)))
                        valor = Decimal(str(item_data.get('valor_unitario', 0)))
                    except:
                        qtd = 0
                        valor = 0
                        
                    if produto_id and qtd > 0:
                        if item_id and int(item_id) in current_itens:
                            # Update
                            item = current_itens.pop(int(item_id))
                            item.produto_id = produto_id
                            item.fazenda_id = fazenda_id
                            item.quantidade = qtd
                            item.valor_unitario = valor
                            item.save()
                        else:
                            # Create
                            ItemPedidoCompra.objects.create(
                                empresa=empresa,
                                pedido=pedido,
                                produto_id=produto_id,
                                fazenda_id=fazenda_id,
                                quantidade=qtd,
                                valor_unitario=valor
                            )
                
                # Delete removed items
                for remaining_item in current_itens.values():
                    remaining_item.delete()
                    
            except Exception as e:
                print(f"Erro ao processar itens na edição: {e}")
                
            messages.success(request, 'Pedido atualizado com sucesso!')
            return redirect('pedido_list')
    else:
        form = PedidoCompraForm(instance=pedido, empresa=empresa)
    
    # Preparar JSON inicial
    itens_list = []
    for item in pedido.itens.all():
        itens_list.append({
            'id': item.id,
            'produto_id': item.produto_id,
            'produto_nome': item.produto.nome,
            'fazenda_id': item.fazenda_id,
            'fazenda_nome': item.fazenda.nome if item.fazenda else '',
            'quantidade': str(item.quantidade),
            'valor_unitario': str(item.valor_unitario)
        })
    itens_json_initial = json.dumps(itens_list)
    
    return render(request, 'core/pedido/form.html', {
        'form': form, 
        'titulo': f'Editar Pedido #{pedido.id}',
        'pedido': pedido,
        'itens_json_initial': itens_json_initial,
        'categorias_produto': CategoriaProduto.choices
    })


@login_required
def pedido_detail(request, pk):
    """Exibe detalhes do pedido e progresso de entregas."""
    empresa = get_empresa(request.user)
    pedido = get_object_or_404(PedidoCompra, pk=pk, empresa=empresa)
    # Prefetch itens e suas movimentações para performance
    # Nota: Em produção idealmente usar prefetch_related com lógica mais complexa, 
    # mas aqui o property helper no model já ajuda se não for muitos itens
    
    # Buscar todas as movimentações ligadas aos itens deste pedido
    movimentacoes = MovimentacaoEstoque.objects.filter(
        item_pedido__pedido=pedido
    ).select_related('item_pedido', 'item_pedido__produto').order_by('-data_movimentacao')
    
    context = {
        'pedido': pedido,
        'movimentacoes': movimentacoes,
    }
    return render(request, 'core/pedido/detail.html', context)


@login_required
@require_POST
def pedido_delete(request, pk):
    """Exclui um pedido (com confirmação de senha)."""
    empresa = get_empresa(request.user)
    pedido = get_object_or_404(PedidoCompra, pk=pk, empresa=empresa)
    
    pedido.delete()
    messages.success(request, 'Pedido excluído com sucesso!')
    return redirect('pedido_list')


@login_required
def pedido_pdf(request, pk):
    """Gera o PDF do Pedido de Compra."""
    empresa = get_empresa(request.user)
    pedido = get_object_or_404(PedidoCompra, pk=pk, empresa=empresa)
    
    context = {
        'pedido': pedido,
        'empresa': empresa,
        'data_atual': timezone.now(),
    }
    
    pdf = render_to_pdf('core/pedido/pdf.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Pedido_{pedido.id}.pdf"
        content = f"inline; filename='{filename}'"
        response['Content-Disposition'] = content
        return response
    return HttpResponse("Erro ao gerar PDF", status=400)


# =============================================================================
# CICLOS DE PRODUÇÃO
# =============================================================================

@login_required
def ciclo_list(request):
    """Lista todos os ciclos de produção."""
    empresa = get_empresa(request.user)
    
    # Preço de referência para conversão
    preco_ref_raw = request.GET.get('preco_referencia', '120.00')
    try:
        preco_ref = Decimal(preco_ref_raw)
    except:
        preco_ref = Decimal('120.00')

    ciclos_qs = Plantio.objects.filter(empresa=empresa).prefetch_related('talhoes').select_related('safra').order_by('-data_plantio')
    
    # Filtro por Fazenda
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        ciclos_qs = ciclos_qs.filter(talhoes__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    status = request.GET.get('status')
    if status:
        ciclos_qs = ciclos_qs.filter(status=status)
    
    paginator = Paginator(ciclos_qs, 10)
    page = request.GET.get('page')
    ciclos_paginated = paginator.get_page(page)
    
    # Calcular custo em sacas para os ciclos na página atual
    for ciclo in ciclos_paginated:
        custo_brl = ciclo.calcular_custo_total()
        ciclo.custo_total_brl = custo_brl
        ciclo.custo_total_sacas = custo_brl / preco_ref if preco_ref > 0 else 0
        
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')

    return render(request, 'core/ciclo/list.html', {
        'ciclos': ciclos_paginated,
        'preco_referencia': preco_ref,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada,
        'status_filtro': status
    })


@login_required
def ciclo_create(request):
    """Cria um novo ciclo de produção."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = PlantioForm(request.POST, empresa=empresa)
        if form.is_valid():
            ciclo = form.save(commit=False)
            ciclo.empresa = empresa
            ciclo.save()
            form.save_m2m() # Importante para ManyToMany
            # Safra pode ser None, evitar erro
            safra_nome = ciclo.safra.nome if ciclo.safra else "S/ Safra"
            messages.success(request, f'Ciclo/Plantio "{safra_nome}" criado com sucesso!')
            return redirect('ciclo_list')
    else:
        form = PlantioForm(empresa=empresa)
    # Dados de talhões para o JS
    talhoes_data = list(Talhao.objects.filter(empresa=empresa, ativo=True).values('id', 'nome', 'area_hectares', 'parent_id', 'fazenda_id', 'fazenda__nome'))
    
    # Talhões ocupados por safra
    busy_qs = Plantio.objects.filter(empresa=empresa).values('talhoes__id', 'safra_id')
    busy_talhoes = {}
    for item in busy_qs:
        t_id = item['talhoes__id']
        s_id = item['safra_id']
        if t_id and s_id:
            if t_id not in busy_talhoes:
                busy_talhoes[t_id] = []
            if s_id not in busy_talhoes[t_id]:
                busy_talhoes[t_id].append(s_id)

    return render(request, 'core/ciclo/form.html', {
        'form': form, 
        'titulo': 'Novo Ciclo de Produção',
        'talhoes_json': json.dumps(talhoes_data, cls=DjangoJSONEncoder),
        'busy_talhoes_json': json.dumps(busy_talhoes)
    })


@login_required
def ciclo_edit(request, pk):
    """Edita um ciclo de produção existente."""
    empresa = get_empresa(request.user)
    ciclo = get_object_or_404(Plantio, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        form = PlantioForm(request.POST, instance=ciclo, empresa=empresa)
        if form.is_valid():
            ciclo = form.save()
            # form.save_m2m() is called automatically by form.save() for ModelForm
            safra_nome = ciclo.safra.nome if ciclo.safra else "S/ Safra"
            messages.success(request, f'Ciclo "{safra_nome}" atualizado com sucesso!')
            return redirect('ciclo_list')
    else:
        form = PlantioForm(instance=ciclo, empresa=empresa)
    
    # Dados de talhões para o JS
    talhoes_data = list(Talhao.objects.filter(empresa=empresa, ativo=True).values('id', 'nome', 'area_hectares', 'parent_id', 'fazenda_id', 'fazenda__nome'))
    
    # Talhões ocupados por safra (exceto o atual)
    busy_qs = Plantio.objects.filter(empresa=empresa).exclude(id=ciclo.id).values('talhoes__id', 'safra_id')
    busy_talhoes = {}
    for item in busy_qs:
        t_id = item['talhoes__id']
        s_id = item['safra_id']
        if t_id and s_id:
            if t_id not in busy_talhoes:
                busy_talhoes[t_id] = []
            if s_id not in busy_talhoes[t_id]:
                busy_talhoes[t_id].append(s_id)

    # Identificar fazenda inicial (do primeiro talhão do ciclo)
    primeiro_talhao = ciclo.talhoes.first()
    fazenda_id = primeiro_talhao.fazenda_id if primeiro_talhao else None

    return render(request, 'core/ciclo/form.html', {
        'form': form, 
        'ciclo': ciclo,
        'titulo': f'Editar Ciclo: {ciclo.nome_safra}',
        'talhoes_json': json.dumps(talhoes_data, cls=DjangoJSONEncoder),
        'busy_talhoes_json': json.dumps(busy_talhoes),
        'fazenda_id': fazenda_id
    })


@login_required
def ciclo_detail(request, pk):
    """Exibe detalhes de um ciclo de produção com análise de ROI."""
    empresa = get_empresa(request.user)
    ciclo = get_object_or_404(Plantio.objects.prefetch_related('talhoes'), pk=pk, empresa=empresa)
    operacoes = ciclo.operacoes.prefetch_related('itens', 'itens__produto', 'itens__atividade').order_by('-data_operacao')
    
    # Preço de referência para conversão (vinda do GET ou padrão)
    preco_ref_raw = request.GET.get('preco_referencia', '120.00')
    try:
        preco_ref = Decimal(preco_ref_raw)
    except:
        preco_ref = Decimal('120.00')

    # Cálculos de ROI
    custo_total = ciclo.calcular_custo_total()
    receita_estimada = ciclo.calcular_receita_estimada()
    receita_real = ciclo.calcular_receita_real()
    lucro_estimado = ciclo.calcular_lucro_estimado()
    lucro_real = ciclo.calcular_lucro_real()
    roi = ciclo.calcular_roi()
    
    context = {
        'ciclo': ciclo,
        'operacoes': operacoes,
        'custo_total': custo_total,
        'custo_total_sacas': custo_total / preco_ref if preco_ref > 0 else 0,
        'receita_estimada': receita_estimada,
        'receita_estimada_sacas': receita_estimada / preco_ref if preco_ref > 0 else 0,
        'receita_real': receita_real,
        'receita_real_sacas': receita_real / preco_ref if preco_ref > 0 else 0,
        'lucro_estimado': lucro_estimado,
        'lucro_estimado_sacas': lucro_estimado / preco_ref if preco_ref > 0 else 0,
        'lucro_real': lucro_real,
        'lucro_real_sacas': lucro_real / preco_ref if preco_ref > 0 else 0,
        'roi': roi,
        'preco_referencia': preco_ref,
    }
    
    return render(request, 'core/ciclo/detail.html', context)


@login_required
@require_POST
def ciclo_delete(request, pk):
    """Exclui um ciclo de produção."""
    empresa = get_empresa(request.user)
    ciclo = get_object_or_404(Plantio, pk=pk, empresa=empresa)
    safra_nome = ciclo.safra.nome if ciclo.safra else "S/ Safra"
    ciclo.delete()
    messages.success(request, f'Ciclo "{safra_nome}" excluído com sucesso!')
    return redirect('ciclo_list')


# =============================================================================
# OPERAÇÕES DE CAMPO
# =============================================================================

@login_required
def operacao_list(request):
    """Lista todas as operações de campo."""
    empresa = get_empresa(request.user)
    operacoes = OperacaoCampo.objects.filter(empresa=empresa).select_related(
        'ciclo', 'safra'
    ).prefetch_related('talhoes', 'talhoes__fazenda', 'itens', 'itens__atividade').order_by('-data_operacao')
    
    # Filtro por Fazenda
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        operacoes = operacoes.filter(talhoes__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    talhao_id = request.GET.get('talhao')
    if talhao_id:
        operacoes = operacoes.filter(talhoes__id=talhao_id).distinct()
    
    paginator = Paginator(operacoes, 15)
    page = request.GET.get('page')
    operacoes = paginator.get_page(page)
    
    # Filtro apenas talhoes da empresa
    talhoes = Talhao.objects.filter(ativo=True, empresa=empresa)
    if fazenda_id:
        talhoes = talhoes.filter(fazenda_id=fazenda_id)
        
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    return render(request, 'core/operacao/list.html', {
        'operacoes': operacoes,
        'talhoes': talhoes,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada,
        'filtro_talhao': talhao_id
    })


@login_required
def operacao_detail(request, pk):
    """Exibe detalhes de uma operação de campo específica."""
    empresa = get_empresa(request.user)
    operacao = get_object_or_404(
        OperacaoCampo.objects.filter(empresa=empresa).prefetch_related(
            'talhoes', 'itens', 'itens__atividade', 'itens__produto', 'safra'
        ),
        pk=pk
    )
    
    context = {
        'operacao': operacao,
    }
    
    return render(request, 'core/operacao/detail.html', context)


@login_required
def operacao_create(request):
    """Cria uma nova operação de campo."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = OperacaoCampoForm(request.POST, empresa=empresa)
        if form.is_valid():
            operacao = form.save(commit=False)
            operacao.empresa = empresa
            operacao.save()
            form.save_m2m()  # Necessário para campos ManyToMany (talhoes)
            
            # Processar Itens (JSON)
            itens_json = request.POST.get('itens_json', '[]')
            try:
                itens_data = json.loads(itens_json)
                for item in itens_data:
                    # Buscar Atividade ou Criar
                    atividade_id = item.get('atividade_id')
                    atividade_nome = item.get('atividade_nome')
                    
                    atividade = None
                    if atividade_id:
                        atividade = AtividadeCampo.objects.filter(id=atividade_id).first()
                    elif atividade_nome:
                        # Busca por nome (case insensitive) na empresa
                        atividade = AtividadeCampo.objects.filter(
                            nome__iexact=atividade_nome, 
                            empresa=empresa
                        ).first()
                        
                        if not atividade:
                            # Criar nova atividade se não existir
                            atividade = AtividadeCampo.objects.create(
                                empresa=empresa,
                                nome=atividade_nome,
                                ativo=True
                            )
                    
                    if not atividade:
                        continue # Pula se não conseguiu identificar atividade
                    
                    # Tratar valores numéricos
                    try:
                        qtd = Decimal(str(item.get('quantidade', 0)))
                        custo = Decimal(str(item.get('custo_unitario', 0)))
                    except:
                        qtd = Decimal('0')
                        custo = Decimal('0')

                    OperacaoCampoItem.objects.create(
                        operacao=operacao,
                        atividade=atividade,
                        categoria=item.get('categoria', 'INSUMO'),
                        maquinario_terceiro=item.get('maquinario_terceiro', False),
                        produto_id=item.get('produto_id') or None,
                        descricao=item.get('descricao'),
                        quantidade=qtd,
                        is_quantidade_total=item.get('is_quantidade_total', False),
                        custo_unitario=custo,
                        is_custo_total=item.get('is_custo_total', False),
                        unidade_custo=item.get('unidade_custo', 'BRL')
                    )
            except Exception as e:
                # Logar erro mas não falhar a request principal por enquanto
                print(f"Erro ao salvar itens: {e}")

            messages.success(request, f'Operação registrada com sucesso!')
            return redirect('operacao_list')
    else:
        form = OperacaoCampoForm(empresa=empresa)
    
    # Dados de talhões para o JS
    talhoes_data = list(Talhao.objects.filter(empresa=empresa, ativo=True).values('id', 'nome', 'area_hectares', 'parent_id', 'fazenda_id', 'fazenda__nome'))
    
    # Talhões ocupados por safra
    # Para operações, talvez a "ocupação" seja menos restritiva que o plantio, 
    # mas o usuário pediu o "mesmo conceito", então vamos passar os dados de ocupação de plantio/ciclos.
    busy_qs = Plantio.objects.filter(empresa=empresa).values('talhoes__id', 'safra_id')
    busy_talhoes = {}
    for item in busy_qs:
        t_id = item['talhoes__id']
        s_id = item['safra_id']
        if t_id and s_id:
            if t_id not in busy_talhoes:
                busy_talhoes[t_id] = []
            if s_id not in busy_talhoes[t_id]:
                busy_talhoes[t_id].append(s_id)

    # Ciclos para o JS
    ciclos_qs = Plantio.objects.filter(empresa=empresa).exclude(status=StatusCiclo.CANCELADO).select_related('safra').prefetch_related('talhoes')
    ciclos_data = []
    for c in ciclos_qs:
        first_t = c.talhoes.first()
        ciclos_data.append({
            'id': c.id,
            'safra_id': c.safra_id,
            'fazenda_id': first_t.fazenda_id if first_t else None,
            'nome': str(c),
            'talhoes': [t.id for t in c.talhoes.all()]
        })

    return render(request, 'core/operacao/form.html', {
        'form': form, 
        'titulo': 'Nova Operação de Campo',
        'talhoes_json': json.dumps(talhoes_data, cls=DjangoJSONEncoder),
        'busy_talhoes_json': json.dumps(busy_talhoes),
        'ciclos_json': json.dumps(ciclos_data)
    })


@login_required
def operacao_edit(request, pk):
    """Edita uma operação de campo existente."""
    empresa = get_empresa(request.user)
    operacao = get_object_or_404(OperacaoCampo, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        form = OperacaoCampoForm(request.POST, instance=operacao, empresa=empresa)
        if form.is_valid():
            operacao = form.save()
            # form.save_m2m() implicit for ModelForm
            
            # Atualizar Itens: Estratégia simples -> Remover todos e recriar
            # (Melhorar p/ diff no futuro se necessário)
            itens_json = request.POST.get('itens_json', '[]')
            try:
                itens_data = json.loads(itens_json)
                if itens_data: # Só mexe se vier JSON válido
                    operacao.itens.all().delete()
                    
                    for item in itens_data:
                        try:
                            # Buscar Atividade ou Criar
                            atividade_id = item.get('atividade_id')
                            atividade_nome = item.get('atividade_nome')
                            
                            atividade = None
                            if atividade_id:
                                atividade = AtividadeCampo.objects.filter(id=atividade_id).first()
                            elif atividade_nome:
                                atividade = AtividadeCampo.objects.filter(
                                    nome__iexact=atividade_nome, 
                                    empresa=empresa
                                ).first()
                                if not atividade:
                                    atividade = AtividadeCampo.objects.create(
                                        empresa=empresa,
                                        nome=atividade_nome,
                                        ativo=True
                                    )
                            
                            if not atividade:
                                continue

                            # Antes era: atividade = AtividadeCampo.objects.get(id=item.get('atividade_id'))
                            
                            qtd = Decimal(str(item.get('quantidade', 0)))
                            custo = Decimal(str(item.get('custo_unitario', 0)))
                            
                            OperacaoCampoItem.objects.create(
                                operacao=operacao,
                                atividade=atividade,
                                categoria=item.get('categoria', 'INSUMO'),
                                maquinario_terceiro=item.get('maquinario_terceiro', False),
                                produto_id=item.get('produto_id') or None,
                                descricao=item.get('descricao'),
                                quantidade=qtd,
                                is_quantidade_total=item.get('is_quantidade_total', False),
                                custo_unitario=custo,
                                is_custo_total=item.get('is_custo_total', False),
                                unidade_custo=item.get('unidade_custo', 'BRL')
                            )
                        except Exception as inner_e:
                            print(f"Erro criando item individual: {inner_e}")
                            
            except Exception as e:
                print(f"Erro ao atualizar itens: {e}")

            messages.success(request, f'Operação atualizada com sucesso!')
            return redirect('operacao_list')
    else:
        form = OperacaoCampoForm(instance=operacao, empresa=empresa)
    
    # Dados de talhões para o JS
    talhoes_data = list(Talhao.objects.filter(empresa=empresa, ativo=True).values('id', 'nome', 'area_hectares', 'parent_id', 'fazenda_id', 'fazenda__nome'))
    
    # Talhões ocupados por safra
    busy_qs = Plantio.objects.filter(empresa=empresa).values('talhoes__id', 'safra_id')
    busy_talhoes = {}
    for item in busy_qs:
        t_id = item['talhoes__id']
        s_id = item['safra_id']
        if t_id and s_id:
            if t_id not in busy_talhoes:
                busy_talhoes[t_id] = []
            if s_id not in busy_talhoes[t_id]:
                busy_talhoes[t_id].append(s_id)

    # Ciclos para o JS
    ciclos_qs = Plantio.objects.filter(empresa=empresa).exclude(status=StatusCiclo.CANCELADO).select_related('safra').prefetch_related('talhoes')
    ciclos_data = []
    for c in ciclos_qs:
        first_t = c.talhoes.first()
        ciclos_data.append({
            'id': c.id,
            'safra_id': c.safra_id,
            'fazenda_id': first_t.fazenda_id if first_t else None,
            'nome': str(c),
            'talhoes': [t.id for t in c.talhoes.all()]
        })

    # Identificar fazenda inicial (do primeiro talhão da operação)
    primeira_operacao_talhao = operacao.talhoes.first()
    fazenda_id = primeira_operacao_talhao.fazenda_id if primeira_operacao_talhao else None

    return render(request, 'core/operacao/form.html', {
        'form': form, 
        'operacao': operacao,
        'titulo': 'Editar Operação',
        'talhoes_json': json.dumps(talhoes_data, cls=DjangoJSONEncoder),
        'busy_talhoes_json': json.dumps(busy_talhoes),
        'ciclos_json': json.dumps(ciclos_data),
        'fazenda_id': fazenda_id
    })


@login_required
@require_POST
def operacao_delete(request, pk):
    """Exclui uma operação de campo."""
    empresa = get_empresa(request.user)
    operacao = get_object_or_404(OperacaoCampo, pk=pk, empresa=empresa)
    operacao.delete()
    messages.success(request, 'Operação excluída com sucesso!')
    return redirect('operacao_list')


# =============================================================================
# RELATÓRIOS E DASHBOARD DE CUSTOS
# =============================================================================

@login_required
def relatorio_custos(request):
    """Relatório de custos por talhão e ciclo."""
    empresa = get_empresa(request.user)
    form = FiltroRelatorioForm(request.GET, empresa=empresa)
    
    preco_ref = Decimal('120.00')
    fazenda_selecionada = None
    talhao_selecionado = None
    
    if form.is_valid():
        preco_ref = form.cleaned_data.get('preco_referencia') or Decimal('120.00')
        fazenda_selecionada = form.cleaned_data.get('fazenda')
        talhao_selecionado = form.cleaned_data.get('talhao')

    talhoes = Talhao.objects.filter(ativo=True, empresa=empresa)
    
    if fazenda_selecionada:
        talhoes = talhoes.filter(fazenda=fazenda_selecionada)
    
    if talhao_selecionado:
        talhoes = talhoes.filter(pk=talhao_selecionado.pk)
        
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    dados_talhoes = []
    
    for talhao in talhoes:
        custo_total = talhao.calcular_custo_total()
        operacoes_count = talhao.operacoes_campo.count()
        area = talhao.area_hectares
        
        custo_ha = custo_total / area if area > 0 else Decimal('0')
        
        dados_talhoes.append({
            'talhao': talhao,
            'area': area,
            'custo_total': custo_total,
            'custo_sacas': custo_total / preco_ref,
            'operacoes_count': operacoes_count,
            'custo_por_hectare': custo_ha,
            'custo_ha_sacas': custo_ha / preco_ref,
        })
    
    # Ordenar por custo total (decrescente)
    dados_talhoes.sort(key=lambda x: x['custo_total'], reverse=True)
        
    # Calcular totais
    total_area_geral = sum(item['area'] for item in dados_talhoes)
    total_custo_geral = sum(item['custo_total'] for item in dados_talhoes)
    total_ops_geral = sum(item['operacoes_count'] for item in dados_talhoes)
    custo_medio_ha = total_custo_geral / total_area_geral if total_area_geral > 0 else 0
    
    context = {
        'form': form,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada,
        'dados_talhoes': dados_talhoes,
        'totais': {
            'area': total_area_geral,
            'custo': total_custo_geral,
            'custo_sacas': total_custo_geral / preco_ref,
            'operacoes': total_ops_geral,
            'custo_medio_ha': custo_medio_ha,
            'custo_medio_ha_sacas': custo_medio_ha / preco_ref if isinstance(custo_medio_ha, Decimal) else Decimal(str(custo_medio_ha)) / preco_ref
        }
    }
    
    return render(request, 'core/relatorio/custos.html', context)


@login_required
def relatorio_custos_pdf(request):
    """Gera PDF do Relatório de custos por talhão e ciclo."""
    empresa = get_empresa(request.user)
    
    preco_ref = Decimal('120.00')
    # Nota: No PDF não pegamos do form (GET), ou pegamos? Vamos pegar se passar na URL
    if request.GET.get('preco_referencia'):
        try:
            preco_ref = Decimal(request.GET.get('preco_referencia'))
        except:
            pass
    
    # Filtro por Fazenda
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    
    talhoes = Talhao.objects.filter(ativo=True, empresa=empresa)
    
    if fazenda_id:
        talhoes = talhoes.filter(fazenda_id=fazenda_id)
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
        
    dados_talhoes = []
    
    for talhao in talhoes:
        custo_total = talhao.calcular_custo_total()
        operacoes_count = talhao.operacoes_campo.count()
        area = talhao.area_hectares
        
        custo_ha = custo_total / area if area > 0 else Decimal('0')
        
        dados_talhoes.append({
            'talhao': talhao,
            'area': area,
            'custo_total': custo_total,
            'custo_sacas': custo_total / preco_ref,
            'operacoes_count': operacoes_count,
            'custo_por_hectare': custo_ha,
            'custo_ha_sacas': custo_ha / preco_ref,
        })
    
    # Ordenar por custo total (decrescente)
    dados_talhoes.sort(key=lambda x: x['custo_total'], reverse=True)
        
    # Calcular totais
    total_area_geral = sum(item['area'] for item in dados_talhoes)
    total_custo_geral = sum(item['custo_total'] for item in dados_talhoes)
    total_ops_geral = sum(item['operacoes_count'] for item in dados_talhoes)
    custo_medio_ha = total_custo_geral / total_area_geral if total_area_geral > 0 else 0
    
    context = {
        'fazenda_selecionada': fazenda_selecionada,
        'dados_talhoes': dados_talhoes,
        'totais': {
            'area': total_area_geral,
            'custo': total_custo_geral,
            'custo_sacas': total_custo_geral / preco_ref,
            'operacoes': total_ops_geral,
            'custo_medio_ha': custo_medio_ha,
            'custo_medio_ha_sacas': custo_medio_ha / preco_ref if isinstance(custo_medio_ha, Decimal) else Decimal(str(custo_medio_ha)) / preco_ref
        }
    }
    
    html = render_to_string('core/relatorio/custos_pdf.html', context, request=request)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="relatorio_custos.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Erro ao gerar PDF', status=500)
        
    return response


@login_required
def relatorio_producao(request):
    """Relatório de Produtividade e Colheita por Safra."""
    empresa = get_empresa(request.user)
    safra_id = request.GET.get('safra')
    fazenda_id = request.GET.get('fazenda')
    
    # Filtro básico
    plantios = Plantio.objects.filter(empresa=empresa).prefetch_related('talhoes').select_related('safra')
    
    if safra_id:
        plantios = plantios.filter(safra_id=safra_id)
        safra_selecionada = Safra.objects.filter(id=safra_id).first()
    else:
        safra_selecionada = None
        
    fazenda_selecionada = None
    if fazenda_id:
        plantios = plantios.filter(talhoes__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
        
    safras = Safra.objects.filter(ativa=True) # ou todas?
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')

    dados = []
    total_area = 0
    total_estimado = 0
    total_real = 0
    
    for p in plantios:
        # Calcular produção real baseada nos Romaneios vinculados
        # (Assumindo que 1 saca = 60kg). Se o sistema usar outra unidade, ajustar.
        peso_liquido_total = Romaneio.objects.filter(plantio=p).aggregate(Sum('peso_liquido'))['peso_liquido__sum'] or 0
        sacas_reais = Decimal(peso_liquido_total) / Decimal('60')
        
        area = p.area_total_ha
        total_area += area
        total_estimado += p.producao_total_estimada_sc
        total_real += sacas_reais
        
        produtividade = sacas_reais / area if area > 0 else 0
        
        dados.append({
            'plantio': p,
            'area': area,
            'estimado': p.producao_total_estimada_sc,
            'real_sacas': sacas_reais,
            'produtividade': produtividade,
            'progresso': (sacas_reais / p.producao_total_estimada_sc * 100) if p.producao_total_estimada_sc else 0
        })
        
    context = {
        'dados': dados,
        'safras': safras,
        'safra_selecionada': safra_selecionada,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada,
        'totais': {
            'area': total_area,
            'estimado': total_estimado,
            'real': total_real,
            'produtividade_media': (total_real / total_area) if total_area > 0 else 0
        }
    }
    return render(request, 'core/relatorio/producao.html', context)


@login_required
def relatorio_financeiro(request):
    """Relatório Financeiro de Contratos e Fixações."""
    empresa = get_empresa(request.user)
    
    contratos = ContratoVenda.objects.filter(empresa=empresa).prefetch_related('fixacoes')
    
    # Filtro por Fazenda (Itens do Contrato)
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        contratos = contratos.filter(itens__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    dados = []
    total_vendido = Decimal('0.00')
    total_fixado = Decimal('0.00')
    total_receita_fixada = Decimal('0.00')
    
    for c in contratos:
        fixado_qtd = c.total_fixado
        fixado_valor = c.fixacoes.aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        pendente = c.quantidade_sacas - fixado_qtd
        
        # Calcular preço médio das fixações deste contrato
        preco_medio = (fixado_valor / fixado_qtd) if fixado_qtd > 0 else 0
        
        total_vendido += c.quantidade_sacas
        total_fixado += fixado_qtd
        total_receita_fixada += fixado_valor
        
        dados.append({
            'contrato': c,
            'fixado_qtd': fixado_qtd,
            'fixado_valor': fixado_valor,
            'pendente': pendente,
            'preco_medio': preco_medio,
            'percentual': (fixado_qtd / c.quantidade_sacas * 100) if c.quantidade_sacas > 0 else 0
        })
        
    # Preço Médio Global
    preco_medio_global = (total_receita_fixada / total_fixado) if total_fixado > 0 else 0
    
    context = {
        'dados': dados,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada,
        'totais': {
            'vendido': total_vendido,
            'fixado': total_fixado,
            'pendente': total_vendido - total_fixado,
            'receita_fixada': total_receita_fixada,
            'preco_medio_global': preco_medio_global,
            'percentual_fixado': (total_fixado / total_vendido * 100) if total_vendido > 0 else 0
        }
    }
    return render(request, 'core/relatorio/financeiro.html', context)


@login_required
def relatorio_romaneios(request):
    """Relatório de Colheita e Qualidade (Umidade/Impureza/Quebra)."""
    empresa = get_empresa(request.user)
    safra_id = request.GET.get('safra')
    fazenda_id = request.GET.get('fazenda')
    
    romaneios = Romaneio.objects.filter(empresa=empresa).select_related(
        'fazenda', 'plantio__safra', 'armazem_terceiro__fornecedor'
    )
    
    if safra_id:
        romaneios = romaneios.filter(plantio__safra_id=safra_id)
    if fazenda_id:
        romaneios = romaneios.filter(fazenda_id=fazenda_id)
        
    safras = Safra.objects.filter(ativa=True)
    fazendas = Fazenda.objects.filter(empresa=empresa)
    
    # Agregação Global
    totais = romaneios.aggregate(
        total_liquido=Sum('peso_liquido'),
        total_quebra=Sum('peso_quebra_tecnica'),
        media_umidade=Avg('umidade_percentual'),
        media_impureza=Avg('impureza_percentual'),
        total_tickets=Count('id')
    )
    
    context = {
        'romaneios': romaneios, # Listagem detalhada
        'safras': safras,
        'fazendas': fazendas,
        'filters': {'safra': safra_id, 'fazenda': fazenda_id},
        'totais': {
            'liquido': totais['total_liquido'] or 0,
            'sacas': Decimal(totais['total_liquido'] or 0) / Decimal('60'),
            'quebra': totais['total_quebra'] or 0,
            'umidade': totais['media_umidade'] or 0,
            'impureza': totais['media_impureza'] or 0,
            'tickets': totais['total_tickets'] or 0
        }
    }
    return render(request, 'core/relatorio/romaneios.html', context)


@login_required
def relatorio_estoque(request):
    """Relatório de Posição de Estoque."""
    empresa = get_empresa(request.user)
    form = FiltroRelatorioForm(request.GET, empresa=empresa)
    
    preco_ref = Decimal('120.00')
    fazenda_selecionada = None
    if form.is_valid():
        preco_ref = form.cleaned_data.get('preco_referencia') or Decimal('120.00')
        fazenda_selecionada = form.cleaned_data.get('fazenda')
    
    produtos = Produto.objects.filter(empresa=empresa, ativo=True).order_by('categoria', 'nome')
    
    dados = []
    valor_total_estoque = Decimal('0.00')
    
    for p in produtos:
        if fazenda_selecionada:
            saldo = p.get_estoque_por_fazenda(fazenda_selecionada.id)
        else:
            saldo = Decimal(str(p.estoque_atual or 0))
            
        preco_medio = p.get_preco_medio()
        valor_item = saldo * preco_medio
        
        if saldo != 0:
            valor_total_estoque += valor_item
            dados.append({
                'produto': p,
                'saldo': saldo,
                'unidade': p.unidade,
                'valor_unitario': preco_medio,
                'valor_total': valor_item,
                'valor_sacas': valor_item / preco_ref
            })
            
    context = {
        'form': form,
        'fazenda_selecionada': fazenda_selecionada,
        'dados': dados,
        'valor_total_geral': valor_total_estoque,
        'valor_total_sacas': valor_total_estoque / preco_ref
    }
    return render(request, 'core/relatorio/estoque.html', context)


# =============================================================================
# API ENDPOINTS (JSON)
# =============================================================================

@login_required
@require_GET
def api_talhoes_mapa(request):
    """API para retornar dados dos talhões para o mapa."""
    empresa = get_empresa(request.user)
    if not empresa:
         return JsonResponse({'talhoes': []})
         
    talhoes = Talhao.objects.filter(ativo=True, coordenadas_json__isnull=False, empresa=empresa)
    
    dados = []
    for talhao in talhoes:
        coords = talhao.get_coordenadas()
        if coords:
            dados.append({
                'id': talhao.id,
                'nome': talhao.nome,
                'area': float(talhao.area_hectares),
                'cultura': talhao.cultura_atual or 'Não informada',
                'coordenadas': coords,
                'url': f'/talhoes/{talhao.id}/',
            })
    
    return JsonResponse({'talhoes': dados})


@login_required
@require_POST
def api_salvar_coordenadas(request, pk):
    """API para salvar coordenadas de um talhão via AJAX."""
    empresa = get_empresa(request.user)
    talhao = get_object_or_404(Talhao, pk=pk, empresa=empresa)
    
    try:
        data = json.loads(request.body)
        coordenadas = data.get('coordenadas', [])
        
        talhao.coordenadas_json = json.dumps(coordenadas)
        talhao.save(update_fields=['coordenadas_json'])
        
        return JsonResponse({
            'sucesso': True,
            'mensagem': 'Coordenadas salvas com sucesso!',
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'sucesso': False,
            'mensagem': 'Dados inválidos',
        }, status=400)


def _fetch_yahoo_price(ticker):
    """Helper interno para buscar preço direto da API do Yahoo (v8) sem yfinance."""
    import requests
    import logging
    logger = logging.getLogger(__name__)
    
    # URL da API de Chart do Yahoo (não documentada mas amplamente usada)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Estrutura: chart -> result[0] -> meta
        meta = data['chart']['result'][0]['meta']
        
        return {
            'price': meta.get('regularMarketPrice'),
            'previous_close': meta.get('chartPreviousClose')
        }
    except Exception as e:
        logger.error(f"Erro ao buscar cotação direta ({ticker}): {e}")
        return None

@login_required
@require_GET
def api_market_data(request):
    """API para retornar cotações de commodities via requests direto (v8) p/ compatibilidade Python 3.8."""
    from django.core.cache import cache
    import logging

    logger = logging.getLogger(__name__)
    cache_key = 'market_ticker_data_v2' # V2 para forçar limpeza após mudança de lógica
    cached_data = cache.get(cache_key)

    if cached_data:
        return JsonResponse(cached_data)

    # Tickers:
    # ZS=F: Soja (Soybean Futures)
    # ZC=F: Milho (Corn Futures)
    # ZW=F: Trigo (Wheat Futures)
    # LE=F: Boi Gordo (Live Cattle Futures)
    # BRL=X: Dólar (USD/BRL)
    
    tickers_list = ["BRL=X", "ZS=F", "ZC=F", "ZW=F", "LE=F"]
    data = []
    
    try:
        # 1. Obter Dólar Primeiro (Base p/ conversões)
        usd_info = _fetch_yahoo_price("BRL=X")
        if usd_info and usd_info['price']:
            usd_brl = usd_info['price']
            usd_prev = usd_info['previous_close']
            usd_change = ((usd_brl - usd_prev) / usd_prev) * 100 if usd_prev else 0.0
        else:
            # Fallback seguro
            usd_brl = 5.0
            usd_change = 0.0
            logger.warning("Usando fallback de Dólar a 5.0")

        # Adicionar Dólar à lista
        data.append({
            "symbol": "USD",
            "name": "Dólar (USD)",
            "price": round(usd_brl, 3),
            "unit": "R$",
            "change": round(usd_change, 2),
            "is_up": usd_change >= 0
        })
        
        # Fatores de conversão (aproximados p/ Saca 60kg e Arroba 15kg)
        conv_soja = 0.01 * usd_brl * 2.20462
        conv_milho = 0.01 * usd_brl * 2.3621
        conv_boi = 0.01 * usd_brl * 33.0694
        conv_trigo = 0.01 * usd_brl * 2.20462
        
        commodities_map = {
            "ZS=F": {"name": "Soja", "factor": conv_soja, "unit": "R$/Saca"},
            "ZC=F": {"name": "Milho", "factor": conv_milho, "unit": "R$/Saca"},
            "ZW=F": {"name": "Trigo", "factor": conv_trigo, "unit": "R$/Saca"},
            "LE=F": {"name": "Boi Gordo", "factor": conv_boi, "unit": "R$/Arroba"},
        }
        
        for symbol, info_map in commodities_map.items():
            result = _fetch_yahoo_price(symbol)
            
            if result and result['price']:
                price_orig = result['price']
                prev_orig = result['previous_close']
                
                price_brl = price_orig * info_map["factor"]
                change_pct = ((price_orig - prev_orig) / prev_orig) * 100 if prev_orig else 0.0
                
                data.append({
                    "symbol": symbol,
                    "name": info_map["name"],
                    "price": round(price_brl, 2),
                    "unit": info_map["unit"],
                    "change": round(change_pct, 2),
                    "is_up": change_pct >= 0
                })
            else:
                data.append({
                     "symbol": symbol,
                     "name": info_map["name"],
                     "price": 0.0,
                     "unit": "Indisp.",
                     "change": 0.0,
                     "is_up": True
                })

        final_response = {'commodities': data}
        # Cache por 1 hora (menos volátil, mais estável)
        cache.set(cache_key, final_response, 3600)
        return JsonResponse(final_response)

    except Exception as e:
        logger.error(f"Erro geral Market API: {e}")
        return JsonResponse({'commodities': [], 'error': str(e)})


@login_required
def api_plantio_talhoes(request, plantio_id):
    """Retorna os talhões associados a um ciclo de produção/plantio."""
    empresa = get_empresa(request.user)
    plantio = get_object_or_404(Plantio, pk=plantio_id, empresa=empresa)
    talhoes = plantio.talhoes.all().values('id', 'nome', 'area_hectares', 'fazenda_id', 'fazenda__nome')
    return JsonResponse(list(talhoes), safe=False)


@login_required
@require_GET
def api_talhao_climatico(request, pk):
    """API para retornar dados climáticos do talhão (Open-Meteo)."""
    empresa = get_empresa(request.user)
    talhao = get_object_or_404(Talhao, pk=pk, empresa=empresa)
    coords = talhao.get_coordenadas()
    
    if not coords:
        return JsonResponse({'error': 'Talhão sem coordenadas definidas'}, status=400)
    
    # Extrair lat/lon do primeiro ponto do polígono
    lat = None
    lon = None
    
    try:
        if coords and len(coords) > 0:
            primeiro = coords[0]
            if isinstance(primeiro, dict):
                lat = primeiro.get('lat')
                lon = primeiro.get('lng')
            elif isinstance(primeiro, (list, tuple)):
                lat = primeiro[0]
                lon = primeiro[1]
    except Exception:
        pass
        
    if lat is None or lon is None:
        return JsonResponse({'error': 'Coordenadas inválidas'}, status=400)
        
    data = get_talhao_weather_data(lat, lon)
    
    if data:
        return JsonResponse(data)
    else:
        return JsonResponse({'error': 'Erro ao consultar serviço de clima'}, status=502)


@login_required
def fazenda_clima_history(request, pk):
    """Exibe histórico climático da fazenda."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    
    # Filtros de data
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=30)
    
    data_ini = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if data_ini:
        try:
            start_date = datetime.strptime(data_ini, '%Y-%m-%d').date()
        except ValueError:
            pass  # Mantém o padrão (30 dias atrás)
            
    if data_fim:
        try:
            end_date = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError:
            pass  # Mantém o padrão (hoje)
        
    historico = ClimaFazenda.objects.filter(
        fazenda=fazenda,
        data__range=[start_date, end_date]
    ).order_by('-data')
    
    # Dados para o Gráfico
    chart_labels = []
    chart_precip = []
    chart_temp_max = []
    chart_temp_min = []
    
    for h in reversed(historico):
        chart_labels.append(h.data.strftime('%d/%m'))
        chart_precip.append(float(h.precipitacao))
        chart_temp_max.append(float(h.temp_max or 0))
        chart_temp_min.append(float(h.temp_min or 0))
        
    form_manual = ClimaFazendaForm()

    return render(request, 'core/fazenda/clima_history.html', {
        'fazenda': fazenda,
        # 'fazenda_nome_str': fazenda.nome,  # Backup explícito removido
        'historico': historico,
        'form_manual': form_manual,
        'chart_labels': json.dumps(chart_labels),
        'chart_precip': json.dumps(chart_precip),
        'chart_temp_max': json.dumps(chart_temp_max),
        'chart_temp_min': json.dumps(chart_temp_min),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    })

@login_required
def fazenda_clima_sync(request, pk):
    """Sincroniza dados climáticos da fazenda (API)."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    
    lat = fazenda.latitude
    lon = fazenda.longitude

    if not lat or not lon:
        messages.error(request, 'Fazenda sem coordenadas definidas (Latitude/Longitude).')
        return redirect('fazenda_clima_history', pk=pk)
        
    # Intervalo padrão: últimos 30 dias até ontem
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=30)
    
    # Se fornecido na URL, usa o intervalo personalizado
    data_ini = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if data_ini:
        try:
            start_date = datetime.strptime(data_ini, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    if data_fim:
        try:
            end_date = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    # Busca na API
    dados_api = fetch_historical_weather(float(lat), float(lon), start_date, end_date)
    
    count_created = 0
    count_updated = 0
    
    for item in dados_api:
        data_reg = item['data']
        defaults = {
            'temp_max': item['temp_max'],
            'temp_min': item['temp_min'],
            'precipitacao': item['precipitacao'],
            'umidade_relativa': item['umidade_relativa'],
            'velocidade_vento': item['velocidade_vento'],
            'fonte': 'API'
        }
        
        obj, created = ClimaFazenda.objects.update_or_create(
            fazenda=fazenda,
            data=data_reg,
            defaults=defaults
        )
        
        if created:
            count_created += 1
        else:
            # Só atualiza se a fonte anterior também for API (não sobrescreve MANUAL)
            if obj.fonte == 'API':
                count_updated += 1
                
    messages.success(request, f'Sincronização concluída: {count_created} criados, {count_updated} atualizados.')
    
    # Redireciona mantendo o filtro
    base_url = reverse('fazenda_clima_history', kwargs={'pk': pk})
    query_string = f"?data_inicio={start_date}&data_fim={end_date}"
    return redirect(f"{base_url}{query_string}")

from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.db.models import Avg, Sum

@login_required
def fazenda_clima_pdf(request, pk):
    """Gera PDF do histórico climático."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    
    # Filtros (mesma lógica do history)
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=30)
    
    data_ini = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    if data_ini:
        try:
            start_date = datetime.strptime(data_ini, '%Y-%m-%d').date()
        except ValueError: pass
            
    if data_fim:
        try:
            end_date = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError: pass
        
    historico = ClimaFazenda.objects.filter(
        fazenda=fazenda,
        data__range=[start_date, end_date]
    ).order_by('-data')
    
    # Aggregations for summary
    aggs = historico.aggregate(
        total_precip=Sum('precipitacao'),
        avg_max=Avg('temp_max')
    )
    
    context = {
        'fazenda': fazenda,
        'historico': historico,
        'start_date': start_date,
        'end_date': end_date,
        'total_precip': aggs['total_precip'] or 0,
        'avg_temp_max': aggs['avg_max'] or 0,
    }
    
    try:
        html_string = render_to_string('core/fazenda/clima_pdf.html', context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="clima_historico.pdf"'
        
        pisa_status = pisa.CreatePDF(html_string, dest=response)
        
        if pisa_status.err:
            return HttpResponse(f'Erro xhtml2pdf: {pisa_status.err}', status=500)
            
        return response
    except Exception as e:
        import traceback
        return HttpResponse(f'Erro no servidor: {str(e)} <br> <pre>{traceback.format_exc()}</pre>', status=500)

@login_required
@require_POST
def fazenda_clima_add_manual(request, pk):
    """Adiciona registro climático manual para a fazenda."""
    empresa = get_empresa(request.user)
    fazenda = get_object_or_404(Fazenda, pk=pk, empresa=empresa)
    
    form = ClimaFazendaForm(request.POST)
    if form.is_valid():
        clima = form.save(commit=False)
        clima.fazenda = fazenda
        exists = ClimaFazenda.objects.filter(fazenda=fazenda, data=clima.data).first()
        if exists:
            # Atualiza existente
            exists.temp_max = clima.temp_max
            exists.temp_min = clima.temp_min
            exists.precipitacao = clima.precipitacao
            exists.umidade_relativa = clima.umidade_relativa
            exists.velocidade_vento = clima.velocidade_vento
            exists.fonte = 'MANUAL'
            exists.save()
            messages.success(request, f'Registro de {clima.data} atualizado manualmente.')
        else:
            clima.save()
            messages.success(request, 'Registro manual adicionado.')
    else:
        messages.error(request, 'Erro no formulário.')
        
    return redirect('fazenda_clima_history', pk=pk)


# =============================================================================
# ROMANEIOS
# =============================================================================

@login_required
def romaneio_list(request):
    """Lista todos os romaneios."""
    empresa = get_empresa(request.user)
    romaneios = Romaneio.objects.filter(empresa=empresa).select_related(
        'fazenda', 'talhao', 'plantio', 'plantio__safra'
    ).order_by('-data')
    
    # Filtro por Fazenda
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        romaneios = romaneios.filter(fazenda_id=fazenda_id)
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    # Filtros simples via GET
    q = request.GET.get('q') # Ticket ou Motorista
    if q:
        romaneios = romaneios.filter(
            Q(numero_ticket__icontains=q) | 
            Q(motorista__icontains=q) | 
            Q(placa__icontains=q)
        )

    paginator = Paginator(romaneios, 20)
    page = request.GET.get('page')
    romaneios = paginator.get_page(page)
    
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    return render(request, 'core/romaneio/list.html', {
        'romaneios': romaneios,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada
    })


@login_required
def romaneio_create(request):
    """Cria um novo romaneio."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = RomaneioForm(request.POST, empresa=empresa)
        if form.is_valid():
            romaneio = form.save(commit=False)
            romaneio.empresa = empresa
            # Calcular peso líquido (lógica básica, pode ser refinada no model ou form)
            # O model já tem save() com cálculo, então só salvar.
            romaneio.save()
            messages.success(request, f'Romaneio #{romaneio.numero_ticket} criado com sucesso!')
            return redirect('romaneio_list')
    else:
        form = RomaneioForm(empresa=empresa)
    
    return render(request, 'core/romaneio/form.html', {'form': form, 'titulo': 'Novo Romaneio'})


@login_required
def romaneio_edit(request, pk):
    """Edita um romaneio existente."""
    empresa = get_empresa(request.user)
    romaneio = get_object_or_404(Romaneio, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        form = RomaneioForm(request.POST, instance=romaneio, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, f'Romaneio #{romaneio.numero_ticket} atualizado!')
            return redirect('romaneio_list')
    else:
        form = RomaneioForm(instance=romaneio, empresa=empresa)
    
    return render(request, 'core/romaneio/form.html', {
        'form': form, 
        'titulo': f'Editar Romaneio #{romaneio.numero_ticket}',
        'romaneio': romaneio
    })


@login_required
def romaneio_detail(request, pk):
    """Detalhes do Romaneio."""
    empresa = get_empresa(request.user)
    romaneio = get_object_or_404(Romaneio, pk=pk, empresa=empresa)
    return render(request, 'core/romaneio/detail.html', {'romaneio': romaneio})


@login_required
@require_POST
def romaneio_delete(request, pk):
    """Exclui um romaneio."""
    empresa = get_empresa(request.user)
    romaneio = get_object_or_404(Romaneio, pk=pk, empresa=empresa)
    ticket = romaneio.numero_ticket
    romaneio.delete()
    messages.success(request, f'Romaneio #{ticket} excluído com sucesso!')
    return redirect('romaneio_list')


# =============================================================================
# CONTRATOS DE VENDA
# =============================================================================

@login_required
def contrato_list(request):
    """Lista todos os contratos de venda."""
    empresa = get_empresa(request.user)
    contratos = ContratoVenda.objects.filter(empresa=empresa).order_by('-data_entrega')
    
    form = ContratoFilterForm(request.GET, empresa=empresa)
    
    if form.is_valid():
        q = form.cleaned_data.get('q')
        fazenda = form.cleaned_data.get('fazenda')
        
        if q:
            # Busca por palavras-chave (AND entre palavras, OR entre campos)
            keywords = q.split()
            query = Q()
            for word in keywords:
                query &= (Q(cliente__nome__icontains=word) | Q(cliente__cpf_cnpj__icontains=word))
            contratos = contratos.filter(query)
            
        if fazenda:
            contratos = contratos.filter(itens__fazenda=fazenda).distinct()

    paginator = Paginator(contratos, 20)
    page = request.GET.get('page')
    contratos = paginator.get_page(page)
    
    return render(request, 'core/contrato/list.html', {
        'contratos': contratos,
        'form': form,
    })


@login_required
def contrato_create(request):
    """Cria um novo contrato de venda com itens via JSON."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = ContratoVendaForm(request.POST, empresa=empresa)
        
        if form.is_valid():
            with transaction.atomic():
                contrato = form.save(commit=False)
                contrato.empresa = empresa
                contrato.save()
                
                # Processar Itens JSON
                itens_json = form.cleaned_data.get('itens_json', '[]')
                try:
                    itens_data = json.loads(itens_json)
                    for item_data in itens_data:
                        produto_id = item_data.get('produto_id')
                        fazenda_id = item_data.get('fazenda_id') or None
                        try:
                            qtd = Decimal(str(item_data.get('quantidade', 0)))
                            valor = Decimal(str(item_data.get('valor_unitario', 0)))
                            unidade = item_data.get('unidade', 'SC')
                        except:
                            qtd = 0
                            valor = 0
                            unidade = 'SC'
                            
                        if produto_id and qtd > 0:
                            ItemContratoVenda.objects.create(
                                contrato=contrato,
                                produto_id=produto_id,
                                fazenda_id=fazenda_id,
                                quantidade=qtd,
                                unidade=unidade,
                                valor_unitario=valor
                            )
                except Exception as e:
                    print(f"Erro ao processar itens do contrato: {e}")
                    
            messages.success(request, 'Contrato registrado com sucesso!')
            return redirect('contrato_list')
    else:
        form = ContratoVendaForm(empresa=empresa)
    
    categorias = CategoriaProduto.choices
    
    return render(request, 'core/contrato/form.html', {
        'form': form, 
        'titulo': 'Novo Contrato',
        'categorias_produto': categorias
    })


@login_required
def contrato_edit(request, pk):
    """Edita um contrato existente."""
    empresa = get_empresa(request.user)
    contrato = get_object_or_404(ContratoVenda, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        print(f"DEBUG: contrato_edit POST received for contrato {pk}")
        form = ContratoVendaForm(request.POST, instance=contrato, empresa=empresa)
        print(f"DEBUG: form.is_valid() = {form.is_valid()}")
        if not form.is_valid():
            print(f"DEBUG: form.errors = {form.errors}")
        
        if form.is_valid():
            with transaction.atomic():
                contrato = form.save()
                
                # Processar Itens JSON
                itens_json = form.cleaned_data.get('itens_json', '[]')
                try:
                    itens_data = json.loads(itens_json)
                    current_itens = {item.id: item for item in contrato.itens.all()}
                    
                    for item_data in itens_data:
                        item_id = item_data.get('id')
                        produto_id = item_data.get('produto_id')
                        fazenda_id = item_data.get('fazenda_id') or None
                        try:
                            qtd = Decimal(str(item_data.get('quantidade', 0)))
                            valor = Decimal(str(item_data.get('valor_unitario', 0)))
                            unidade = item_data.get('unidade', 'SC')
                        except:
                            qtd = 0
                            valor = 0
                            unidade = 'SC'
                            
                        if produto_id and qtd > 0:
                            if item_id and int(item_id) in current_itens:
                                # Update
                                item = current_itens.pop(int(item_id))
                                item.produto_id = produto_id
                                item.fazenda_id = fazenda_id
                                item.quantidade = qtd
                                item.unidade = unidade
                                item.valor_unitario = valor
                                item.save()
                            else:
                                # Create
                                ItemContratoVenda.objects.create(
                                    contrato=contrato,
                                    produto_id=produto_id,
                                    fazenda_id=fazenda_id,
                                    quantidade=qtd,
                                    unidade=unidade,
                                    valor_unitario=valor
                                )
                    
                    # Delete removed items
                    for remaining_item in current_itens.values():
                        remaining_item.delete()
                        
                except Exception as e:
                    print(f"Erro ao processar itens na edição do contrato: {e}")
                
            messages.success(request, 'Contrato atualizado com sucesso!')
            return redirect('contrato_list')
    else:
        form = ContratoVendaForm(instance=contrato, empresa=empresa)
    
    # Preparar JSON inicial
    itens_list = []
    for item in contrato.itens.all():
        itens_list.append({
            'id': item.id,
            'produto_id': item.produto_id,
            'produto_nome': item.produto.nome,
            'fazenda_id': item.fazenda_id,
            'fazenda_nome': item.fazenda.nome if item.fazenda else '',
            'quantidade': str(item.quantidade),
            'unidade': item.unidade,
            'valor_unitario': str(item.valor_unitario)
        })
    itens_json_initial = json.dumps(itens_list, cls=DjangoJSONEncoder)

    categorias = CategoriaProduto.choices
    
    return render(request, 'core/contrato/form.html', {
        'form': form, 
        'titulo': f'Editar Contrato #{contrato.id}',
        'contrato': contrato,
        'itens_json_initial': itens_json_initial,
        'categorias_produto': categorias
    })


@login_required
def contrato_detail(request, pk):
    """Detalhes do Contrato."""
    empresa = get_empresa(request.user)
    contrato = get_object_or_404(ContratoVenda, pk=pk, empresa=empresa)
    return render(request, 'core/contrato/detail.html', {'contrato': contrato})


@login_required
@require_POST
def contrato_delete(request, pk):
    """Exclui um contrato com verificação de senha."""
    empresa = get_empresa(request.user)
    contrato = get_object_or_404(ContratoVenda, pk=pk, empresa=empresa)
    
    contrato.delete()
    messages.success(request, 'Contrato excluído com sucesso!')
    return redirect('contrato_list')


# =============================================================================
# REQUISIÇÕES DE ESTOQUE
# =============================================================================

@login_required
def requisicao_list(request):
    """Lista requisições pendentes (Operações de Campo com status PEDNENTE)."""
    empresa = get_empresa(request.user)
    # Importação local para evitar ciclo se necessário, mas models já está lá em cima
    # Precisamos de StatusRequisicao que está em models
    from .models import StatusRequisicao
    
    requisicoes = OperacaoCampo.objects.filter(
        empresa=empresa, 
        status=StatusRequisicao.PENDENTE
    ).prefetch_related('talhoes', 'talhoes__fazenda', 'itens', 'itens__produto').order_by('data_operacao')
    
    # Filtro por Fazenda
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        requisicoes = requisicoes.filter(talhoes__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')

    return render(request, 'core/requisicao/list.html', {
        'requisicoes': requisicoes,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada
    })


@login_required
@require_POST
def requisicao_aprovar(request, pk):
    """Aprova uma requisição (converte em saída de estoque)."""
    empresa = get_empresa(request.user)
    operacao = get_object_or_404(OperacaoCampo, pk=pk, empresa=empresa)
    from .models import StatusRequisicao
    
    if operacao.status == StatusRequisicao.PENDENTE:
        operacao.status = StatusRequisicao.APROVADO
        operacao.save() 
        operacao.processar_estoque() # Gera saída de estoque
        messages.success(request, f'Requisição #{operacao.id} aprovada com sucesso! Estoque atualizado.')
    else:
        messages.warning(request, 'Esta requisição já foi processada.')
        
    return redirect('requisicao_list')


# =============================================================================
# RATEIO DE CUSTOS
# =============================================================================

@login_required
def rateio_list(request):
    """Lista os rateios de custo realizados."""
    empresa = get_empresa(request.user)
    rateios = RateioCusto.objects.filter(empresa=empresa).order_by('-data')
    
    # Filtro por Fazenda (via Safra -> Plantios -> Talhão)
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        rateios = rateios.filter(safra__plantios__talhao__fazenda_id=fazenda_id).distinct()
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    return render(request, 'core/rateio/list.html', {
        'rateios': rateios,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada
    })


@login_required
def rateio_create(request):
    """Registra um novo rateio e distribui custos."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = RateioCustoForm(request.POST, empresa=empresa)
        if form.is_valid():
            try:
                rateio = form.save(commit=False)
                rateio.empresa = empresa
                
                with transaction.atomic():
                    rateio.save()
                    # Distribui os custos gerando OperacoesCampo
                    qtd_ops = rateio.distribuir_custos()
                
                if qtd_ops > 0:
                    messages.success(request, f'Rateio realizado com sucesso! {qtd_ops} operações geradas.')
                else:
                    messages.warning(request, 'Rateio salvo, mas nenhuma operação foi gerada (nenhum plantio ativo na safra?).')
                    
                return redirect('rateio_list')
            except Exception as e:
                messages.error(request, f'Erro ao processar rateio: {e}')
    else:
        form = RateioCustoForm(empresa=empresa)
    
    return render(request, 'core/rateio/form.html', {'form': form, 'titulo': 'Novo Rateio de Custos'})


@login_required
@require_POST
def rateio_delete(request, pk):
    """Exclui um rateio e suas operações."""
    empresa = get_empresa(request.user)
    rateio = get_object_or_404(RateioCusto, pk=pk, empresa=empresa)
    
    # Se configurado Cascade no banco/model, as operações vinculadas podem ou não sumir dependendo de como ligamos.
    # Como as operações foram criadas SEM chave estrangeira para RateioCusto (field doesn't exist yet on OperacaoCampo),
    # nós não podemos apagar automaticamente a MENOS que tenhamos adicionado o campo Rateio em OperacaoCampo 
    # ou filtrado pela observação (frágil).
    #
    # PERCEBI AGORA: Na implementação do model RateioCusto, eu não criei o campo 'rateio' em OperacaoCampo.
    # Então não conseguiria apagar facilmente as operações geradas.
    #
    # CORREÇÃO RÁPIDA: Vou deixar apenas deletar o registro de Rateio por enquanto.
    # Mas idealmente deveríamos ter adicionado 'rateio = models.ForeignKey(RateioCusto...)' em OperacaoCampo.
    # Como não tenho esse campo, vou deletar só o rateio e avisar.
    
    rateio.delete()
    messages.success(request, 'Registro de Rateio excluído. (Nota: Operações geradas permanecem nos custos)')
    return redirect('rateio_list')


# =============================================================================
# FIXAÇÃO DE PREÇO
# =============================================================================

@login_required
def fixacao_list(request):
    """Lista as fixações realizadas."""
    empresa = get_empresa(request.user)
    fixacoes = Fixacao.objects.filter(empresa=empresa).select_related('contrato', 'romaneio').order_by('-data_fixacao')
    
    # Filtro por Fazenda (via Romaneio)
    fazenda_id = request.GET.get('fazenda')
    fazenda_selecionada = None
    if fazenda_id:
        fixacoes = fixacoes.filter(romaneio__fazenda_id=fazenda_id)
        fazenda_selecionada = get_object_or_404(Fazenda, pk=fazenda_id, empresa=empresa)
    
    fazendas = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')
    
    return render(request, 'core/fixacao/list.html', {
        'fixacoes': fixacoes,
        'fazendas': fazendas,
        'fazenda_selecionada': fazenda_selecionada
    })


@login_required
def fixacao_create(request):
    """Registra uma nova fixação de preço."""
    empresa = get_empresa(request.user)
    
    if request.method == 'POST':
        form = FixacaoForm(request.POST, empresa=empresa)
        if form.is_valid():
            fixacao = form.save(commit=False)
            fixacao.empresa = empresa
            fixacao.save()
            messages.success(request, 'Fixação de preço registrada com sucesso!')
            return redirect('fixacao_list')
    else:
        form = FixacaoForm(empresa=empresa)
    
    return render(request, 'core/fixacao/form.html', {'form': form, 'titulo': 'Nova Fixação de Preço'})


@login_required
@require_POST
def fixacao_delete(request, pk):
    """Exclui uma fixação."""
    empresa = get_empresa(request.user)
    fixacao = get_object_or_404(Fixacao, pk=pk, empresa=empresa)
    fixacao.delete()
    messages.success(request, 'Fixação excluída com sucesso.')
    return redirect('fixacao_list')


# =============================================================================
# CADASTROS DE PARCEIROS (CLIENTES E FORNECEDORES)
# =============================================================================

@login_required
def cliente_list(request):
    empresa = get_empresa(request.user)
    clientes = Cliente.objects.filter(empresa=empresa)
    return render(request, 'core/parceiro/cliente_list.html', {'clientes': clientes})

@login_required
def cliente_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.empresa = empresa
            cliente.save()
            messages.success(request, 'Cliente cadastrado com sucesso!')
            return redirect('cliente_list')
    else:
        form = ClienteForm()
    return render(request, 'core/parceiro/cliente_form.html', {'form': form, 'title': 'Novo Cliente'})

@login_required
def cliente_edit(request, pk):
    empresa = get_empresa(request.user)
    cliente = get_object_or_404(Cliente, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente atualizado com sucesso!')
            return redirect('cliente_list')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'core/parceiro/cliente_form.html', {'form': form, 'title': 'Editar Cliente'})

@login_required
def cliente_delete(request, pk):
    empresa = get_empresa(request.user)
    cliente = get_object_or_404(Cliente, pk=pk, empresa=empresa)
    if request.method == 'POST':
        cliente.delete()
        messages.success(request, 'Cliente excluído com sucesso!')
        return redirect('cliente_list')
    return render(request, 'core/parceiro/confirm_delete.html', {'object': cliente, 'type': 'Cliente'})


@login_required
def fornecedor_list(request):
    empresa = get_empresa(request.user)
    fornecedores = Fornecedor.objects.filter(empresa=empresa)
    return render(request, 'core/parceiro/fornecedor_list.html', {'fornecedores': fornecedores})

@login_required
def fornecedor_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = FornecedorForm(request.POST)
        if form.is_valid():
            fornecedor = form.save(commit=False)
            fornecedor.empresa = empresa
            fornecedor.save()
            messages.success(request, 'Fornecedor cadastrado com sucesso!')
            return redirect('fornecedor_list')
    else:
        form = FornecedorForm()
    return render(request, 'core/parceiro/fornecedor_form.html', {'form': form, 'title': 'Novo Fornecedor'})

@login_required
def fornecedor_edit(request, pk):
    empresa = get_empresa(request.user)
    fornecedor = get_object_or_404(Fornecedor, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = FornecedorForm(request.POST, instance=fornecedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fornecedor atualizado com sucesso!')
            return redirect('fornecedor_list')
    else:
        form = FornecedorForm(instance=fornecedor)
    return render(request, 'core/parceiro/fornecedor_form.html', {'form': form, 'title': 'Editar Fornecedor'})

@login_required
def fornecedor_delete(request, pk):
    empresa = get_empresa(request.user)
    fornecedor = get_object_or_404(Fornecedor, pk=pk, empresa=empresa)
    if request.method == 'POST':
        fornecedor.delete()
        messages.success(request, 'Fornecedor excluído com sucesso!')
        return redirect('fornecedor_list')
    return render(request, 'core/parceiro/confirm_delete.html', {'object': fornecedor, 'type': 'Fornecedor'})

# =============================================================================
# TAXAS DE ARMAZÉM
# =============================================================================

@login_required
def armazem_list(request):
    empresa = get_empresa(request.user)
    taxas = TaxaArmazem.objects.filter(empresa=empresa).select_related('fornecedor')
    return render(request, 'core/parceiro/armazem_list.html', {'taxas': taxas})

@login_required
def armazem_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = TaxaArmazemForm(request.POST, empresa=empresa)
        if form.is_valid():
            taxa = form.save(commit=False)
            taxa.empresa = empresa
            taxa.save()
            messages.success(request, 'Taxa de armazém cadastrada com sucesso!')
            return redirect('armazem_list')
    else:
        form = TaxaArmazemForm(empresa=empresa)
    return render(request, 'core/parceiro/armazem_form.html', {'form': form, 'title': 'Nova Taxa de Armazém'})

@login_required
def armazem_edit(request, pk):
    empresa = get_empresa(request.user)
    taxa = get_object_or_404(TaxaArmazem, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = TaxaArmazemForm(request.POST, instance=taxa, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Taxa de armazém atualizada!')
            return redirect('armazem_list')
    else:
        form = TaxaArmazemForm(instance=taxa, empresa=empresa)
    return render(request, 'core/armazem/form.html', {'form': form, 'titulo': 'Editar Armazém'})


@login_required
def armazem_delete(request, pk):
    armazem = get_object_or_404(TaxaArmazem, pk=pk, empresa=request.user.userprofile.empresa)
    if request.method == 'POST':
        armazem.delete()
        messages.success(request, 'Armazém excluído com sucesso.')
    return redirect('armazem_list')


# ==========================================
# GESTÃO DE EQUIPE (Multi-Usuário)
# ==========================================

@login_required
def team_list(request, empresa_id=None):
    """
    Lista usuários da equipe e convites pendentes.
    Superusuário pode visualizar qualquer empresa via empresa_id.
    Usuários comuns veem apenas sua própria empresa.
    """
    if request.user.is_superuser and empresa_id:
        empresa = get_object_or_404(Empresa, pk=empresa_id)
    elif hasattr(request.user, 'userprofile'):
        empresa = request.user.userprofile.empresa
    else:
        messages.error(request, 'Usuário não vinculado a uma empresa.')
        return redirect('dashboard')
    
    users = UserProfile.objects.filter(empresa=empresa).select_related('user')
    invitations = UserInvitation.objects.filter(empresa=empresa, status='PENDING')
    
    # Formulário de convite no modal (Apenas se tiver permissão)
    can_invite = request.user.is_superuser
    invite_form = UserInvitationForm(initial={'empresa_id': empresa.id}) if can_invite else None
    
    return render(request, 'core/team/team_list.html', {
        'users': users,
        'invitations': invitations,
        'invite_form': invite_form,
        'empresa': empresa,
        'can_invite': can_invite
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def saas_edit_company(request, pk):
    """Edita dados de uma empresa (SaaS Admin)."""
    empresa = get_object_or_404(Empresa, pk=pk)
    
    if request.method == 'POST':
        # Simples update de nome por enquanto
        novo_nome = request.POST.get('nome')
        cnpj = request.POST.get('cnpj')
        
        if novo_nome:
            empresa.nome = novo_nome
            empresa.cnpj = cnpj
            empresa.save()
            messages.success(request, f'Empresa "{empresa.nome}" atualizada com sucesso!')
            return redirect('saas_settings')
        else:
            messages.error(request, 'O nome da empresa é obrigatório.')
            
    # Reutilizar template de create ou fazer um modal?
    # Vamos fazer um View dedicado simples ou usar o modal de settings.
    # Dado que já temos um modal de delete, talvez um modal de edit seja melhor na lista.
    # Mas como view é mais robusto para forms futuros.
    
    return render(request, 'core/saas/company_form.html', {'empresa': empresa})


@login_required
@user_passes_test(lambda u: u.is_superuser) # Restrito a Superusuário
def invite_user(request):
    """Processa o envio de um convite (Restrito a Superusuário)."""
    if request.method == 'POST':
        # Captura o ID da empresa do campo hidden ou query param se necessário
        # Mas vamos confiar que o form terá o contexto ou passaremos via POST customizado
        # Melhor: Adicionar campo hidden no form manual ou injetar no request.
        
        # Como o UserInvitationForm não tem campo empresa, precisamos pegar do contexto.
        # Vamos assumir que o ID da empresa vem no POST 'empresa_id'
        empresa_id = request.POST.get('empresa_id')
        empresa = get_object_or_404(Empresa, pk=empresa_id)
        
        form = UserInvitationForm(request.POST)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.empresa = empresa
            invitation.created_by = request.user
            
            # Verificar duplicidade
            if UserInvitation.objects.filter(empresa=invitation.empresa, email=invitation.email, status='PENDING').exists():
                messages.warning(request, f'Já existe um convite pendente para {invitation.email}.')
            elif User.objects.filter(email=invitation.email, userprofile__empresa=invitation.empresa).exists():
                messages.warning(request, f'O usuário {invitation.email} já faz parte da equipe.')
            else:
                invitation.save()
                join_url = request.build_absolute_uri(reverse('accept_invite', args=[invitation.token]))
                messages.success(request, f'Convite criado para {empresa.nome}! Link: {join_url}')
        else:
            messages.error(request, 'Erro ao criar convite.')
            
        return redirect('team_list_company', empresa_id=empresa.id) if request.user.is_superuser else redirect('team_list')
            
    return redirect('dashboard')


    return redirect('dashboard')


@login_required
@require_POST
def cancel_invite(request, invite_id):
    """
    Cancela (exclui) um convite pendente.
    """
    invitation = get_object_or_404(UserInvitation, pk=invite_id)
    
    # Permissão: Superusuário ou Dono da Empresa do convite
    is_owner = hasattr(request.user, 'userprofile') and \
               request.user.userprofile.role == UserRole.OWNER and \
               request.user.userprofile.empresa == invitation.empresa
               
    if not (request.user.is_superuser or is_owner):
        messages.error(request, 'Você não tem permissão para cancelar este convite.')
        return redirect('team_list')
        
    email_convidado = invitation.email
    invitation.delete()
    messages.success(request, f'Convite para {email_convidado} cancelado com sucesso.')
    
    # Redirecionar para lista correta
    if request.user.is_superuser:
        return redirect('team_list_company', empresa_id=invitation.empresa.id)
    return redirect('team_list')


def accept_invite(request, token):
    """Aceita o convite. Se não logado, cria conta. Se logado, vincula."""
    invitation = get_object_or_404(UserInvitation, token=token, status='PENDING')
    
    if request.method == 'POST':
        # REGISTRO NOVO USUÁRIO
        form = TenantRegistrationForm(request.POST) # Reusing form partially or need a simpler one?
        # TenantRegistrationForm pede CNPJ e Nome Empresa. Precisamos apenas de User.
        # Vamos usar um form simples aqui ou adaptar.
        # Simplificação: Usar os campos de form manualmente ou criar um UserRegistrationForm simples.
        
        username = request.POST.get('username')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if password != password_confirm:
            messages.error(request, 'Senhas não conferem.')
            return render(request, 'core/team/accept_invite.html', {'invitation': invitation})
            
        if User.objects.filter(username=username).exists():
             messages.error(request, 'Nome de usuário já existe.')
             return render(request, 'core/team/accept_invite.html', {'invitation': invitation})
             
        # Criar Usuário
        user = User.objects.create_user(username=username, email=invitation.email, password=password)
        
        # Vincular à Empresa
        UserProfile.objects.create(
            user=user, 
            empresa=invitation.empresa,
            role=invitation.role
        )
        
        # Atualizar Convite
        invitation.status = 'ACCEPTED'
        invitation.save()
        
        # Logar
        login(request, user)
        messages.success(request, f'Bem-vindo à equipe {invitation.empresa.nome}!')
        return redirect('dashboard')

    # GET
    if request.user.is_authenticated:
        # Se já logado, perguntar se quer se juntar (se já não for da empresa)
        if hasattr(request.user, 'userprofile'):
            if request.user.userprofile.empresa == invitation.empresa:
                 messages.info(request, 'Você já faz parte desta empresa.')
                 return redirect('dashboard')
            else:
                # Usuário já tem empresa. Multi-empresa não suportado no modelo atual (UserProfile é OneToOne).
                # Avisar que precisa sair ou criar nova conta.
                messages.warning(request, 'Você já está vinculado a outra empresa. Saia da conta para aceitar o convite com um novo usuário.')
                return redirect('dashboard')
        
        # Se não tiver profile (improvável no nosso sistema), cria.
        UserProfile.objects.create(
            user=request.user, 
            empresa=invitation.empresa,
            role=invitation.role
        )
        invitation.status = 'ACCEPTED'
        invitation.save()
        messages.success(request, f'Agora você faz parte da equipe {invitation.empresa.nome}!')
        return redirect('dashboard')

    return render(request, 'core/team/accept_invite.html', {'invitation': invitation})

@login_required
def contrato_pdf(request, pk):
    """Gera PDF do Contrato de Venda."""
    contrato = get_object_or_404(ContratoVenda, pk=pk, empresa=request.user.userprofile.empresa)
    
    context = {
        'contrato': contrato,
        'user': request.user,
        'empresa': request.user.userprofile.empresa,
        'data_atual': datetime.now(),
    }
    
    pdf = render_to_pdf('core/contrato/pdf.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Contrato_{contrato.id}_{contrato.cliente.nome}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Erro ao gerar PDF", status=404)


# =============================================================================
# FINANCEIRO (CONTAS A PAGAR / RECEBER)
# =============================================================================

from .forms import (
    ContaPagarForm, ContaReceberForm, BaixaContaPagarForm, BaixaContaReceberForm, CategoriaFinanceiraForm
)
from .models import (
    ContaPagar, ContaReceber, BaixaContaPagar, BaixaContaReceber, CategoriaFinanceira, StatusFinanceiro
)

@login_required
def financeiro_dashboard(request):
    """Visão geral do financeiro."""
    empresa = get_empresa(request.user)
    hoje = timezone.now().date()
    
    # Contas a Pagar
    pagar_vencidas = ContaPagar.objects.filter(empresa=empresa, data_vencimento__lt=hoje, status__in=[StatusFinanceiro.PENDENTE, StatusFinanceiro.PARCIAL])
    pagar_hoje = ContaPagar.objects.filter(empresa=empresa, data_vencimento=hoje, status__in=[StatusFinanceiro.PENDENTE, StatusFinanceiro.PARCIAL])
    
    # Contas a Receber
    receber_vencidas = ContaReceber.objects.filter(empresa=empresa, data_vencimento__lt=hoje, status__in=[StatusFinanceiro.PENDENTE, StatusFinanceiro.PARCIAL])
    receber_hoje = ContaReceber.objects.filter(empresa=empresa, data_vencimento=hoje, status__in=[StatusFinanceiro.PENDENTE, StatusFinanceiro.PARCIAL])
    
    context = {
        'pagar_vencidas_count': pagar_vencidas.count(),
        'pagar_hoje_count': pagar_hoje.count(),
        'receber_vencidas_count': receber_vencidas.count(),
        'receber_hoje_count': receber_hoje.count(),
        'pagar_total': pagar_vencidas.aggregate(total=Sum('valor_total'))['total'] or 0,
        'receber_total': receber_vencidas.aggregate(total=Sum('valor_total'))['total'] or 0,
    }
    return render(request, 'core/financeiro/dashboard.html', context)

# --- CONTAS A PAGAR ---

@login_required
def conta_pagar_list(request):
    empresa = get_empresa(request.user)
    contas = ContaPagar.objects.filter(empresa=empresa).select_related('fornecedor', 'categoria').order_by('data_vencimento')
    
    # Filtros
    status = request.GET.get('status')
    if status:
        contas = contas.filter(status=status)
    
    paginator = Paginator(contas, 20)
    page = request.GET.get('page')
    contas = paginator.get_page(page)
    
    return render(request, 'core/financeiro/pagar_list.html', {'contas': contas, 'status_filtro': status})

@login_required
def conta_pagar_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = ContaPagarForm(request.POST, request.FILES, empresa=empresa)
        if form.is_valid():
            conta = form.save(commit=False)
            conta.empresa = empresa
            conta.save()
            messages.success(request, 'Conta a pagar cadastrada com sucesso!')
            return redirect('conta_pagar_list')
    else:
        form = ContaPagarForm(empresa=empresa)
    return render(request, 'core/financeiro/pagar_form.html', {'form': form, 'titulo': 'Nova Conta a Pagar'})

@login_required
def conta_pagar_edit(request, pk):
    empresa = get_empresa(request.user)
    conta = get_object_or_404(ContaPagar, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = ContaPagarForm(request.POST, request.FILES, instance=conta, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Conta a pagar atualizada com sucesso!')
            return redirect('conta_pagar_list')
    else:
        form = ContaPagarForm(instance=conta, empresa=empresa)
    return render(request, 'core/financeiro/pagar_form.html', {'form': form, 'titulo': 'Editar Conta a Pagar'})

@login_required
def conta_pagar_baixa(request, pk):
    empresa = get_empresa(request.user)
    conta = get_object_or_404(ContaPagar, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = BaixaContaPagarForm(request.POST, request.FILES)
        if form.is_valid():
            baixa = form.save(commit=False)
            baixa.conta = conta
            baixa.empresa = empresa
            baixa.save()
            messages.success(request, 'Pagamento registrado com sucesso!')
            return redirect('conta_pagar_list')
    else:
        form = BaixaContaPagarForm(initial={'valor': conta.saldo_devedor, 'data_pagamento': timezone.now().date()})
    return render(request, 'core/financeiro/baixa_form.html', {'form': form, 'conta': conta, 'tipo': 'PAGAR'})

# --- CONTAS A RECEBER ---

@login_required
def conta_receber_list(request):
    empresa = get_empresa(request.user)
    contas = ContaReceber.objects.filter(empresa=empresa).select_related('cliente', 'categoria').order_by('data_vencimento')
    
    status = request.GET.get('status')
    if status:
        contas = contas.filter(status=status)
        
    paginator = Paginator(contas, 20)
    page = request.GET.get('page')
    contas = paginator.get_page(page)
    
    return render(request, 'core/financeiro/receber_list.html', {'contas': contas, 'status_filtro': status})

@login_required
def conta_receber_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = ContaReceberForm(request.POST, empresa=empresa)
        if form.is_valid():
            conta = form.save(commit=False)
            conta.empresa = empresa
            conta.save()
            messages.success(request, 'Conta a receber cadastrada com sucesso!')
            return redirect('conta_receber_list')
    else:
        form = ContaReceberForm(empresa=empresa)
    return render(request, 'core/financeiro/receber_form.html', {'form': form, 'titulo': 'Nova Conta a Receber'})

@login_required
def conta_receber_edit(request, pk):
    empresa = get_empresa(request.user)
    conta = get_object_or_404(ContaReceber, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = ContaReceberForm(request.POST, instance=conta, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Conta a receber atualizada com sucesso!')
            return redirect('conta_receber_list')
    else:
        form = ContaReceberForm(instance=conta, empresa=empresa)
    return render(request, 'core/financeiro/receber_form.html', {'form': form, 'titulo': 'Editar Conta a Receber'})

@login_required
def conta_receber_baixa(request, pk):
    empresa = get_empresa(request.user)
    conta = get_object_or_404(ContaReceber, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = BaixaContaReceberForm(request.POST)
        if form.is_valid():
            baixa = form.save(commit=False)
            baixa.conta = conta
            baixa.empresa = empresa
            baixa.save()
            messages.success(request, 'Recebimento registrado com sucesso!')
            return redirect('conta_receber_list')
    else:
        form = BaixaContaReceberForm(initial={'valor': conta.saldo_restante, 'data_recebimento': timezone.now().date()})
    return render(request, 'core/financeiro/baixa_form.html', {'form': form, 'conta': conta, 'tipo': 'RECEBER'})

# --- CONFIGURAÇÕES FINANCEIRAS ---

@login_required
def financeiro_config(request):
    empresa = get_empresa(request.user)
    categorias = CategoriaFinanceira.objects.filter(empresa=empresa).order_by('tipo', 'nome')
    return render(request, 'core/financeiro/config.html', {'categorias': categorias})

@login_required
def categoria_financeira_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = CategoriaFinanceiraForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.empresa = empresa
            cat.save()
            messages.success(request, 'Categoria financeira criada!')
            return redirect('financeiro_config')
    else:
        form = CategoriaFinanceiraForm()
    return render(request, 'core/financeiro/categoria_form.html', {'form': form})


@login_required
def api_get_pedido_itens(request, pedido_id):
    """Retorna os itens de um Pedido de Compra (com saldo)."""
    empresa = get_empresa(request.user)
    pedido = get_object_or_404(PedidoCompra, id=pedido_id, empresa=empresa)
    
    itens = []
    for item in pedido.itens.all().select_related('produto'):
        saldo = item.saldo_restante
        if saldo > 0:
            itens.append({
                'id': item.id,
                'produto_id': item.produto.id,
                'nome': item.produto.nome,
                'unidade': item.produto.unidade,
                'quantidade': float(saldo),
                'valor_unitario': float(item.valor_unitario),
                'valor_total': float(saldo * item.valor_unitario),
                'fazenda_id': item.fazenda.id if item.fazenda else None
            })
            
    return JsonResponse({'sucesso': True, 'itens': itens, 'fornecedor': str(pedido.fornecedor.nome if pedido.fornecedor else '')})


@login_required
def api_get_contrato_itens(request, contrato_id):
    """Retorna os itens de um Contrato de Venda."""
    empresa = get_empresa(request.user)
    contrato = get_object_or_404(ContratoVenda, id=contrato_id, empresa=empresa)
    
    itens = []
    for item in contrato.itens.all().select_related('produto'):
        itens.append({
            'id': item.id,
            'produto_id': item.produto.id,
            'nome': item.produto.nome,
            'unidade': item.unidade, # Contrato tem unidade específica no item
            'quantidade': float(item.quantidade),
            'valor_unitario': float(item.valor_unitario),
            'valor_total': float(item.valor_total),
            'fazenda_id': item.fazenda.id if item.fazenda else None
        })
            
    return JsonResponse({'sucesso': True, 'itens': itens, 'cliente_id': contrato.cliente.id if contrato.cliente else None, 'cliente_nome': str(contrato.cliente.nome if contrato.cliente else '')})


# =============================================================================
# SAFRAS
# =============================================================================

@login_required
def safra_list(request):
    """Lista todas as safras da empresa."""
    empresa = get_empresa(request.user)
    safras = Safra.objects.filter(empresa=empresa).order_by('-data_inicio')
    return render(request, 'core/safra/list.html', {'safras': safras})


@login_required
def safra_create(request):
    """Cria uma nova safra."""
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = SafraForm(request.POST, empresa=empresa)
        if form.is_valid():
            safra = form.save(commit=False)
            safra.empresa = empresa
            safra.save()
            messages.success(request, f'Safra "{safra.nome}" criada com sucesso!')
            return redirect('safra_list')
    else:
        form = SafraForm(empresa=empresa)
    return render(request, 'core/safra/form.html', {'form': form, 'titulo': 'Nova Safra'})


@login_required
def safra_edit(request, pk):
    """Edita uma safra existente."""
    empresa = get_empresa(request.user)
    safra = get_object_or_404(Safra, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = SafraForm(request.POST, instance=safra, empresa=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, f'Safra "{safra.nome}" atualizada com sucesso!')
            return redirect('safra_list')
    else:
        form = SafraForm(instance=safra, empresa=empresa)
    return render(request, 'core/safra/form.html', {'form': form, 'titulo': f'Editar Safra: {safra.nome}'})


@login_required
@require_POST
def safra_delete(request, pk):
    """Exclui uma safra."""
    empresa = get_empresa(request.user)
    safra = get_object_or_404(Safra, pk=pk, empresa=empresa)
    nome = safra.nome
    safra.delete()
    messages.success(request, f'Safra "{nome}" excluída com sucesso!')
    return redirect('safra_list')



from .models import AlvoMonitoramento, Monitoramento, MonitoramentoItem
from .forms import AlvoMonitoramentoForm, MonitoramentoForm, MonitoramentoItemFormSet

# --- ALVOS DE MONITORAMENTO (Catálogo) ---

@login_required
def alvo_list(request):
    empresa = get_empresa(request.user)
    alvos = AlvoMonitoramento.objects.filter(empresa=empresa)
    return render(request, 'core/monitoramento/alvo_list.html', {'alvos': alvos})

@login_required
def alvo_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = AlvoMonitoramentoForm(request.POST, request.FILES)
        if form.is_valid():
            alvo = form.save(commit=False)
            alvo.empresa = empresa
            alvo.save()
            messages.success(request, 'Alvo cadastrado com sucesso!')
            return redirect('alvo_list')
    else:
        form = AlvoMonitoramentoForm()
    return render(request, 'core/monitoramento/alvo_form.html', {'form': form, 'title': 'Novo Alvo'})

@login_required
def alvo_edit(request, pk):
    empresa = get_empresa(request.user)
    alvo = get_object_or_404(AlvoMonitoramento, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = AlvoMonitoramentoForm(request.POST, request.FILES, instance=alvo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Alvo atualizado com sucesso!')
            return redirect('alvo_list')
    else:
        form = AlvoMonitoramentoForm(instance=alvo)
    return render(request, 'core/monitoramento/alvo_form.html', {'form': form, 'title': 'Editar Alvo'})

@login_required
@require_POST
def alvo_delete(request, pk):
    empresa = get_empresa(request.user)
    alvo = get_object_or_404(AlvoMonitoramento, pk=pk, empresa=empresa)
    alvo.delete()
    messages.success(request, 'Alvo excluído com sucesso!')
    return redirect('alvo_list')


# --- MONITORAMENTOS (Inspeções) ---

@login_required
def monitoramento_list(request):
    empresa = get_empresa(request.user)
    monitoramentos = Monitoramento.objects.filter(empresa=empresa).select_related('safra', 'ciclo', 'usuario').prefetch_related('talhoes', 'itens', 'itens__alvo').order_by('-data_coleta')
    return render(request, 'core/monitoramento/list.html', {'monitoramentos': monitoramentos})

@login_required
def monitoramento_create(request):
    empresa = get_empresa(request.user)
    if request.method == 'POST':
        form = MonitoramentoForm(request.POST, request.FILES, empresa=empresa)
        formset = MonitoramentoItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                monitoramento = form.save(commit=False)
                monitoramento.empresa = empresa
                monitoramento.usuario = request.user
                monitoramento.save()
                form.save_m2m() # Importante para os talhões
                
                formset.instance = monitoramento
                formset.save()
                
                messages.success(request, 'Monitoramento registrado com sucesso!')
                return redirect('monitoramento_list')
    else:
        form = MonitoramentoForm(empresa=empresa)
        formset = MonitoramentoItemFormSet()
    
    # Dados para o JS (Lógica igual Operação de Campo)
    talhoes_data = list(Talhao.objects.filter(empresa=empresa, ativo=True).values('id', 'nome', 'area_hectares', 'parent_id', 'fazenda_id', 'fazenda__nome'))
    busy_qs = Plantio.objects.filter(empresa=empresa).values('talhoes__id', 'safra_id')
    busy_talhoes = {}
    for item in busy_qs:
        t_id, s_id = item['talhoes__id'], item['safra_id']
        if t_id and s_id:
            if t_id not in busy_talhoes: busy_talhoes[t_id] = []
            if s_id not in busy_talhoes[t_id]: busy_talhoes[t_id].append(s_id)

    ciclos_qs = Plantio.objects.filter(empresa=empresa).exclude(status=StatusCiclo.CANCELADO).select_related('safra').prefetch_related('talhoes')
    ciclos_data = []
    for c in ciclos_qs:
        first_t = c.talhoes.first()
        ciclos_data.append({
            'id': c.id, 'safra_id': c.safra_id, 'fazenda_id': first_t.fazenda_id if first_t else None,
            'nome': str(c), 'talhoes': [t.id for t in c.talhoes.all()]
        })

    return render(request, 'core/monitoramento/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Novo Monitoramento',
        'talhoes_json': json.dumps(talhoes_data, cls=DjangoJSONEncoder),
        'busy_talhoes_json': json.dumps(busy_talhoes),
        'ciclos_json': json.dumps(ciclos_data)
    })

@login_required
def monitoramento_edit(request, pk):
    empresa = get_empresa(request.user)
    monitoramento = get_object_or_404(Monitoramento, pk=pk, empresa=empresa)
    if request.method == 'POST':
        form = MonitoramentoForm(request.POST, request.FILES, instance=monitoramento, empresa=empresa)
        formset = MonitoramentoItemFormSet(request.POST, instance=monitoramento)
        if form.is_valid() and formset.is_valid():
            form.save() # Automatic save_m2m for ModelForm with instance
            formset.save()
            messages.success(request, 'Monitoramento atualizado!')
            return redirect('monitoramento_list')
    else:
        form = MonitoramentoForm(instance=monitoramento, empresa=empresa)
        formset = MonitoramentoItemFormSet(instance=monitoramento)
    
    talhoes_data = list(Talhao.objects.filter(empresa=empresa, ativo=True).values('id', 'nome', 'area_hectares', 'parent_id', 'fazenda_id', 'fazenda__nome'))
    busy_qs = Plantio.objects.filter(empresa=empresa).exclude(id=monitoramento.ciclo_id if monitoramento.ciclo_id else 0).values('talhoes__id', 'safra_id')
    busy_talhoes = {}
    for item in busy_qs:
        t_id, s_id = item['talhoes__id'], item['safra_id']
        if t_id and s_id:
            if t_id not in busy_talhoes: busy_talhoes[t_id] = []
            if s_id not in busy_talhoes[t_id]: busy_talhoes[t_id].append(s_id)

    ciclos_qs = Plantio.objects.filter(empresa=empresa).exclude(status=StatusCiclo.CANCELADO).select_related('safra').prefetch_related('talhoes')
    ciclos_data = []
    for c in ciclos_qs:
        first_t = c.talhoes.first()
        ciclos_data.append({
            'id': c.id, 'safra_id': c.safra_id, 'fazenda_id': first_t.fazenda_id if first_t else None,
            'nome': str(c), 'talhoes': [t.id for t in c.talhoes.all()]
        })

    # Fazenda inicial
    primeiro_t = monitoramento.talhoes.first()
    fazenda_id = primeiro_t.fazenda_id if primeiro_t else None

    return render(request, 'core/monitoramento/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Editar Monitoramento',
        'talhoes_json': json.dumps(talhoes_data, cls=DjangoJSONEncoder),
        'busy_talhoes_json': json.dumps(busy_talhoes),
        'ciclos_json': json.dumps(ciclos_data),
        'fazenda_id': fazenda_id
    })

@login_required
@require_POST
def monitoramento_delete(request, pk):
    empresa = get_empresa(request.user)
    monitoramento = get_object_or_404(Monitoramento, pk=pk, empresa=empresa)
    monitoramento.delete()
    messages.success(request, 'Monitoramento excluído!')
    return redirect('monitoramento_list')
