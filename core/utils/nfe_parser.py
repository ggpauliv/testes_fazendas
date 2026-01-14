"""
AgroTalhoes - Parser de NFe (Nota Fiscal Eletrônica)

Módulo para importação e processamento de arquivos XML de NFe.
Extrai informações dos produtos e registra entrada no estoque.
"""

import xmltodict
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone

from core.models import Produto, MovimentacaoEstoque, CategoriaProduto, TipoMovimentacao, CategoriaFinanceira, ContaPagar, StatusFinanceiro


class NFeParseError(Exception):
    """Exceção personalizada para erros de parse de NFe."""
    pass


class NFeParser:
    """
    Classe para processar arquivos XML de NFe e importar produtos para o estoque.
    
    Uso:
        parser = NFeParser()
        resultado = parser.importar_nfe_xml(arquivo_xml)
    """
    
    # Mapeamento de palavras-chave para categorias
    CATEGORIA_KEYWORDS = {
        CategoriaProduto.SEMENTE: ['semente', 'seed', 'sementes'],
        CategoriaProduto.FERTILIZANTE: ['fertilizante', 'adubo', 'npk', 'ureia', 'potassio', 'fosforo'],
        CategoriaProduto.HERBICIDA: ['herbicida', 'glifosato', 'roundup', 'paraquat'],
        CategoriaProduto.FUNGICIDA: ['fungicida', 'fungic'],
        CategoriaProduto.INSETICIDA: ['inseticida', 'insetic'],
        CategoriaProduto.DEFENSIVO: ['defensivo', 'agrotóxico', 'agrotoxico', 'pesticida'],
    }

    def __init__(self):
        self.erros = []
        self.produtos_importados = []

    def _detectar_categoria(self, nome_produto: str) -> str:
        """
        Tenta detectar a categoria do produto baseado no nome.
        """
        nome_lower = nome_produto.lower()
        
        for categoria, keywords in self.CATEGORIA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in nome_lower:
                    return categoria
        
        return CategoriaProduto.OUTROS

    def _parse_decimal(self, valor: str, default: Decimal = Decimal('0')) -> Decimal:
        """
        Converte string para Decimal de forma segura.
        """
        if not valor:
            return default
        try:
            # Tratar formato brasileiro (vírgula como decimal)
            valor_limpo = str(valor).replace(',', '.')
            return Decimal(valor_limpo)
        except (InvalidOperation, ValueError):
            return default

    def _extrair_dados_emitente(self, emit: Dict) -> Dict:
        """
        Extrai dados do emitente (fornecedor) da NFe.
        """
        if not emit:
            return {'nome': 'Não identificado', 'cnpj': ''}
        
        return {
            'nome': emit.get('xNome', emit.get('xFant', 'Não identificado')),
            'cnpj': emit.get('CNPJ', emit.get('CPF', '')),
        }

    def _extrair_dados_nfe(self, ide: Dict, prot: Dict = None) -> Dict:
        """
        Extrai dados gerais da NFe (número, série, chave).
        """
        chave = ''
        if prot and isinstance(prot, dict):
            inf_prot = prot.get('infProt', {})
            chave = inf_prot.get('chNFe', '')
        
        return {
            'numero': ide.get('nNF', ''),
            'serie': ide.get('serie', ''),
            'data_emissao': ide.get('dhEmi', ide.get('dEmi', '')),
            'chave': chave,
        }

    def _processar_item(self, item: Dict, dados_nfe: Dict, fornecedor: str) -> Optional[Dict]:
        """
        Processa um item individual da NFe.
        
        Args:
            item: Dicionário com dados do item (det)
            dados_nfe: Dados gerais da NFe
            fornecedor: Nome do fornecedor
            
        Returns:
            Dicionário com informações do produto processado ou None se erro
        """
        try:
            prod = item.get('prod', {})
            
            if not prod:
                return None
            
            # Extrair informações do produto
            codigo = prod.get('cProd', '')
            nome = prod.get('xProd', 'Produto não identificado')
            ncm = prod.get('NCM', '')
            unidade = prod.get('uCom', prod.get('uTrib', 'UN'))
            quantidade = self._parse_decimal(prod.get('qCom', prod.get('qTrib', '0')))
            valor_unitario = self._parse_decimal(prod.get('vUnCom', prod.get('vUnTrib', '0')))
            valor_total = self._parse_decimal(prod.get('vProd', '0'))
            
            # Calcular valor unitário se não informado
            if valor_unitario == 0 and quantidade > 0:
                valor_unitario = valor_total / quantidade
            
            return {
                'codigo': codigo,
                'nome': nome,
                'ncm': ncm,
                'unidade': unidade.upper()[:20],  # Limitar tamanho
                'quantidade': quantidade,
                'valor_unitario': valor_unitario,
                'valor_total': valor_total,
                'categoria': self._detectar_categoria(nome),
                'chave_nfe': dados_nfe.get('chave', ''),
                'numero_nfe': dados_nfe.get('numero', ''),
                'fornecedor': fornecedor,
            }
            
        except Exception as e:
            self.erros.append(f"Erro ao processar item: {str(e)}")
            return None

    def _garantir_lista(self, valor) -> List:
        """
        Garante que o valor seja uma lista (XML pode retornar dict se houver só 1 item).
        """
        if valor is None:
            return []
        if isinstance(valor, list):
            return valor
        return [valor]

    def processar_xml_dados(self, arquivo_xml, empresa=None):
        """
        Lê e extrai dados do XML sem salvar no banco.
        Retorna dicionário com dados da NFe, Emitente e Itens.
        Se empresa for passada, tenta identificar produto existente.
        """
        try:
            # Ler conteúdo do XML
            if hasattr(arquivo_xml, 'read'):
                arquivo_xml.seek(0) # Garantir inicio
                conteudo_xml = arquivo_xml.read()
                if isinstance(conteudo_xml, bytes):
                    conteudo_xml = conteudo_xml.decode('utf-8')
            else:
                conteudo_xml = arquivo_xml
            
            # Parse do XML para dicionário
            doc = xmltodict.parse(conteudo_xml)
            
            nfe_proc = doc.get('nfeProc', doc)
            nfe = nfe_proc.get('NFe', nfe_proc)
            inf_nfe = nfe.get('infNFe', {})
            
            if not inf_nfe:
                raise NFeParseError("Estrutura de NFe não encontrada no XML")
            
            # Emitente
            emit = inf_nfe.get('emit', {})
            dados_emitente = self._extrair_dados_emitente(emit)
            
            # Dados NFe
            ide = inf_nfe.get('ide', {})
            prot_nfe = nfe_proc.get('protNFe', {})
            dados_nfe = self._extrair_dados_nfe(ide, prot_nfe)
            
            # Itens
            itens_orig = self._garantir_lista(inf_nfe.get('det', []))
            produtos = []
            
            for item in itens_orig:
                dados_prod = self._processar_item(item, dados_nfe, dados_emitente['nome'])
                if dados_prod:
                    # Tentar encontrar correspondência no banco se empresa for passada
                    if empresa:
                        produto_existente = Produto.objects.filter(
                            empresa=empresa, 
                            nome__iexact=dados_prod['nome']
                        ).first()
                        if produto_existente:
                            dados_prod['produto_id'] = produto_existente.id
                            dados_prod['produto_nome_match'] = produto_existente.nome
                        else:
                            dados_prod['produto_id'] = None
                            dados_prod['produto_nome_match'] = None

                    produtos.append(dados_prod)
            
            return {
                'sucesso': True,
                'nfe': dados_nfe,
                'emitente': dados_emitente,
                'itens': produtos
            }
            
        except Exception as e:
            return {'sucesso': False, 'erro': str(e)}

    @transaction.atomic
    def importar_nfe_xml(self, arquivo_xml, empresa=None) -> Dict:
        """
        Função principal para importar NFe de arquivo XML.
        """
        self.erros = []
        self.produtos_importados = []
        
        # Reutiliza a lógica de extração
        dados_parsed = self.processar_xml_dados(arquivo_xml, empresa=empresa)
        if not dados_parsed['sucesso']:
             return {
                'sucesso': False,
                'mensagem': f"Erro ao processar XML: {dados_parsed['erro']}",
                'produtos_importados': 0,
                'produtos': [],
                'erros': [dados_parsed['erro']],
                'dados_nfe': {},
            }
            
        dados_nfe = dados_parsed['nfe']
        dados_emitente = dados_parsed['emitente']
        produtos_extraidos = dados_parsed['itens']
        nome_fornecedor = dados_emitente['nome']
        
        # Verificar duplicidade
        if dados_nfe['chave']:
                existe = MovimentacaoEstoque.objects.filter(
                    chave_nfe=dados_nfe['chave'],
                    empresa=empresa
                ).exists()
                if existe:
                    return {
                        'sucesso': False,
                        'mensagem': f"NFe {dados_nfe['numero']} já foi importada anteriormente.",
                        'produtos_importados': 0,
                        'produtos': [],
                        'erros': ['NFe duplicada'],
                        'dados_nfe': dados_nfe,
                    }

        produtos_processados = []
        
        # Tentar encontrar Pedido de Compra compatível
        from core.models import PedidoCompra, ItemPedidoCompra, StatusPedido
        pedido_vinculado = None
        if empresa:
            pedidos_compativeis = PedidoCompra.objects.filter(
                empresa=empresa,
                status__in=[StatusPedido.ABERTO, StatusPedido.PARCIAL],
                fornecedor__icontains=nome_fornecedor.split(' ')[0]
            )
            if pedidos_compativeis.exists():
                pedido_vinculado = pedidos_compativeis.first()
        
        for dados_produto in produtos_extraidos:
            if dados_produto['quantidade'] > 0:
                # Buscar ou criar produto (Escopo da Empresa)
                produto = None
                criado = False
                
                if empresa:
                    produto = Produto.objects.filter(empresa=empresa, nome__iexact=dados_produto['nome']).first()
                    if not produto:
                            produto = Produto.objects.create(
                            empresa=empresa,
                            nome=dados_produto['nome'],
                            codigo=dados_produto['codigo'],
                            categoria=dados_produto['categoria'],
                            unidade=dados_produto['unidade'],
                            valor_base=dados_produto['valor_unitario']
                        )
                            criado = True
                
                # Tentar vincular a ItemPedidoCompra
                item_pedido = None
                if pedido_vinculado and produto:
                    item_pedido = ItemPedidoCompra.objects.filter(
                        pedido=pedido_vinculado,
                        produto=produto
                    ).first()

                # Criar movimentação de entrada
                movimentacao = MovimentacaoEstoque.objects.create(
                    empresa=empresa,
                    produto=produto,
                    tipo=TipoMovimentacao.ENTRADA,
                    quantidade=dados_produto['quantidade'],
                    valor_unitario=dados_produto['valor_unitario'],
                    data_movimentacao=timezone.now(),
                    chave_nfe=dados_produto['chave_nfe'],
                    numero_nfe=dados_produto['numero_nfe'],
                    fornecedor=dados_produto['fornecedor'],
                    item_pedido=item_pedido, # Vincula se encontrou
                    observacao=f"Importado via NFe {dados_produto['numero_nfe']}"
                )
                
                produtos_processados.append({
                    'produto_id': produto.id,
                    'nome': produto.nome,
                    'quantidade': float(dados_produto['quantidade']),
                    'valor_unitario': float(dados_produto['valor_unitario']),
                    'valor_total': float(dados_produto['valor_total']),
                    'movimentacao_id': movimentacao.id,
                    'produto_criado': criado,
                    'pedido_vinculado': pedido_vinculado.id if pedido_vinculado else None
                })
        
        self.produtos_importados = produtos_processados
        
        # --- INTEGRAÇÃO FINANCEIRA ---
        if empresa and len(produtos_processados) > 0:
            total_nfe = sum(Decimal(str(p['valor_total'])) for p in produtos_processados)
            primeiro_item = produtos_processados[0]
            
            # Buscar uma categoria padrão ou a primeira de SAIDA
            categoria = CategoriaFinanceira.objects.filter(empresa=empresa, tipo='SAIDA', ativo=True).first()
            if not categoria:
                categoria = CategoriaFinanceira.objects.create(
                    empresa=empresa,
                    nome='Aquisição de Insumos/Produtos',
                    tipo='SAIDA'
                )
            
            # Criar conta a pagar
            fornecedor_obj = None
            if nome_fornecedor:
                from core.models import Fornecedor
                fornecedor_obj, _ = Fornecedor.objects.get_or_create(
                    nome=nome_fornecedor,
                    empresa=empresa
                )

            ContaPagar.objects.create(
                empresa=empresa,
                descricao=f"Comp: NFe {dados_nfe['numero']} - {nome_fornecedor}",
                fornecedor=fornecedor_obj,
                categoria=categoria,
                valor_total=total_nfe,
                data_vencimento=timezone.now().date(), # Vencimento inicial hoje
                numero_nfe=dados_nfe['numero'],
                movimentacao_origem=MovimentacaoEstoque.objects.get(id=primeiro_item['movimentacao_id']),
                status=StatusFinanceiro.PENDENTE,
                observacao=f"Gerado automaticamente via importação de NFe {dados_nfe['numero']}."
            )

        msg_vinculo = ""
        if pedido_vinculado:
            msg_vinculo = f" (Vinculada ao Pedido #{pedido_vinculado.id})"

        return {
            'sucesso': True,
            'mensagem': f"NFe {dados_nfe['numero']} importada com sucesso! {len(produtos_processados)} itens registrados.{msg_vinculo}",
            'produtos_importados': len(produtos_processados),
            'produtos': produtos_processados,
            'erros': self.erros,
            'dados_nfe': dados_nfe,
            'fornecedor': dados_emitente,
        }


def importar_nfe_xml(arquivo_xml, empresa=None) -> Dict:
    """
    Função utilitária para importar NFe de arquivo XML.
    Wrapper para facilitar o uso direto.
    
    Args:
        arquivo_xml: Arquivo XML (file-like object ou string)
        empresa: Objeto empresa (Otimiza busca de produtos e duplicidade)
        
    Returns:
        Dicionário com resultado da importação
    """
    parser = NFeParser()
    return parser.importar_nfe_xml(arquivo_xml, empresa=empresa)
