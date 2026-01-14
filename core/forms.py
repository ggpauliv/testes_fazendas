"""
AgroTalhoes - Formulários

Formulários Django para o sistema de gestão de fazendas.
Utiliza django-crispy-forms com Bootstrap 5.
"""

from django import forms
from decimal import Decimal
from django.core.validators import FileExtensionValidator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML, Field
from crispy_forms.bootstrap import FormActions
from django.forms import inlineformset_factory
from django.contrib.auth.models import User

from .models import (
    Fazenda, Talhao, Safra, Plantio, StatusCiclo,
    AtividadeCampo, Produto, CategoriaOperacao,
    OperacaoCampo, OperacaoCampoItem, MovimentacaoEstoque,
    TipoMovimentacao, RateioCusto, ContratoVenda,
    UnidadeCusto, ConfiguracaoSistema,
    PedidoCompra, ItemPedidoCompra, StatusPedido, Romaneio,
    Fixacao, TaxaArmazem,
    Cliente, Fornecedor, ItemContratoVenda, UserInvitation, UserRole,
    AlvoMonitoramento, Monitoramento, MonitoramentoItem
)



class TalhaoChoiceField(forms.ModelChoiceField):
    """Campo customizado para exibir hierarquia de talhões (Pai > Filho)."""
    def label_from_instance(self, obj):
        if obj.parent:
            return f"{obj.parent.nome} > {obj.nome} ({obj.area_hectares} ha)"
        return f"{obj.nome} ({obj.area_hectares} ha)"


