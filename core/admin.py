"""
AgroTalhoes - Configuração do Admin

Registro dos modelos no Django Admin.
"""

from django.contrib import admin
from .models import (
    Talhao, Produto, MovimentacaoEstoque, 
    Plantio, OperacaoCampo, OperacaoCampoItem, AtividadeCampo, Empresa, UserProfile, ConfiguracaoSistema, Fazenda,
    Safra, TabelaClassificacao, Romaneio, ContratoVenda, RateioCusto,
    TaxaArmazem
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cnpj', 'ativo', 'created_at']
    search_fields = ['nome', 'cnpj']


@admin.register(Fazenda)
class FazendaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'empresa', 'cidade', 'estado', 'area_total_hectares', 'ativo', 'created_at']
    list_filter = ['empresa', 'ativo', 'estado']
    search_fields = ['nome', 'cidade', 'empresa__nome']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'empresa']
    list_filter = ['empresa']
    search_fields = ['user__username', 'empresa__nome']


@admin.register(Talhao)
class TalhaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'empresa', 'fazenda', 'area_hectares', 'cultura_atual', 'ativo', 'data_cadastro']
    list_filter = ['empresa', 'fazenda', 'ativo', 'cultura_atual']
    search_fields = ['nome', 'descricao', 'empresa__nome', 'fazenda__nome']
    readonly_fields = ['data_cadastro', 'data_atualizacao']


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'empresa', 'categoria', 'unidade', 'estoque_atual', 'estoque_minimo', 'ativo']
    list_filter = ['empresa', 'categoria', 'ativo']
    search_fields = ['nome', 'codigo', 'empresa__nome']
    readonly_fields = ['data_cadastro']


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ['produto', 'empresa', 'tipo', 'quantidade', 'valor_unitario', 'data_movimentacao', 'fornecedor']
    list_filter = ['empresa', 'tipo', 'data_movimentacao']
    search_fields = ['produto__nome', 'chave_nfe', 'numero_nfe', 'fornecedor', 'empresa__nome']
    readonly_fields = ['data_cadastro']
    date_hierarchy = 'data_movimentacao'


@admin.register(Safra)
class SafraAdmin(admin.ModelAdmin):
    list_display = ['nome', 'data_inicio', 'data_fim', 'ativa']

@admin.register(Plantio)
class PlantioAdmin(admin.ModelAdmin):
    list_display = ['safra', 'empresa', 'get_talhoes', 'cultura', 'status', 'data_plantio', 'data_fim']
    list_filter = ['empresa', 'status', 'cultura', 'safra']
    search_fields = ['safra__nome', 'talhoes__nome', 'cultura', 'empresa__nome']
    readonly_fields = ['data_cadastro']

    def get_talhoes(self, obj):
        return ", ".join([t.nome for t in obj.talhoes.all()])
    get_talhoes.short_description = 'Talhões'


class OperacaoCampoItemInline(admin.TabularInline):
    model = OperacaoCampoItem
    extra = 1

@admin.register(OperacaoCampo)
class OperacaoCampoAdmin(admin.ModelAdmin):
    list_display = ['id', 'safra', 'ciclo', 'data_operacao', 'status', 'responsavel']
    list_filter = ['safra', 'status', 'data_operacao']
    search_fields = ['responsavel', 'observacao']
    readonly_fields = ['data_cadastro']
    inlines = [OperacaoCampoItemInline]
    date_hierarchy = 'data_operacao'


@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    list_display = ['nome_sistema', 'cor_primaria', 'updated_at']
    fieldsets = (
        ('Identidade Visual', {
            'fields': ('nome_sistema', 'logo', 'cor_primaria')
        }),
        ('Conteúdo', {
            'fields': ('mensagem_dashboard',)
        }),
    )


@admin.register(Romaneio)
class RomaneioAdmin(admin.ModelAdmin):
    list_display = ['numero_ticket', 'fazenda', 'talhao', 'motorista', 'peso_liquido', 'data']
    list_filter = ['fazenda', 'data']

@admin.register(ContratoVenda)
class ContratoVendaAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'data_entrega', 'tipo']
    list_filter = ['tipo', 'data_entrega']

@admin.register(RateioCusto)
class RateioCustoAdmin(admin.ModelAdmin):
    list_display = ['data', 'descricao', 'valor_total', 'safra', 'criterio']
    list_filter = ['safra', 'data']

@admin.register(TaxaArmazem)
class TaxaArmazemAdmin(admin.ModelAdmin):
    list_display = ['fornecedor', 'taxa_recepcao', 'taxa_armazenagem', 'quebra_tecnica']
    search_fields = ['fornecedor']

@admin.register(TabelaClassificacao)
class TabelaClassificacaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cultura', 'padrao_umidade', 'padrao_impureza', 'padrao_avariado']
    list_filter = ['cultura']
