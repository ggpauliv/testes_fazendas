"""
AgroTalhoes - Modelos de Dados

Sistema de Gestão de Fazendas
Modelos compatíveis com SQL Server via mssql-django
"""

from django.db import models
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal
from decimal import Decimal
import json
import uuid
from django.contrib.auth.models import User


class Empresa(models.Model):
    """
    Representa a empresa/fazenda cliente (Tenant).
    """
    nome = models.CharField(max_length=100, verbose_name='Nome da Empresa')
    cnpj = models.CharField(max_length=18, blank=True, null=True, verbose_name='CNPJ')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')

    class Meta:
        db_table = 'empresas'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.nome


class UserRole(models.TextChoices):
    OWNER = 'OWNER', 'Proprietário'
    MANAGER = 'MANAGER', 'Gerente'
    OPERATOR = 'OPERATOR', 'Operador'

class UserProfile(models.Model):
    """
    Extensão do usuário para vincular à empresa.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='usuarios')
    role = models.CharField(
        max_length=20, 
        choices=UserRole.choices, 
        default=UserRole.OWNER,
        verbose_name='Função'
    )

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuário'

    def __str__(self):
        return f"{self.user.username} - {self.empresa.nome} ({self.get_role_display()})"


class UserInvitation(models.Model):
    """
    Convite para novos usuários se juntarem a uma empresa.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name='Empresa')
    email = models.EmailField(verbose_name='E-mail do Convidado')
    role = models.CharField(
        max_length=20, 
        choices=UserRole.choices, 
        default=UserRole.OPERATOR,
        verbose_name='Função'
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pendente'),
            ('ACCEPTED', 'Aceito'),
            ('EXPIRED', 'Expirado')
        ],
        default='PENDING',
        verbose_name='Status'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Convidado por')

    class Meta:
        db_table = 'user_invitations'
        verbose_name = 'Convite de Usuário'
        verbose_name_plural = 'Convites de Usuários'

    def __str__(self):
        return f"Convite para {self.email} - {self.empresa.nome}"


class TenantAwareModel(models.Model):
    """
    Classe abstrata para adicionar suporte a multi-tenancy.
    """
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name='Empresa'
    )

    class Meta:
        abstract = True


class Cliente(TenantAwareModel):
    """
    Representa um cliente (comprador de grãos).
    """
    nome = models.CharField(max_length=200, verbose_name='Razão Social / Nome')
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True, verbose_name='CPF/CNPJ')
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefone')
    email = models.EmailField(blank=True, null=True, verbose_name='Email')
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cidade')
    estado = models.CharField(max_length=2, blank=True, null=True, verbose_name='UF')
    
    class Meta:
        db_table = 'clientes'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Fornecedor(TenantAwareModel):
    """
    Representa um fornecedor (insumos, armazém, serviços).
    """
    nome = models.CharField(max_length=200, verbose_name='Razão Social / Nome')
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True, verbose_name='CPF/CNPJ')
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefone')
    email = models.EmailField(blank=True, null=True, verbose_name='Email')
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cidade')
    estado = models.CharField(max_length=2, blank=True, null=True, verbose_name='UF')
    
    class Meta:
        db_table = 'fornecedores'
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome']

    def __str__(self):
        return self.nome

class Safra(TenantAwareModel):
    """
    Representa o ano agrícola/safra (ex: 2023/2024).
    """
    nome = models.CharField(max_length=50, verbose_name='Nome da Safra (Ex: 23/24)')
    data_inicio = models.DateField(verbose_name='Data Início')
    data_fim = models.DateField(verbose_name='Data Fim')
    ativa = models.BooleanField(default=True, verbose_name='Safra Atual?')

    class Meta:
        db_table = 'safras'
        verbose_name = 'Safra'
        verbose_name_plural = 'Safras'
        ordering = ['-data_inicio']

    def __str__(self):
        return self.nome


class Fazenda(TenantAwareModel):
    """
    Representa uma fazenda pertencente a uma empresa/tenant.
    Agrupa diversos talhões.
    """
    nome = models.CharField(max_length=100, verbose_name='Nome da Fazenda')
    endereco = models.CharField(max_length=200, blank=True, null=True, verbose_name='Endereço')
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cidade')
    estado = models.CharField(max_length=2, blank=True, null=True, verbose_name='UF')
    area_total_hectares = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0, 
        verbose_name='Área Total (ha)'
    )
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True, 
        verbose_name='Latitude'
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True, 
        verbose_name='Longitude'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Atualização')

    class Meta:
        db_table = 'fazendas'
        verbose_name = 'Fazenda'
        verbose_name_plural = 'Fazendas'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Talhao(TenantAwareModel):
    """
    Modelo para representar um talhão (parcela de terra) na fazenda.
    As coordenadas são armazenadas como JSON para compatibilidade com Google Maps.
    """
    fazenda = models.ForeignKey(
        Fazenda,
        on_delete=models.CASCADE,
        related_name='talhoes',
        verbose_name='Fazenda',
        null=True,  # Nullable initially to support existing records
        blank=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='subtalhoes',
        verbose_name='Talhão Pai',
        null=True,
        blank=True,
        help_text='Se preenchido, este talhão é uma subdivisão do pai.'
    )
    nome = models.CharField(
        max_length=100,
        verbose_name='Nome do Talhão'
    )
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição'
    )
    tipo_solo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Tipo de Solo',
        choices=[
            ('ARGILOSO', 'Argiloso'),
            ('ARENOSO', 'Arenoso'),
            ('MISTO', 'Misto'),
            ('HUMIFERO', 'Humífero')
        ]
    )
    coordenadas_json = models.TextField(
        blank=True,
        null=True,
        verbose_name='Coordenadas (JSON)',
        help_text='Array de coordenadas lat/lng do polígono no formato JSON'
    )
    area_hectares = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name='Área (hectares)'
    )
    cultura_atual = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Cultura Atual'
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Cadastro'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Atualização'
    )

    class Meta:
        db_table = 'talhoes'
        verbose_name = 'Talhão'
        verbose_name_plural = 'Talhões'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.area_hectares} ha)"

    def get_coordenadas(self):
        """Retorna as coordenadas como lista Python."""
        if self.coordenadas_json:
            try:
                return json.loads(self.coordenadas_json)
            except json.JSONDecodeError:
                return []
        return []

    def set_coordenadas(self, coordenadas_list):
        """Define as coordenadas a partir de uma lista Python."""
        self.coordenadas_json = json.dumps(coordenadas_list)

    def calcular_custo_total(self):
        """
        Calcula o custo total de todas as operações realizadas neste talhão.
        Considera rateio pela área do talhão se a operação envolve múltiplos talhões.
        """
        custo_total = Decimal('0.00')
        # Usar operacoes_campo (nome do related_name definido no M2M) ou checar definição
        for operacao in self.operacoes_campo.all():
           op_custo = operacao.custo_total
           op_area = operacao.area_aplicada_ha or Decimal('1')
           
           # Rateio simples pela área do talhão (Assumindo que a operação cobriu o talhão todo)
           # Se op_area > self.area_hectares, entende-se que cobriu mais áreas.
           # Proporção = self.area_hectares / op_area
           if op_area > 0:
               proporcao = self.area_hectares / op_area
               if proporcao > 1: proporcao = Decimal('1.0') # Não cobrar mais que o total
               custo_total += op_custo * proporcao
           else:
               custo_total += op_custo

        return custo_total

    def calcular_lucro(self, producao_estimada_sc_ha=0, preco_venda_estimado_sc=Decimal('0.00')):
        """
        Calcula o lucro estimado do talhão.
        Lucro = (Produção Estimada * Preço Venda) - Custo Total
        """
        receita = Decimal(producao_estimada_sc_ha) * preco_venda_estimado_sc
        custo = self.calcular_custo_total()
        return receita - custo