class FazendaForm(forms.ModelForm):
    """Formulário para cadastro/edição de Fazenda."""

    class Meta:
        model = Fazenda
        fields = ['nome', 'endereco', 'cidade', 'estado', 'area_total_hectares', 'latitude', 'longitude', 'ativo']
        widgets = {
            'latitude': forms.TextInput(attrs={'placeholder': 'Ex: -12.123456'}),
            'longitude': forms.TextInput(attrs={'placeholder': 'Ex: -45.654321'}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nome', css_class='col-md-6'),
                Column('area_total_hectares', css_class='col-md-6'),
            ),
            Row(
                Column('endereco', css_class='col-md-6'),
                Column('cidade', css_class='col-md-4'),
                Column('estado', css_class='col-md-2'),
            ),
            Row(
                Column('latitude', css_class='col-md-3'),
                Column('longitude', css_class='col-md-3'),
                Column('ativo', css_class='col-md-3 pt-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Fazenda', css_class='btn btn-success'),
                HTML('<a href="{% url \'fazenda_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class TalhaoForm(forms.ModelForm):
    """Formulário para cadastro/edição de Talhão."""
    
    class Meta:
        model = Talhao
        fields = ['fazenda', 'parent', 'nome', 'descricao', 'coordenadas_json', 'area_hectares', 'cultura_atual', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'coordenadas_json': forms.HiddenInput(),
            'parent': forms.HiddenInput(),
            'fazenda': forms.Select(attrs={'class': 'form-select form-select-lg'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        area_hectares = cleaned_data.get('area_hectares')
        parent = cleaned_data.get('parent')

        if parent and area_hectares:
            # Validar se a soma das áreas dos subtalhões excede a área do pai
            siblings = Talhao.objects.filter(parent=parent, ativo=True)
            if self.instance.pk:
                siblings = siblings.exclude(pk=self.instance.pk)
            
            total_siblings_area = sum(t.area_hectares for t in siblings)
            total_area = total_siblings_area + area_hectares

            if total_area > parent.area_hectares:
                raise forms.ValidationError(
                    f"A soma das áreas dos subtalhões ({total_area} ha) excede a área do talhão pai ({parent.area_hectares} ha)."
                )
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['fazenda'].queryset = Fazenda.objects.filter(ativo=True, empresa=self.empresa)
            # Também filtrar o parent para não permitir parent de outra empresa
            self.fields['parent'].queryset = Talhao.objects.filter(ativo=True, empresa=self.empresa)
        else:
            self.fields['fazenda'].queryset = Fazenda.objects.none()
            self.fields['parent'].queryset = Talhao.objects.none()

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('fazenda', css_class='col-md-4'),
                Column('nome', css_class='col-md-4'),
                Column('area_hectares', css_class='col-md-2'),
                Column('cultura_atual', css_class='col-md-2'),
            ),
            'descricao',
            'coordenadas_json',
            Row(
                Column('ativo', css_class='col-md-12'),
            ),
            HTML('<div id="map-container" class="mb-3"><div id="map" style="height: 400px; border-radius: 8px;"></div></div>'),
            FormActions(
                Submit('submit', 'Salvar Talhão', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'talhao_list\' %}" class="btn btn-secondary btn-lg ms-2">Cancelar</a>'),
            )
        )


class ProdutoForm(forms.ModelForm):
    """Formulário para cadastro/edição de Produto."""
    
    class Meta:
        model = Produto
        fields = ['nome', 'codigo', 'categoria', 'unidade', 'estoque_minimo', 'ativo']

    def __init__(self, *args, **kwargs):
        kwargs.pop('empresa', None)  # Remove empresa if passed (not used in this form)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nome', css_class='col-md-6'),
                Column('codigo', css_class='col-md-3'),
                Column('categoria', css_class='col-md-3'),
            ),
            Row(
                Column('unidade', css_class='col-md-4'),
                Column('estoque_minimo', css_class='col-md-4'),
                Column('ativo', css_class='col-md-4 pt-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Produto', css_class='btn btn-success'),
                HTML('<a href="{% url \'produto_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class MovimentacaoEntradaForm(forms.ModelForm):
    """Formulário especializado para entradas de estoque."""
    
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'quantidade', 'valor_unitario', 'data_movimentacao', 
                  'fazenda', 'fornecedor', 'numero_nfe', 'arquivo_nfe', 'observacao', 'item_pedido']
        widgets = {
            'data_movimentacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    pedido_compra = forms.ModelChoiceField(
        queryset=PedidoCompra.objects.none(),
        required=False,
        label='Pedido de Compra'
    )

    gerar_financeiro = forms.ChoiceField(
        choices=[(True, 'Sim'), (False, 'Não')],
        initial=True,
        label='Gerar Financeiro?',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    batch_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['produto'].queryset = Produto.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['fornecedor'].queryset = Fornecedor.objects.filter(empresa=self.empresa)
            self.fields['fazenda'].queryset = Fazenda.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['pedido_compra'].queryset = PedidoCompra.objects.filter(
                empresa=self.empresa,
                status__in=[StatusPedido.ABERTO, StatusPedido.PARCIAL]
            )
            self.fields['item_pedido'].queryset = ItemPedidoCompra.objects.filter(
                status__in=[StatusPedido.ABERTO, StatusPedido.PARCIAL], 
                pedido__empresa=self.empresa
            ).select_related('pedido', 'produto')
        else:
            self.fields['produto'].queryset = Produto.objects.none()
            self.fields['fornecedor'].queryset = Fornecedor.objects.none()
            self.fields['fazenda'].queryset = Fazenda.objects.none()
            self.fields['pedido_compra'].queryset = PedidoCompra.objects.none()
            self.fields['item_pedido'].queryset = ItemPedidoCompra.objects.none()

        self.fields['produto'].required = False
        self.fields['quantidade'].required = False
        self.fields['valor_unitario'].required = False

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Div(
                HTML('<h5 class="card-title text-primary border-bottom pb-2 mb-3">1. Dados da Nota / Entrada</h5>'),
                Row(
                    Column('data_movimentacao', css_class='col-md-3'),
                    Column('fazenda', css_class='col-md-3'),
                    Column('fornecedor', css_class='col-md-3'),
                    Column('gerar_financeiro', css_class='col-md-3'),
                ),
                Row(
                    Column(Field('numero_nfe', wrapper_class='mb-0'), css_class='col-md-3'),
                    Column(Field('arquivo_nfe', wrapper_class='mb-0'), css_class='col-md-7'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" id="btn-carregar-xml" class="btn btn-outline-primary w-100" onclick="carregarDadosXml()"><i class="bi bi-cloud-arrow-up me-1"></i> XML</button>'),
                        css_class='col-md-2'
                    ),
                    css_class='mb-3'
                ),
                Row(
                    Column(Field('pedido_compra', wrapper_class='mb-0'), css_class='col-md-10'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-outline-primary w-100" onclick="carregarItensPedido()"><i class="bi bi-download"></i> Itens</button>'),
                        css_class='col-md-2'
                    ),
                    css_class='mb-3'
                ),
                css_class='mb-4'
            ),
            Div(
                HTML('<h5 class="card-title text-primary border-bottom pb-2 mb-3">2. Itens da Entrada</h5>'),
                Row(
                    Column(Field('produto', wrapper_class='mb-0'), css_class='col-md-4'),
                    Column(Field('quantidade', wrapper_class='mb-0'), css_class='col-md-2'),
                    Column(Field('valor_unitario', wrapper_class='mb-0'), css_class='col-md-3'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-primary w-100" onclick="adicionarItemManual()"><i class="bi bi-plus-lg"></i> Adicionar Item</button>'),
                        css_class='col-md-3'
                    ),
                    css_class='mb-3'
                ),
                Row(
                    Column('observacao', css_class='col-12'),
                ),
                css_class='mb-4'
            ),
            Field('batch_data'),
            Field('item_pedido', type="hidden"),
            Div(
                HTML('<div class="alert alert-warning d-none" id="batch-alert">Há itens na lista que serão salvos.</div>'),
                HTML('<button type="submit" class="btn btn-success btn-lg px-5" id="btn-submit-main"><i class="bi bi-check-circle me-2"></i>Salvar Entrada</button>'),
                css_class='text-end mt-4'
            )
        )


class MovimentacaoSaidaForm(forms.ModelForm):
    """Formulário especializado para saídas de estoque."""
    
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'quantidade', 'valor_unitario', 'data_movimentacao', 
                  'fazenda', 'cliente', 'numero_nfe', 'observacao', 'item_contrato']
        widgets = {
            'data_movimentacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    contrato_venda = forms.ModelChoiceField(
        queryset=ContratoVenda.objects.none(),
        required=False,
        label='Contrato de Venda'
    )

    gerar_financeiro = forms.ChoiceField(
        choices=[(True, 'Sim'), (False, 'Não')],
        initial=True,
        label='Gerar Financeiro?',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    batch_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['produto'].queryset = Produto.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['cliente'].queryset = Cliente.objects.filter(empresa=self.empresa)
            self.fields['fazenda'].queryset = Fazenda.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['contrato_venda'].queryset = ContratoVenda.objects.filter(
                empresa=self.empresa
            )
            self.fields['item_contrato'].queryset = ItemContratoVenda.objects.filter(
                contrato__empresa=self.empresa
            ).select_related('contrato', 'produto')
        else:
            self.fields['produto'].queryset = Produto.objects.none()
            self.fields['cliente'].queryset = Fornecedor.objects.none()
            self.fields['fazenda'].queryset = Fazenda.objects.none()
            self.fields['contrato_venda'].queryset = ContratoVenda.objects.none()
            self.fields['item_contrato'].queryset = ItemContratoVenda.objects.none()

        self.fields['produto'].required = False
        self.fields['quantidade'].required = False
        self.fields['valor_unitario'].required = False

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Div(
                HTML('<h5 class="card-title text-primary border-bottom pb-2 mb-3">1. Dados da Nota / Saída</h5>'),
                Row(
                    Column('data_movimentacao', css_class='col-md-3'),
                    Column('fazenda', css_class='col-md-3'),
                    Column('cliente', css_class='col-md-3'),
                    Column('gerar_financeiro', css_class='col-md-3'),
                ),
                Row(
                    Column(Field('numero_nfe', wrapper_class='mb-0'), css_class='col-md-3'),
                    Column(Field('contrato_venda', wrapper_class='mb-0'), css_class='col-md-7'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-outline-success w-100" onclick="carregarItensContrato()"><i class="bi bi-download"></i> Contrato</button>'),
                        css_class='col-md-2'
                    ),
                    css_class='mb-3'
                ),
                css_class='mb-4'
            ),
            Div(
                HTML('<h5 class="card-title text-primary border-bottom pb-2 mb-3">2. Itens da Saída</h5>'),
                Row(
                    Column(Field('produto', wrapper_class='mb-0'), css_class='col-md-4'),
                    Column(Field('quantidade', wrapper_class='mb-0'), css_class='col-md-2'),
                    Column(Field('valor_unitario', wrapper_class='mb-0'), css_class='col-md-3'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-primary w-100" onclick="adicionarItemManual()"><i class="bi bi-plus-lg"></i> Adicionar Item</button>'),
                        css_class='col-md-3'
                    ),
                    css_class='mb-3'
                ),
                Row(
                    Column('observacao', css_class='col-12'),
                ),
                css_class='mb-4'
            ),
            Field('batch_data'),
            Field('item_contrato', type="hidden"),
            Div(
                HTML('<div class="alert alert-warning d-none" id="batch-alert">Há itens na lista que serão salvos.</div>'),
                HTML('<button type="submit" class="btn btn-success btn-lg px-5" id="btn-submit-main"><i class="bi bi-check-circle me-2"></i>Salvar Saída</button>'),
                css_class='text-end mt-4'
            )
        )


class MovimentacaoEstoqueForm(forms.ModelForm):
    """Formulário para registro de movimentação de estoque manual."""
    
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'tipo', 'quantidade', 'valor_unitario', 'data_movimentacao', 
                  'fazenda', 'item_pedido', 'item_contrato', 'fornecedor', 'cliente', 'numero_nfe', 'arquivo_nfe', 'observacao']
        widgets = {
            'data_movimentacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    pedido_compra = forms.ModelChoiceField(
        queryset=PedidoCompra.objects.none(),
        required=False,
        label='Pedido de Compra'
    )
    contrato_venda = forms.ModelChoiceField(
        queryset=ContratoVenda.objects.none(),
        required=False,
        label='Contrato de Venda'
    )

    # Opção para gerar financeiro
    gerar_financeiro = forms.ChoiceField(
        choices=[(True, 'Sim'), (False, 'Não')],
        initial=True,
        label='Gerar Financeiro?',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Campo oculto para armazenar JSON do lote
    batch_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['produto'].queryset = Produto.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['fornecedor'].queryset = Fornecedor.objects.filter(empresa=self.empresa)
            self.fields['cliente'].queryset = Cliente.objects.filter(empresa=self.empresa)
            self.fields['fazenda'].queryset = Fazenda.objects.filter(ativo=True, empresa=self.empresa)
            # Filtra itens de pedido ABERTO ou PARCIAL
            self.fields['item_pedido'].queryset = ItemPedidoCompra.objects.filter(
                status__in=[StatusPedido.ABERTO, StatusPedido.PARCIAL], 
                pedido__empresa=self.empresa
            ).select_related('pedido', 'produto')
            self.fields['pedido_compra'].queryset = PedidoCompra.objects.filter(
                empresa=self.empresa,
                status__in=[StatusPedido.ABERTO, StatusPedido.PARCIAL]
            )
            self.fields['contrato_venda'].queryset = ContratoVenda.objects.filter(
                empresa=self.empresa
            )
        else:
            self.fields['produto'].queryset = Produto.objects.none()
            self.fields['fornecedor'].queryset = Fornecedor.objects.none()
            self.fields['cliente'].queryset = Cliente.objects.none()
            self.fields['fazenda'].queryset = Fazenda.objects.none()
            self.fields['item_pedido'].queryset = ItemPedidoCompra.objects.none()
            self.fields['pedido_compra'].queryset = PedidoCompra.objects.none()
            self.fields['contrato_venda'].queryset = ContratoVenda.objects.none()

        # Tornar campos de item opcionais (pois usamos a lista em lote agora)
        self.fields['produto'].required = False
        self.fields['quantidade'].required = False
        self.fields['valor_unitario'].required = False
        self.fields['item_pedido'].required = False

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            # 1. Cabeçalho (Dados Gerais)
            Div(
                HTML('<h5 class="card-title text-primary border-bottom pb-2 mb-3">1. Dados da Nota / Movimentação</h5>'),
                Row(
                    Column('data_movimentacao', css_class='col-md-3'),
                    Column('tipo', css_class='col-md-2'),
                    Column('fazenda', css_class='col-md-3'),
                    Column('fornecedor', css_class='col-md-2'),
                    Column('cliente', css_class='col-md-2'),
                ),
                Row(
                    Column('gerar_financeiro', css_class='col-md-3'),
                ),
                Row(
                    Column(Field('numero_nfe', wrapper_class='mb-0'), css_class='col-md-3'),
                    Column(Field('arquivo_nfe', wrapper_class='mb-0'), css_class='col-md-7'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" id="btn-carregar-xml" class="btn btn-outline-primary w-100" onclick="carregarDadosXml()"><i class="bi bi-cloud-arrow-up me-1"></i> XML</button>'),
                        css_class='col-md-2'
                    ),
                    css_class='mb-3'
                ),
                Row(
                    Column(Field('pedido_compra', wrapper_class='mb-0'), css_class='col-md-4'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-outline-primary w-100" onclick="carregarItensPedido()"><i class="bi bi-download"></i> Itens</button>'),
                        css_class='col-md-2'
                    ),
                    Column(Field('contrato_venda', wrapper_class='mb-0'), css_class='col-md-4'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-outline-success w-100" onclick="carregarItensContrato()"><i class="bi bi-download"></i> Contrato</button>'),
                        css_class='col-md-2'
                    ),
                    css_class='mb-3'
                ),
                css_class='mb-4'
            ),

            # 2. Entrada de Itens
            Div(
                HTML('<h5 class="card-title text-primary border-bottom pb-2 mb-3">2. Itens da Movimentação</h5>'),
                Row(
                    Column(Field('produto', wrapper_class='mb-0'), css_class='col-md-4'),
                    Column(Field('quantidade', wrapper_class='mb-0'), css_class='col-md-2'),
                    Column(Field('valor_unitario', wrapper_class='mb-0'), css_class='col-md-3'),
                    Column(
                        HTML('<label class="form-label d-block">&nbsp;</label>'),
                        HTML('<button type="button" class="btn btn-primary w-100" onclick="adicionarItemManual()"><i class="bi bi-plus-lg"></i> Adicionar Item</button>'),
                        css_class='col-md-3'
                    ),
                    css_class='mb-3'
                ),
                Row(
                    Column('observacao', css_class='col-12'),
                ),
                css_class='mb-3'
            ),

            # 3. Área da Tabela Visual (Inserida via HTML)
            HTML('<div id="batch-creation-area"></div>'),
            Field('batch_data'),

            FormActions(
                Submit('submit', 'Finalizar e Salvar Movimentação', css_class='btn btn-success btn-lg w-100'),
                HTML('<a href="{% url \'movimentacao_list\' %}" class="btn btn-secondary mt-2 w-100">Cancelar</a>'),
                css_class='d-grid gap-2 mt-4'
            )
        )


class PedidoFilterForm(forms.Form):
    """Formulário para filtrar pedidos."""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar fornecedor...'})
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + list(StatusPedido.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'this.form.submit()'})
    )


