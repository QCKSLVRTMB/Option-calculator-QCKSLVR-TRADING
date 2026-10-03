import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import json
import math
import re
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="MOEX Options & Black-Scholes",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
</style>
""", unsafe_allow_html=True)

# ================= MOEX API =================
API_BASE_URL = "https://iss.moex.com/iss/apps/option-calc/v1"
SECURITIES_URL = "https://iss.moex.com/iss/engines/futures/markets/options/securities.json?iss.meta=off"

ASSET_TYPE_MAP = {
    'Фьючерс': 'futures',
    'Акция': 'share',
    'Валюта': 'currency',
    'Товар': 'commodity',
    'Индекс': 'index',
}

# ================= Справочник инструментов MOEX =================
MOEX_INSTRUMENTS = {
    "Индексы": {
        "RTS":      ("Индекс", "Индекс РТС"),
        "MIX":      ("Индекс", "Индекс МосБиржи"),
        "RVI":      ("Индекс", "Индекс волатильности RVI"),
        "MOEXCNY":  ("Индекс", "Индекс МосБиржи в юанях"),
        "RGBI":     ("Индекс", "Индекс RGBI"),
        "MMI":      ("Индекс", "Индекс металлов и добычи"),
        "FNI":      ("Индекс", "Индекс финансов"),
        "OGI":      ("Индекс", "Индекс нефти и газа"),
        "MXI":      ("Индекс", "Индекс МосБиржи (мини)"),
        "RTSM":     ("Индекс", "Индекс РТС (мини)"),
    },
    "Акции": {
        "GAZP":     ("Акция", "Газпром"),
        "SBER":     ("Акция", "Сбербанк о.с."),
        "SBERP":    ("Акция", "Сбербанк п.с."),
        "LKOH":     ("Акция", "ЛУКОЙЛ"),
        "ROSN":     ("Акция", "Роснефть"),
        "NOTK":     ("Акция", "НОВАТЭК"),
        "TATN":     ("Акция", "Татнефть о.с."),
        "TATNP":    ("Акция", "Татнефть п.с."),
        "SNGSP":    ("Акция", "Сургутнефтегаз п.с."),
        "MTSS":     ("Акция", "МТС"),
        "MGNT":     ("Акция", "Магнит"),
        "GMKN":     ("Акция", "Норникель"),
        "NLMK":     ("Акция", "НЛМК"),
        "CHMF":     ("Акция", "Северсталь"),
        "ALRS":     ("Акция", "АЛРОСА"),
        "VTBR":     ("Акция", "ВТБ"),
        "MOEX":     ("Акция", "Московская Биржа"),
        "AFKS":     ("Акция", "АФК Система"),
        "IRAO":     ("Акция", "Интер РАО"),
        "HYDR":     ("Акция", "РусГидро"),
        "RTKM":     ("Акция", "Ростелеком"),
        "PLZL":     ("Акция", "Полюс"),
        "MAGN":     ("Акция", "ММК"),
        "YDEX":     ("Акция", "Яндекс"),
        "PHOR":     ("Акция", "ФосАгро"),
        "RUAL":     ("Акция", "РУСАЛ"),
        "FEES":     ("Акция", "ФСК ЕЭС"),
        "TRNFP":    ("Акция", "Транснефть п.с."),
        "AFLT":     ("Акция", "Аэрофлот"),
        "SIBN":     ("Акция", "Газпром нефть"),
        "PIKK":     ("Акция", "ПИК"),
        "FLOT":     ("Акция", "Совкомфлот"),
        "CBOM":     ("Акция", "МКБ"),
        "SGZH":     ("Акция", "Сегежа"),
        "BSPB":     ("Акция", "Банк Санкт-Петербург"),
        "KMAZ":     ("Акция", "КАМАЗ"),
        "ASTR":     ("Акция", "Группа Астра"),
        "SVCB":     ("Акция", "Совкомбанк"),
    },
    "Фьючерсы": {
        "GAZR":     ("Фьючерс", "Газпром (фьючерс)"),
        "SBRF":     ("Фьючерс", "Сбербанк о.с. (фьючерс)"),
        "SBPR":     ("Фьючерс", "Сбербанк п.с. (фьючерс)"),
        "LKOH":     ("Фьючерс", "ЛУКОЙЛ (фьючерс)"),
        "ROSN":     ("Фьючерс", "Роснефть (фьючерс)"),
        "NOTK":     ("Фьючерс", "НОВАТЭК (фьючерс)"),
        "TATN":     ("Фьючерс", "Татнефть о.с. (фьючерс)"),
        "TATP":     ("Фьючерс", "Татнефть п.с. (фьючерс)"),
        "SNGR":     ("Фьючерс", "Сургутнефтегаз о.с. (фьючерс)"),
        "SNGP":     ("Фьючерс", "Сургутнефтегаз п.с. (фьючерс)"),
        "MTSS":     ("Фьючерс", "МТС (фьючерс)"),
        "MGNT":     ("Фьючерс", "Магнит (фьючерс)"),
        "GMKN":     ("Фьючерс", "Норникель (фьючерс)"),
        "NLMK":     ("Фьючерс", "НЛМК (фьючерс)"),
        "CHMF":     ("Фьючерс", "Северсталь (фьючерс)"),
        "ALRS":     ("Фьючерс", "АЛРОСА (фьючерс)"),
        "VTBR":     ("Фьючерс", "ВТБ (фьючерс)"),
        "MOEX":     ("Фьючерс", "Московская Биржа (фьючерс)"),
        "AFKS":     ("Фьючерс", "АФК Система (фьючерс)"),
        "IRAO":     ("Фьючерс", "Интер РАО (фьючерс)"),
        "HYDR":     ("Фьючерс", "РусГидро (фьючерс)"),
        "RTKM":     ("Фьючерс", "Ростелеком (фьючерс)"),
        "PLZL":     ("Фьючерс", "Полюс (фьючерс)"),
        "MAGN":     ("Фьючерс", "ММК (фьючерс)"),
        "YDEX":     ("Фьючерс", "Яндекс (фьючерс)"),
        "PHOR":     ("Фьючерс", "ФосАгро (фьючерс)"),
        "RUAL":     ("Фьючерс", "РУСАЛ (фьючерс)"),
        "FEES":     ("Фьючерс", "ФСК ЕЭС (фьючерс)"),
        "TRNF":     ("Фьючерс", "Транснефть п.с. (фьючерс)"),
        "AFLT":     ("Фьючерс", "Аэрофлот (фьючерс)"),
        "SIBN":     ("Фьючерс", "Газпром нефть (фьючерс)"),
        "PIKK":     ("Фьючерс", "ПИК (фьючерс)"),
        "FLOT":     ("Фьючерс", "Совкомфлот (фьючерс)"),
        "CBOM":     ("Фьючерс", "МКБ (фьючерс)"),
        "SGZH":     ("Фьючерс", "Сегежа (фьючерс)"),
        "BSPB":     ("Фьючерс", "Банк Санкт-Петербург (фьючерс)"),
        "KMAZ":     ("Фьючерс", "КАМАЗ (фьючерс)"),
        "ASTR":     ("Фьючерс", "Группа Астра (фьючерс)"),
        "SVCB":     ("Фьючерс", "Совкомбанк (фьючерс)"),
    },
    "Валюты": {
        "Si":       ("Валюта", "Доллар США / Рубль"),
        "Eu":       ("Валюта", "Евро / Рубль"),
        "CNY":      ("Валюта", "Юань / Рубль"),
        "TRY":      ("Валюта", "Турецкая лира / Рубль"),
        "HKD":      ("Валюта", "Гонконгский доллар / Рубль"),
        "AED":      ("Валюта", "Дирхам ОАЭ / Рубль"),
        "KZT":      ("Валюта", "Казахстанский тенге / Рубль"),
        "AMD":      ("Валюта", "Армянский драм / Рубль"),
        "BYN":      ("Валюта", "Белорусский рубль / Рубль"),
        "ED":       ("Валюта", "Евро / Доллар"),
        "AUDU":     ("Валюта", "Австралийский доллар / Доллар"),
        "GBPU":     ("Валюта", "Фунт стерлингов / Доллар"),
        "UCAD":     ("Валюта", "Доллар / Канадский доллар"),
        "UCHF":     ("Валюта", "Доллар / Швейцарский франк"),
        "UJPY":     ("Валюта", "Доллар / Японская йена"),
        "UCNY":     ("Валюта", "Доллар / Юань"),
    },
    "Товары": {
        "BR":       ("Товар", "Нефть Brent"),
        "CL":       ("Товар", "Нефть Light Sweet"),
        "GOLD":     ("Товар", "Золото"),
        "SILV":     ("Товар", "Серебро"),
        "PLD":      ("Товар", "Палладий"),
        "PLT":      ("Товар", "Платина"),
        "ALMN":     ("Товар", "Алюминий"),
        "Co":       ("Товар", "Медь"),
        "Nl":       ("Товар", "Никель"),
        "Zn":       ("Товар", "Цинк"),
        "NG":       ("Товар", "Природный газ"),
        "WHEAT":    ("Товар", "Пшеница"),
        "SUGR":     ("Товар", "Сахар"),
    },
}

# ================= Соответствие MOEX-код → тикер TradingView =================
TV_TICKER_MAP = {
    "Акция": {
        "GAZP": "MOEX:GAZP", "SBER": "MOEX:SBER", "SBERP": "MOEX:SBERP",
        "LKOH": "MOEX:LKOH", "ROSN": "MOEX:ROSN", "NOTK": "MOEX:NOTK",
        "TATN": "MOEX:TATN", "TATNP": "MOEX:TATNP",
        "SNGSP": "MOEX:SNGSP", "MTSS": "MOEX:MTSS",
        "MGNT": "MOEX:MGNT", "GMKN": "MOEX:GMKN", "NLMK": "MOEX:NLMK",
        "CHMF": "MOEX:CHMF", "ALRS": "MOEX:ALRS", "VTBR": "MOEX:VTBR",
        "MOEX": "MOEX:MOEX", "AFKS": "MOEX:AFKS", "IRAO": "MOEX:IRAO",
        "HYDR": "MOEX:HYDR", "RTKM": "MOEX:RTKM", "PLZL": "MOEX:PLZL",
        "MAGN": "MOEX:MAGN", "YDEX": "MOEX:YDEX", "PHOR": "MOEX:PHOR",
        "RUAL": "MOEX:RUAL", "FEES": "MOEX:FEES", "TRNFP": "MOEX:TRNFP",
        "AFLT": "MOEX:AFLT", "SIBN": "MOEX:SIBN", "PIKK": "MOEX:PIKK",
        "FLOT": "MOEX:FLOT", "CBOM": "MOEX:CBOM", "SGZH": "MOEX:SGZH",
        "BSPB": "MOEX:BSPB", "KMAZ": "MOEX:KMAZ", "ASTR": "MOEX:ASTR",
        "SVCB": "MOEX:SVCB",
    },
    "Фьючерс": {
        "GAZR": "MOEX:GZ1!", "GZ": "MOEX:GZ1!",
        "SBRF": "MOEX:SR1!", "SR": "MOEX:SR1!",
        "SBPR": "MOEX:SP1!", "SP": "MOEX:SP1!",
        "LKOH": "MOEX:LK1!", "LK": "MOEX:LK1!",
        "ROSN": "MOEX:RN1!", "RN": "MOEX:RN1!",
        "NOTK": "MOEX:NK1!", "NK": "MOEX:NK1!",
        "TATN": "MOEX:TT1!", "TT": "MOEX:TT1!",
        "SNGR": "MOEX:SN1!", "SN": "MOEX:SN1!",
        "MTSS": "MOEX:MT1!", "MT": "MOEX:MT1!",
        "MGNT": "MOEX:MG1!", "MG": "MOEX:MG1!",
        "GMKN": "MOEX:GM1!", "GK": "MOEX:GM1!",
        "NLMK": "MOEX:NM1!", "NM": "MOEX:NM1!",
        "CHMF": "MOEX:CH1!", "CH": "MOEX:CH1!",
        "ALRS": "MOEX:AL1!", "AL": "MOEX:AL1!",
        "VTBR": "MOEX:VB1!", "VB": "MOEX:VB1!",
        "MOEX": "MOEX:ME1!", "ME": "MOEX:ME1!",
        "AFKS": "MOEX:AK1!", "AK": "MOEX:AK1!",
        "IRAO": "MOEX:IR1!", "IR": "MOEX:IR1!",
        "HYDR": "MOEX:HY1!", "HY": "MOEX:HY1!",
        "RTKM": "MOEX:RT1!", "RT": "MOEX:RT1!",
        "PLZL": "MOEX:PL1!", "PL": "MOEX:PL1!",
        "MAGN": "MOEX:MM1!",
        "YDEX": "MOEX:YD1!", "YD": "MOEX:YD1!",
        "PHOR": "MOEX:PH1!", "PH": "MOEX:PH1!",
        "RUAL": "MOEX:RL1!", "RL": "MOEX:RL1!",
        "FEES": "MOEX:FS1!", "FS": "MOEX:FS1!",
        "TRNF": "MOEX:TN1!", "TN": "MOEX:TN1!",
        "AFLT": "MOEX:AF1!", "AF": "MOEX:AF1!",
        "PIKK": "MOEX:PI1!", "PI": "MOEX:PI1!",
        "FLOT": "MOEX:FL1!", "FL": "MOEX:FL1!",
        "KMAZ": "MOEX:KM1!", "KM": "MOEX:KM1!",
        "ASTR": "MOEX:AS1!", "AS": "MOEX:AS1!",
        "SVCB": "MOEX:SC1!", "SC": "MOEX:SC1!",
        "RTS": "MOEX:RI1!", "RI": "MOEX:RI1!",
        "MIX": "MOEX:MIX1!",
        "RVI": "MOEX:VI1!", "VI": "MOEX:VI1!",
        "RGBI": "MOEX:RB1!", "RB": "MOEX:RB1!",
        "MOEXCNY": "MOEX:CR1!",
        "Si": "MOEX:SI1!", "Eu": "MOEX:EU1!",
        "CNY": "MOEX:CR1!", "CR": "MOEX:CR1!",
        "TRY": "MOEX:TRY1!",
        "BR": "MOEX:BR1!", "GOLD": "MOEX:GD1!", "GD": "MOEX:GD1!",
        "SILV": "MOEX:SV1!", "SV": "MOEX:SV1!",
        "NG": "MOEX:NG1!", "CL": "MOEX:CL1!",
    },
    "Индекс": {
        "RTS": "MOEX:RI1!", "RI": "MOEX:RI1!",
        "MIX": "MOEX:MIX1!",
        "RVI": "MOEX:VI1!", "VI": "MOEX:VI1!",
        "RGBI": "MOEX:RB1!", "RB": "MOEX:RB1!",
        "MOEXCNY": "MOEX:CR1!", "CR": "MOEX:CR1!",
        "MXI": "MOEX:MIX1!", "RTSM": "MOEX:RTSM1!",
        "MMI": "MOEX:MMI1!", "FNI": "MOEX:FNI1!", "OGI": "MOEX:OGI1!",
    },
    "Валюта": {
        "Si": "MOEX:SI1!", "Eu": "MOEX:EU1!",
        "CNY": "MOEX:CR1!", "CR": "MOEX:CR1!",
        "TRY": "MOEX:TRY1!", "HKD": "MOEX:HKD1!",
        "AED": "MOEX:AED1!", "KZT": "MOEX:KZT1!",
        "AMD": "MOEX:AMD1!", "BYN": "MOEX:BYN1!",
        "ED": "MOEX:ED1!", "AUDU": "MOEX:AUDU1!",
        "GBPU": "MOEX:GBPU1!", "UCAD": "MOEX:UCAD1!",
        "UCHF": "MOEX:UCHF1!", "UJPY": "MOEX:UJPY1!",
        "UCNY": "MOEX:UCNY1!",
    },
    "Товар": {
        "BR": "MOEX:BR1!", "CL": "MOEX:CL1!",
        "GOLD": "MOEX:GD1!", "GD": "MOEX:GD1!",
        "SILV": "MOEX:SV1!", "SV": "MOEX:SV1!",
        "PLD": "MOEX:PD1!", "PD": "MOEX:PD1!",
        "PLT": "MOEX:PT1!", "PT": "MOEX:PT1!",
        "ALMN": "MOEX:ALMN1!",
        "Co": "MOEX:CO1!", "Nl": "MOEX:NI1!", "Zn": "MOEX:ZN1!",
        "NG": "MOEX:NG1!", "WHEAT": "MOEX:WHEAT1!", "SUGR": "MOEX:SUGR1!",
    },
}


def resolve_tv_ticker(asset_code: str, asset_type_ui: str):
    return TV_TICKER_MAP.get(asset_type_ui, {}).get(asset_code)


# ================= Дивиденды (smart-lab.ru) =================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dividends_smartlab() -> pd.DataFrame:
    """Загружает таблицу дивидендов с smart-lab.ru и возвращает DataFrame.

    Колонки: ticker, dividend_rub, record_date (date).
    """
    url = "https://smart-lab.ru/dividends/index/order_by_ticker/desc/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        st.warning(f"Не удалось загрузить таблицу дивидендов: {e}")
        return pd.DataFrame(columns=["ticker", "dividend_rub", "record_date"])

    # Простой парсинг HTML: ищем строки таблицы с тикерами и датами
    rows = re.findall(
        r'<tr[^>]*>(.*?)</tr>',
        r.text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    records = []
    for row_html in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 8:
            continue
        # Убираем HTML-теги из ячеек
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        ticker = clean[1].upper() if len(clean) > 1 else ""
        if not ticker or not re.match(r'^[A-Z0-9]+$', ticker):
            continue
        try:
            dividend = float(clean[3].replace(",", ".").replace(" ", ""))
        except Exception:
            continue
        # Дата закрытия реестра — обычно 8-й столбец (индекс 7)
        date_str = None
        for idx in (7, 6, 8):
            if idx < len(clean) and re.match(r'\d{2}\.\d{2}\.\d{4}', clean[idx]):
                date_str = clean[idx]
                break
        if not date_str:
            continue
        try:
            record_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        except Exception:
            continue
        records.append({
            "ticker": ticker,
            "dividend_rub": dividend,
            "record_date": record_date,
        })

    return pd.DataFrame(records)


def get_dividend_yield_for_ticker(
    ticker: str,
    expiry_str: str,
    spot_buy: float,
    spot_sell: float,
):
    """Возвращает дивидендную доходность (в долях) для опциона на акцию.

    Условия:
      * опцион на акцию (проверяется вызывающим кодом),
      * тикер совпадает с тикером со smart-lab,
      * дата закрытия реестра ≤ дата экспирации опциона.

    Возвращает (q_buy, q_sell) — доли (например, 0.115 для 11.5%),
    либо (None, None), если подходящего дивиденда нет.
    """
    df = fetch_dividends_smartlab()
    if df.empty:
        return None, None

    try:
        exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except Exception:
        return None, None

    candidates = df[
        (df["ticker"] == ticker.upper())
        & (df["record_date"] <= exp_date)
        & (df["record_date"] >= date.today())
    ]
    if candidates.empty:
        return None, None

    # Берём ближайший по дате дивиденд
    row = candidates.sort_values("record_date").iloc[0]
    div = float(row["dividend_rub"])

    q_buy = None
    q_sell = None
    if spot_buy and spot_buy > 0:
        q_buy = div / spot_buy           # доля
    if spot_sell and spot_sell > 0:
        q_sell = div / spot_sell         # доля

    return q_buy, q_sell


# ================= G-кривая MOEX → безрисковая ставка =================

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_g_curve_params():
    """Загружает актуальные параметры G-кривой (КБД ОФЗ) с MOEX ISS."""
    url = "https://iss.moex.com/iss/engines/stock/zcyc/securities.json"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        st.warning(f"Не удалось загрузить параметры G-кривой: {e}")
        return None

    params = data.get('params', {})
    columns = params.get('columns', [])
    values = params.get('data', [])
    if not columns or not values:
        return None

    df = pd.DataFrame(values, columns=columns)
    row = df.iloc[0]

    try:
        return {
            'beta0': float(row['B1']),
            'beta1': float(row['B2']),
            'beta2': float(row['B3']),
            'tau':   float(row['T1']),
            'g':     [float(row[f'G{i}']) for i in range(1, 10)],
            'tradedate': str(row.get('tradedate', '')),
            'tradetime': str(row.get('tradetime', '')),
        }
    except Exception as e:
        st.warning(f"Ошибка разбора параметров G-кривой: {e}")
        return None


_GC_A = [0.0, 0.4, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0]
_GC_B = [0.4, 0.6, 1.0, 1.6, 2.4, 4.0, 6.4, 9.6, 16.0]


def g_curve_yield(t_years: float, p: dict):
    """Доходность КБД ОФЗ (%) на срок t_years лет (модель Нельсона-Сигеля MOEX)."""
    if p is None or t_years <= 0:
        return None

    b0, b1, b2, tau = p['beta0'], p['beta1'], p['beta2'], p['tau']
    g = p['g']

    if tau <= 0:
        tau = 1.0

    exp_term = math.exp(-t_years / tau)
    frac = (1 - exp_term) * tau / t_years

    term1 = b0
    term2 = b1 * frac
    term3 = b2 * (frac - exp_term)

    term4 = 0.0
    for i in range(9):
        if _GC_B[i] != 0:
            term4 += g[i] * math.exp(-((t_years - _GC_A[i]) ** 2) / (_GC_B[i] ** 2))

    raw = term1 + term2 + term3 + term4
    rate_pct = raw / 10000.0
    if rate_pct < 0.5 or rate_pct > 50:
        rate_pct = raw / 100.0 if raw > 100 else raw
    return rate_pct


def get_risk_free_rate_for_expiry(expiry_str: str, current_str: str = None):
    """Безрисковая ставка (%) для даты экспирации. None — если не удалось."""
    params = fetch_g_curve_params()
    if params is None:
        return None
    try:
        exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        cur_date = (datetime.strptime(current_str, "%Y-%m-%d").date()
                    if current_str else date.today())
        days = (exp_date - cur_date).days
        if days <= 0:
            return None
        return round(g_curve_yield(days / 365.0, params), 4)
    except Exception:
        return None


# ================= Цветовые маркеры дат экспирации =================

def expiry_marker(expiry_str: str) -> str:
    """Цветовой маркер даты экспирации (по неделям, Пн–Вс)."""
    try:
        d = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except Exception:
        return "⚪"

    today = date.today()
    monday_this_week = today - timedelta(days=today.weekday())
    end_next_week = monday_this_week + timedelta(days=13)
    end_week_after = monday_this_week + timedelta(days=20)

    if d <= end_next_week:
        return "🔴"
    if d <= end_week_after:
        return "🔵"
    return "🟢"


@st.cache_data(ttl=1800, show_spinner=False)
def get_asset_code_and_type(asset_input: str, asset_type_ui: str):
    moex_type = ASSET_TYPE_MAP.get(asset_type_ui, 'futures')
    code_to_fetch = asset_input
    if moex_type != 'futures':
        try:
            resp = requests.get(SECURITIES_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            securities = data.get('securities', {}).get('data', [])
            columns = data.get('securities', {}).get('columns', [])
            assetcode_idx = columns.index('ASSETCODE') if 'ASSETCODE' in columns else -1
            underlying_idx = columns.index('UNDERLYINGASSET') if 'UNDERLYINGASSET' in columns else -1
            type_idx = columns.index('UNDERLYINGTYPE') if 'UNDERLYINGTYPE' in columns else -1
            if assetcode_idx != -1 and underlying_idx != -1 and type_idx != -1:
                for row in securities:
                    if row[assetcode_idx] == asset_input:
                        if row[type_idx] != 'F':
                            code_to_fetch = row[underlying_idx]
                        break
        except Exception as e:
            st.warning(f"Не удалось уточнить код актива: {e}")
    return code_to_fetch, moex_type


@st.cache_data(ttl=300, show_spinner=False)
def fetch_optionseries(asset: str, asset_type_ui: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries"
    r = requests.get(url, params={'asset_type': moex_type}, timeout=15)
    r.raise_for_status()
    data = r.json()
    series = []
    if isinstance(data, list):
        for item in data:
            if 'optionseries_code' in item and 'expiration_date' in item:
                series.append({'code': item['optionseries_code'], 'expiry': item['expiration_date']})
    elif isinstance(data, dict) and 'data' in data:
        for item in data['data']:
            if 'optionseries_code' in item and 'expiration_date' in item:
                series.append({'code': item['optionseries_code'], 'expiry': item['expiration_date']})
    return series


@st.cache_data(ttl=300, show_spinner=False)
def fetch_series_info(asset: str, asset_type_ui: str, series_code: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}"
    r = requests.get(url, params={'asset_type': moex_type}, timeout=15)
    if r.status_code != 200:
        r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    translated = {
        "Опционная серия": data.get('optionseries_code', '—'),
        "Базовый актив": data.get('asset_code', '—'),
        "Тип БА": data.get('asset_type', '—'),
        "Тикер": data.get('futures_code', '—'),
        "Тип серии": data.get('series_type', '—'),
        "Дата экспирации": data.get('expiration_date', '—'),
        "Центральный страйк": data.get('central_strike', '—'),
    }
    for side_key, label in (('call', 'Опционы Call'), ('put', 'Опционы Put')):
        if side_key in data:
            s = data[side_key]
            translated[label] = {
                "Объем (руб.)": s.get('volume_rub', 0),
                "Контрактов": s.get('volume_contracts', 0),
                "Открытых позиций": s.get('openposition', 0),
                "ОИ изменение": s.get('oichange', 0),
            }
    return translated


def fetch_central_strike(asset_code, series_code, asset_type):
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}"
    try:
        r = requests.get(url, params={'asset_type': asset_type}, timeout=10)
        if r.status_code == 200:
            return r.json().get('central_strike')
    except Exception:
        pass
    return None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_optionboard(asset: str, asset_type_ui: str, series_code: str):
    asset_code, _ = get_asset_code_and_type(asset, asset_type_ui)
    board_data, used_asset_type = None, None
    for at in ['share', 'futures', 'index', 'currency', 'commodity']:
        url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}/optionboard"
        try:
            r = requests.get(url, params={'asset_type': at}, timeout=15)
            if r.status_code == 200:
                board_data = r.json()
                used_asset_type = at
                break
        except Exception:
            continue
    if not board_data:
        raise RuntimeError("Не удалось получить доску опционов")
    board_data['central_strike'] = fetch_central_strike(asset_code, series_code, used_asset_type)
    board_data['series_code'] = series_code
    return board_data


@st.cache_data(ttl=300, show_spinner=False)
def fetch_volatility_graph(asset: str, series_code: str, asset_type_ui: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}/volatility_graph"
    try:
        r = requests.get(url, params={'asset_type': moex_type}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


# ================= Мост HTML ↔ Python =================

def _send_to_iframes(payload: dict, delays=(300, 1000, 2500)):
    delays_js = "\n".join([f"setTimeout(send, {d});" for d in delays])
    js = f"""
    <script>
    (function() {{
      const payload = {json.dumps(payload, ensure_ascii=False)};
      function send() {{
        try {{
          const frames = window.parent.document.querySelectorAll('iframe');
          frames.forEach(f => {{
            try {{ f.contentWindow.postMessage(payload, '*'); }} catch (e) {{}}
          }});
        }} catch (e) {{}}
      }}
      send();
      {delays_js}
    }})();
    </script>
    """
    components.html(js, height=0)


def push_expiry_to_calculator(expiry_str: str, series_code: str = ""):
    _send_to_iframes({
        "type": "setExpiry",
        "value": expiry_str,
        "series_code": series_code,
    })


def push_tv_ticker(ticker_label: str, tv_symbol: str):
    _send_to_iframes({
        "type": "setTicker",
        "ticker": ticker_label,
        "symbol": tv_symbol,
    })


def push_strikes_to_calculator(strikes_iv: list, central_strike):
    _send_to_iframes({
        "type": "setStrikes",
        "strikes": strikes_iv,
        "central": central_strike,
    }, delays=(300, 800, 1500, 2500))


def push_risk_free_rate(rate_value):
    """Отправляет безрисковую ставку в iframe (0 — если None)."""
    payload_value = float(rate_value) if rate_value is not None else 0.0
    _send_to_iframes({
        "type": "setRiskFree",
        "value": payload_value,
    }, delays=(500, 1500, 3000))


def push_dividend_yield(q_buy, q_sell):
    """Отправляет дивидендную доходность (в долях) в iframe."""
    payload = {
        "type": "setDividend",
        "q_buy": float(q_buy) if q_buy is not None else 0.0,
        "q_sell": float(q_sell) if q_sell is not None else 0.0,
    }
    _send_to_iframes(payload, delays=(700, 1700, 3200))


# ================= UI =================

st.title("Калькулятор опционов QCKSLVR TRADING")

calc_html = Path("index.html").read_text(encoding="utf-8")
components.html(calc_html, height=1000, scrolling=True)

st.markdown("---")
st.header("Выберите опционную серию")

if "asset_input" not in st.session_state:
    st.session_state.asset_input = "RTS"
if "asset_type_ui" not in st.session_state:
    st.session_state.asset_type_ui = "Фьючерс"

with st.expander("📖 Справочник инструментов MOEX — кликните по тикеру, "
                 "чтобы подставить его и категорию в поля ниже", expanded=False):
    filter_text = st.text_input(
        "🔍 Поиск по коду или названию",
        key="dict_filter",
        placeholder="GAZP, Сбер, золото…",
    ).strip().lower()

    dict_tabs = st.tabs(list(MOEX_INSTRUMENTS.keys()))
    for tab, (category, items) in zip(dict_tabs, MOEX_INSTRUMENTS.items()):
        with tab:
            filtered = {
                code: (atype, name)
                for code, (atype, name) in items.items()
                if not filter_text
                or filter_text in code.lower()
                or filter_text in name.lower()
            }
            if not filtered:
                st.caption("Ничего не найдено.")
                continue

            n_cols = 4
            cols = st.columns(n_cols)
            for i, (code, (asset_type, name)) in enumerate(filtered.items()):
                with cols[i % n_cols]:
                    if st.button(
                        code,
                        key=f"dict_{category}_{code}",
                        use_container_width=True,
                        help=f"{name} → категория «{asset_type}»",
                    ):
                        st.session_state.asset_input = code
                        st.session_state.asset_type_ui = asset_type
                        st.rerun()
                    st.caption(name)

col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    asset = st.text_input(
        "Базовый актив",
        key="asset_input",
        placeholder="RTS, Si, GAZR…",
    ).strip().upper()
with col2:
    asset_type_ui = st.selectbox(
        "Категория базового актива",
        ["Фьючерс", "Акция", "Валюта", "Товар", "Индекс"],
        key="asset_type_ui",
    )
with col3:
    st.write("")
    load_btn = st.button("Загрузить доску опционов", use_container_width=True)

if st.button("Сбросить кэш MOEX"):
    st.cache_data.clear()
    st.rerun()

if "series_list" not in st.session_state:
    st.session_state.series_list = []

if load_btn and asset:
    try:
        with st.spinner("Загрузка серий..."):
            st.session_state.series_list = fetch_optionseries(asset, asset_type_ui)
    except Exception as e:
        st.error(f"Ошибка загрузки серий: {e}")
        st.session_state.series_list = []

if st.session_state.series_list:
    sorted_series = sorted(
        st.session_state.series_list,
        key=lambda x: x.get("expiry", "")
    )

    option_labels = [
        f"{expiry_marker(s['expiry'])} {s['expiry']} — {s['code']}"
        for s in sorted_series
    ]

    chosen = st.selectbox("Дата экспирации (серия)", option_labels, index=0)
    chosen_idx = option_labels.index(chosen)
    selected = sorted_series[chosen_idx]
    series_code = selected["code"]
    expiry_str = selected["expiry"]

    push_expiry_to_calculator(expiry_str, series_code)

    # --- Безрисковая ставка: только для опционов на акции ---
    if asset_type_ui == "Акция":
        rfr = get_risk_free_rate_for_expiry(expiry_str)
        push_risk_free_rate(rfr)
        if rfr is not None:
            st.caption(f"Безрисковая ставка (G-кривая ОФЗ MOEX): **{rfr:.4f} %**")
        else:
            st.caption("⚠ Не удалось получить ставку из G-кривой — оставлено 0.")
    else:
        push_risk_free_rate(0.0)

    # --- Дивидендная доходность: только для опционов на акции ---
    if asset_type_ui == "Акция":
        spot_buy = None
        spot_sell = None
        try:
            # Пробуем получить значения полей из iframe через query-параметры
            # (если не получится — используем дефолты: цена = 1.0)
            spot_buy = float(st.session_state.get("price_buy", 0) or 0)
            spot_sell = float(st.session_state.get("price_sell", 0) or 0)
        except Exception:
            pass

        if not spot_buy:
            spot_buy = 1.0
        if not spot_sell:
            spot_sell = 1.0

        q_buy, q_sell = get_dividend_yield_for_ticker(
            asset, expiry_str, spot_buy, spot_sell
        )
        push_dividend_yield(q_buy, q_sell)

        if q_buy is not None and q_sell is not None:
            st.caption(
                f"Дивидендная доходность (smart-lab.ru): "
                f"q_buy = **{q_buy:.4f}** ({q_buy*100:.2f} %), "
                f"q_sell = **{q_sell:.4f}** ({q_sell*100:.2f} %)"
            )
        else:
            st.caption("Дивиденды по этому тикеру до экспирации не найдены — q = 0.")
    else:
        push_dividend_yield(0.0, 0.0)

    st.caption(f"Выбрана дата экспирации: **{expiry_str}** "
               f"(серия `{series_code}`)")

    tv_symbol = resolve_tv_ticker(asset, asset_type_ui)
    if tv_symbol:
        push_tv_ticker(asset, tv_symbol)
        st.caption(f"Тикер TradingView: `{tv_symbol}`")
    else:
        st.warning(
            f"⚠️ Для «{asset}» ({asset_type_ui}) не задан тикер TradingView. "
            f"Добавьте его в `TV_TICKER_MAP[\"{asset_type_ui}\"]` в `app.py`."
        )

    try:
        info = fetch_series_info(asset, asset_type_ui, series_code)
        with st.expander("Об опционной серии", expanded=False):
            st.json(info, expanded=True)
    except Exception as e:
        st.warning(f"Не удалось загрузить информацию о серии: {e}")

    try:
        board = fetch_optionboard(asset, asset_type_ui, series_code)
    except Exception as e:
        st.error(f"Не удалось загрузить доску: {e}")
        board = None

    if board:
        calls = board.get('call') or []
        puts = board.get('put') or []
        central = board.get('central_strike')

        strikes = sorted({c['strike'] for c in calls} | {p['strike'] for p in puts})
        c_map = {c['strike']: c for c in calls}
        p_map = {p['strike']: p for p in puts}

        strikes_iv = []
        for k in strikes:
            c = c_map.get(k, {})
            p = p_map.get(k, {})
            iv = c.get('volatility') or p.get('volatility')
            strikes_iv.append({
                "strike": int(k) if float(k).is_integer() else k,
                "iv": float(iv) if iv is not None else None,
            })
        push_strikes_to_calculator(strikes_iv, central)

        rows = []
        for k in strikes:
            c = c_map.get(k, {})
            p = p_map.get(k, {})
            iv = c.get('volatility') or p.get('volatility')
            rows.append({
                "Call_Ticker": c.get('secid', '—'),
                "Call_Rho":   c.get('rho'),
                "Call_Theta": c.get('theta'),
                "Call_Vega":  c.get('vega'),
                "Call_Gamma": c.get('gamma'),
                "Call_Delta": c.get('delta'),
                "Call_Theor": c.get('theorprice'),
                "Call_Last":  c.get('last'),
                "Call_Offer": c.get('offer'),
                "Call_Bid":   c.get('bid'),
                "Strike":     k,
                "IV_%":       iv,
                "Put_Bid":    p.get('bid'),
                "Put_Offer":  p.get('offer'),
                "Put_Last":   p.get('last'),
                "Put_Theor":  p.get('theorprice'),
                "Put_Delta":  p.get('delta'),
                "Put_Gamma":  p.get('gamma'),
                "Put_Vega":   p.get('vega'),
                "Put_Theta":  p.get('theta'),
                "Put_Rho":    p.get('rho'),
                "Put_Ticker": p.get('secid', '—'),
            })
        df = pd.DataFrame(rows)

        def style_row(row):
            strike = row["Strike"]
            is_central = central is not None and abs(strike - central) < 0.01
            call_bg = "#e1e3fb" if is_central else "#dbf3df"
            put_bg  = "#fee5cd" if is_central else "#ffcdce"
            styles = []
            for col in row.index:
                if col.startswith("Call_"):
                    styles.append(f"background-color: {call_bg}")
                elif col.startswith("Put_"):
                    styles.append(f"background-color: {put_bg}")
                elif col in ("Strike", "IV_%") and is_central:
                    styles.append("background-color: #e3e7ec; font-weight: bold")
                else:
                    styles.append("")
            return styles

        column_display = {
            "Call_Ticker": "Тикер",
            "Call_Rho":    "Ро",
            "Call_Theta":  "Тета",
            "Call_Vega":   "Вега",
            "Call_Gamma":  "Гамма",
            "Call_Delta":  "Дельта",
            "Call_Theor":  "Теор.Ц",
            "Call_Last":   "Посл.Ц",
            "Call_Offer":  "Offer",
            "Call_Bid":    "Bid",
            "Strike":      "Страйк",
            "IV_%":        "IV%",
            "Put_Bid":     "Bid",
            "Put_Offer":   "Offer",
            "Put_Last":    "Посл.Ц",
            "Put_Theor":   "Теор.Ц",
            "Put_Delta":   "Дельта",
            "Put_Gamma":   "Гамма",
            "Put_Vega":    "Вега",
            "Put_Theta":   "Тета",
            "Put_Rho":     "Ро",
            "Put_Ticker":  "Тикер",
        }

        st.subheader("Доска опционов")
        st.caption(f"Центральный страйк: **{central if central is not None else 'не определён'}** · "
                   f"всего страйков: {len(df)}")
        st.dataframe(
            df.style
              .apply(style_row, axis=1)
              .format(
                  {"Strike": "{:.0f}", "IV_%": "{:.2f}"},
                  precision=4,
                  na_rep="—",
              ),
            column_config=column_display,
            use_container_width=True,
            height=600,
        )

        try:
            points = fetch_volatility_graph(asset, series_code, asset_type_ui)
        except Exception:
            points = []
        if points:
            strikes_g = [p['strike'] for p in points]
            vols_g = [p['volatility'] for p in points]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=strikes_g, y=vols_g, mode='lines+markers',
                line=dict(color='#2c7da0', width=2),
                fill='tozeroy', fillcolor='rgba(44,125,160,0.1)',
                name='IV, %',
            ))
            fig.update_layout(
                title="Улыбка волатильности",
                xaxis_title="Страйк", yaxis_title="IV, %",
                height=380, margin=dict(l=20, r=20, t=50, b=20),
                xaxis=dict(tickformat=".0f", hoverformat=".0f"),
                yaxis=dict(tickformat=".2f", hoverformat=".2f"),
            )
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Введите тикер базового актива и нажмите «Загрузить серии».")