class CategoriaProduto(models.TextChoices):
    """Categorias de produtos/insumos."""
    SEMENTE = 'SEMENTE', 'Semente'
    FERTILIZANTE = 'FERTILIZANTE', 'Fertilizante'
    DEFENSIVO = 'DEFENSIVO', 'Defensivo Agrícola'
    HERBICIDA = 'HERBICIDA', 'Herbicida'
    FUNGICIDA = 'FUNGICIDA', 'Fungicida'
    INSETICIDA = 'INSETICIDA', 'Inseticida'
    GRAO = 'GRAO', 'Grão (Produção)'
    OUTROS = 'OUTROS', 'Outros'


class Produto(TenantAwareModel):
    """
    Modelo para representar produtos/insumos agrícolas.
    """
    nome = models.CharField(
        max_length=200,
        verbose_name='Nome do Produto'
    )
    codigo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Código',
        help_text='Código interno ou NCM'
    )
    categoria = models.CharField(
        max_length=20,
        choices=CategoriaProduto.choices,
        default=CategoriaProduto.OUTROS,
        verbose_name='Categoria'
    )
    unidade = models.CharField(
        max_length=20,
        default='KG',
        verbose_name='Unidade de Medida',
        help_text='Ex: KG, L, UN, SC'
    )
    estoque_atual = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        verbose_name='Estoque Atual'
    )
    estoque_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        verbose_name='Estoque Mínimo'
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Cadastro'
    )

    class Meta:
        db_table = 'produtos'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.unidade})"

    def get_preco_medio(self):
        """
        Calcula o preço médio do produto baseado nas movimentações de entrada.
        """
        entradas = self.movimentacoes.filter(tipo='ENTRADA')
        total_quantidade = entradas.aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']
        total_valor = entradas.aggregate(
            total=Coalesce(
                Sum(F('quantidade') * F('valor_unitario'), output_field=DecimalField()),
                Decimal('0')
            )
        )['total']
        
        if total_quantidade and total_quantidade > 0:
            return total_valor / total_quantidade
        return Decimal('0.00')

    def atualizar_estoque(self):
        """
        Atualiza o estoque atual baseado nas movimentações.
        """
        entradas = self.movimentacoes.filter(tipo='ENTRADA').aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']
        saidas = self.movimentacoes.filter(tipo='SAIDA').aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']
        
        self.estoque_atual = entradas - saidas
        self.save(update_fields=['estoque_atual'])

    def get_estoque_por_fazenda(self, fazenda_id):
        """
        Calcula o estoque atual de um produto em uma fazenda específica.
        """
        entradas = self.movimentacoes.filter(tipo='ENTRADA', fazenda_id=fazenda_id).aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']
        saidas = self.movimentacoes.filter(tipo='SAIDA', fazenda_id=fazenda_id).aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']
        return entradas - saidas

    @property
    def estoque_baixo(self):
        """Verifica se o estoque está abaixo do mínimo."""
        return self.estoque_atual <= self.estoque_minimo


class TipoMovimentacao(models.TextChoices):
    """Tipos de movimentação de estoque."""
    ENTRADA = 'ENTRADA', 'Entrada'
    SAIDA = 'SAIDA', 'Saída'


class StatusPedido(models.TextChoices):
    ABERTO = 'ABERTO', 'Aberto'
    PARCIAL = 'PARCIAL', 'Parcialmente Atendido'
    CONCLUIDO = 'CONCLUIDO', 'Concluído'
    CANCELADO = 'CANCELADO', 'Cancelado'


class PedidoCompra(TenantAwareModel):
    """
    Cabeçalho do Pedido de Compra.
    Agrupa vários itens solicitados a um fornecedor.
    """
    fornecedor = models.ForeignKey(
        Fornecedor, 
        on_delete=models.CASCADE, 
        verbose_name='Fornecedor',
        null=True, 
        blank=True
    )
    data_pedido = models.DateField(verbose_name='Data do Pedido')
    data_prevista = models.DateField(blank=True, null=True, verbose_name='Previsão de Entrega')
    arquivo = models.FileField(upload_to='pedidos/', blank=True, null=True, verbose_name='Arquivo/Contrato')
    status = models.CharField(
        max_length=20, choices=StatusPedido.choices, default=StatusPedido.ABERTO, verbose_name='Status Geral'
    )
    observacoes = models.TextField(blank=True, null=True, verbose_name='Observações')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pedidos_compra'
        verbose_name = 'Pedido de Compra'
        verbose_name_plural = 'Pedidos de Compra'
        ordering = ['-data_pedido']

    def __str__(self):
        return f"Pedido #{self.id} - {self.fornecedor}"

    @property
    def valor_total(self):
        return self.itens.aggregate(
            total=Coalesce(Sum(F('quantidade') * F('valor_unitario')), Decimal('0'))
        )['total']

    @property
    def progresso_geral(self):
        total_items = self.itens.count()
        if total_items == 0: return 0
        concluidos = self.itens.filter(status=StatusPedido.CONCLUIDO).count()
        return (concluidos / total_items) * 100


class ItemPedidoCompra(TenantAwareModel):
    """
    Item individual do Pedido de Compra (Ex: 100 sacas de Soja).
    """
    pedido = models.ForeignKey(PedidoCompra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, verbose_name='Produto')
    fazenda = models.ForeignKey(Fazenda, on_delete=models.SET_NULL, verbose_name='Fazenda (Opcional)', null=True, blank=True, help_text="Informe se este item será destinado a uma fazenda específica.")
    quantidade = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Qtd. Solicitada')
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='Valor Unitário')
    status = models.CharField(
        max_length=20, choices=StatusPedido.choices, default=StatusPedido.ABERTO, verbose_name='Status Item'
    )

    class Meta:
        db_table = 'itens_pedido_compra'
        verbose_name = 'Item do Pedido'
        verbose_name_plural = 'Itens do Pedido'

    def __str__(self):
        return f"{self.produto.nome} ({self.quantidade} {self.produto.unidade})"

    @property
    def valor_total(self):
        return self.quantidade * self.valor_unitario

    @property
    def quantidade_entregue(self):
        """Soma das movimentações de ENTRADA vinculadas a este item."""
        return self.movimentacoes.aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']

    @property
    def saldo_restante(self):
        return self.quantidade - self.quantidade_entregue

    @property
    def percentual_concluido(self):
        if self.quantidade > 0:
            return (self.quantidade_entregue / self.quantidade) * 100
        return Decimal('0')

    def update_status(self):
        """Atualiza status do item baseado no saldo."""
        saldo = self.saldo_restante
        if saldo <= 0:
            self.status = StatusPedido.CONCLUIDO
        elif saldo < self.quantidade:
            self.status = StatusPedido.PARCIAL
        else:
            self.status = StatusPedido.ABERTO
        self.save()
        # Atualiza status do pai também se necessário (simplificado)