class ContratoFilterForm(forms.Form):
    """Formulário para filtrar contratos de venda."""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar cliente...'})
    )
    fazenda = forms.ModelChoiceField(
        queryset=Fazenda.objects.none(),
        required=False,
        empty_label="Todas as Fazendas",
        widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'this.form.submit()'})
    )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if empresa:
            self.fields['fazenda'].queryset = Fazenda.objects.filter(empresa=empresa, ativo=True).order_by('nome')




class PedidoCompraForm(forms.ModelForm):
    """Formulário para cadastro/edição de Cabeçalho de Pedido."""
    class Meta:
        model = PedidoCompra
        fields = ['fornecedor', 'data_pedido', 'data_prevista', 'arquivo', 'status', 'observacoes']
        widgets = {
            'data_pedido': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_prevista': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
        }
    
    itens_json = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    # Aux fields for adding items via JS
    aux_produto = forms.ModelChoiceField(queryset=Produto.objects.none(), label='', required=False)
    aux_fazenda = forms.ModelChoiceField(queryset=Fazenda.objects.none(), label='Fazenda Destino', required=False)
    aux_quantidade = forms.DecimalField(label='Quantidade', required=False, min_value=0)
    aux_valor_unitario = forms.DecimalField(label='Valor Unit. (R$)', required=False, min_value=0)

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['fornecedor'].queryset = Fornecedor.objects.filter(empresa=self.empresa)
            self.fields['aux_produto'].queryset = Produto.objects.filter(empresa=self.empresa, ativo=True)
            self.fields['aux_fazenda'].queryset = Fazenda.objects.filter(empresa=self.empresa, ativo=True)
        else:
            self.fields['fornecedor'].queryset = Fornecedor.objects.none()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                HTML('<h5 class="card-title mb-3">Dados Cadastrais</h5>'),
                Row(
                    Column('fornecedor', css_class='col-md-6'),
                    Column('data_pedido', css_class='col-md-3'),
                    Column('data_prevista', css_class='col-md-3'),
                ),
                Row(
                    Column('arquivo', css_class='col-md-6'),
                    Column('status', css_class='col-md-6'),
                ),
                Row(
                    Column('observacoes', css_class='col-12'),
                ),
                css_class='card-body'
            ),
            HTML('<hr class="my-4">'),
            Div(
                HTML('<h5 class="card-title mb-3">Itens do Pedido</h5>'),
                Div(
                    Row(
                        Column(
                            HTML('<div class="d-flex justify-content-between"><label class="form-label">Produto</label><a href="#" data-bs-toggle="modal" data-bs-target="#newProductModal" class="small text-success font-weight-bold">+ Novo</a></div>'),
                            Field('aux_produto', wrapper_class='mb-0'),
                            css_class='col-md-4'
                        ),
                        Column('aux_fazenda', css_class='col-md-3'),
                        Column('aux_quantidade', css_class='col-md-2'),
                        Column('aux_valor_unitario', css_class='col-md-2'),
                        Column(
                            HTML('<label>&nbsp;</label><button type="button" id="btn-add-item" class="btn btn-success w-100"><i class="bi bi-plus-lg"></i></button>'),
                            css_class='col-md-1'
                        ),
                    ),
                    css_class='p-3 bg-light border rounded mb-3'
                ),
                HTML('''
                <div class="table-responsive">
                    <table class="table table-bordered table-hover" id="table-itens">
                        <thead class="table-light">
                            <tr>
                                <th>Produto</th>
                                <th>Fazenda</th>
                                <th class="text-end">Qtd</th>
                                <th class="text-end">Valor Unit.</th>
                                <th class="text-end">Total</th>
                                <th class="text-center" style="width: 50px;">Ações</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                        <tfoot>
                             <tr class="table-active fw-bold">
                                <td colspan="4" class="text-end">Total do Pedido:</td>
                                <td class="text-end" id="display-total-pedido">0,00</td>
                                <td></td>
                             </tr>
                        </tfoot>
                    </table>
                </div>
                '''),
                Field('itens_json'),
                css_class='card-body'
            )
        )


