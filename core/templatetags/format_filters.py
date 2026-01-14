from django import template
import decimal

register = template.Library()

@register.filter(name='formato_br')
def formato_br(value, decimal_places=2):
    """
    Formata um número para o padrão brasileiro: 1.234,56
    """
    if value is None or value == '':
        return '0,00'
    
    try:
        if isinstance(value, str):
            value = value.replace(',', '.')
        
        number = decimal.Decimal(str(value))
        
        # Formata com separador de milhar e casas decimais
        # O formato '{:,.2f}' usa vírgula para milhar e ponto para decimal
        # Então trocamos para o padrão BR
        # Nota: Django localization já deveria fazer isso se USE_L10N=True e LANGUAGE_CODE='pt-br'
        # Mas este filtro garante a consistência e o número de casas.
        
        formatted = "{:,.{}f}".format(number, decimal_places)
        
        # Troca , por [TEMP], . por , e [TEMP] por .
        import re
        parts = formatted.split('.')
        main_part = parts[0].replace(',', '.')
        decimal_part = parts[1]
        
        return f"{main_part},{decimal_part}"
        
    except (ValueError, decimal.InvalidOperation, TypeError, IndexError):
        return value