class MovimentacaoEstoque(TenantAwareModel):
    """
    Modelo para registrar movimentações de entrada e saída de estoque.
    Suporta importação de NFe com armazenamento da chave de acesso.
    """
    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
        related_name='movimentacoes',
        verbose_name='Produto'
    )
    fazenda = models.ForeignKey(
        'Fazenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes',
        verbose_name='Fazenda'
    )
    tipo = models.CharField(
        max_length=10,
        choices=TipoMovimentacao.choices,
        verbose_name='Tipo'
    )
    quantidade = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name='Quantidade'
    )
    valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name='Valor Unitário'
    )
    data_movimentacao = models.DateTimeField(
        default=timezone.now,
        verbose_name='Data da Movimentação'
    )
    chave_nfe = models.CharField(
        max_length=44,
        blank=True,
        null=True,
        verbose_name='Chave NFe',
        help_text='Chave de acesso da Nota Fiscal Eletrônica (44 dígitos)'
    )
    numero_nfe = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Número da NFe'
    )
    arquivo_nfe = models.FileField(
        upload_to='nfe_arquivos/',
        blank=True,
        null=True,
        verbose_name='Arquivo NFe/XML'
    )
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Fornecedor'
    )
    observacao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observação'
    )
    operacao_campo = models.ForeignKey(
        'OperacaoCampo',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='movimentacoes',
        verbose_name='Operação de Campo'
    )
    item_pedido = models.ForeignKey(
        ItemPedidoCompra,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes',
        verbose_name='Item do Pedido de Compra'
    )
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Cliente'
    )
    item_contrato = models.ForeignKey(
        'ItemContratoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes',
        verbose_name='Item do Contrato de Venda'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Cadastro'
    )

    class Meta:
        db_table = 'movimentacoes_estoque'
        verbose_name = 'Movimentação de Estoque'
        verbose_name_plural = 'Movimentações de Estoque'
        ordering = ['-data_movimentacao']

    def __str__(self):
        return f"{self.tipo} - {self.produto.nome} ({self.quantidade})"

    @property
    def valor_total(self):
        """Calcula o valor total da movimentação."""
        return self.quantidade * self.valor_unitario

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Atualizar estoque do produto após salvar
        self.produto.atualizar_estoque()
        
        # Se estiver vinculada a um item de pedido, atualizar o status do item
        if self.item_pedido:
            self.item_pedido.update_status()
        
        if self.item_contrato:
            self.item_contrato.update_status()


class StatusCiclo(models.TextChoices):
    """Status possíveis de um ciclo de produção."""
    PLANEJAMENTO = 'PLANEJAMENTO', 'Em Planejamento'
    EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em Andamento'
    CONCLUIDO = 'CONCLUIDO', 'Concluído'
    CANCELADO = 'CANCELADO', 'Cancelado'


class Plantio(TenantAwareModel):
    """
    Representa o plantio de uma cultura em um talhão durante uma safra.
    Antigo CicloProducao.
    """
    safra = models.ForeignKey(
        Safra,
        on_delete=models.CASCADE,
        related_name='plantios',
        verbose_name='Safra',
        null=True # Nullable for migration
    )
    talhoes = models.ManyToManyField(
        Talhao,
        related_name='plantios_multi',
        verbose_name='Talhões',
        blank=True
    )
    cultura = models.CharField(
        max_length=100,
        verbose_name='Cultura',
        help_text='Ex: Soja, Milho, Trigo'
    )
    data_plantio = models.DateField(
        verbose_name='Data de Plantio'
    )
    data_colheita_prevista = models.DateField(
        blank=True,
        null=True,
        verbose_name='Previsão de Colheita'
    )
    data_fim = models.DateField(
        blank=True,
        null=True,
        verbose_name='Data de Término'
    )
    status = models.CharField(
        max_length=20,
        choices=StatusCiclo.choices,
        default=StatusCiclo.PLANEJAMENTO,
        verbose_name='Status'
    )
    producao_estimada_sc_ha = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Produção Estimada (sc/ha)'
    )
    producao_real_saca = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        blank=True,
        null=True,
        verbose_name='Produção Real (sc)'
    )
    preco_venda_estimado_sc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Preço de Venda Estimado (R$/sc)'
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Cadastro'
    )

    class Meta:
        db_table = 'plantios'
        verbose_name = 'Plantio'
        verbose_name_plural = 'Plantios'
        ordering = ['-data_plantio']

    @property
    def nome_safra(self):
        """Retorna o nome da safra ou valor padrão."""
        return self.safra.nome if self.safra else "S/ Safra"

    def __str__(self):
        safra_nome = self.nome_safra
        talhao_nomes = ", ".join([t.nome for t in self.talhoes.all()[:3]])
        if self.talhoes.count() > 3:
            talhao_nomes += "..."
        return f"{safra_nome} - {self.cultura} ({talhao_nomes})"

    @property
    def area_total_ha(self):
        """Soma das áreas de todos os talhões vinculados."""
        return self.talhoes.aggregate(total=Sum('area_hectares'))['total'] or Decimal('0.0000')

    @property
    def producao_total_estimada_sc(self):
        """Cálculo automático: Área Total x Prod. sc/ha."""
        return self.area_total_ha * self.producao_estimada_sc_ha

    def calcular_custo_total(self):
        """Soma o custo de todas as operações vinculadas a este ciclo."""
        custo_total = Decimal('0.00')
        for operacao in self.operacoes.all():
            custo_total += operacao.custo_total
        return custo_total

    def calcular_receita_estimada(self):
        """Calcula a receita estimada com base na produção total e preço estimado."""
        return self.producao_total_estimada_sc * self.preco_venda_estimado_sc

    def calcular_receita_real(self):
        """Calcula a receita real (se houver produção real registrada)."""
        if self.producao_real_saca:
            return self.producao_real_saca * self.preco_venda_estimado_sc
        return Decimal('0.00')

    def calcular_lucro_estimado(self):
        """Lucro Estimado = Receita Estimada - Custo Total."""
        return self.calcular_receita_estimada() - self.calcular_custo_total()

    def calcular_lucro_real(self):
        """Lucro Real = Receita Real - Custo Total."""
        return self.calcular_receita_real() - self.calcular_custo_total()

    def calcular_roi(self):
        """
        ROI = (Lucro / Custo) * 100
        Retorna percentual.
        """
        custo = self.calcular_custo_total()
        if custo > 0:
            lucro = self.calcular_lucro_estimado()
            return (lucro / custo) * 100
        return Decimal('0.00')


class TipoOperacao(models.TextChoices):
    """Tipos de operações de campo."""
    PLANTIO = 'PLANTIO', 'Plantio'
    ADUBACAO = 'ADUBACAO', 'Adubação'
    PULVERIZACAO = 'PULVERIZACAO', 'Pulverização'
    COLHEITA = 'COLHEITA', 'Colheita'
    IRRIGACAO = 'IRRIGACAO', 'Irrigação'
    PREPARO_SOLO = 'PREPARO_SOLO', 'Preparo do Solo'
    OUTROS = 'OUTROS', 'Outros'


class AtividadeCampo(TenantAwareModel):
    """Modelo para as atividades que podem ser realizadas em uma operação."""
    nome = models.CharField(max_length=100, verbose_name='Nome da Atividade')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        db_table = 'atividades_campo'
        verbose_name = 'Atividade de Campo'
        verbose_name_plural = 'Atividades de Campo'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CategoriaOperacao(models.TextChoices):
    INSUMO = 'INSUMO', 'Insumo/Produto'
    MAO_DE_OBRA = 'MAO_DE_OBRA', 'Mão de Obra'
    SERVICO = 'SERVICO', 'Serviço'

