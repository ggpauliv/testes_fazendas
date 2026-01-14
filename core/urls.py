"""
AgroTalhoes - URLs do App Core

Rotas para todas as funcionalidades do sistema.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # SaaS Admin (Master Only)
    path('saas/cadastrar-empresa/', views.saas_create_tenant, name='saas_create_tenant'),
    path('saas/settings/', views.saas_settings, name='saas_settings'),
    path('saas/company/<int:pk>/edit/', views.saas_edit_company, name='saas_edit_company'),
    path('saas/company/<int:pk>/delete/', views.saas_delete_company, name='saas_delete_company'),

    # Perfil / Profile
    path('accounts/profile/', views.profile_edit, name='profile_edit'),

    # Fazendas
    path('fazendas/', views.fazenda_list, name='fazenda_list'),
    path('fazendas/nova/', views.fazenda_create, name='fazenda_create'),
    path('fazendas/<int:pk>/', views.fazenda_detail, name='fazenda_detail'),
    path('fazendas/<int:pk>/editar/', views.fazenda_edit, name='fazenda_edit'),
    path('fazenda/<int:pk>/editar/', views.fazenda_edit, name='fazenda_edit'),
    path('fazenda/<int:pk>/excluir/', views.fazenda_delete_secure, name='fazenda_delete'),
    
    # Talhões
    path('talhoes/', views.talhao_list, name='talhao_list'),
    path('fazenda/<int:fazenda_id>/talhao/novo/', views.talhao_create, name='talhao_create'),
    path('talhoes/novo/', views.talhao_create, name='talhao_create'),
    path('talhoes/<int:pk>/', views.talhao_detail, name='talhao_detail'),
    path('talhoes/<int:pk>/novo-sub/', views.subtalhao_create, name='subtalhao_create'),
    path('talhoes/<int:pk>/editar/', views.talhao_edit, name='talhao_edit'),
    path('talhoes/<int:pk>/excluir/', views.talhao_delete, name='talhao_delete'),
    
    # Produtos
    path('produtos/', views.produto_list, name='produto_list'),
    path('produtos/novo/', views.produto_create, name='produto_create'),
    path('produtos/<int:pk>/editar/', views.produto_edit, name='produto_edit'),
    path('produtos/<int:pk>/excluir/', views.produto_delete, name='produto_delete'),
    path('api/produtos/quick-create/', views.api_produto_quick_create, name='api_produto_quick_create'),
    
    # Movimentações de Estoque
    path('movimentacoes/', views.movimentacao_list, name='movimentacao_list'),
    path('movimentacoes/nova/', views.movimentacao_create, name='movimentacao_create'),
    path('movimentacoes/entrada/', views.movimentacao_entrada, name='movimentacao_entrada'),
    path('movimentacoes/saida/', views.movimentacao_saida, name='movimentacao_saida'),
    path('movimentacoes/<int:pk>/editar/', views.movimentacao_edit, name='movimentacao_edit'),
    path('movimentacoes/<int:pk>/excluir/', views.movimentacao_delete, name='movimentacao_delete'),
    path('api/ler-nfe/', views.api_ler_dados_nfe, name='api_ler_dados_nfe'),
    path('api/salvar-lote-movimentacao/', views.api_salvar_lote_movimentacao, name='api_salvar_lote_movimentacao'),
    path('api/pedido/<int:pedido_id>/itens/', views.api_get_pedido_itens, name='api_get_pedido_itens'),
    path('api/contrato/<int:contrato_id>/itens/', views.api_get_contrato_itens, name='api_get_contrato_itens'),
    path('movimentacoes/importar-nfe/', views.importar_nfe, name='importar_nfe'),
    
    # Pedidos de Compra
    path('pedidos/', views.pedido_list, name='pedido_list'),
    path('pedidos/novo/', views.pedido_create, name='pedido_create'),
    path('pedidos/<int:pk>/', views.pedido_detail, name='pedido_detail'),
    path('pedidos/<int:pk>/pdf/', views.pedido_pdf, name='pedido_pdf'),
    path('pedidos/<int:pk>/editar/', views.pedido_edit, name='pedido_edit'),
    path('pedidos/<int:pk>/excluir/', views.pedido_delete, name='pedido_delete'),

    # Ciclos de Produção
    path('ciclos/', views.ciclo_list, name='ciclo_list'),
    path('ciclos/novo/', views.ciclo_create, name='ciclo_create'),
    path('ciclos/<int:pk>/', views.ciclo_detail, name='ciclo_detail'),
    path('ciclos/<int:pk>/editar/', views.ciclo_edit, name='ciclo_edit'),
    path('ciclos/<int:pk>/excluir/', views.ciclo_delete, name='ciclo_delete'),

    # Safras
    path('safras/', views.safra_list, name='safra_list'),
    path('safras/novo/', views.safra_create, name='safra_create'),
    path('safras/<int:pk>/editar/', views.safra_edit, name='safra_edit'),
    path('safras/<int:pk>/excluir/', views.safra_delete, name='safra_delete'),
    
    # Operações de Campo
    path('operacoes/', views.operacao_list, name='operacao_list'),
    path('operacoes/nova/', views.operacao_create, name='operacao_create'),
    path('operacoes/<int:pk>/', views.operacao_detail, name='operacao_detail'),
    path('operacoes/<int:pk>/editar/', views.operacao_edit, name='operacao_edit'),
    path('operacoes/<int:pk>/excluir/', views.operacao_delete, name='operacao_delete'),
    
    # Relatórios
    path('relatorios/custos/', views.relatorio_custos, name='relatorio_custos'),
    path('relatorios/custos/pdf/', views.relatorio_custos_pdf, name='relatorio_custos_pdf'),
    path('relatorios/producao/', views.relatorio_producao, name='relatorio_producao'),
    path('relatorios/financeiro/', views.relatorio_financeiro, name='relatorio_financeiro'),
    path('relatorios/romaneios/', views.relatorio_romaneios, name='relatorio_romaneios'),
    path('relatorios/estoque/', views.relatorio_estoque, name='relatorio_estoque'),
    
    # APIs (JSON)
    path('api/talhoes/mapa/', views.api_talhoes_mapa, name='api_talhoes_mapa'),
    path('api/talhoes/<int:pk>/coordenadas/', views.api_salvar_coordenadas, name='api_salvar_coordenadas'),
    path('api/ler-dados-nfe/', views.api_ler_dados_nfe, name='api_ler_dados_nfe'),
    path('api/pedido/<int:pedido_id>/itens/', views.api_get_pedido_itens, name='api_get_pedido_itens'),
    path('api/contrato/<int:contrato_id>/itens/', views.api_get_contrato_itens, name='api_get_contrato_itens'),
    path('api/market-data/', views.api_market_data, name='api_market_data'),
    path('api/ciclos/<int:plantio_id>/talhoes/', views.api_plantio_talhoes, name='api_plantio_talhoes'),
    path('api/talhoes/<int:pk>/clima/', views.api_talhao_climatico, name='api_talhao_climatico'),
    
    # Clima (Fazenda)
    path('fazendas/<int:pk>/clima/', views.fazenda_clima_history, name='fazenda_clima_history'),
    path('fazendas/<int:pk>/clima/sync/', views.fazenda_clima_sync, name='fazenda_clima_sync'),
    path('fazendas/<int:pk>/clima/manual/', views.fazenda_clima_add_manual, name='fazenda_clima_add_manual'),
    path('fazendas/<int:pk>/clima/pdf/', views.fazenda_clima_pdf, name='fazenda_clima_pdf'),
    
    # Romaneios
    path('romaneios/', views.romaneio_list, name='romaneio_list'),
    path('romaneios/novo/', views.romaneio_create, name='romaneio_create'),
    path('romaneios/<int:pk>/', views.romaneio_detail, name='romaneio_detail'),
    path('romaneios/<int:pk>/editar/', views.romaneio_edit, name='romaneio_edit'),
    path('romaneios/<int:pk>/excluir/', views.romaneio_delete, name='romaneio_delete'),

    # Contratos
    path('contratos/', views.contrato_list, name='contrato_list'),
    path('contratos/novo/', views.contrato_create, name='contrato_create'),
    path('contratos/<int:pk>/', views.contrato_detail, name='contrato_detail'),
    path('contratos/<int:pk>/editar/', views.contrato_edit, name='contrato_edit'),
    path('contratos/<int:pk>/pdf/', views.contrato_pdf, name='contrato_pdf'),
    path('contratos/<int:pk>/excluir/', views.contrato_delete, name='contrato_delete'),

    # Requisições
    path('requisicoes/', views.requisicao_list, name='requisicao_list'),
    path('requisicoes/<int:pk>/aprovar/', views.requisicao_aprovar, name='requisicao_aprovar'),

    # Rateio de Custos
    path('rateios/', views.rateio_list, name='rateio_list'),
    path('rateios/novo/', views.rateio_create, name='rateio_create'),
    path('rateios/<int:pk>/excluir/', views.rateio_delete, name='rateio_delete'),

    # Fixação de Preço
    path('fixacoes/', views.fixacao_list, name='fixacao_list'),
    path('fixacoes/novo/', views.fixacao_create, name='fixacao_create'),
    path('fixacoes/<int:pk>/excluir/', views.fixacao_delete, name='fixacao_delete'),

    # Clientes
    path('clientes/', views.cliente_list, name='cliente_list'),
    path('clientes/novo/', views.cliente_create, name='cliente_create'),
    path('clientes/<int:pk>/editar/', views.cliente_edit, name='cliente_edit'),
    path('clientes/<int:pk>/excluir/', views.cliente_delete, name='cliente_delete'),

    # Fornecedores
    path('fornecedores/', views.fornecedor_list, name='fornecedor_list'),
    path('fornecedores/novo/', views.fornecedor_create, name='fornecedor_create'),
    path('fornecedores/<int:pk>/editar/', views.fornecedor_edit, name='fornecedor_edit'),
    path('fornecedores/<int:pk>/excluir/', views.fornecedor_delete, name='fornecedor_delete'),

    # Taxas de Armazém
    path('armazens/', views.armazem_list, name='armazem_list'),
    path('armazens/novo/', views.armazem_create, name='armazem_create'),
    path('armazens/<int:pk>/editar/', views.armazem_edit, name='armazem_edit'),
    path('armazens/<int:pk>/excluir/', views.armazem_delete, name='armazem_delete'),

    # Gestão de Equipe
    path('equipe/', views.team_list, name='team_list'),
    path('equipe/<int:empresa_id>/', views.team_list, name='team_list_company'),
    path('equipe/convidar/', views.invite_user, name='invite_user'),
    path('equipe/cancelar-convite/<int:invite_id>/', views.cancel_invite, name='cancel_invite'),
    path('convite/<uuid:token>/', views.accept_invite, name='accept_invite'),

    # Financeiro
    path('financeiro/', views.financeiro_dashboard, name='financeiro_dashboard'),
    path('financeiro/config/', views.financeiro_config, name='financeiro_config'),
    path('financeiro/categoria/nova/', views.categoria_financeira_create, name='categoria_financeira_create'),
    
    # Contas a Pagar
    path('financeiro/pagar/', views.conta_pagar_list, name='conta_pagar_list'),
    path('financeiro/pagar/novo/', views.conta_pagar_create, name='conta_pagar_create'),
    path('financeiro/pagar/<int:pk>/editar/', views.conta_pagar_edit, name='conta_pagar_edit'),
    path('financeiro/pagar/<int:pk>/baixa/', views.conta_pagar_baixa, name='conta_pagar_baixa'),
    
    # Contas a Receber
    path('financeiro/receber/', views.conta_receber_list, name='conta_receber_list'),
    path('financeiro/receber/novo/', views.conta_receber_create, name='conta_receber_create'),
    path('financeiro/receber/<int:pk>/editar/', views.conta_receber_edit, name='conta_receber_edit'),
    path('financeiro/receber/<int:pk>/baixa/', views.conta_receber_baixa, name='conta_receber_baixa'),

    # Monitoramento de Pragas
    path('monitoramento/alvos/', views.alvo_list, name='alvo_list'),
    path('monitoramento/alvos/novo/', views.alvo_create, name='alvo_create'),
    path('monitoramento/alvos/<int:pk>/editar/', views.alvo_edit, name='alvo_edit'),
    path('monitoramento/alvos/<int:pk>/excluir/', views.alvo_delete, name='alvo_delete'),
    
    path('monitoramento/', views.monitoramento_list, name='monitoramento_list'),
    path('monitoramento/novo/', views.monitoramento_create, name='monitoramento_create'),
    path('monitoramento/<int:pk>/editar/', views.monitoramento_edit, name='monitoramento_edit'),
    path('monitoramento/<int:pk>/excluir/', views.monitoramento_delete, name='monitoramento_delete'),
]
