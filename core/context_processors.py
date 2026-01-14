"""
Context Processors para o sistema AgroTalhoes.
"""

from .models import ConfiguracaoSistema


def sistema_config(request):
    """
    Adiciona as configurações do sistema ao contexto de todos os templates.
    Uso no template: {{ sistema_config.nome_sistema }}, {{ sistema_config.logo.url }}
    """
    try:
        config = ConfiguracaoSistema.get_config()
        return {'sistema_config': config}
    except Exception:
        return {'sistema_config': None}