class UnidadeCusto(models.TextChoices):
    BRL = 'BRL', 'Reais (R$)'
    SACA = 'SACA', 'Sacas'

class StatusRequisicao(models.TextChoices):
    PENDENTE = 'PENDENTE', 'Pendente'
    APROVADO = 'APROVADO', 'Aprovado/Realizado'
    CANCELADO = 'CANCELADO', 'Cancelado'

class OperacaoCampo(TenantAwareModel):
    """
    Modelo para registrar operações realizadas no campo.
    Agora suporta múltiplos talhões e múltiplos itens detalhados.
    """
    safra = models.ForeignKey(
        Safra,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operacoes',
        verbose_name='Safra'
    )
    ciclo = models.ForeignKey(
        Plantio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operacoes',
        verbose_name='Ciclo de Produção'
    )
    talhoes = models.ManyToManyField(
        Talhao,
        related_name='operacoes_campo',
        verbose_name='Talhões',
        blank=True
    )
    data_operacao = models.DateField(default=timezone.now, verbose_name='Data da Operação')
    area_aplicada_ha = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, blank=True,
        verbose_name='Área Aplicada (ha)'
    )
    responsavel = models.CharField(max_length=100, blank=True, null=True, verbose_name='Responsável')
    status = models.CharField(
        max_length=20,
        choices=StatusRequisicao.choices,
        default=StatusRequisicao.APROVADO,
        verbose_name='Status da Requisição'
    )
    observacao = models.TextField(blank=True, null=True, verbose_name='Observação')
    
    # Auditoria
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name='Data de Cadastro')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'operacoes_campo'
        verbose_name = 'Operação de Campo'
        verbose_name_plural = 'Operações de Campo'
        ordering = ['-data_operacao']

    def __str__(self):
        safra_nome = self.safra.nome if self.safra else (self.ciclo.safra.nome if self.ciclo else '-')
        data_str = self.data_operacao.strftime('%d/%m/%Y')
        itens = self.itens.all()
        if itens.exists():
            atividades = ", ".join([i.atividade.nome for i in itens[:3]])
            if itens.count() > 3: atividades += "..."
            return f"{atividades} - {safra_nome} ({data_str})"
        return f"Operação {self.pk} - {safra_nome} ({data_str})"

    @property
    def custo_total(self):
        return sum(item.custo_final for item in self.itens.all())

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Se aprovado, processar estoque (se ainda não processou)
        # Lógica movida para método explícito ou signal, mas podemos chamar aqui se status mudou.
        # Por simplificação, o view chama processurar_estoque()

    def processar_estoque(self):
        """Gera movimentações de saída para os itens desta operação."""
        from .models import MovimentacaoEstoque, TipoMovimentacao
        
        for item in self.itens.all():
            if item.produto:
                # Verificar se já existe mov vinculada a este item (futuro: Linkar Item -> Mov)
                # Por enquanto, verificamos se existe mov para esta operação e produto com mesmo valor/qtd
                # Mas como agora é 1:N, ideal é linkar Operacao + Item.
                # Simplificação: Criar sempre que chamar, quem chama garante idempotência ou status.
                
                MovimentacaoEstoque.objects.create(
                    empresa=self.empresa,
                    produto=item.produto,
                    tipo=TipoMovimentacao.SAIDA,
                    quantidade=item.quantidade,
                    data_movimentacao=self.data_operacao,
                    operacao_campo=self, # Vínculo antigo ainda útil para rastreio geral
                    observacao=f"Ref. Operação #{self.id} - {item.atividade.nome}"
                )

class OperacaoCampoItem(TenantAwareModel):
    """Item detalhado de uma operação de campo."""
    operacao = models.ForeignKey(
        OperacaoCampo, 
        on_delete=models.CASCADE, 
        related_name='itens',
        verbose_name='Operação'
    )
    atividade = models.ForeignKey(
        AtividadeCampo, 
        on_delete=models.PROTECT, 
        related_name='itens',
        verbose_name='Atividade/Tipo'
    )
    categoria = models.CharField(
        max_length=20, 
        choices=CategoriaOperacao.choices, 
        default=CategoriaOperacao.INSUMO,
        verbose_name='Categoria'
    )
    maquinario_terceiro = models.BooleanField(default=False, verbose_name='Maquinário de Terceiro')
    
    produto = models.ForeignKey(
        'Produto', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='itens_operacao',
        verbose_name='Produto/Insumo'
    )
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name='Descrição/Serviço')
    
    # Quantidade
    quantidade = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='Quantidade')
    is_quantidade_total = models.BooleanField(default=False, verbose_name='Qtd é Total?', help_text="Se desmarcado, considera Qtd/ha")
    
    # Custo
    custo_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='Custo Unitário')
    is_custo_total = models.BooleanField(default=False, verbose_name='Custo é Total?', help_text="Se desmarcado, considera Custo/ha")
    unidade_custo = models.CharField(
        max_length=10,
        choices=UnidadeCusto.choices,
        default=UnidadeCusto.BRL,
        verbose_name='Unidade'
    )
    
    # Calculado no save
    custo_final = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Custo Final')

    def save(self, *args, **kwargs):
        from decimal import Decimal
        # Cálculo do Custo Final
        area = Decimal('1.0')
        if self.operacao and self.operacao.area_aplicada_ha:
             area = self.operacao.area_aplicada_ha

        if self.is_custo_total:
            self.custo_final = self.custo_unitario
        else:
            self.custo_final = self.custo_unitario * area
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.atividade.nome if self.atividade else 'Sem Atividade'} - {self.get_categoria_display()}"

    class Meta:
        verbose_name = 'Item de Operação'
        verbose_name_plural = 'Itens de Operação'

class ConfiguracaoSistema(models.Model):
    """
    Configurações globais de branding e comportamento do sistema (Master Only).
    """
    nome_sistema = models.CharField(max_length=100, default='Agro Gestor PV', verbose_name='Nome do Sistema')
    logo = models.ImageField(upload_to='logos/', blank=True, null=True, verbose_name='Logo do Sistema')
    cor_primaria = models.CharField(max_length=20, default='#212529', verbose_name='Cor Primária (Hex)')
    mensagem_dashboard = models.TextField(blank=True, null=True, verbose_name='Mensagem de Boas-vindas (Dashboard)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuracao_sistema'
        verbose_name = 'Configuração do Sistema'
        verbose_name_plural = 'Configurações do Sistema'

    def __str__(self):
        return self.nome_sistema

    @classmethod
    def get_config(cls):
        """Retorna a configuração ativa (primeiro registro)."""
        config, _ = cls.objects.get_or_create(id=1)
        return config


# Sinais para garantir a atualização do estoque ao deletar movimentações
from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=MovimentacaoEstoque)
def atualizar_estoque_ao_deletar(sender, instance, **kwargs):
    instance.produto.atualizar_estoque()


class FonteDadosClimaticos(models.TextChoices):
    API = 'API', 'Automático (API)'
    MANUAL = 'MANUAL', 'Manual'


