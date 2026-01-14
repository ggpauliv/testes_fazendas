import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def get_talhao_weather_data(lat, lon):
    """
    Busca dados meteorológicos do Open-Meteo para um talhão.
    Retorna:
    - Umidade do solo atual (Estimada 0-9cm) - Média
    - Chuva acumulada nos últimos 30 dias
    - Dados diários de Balanço Hídrico (30 dias passados)
    - Previsão do tempo para os próximos 5 dias
    """
    if not lat or not lon:
        return None

    try:
        # Endpoint principal da Open-Meteo
        url = "https://api.open-meteo.com/v1/forecast"
        
        # Parâmetros:
        # daily: Chuva, ET0, Temp Max/Min, Código Clima, Probabilidade Chuva
        # hourly: Umidade do solo
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm",
            "daily": "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
            "timezone": "auto",
            "past_days": 30,
            "forecast_days": 6 
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # === 1. DADOS ATUAIS (SOLO) ===
        hourly = data.get('hourly', {})
        times = hourly.get('time', [])
        current_hour_iso = datetime.now().strftime("%Y-%m-%dT%H:00")
        
        try:
            index = times.index(current_hour_iso)
        except ValueError:
            index = -1 
            
        sm0 = hourly.get('soil_moisture_0_to_1cm', [])
        sm1 = hourly.get('soil_moisture_1_to_3cm', [])
        sm3 = hourly.get('soil_moisture_3_to_9cm', [])
        
        val_sm0 = sm0[index] if sm0 and len(sm0) > index else 0
        val_sm1 = sm1[index] if sm1 and len(sm1) > index else 0
        val_sm3 = sm3[index] if sm3 and len(sm3) > index else 0
        
        avg_moisture = ((val_sm0 + val_sm1 + val_sm3) / 3) * 100
        
        # === 2. HISTÓRICO 30 DIAS (CHART) ===
        daily = data.get('daily', {})
        daily_dates = daily.get('time', [])
        precip = daily.get('precipitation_sum', [])
        et0 = daily.get('et0_fao_evapotranspiration', [])
        
        # Cortar para pegar apenas os 30 dias passados
        # O array daily contém past_days (30) + forecast_days (6) = 36 dias
        # Indices 0 a 29 são passado. 30 é hoje.
        
        history_len = 30
        
        history_precip = precip[:history_len]
        total_rain_30d = sum(x for x in history_precip if x is not None)
        
        chart_data = []
        for i in range(history_len):
            if i >= len(daily_dates): break
            
            p = precip[i] if precip[i] is not None else 0
            e = et0[i] if et0[i] is not None else 0
            date = daily_dates[i]
            
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                date_fmt = date_obj.strftime("%d/%m")
            except:
                date_fmt = date
            
            chart_data.append({
                'date': date_fmt,
                'precipitation': p,
                'et0': e,
                'balance': p - e
            })
            
        # === 3. PREVISÃO (PRÓXIMOS 5 DIAS) ===
        # Começa de hoje (index 30) até o fim
        forecast_data = []
        
        temp_max = daily.get('temperature_2m_max', [])
        temp_min = daily.get('temperature_2m_min', [])
        w_codes = daily.get('weather_code', [])
        prob_rain = daily.get('precipitation_probability_max', [])
        
        start_idx = history_len
        end_idx = len(daily_dates)
        
        # Mapeamento códigos WMO -> Ícones Bootstrap/Texto
        wmo_map = {
            0: {'icon': 'bi-sun', 'desc': 'Limpo'},
            1: {'icon': 'bi-sun', 'desc': 'Parc. Nublado'},
            2: {'icon': 'bi-cloud-sun', 'desc': 'Nublado'},
            3: {'icon': 'bi-clouds', 'desc': 'Encoberto'},
            45: {'icon': 'bi-cloud-haze', 'desc': 'Nevoeiro'},
            48: {'icon': 'bi-cloud-haze', 'desc': 'Nevoeiro'},
            51: {'icon': 'bi-cloud-drizzle', 'desc': 'Garoa Leve'},
            53: {'icon': 'bi-cloud-drizzle', 'desc': 'Garoa Mod.'},
            55: {'icon': 'bi-cloud-drizzle', 'desc': 'Garoa Forte'},
            61: {'icon': 'bi-cloud-rain', 'desc': 'Chuva Leve'},
            63: {'icon': 'bi-cloud-rain', 'desc': 'Chuva Mod.'},
            65: {'icon': 'bi-cloud-rain', 'desc': 'Chuva Forte'},
            71: {'icon': 'bi-snow', 'desc': 'Neve'},
            80: {'icon': 'bi-cloud-rain-heavy', 'desc': 'Pancadas'},
            81: {'icon': 'bi-cloud-rain-heavy', 'desc': 'Pancadas'},
            82: {'icon': 'bi-cloud-rain-heavy', 'desc': 'Pancadas'},
            95: {'icon': 'bi-cloud-lightning-rain', 'desc': 'Temporal'},
        }
        
        for i in range(start_idx, end_idx):
            if i >= len(daily_dates): break
            
            d_date = daily_dates[i]
            d_max = temp_max[i] if i < len(temp_max) else 0
            d_min = temp_min[i] if i < len(temp_min) else 0
            d_precip = precip[i] if i < len(precip) else 0
            d_code = w_codes[i] if i < len(w_codes) else 0
            d_prob = prob_rain[i] if prob_rain and i < len(prob_rain) else 0
            
            # Formatar data
            try:
                dt = datetime.strptime(d_date, "%Y-%m-%d")
                weekday = dt.strftime("%a") # Seg, Ter... (depende do locale, mas ok)
                # Tradução manual simples pra PT-BR se locale não estiver setado
                week_map = {'Mon': 'Seg', 'Tue': 'Ter', 'Wed': 'Qua', 'Thu': 'Qui', 'Fri': 'Sex', 'Sat': 'Sáb', 'Sun': 'Dom'}
                weekday = week_map.get(weekday, weekday)
                date_display = dt.strftime("%d/%m")
            except:
                weekday = ""
                date_display = d_date
                
            w_info = wmo_map.get(d_code, {'icon': 'bi-cloud', 'desc': '---'})
            
            forecast_data.append({
                'date': date_display,
                'weekday': weekday,
                'min': round(d_min),
                'max': round(d_max),
                'precip': d_precip,
                'prob': d_prob,
                'icon': w_info['icon'],
                'desc': w_info['desc']
            })
            
        return {
            'current_soil_moisture': round(avg_moisture, 1),
            'total_rain_30d': round(total_rain_30d, 1),
            'chart_data': chart_data,
            'forecast': forecast_data
        }

    except Exception as e:
        logger.error(f"Erro ao buscar dados do Open-Meteo: {e}")
        return None


def fetch_historical_weather(lat, lon, start_date, end_date):
    """
    Busca histórico climático para intervalo de datas.
    Campos: Temp Max/Min, Chuva, Vento Max, Umidade Média.
    """
    if not lat or not lon:
        return []

    try:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,relative_humidity_2m_mean",
            "timezone": "auto"
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        daily = data.get('daily', {})
        times = daily.get('time', [])
        t_max = daily.get('temperature_2m_max', [])
        t_min = daily.get('temperature_2m_min', [])
        rain = daily.get('precipitation_sum', [])
        wind = daily.get('wind_speed_10m_max', [])
        hum = daily.get('relative_humidity_2m_mean', [])

        results = []
        for i, date_str in enumerate(times):
            results.append({
                'data': date_str,
                'temp_max': t_max[i] if t_max[i] is not None else 0,
                'temp_min': t_min[i] if t_min[i] is not None else 0,
                'precipitacao': rain[i] if rain[i] is not None else 0,
                'velocidade_vento': wind[i] if wind[i] is not None else 0,
                'umidade_relativa': hum[i] if hum[i] is not None else 0,
            })
            
        return results

    except Exception as e:
        logger.error(f"Erro ao buscar histórico Open-Meteo: {e}")
        return []
