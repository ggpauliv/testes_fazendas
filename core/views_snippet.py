
import yfinance as yf
from django.core.cache import cache

def market_data(request):
    """
    API para retornar dados de mercado (cotações)
    """
    # Cache key para evitar muitas requisições ao Yahoo Finance
    cache_key = 'market_data_cache'
    data = cache.get(cache_key)

    if not data:
        tickers = {
            'ZS=F': 'Soja',        # Soybean Futures
            'ZC=F': 'Milho',       # Corn Futures
            'LE=F': 'Boi Gordo',   # Live Cattle Futures
            'BRL=X': 'USD/BRL'     # Dolar Comercial
        }
        
        results = []
        try:
            for symbol, name in tickers.items():
                ticker = yf.Ticker(symbol)
                history = ticker.history(period="2d")
                
                if not history.empty:
                    current_price = history['Close'].iloc[-1]
                    try:
                        prev_price = history['Close'].iloc[-2]
                        change_pct = ((current_price - prev_price) / prev_price) * 100
                    except IndexError:
                        change_pct = 0.0
                    
                    is_up = change_pct >= 0
                    
                    # Formatar Preço
                    if symbol == 'BRL=X':
                        price_fmt = f"R$ {current_price:.2f}"
                    else:
                        # Commodities agrícolas em USD (cents per bushel ou pound)
                        price_fmt = f"U$ {current_price:.2f}"

                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'price': price_fmt,
                        'change': f"{change_pct:+.2f}",
                        'is_up': is_up
                    })
        except Exception as e:
            print(f"Erro ao buscar dados de mercado: {e}")
            
        data = {'commodities': results}
        # Cache por 15 minutos
        cache.set(cache_key, data, 900)

    return JsonResponse(data)