class ClimaFazenda(TenantAwareModel):
    """
    Histórico climático diário de uma fazenda.
    Armazena dados de temperatura, chuva, vento e umidade.
    Pode ser alimentado via API (Open-Meteo) ou entrada manual.
    """
    fazenda = models.ForeignKey(
        Fazenda,
        on_delete=models.CASCADE,
        related_name='dados_climaticos',
        verbose_name='Fazenda'
    )
    data = models.DateField(
        verbose_name='Data'
    )
    temp_max = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Temp. Máxima (°C)'
    )
    temp_min = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Temp. Mínima (°C)'
    )
    precipitacao = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name='Precipitação (mm)'
    )
    umidade_relativa = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Umidade Relativa (%)'
    )
    velocidade_vento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Velocidade Vento (km/h)'
    )
    fonte = models.CharField(
        max_length=20,
        choices=FonteDadosClimaticos.choices,
        default=FonteDadosClimaticos.API,
        verbose_name='Fonte dos Dados'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clima_fazenda'
        verbose_name = 'Dado Climático'
        verbose_name_plural = 'Dados Climáticos'
        ordering = ['-data']
        unique_together = ['fazenda', 'data']

    def __str__(self):
        return f"{self.fazenda.nome} - {self.data} ({self.precipitacao}mm)"


class TabelaClassificacao(TenantAwareModel):
    """
    Tabela para definir regras de desconto por classificação (Umidade/Impureza).
    """
    nome = models.CharField(max_length=100, verbose_name='Nome da Tabela')
    cultura = models.CharField(max_length=50, verbose_name='Cultura')
    padrao_umidade = models.DecimalField(max_digits=5, decimal_places=2, default=14.00, verbose_name='Padrão Umidade (%)')
    padrao_impureza = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name='Padrão Impureza (%)')
    padrao_avariado = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='Padrão Avariado (%)')
    taxa_secagem = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='Taxa Secagem Extra (%)')

    class Meta:
        db_table = 'tabelas_classificacao'
        verbose_name = 'Tabela de Classificação'
        verbose_name_plural = 'Tabelas de Classificação'

    def __str__(self):
        return f"{self.nome} - {self.cultura}"


class Romaneio(TenantAwareModel):
    """
    Registro de entrada de grãos (Ticket de Pesagem).
    """
    data = models.DateField(verbose_name='Data')
    numero_ticket = models.CharField(max_length=50, verbose_name='Nº Ticket/Romaneio')
    fazenda = models.ForeignKey(Fazenda, on_delete=models.CASCADE, verbose_name='Fazenda')
    talhao = models.ForeignKey(Talhao, on_delete=models.CASCADE, verbose_name='Talhão')
    plantio = models.ForeignKey(Plantio, on_delete=models.CASCADE, verbose_name='Plantio/Safra', null=True)
    motorista = models.CharField(max_length=100, blank=True, null=True, verbose_name='Motorista')
    placa = models.CharField(max_length=20, blank=True, null=True, verbose_name='Placa')
    
    peso_tara = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Peso Tara (kg)')
    peso_bruto = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Peso Bruto (kg)')
    
    umidade_percentual = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Umidade (%)')
    impureza_percentual = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Impureza (%)')
    avariado_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Avariado (%)')

    # Descontos calculados (em kg)
    desconto_kg_umidade = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Desc. Umidade (kg)')
    desconto_kg_impureza = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Desc. Impureza (kg)')
    desconto_kg_avariado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Desc. Avariado (kg)')
    total_descontos_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total Descontos (kg)')

    # Campos de Armazenagem
    armazem_terceiro = models.ForeignKey('TaxaArmazem', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Armazém (Terceiro)')
    peso_quebra_tecnica = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Quebra Técnica (kg)')
    
    peso_liquido = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Peso Líquido/Armazém (kg)', blank=True, null=True)
    
    class Meta:
        db_table = 'romaneios'
        verbose_name = 'Romaneio'
        verbose_name_plural = 'Romaneios'
        ordering = ['-data']

    @property
    def peso_carga(self):
        """Peso Bruto - Tara."""
        return (self.peso_bruto or Decimal('0')) - (self.peso_tara or Decimal('0'))

    @property
    def peso_descontos(self):
        """Soma dos descontos de umidade e impureza (antes da quebra)."""
        if self.peso_liquido is None:
            return Decimal('0')
        return self.peso_carga - (self.peso_liquido + self.peso_quebra_tecnica)

    def __str__(self):
        return f"Romaneio {self.numero_ticket} - {self.peso_liquido}kg"

    def save(self, *args, **kwargs):
        # Garantir que valores sejam Decimal para cálculos
        peso_bruto = Decimal(str(self.peso_bruto or 0))
        peso_tara = Decimal(str(self.peso_tara or 0))
        umidade = Decimal(str(self.umidade_percentual or 0))
        impureza = Decimal(str(self.impureza_percentual or 0))
        avariado = Decimal(str(self.avariado_percentual or 0))

        # Lógica de Peso Líquido
        peso_carga = peso_bruto - peso_tara
        desconto_umidade = Decimal('0.00')
        desconto_impureza = Decimal('0.00')
        desconto_avariado = Decimal('0.00')
        quebra_tec = Decimal('0.00')
        
        # Valores padrão
        padrao_umid = Decimal('14.00')
        padrao_imp = Decimal('1.00')
        padrao_avar = Decimal('0.00')
        taxa_sec = Decimal('0.00')

        # Buscar parâmetros na Tabela de Classificação
        if self.plantio:
            tabela = TabelaClassificacao.objects.filter(
                empresa=self.empresa, 
                cultura__iexact=self.plantio.cultura
            ).first()
            
            if tabela:
                padrao_umid = tabela.padrao_umidade
                padrao_imp = tabela.padrao_impureza
                padrao_avar = tabela.padrao_avariado
                taxa_sec = tabela.taxa_secagem

        # Cálculo Desconto Umidade
        if umidade > padrao_umid:
            excesso = umidade - padrao_umid
            desc_peso = peso_carga * (excesso / Decimal('100'))
            desc_taxa = peso_carga * (taxa_sec / Decimal('100'))
            desconto_umidade = desc_peso + desc_taxa
            
        # Cálculo Desconto Impureza
        if impureza > padrao_imp:
             excesso_imp = impureza - padrao_imp
             desconto_impureza = peso_carga * (excesso_imp / Decimal('100'))

        # Cálculo Desconto Avariado
        if avariado > padrao_avar:
             excesso_av = avariado - padrao_avar
             desconto_avariado = peso_carga * (excesso_av / Decimal('100'))

        # Salvar valores individuais em kg (Priorizar input manual se houver, senão usa calculado)
        if not self.desconto_kg_umidade or self.desconto_kg_umidade == 0:
            self.desconto_kg_umidade = desconto_umidade
        
        if not self.desconto_kg_impureza or self.desconto_kg_impureza == 0:
             self.desconto_kg_impureza = desconto_impureza
        
        if not self.desconto_kg_avariado or self.desconto_kg_avariado == 0:
             self.desconto_kg_avariado = desconto_avariado

        self.total_descontos_kg = self.desconto_kg_umidade + self.desconto_kg_impureza + self.desconto_kg_avariado

        # Peso após descontos de classificação
        peso_pos_classificacao = peso_carga - self.total_descontos_kg

        # Cálculo Quebra Técnica (Se houver armazém terceiro vinculado)
        if self.armazem_terceiro:
             indice_quebra = Decimal(str(self.armazem_terceiro.quebra_tecnica or 0))
             quebra_tec = peso_pos_classificacao * (indice_quebra / Decimal('100'))
             self.peso_quebra_tecnica = quebra_tec
        else:
             self.peso_quebra_tecnica = 0

        self.peso_liquido = peso_pos_classificacao - quebra_tec
        super().save(*args, **kwargs)


class ContratoVenda(TenantAwareModel):
    """
    Contrato de Venda de Grãos (Futuro ou Spot).
    """
    TIPO_VENDA_CHOICES = [
        ('FUTURO', 'Mercado Futuro'),
        ('SPOT', 'Mercado Spot (Disponível)'),
    ]
    
    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        verbose_name='Cliente/Comprador',
        null=True, 
        blank=True
    )
    tipo = models.CharField(max_length=20, choices=TIPO_VENDA_CHOICES, default='SPOT', verbose_name='Tipo de Venda')
    
    data_entrega = models.DateField(verbose_name='Data Entrega/Vencimento')
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'contratos_venda'
        verbose_name = 'Contrato de Venda'
        verbose_name_plural = 'Contratos de Venda'
    
    def __str__(self):
        return f"Contrato {self.id} - {self.cliente}"

    @property
    def total_fixado(self):
        """Retorna o valor total já fixado (soma das fixações dos itens)."""
        return sum(item.total_fixado for item in self.itens.all())

    @property
    def valor_total_contrato(self):
        """Soma do valor total de todos os itens."""
        return sum(item.valor_total for item in self.itens.all())

    @property
    def quantidade_sacas(self):
        """Retorna a quantidade total (soma dos itens) para retrocompatibilidade."""
        return sum(item.quantidade for item in self.itens.all())

    @property
    def valor_total_fixado(self):
        """Retorna o VALOR financeiro total já fixado."""
        return self.fixacoes.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')