class ImportarNFeForm(forms.Form):
    """Formulário para upload de arquivo XML de NFe."""
    
    arquivo_xml = forms.FileField(
        label='Arquivo XML da NFe',
        validators=[FileExtensionValidator(allowed_extensions=['xml'])],
        widget=forms.FileInput(attrs={
            'accept': '.xml',
            'class': 'form-control',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Div(
                HTML('''
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i>
                    <strong>Instruções:</strong> Selecione o arquivo XML da Nota Fiscal Eletrônica (NFe) 
                    para importar automaticamente os produtos para o estoque.
                </div>
                '''),
                'arquivo_xml',
                css_class='mb-3'
            ),
            FormActions(
                Submit('submit', 'Importar NFe', css_class='btn btn-primary btn-lg'),
            )
        )


class PlantioForm(forms.ModelForm):
    """Formulário para cadastro/edição de Plantio (Ciclo)."""
    
    talhoes = forms.ModelMultipleChoiceField(
        queryset=Talhao.objects.none(),
        label='Talhões Selecionados',
        widget=forms.SelectMultiple(attrs={'class': 'form-select d-none'}) # Hidden, managed by JS
    )
    safra = forms.ModelChoiceField(
        queryset=Safra.objects.all(),
        label='Safra',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Campos auxiliares para seleção interativa
    fazenda_selector = forms.ModelChoiceField(
        queryset=Fazenda.objects.none(),
        label='Selecione a Fazenda',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_fazenda_selector'})
    )
    talhao_selector = forms.ChoiceField(
        choices=[('', 'Selecione a Fazenda primeiro')],
        label='Selecione o Talhão',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_talhao_selector'})
    )

    class Meta:
        model = Plantio
        fields = ['safra', 'talhoes', 'cultura', 'data_plantio', 'data_fim',  
                  'status', 'producao_estimada_sc_ha', 'producao_real_saca', 
                  'preco_venda_estimado_sc', 'observacoes']
        labels = {
            'producao_estimada_sc_ha': 'Prod. Estimada (sc/ha)',
            'preco_venda_estimado_sc': 'Preço Venda Estimado (R$/sc)',
        }
        widgets = {
            'data_plantio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtra safras ativas ou todas? Vamos mostrar todas por enquanto.
        self.fields['safra'].queryset = Safra.objects.filter(ativa=True) # Exemplo

        if self.empresa:
            self.fields['talhoes'].queryset = Talhao.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['fazenda_selector'].queryset = Fazenda.objects.filter(ativo=True, empresa=self.empresa)
        else:
            self.fields['talhoes'].queryset = Talhao.objects.none()
            self.fields['fazenda_selector'].queryset = Fazenda.objects.none()

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('safra', css_class='col-md-4'),
                Column('cultura', css_class='col-md-4'),
                Column('status', css_class='col-md-4'),
            ),
            HTML('<hr><h5 class="mb-3 text-secondary">Seleção de Talhões</h5>'),
            Row(
                Column('fazenda_selector', css_class='col-md-5'),
                Column('talhao_selector', css_class='col-md-5'),
                Column(
                    HTML('<button type="button" id="btn-add-talhao" class="btn btn-primary mt-4 w-100"><i class="bi bi-plus-lg me-1"></i>Adicionar</button>'),
                    css_class='col-md-2'
                ),
            ),
            HTML('''
                <div class="table-responsive mt-3 mb-4">
                    <table class="table table-sm table-hover border rounded" id="table-talhoes-selecionados">
                        <thead class="table-light">
                            <tr>
                                <th>Fazenda</th>
                                <th>Talhão</th>
                                <th class="text-center" style="width: 100px;">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            <!-- Preenchido via JS -->
                        </tbody>
                    </table>
                </div>
            '''),
            Div('talhoes', css_class='d-none'), # Campo real escondido
            HTML('''
                <div class="row mb-3">
                    <div class="col-md-6">
                        <label class="form-label mb-0 fw-bold">Área Total Selecionada (ha):</label>
                        <div id="display-area-total" class="fs-5 text-primary fw-bold">-</div>
                    </div>
                    <div class="col-md-6 text-end">
                        <label class="form-label mb-0 fw-bold">Produção Total Estimada (sc):</label>
                        <div id="display-producao-total" class="fs-5 text-success fw-bold">-</div>
                    </div>
                </div>
                <hr>
            '''),
            Row(
                Column('data_plantio', css_class='col-md-4'),
                Column('data_fim', css_class='col-md-4'),
                Column('preco_venda_estimado_sc', css_class='col-md-4'),
            ),
            Row(
                Column('producao_estimada_sc_ha', css_class='col-md-6'),
                Column('producao_real_saca', css_class='col-md-6'),
            ),
            'observacoes',
            FormActions(
                Submit('submit', 'Salvar Ciclo/Plantio', css_class='btn btn-success'),
                HTML('<a href="{% url \'ciclo_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class OperacaoCampoForm(forms.ModelForm):
    """Formulário para registro de Operação de Campo."""
    
    # Seletores auxiliares
    fazenda_selector = forms.ModelChoiceField(
        queryset=Fazenda.objects.none(),
        label='Selecione a Fazenda',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    talhao_selector = forms.ChoiceField(
        label='Selecione o Talhão',
        required=False,
        choices=[('', 'Selecione a Fazenda primeiro')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    atividade_selector = forms.CharField(
        label='Adicionar Atividade/Item',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite o nome da atividade/item (Ex: Plantio, Adubo, Diesel...)'
        })
    )

    produto_selector = forms.ModelChoiceField(
        queryset=Produto.objects.all(), # Filtro por empresa no __init__
        label='Produto/Insumo',
        required=False,
        empty_label='Selecione...',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Campos auxiliares para o formulário de itens (não salvos diretamente no model pai)
    aux_categoria = forms.ChoiceField(
        choices=CategoriaOperacao.choices,
        label='Categoria',
        required=False,
        initial=CategoriaOperacao.INSUMO,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    aux_descricao = forms.CharField(
        label='Descrição/Serviço',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Aplicação Aérea'})
    )
    aux_quantidade = forms.DecimalField(
        label='Qtd',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    aux_custo_unitario = forms.DecimalField(
        label='Custo Unit.',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    aux_unidade_custo = forms.ChoiceField(
        choices=UnidadeCusto.choices,
        label='Unidade (Custo)',
        required=False,
        initial=UnidadeCusto.BRL,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    TIPO_CALCULO_CHOICES = [
        (False, '/ ha'),
        (True, 'Total'),
    ]
    aux_is_quantidade_total = forms.ChoiceField(
        choices=TIPO_CALCULO_CHOICES,
        label='Tipo Qtd',
        required=False,
        initial=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    aux_is_custo_total = forms.ChoiceField(
        choices=TIPO_CALCULO_CHOICES,
        label='Tipo Custo',
        required=False,
        initial=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    aux_maquinario_terceiro = forms.BooleanField(
        label='Maquinário de Terceiro?',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = OperacaoCampo
        fields = ['safra', 'ciclo', 'data_operacao', 'area_aplicada_ha', 
                  'responsavel', 'observacao', 'status', 'talhoes']
        widgets = {
            'data_operacao': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacao': forms.Textarea(attrs={'rows': 2}),
            'talhoes': forms.SelectMultiple(attrs={'class': 'd-none'}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['safra'].queryset = Safra.objects.filter(empresa=self.empresa, ativa=True)
            self.fields['fazenda_selector'].queryset = Fazenda.objects.filter(empresa=self.empresa, ativo=True)
            self.fields['talhoes'].queryset = Talhao.objects.filter(empresa=self.empresa, ativo=True)
            self.fields['ciclo'].queryset = Plantio.objects.filter(empresa=self.empresa).exclude(status=StatusCiclo.CANCELADO)
            self.fields['atividade_selector'].queryset = AtividadeCampo.objects.filter(empresa=self.empresa, ativo=True)
        else:
            self.fields['safra'].queryset = Safra.objects.none()
            self.fields['fazenda_selector'].queryset = Fazenda.objects.none()
            self.fields['talhoes'].queryset = Talhao.objects.none()
            self.fields['ciclo'].queryset = Plantio.objects.none()
        
        # Make area optional as it can be calculated
        self.fields['area_aplicada_ha'].required = False

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('safra', css_class='col-md-4'),
                Column('ciclo', css_class='col-md-4'),
                Column('data_operacao', css_class='col-md-4'),
            ),
            HTML('<hr class="my-3">'),
            HTML('<h6 class="text-muted mb-3">Localização (Talhões)</h6>'),
            Row(
                Column('fazenda_selector', css_class='col-md-6'),
                Column('talhao_selector', css_class='col-md-6'),
            ),
            Row(
                Column(
                    HTML('<div class="text-center"><button type="button" id="btn-add-talhao" class="btn btn-primary px-5"><i class="bi bi-plus-lg"></i> Adicionar Talhão</button></div>'),
                    css_class='col-12'
                ),
                css_class='mb-3'
            ),
            HTML('''
                <div class="table-responsive mt-3 mb-4">
                    <table class="table table-sm table-hover border" id="table-talhoes-selecionados">
                        <thead class="table-light">
                            <tr>
                                <th>Fazenda</th>
                                <th>Talhão</th>
                                <th class="text-end">Área (ha)</th>
                                <th class="text-center" style="width: 100px;">Ações</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            '''),
            Div('talhoes', css_class='d-none'),
            
            HTML('<hr class="my-3">'),
            HTML('<h6 class="text-muted mb-3">Itens e Atividades</h6>'),
            
            # Card para Adicionar Item
            Div(
                Row(
                   Column('atividade_selector', css_class='col-md-4'),
                   Column('aux_categoria', css_class='col-md-3'),
                   Column('produto_selector', css_class='col-md-5 field-produto'),
                   Column('aux_descricao', css_class='col-md-5 field-descricao', style="display:none;"),
                ),
                Row(
                   Column('aux_quantidade', css_class='col-md-2'),
                   Column('aux_is_quantidade_total', css_class='col-md-2'),
                   Column('aux_custo_unitario', css_class='col-md-2'),
                   Column('aux_is_custo_total', css_class='col-md-2'),
                   Column('aux_unidade_custo', css_class='col-md-2'),
                   Column('aux_maquinario_terceiro', css_class='col-md-2 pt-4'),
                ),
                Row(
                   Column(
                        HTML('<button type="button" id="btn-add-item" class="btn btn-warning w-100"><i class="bi bi-plus-circle"></i> Adicionar ao Grid</button>'),
                        css_class='col-md-12 mt-3'
                   )
                ),
                css_class='p-3 bg-light border rounded mb-3'
            ),
            
            # Tabela de Itens
            HTML('''
                <div class="table-responsive mb-4">
                    <table class="table table-sm table-hover border" id="table-itens-selecionados">
                        <thead class="table-light">
                            <tr>
                                <th>Atividade</th>
                                <th>Detalhe (Produto/Desc)</th>
                                <th class="text-center">Tipo</th>
                                <th class="text-end">Qtd</th>
                                <th class="text-end">Custo Unit.</th>
                                <th class="text-center" style="width: 100px;">Ações</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            '''),
            # Campo escondido para JSON dos itens
            HTML('<input type="hidden" name="itens_json" id="id_itens_json">'),

            Row(
                Column(
                    HTML('<div class="text-end fw-bold">Área Total: <span id="display-area-total" class="text-primary">0.00</span> ha</div>'),
                    css_class='col-12'
                )
            ),
            HTML('<hr class="my-3">'),
            Row(
                 Column('area_aplicada_ha', css_class='col-md-3'), 
                 Column('status', css_class='col-md-3'),
                 Column('responsavel', css_class='col-md-6')
            ),
            'observacao',
            FormActions(
                Submit('submit', 'Registrar Operação', css_class='btn btn-success'),
                HTML('<a href="{% url \'operacao_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class FiltroRelatorioForm(forms.Form):
    """Formulário para filtros do dashboard/relatórios."""
    
    fazenda = forms.ModelChoiceField(
        queryset=Fazenda.objects.filter(ativo=True),
        required=False,
        empty_label='Todas as Fazendas'
    )
    talhao = forms.ModelChoiceField(
        queryset=Talhao.objects.filter(ativo=True),
        required=False,
        empty_label='Todos os Talhões'
    )
    ciclo = forms.ModelChoiceField(
        queryset=Plantio.objects.all(),
        required=False,
        empty_label='Todos os Ciclos'
    )
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    preco_referencia = forms.DecimalField(
        label='Preço Saca (R$)',
        required=False,
        initial=Decimal('120.00'),
        min_value=Decimal('0.01'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['fazenda'].queryset = Fazenda.objects.filter(empresa=self.empresa, ativo=True)
            self.fields['talhao'].queryset = Talhao.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['ciclo'].queryset = Plantio.objects.filter(empresa=self.empresa)
        else:
            self.fields['fazenda'].queryset = Fazenda.objects.none()
            self.fields['talhao'].queryset = Talhao.objects.none()
            self.fields['ciclo'].queryset = Plantio.objects.none()

        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_class = 'row g-3 align-items-end'
        self.helper.layout = Layout(
            Column('fazenda', css_class='col-md-3'),
            Column('talhao', css_class='col-md-3'),
            Column('ciclo', css_class='col-md-2'),
            Column('preco_referencia', css_class='col-md-2'),
            Column(
                Submit('filtrar', 'Filtrar', css_class='btn btn-primary w-100'),
                css_class='col-md-2'
            ),
        )


class TenantRegistrationForm(forms.Form):
    """Formulário para cadastro de nova Empresa e Administrador (SaaS)."""
    
    # Dados da Empresa
    nome_empresa = forms.CharField(label='Nome da Empresa', max_length=100)
    cnpj = forms.CharField(label='CNPJ', max_length=18, required=False)
    
    # Dados do Admin
    username = forms.CharField(label='Usuário Admin', max_length=150)
    email = forms.EmailField(label='Email', max_length=254)
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Confirmar Senha', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "As senhas não conferem.")
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3 text-primary border-bottom pb-2">Dados da Empresa</h5>'),
            Row(
                Column('nome_empresa', css_class='col-md-8'),
                Column('cnpj', css_class='col-md-4'),
            ),
            HTML('<h5 class="mb-3 mt-4 text-primary border-bottom pb-2">Dados do Administrador</h5>'),
            Row(
                Column('username', css_class='col-md-6'),
                Column('email', css_class='col-md-6'),
            ),
            Row(
                Column('password', css_class='col-md-6'),
                Column('password_confirm', css_class='col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Cadastrar Empresa', css_class='btn btn-success btn-lg mt-3'),
            )
        )


class ConfiguracaoSistemaForm(forms.ModelForm):
    """Formulário para edição das configurações do sistema (Master)."""
    
    class Meta:
        model = ConfiguracaoSistema
        fields = ['nome_sistema', 'logo', 'cor_primaria', 'mensagem_dashboard']
        widgets = {
            'mensagem_dashboard': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3 text-primary border-bottom pb-2">Identidade Visual</h5>'),
            Row(
                Column('nome_sistema', css_class='col-md-6'),
                Column('cor_primaria', css_class='col-md-3'),
            ),
            'logo',
            HTML('<h5 class="mb-3 mt-4 text-primary border-bottom pb-2">Conteúdo</h5>'),
        )


class UserProfileForm(forms.ModelForm):
    """Formulário para edição do perfil do usuário (nome e email)."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail'
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
            ),
            'email',
            FormActions(
                Submit('submit', 'Atualizar Perfil', css_class='btn btn-success'),
                HTML('<a href="{% url \'dashboard\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class UserInvitationForm(forms.ModelForm):
    """Formulário para convidar novo usuário."""
    class Meta:
        model = UserInvitation
        fields = ['email', 'role']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'email',
            'role',
            FormActions(
                Submit('submit', 'Enviar Convite', css_class='btn btn-primary'),
                HTML('<a href="{% url \'team_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )



from .models import ClimaFazenda, FonteDadosClimaticos

class ClimaFazendaForm(forms.ModelForm):
    """Formulário para registro manual de dados climáticos da fazenda."""
    class Meta:
        model = ClimaFazenda
        fields = ['data', 'temp_max', 'temp_min', 'precipitacao', 'umidade_relativa', 'velocidade_vento']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.fonte = FonteDadosClimaticos.MANUAL
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('data', css_class='col-md-12'),
            ),
            Row(
                Column('temp_max', css_class='col-md-6'),
                Column('temp_min', css_class='col-md-6'),
            ),
            Row(
                Column('precipitacao', css_class='col-md-4'),
                Column('umidade_relativa', css_class='col-md-4'),
                Column('velocidade_vento', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Registro', css_class='btn btn-success'),
                HTML('<button type="button" class="btn btn-secondary ms-2" data-bs-dismiss="modal">Cancelar</button>'),
            )
        )


class RomaneioForm(forms.ModelForm):
    """Formulário para cadastro de Romaneio."""
    
    class Meta:
        model = Romaneio
        fields = [
            'data', 'numero_ticket', 'fazenda', 'talhao', 'plantio', 'motorista', 'placa', 
            'peso_bruto', 'peso_tara', 
            'umidade_percentual', 'impureza_percentual', 'avariado_percentual',
            'desconto_kg_umidade', 'desconto_kg_impureza', 'desconto_kg_avariado',
            'armazem_terceiro'
        ]
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'peso_tara': forms.NumberInput(attrs={'step': '1'}),
            'peso_bruto': forms.NumberInput(attrs={'step': '1'}),
            'umidade_percentual': forms.NumberInput(attrs={'step': '0.01'}),
            'impureza_percentual': forms.NumberInput(attrs={'step': '0.01'}),
            'avariado_percentual': forms.NumberInput(attrs={'step': '0.01'}),
            'desconto_kg_umidade': forms.NumberInput(attrs={'step': '1'}),
            'desconto_kg_impureza': forms.NumberInput(attrs={'step': '1'}),
            'desconto_kg_avariado': forms.NumberInput(attrs={'step': '1'}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['fazenda'].queryset = Fazenda.objects.filter(empresa=self.empresa)
            self.fields['talhao'].queryset = Talhao.objects.filter(ativo=True, empresa=self.empresa)
            self.fields['plantio'].queryset = Plantio.objects.filter(status=StatusCiclo.EM_ANDAMENTO, empresa=self.empresa)
            self.fields['armazem_terceiro'].queryset = TaxaArmazem.objects.filter(empresa=self.empresa)
        else:
            self.fields['fazenda'].queryset = Fazenda.objects.none()
            self.fields['talhao'].queryset = Talhao.objects.none()
            self.fields['plantio'].queryset = Plantio.objects.none()
            self.fields['armazem_terceiro'].queryset = TaxaArmazem.objects.none()

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('data', css_class='col-md-3'),
                Column('numero_ticket', css_class='col-md-3'),
                Column('fazenda', css_class='col-md-6'),
            ),
            Row(
                Column('talhao', css_class='col-md-4'),
                Column('plantio', css_class='col-md-4'),
                Column('armazem_terceiro', css_class='col-md-4'),
            ),
            Row(
                Column('motorista', css_class='col-md-6'),
                Column('placa', css_class='col-md-6'),
            ),
            Row(
                Column('peso_bruto', css_class='col-md-6'),
                Column('peso_tara', css_class='col-md-6'),
            ),
            HTML('<hr class="my-3"><h6 class="text-primary"><i class="bi bi-percent mr-2"></i> Classificação (%)</h6>'),
            Row(
                Column('umidade_percentual', css_class='col-md-4'),
                Column('impureza_percentual', css_class='col-md-4'),
                Column('avariado_percentual', css_class='col-md-4'),
            ),
            HTML('<h6 class="text-danger mt-3"><i class="bi bi-dash-circle mr-2"></i> Descontos em Massa (kg)</h6><small class="text-muted">Informe se houver valores manuais, senão deixe zerado para cálculo automático.</small>'),
            Row(
                Column('desconto_kg_umidade', css_class='col-md-4'),
                Column('desconto_kg_impureza', css_class='col-md-4'),
                Column('desconto_kg_avariado', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Romaneio', css_class='btn btn-success'),
                HTML('<a href="{% url \'romaneio_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class ContratoVendaForm(forms.ModelForm):
    """Formulário para cadastro de Contratos de Venda."""
    
    itens_json = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    # Aux fields
    aux_produto = forms.ModelChoiceField(queryset=Produto.objects.none(), label='', required=False)
    aux_fazenda = forms.ModelChoiceField(queryset=Fazenda.objects.none(), label='Fazenda (Opcional)', required=False)
    aux_quantidade = forms.DecimalField(label='Qtd', required=False, min_value=0)
    aux_unidade = forms.ChoiceField(
        choices=[
            ('SC', 'SC (60kg)'), 
            ('SC50', 'SC (50kg)'),
            ('SC40', 'SC (40kg)'),
            ('SC25', 'SC (25kg)'),
            ('KG', 'Quilo'), 
            ('TON', 'Ton')
        ],
        label='Unid.', required=False
    )
    aux_valor_unitario = forms.DecimalField(label='Valor (R$)', required=False, min_value=0)

    class Meta:
        model = ContratoVenda
        fields = ['cliente', 'tipo', 'data_entrega', 'observacoes']
        widgets = {
            'data_entrega': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['cliente'].queryset = Cliente.objects.filter(empresa=self.empresa)
            self.fields['aux_produto'].queryset = Produto.objects.filter(empresa=self.empresa, ativo=True)
            self.fields['aux_fazenda'].queryset = Fazenda.objects.filter(empresa=self.empresa, ativo=True)
        else:
            self.fields['cliente'].queryset = Cliente.objects.none()
            
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('<h6 class="text-muted mb-2">Dados do Contrato</h6>'),
            Row(
                Column('cliente', css_class='col-md-5'),
                Column('tipo', css_class='col-md-4'),
                Column('data_entrega', css_class='col-md-3'),
            ),
            'observacoes',
            HTML('<h6 class="text-muted mb-2 mt-3">Adicionar Item</h6>'),
            Div(
                Row(
                    Column(
                        HTML('<div class="d-flex justify-content-between"><label class="form-label">Produto</label><a href="#" data-bs-toggle="modal" data-bs-target="#newProductModal" class="small text-success">+ Novo</a></div>'),
                        Field('aux_produto', wrapper_class='mb-0'),
                        css_class='col-md-3'
                    ),
                    Column('aux_fazenda', css_class='col-md-3'),
                    Column('aux_quantidade', css_class='col-md-2'),
                    Column('aux_unidade', css_class='col-md-2'),
                    Column('aux_valor_unitario', css_class='col-md-2'),
                ),
                css_class='p-2 bg-light border rounded'
            ),
            Field('itens_json'),
        ) 


class RateioCustoForm(forms.ModelForm):
    """Formulário para lançar Rateio de Custos."""
    
    class Meta:
        model = RateioCusto
        fields = ['data', 'descricao', 'valor_total', 'safra', 'criterio']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'valor_total': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'R$ 0,00'}),
            'descricao': forms.TextInput(attrs={'placeholder': 'Ex: Energia Elétrica Jan/24'}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['safra'].queryset = Safra.objects.filter(empresa=self.empresa, ativa=True)
            
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('data', css_class='col-md-3'),
                Column('valor_total', css_class='col-md-3'),
                Column('criterio', css_class='col-md-6'),
            ),
            Row(
                Column('descricao', css_class='col-md-8'),
                Column('safra', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Processar Rateio', css_class='btn btn-primary'),
                HTML('<a href="{% url \'rateio_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class FixacaoForm(forms.ModelForm):
    """Formulário para Fixação de Preço."""
    
    class Meta:
        model = Fixacao
        fields = ['data_fixacao', 'contrato', 'romaneio', 'item', 'quantidade', 'preco', 'observacoes']
        widgets = {
            'data_fixacao': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'quantidade': forms.NumberInput(attrs={'step': '0.01'}),
            'preco': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'R$ 0,00'}),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['contrato'].queryset = ContratoVenda.objects.filter(empresa=self.empresa)
            self.fields['romaneio'].queryset = Romaneio.objects.filter(empresa=self.empresa)
            # Item queryset logic relies on contract, ideally filtered by JS, but here we can at least limit to enterprise
            self.fields['item'].queryset = ItemContratoVenda.objects.filter(contrato__empresa=self.empresa)
            
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('data_fixacao', css_class='col-md-3'),
                Column('contrato', css_class='col-md-5'),
                Column('romaneio', css_class='col-md-4'),
            ),
            Row(
                Column('item', css_class='col-md-12'),
            ),
            Row(
                Column('quantidade', css_class='col-md-6'),
                Column('preco', css_class='col-md-6'),
            ),
            'observacoes',
            FormActions(
                Submit('submit', 'Confirmar Fixação', css_class='btn btn-success'),
                HTML('<a href="{% url \'fixacao_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )



class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'cpf_cnpj', 'telefone', 'email', 'cidade', 'estado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nome', css_class='col-md-8'),
                Column('cpf_cnpj', css_class='col-md-4'),
            ),
            Row(
                Column('telefone', css_class='col-md-4'),
                Column('email', css_class='col-md-8'),
            ),
            Row(
                Column('cidade', css_class='col-md-8'),
                Column('estado', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Cliente', css_class='btn btn-primary'),
                HTML('<a class="btn btn-secondary" href="{% url "cliente_list" %}">Cancelar</a>')
            )
        )


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'cpf_cnpj', 'telefone', 'email', 'cidade', 'estado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nome', css_class='col-md-8'),
                Column('cpf_cnpj', css_class='col-md-4'),
            ),
            Row(
                Column('telefone', css_class='col-md-4'),
                Column('email', css_class='col-md-8'),
            ),
            Row(
                Column('cidade', css_class='col-md-8'),
                Column('estado', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Fornecedor', css_class='btn btn-primary'),
                HTML('<a class="btn btn-secondary" href="{% url "fornecedor_list" %}">Cancelar</a>')
            )
        )


class TaxaArmazemForm(forms.ModelForm):
    """Formulário para configuração de taxas de armazém."""
    class Meta:
        model = TaxaArmazem
        fields = ['fornecedor', 'taxa_recepcao', 'taxa_armazenagem', 'frequencia', 'unidade', 'quebra_tecnica']

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['fornecedor'].queryset = Fornecedor.objects.filter(empresa=self.empresa)
        else:
            self.fields['fornecedor'].queryset = Fornecedor.objects.none()

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('fornecedor', css_class='col-md-12 mb-3'),
                css_class='row'
            ),
            Row(
                Column('taxa_recepcao', css_class='col-md-6 mb-3'),
                Column('quebra_tecnica', css_class='col-md-6 mb-3'),
                css_class='row'
            ),
            HTML('<hr>'),
            Row(
                Column('taxa_armazenagem', css_class='col-md-4 mb-3'),
                Column('frequencia', css_class='col-md-4 mb-3'),
                Column('unidade', css_class='col-md-4 mb-3'),
                css_class='row'
            ),
            FormActions(
                Submit('submit', 'Salvar Taxas', css_class='btn btn-primary'),
                HTML('<a class="btn btn-secondary" href="{% url "armazem_list" %}">Cancelar</a>')
            )
        )


from .models import (
    CategoriaFinanceira, ContaPagar, ContaReceber, BaixaContaPagar, BaixaContaReceber, StatusFinanceiro
)

class CategoriaFinanceiraForm(forms.ModelForm):
    class Meta:
        model = CategoriaFinanceira
        fields = ['nome', 'tipo', 'ativo']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'nome',
            'tipo',
            'ativo',
            FormActions(
                Submit('submit', 'Salvar Categoria', css_class='btn btn-success'),
                HTML('<a href="{% url \'financeiro_config\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )


class ContaPagarForm(forms.ModelForm):
    class Meta:
        model = ContaPagar
        fields = ['descricao', 'fornecedor', 'categoria', 'fazenda', 'data_vencimento', 'valor_total', 'status', 'observacao', 'arquivo']
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if self.empresa:
            self.fields['fornecedor'].queryset = Fornecedor.objects.filter(empresa=self.empresa)
            self.fields['categoria'].queryset = CategoriaFinanceira.objects.filter(empresa=self.empresa, tipo='SAIDA', ativo=True)
            self.fields['fazenda'].queryset = Fazenda.objects.filter(empresa=self.empresa, ativo=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('descricao', css_class='col-md-12'),
            ),
            Row(
                Column('fornecedor', css_class='col-md-6'),
                Column('categoria', css_class='col-md-6'),
            ),
            Row(
                Column('fazenda', css_class='col-md-4'),
                Column('data_vencimento', css_class='col-md-4'),
                Column('valor_total', css_class='col-md-4'),
            ),
            'observacao',
            'arquivo',
            Row(
                Column('status', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Conta', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'conta_pagar_list\' %}" class="btn btn-secondary btn-lg ms-2">Cancelar</a>'),
            )
        )


class ContaReceberForm(forms.ModelForm):
    class Meta:
        model = ContaReceber
        fields = ['descricao', 'cliente', 'categoria', 'fazenda', 'data_vencimento', 'valor_total', 'status', 'observacao']
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        if self.empresa:
            self.fields['cliente'].queryset = Cliente.objects.filter(empresa=self.empresa)
            self.fields['categoria'].queryset = CategoriaFinanceira.objects.filter(empresa=self.empresa, tipo='ENTRADA', ativo=True)
            self.fields['fazenda'].queryset = Fazenda.objects.filter(empresa=self.empresa, ativo=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('descricao', css_class='col-md-12'),
            ),
            Row(
                Column('cliente', css_class='col-md-6'),
                Column('categoria', css_class='col-md-6'),
            ),
            Row(
                Column('fazenda', css_class='col-md-4'),
                Column('data_vencimento', css_class='col-md-4'),
                Column('valor_total', css_class='col-md-4'),
            ),
            'observacao',
            Row(
                Column('status', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Salvar Conta', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'conta_receber_list\' %}" class="btn btn-secondary btn-lg ms-2">Cancelar</a>'),
            )
        )


class BaixaContaPagarForm(forms.ModelForm):
    class Meta:
        model = BaixaContaPagar
        fields = ['data_pagamento', 'valor', 'metodo', 'comprovante', 'observacao']
        widgets = {
            'data_pagamento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('data_pagamento', css_class='col-md-6'),
                Column('valor', css_class='col-md-6'),
            ),
            'metodo',
            'comprovante',
            'observacao',
            FormActions(
                Submit('submit', 'Confirmar Pagamento', css_class='btn btn-primary w-100'),
            )
        )


class BaixaContaReceberForm(forms.ModelForm):
    class Meta:
        model = BaixaContaReceber
        fields = ['data_recebimento', 'valor', 'metodo', 'observacao']
        widgets = {
            'data_recebimento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observacao': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('data_recebimento', css_class='col-md-6'),
                Column('valor', css_class='col-md-6'),
            ),
            'metodo',
            'observacao',
            FormActions(
                Submit('submit', 'Confirmar Recebimento', css_class='btn btn-primary w-100'),
            )
        )


class SafraForm(forms.ModelForm):
    """Formulário para cadastro/edição de Safra."""

    class Meta:
        model = Safra
        fields = ['nome', 'data_inicio', 'data_fim', 'ativa']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        # Empresa is not strictly needed for Safra in current model (it inherits TenantAware but Safra logic is usually global or by company)
        # But we keep consistency with other forms
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nome', css_class='col-md-6'),
                Column('ativa', css_class='col-md-6 pt-4'),
            ),
            Row(
                Column('data_inicio', css_class='col-md-6'),
                Column('data_fim', css_class='col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Salvar Safra', css_class='btn btn-success'),
                HTML('<a href="{% url \'safra_list\' %}" class="btn btn-secondary ms-2">Cancelar</a>'),
            )
        )





class AlvoMonitoramentoForm(forms.ModelForm):
    class Meta:
        model = AlvoMonitoramento
        fields = ['nome', 'tipo', 'nivel_alerta', 'imagem', 'descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nome', css_class='col-md-8'),
                Column('tipo', css_class='col-md-4'),
            ),
            Row(
                Column('nivel_alerta', css_class='col-md-4'),
                Column('imagem', css_class='col-md-8'),
            ),
            'descricao',
            FormActions(
                Submit('submit', 'Salvar Alvo', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'alvo_list\' %}" class="btn btn-secondary btn-lg ms-2">Cancelar</a>'),
            )
        )

class MonitoramentoForm(forms.ModelForm):
    """
    Formulário para registro de monitoramento com suporte a Safra/Ciclo e múltiplos talhões.
    """
    fazenda_selector = forms.ModelChoiceField(
        queryset=Fazenda.objects.none(),
        label='Filtrar por Fazenda',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Monitoramento
        fields = ['safra', 'ciclo', 'talhoes', 'data_coleta', 'foto', 'latitude', 'longitude', 'observacoes']
        widgets = {
            'data_coleta': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
            'talhoes': forms.SelectMultiple(attrs={'class': 'd-none'}), # Will be handled by JS/Checkboxes in template
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            self.fields['safra'].queryset = Safra.objects.filter(empresa=empresa, ativa=True)
            self.fields['ciclo'].queryset = Plantio.objects.filter(empresa=empresa).exclude(status=StatusCiclo.CANCELADO)
            self.fields['talhoes'].queryset = Talhao.objects.filter(empresa=empresa, ativo=True)
            self.fields['fazenda_selector'].queryset = Fazenda.objects.filter(empresa=empresa, ativo=True)
        
        self.helper = FormHelper()
        self.helper.form_tag = False 
        self.helper.layout = Layout(
            Row(
                Column('safra', css_class='col-md-4'),
                Column('ciclo', css_class='col-md-4'),
                Column('data_coleta', css_class='col-md-4'),
            ),
            Row(
                Column('fazenda_selector', css_class='col-md-6'),
                Column('foto', css_class='col-md-6'),
            ),
            Row(
                Column('latitude', css_class='col-md-6'),
                Column('longitude', css_class='col-md-6'),
            ),
            'talhoes',
            'observacoes',
        )

# Formset for Monitoring Items
MonitoramentoItemFormSet = inlineformset_factory(
    Monitoramento, 
    MonitoramentoItem,
    fields=['alvo', 'incidencia', 'severidade', 'contagem'],
    extra=1,
    can_delete=True,
    widgets={
        'alvo': forms.Select(attrs={'class': 'form-select'}),
        'incidencia': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '%'}),
        'severidade': forms.Select(attrs={'class': 'form-select'}),
        'contagem': forms.NumberInput(attrs={'class': 'form-control'}),
    }
)