class ItemContratoVenda(models.Model):
    """
    Itens (Produtos) de um Contrato de Venda.
    """
    contrato = models.ForeignKey(ContratoVenda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, verbose_name='Produto')
    fazenda = models.ForeignKey(Fazenda, on_delete=models.SET_NULL, verbose_name='Fazenda (Opcional)', null=True, blank=True, help_text="Informe se este item sair de uma fazenda específica.")
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Quantidade')
    unidade = models.CharField(
        max_length=5, 
        choices=[
            ('SC', 'Sacas (60kg)'), 
            ('SC50', 'Sacas (50kg)'),
            ('SC40', 'Sacas (40kg)'),
            ('SC25', 'Sacas (25kg)'),
            ('KG', 'Quilogramas (Granel)'), 
            ('TON', 'Toneladas (Granel)')
        ], 
        default='SC', 
        verbose_name='Unidade'
    )
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Unitário (R$)')
    
    class Meta:
        db_table = 'itens_contrato_venda'
        verbose_name = 'Item do Contrato'
        verbose_name_plural = 'Itens do Contrato'

    @property
    def valor_total(self):
        return self.quantidade * self.valor_unitario

    def __str__(self):
        return f"{self.produto.nome} ({self.quantidade} {self.unidade})"

    @property
    def total_fixado(self):
        return self.fixacoes.aggregate(total=Sum('quantidade'))['total'] or Decimal('0.00')

    @property
    def quantidade_entregue(self):
        """Soma das movimentações de SAIDA vinculadas a este item."""
        return self.movimentacoes.aggregate(
            total=Coalesce(Sum('quantidade'), Decimal('0'))
        )['total']

    @property
    def saldo_restante(self):
        return self.quantidade - self.quantidade_entregue

    def update_status(self):
        """Atualiza status do item (e futuramente do contrato)."""
        # Por enquanto apenas para rastro. Podemos adicionar campo 'status' se necessário.
        pass

    @property
    def saldo_a_fixar(self):
        return self.quantidade - self.total_fixado


class Cotacao(models.Model):
    """
    Cotações diárias de commodities.
    """
    data = models.DateField(verbose_name='Data')
    produto = models.CharField(max_length=50, verbose_name='Produto (Soja/Milho)')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor (R$)')
    fonte = models.CharField(max_length=100, verbose_name='Fonte', blank=True, null=True)
    
    class Meta:
        db_table = 'cotacoes'
        verbose_name = 'Cotação'
        verbose_name_plural = 'Cotações'
        unique_together = ['data', 'produto']
        ordering = ['-data']

    def __str__(self):
        return f"{self.produto} - {self.data}: R$ {self.valor}"


class RateioCusto(TenantAwareModel):
    """
    Rateio de custos indiretos entre talhões.
    """
    CRITERIO_CHOICES = [
        ('AREA', 'Proporcional à Área (ha)'),
        ('IGUAL', 'Divisão Igualitária entre Talhões'),
    ]
    
    data = models.DateField(verbose_name='Data do Rateio')
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor Total a Ratear')
    descricao = models.CharField(max_length=200, verbose_name='Descrição do Custo (Ex: Energia, Adm)')
    safra = models.ForeignKey(Safra, on_delete=models.CASCADE, verbose_name='Safra de Referência', null=True)
    criterio = models.CharField(max_length=20, choices=CRITERIO_CHOICES, default='AREA', verbose_name='Critério de Rateio')
    
    class Meta:
        db_table = 'rateios_custo'
        verbose_name = 'Rateio de Custo'
        verbose_name_plural = 'Rateios de Custo'

    def __str__(self):
        return f"Rateio {self.descricao} - {self.data}"

    def distribuir_custos(self):
        """
        Gera OperacoesCampo para cada Plantio da Safra baseado no critério.
        Retorna o número de operações geradas.
        """
        plantios = self.safra.plantios.filter(status__in=[StatusCiclo.EM_ANDAMENTO, StatusCiclo.CONCLUIDO])
        
        if not plantios.exists():
            return 0
            
        total_operacoes = 0
        
        if self.criterio == 'AREA':
            # Soma total de hectares dos plantios ativos
            area_total = sum(p.talhao.area_hectares for p in plantios)
            if area_total <= 0: return 0
            
            for p in plantios:
                area_talhao = p.talhao.area_hectares
                fator = area_talhao / area_total
                valor_parcela = self.valor_total * fator
                
                self._criar_operacao(p, valor_parcela, f"Rateio (Área): {self.descricao}")
                total_operacoes += 1
                
        elif self.criterio == 'IGUAL':
            qtd = plantios.count()
            valor_parcela = self.valor_total / Decimal(qtd)
            
            for p in plantios:
                self._criar_operacao(p, valor_parcela, f"Rateio (Igual): {self.descricao}")
                total_operacoes += 1
                
        return total_operacoes
        
    def _criar_operacao(self, plantio, valor, desc):
        """Helper para criar a operação de campo."""
        OperacaoCampo.objects.create(
            empresa=self.empresa,
            talhao=plantio.talhao,
            ciclo=plantio,
            categoria=CategoriaOperacao.SERVICO,
            tipo_operacao=TipoOperacao.OUTROS,
            descricao=desc,
            data_operacao=self.data,
            custo_operacao=valor,
            unidade_custo=UnidadeCusto.BRL,
            observacao=f"Gerado automaticamente pelo Rateio #{self.id}"
        )


class Fixacao(TenantAwareModel):
    """
    Fixação de Preço: Vincula um Romaneio (físico) a um Contrato de Venda (Financeiro).
    Representa a efetivação da venda de um lote de grãos.
    """
    data_fixacao = models.DateField(verbose_name='Data da Fixação')
    contrato = models.ForeignKey(ContratoVenda, on_delete=models.CASCADE, related_name='fixacoes', verbose_name='Contrato')
    item = models.ForeignKey(ItemContratoVenda, on_delete=models.CASCADE, related_name='fixacoes', verbose_name='Item do Contrato', null=True)
    romaneio = models.ForeignKey(Romaneio, on_delete=models.CASCADE, related_name='fixacoes', verbose_name='Romaneio')
    
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Quantidade Fixada')
    preco = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Preço na Fixação (R$)')
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor Total (R$)', editable=False)
    
    observacoes = models.TextField(blank=True, null=True, verbose_name='Observações')

    class Meta:
        db_table = 'fixacoes'
        verbose_name = 'Fixação de Preço'
        verbose_name_plural = 'Fixações'

    def clean(self):
        super().clean()
        if self.item and self.contrato:
            if self.item.contrato != self.contrato:
                raise ValidationError({'item': 'O item selecionado não pertence ao contrato informado.'})

    def __str__(self):
        return f"Fixação #{self.id} - {self.quantidade_sacas}sc ({self.contrato.cliente})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.valor_total = self.quantidade * self.preco
        super().save(*args, **kwargs)
        
        # --- INTEGRAÇÃO FINANCEIRA ---
        if is_new:
            # Importação atrasada de modelos financeiros para evitar circularidade
            from core.models import ContaReceber, CategoriaFinanceira, StatusFinanceiro
            
            # Buscar categoria padrão de Entrada
            categoria = CategoriaFinanceira.objects.filter(empresa=self.empresa, tipo='ENTRADA', ativo=True).first()
            if not categoria:
                categoria = CategoriaFinanceira.objects.create(
                    empresa=self.empresa,
                    nome='Venda de Grãos',
                    tipo='ENTRADA'
                )

            ContaReceber.objects.create(
                empresa=self.empresa,
                descricao=f"Fixação #{self.id} - Contrato {self.contrato.id} ({self.quantidade} {self.item.unidade if self.item else 'SC'})",
                cliente=self.contrato.cliente,
                categoria=categoria,
                valor_total=self.valor_total,
                data_vencimento=self.data_fixacao, # Vencimento inicial = data fixação
                fixacao_origem=self,
                contrato_origem=self.contrato,
                status=StatusFinanceiro.PENDENTE,
                observacao=f"Gerado via fixação de preço no contrato {self.contrato.id}."
            )


class FrequenciaTaxa(models.TextChoices):
    SEMANAL = 'SEMANAL', 'Semanal'
    QUINZENAL = 'QUINZENAL', 'Quinzenal'
    MENSAL = 'MENSAL', 'Mensal'

class TipoPagamento(models.TextChoices):
    BRL = 'BRL', 'Reais (R$)'
    SACA = 'SACA', 'Saca'


class TaxaArmazem(TenantAwareModel):
    """
    Configuração de taxas cobradas por armazéns terceiros.
    """
    fornecedor = models.ForeignKey(
        Fornecedor, 
        on_delete=models.CASCADE, 
        verbose_name='Armazém/Fornecedor',
        null=True, 
        blank=True
    )
    taxa_recepcao = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Taxa Recepção (R$/Ton)')
    taxa_armazenagem = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Taxa de Armazenagem')
    
    frequencia = models.CharField(
        max_length=20,
        choices=FrequenciaTaxa.choices,
        default=FrequenciaTaxa.QUINZENAL,
        verbose_name='Frequência'
    )
    
    unidade = models.CharField(
        max_length=20,
        choices=TipoPagamento.choices,
        default=TipoPagamento.BRL,
        verbose_name='Unidade de Pagamento'
    )
    
    quebra_tecnica = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Quebra Técnica (%)')
    
    class Meta:
        db_table = 'taxas_armazem'
        verbose_name = 'Taxa de Armazém'
        verbose_name_plural = 'Taxas de Armazém'
        unique_together = ['empresa', 'fornecedor']

    def __str__(self):
        return f"{self.fornecedor} (Rec: {self.taxa_recepcao}, Arm: {self.taxa_armazenagem}/{self.get_frequencia_display()})"


class CategoriaFinanceira(TenantAwareModel):
    """
    Categorização para Contas a Pagar e Receber (Plano de Contas).
    """
    nome = models.CharField(max_length=100, verbose_name='Nome da Categoria')
    tipo = models.CharField(
        max_length=10,
        choices=[('ENTRADA', 'Entrada/Receita'), ('SAIDA', 'Saída/Despesa')],
        verbose_name='Tipo'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')

    class Meta:
        db_table = 'categorias_financeiras'
        verbose_name = 'Categoria Financeira'
        verbose_name_plural = 'Categorias Financeiras'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class StatusFinanceiro(models.TextChoices):
    PENDENTE = 'PENDENTE', 'Pendente'
    PARCIAL = 'PARCIAL', 'Pago Parcial'
    PAGO = 'PAGO', 'Pago/Liquidado'
    CANCELADO = 'CANCELADO', 'Cancelado'


class ContaPagar(TenantAwareModel):
    """
    Registro de obrigações financeiras.
    """
    descricao = models.CharField(max_length=200, verbose_name='Descrição')
    fornecedor = models.ForeignKey(
        Fornecedor, 
        on_delete=models.PROTECT, 
        related_name='contas_pagar',
        verbose_name='Fornecedor',
        null=True,
        blank=True
    )
    categoria = models.ForeignKey(
        CategoriaFinanceira,
        on_delete=models.PROTECT,
        verbose_name='Categoria/Plano de Contas',
        limit_choices_to={'tipo': 'SAIDA'},
        null=True,
        blank=True
    )
    fazenda = models.ForeignKey(
        Fazenda,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Fazenda Relacionada'
    )
    data_vencimento = models.DateField(verbose_name='Data de Vencimento')
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor Total')
    status = models.CharField(
        max_length=20,
        choices=StatusFinanceiro.choices,
        default=StatusFinanceiro.PENDENTE,
        verbose_name='Status'
    )
    observacao = models.TextField(blank=True, null=True, verbose_name='Observação')
    
    arquivo = models.FileField(upload_to='financeiro/pagar/', blank=True, null=True, verbose_name='Anexo (Boleto/NF)')
    
    # Rastreabilidade
    numero_nfe = models.CharField(max_length=50, blank=True, null=True, verbose_name='Nº NFe')
    movimentacao_origem = models.ForeignKey(
        'MovimentacaoEstoque', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='contas_pagar',
        verbose_name='Movimentação de Origem'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contas_pagar'
        verbose_name = 'Conta a Pagar'
        verbose_name_plural = 'Contas a Pagar'
        ordering = ['data_vencimento']

    def __str__(self):
        return f"{self.descricao} - {self.valor_total} ({self.data_vencimento})"

    @property
    def valor_pago(self):
        return self.baixas.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    @property
    def saldo_devedor(self):
        return self.valor_total - self.valor_pago


class ContaReceber(TenantAwareModel):
    """
    Registro de direitos financeiros (recebíveis).
    """
    descricao = models.CharField(max_length=200, verbose_name='Descrição')
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='contas_receber',
        verbose_name='Cliente',
        null=True,
        blank=True
    )
    categoria = models.ForeignKey(
        CategoriaFinanceira,
        on_delete=models.PROTECT,
        verbose_name='Categoria/Plano de Contas',
        limit_choices_to={'tipo': 'ENTRADA'},
        null=True,
        blank=True
    )
    fazenda = models.ForeignKey(
        Fazenda,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Fazenda Relacionada'
    )
    data_vencimento = models.DateField(verbose_name='Data de Vencimento')
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor Total')
    status = models.CharField(
        max_length=20,
        choices=StatusFinanceiro.choices,
        default=StatusFinanceiro.PENDENTE,
        verbose_name='Status'
    )
    observacao = models.TextField(blank=True, null=True, verbose_name='Observação')
    
    # Rastreabilidade
    fixacao_origem = models.ForeignKey(
        'Fixacao',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contas_receber',
        verbose_name='Fixação de Origem'
    )
    contrato_origem = models.ForeignKey(
        'ContratoVenda',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contas_receber',
        verbose_name='Contrato de Origem'
    )
    numero_nfe = models.CharField(max_length=50, blank=True, null=True, verbose_name='Nº NFe/Doc')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contas_receber'
        verbose_name = 'Conta a Receber'
        verbose_name_plural = 'Contas a Receber'
        ordering = ['data_vencimento']

    def __str__(self):
        return f"{self.descricao} - {self.valor_total} ({self.data_vencimento})"

    @property
    def valor_recebido(self):
        return self.baixas.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    @property
    def saldo_restante(self):
        return self.valor_total - self.valor_recebido


class MetodoPagamento(models.TextChoices):
    BOLETO = 'BOLETO', 'Boleto'
    PIX = 'PIX', 'PIX'
    TRANSFERENCIA = 'TRANSFERENCIA', 'Transferência/TED'
    DINHEIRO = 'DINHEIRO', 'Dinheiro'
    CARTAO = 'CARTAO', 'Cartão'
    CHEQUE = 'CHEQUE', 'Cheque'
    OUTROS = 'OUTROS', 'Outros'


class BaixaContaPagar(TenantAwareModel):
    """
    Registro de pagamentos efetuados.
    """
    conta = models.ForeignKey(ContaPagar, on_delete=models.CASCADE, related_name='baixas')
    data_pagamento = models.DateField(verbose_name='Data do Pagamento')
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor Pago')
    metodo = models.CharField(
        max_length=20, 
        choices=MetodoPagamento.choices, 
        default=MetodoPagamento.TRANSFERENCIA,
        verbose_name='Método de Pagamento'
    )
    comprovante = models.FileField(upload_to='financeiro/comprovantes/', blank=True, null=True, verbose_name='Comprovante')
    observacao = models.TextField(blank=True, null=True, verbose_name='Observação')

    class Meta:
        db_table = 'baixas_contas_pagar'
        verbose_name = 'Baixa de Conta a Pagar'
        verbose_name_plural = 'Baixas de Contas a Pagar'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Atualizar status da conta pai
        conta = self.conta
        total_pago = conta.valor_pago
        if total_pago >= conta.valor_total:
            conta.status = StatusFinanceiro.PAGO
        elif total_pago > 0:
            conta.status = StatusFinanceiro.PARCIAL
        conta.save()


class BaixaContaReceber(TenantAwareModel):
    """
    Registro de recebimentos efetuados.
    """
    conta = models.ForeignKey(ContaReceber, on_delete=models.CASCADE, related_name='baixas')
    data_recebimento = models.DateField(verbose_name='Data do Recebimento')
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor Recebido')
    metodo = models.CharField(
        max_length=20, 
        choices=MetodoPagamento.choices, 
        default=MetodoPagamento.TRANSFERENCIA,
        verbose_name='Método de Recebimento'
    )
    observacao = models.TextField(blank=True, null=True, verbose_name='Observação')

    class Meta:
        db_table = 'baixas_contas_receber'
        verbose_name = 'Baixa de Conta a Receber'
        verbose_name_plural = 'Baixas de Contas a Receber'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Atualizar status da conta pai
        conta = self.conta
        total_recebido = conta.valor_recebido
        if total_recebido >= conta.valor_total:
            conta.status = StatusFinanceiro.PAGO
        elif total_recebido > 0:
            conta.status = StatusFinanceiro.PARCIAL
        conta.save()
class TipoAlvo(models.TextChoices):
    PRAGA = 'PRAGA', 'Praga'
    DOENCA = 'DOENCA', 'Doenca'
    DANINHA = 'DANINHA', 'Planta Daninha'


class TipoAlvo(models.TextChoices):
    PRAGA = 'PRAGA', 'Praga'
    DOENCA = 'DOENCA', 'Doença'
    DANINHA = 'DANINHA', 'Planta Daninha'

class AlvoMonitoramento(TenantAwareModel):
    """
    Catálogo de pragas, doenças ou plantas daninhas.
    """
    nome = models.CharField(max_length=100, verbose_name='Nome do Alvo')
    tipo = models.CharField(max_length=20, choices=TipoAlvo.choices, verbose_name='Tipo')
    nivel_alerta = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        verbose_name='Nível de Alerta (%)',
        help_text='Limite de incidência para tomada de decisão'
    )
    imagem = models.ImageField(upload_to='alvos/', blank=True, null=True, verbose_name='Imagem de Referência')
    descricao = models.TextField(blank=True, null=True, verbose_name='Descrição/Danos')

    class Meta:
        db_table = 'alvos_monitoramento'
        verbose_name = 'Alvo de Monitoramento'
        verbose_name_plural = 'Alvos de Monitoramento'
        ordering = ['tipo', 'nome']

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class Monitoramento(TenantAwareModel):
    """
    Cabeçalho de uma inspeção de campo (Scouting).
    """
    safra = models.ForeignKey(Safra, on_delete=models.SET_NULL, null=True, blank=True, related_name='monitoramentos', verbose_name='Safra')
    ciclo = models.ForeignKey(Plantio, on_delete=models.SET_NULL, null=True, blank=True, related_name='monitoramentos', verbose_name='Ciclo de Produção')
    talhoes = models.ManyToManyField(Talhao, related_name='monitoramentos', verbose_name='Talhões', blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Responsável')
    data_coleta = models.DateTimeField(default=timezone.now, verbose_name='Data/Hora da Coleta')
    foto = models.ImageField(upload_to='monitoramentos/', blank=True, null=True, verbose_name='Foto da Inspeção')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Longitude')
    observacoes = models.TextField(blank=True, null=True, verbose_name='Observações')

    class Meta:
        db_table = 'monitoramentos'
        verbose_name = 'Monitoramento'
        verbose_name_plural = 'Monitoramentos'
        ordering = ['-data_coleta']

    def __str__(self):
        nome_contexto = self.ciclo.identificador if self.ciclo else (self.safra.nome if self.safra else 'Monitoramento')
        return f"{nome_contexto} - {self.data_coleta.strftime('%d/%m/%Y')}"


class MonitoramentoItem(models.Model):
    """
    Detalhes dos alvos encontrados em um monitoramento específico.
    """
    monitoramento = models.ForeignKey(Monitoramento, on_delete=models.CASCADE, related_name='itens')
    alvo = models.ForeignKey(AlvoMonitoramento, on_delete=models.CASCADE, verbose_name='Alvo')
    incidencia = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Incidência (%)')
    severidade = models.IntegerField(
        default=1, 
        choices=[(i, str(i)) for i in range(1, 6)],
        verbose_name='Severidade (1-5)',
        help_text='Escala de dano: 1 (Leve) a 5 (Muito Forte)'
    )
    contagem = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Contagem (por m² ou planta)')

    class Meta:
        db_table = 'monitoramento_itens'
        verbose_name = 'Item de Monitoramento'
        verbose_name_plural = 'Itens de Monitoramento'

    def __str__(self):
        return f"{self.alvo.nome}: {self.incidencia}%"

    @property
    def em_alerta(self):
        """Verifica se a incidência ultrapassou o nível de alerta do alvo."""
        return self.incidencia >= self.alvo.nivel_alerta
