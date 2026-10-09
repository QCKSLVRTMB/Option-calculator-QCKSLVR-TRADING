import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import numpy as np
import json
import math
import re
import uuid
import time
import hashlib
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime, date, timedelta
from io import BytesIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

st.set_page_config(
    page_title="MOEX Options & Black-Scholes",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "cache_cleared_v5" not in st.session_state:
    st.cache_data.clear()
    st.session_state["cache_cleared_v5"] = True

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
[data-testid="stForm"] {
    border: 1px solid #cfdfe9 !important;
    border-radius: 12px !important;
    padding: 14px 16px !important;
}
.pos-row-wrap [data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid #e6edf4;
    padding: 2px 0;
}
.pos-row-wrap [data-testid="stHorizontalBlock"]:last-child {
    border-bottom: none;
}
</style>
""", unsafe_allow_html=True)

# ================= MOEX API =================
API_BASE_URL = "https://iss.moex.com/iss/apps/option-calc/v1"

ASSET_TYPE_MAP = {
    'Фьючерс': 'futures', 'Акция': 'share', 'Валюта': 'currency',
    'Товар': 'commodity', 'Индекс': 'index',
}

DEFAULT_COMM_OPTIONS_PCT = 3.0
DEFAULT_COMM_OPTIONS_MIN = 0.02
DEFAULT_COMM_FUTURES_PCT = 0.1
DEFAULT_COMM_STOCKS_PCT  = 0.3

HTML_PLACEHOLDER = "/*__INJECT_PLACEHOLDER__*/{}"

ALERTS_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRKISFld2M8tFEEE1o1Fo5nQgHP6qMmOFu57JDmi-t-Y4Xj67N5SQP9uQ02JW2Ixyd663zewMYY1hfx"
    "/pub?output=xlsx"
)

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
        "Si":       ("Фьючерс", "Доллар США / Рубль (фьючерс)"),
        "Eu":       ("Фьючерс", "Евро / Рубль (фьючерс)"),
        "CNY":      ("Фьючерс", "Юань / Рубль (фьючерс)"),
        "ED":       ("Фьючерс", "Евро / Доллар (фьючерс)"),
        "TRY":      ("Фьючерс", "Турецкая лира / Рубль (фьючерс)"),
        "HKD":      ("Фьючерс", "Гонконгский доллар / Рубль (фьючерс)"),
        "AED":      ("Фьючерс", "Дирхам ОАЭ / Рубль (фьючерс)"),
        "KZT":      ("Фьючерс", "Казахстанский тенге / Рубль (фьючерс)"),
        "AMD":      ("Фьючерс", "Армянский драм / Рубль (фьючерс)"),
        "BYN":      ("Фьючерс", "Белорусский рубль / Рубль (фьючерс)"),
        "AUDU":     ("Фьючерс", "Австралийский доллар / Доллар (фьючерс)"),
        "GBPU":     ("Фьючерс", "Фунт стерлингов / Доллар (фьючерс)"),
        "UCAD":     ("Фьючерс", "Доллар / Канадский доллар (фьючерс)"),
        "UCHF":     ("Фьючерс", "Доллар / Швейцарский франк (фьючерс)"),
        "UJPY":     ("Фьючерс", "Доллар / Японская йена (фьючерс)"),
        "UCNY":     ("Фьючерс", "Доллар / Юань (фьючерс)"),
        "BR":       ("Фьючерс", "Нефть Brent (фьючерс)"),
        "CL":       ("Фьючерс", "Нефть Light Sweet (фьючерс)"),
        "GOLD":     ("Фьючерс", "Золото (фьючерс)"),
        "SILV":     ("Фьючерс", "Серебро (фьючерс)"),
        "PLD":      ("Фьючерс", "Палладий (фьючерс)"),
        "PLT":      ("Фьючерс", "Платина (фьючерс)"),
        "ALMN":     ("Фьючерс", "Алюминий (фьючерс)"),
        "Co":       ("Фьючерс", "Медь (фьючерс)"),
        "Nl":       ("Фьючерс", "Никель (фьючерс)"),
        "Zn":       ("Фьючерс", "Цинк (фьючерс)"),
        "NG":       ("Фьючерс", "Природный газ (фьючерс)"),
        "WHEAT":    ("Фьючерс", "Пшеница (фьючерс)"),
        "SUGR":     ("Фьючерс", "Сахар (фьючерс)"),
        "RTS":      ("Фьючерс", "Индекс РТС (фьючерс)"),
        "MIX":      ("Фьючерс", "Индекс МосБиржи (фьючерс)"),
        "RVI":      ("Фьючерс", "Индекс волатильности RVI (фьючерс)"),
        "RGBI":     ("Фьючерс", "Индекс RGBI (фьючерс)"),
        "MOEXCNY":  ("Фьючерс", "Индекс МосБиржи в юанях (фьючерс)"),
        "MMI":      ("Фьючерс", "Индекс металлов и добычи (фьючерс)"),
        "FNI":      ("Фьючерс", "Индекс финансов (фьючерс)"),
        "OGI":      ("Фьючерс", "Индекс нефти и газа (фьючерс)"),
        "MXI":      ("Фьючерс", "Индекс МосБиржи (мини, фьючерс)"),
        "RTSM":     ("Фьючерс", "Индекс РТС (мини, фьючерс)"),
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

# ================= Тикеры TradingView =================
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


# ================= Предустановленные стратегии =================
PREDEFINED_STRATEGIES = {
    "Long Call": {"category": "Одиночные", "description": "Покупка опциона Call — ставка на рост",
        "strike_order": [], "legs": [{"label": "Страйк (Buy Call)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K"}]},
    "Long Put": {"category": "Одиночные", "description": "Покупка опциона Put — ставка на падение",
        "strike_order": [], "legs": [{"label": "Страйк (Buy Put)", "option": "Put", "side": "Buy", "qty": 1, "strike_group": "K"}]},
    "Short Call": {"category": "Одиночные", "description": "Продажа опциона Call",
        "strike_order": [], "legs": [{"label": "Страйк (Sell Call)", "option": "Call", "side": "Sell", "qty": 1, "strike_group": "K"}]},
    "Short Put": {"category": "Одиночные", "description": "Продажа опциона Put",
        "strike_order": [], "legs": [{"label": "Страйк (Sell Put)", "option": "Put", "side": "Sell", "qty": 1, "strike_group": "K"}]},
    "Bull Call Spread": {"category": "Вертикальные спреды", "description": "Buy Call (низ) + Sell Call (верх)",
        "strike_order": ["K_low", "K_high"], "legs": [
            {"label": "Buy Call (низ)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K_low"},
            {"label": "Sell Call (верх)", "option": "Call", "side": "Sell", "qty": 1, "strike_group": "K_high"}]},
    "Bear Call Spread": {"category": "Вертикальные спреды", "description": "Sell Call (низ) + Buy Call (верх)",
        "strike_order": ["K_low", "K_high"], "legs": [
            {"label": "Sell Call (низ)", "option": "Call", "side": "Sell", "qty": 1, "strike_group": "K_low"},
            {"label": "Buy Call (верх)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K_high"}]},
    "Bull Put Spread": {"category": "Вертикальные спреды", "description": "Sell Put (верх) + Buy Put (низ)",
        "strike_order": ["K_low", "K_high"], "legs": [
            {"label": "Buy Put (низ)", "option": "Put", "side": "Buy", "qty": 1, "strike_group": "K_low"},
            {"label": "Sell Put (верх)", "option": "Put", "side": "Sell", "qty": 1, "strike_group": "K_high"}]},
    "Bear Put Spread": {"category": "Вертикальные спреды", "description": "Buy Put (верх) + Sell Put (низ)",
        "strike_order": ["K_low", "K_high"], "legs": [
            {"label": "Sell Put (низ)", "option": "Put", "side": "Sell", "qty": 1, "strike_group": "K_low"},
            {"label": "Buy Put (верх)", "option": "Put", "side": "Buy", "qty": 1, "strike_group": "K_high"}]},
    "Long Butterfly (Call)": {"category": "Бабочки", "description": "Buy 1 Call + Sell 2 Call + Buy 1 Call",
        "strike_order": ["K1", "K2", "K3"], "legs": [
            {"label": "Buy Call (K1 — низ)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K1"},
            {"label": "Sell Call ×2 (K2)", "option": "Call", "side": "Sell", "qty": 2, "strike_group": "K2"},
            {"label": "Buy Call (K3 — верх)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K3"}]},
    "Long Straddle": {"category": "Straddle / Strangle", "description": "Buy Call + Buy Put на одном страйке",
        "strike_order": [], "legs": [
            {"label": "Страйк (Buy Call + Buy Put)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put", "side": "Buy", "qty": 1, "strike_group": "K"}]},
    "Short Straddle": {"category": "Straddle / Strangle", "description": "Sell Call + Sell Put на одном страйке",
        "strike_order": [], "legs": [
            {"label": "Страйк (Sell Call + Sell Put)", "option": "Call", "side": "Sell", "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put", "side": "Sell", "qty": 1, "strike_group": "K"}]},
    "Iron Condor": {"category": "Кондоры", "description": "Buy Put + Sell Put + Sell Call + Buy Call",
        "strike_order": ["K1", "K2", "K3", "K4"], "legs": [
            {"label": "Buy Put (K1)", "option": "Put", "side": "Buy", "qty": 1, "strike_group": "K1"},
            {"label": "Sell Put (K2)", "option": "Put", "side": "Sell", "qty": 1, "strike_group": "K2"},
            {"label": "Sell Call (K3)", "option": "Call", "side": "Sell", "qty": 1, "strike_group": "K3"},
            {"label": "Buy Call (K4)", "option": "Call", "side": "Buy", "qty": 1, "strike_group": "K4"}]},
}


# ================= Устойчивый HTTP-клиент к ISS =================
def _make_iss_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.6,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": "MOEX-Options-Calc/1.0",
                      "Accept": "application/json, */*"})
    return s


_ISS_SESSION = _make_iss_session()


def iss_get(url, params=None, timeout=20):
    for attempt in range(3):
        try:
            r = _ISS_SESSION.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException:
            if attempt == 2:
                return None
            time.sleep(0.7 * (attempt + 1))
    return None


def iss_get_json(url, params=None, timeout=20):
    r = iss_get(url, params=params, timeout=timeout)
    if r is None:
        return None
    try:
        return r.json()
    except Exception:
        return None


_FAILED_UNTIL = {}


def _is_failed_recently(key: str, cooldown_sec: int = 60) -> bool:
    now = time.time()
    ts = _FAILED_UNTIL.get(key)
    return ts is not None and now < ts


def _mark_failed(key: str, cooldown_sec: int = 60):
    _FAILED_UNTIL[key] = time.time() + cooldown_sec


# ================= Канонизация тикера =================
def resolve_canonical_asset_code(user_input: str, asset_type_ui: str = None) -> str:
    if not user_input:
        return user_input
    s = user_input.strip()
    if not s:
        return s
    s_upper = s.upper()
    if asset_type_ui and asset_type_ui in MOEX_INSTRUMENTS:
        items = MOEX_INSTRUMENTS[asset_type_ui]
        for code in items.keys():
            if code.upper() == s_upper:
                return code
        return s_upper
    for cat_items in MOEX_INSTRUMENTS.values():
        for code in cat_items.keys():
            if code.upper() == s_upper:
                return code
    return s_upper


# ================= Комиссии =================
def calc_commission(premium, instrument_type="Опцион",
                    min_comm_options=0.02,
                    comm_options_pct=3.0,
                    comm_futures_pct=0.1,
                    comm_stocks_pct=0.3):
    if premium is None or premium <= 0:
        return 0.0
    t = (instrument_type or "").strip().lower()
    if t in ("опцион", "option"):
        return max((comm_options_pct / 100.0) * premium, min_comm_options)
    if t in ("фьючерс", "futures"):
        return (comm_futures_pct / 100.0) * premium
    if t in ("акция", "stock", "share", "облигация", "etf", "bond"):
        return (comm_stocks_pct / 100.0) * premium
    return 0.0


def _calc_comm_ui(premium, instr_type="Опцион"):
    cop = st.session_state.get("cop_inp", DEFAULT_COMM_OPTIONS_PCT)
    cmo = st.session_state.get("cmo_inp", DEFAULT_COMM_OPTIONS_MIN)
    cfp = st.session_state.get("cfp_inp", DEFAULT_COMM_FUTURES_PCT)
    csp = st.session_state.get("csp_inp", DEFAULT_COMM_STOCKS_PCT)
    return calc_commission(premium, instrument_type=instr_type,
                           min_comm_options=cmo,
                           comm_options_pct=cop,
                           comm_futures_pct=cfp,
                           comm_stocks_pct=csp)


# ================= Дивиденды (smart-lab.ru) =================
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_dividends_smartlab() -> pd.DataFrame:
    url = "https://smart-lab.ru/dividends/index/order_by_ticker/desc/"
    headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36")}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception:
        return pd.DataFrame(columns=["ticker", "dividend_rub", "record_date", "stock_price"])
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, flags=re.DOTALL | re.IGNORECASE)
    records = []
    for row_html in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 10:
            continue
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        ticker = clean[1].upper() if len(clean) > 1 else ""
        if not ticker or not re.match(r'^[A-Z0-9]+$', ticker):
            continue
        try:
            dividend = float(clean[3].replace(",", ".").replace(" ", ""))
        except Exception:
            continue
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
        stock_price = None
        try:
            price_str = clean[9].replace(",", ".").replace(" ", "").replace("₽", "")
            stock_price = float(price_str)
        except Exception:
            pass
        records.append({"ticker": ticker, "dividend_rub": dividend,
                        "record_date": record_date, "stock_price": stock_price})
    return pd.DataFrame(records)


def get_dividend_yield_for_ticker(ticker: str, expiry_str: str):
    df = fetch_dividends_smartlab()
    if df.empty:
        return None, None, None
    try:
        exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except Exception:
        return None, None, None
    candidates = df[
        (df["ticker"] == ticker.upper())
        & (df["record_date"] <= exp_date)
        & (df["record_date"] >= date.today())
    ]
    if candidates.empty:
        return None, None, None
    row = candidates.sort_values("record_date").iloc[0]
    div = float(row["dividend_rub"])
    price = row["stock_price"]
    if price is None or price <= 0:
        return None, None, None
    return div / price, float(price), row["record_date"]


# ================= G-кривая ОФЗ =================
@st.cache_data(ttl=600, show_spinner=False)
def fetch_g_curve_params():
    if _is_failed_recently("g_curve", cooldown_sec=30):
        return None
    url = "https://iss.moex.com/iss/engines/stock/zcyc/securities.json"
    data = iss_get_json(url, timeout=15)
    if data is None:
        _mark_failed("g_curve", cooldown_sec=30)
        return None
    params = data.get('params', {})
    columns = params.get('columns', [])
    values = params.get('data', [])
    if not columns or not values:
        _mark_failed("g_curve", cooldown_sec=30)
        return None
    df = pd.DataFrame(values, columns=columns)
    row = df.iloc[0]
    try:
        return {'beta0': float(row['B1']), 'beta1': float(row['B2']),
                'beta2': float(row['B3']), 'tau': float(row['T1']),
                'g': [float(row[f'G{i}']) for i in range(1, 10)]}
    except Exception:
        return None


_GC_A = [0.0, 0.4, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0]
_GC_B = [0.4, 0.6, 1.0, 1.6, 2.4, 4.0, 6.4, 9.6, 16.0]


def g_curve_yield(t_years: float, p: dict):
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


# ================= LAST-цена БА с ISS =================
@st.cache_data(ttl=10, show_spinner=False)
def fetch_last_price_from_iss(secid: str, asset_type_ui: str):
    if not secid:
        return {"last": None, "secid": secid, "source": "—"}
    if asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
        engine, market = "futures", "forts"
    elif asset_type_ui == "Индекс":
        engine, market = "stock", "index"
    else:
        engine, market = "stock", "shares"
    url = (f"https://iss.moex.com/iss/engines/{engine}/markets/{market}"
           f"/securities/{secid}.json")
    data = iss_get_json(url, params={"iss.meta": "off", "iss.only": "marketdata"}, timeout=15)
    if data is None:
        return {"last": None, "secid": secid, "source": "ошибка запроса"}
    md = data.get("marketdata", {})
    cols = md.get("columns", [])
    rows = md.get("data", [])
    if not rows or not cols:
        return {"last": None, "secid": secid, "source": "нет данных"}
    rd = dict(zip(cols, rows[0]))
    for key in ("LAST", "MARKETPRICE", "LCLOSEPRICE",
                "LASTTOPREVPRICE", "OPEN", "SETTLEPRICE"):
        val = rd.get(key)
        if val and val > 0:
            return {"last": float(val), "secid": secid, "source": key}
    return {"last": None, "secid": secid, "source": "нет цены"}


# ================= Загрузка Google Sheets =================
@st.cache_data(ttl=30, show_spinner=False)
def load_google_sheet_cached(sheet_url: str, cache_buster: int):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(sheet_url, headers=headers, timeout=20)
        resp.raise_for_status()
        df = pd.read_excel(BytesIO(resp.content), engine="openpyxl")
        return df, None
    except requests.exceptions.Timeout:
        return pd.DataFrame(), "Таймаут при обращении к Google Sheets"
    except Exception as e:
        return pd.DataFrame(), f"Ошибка загрузки Google Sheets: {e}"


def _normalize_alerts_df(_xls: pd.DataFrame):
    _col_map = {}
    for c in _xls.columns:
        c_str = str(c).strip().lower()
        if "тикер" in c_str:
            _col_map[c] = "Тикер БА"
        elif "категор" in c_str:
            _col_map[c] = "Категория БА"
        elif "покуп" in c_str or "bid" in c_str:
            _col_map[c] = "Уровень покупок"
        elif "продаж" in c_str or "ask" in c_str:
            _col_map[c] = "Уровень продаж"
    _xls = _xls.rename(columns=_col_map)
    required = ["Тикер БА", "Категория БА", "Уровень покупок", "Уровень продаж"]
    missing = [c for c in required if c not in _xls.columns]
    if missing:
        return pd.DataFrame(), f"В таблице нет колонок: {', '.join(missing)}"
    _xls["Уровень покупок"] = pd.to_numeric(_xls["Уровень покупок"], errors="coerce")
    _xls["Уровень продаж"] = pd.to_numeric(_xls["Уровень продаж"], errors="coerce")
    _xls = _xls.dropna(subset=["Тикер БА", "Уровень покупок", "Уровень продаж"])
    return _xls, None


def _get_engine_market(asset_type_ui: str):
    if asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
        return "futures", "forts"
    if asset_type_ui == "Индекс":
        return "stock", "index"
    return "stock", "shares"


# ================= Resolve secid =================
@st.cache_data(ttl=86400, show_spinner=False)
def resolve_underlying_secid(asset_code: str, asset_type_ui: str):
    if asset_type_ui == "Акция":
        return asset_code.upper()
    if asset_type_ui == "Индекс":
        idx_map = {"RTS": "RTSI", "MIX": "IMOEX"}
        return idx_map.get(asset_code.upper(), asset_code.upper())
    if asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
        url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
        data = iss_get_json(url, params={"iss.meta": "off", "iss.only": "securities"}, timeout=20)
        if data is None:
            return None
        try:
            cols = data["securities"]["columns"]
            rows = data["securities"]["data"]
            df = pd.DataFrame(rows, columns=cols)
            if "ASSETCODE" not in df.columns:
                return None
            df = df[df["ASSETCODE"] == asset_code.upper()]
            if df.empty:
                return None
            today_str = date.today().isoformat()
            if "LASTTRADEDATE" in df.columns:
                df_live = df[df["LASTTRADEDATE"] >= today_str]
                df = df_live if not df_live.empty else df
                df = df.dropna(subset=["LASTTRADEDATE"])
                df = df.sort_values("LASTTRADEDATE")
            return df.iloc[0]["SECID"] if not df.empty else None
        except Exception:
            return None
    return asset_code.upper()


# ================= Данные БА с ISS =================
@st.cache_data(ttl=600, show_spinner=False)
def fetch_futures_info_iss(secid: str):
    if not secid:
        return None
    url = f"https://iss.moex.com/iss/engines/futures/markets/forts/securities/{secid}.json"
    params = {"iss.meta": "off", "iss.only": "securities,marketdata"}
    data = iss_get_json(url, params=params, timeout=15)
    if data is None:
        return None
    result = {"last": None, "expiration": None, "go": None, "secid": secid}
    sec = data.get("securities", {})
    if sec.get("data"):
        rd = dict(zip(sec["columns"], sec["data"][0]))
        for key in ("LASTTRADEDATE", "LASTDELDATE"):
            if rd.get(key):
                try:
                    result["expiration"] = str(rd[key])
                except Exception:
                    pass
                break
    md = data.get("marketdata", {})
    if md.get("data"):
        rd = dict(zip(md["columns"], md["data"][0]))
        for key in ("LAST", "MARKETPRICE", "LCLOSEPRICE",
                    "LASTTOPREVPRICE", "OPEN", "SETTLEPRICE"):
            v = rd.get(key)
            if v and v > 0:
                result["last"] = float(v)
                break
    return result


@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_info_iss(secid: str):
    if not secid:
        return None
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{secid}.json"
    params = {"iss.meta": "off", "iss.only": "securities,marketdata"}
    data = iss_get_json(url, params=params, timeout=15)
    if data is None:
        return None
    result = {"last": None, "shortname": None, "secid": secid}
    sec = data.get("securities", {})
    if sec.get("data"):
        rd = dict(zip(sec["columns"], sec["data"][0]))
        result["shortname"] = rd.get("SHORTNAME")
        for key in ("LAST", "PREVPRICE", "PREVLEGALCLOSEPRICE"):
            v = rd.get(key)
            if v and v > 0:
                result["last"] = float(v)
                break
    md = data.get("marketdata", {})
    if md.get("data"):
        rd = dict(zip(md["columns"], md["data"][0]))
        for key in ("LAST", "MARKETPRICE", "LCLOSEPRICE",
                    "LASTTOPREVPRICE", "OPEN"):
            v = rd.get(key)
            if v and v > 0:
                result["last"] = float(v)
                break
    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_index_info_iss(secid: str):
    if not secid:
        return None
    url = f"https://iss.moex.com/iss/engines/stock/markets/index/securities/{secid}.json"
    params = {"iss.meta": "off", "iss.only": "securities,marketdata"}
    data = iss_get_json(url, params=params, timeout=15)
    if data is None:
        return None
    result = {"last": None, "secid": secid, "expiration": None}
    md = data.get("marketdata", {})
    if md.get("data"):
        rd = dict(zip(md["columns"], md["data"][0]))
        for key in ("CURRENTVALUE", "LASTVALUE", "LAST", "LCLOSEPRICE", "OPEN"):
            v = rd.get(key)
            if v and v > 0:
                result["last"] = float(v)
                break
    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ba_iss_info(secid: str, asset_type_ui: str):
    if asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
        return fetch_futures_info_iss(secid)
    elif asset_type_ui == "Индекс":
        return fetch_index_info_iss(secid)
    return fetch_stock_info_iss(secid)


# ================= Список контрактов фьючерса =================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_futures_contracts_list(asset_code: str):
    if not asset_code:
        return []
    url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
    data = iss_get_json(url, params={"iss.meta": "off", "iss.only": "securities"}, timeout=20)
    if data is None:
        return []
    try:
        cols = data["securities"]["columns"]
        rows = data["securities"]["data"]
        df = pd.DataFrame(rows, columns=cols)
        if "ASSETCODE" not in df.columns:
            return []
        df = df[df["ASSETCODE"] == asset_code.upper()]
        if df.empty:
            return []
        if "LASTTRADEDATE" in df.columns:
            df = df.dropna(subset=["LASTTRADEDATE"])
            today_str = date.today().isoformat()
            df = df[df["LASTTRADEDATE"] >= today_str]
        df = df.sort_values("LASTTRADEDATE")
        result = []
        for _, row in df.iterrows():
            secid = str(row.get("SECID", "")).strip()
            ltd = str(row.get("LASTTRADEDATE", "")).strip()
            shortname = str(row.get("SHORTNAME", secid)).strip()
            if secid and ltd and ltd >= "2000-01-01":
                result.append({"secid": secid, "expiration": ltd, "shortname": shortname})
        return result
    except Exception:
        return []


# ================= Паритет опционов =================
def apply_parity_delta(position: dict) -> dict:
    if position.get("Тип инструмента") == "БА" or position.get("Опцион") == "БА":
        qty = int(position.get("Кол-во", 0))
        sign = 1 if qty >= 0 else -1
        position["Дельта"] = float(sign)
        position["Гамма"]  = 0.0
        position["Вега"]   = 0.0
        position["Тета"]   = 0.0
        position["Ро"]     = 0.0
    return position


# ================= Оповещения: search & cache =================
def find_alert_levels(ticker: str, category: str = None):
    df = st.session_state.get("alerts_df")
    if df is None or df.empty:
        return {"buy": None, "sell": None, "found": False}

    _cache_key = f"{ticker.upper().strip()}|{category or ''}"
    _cache = st.session_state.get("_alert_levels_cache")
    if _cache is None:
        _cache = {}
        st.session_state["_alert_levels_cache"] = _cache
    if _cache_key in _cache:
        return _cache[_cache_key]

    tk = ticker.upper().strip()
    try:
        mask = df["Тикер БА"].astype(str).str.upper().str.strip() == tk
        if category and "Категория БА" in df.columns:
            mask_cat = df["Категория БА"].astype(str).str.strip() == category
            rows = df[mask & mask_cat]
            if rows.empty:
                rows = df[mask]
        else:
            rows = df[mask]
        if rows.empty:
            result = {"buy": None, "sell": None, "found": False}
        else:
            row = rows.iloc[0]
            result = {"buy": float(row["Уровень покупок"]),
                      "sell": float(row["Уровень продаж"]),
                      "found": True}
    except Exception:
        result = {"buy": None, "sell": None, "found": False}

    _cache[_cache_key] = result
    return result


def get_alert_assets_list():
    """Список активов из листа оповещений для выпадающего списка."""
    df = st.session_state.get("alerts_df")
    if df is None or df.empty:
        return []
    try:
        items = []
        seen = set()
        for _, row in df.iterrows():
            tk = str(row["Тикер БА"]).strip().upper()
            cat = str(row["Категория БА"]).strip()
            key = f"{tk}|{cat}"
            if key in seen:
                continue
            seen.add(key)
            items.append({"ticker": tk, "category": cat})
        items.sort(key=lambda x: (x["ticker"], x["category"]))
        return items
    except Exception:
        return []


# ================= MOEX API: опционы =================
@st.cache_data(ttl=600, show_spinner=False)
def get_asset_code_and_type(asset_input: str, asset_type_ui: str):
    moex_type = ASSET_TYPE_MAP.get(asset_type_ui, 'futures')
    code_to_fetch = asset_input
    s_upper = asset_input.strip().upper()
    if asset_type_ui == "Индекс":
        idx_map = {"RTS": "RTSI", "MIX": "IMOEX"}
        code_to_fetch = idx_map.get(s_upper, s_upper)
    elif asset_type_ui == "Акция":
        code_to_fetch = s_upper
    return code_to_fetch, moex_type


@st.cache_data(ttl=300, show_spinner=False)
def fetch_optionseries(asset: str, asset_type_ui: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries"
    data = iss_get_json(url, params={'asset_type': moex_type}, timeout=15)
    if data is None:
        return []
    series = []
    if isinstance(data, list):
        for item in data:
            if 'optionseries_code' in item and 'expiration_date' in item:
                series.append({'code': item['optionseries_code'],
                               'expiry': item['expiration_date']})
    elif isinstance(data, dict) and 'data' in data:
        for item in data['data']:
            if 'optionseries_code' in item and 'expiration_date' in item:
                series.append({'code': item['optionseries_code'],
                               'expiry': item['expiration_date']})
    return series


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_series_for_asset(asset: str, asset_type_ui: str):
    series = fetch_optionseries(asset, asset_type_ui)
    if not series:
        return []
    return sorted(series, key=lambda x: x.get("expiry", ""))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_series_info(asset: str, asset_type_ui: str, series_code: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}"
    r = iss_get(url, params={'asset_type': moex_type}, timeout=15)
    if r is None or r.status_code != 200:
        r = iss_get(url, timeout=15)
    if r is None:
        return {}
    try:
        data = r.json()
    except Exception:
        return {}
    translated = {
        "Опционная серия": data.get('optionseries_code', '—'),
        "Базовый актив": data.get('asset_code', '—'),
        "Тип БА": data.get('asset_type', '—'),
        "Тикер": data.get('futures_code', '—'),
        "Тип серии": data.get('series_type', '—'),
        "Дата исполнения": data.get('expiration_date', '—'),
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


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_optionboard_raw(asset_code: str, series_code: str, asset_type: str):
    for at in [asset_type, 'share', 'futures', 'index', 'currency', 'commodity']:
        url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}/optionboard"
        data = iss_get_json(url, params={'asset_type': at}, timeout=15)
        if data is not None:
            return data
    return None


def fetch_central_strike(asset_code, series_code, asset_type):
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}"
    data = iss_get_json(url, params={'asset_type': asset_type}, timeout=15)
    if data is not None:
        cs = data.get('central_strike')
        if cs:
            try:
                return float(cs)
            except (TypeError, ValueError):
                pass
    try:
        board = _fetch_optionboard_raw(asset_code, series_code, asset_type)
        if board:
            calls = board.get('call') or []
            puts = board.get('put') or []
            c_map = {c['strike']: c for c in calls
                     if c.get('theorprice') and c.get('strike') is not None}
            p_map = {p['strike']: p for p in puts
                     if p.get('theorprice') and p.get('strike') is not None}
            common = sorted(set(c_map.keys()) & set(p_map.keys()))
            fs_est = []
            for k in common:
                ct = c_map[k]['theorprice']
                pt = p_map[k]['theorprice']
                if ct and pt and ct > 0 and pt > 0:
                    fs_est.append(ct - pt + float(k))
            if fs_est:
                fs_est.sort()
                f_current = fs_est[len(fs_est) // 2]
                all_strikes = list(c_map.keys()) | list(p_map.keys())
                if all_strikes:
                    return float(min(all_strikes,
                                     key=lambda s: abs(float(s) - f_current)))
    except Exception:
        pass
    return None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_optionboard(asset: str, asset_type_ui: str, series_code: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    board_data, used_asset_type = None, None
    tried = []
    for at in [moex_type, 'share', 'futures', 'index', 'currency', 'commodity']:
        if at in tried:
            continue
        tried.append(at)
        url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}/optionboard"
        data = iss_get_json(url, params={'asset_type': at}, timeout=15)
        if data is not None:
            board_data = data
            used_asset_type = at
            break
    if not board_data:
        raise RuntimeError("Не удалось получить доску опционов")
    cs = None
    try:
        _s_info = fetch_series_info(asset, asset_type_ui, series_code)
        _cs_raw = _s_info.get("Центральный страйк")
        if _cs_raw not in (None, "—", ""):
            cs = float(_cs_raw)
    except Exception:
        cs = None
    if cs is None:
        cs = fetch_central_strike(asset_code, series_code, used_asset_type)
    board_data['central_strike'] = cs
    board_data['series_code'] = series_code
    return board_data


@st.cache_data(ttl=300, show_spinner=False)
def fetch_volatility_graph(asset: str, series_code: str, asset_type_ui: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}/volatility_graph"
    data = iss_get_json(url, params={'asset_type': moex_type}, timeout=15)
    return data if data is not None else []


@st.cache_data(ttl=300, show_spinner=False)
def fetch_series_overview(asset: str, asset_type_ui: str):
    """Сводная таблица по всем сериям: тип, экспирация, объём, ОИ, изменение."""
    series_list = fetch_optionseries(asset, asset_type_ui)
    if not series_list:
        return pd.DataFrame()
    rows = []
    today = date.today()
    for s in series_list:
        info = fetch_series_info(asset, asset_type_ui, s["code"])
        if not info:
            continue
        call_info = info.get("Опционы Call", {}) or {}
        put_info  = info.get("Опционы Put",  {}) or {}
        vol_rub   = (float(call_info.get("Объем (руб.)", 0) or 0)
                     + float(put_info.get("Объем (руб.)", 0) or 0))
        vol_contr = (float(call_info.get("Контрактов", 0) or 0)
                     + float(put_info.get("Контрактов", 0) or 0))
        oi        = (float(call_info.get("Открытых позиций", 0) or 0)
                     + float(put_info.get("Открытых позиций", 0) or 0))
        oi_change = (float(call_info.get("ОИ изменение", 0) or 0)
                     + float(put_info.get("ОИ изменение", 0) or 0))
        series_type = str(info.get("Тип серии", "—")).strip().upper()
        _map_type = {
            "WEEKLY": "W", "W": "W", "НЕДЕЛЬНАЯ": "W",
            "MONTHLY": "M", "M": "M", "МЕСЯЧНАЯ": "M",
            "QUARTERLY": "Q", "Q": "Q", "КВАРТАЛЬНАЯ": "Q",
        }
        series_type_short = _map_type.get(series_type, series_type[:1] or "—")
        expiry = info.get("Дата исполнения", s.get("expiry", "—"))
        try:
            d = datetime.strptime(expiry, "%Y-%m-%d").date()
            days_to = (d - today).days
            expiry_disp = f"{d.strftime('%Y-%m-%d')} ({days_to})"
        except Exception:
            days_to = None
            expiry_disp = expiry
        rows.append({
            "БА":            asset,
            "Тип":           series_type_short,
            "Экспирация":    expiry_disp,
            "_expiry_raw":   expiry,
            "_days_to":      days_to,
            "Объём, ₽":      vol_rub,
            "Об.контр.":     vol_contr,
            "Откр.поз.":     oi,
            "Изменение, ₽":  oi_change,
            "_series_code":  s["code"],
        })
    return pd.DataFrame(rows)


# ================= Бары с MOEX =================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_bars(secid, interval=24, days=180, engine="futures", market="forts"):
    if not secid:
        return pd.DataFrame()
    end = datetime.now()
    start = end - timedelta(days=days)
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/securities/{secid}/candles.json"
    params = {"from": start.strftime("%Y-%m-%d"),
              "till": end.strftime("%Y-%m-%d"),
              "interval": interval, "iss.meta": "off"}
    data = iss_get_json(url, params=params, timeout=20)
    if data is None:
        return pd.DataFrame()
    cols = data.get("candles", {}).get("columns", [])
    rows = data.get("candles", {}).get("data", [])
    if not rows or not cols:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=cols)
    df["begin"] = pd.to_datetime(df["begin"], errors="coerce")
    df = df.dropna(subset=["begin", "open", "high", "low", "close"])
    df = df[df["begin"] >= pd.Timestamp("2000-01-01")]
    df = df[(df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)]
    df = df.sort_values("begin").reset_index(drop=True)
    return df


@st.cache_data(ttl=10, show_spinner=False)
def get_last_close_price(secid: str, engine: str, market: str):
    if not secid:
        return None
    end = datetime.now()
    start = end - timedelta(days=7)
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/securities/{secid}/candles.json"
    params = {"from": start.strftime("%Y-%m-%d"),
              "till": end.strftime("%Y-%m-%d"),
              "interval": 24, "iss.meta": "off"}
    data = iss_get_json(url, params=params, timeout=15)
    if data is None:
        return None
    cols = data.get("candles", {}).get("columns", [])
    rows = data.get("candles", {}).get("data", [])
    if not rows or not cols:
        return None
    df = pd.DataFrame(rows, columns=cols)
    if "close" not in df.columns:
        return None
    df = df.dropna(subset=["close"])
    df = df[df["close"] > 0]
    if df.empty:
        return None
    try:
        return float(df.iloc[-1]["close"])
    except Exception:
        return None


# ================= Payoff-расчёты =================
def _months_between(d1: date, d2: date) -> float:
    return max((d2 - d1).days, 0) / 365.0


def _bs_price_np(S, K, T, r_pct, vol_pct, q_pct, opt_type):
    if T <= 0 or S <= 0 or K <= 0 or vol_pct <= 0:
        return max(0.0, S - K) if opt_type == "call" else max(0.0, K - S)
    r = r_pct / 100.0
    q = q_pct / 100.0
    sigma = vol_pct / 100.0
    sqrtT = math.sqrt(T)
    try:
        d1 = (math.log(S / K) + (r - q + sigma * sigma / 2) * T) / (sigma * sqrtT)
        d2 = d1 - sigma * sqrtT
        nd1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
        nd2 = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))
        if opt_type == "call":
            return S * math.exp(-q * T) * nd1 - K * math.exp(-r * T) * nd2
        return K * math.exp(-r * T) * (1 - nd2) - S * math.exp(-q * T) * (1 - nd1)
    except Exception:
        return max(0.0, S - K) if opt_type == "call" else max(0.0, K - S)


def compute_payoff(positions, S_values, comm_func=None, anchor_expiry: str = None,
                   pricing_date: str = None, vol_default: float = 20.0,
                   r_default: float = 0.0, q_default: float = 0.0):
    S = np.asarray(S_values, dtype=float)
    pnl = np.zeros_like(S)
    all_expiries = []
    for p in positions:
        exp_str = p.get("Эксп.", "—")
        if exp_str and exp_str != "—":
            try:
                d = datetime.strptime(exp_str, "%Y-%m-%d").date()
                all_expiries.append(d)
            except Exception:
                pass
    if anchor_expiry:
        try:
            anchor_date = datetime.strptime(anchor_expiry, "%Y-%m-%d").date()
        except Exception:
            anchor_date = max(all_expiries) if all_expiries else date.today()
    else:
        anchor_date = max(all_expiries) if all_expiries else date.today()

    for p in positions:
        if not p.get("visible", True):
            continue
        qty = int(p.get("Кол-во", 0))
        entry = float(p.get("Цена", 0))
        _instr = p.get("Тип инструмента", "Опцион")
        com = comm_func(entry, _instr) if comm_func else 0.0
        if p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА":
            pnl += (S - entry) * qty
            continue
        K = float(p["Страйк"]) if p.get("Страйк") is not None else 0
        if K == 0:
            continue
        leg_expiry_str = p.get("Эксп.", "—")
        leg_expiry = None
        if leg_expiry_str and leg_expiry_str != "—":
            try:
                leg_expiry = datetime.strptime(leg_expiry_str, "%Y-%m-%d").date()
            except Exception:
                leg_expiry = None
        if leg_expiry is None:
            intrinsic = np.maximum(0, S - K) if p["Опцион"] == "Call" else np.maximum(0, K - S)
            pnl += (intrinsic - entry - com) * qty
            continue
        if leg_expiry <= anchor_date:
            intrinsic = np.maximum(0, S - K) if p["Опцион"] == "Call" else np.maximum(0, K - S)
            pnl += (intrinsic - entry - com) * qty
        else:
            T_remaining = _months_between(anchor_date, leg_expiry)
            opt_type = "call" if p["Опцион"] == "Call" else "put"
            vol_leg = float(p.get("_vol", vol_default) or vol_default)
            r_leg = float(p.get("_r", r_default) or r_default)
            q_leg = float(p.get("_q", q_default) or q_default)
            price_at_anchor = np.array([
                _bs_price_np(Si, K, T_remaining, r_leg, vol_leg, q_leg, opt_type)
                for Si in S
            ])
            pnl += (price_at_anchor - entry - com) * qty
    return pnl


def find_breakevens(positions, price_min, price_max, n=500, comm_func=None, anchor_expiry=None):
    prices = np.linspace(price_min, price_max, n)
    pnl = compute_payoff(positions, prices, comm_func=comm_func, anchor_expiry=anchor_expiry)
    be = []
    for i in range(1, len(prices)):
        if pnl[i-1] * pnl[i] < 0:
            denom = pnl[i] - pnl[i-1]
            if abs(denom) > 1e-12:
                x0 = prices[i-1] + (prices[i] - prices[i-1]) * (-pnl[i-1]) / denom
                be.append(float(x0))
    return be


# ================= Биржевой график =================
def render_exchange_chart(df, positions, buy_level, sell_level, strikes, title, key,
                          current_price=None, comm_func=None, anchor_expiry=None):
    if df is None or df.empty:
        st.info(f"Нет данных для {title}")
        return
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.04, row_heights=[0.78, 0.22],
                        specs=[[{"secondary_y": True}], [{"secondary_y": False}]])
    fig.add_trace(go.Ohlc(x=df["begin"], open=df["open"], high=df["high"],
                          low=df["low"], close=df["close"],
                          increasing_line_color="black", decreasing_line_color="black",
                          name="Цена", showlegend=False),
                  row=1, col=1, secondary_y=False)
    fig.add_trace(go.Bar(x=df["begin"], y=df["volume"], marker_color="black",
                         name="Объём", showlegend=False), row=2, col=1)
    price_min = float(df["low"].min()) * 0.97
    price_max = float(df["high"].max()) * 1.03
    if positions:
        be_points = find_breakevens(positions, price_min, price_max,
                                     n=500, comm_func=comm_func, anchor_expiry=anchor_expiry)
        segments = [price_min] + sorted(be_points) + [price_max]
        for i in range(len(segments) - 1):
            seg_start = segments[i]
            seg_end = segments[i + 1]
            mid = (seg_start + seg_end) / 2
            mid_pnl = compute_payoff(positions, [mid], comm_func=comm_func,
                                     anchor_expiry=anchor_expiry)[0]
            color = ("rgba(0,220,80,0.28)" if mid_pnl > 0 else "rgba(255,40,40,0.22)")
            fig.add_shape(type="rect", xref="x domain", x0=0, x1=1,
                          yref="y", y0=seg_start, y1=seg_end,
                          fillcolor=color, line_width=0, layer="below", row=1, col=1)
    else:
        be_points = []
    visible_strikes = []
    if strikes:
        visible_strikes = sorted(float(s) for s in strikes if price_min <= float(s) <= price_max)
        for K in visible_strikes:
            fig.add_hline(y=K, line=dict(color="#9c00ff", width=1, dash="dot"),
                          opacity=0.45, row=1, col=1)
    buy_markers, sell_markers = [], []
    for p in (positions or []):
        if not p.get("visible", True):
            continue
        if p.get("Опцион") not in ("Call", "Put"):
            continue
        qty = int(p.get("Кол-во", 0))
        if qty == 0:
            continue
        K = p.get("Страйк")
        if K is None:
            continue
        code = "C" if p["Опцион"] == "Call" else "P"
        color = "#00a651" if p["Опцион"] == "Call" else "#d32f2f"
        sign = "+" if qty > 0 else "-"
        Ks = f"{int(K)}" if float(K).is_integer() else f"{K:.2f}"
        exp_marker = ""
        exp_str = p.get("Эксп.", "—")
        if exp_str and exp_str != "—":
            try:
                exp_d = datetime.strptime(exp_str, "%Y-%m-%d").date()
                exp_marker = f" [{exp_d.strftime('%m/%y')}]"
            except Exception:
                pass
        entry = {"text": f"{sign}{abs(qty)}{code} {Ks}{exp_marker}", "color": color}
        if qty > 0:
            buy_markers.append(entry)
        else:
            sell_markers.append(entry)

    def _add_level(level, label_txt, line_color, markers):
        fig.add_hline(y=level, line=dict(color=line_color, width=2.5), row=1, col=1)
        fig.add_annotation(x=0.5, y=level, xref="paper", yref="y",
                           text=label_txt, showarrow=False,
                           font=dict(size=10, color=line_color, family="Arial Black"),
                           bgcolor="rgba(255,255,255,0.85)", yshift=11, row=1, col=1)
        for i, m in enumerate(markers[:6]):
            fig.add_annotation(x=0.5, y=level, xref="paper", yref="y",
                               text=m["text"], showarrow=False,
                               font=dict(size=10, color=m["color"],
                                         family="Consolas, monospace"),
                               bgcolor="rgba(255,255,255,0.88)",
                               xshift=80 + i * 72, yshift=11, row=1, col=1)

    if buy_level and buy_level > 0:
        _add_level(buy_level, f"Покупка {buy_level:.2f}", "#9c00ff", buy_markers)
    if sell_level and sell_level > 0:
        _add_level(sell_level, f"Продажа {sell_level:.2f}", "#fb92f0", sell_markers)
    if current_price is not None and current_price > 0:
        fig.add_hline(y=current_price, line=dict(color="#1e88e5", width=2, dash="dash"), row=1, col=1)
        fig.add_annotation(x=0.5, y=current_price, xref="paper", yref="y",
                           text=f"Текущая {current_price:.2f}", showarrow=False,
                           font=dict(size=10, color="#1e88e5", family="Arial Black"),
                           bgcolor="rgba(255,255,255,0.90)",
                           bordercolor="#1e88e5", borderwidth=1, yshift=-11, row=1, col=1)
    for be in be_points:
        fig.add_hline(y=be, line=dict(color="#00a651", width=1.5, dash="dot"), row=1, col=1)
        fig.add_annotation(x=0.5, y=be, xref="paper", yref="y",
                           text=f"БУ {be:.2f}", showarrow=False,
                           font=dict(size=10, color="#00a651", family="Arial Black"),
                           bgcolor="rgba(255,255,255,0.90)",
                           bordercolor="#00a651", borderwidth=1, yshift=10, row=1, col=1)
    fig.add_trace(go.Scatter(x=[df["begin"].iloc[0], df["begin"].iloc[-1]],
                             y=[price_min, price_max], mode="lines",
                             line=dict(width=0), opacity=0, showlegend=False,
                             hoverinfo="skip", name="_right_axis"),
                  row=1, col=1, secondary_y=True)
    fig.update_layout(title=title, height=520,
                      margin=dict(l=20, r=20, t=50, b=20),
                      plot_bgcolor="white", paper_bgcolor="white",
                      hovermode="x unified", showlegend=False)
    if visible_strikes:
        _strike_vals = [float(k) for k in visible_strikes]
        _strike_text = [f"{int(k)}" if float(k).is_integer() else f"{k:.2f}" for k in _strike_vals]
    else:
        _strike_vals = None
        _strike_text = None
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.05)",
                     side="left", row=1, col=1,
                     tickmode="array" if _strike_vals else "auto",
                     tickvals=_strike_vals if _strike_vals else None,
                     ticktext=_strike_text if _strike_text else None,
                     tickfont=dict(size=10, color="#9c00ff"),
                     showspikes=True, spikemode='across', snapsnap='cursor' if False else 'cursor',
                     spikecolor='#888888', spikethickness=1, spikedash='dot')
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.05)",
                     side="left", row=2, col=1,
                     showspikes=True, spikemode='across', spikesnap='cursor',
                     spikecolor='#888888', spikethickness=1, spikedash='dot')
    fig.update_yaxes(side="right", row=1, col=1, secondary_y=True,
                     showgrid=False, zeroline=False,
                     tickfont=dict(size=10, color="#1a3b4f"),
                     showspikes=False, title=None)
    _x_min_val = df["begin"].min()
    _x_max_val = df["begin"].max()
    if pd.notna(_x_min_val) and pd.notna(_x_max_val):
        if len(df) >= 2:
            _diffs = df["begin"].diff().dropna()
            _step = _diffs.median() if not _diffs.empty else pd.Timedelta(days=1)
        else:
            _step = pd.Timedelta(days=1)
        if pd.isna(_step) or _step <= pd.Timedelta(0):
            _step = pd.Timedelta(days=1)
        _x_max_extended = _x_max_val + _step * 15
        fig.update_xaxes(type='date', range=[_x_min_val, _x_max_extended],
                         showgrid=True, gridcolor="rgba(0,0,0,0.05)",
                         rangeslider_visible=False, row=1, col=1,
                         showspikes=True, spikemode='across', spikesnap='cursor',
                         spikecolor='#888888', spikethickness=1, spikedash='dot')
        fig.update_xaxes(type='date', range=[_x_min_val, _x_max_extended],
                         showgrid=True, gridcolor="rgba(0,0,0,0.05)",
                         row=2, col=1,
                         showspikes=True, spikemode='across', spikesnap='cursor',
                         spikecolor='#888888', spikethickness=1, spikedash='dot')
    st.plotly_chart(fig, use_container_width=True, key=key)


# ================= Вспомогательные =================
def _color_call_put(option: str) -> str:
    if option == "Call":
        return f"<span style='color:#00a651; font-weight:700;'>{option}</span>"
    if option == "Put":
        return f"<span style='color:#d32f2f; font-weight:700;'>{option}</span>"
    return option


def _side_from_qty(qty: int) -> str:
    if qty > 0:
        return "Buy"
    if qty < 0:
        return "Sell"
    return "—"


def _side_ui(side: str) -> str:
    return {"Buy": "Покупка", "Sell": "Продажа"}.get(side, side)


def _side_internal(side_ui: str) -> str:
    return {"Покупка": "Buy", "Продажа": "Sell"}.get(side_ui, side_ui)


def _new_position_id() -> str:
    return uuid.uuid4().hex[:8]


def expiry_marker(expiry_str: str) -> str:
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


def format_series_label(expiry_str: str) -> str:
    try:
        d = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return f"{expiry_marker(expiry_str)} {d.strftime('%d.%m.%Y')}"
    except Exception:
        return f"⚪ {expiry_str}"


# ================= Новые функции: alert_targets =================
def _nearest_otm_strike(strikes, level):
    """Ближайший страйк ≥ level (для Покупки Call / Продажи Put).
       Если такого нет — берём максимальный."""
    if not strikes or level is None:
        return None
    s_sorted = sorted(float(s) for s in strikes)
    for k in s_sorted:
        if k >= float(level):
            return k
    return s_sorted[-1]


def _nearest_itm_strike(strikes, level):
    """Ближайший страйк ≤ level (для Продажи Call / Покупки Put).
       Если такого нет — берём минимальный."""
    if not strikes or level is None:
        return None
    s_sorted = sorted((float(s) for s in strikes), reverse=True)
    for k in s_sorted:
        if k <= float(level):
            return k
    return s_sorted[-1]


def _get_board_price_for(board_data, opt_type, strike, side):
    """Цена опциона из доски. side: 'Buy' → offer, 'Sell' → bid.
       Fallback: theorprice, last."""
    if not board_data or strike is None:
        return None
    src = board_data.get('call' if opt_type == 'call' else 'put') or []
    row = next((x for x in src if x.get('strike') == strike), None)
    if row is None:
        return None
    v = row.get('offer') if side == 'Buy' else row.get('bid')
    if v is None or v <= 0:
        v = row.get('theorprice')
    if v is None or v <= 0:
        v = row.get('last')
    try:
        return float(v) if v and v > 0 else None
    except Exception:
        return None


def build_alert_targets(asset, asset_type_ui, series_code, board_data, levels):
    """Структура alert_targets для iframe.

    Правило OTM/ITM:
      • Уровень покупок (Buy) — мы покупаем Call (OTM) / продаём Put (ITM).
        → strikes_buy.call = ближайший OTM (≥ level)
        → strikes_buy.put  = тот же страйк (для Put он ITM)
      • Уровень продаж (Sell) — мы продаём Call (ITM) / покупаем Put (OTM).
        → strikes_sell.call = ближайший ITM (≤ level)
        → strikes_sell.put  = тот же страйк (для Put он OTM)
      Цены:
        • prices_buy.call / prices_buy.put  — по offer (мы покупаем)
        • prices_sell.call / prices_sell.put — по bid  (мы продаём)
    """
    if not board_data:
        return None
    calls = board_data.get('call') or []
    puts = board_data.get('put') or []
    all_strikes = sorted({float(c['strike']) for c in calls if c.get('strike') is not None}
                         | {float(p['strike']) for p in puts if p.get('strike') is not None})
    if not all_strikes:
        return None

    lvl_buy = levels.get("buy") if levels else None
    lvl_sell = levels.get("sell") if levels else None

    K_buy_call  = _nearest_otm_strike(all_strikes, lvl_buy) if lvl_buy else None
    K_buy_put   = K_buy_call   # для Put тот же страйк (ITM)
    K_sell_call = _nearest_itm_strike(all_strikes, lvl_sell) if lvl_sell else None
    K_sell_put  = K_sell_call  # для Put тот же страйк (OTM)

    def _price_map(strike, opt_type, side):
        if strike is None:
            return {}
        p = _get_board_price_for(board_data, opt_type, strike, side)
        return {str(strike): p} if p is not None else {}

    return {
        "asset": asset,
        "atype": asset_type_ui,
        "series_code": series_code,
        "lvl_buy": lvl_buy,
        "lvl_sell": lvl_sell,
        "strikes_buy": {
            "call": K_buy_call,
            "put":  K_buy_put,
        },
        "strikes_sell": {
            "call": K_sell_call,
            "put":  K_sell_put,
        },
        "prices_buy": {
            "call": _price_map(K_buy_call, 'call', 'Buy'),
            "put":  _price_map(K_buy_put,  'put',  'Buy'),
        },
        "prices_sell": {
            "call": _price_map(K_sell_call, 'call', 'Sell'),
            "put":  _price_map(K_sell_put,  'put',  'Sell'),
        },
    }


# ================= postMessage-мост =================
def _send_to_iframes(payload: dict, delays=(300, 1500)):
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
    _send_to_iframes({"type": "setExpiry", "value": expiry_str, "series_code": series_code})


def push_strikes_to_calculator(strikes_iv: list, central_strike):
    _send_to_iframes({"type": "setStrikes", "strikes": strikes_iv, "central": central_strike})


def push_alert_levels(ticker: str, buy_lvl, sell_lvl):
    _send_to_iframes({"type": "setAlertLevels",
                      "ticker": ticker or "",
                      "buy": float(buy_lvl) if buy_lvl is not None else None,
                      "sell": float(sell_lvl) if sell_lvl is not None else None})
    # ================= UI =================
st.title("MOEX Options & Black-Scholes")

def _safe_float_qp(key, default=0.0):
    try:
        return float(st.query_params.get(key, default) or default)
    except (TypeError, ValueError):
        return default

st.session_state["_calc_level_buy"]  = _safe_float_qp("level_buy", 0.0)
st.session_state["_calc_level_sell"] = _safe_float_qp("level_sell", 0.0)
st.session_state["_calc_riskfree"]   = _safe_float_qp("rf_buy", 0.0)
st.session_state["_calc_volatility"] = _safe_float_qp("vol_buy", 0.0)
st.session_state["_calc_dividend"]   = _safe_float_qp("div_buy", 0.0)

# 🔧 Новая последовательность: Калькулятор → Доска → Позиция → Оповещения
tab_calc, tab_board, tab_position, tab_alerts = st.tabs([
    "Калькулятор",
    "Доска опционов и кривая волатильности",
    "Позиция",
    "Оповещения",
])


# ==================================================================
# ============ ВКЛАДКА 1: КАЛЬКУЛЯТОР =============================
# ==================================================================
@st.fragment
def _render_calc_tab():
    st.header("Калькулятор опционов (Black-Scholes)")

    if "calc_asset_ticker" not in st.session_state:
        st.session_state.calc_asset_ticker = "SBER"
    if "calc_asset_category" not in st.session_state:
        st.session_state.calc_asset_category = "Акция"
    if "calc_series_list" not in st.session_state:
        st.session_state.calc_series_list = []
    if "calc_selected_series" not in st.session_state:
        st.session_state.calc_selected_series = ""
    if "calc_selected_expiry" not in st.session_state:
        st.session_state.calc_selected_expiry = ""
    if "calc_autoloaded_for" not in st.session_state:
        st.session_state.calc_autoloaded_for = (None, None)

    # ============================================================
    # ВЫБОР АКТИВА ИЗ ОПОВЕЩЕНИЙ + РУЧНОЙ ВВОД
    # ============================================================
    _alert_assets = get_alert_assets_list()

    with st.expander(
        "Актив и опционная серия",
        expanded=True,
    ):
        # --- Выбор актива из оповещений ---
        if _alert_assets:
            _opts = ["— выберите актив из оповещений —"] + [
                f"{it['ticker']} · {it['category']}" for it in _alert_assets
            ]
            _sel_label = st.selectbox(
                "Актив из оповещений",
                _opts,
                index=0,
                key="calc_asset_select",
                help="Список формируется автоматически из листа оповещений "
                     "(вкладка «Оповещения»).",
            )
            if _sel_label and not _sel_label.startswith("—"):
                _parts = _sel_label.split(" · ", 1)
                if len(_parts) == 2:
                    _tk_sel, _cat_sel = _parts
                    if (st.session_state.calc_asset_ticker != _tk_sel
                            or st.session_state.calc_asset_category != _cat_sel):
                        st.session_state.calc_asset_ticker = _tk_sel
                        st.session_state.calc_asset_category = _cat_sel
                        st.session_state.calc_series_list = []
                        st.session_state.calc_autoloaded_for = (None, None)
        else:
            st.caption("⚠ Лист оповещений не загружен. Перейдите на вкладку "
                       "«Оповещения» или заполните тикер вручную ниже.")

        # --- Ручной ввод (fallback) ---
        _pc1, _pc2 = st.columns([3, 2])
        with _pc1:
            _raw_asset = st.text_input(
                "Базовый актив (тикер)",
                value=st.session_state.calc_asset_ticker,
                key="calc_asset_input",
                placeholder="SBER, GAZP, RTS…",
            ).strip()
        with _pc2:
            _asset_type_ui = st.selectbox(
                "Категория БА",
                ["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"],
                index=["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"].index(
                    st.session_state.calc_asset_category
                    if st.session_state.calc_asset_category in
                    ["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"]
                    else "Акция"
                ),
                key="calc_asset_type_select",
            )

        _asset_canon = resolve_canonical_asset_code(_raw_asset, _asset_type_ui)

        # Обновляем session_state, если пользователь поменял вручную
        if (_asset_canon != st.session_state.calc_asset_ticker
                or _asset_type_ui != st.session_state.calc_asset_category):
            st.session_state.calc_asset_ticker = _asset_canon
            st.session_state.calc_asset_category = _asset_type_ui
            st.session_state.calc_series_list = []
            st.session_state.calc_autoloaded_for = (None, None)

        # --- Автозагрузка серий при смене актива ---
        _loaded_for = st.session_state.get("calc_autoloaded_for", (None, None))
        if (_asset_canon
                and (_asset_canon, _asset_type_ui) != _loaded_for):
            with st.spinner("Загрузка опционных серий…"):
                try:
                    _series_loaded = fetch_optionseries(_asset_canon, _asset_type_ui)
                    st.session_state.calc_series_list = _series_loaded or []
                    st.session_state.calc_autoloaded_for = (_asset_canon, _asset_type_ui)
                    if not _series_loaded:
                        st.warning(
                            f"⚠ ISS не вернул ни одной серии для "
                            f"**{_asset_canon}** ({_asset_type_ui})."
                        )
                except Exception as e:
                    st.error(f"Ошибка загрузки серий: {e}")
                    st.session_state.calc_series_list = []

        # --- Выбор серии ---
        if st.session_state.calc_series_list:
            _sorted_series = sorted(st.session_state.calc_series_list,
                                     key=lambda x: x.get("expiry", ""))
            _option_labels = [format_series_label(s["expiry"]) for s in _sorted_series]
            _chosen = st.selectbox(
                "Дата исполнения",
                _option_labels,
                index=0,
                key="calc_series_select",
            )
            _chosen_idx = _option_labels.index(_chosen)
            _selected = _sorted_series[_chosen_idx]
            st.session_state.calc_selected_series = _selected["code"]
            st.session_state.calc_selected_expiry = _selected["expiry"]

            # Инфо о серии
            try:
                _info = fetch_series_info(_asset_canon, _asset_type_ui,
                                           _selected["code"])
                with st.expander("Об опционной серии", expanded=False):
                    st.json(_info, expanded=True)
            except Exception as _e:
                st.warning(f"Не удалось загрузить информацию о серии: {_e}")

    # ============================================================
    # УРОВНИ ИЗ ОПОВЕЩЕНИЙ + ФОРМИРОВАНИЕ alert_targets
    # ============================================================
    _levels = find_alert_levels(_asset_canon, category=_asset_type_ui)
    if _levels["found"]:
        st.info(
            f"📊 Уровни из оповещений для **{_asset_canon}**: "
            f"покупка = **{_levels['buy']:.2f} ₽** · "
            f"продажа = **{_levels['sell']:.2f} ₽**"
        )
    else:
        st.caption("ℹ Для этого актива уровни из оповещений не найдены. "
                   "Введите уровни в форме калькулятора вручную.")

    # --- Доска для формирования alert_targets ---
    _board_calc = None
    if st.session_state.calc_selected_series:
        try:
            _board_calc = fetch_optionboard(
                _asset_canon,
                _asset_type_ui,
                st.session_state.calc_selected_series,
            )
        except Exception:
            _board_calc = None

    _alert_targets = None
    if _board_calc is not None:
        try:
            _alert_targets = build_alert_targets(
                _asset_canon,
                _asset_type_ui,
                st.session_state.calc_selected_series,
                _board_calc,
                _levels,
            )
        except Exception:
            _alert_targets = None

    # ============================================================
    # ИНЪЕКЦИЯ В index.html
    # ============================================================
    _inject = {
        "strikes": [],
        "central_strike": None,
        "expiry": st.session_state.calc_selected_expiry or "",
        "series_code": st.session_state.calc_selected_series or "",
        "rf_buy": None, "rf_sell": None,
        "div_buy": None, "div_sell": None,
        "vol_buy": 30.0, "vol_sell": 30.0,
        "alerts": {
            "ticker": _asset_canon,
            "buy": _levels.get("buy") if _levels.get("found") else None,
            "sell": _levels.get("sell") if _levels.get("found") else None,
        },
        "alert_targets": _alert_targets,  # 🔧 НОВОЕ
        "market_price": None,
    }

    # Заполняем страйки и central strike, если есть доска
    if _board_calc is not None:
        try:
            _calls_inj = _board_calc.get('call') or []
            _puts_inj = _board_calc.get('put') or []
            _central_inj = _board_calc.get('central_strike')
            if _central_inj is not None:
                try:
                    _inject["central_strike"] = float(_central_inj)
                except (TypeError, ValueError):
                    _inject["central_strike"] = None

            _strikes_set = set()
            _strikes_iv_inj = []
            for _c in _calls_inj:
                if _c.get('strike') is not None:
                    _strikes_set.add(_c['strike'])
            for _p in _puts_inj:
                if _p.get('strike') is not None:
                    _strikes_set.add(_p['strike'])
            for _k in sorted(_strikes_set):
                _c_iv = next((c.get('volatility') for c in _calls_inj
                              if c.get('strike') == _k), None)
                _p_iv = next((p.get('volatility') for p in _puts_inj
                              if p.get('strike') == _k), None)
                _iv = _c_iv or _p_iv
                _k_val = float(_k)
                _strikes_iv_inj.append({
                    "strike": int(_k_val) if _k_val.is_integer() else _k_val,
                    "iv": float(_iv) if _iv is not None else None,
                })
            _inject["strikes"] = _strikes_iv_inj
        except Exception:
            pass

    # Безрисковая ставка и дивиденды для акций
    if _asset_type_ui == "Акция" and st.session_state.calc_selected_expiry:
        try:
            _rf_inj = get_risk_free_rate_for_expiry(
                st.session_state.calc_selected_expiry)
            _inject["rf_buy"] = _rf_inj
            _inject["rf_sell"] = _rf_inj
        except Exception:
            pass
        try:
            _q_inj, _sp_inj, _rd_inj = get_dividend_yield_for_ticker(
                _asset_canon, st.session_state.calc_selected_expiry)
            _inject["div_buy"] = _q_inj
            _inject["div_sell"] = _q_inj
        except Exception:
            pass
    else:
        _inject["rf_buy"] = 0.0
        _inject["rf_sell"] = 0.0
        _inject["div_buy"] = 0.0
        _inject["div_sell"] = 0.0

    # Рыночная цена БА
    try:
        if _asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
            _eng_mkt, _mkt_mkt = "futures", "forts"
        elif _asset_type_ui == "Индекс":
            _eng_mkt, _mkt_mkt = "stock", "index"
        else:
            _eng_mkt, _mkt_mkt = "stock", "shares"

        _mkt_secid = resolve_underlying_secid(_asset_canon, _asset_type_ui)
        if _mkt_secid:
            _close_price = get_last_close_price(_mkt_secid, _eng_mkt, _mkt_mkt)
            if _close_price is not None:
                _inject["market_price"] = _close_price
                st.session_state["quick_und_last_price"] = _close_price
                st.session_state["_current_market_price"] = _close_price
    except Exception:
        pass

    # Рендер калькулятора
    _calc_html_path = Path("index.html")
    calc_html = None
    if not _calc_html_path.exists():
        st.error("Файл `index.html` не найден рядом со скриптом.")
    else:
        try:
            calc_html = _calc_html_path.read_text(encoding="utf-8")
        except Exception as e:
            st.error(f"Не удалось прочитать index.html: {e}")
            calc_html = None

    if calc_html is not None:
        if HTML_PLACEHOLDER not in calc_html:
            st.warning("⚠ В index.html не найден плейсхолдер "
                       "`/*__INJECT_PLACEHOLDER__*/{}`.")
        else:
            _inject_json = json.dumps(_inject, ensure_ascii=False,
                                      default=str, sort_keys=True)
            _inject_hash = hashlib.md5(_inject_json.encode()).hexdigest()
            _cache_key = f"_calc_html_{_inject_hash}"
            if _cache_key not in st.session_state:
                st.session_state[_cache_key] = calc_html.replace(
                    HTML_PLACEHOLDER,
                    _inject_json.replace("</", "<\\/"))
            calc_html = st.session_state[_cache_key]

    if calc_html is None:
        st.info("Калькулятор недоступен.")
    else:
        components.html(calc_html, height=1100, scrolling=True)
        # ==================================================================
# ============ ВКЛАДКА 2: ДОСКА ОПЦИОНОВ (НЕЗАВИСИМАЯ) ============
# ==================================================================
@st.fragment
def _render_board_tab():
    st.header("Доска опционов и кривая волатильности")

    # 🔧 Собственные ключи session_state — не пересекаются с «Калькулятором»
    if "board_asset" not in st.session_state:
        st.session_state.board_asset = "SBER"
    if "board_category" not in st.session_state:
        st.session_state.board_category = "Акция"
    if "board_series_list" not in st.session_state:
        st.session_state.board_series_list = []
    if "board_series_code" not in st.session_state:
        st.session_state.board_series_code = ""
    if "board_expiry" not in st.session_state:
        st.session_state.board_expiry = ""
    if "board_autoloaded_for" not in st.session_state:
        st.session_state.board_autoloaded_for = (None, None)

    # ============================================================
    # ВЫБОР АКТИВА (свой, независимый)
    # ============================================================
    _bc1, _bc2, _bc3 = st.columns([3, 2, 2])
    with _bc1:
        _board_raw_asset = st.text_input(
            "Базовый актив",
            value=st.session_state.board_asset,
            key="board_asset_input",
            placeholder="SBER, GAZP, RTS…",
        ).strip()
    with _bc2:
        _cat_options = ["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"]
        _cat_idx = (_cat_options.index(st.session_state.board_category)
                    if st.session_state.board_category in _cat_options else 0)
        _board_cat = st.selectbox(
            "Категория БА",
            _cat_options,
            index=_cat_idx,
            key="board_category_select",
        )
    with _bc3:
        st.markdown("<div style='height:1.5rem'></div>",
                    unsafe_allow_html=True)
        _btn_reload = st.button("🔄 Обновить серии",
                                 use_container_width=True,
                                 key="board_reload_btn")

    _board_asset = resolve_canonical_asset_code(_board_raw_asset, _board_cat)

    # Смена актива → сброс серий
    if (_board_asset != st.session_state.board_asset
            or _board_cat != st.session_state.board_category):
        st.session_state.board_asset = _board_asset
        st.session_state.board_category = _board_cat
        st.session_state.board_series_list = []
        st.session_state.board_series_code = ""
        st.session_state.board_expiry = ""
        st.session_state.board_autoloaded_for = (None, None)

    # Автозагрузка серий: при смене актива ИЛИ по кнопке
    _board_loaded_for = st.session_state.get("board_autoloaded_for", (None, None))
    _need_reload = (_board_asset
                    and (_board_asset, _board_cat) != _board_loaded_for) \
                   or _btn_reload

    if _need_reload and _board_asset:
        with st.spinner(f"Загрузка серий для {_board_asset}…"):
            try:
                _new_series = fetch_optionseries(_board_asset, _board_cat)
                st.session_state.board_series_list = _new_series or []
                st.session_state.board_autoloaded_for = (_board_asset, _board_cat)
                # Автовыбор первой серии, если ещё не выбрана
                if _new_series and not st.session_state.board_series_code:
                    _s_first = sorted(_new_series,
                                       key=lambda x: x.get("expiry", ""))[0]
                    st.session_state.board_series_code = _s_first["code"]
                    st.session_state.board_expiry = _s_first["expiry"]
                if not _new_series:
                    st.warning(f"⚠ ISS не вернул ни одной серии "
                               f"для **{_board_asset}** ({_board_cat}).")
            except Exception as e:
                st.error(f"Ошибка загрузки серий: {e}")
                st.session_state.board_series_list = []

    st.markdown("---")

    # ============================================================
    # СВОДНАЯ ТАБЛИЦА ВСЕХ СЕРИЙ — клик по строке меняет серию
    # ============================================================
    if not st.session_state.board_series_list:
        st.info("Нет доступных серий. Проверьте тикер и категорию.")
        st.stop()

    st.markdown(f"### Все серии опционов **{_board_asset}** "
                f"({_board_cat.lower()})")

    try:
        _df_overview = fetch_series_overview(_board_asset, _board_cat)
    except Exception as _e:
        _df_overview = pd.DataFrame()
        st.warning(f"Не удалось загрузить сводку серий: {_e}")

    if not _df_overview.empty:
        _df_show = _df_overview.drop(columns=["_series_code",
                                                "_expiry_raw",
                                                "_days_to"])

        _df_styler = _df_show.style.format({
            "Объём, ₽":     "{:,.0f}",
            "Об.контр.":    "{:,.0f}",
            "Откр.поз.":    "{:,.0f}",
            "Изменение, ₽": "{:+,.0f}",
        }, na_rep="—").apply(
            lambda row: [
                ("color: #00a651; font-weight: 700;"
                 if col == "Изменение, ₽" and isinstance(row[col], (int, float))
                 and row[col] > 0
                 else ("color: #d32f2f; font-weight: 700;"
                       if col == "Изменение, ₽"
                       and isinstance(row[col], (int, float))
                       and row[col] < 0
                       else ""))
                for col in row.index
            ], axis=1)

        _sel_event = st.dataframe(
            _df_styler,
            use_container_width=True,
            hide_index=True,
            height=min(120 + 35 * len(_df_show), 420),
            on_select="rerun",
            selection_mode="single-row",
            key="series_overview_table",
        )

        _sel_rows = []
        try:
            _sel_rows = list(getattr(_sel_event.selection, "rows", []) or [])
        except Exception:
            _sel_rows = []

        if _sel_rows:
            _row_idx = _sel_rows[0]
            if 0 <= _row_idx < len(_df_overview):
                _picked = _df_overview.iloc[_row_idx]
                _new_code = _picked["_series_code"]
                _new_expiry = _picked["_expiry_raw"]
                # 🔧 Меняем ТОЛЬКО board_* ключи — калькулятор не трогаем
                if _new_code != st.session_state.board_series_code:
                    st.session_state.board_series_code = _new_code
                    st.session_state.board_expiry = _new_expiry
                    st.rerun()

    st.markdown("---")

    # ============================================================
    # ДОСКА ОПЦИОНОВ ВЫБРАННОЙ СЕРИИ
    # ============================================================
    _active_series_code = st.session_state.board_series_code
    _active_expiry = st.session_state.board_expiry

    if not _active_series_code:
        st.info("Выберите серию из таблицы выше.")
        st.stop()

    # 🔧 Заголовок читает ТЕКУЩЕЕ значение из session_state — обновляется корректно
    st.markdown(
        f"### Доска опционов — **{_board_asset}** "
        f"(дата исполнения: {format_series_label(_active_expiry)})"
    )

    # Уровни из оповещений для выбранного актива
    _board_levels = find_alert_levels(_board_asset, category=_board_cat)
    _board_buy_level = float(_board_levels["buy"] or 0) if _board_levels["found"] else 0.0
    _board_sell_level = float(_board_levels["sell"] or 0) if _board_levels["found"] else 0.0

    # ---- Информационная строка ----
    try:
        _board_for_price = fetch_optionboard(_board_asset, _board_cat,
                                              _active_series_code)
        _calls_p = _board_for_price.get('call') or []
        _puts_p  = _board_for_price.get('put') or []
        _c_map_p = {c['strike']: c for c in _calls_p
                    if c.get('theorprice') and c.get('strike') is not None}
        _p_map_p = {p2['strike']: p2 for p2 in _puts_p
                    if p2.get('theorprice') and p2.get('strike') is not None}
        _common_p = sorted(set(_c_map_p.keys()) & set(_p_map_p.keys()))
        _fs_est = []
        for k in _common_p:
            ct = _c_map_p[k]['theorprice']
            pt = _p_map_p[k]['theorprice']
            if ct and pt and ct > 0 and pt > 0:
                _fs_est.append(ct - pt + float(k))
        _f_current = None
        if _fs_est:
            _fs_est.sort()
            _f_current = _fs_est[len(_fs_est) // 2]
        _central_p = _board_for_price.get('central_strike')
        _strikes_p = sorted({
            c['strike'] for c in _calls_p if c.get('strike') is not None
        } | {
            p2['strike'] for p2 in _puts_p if p2.get('strike') is not None
        })
        _k_min = _strikes_p[0] if _strikes_p else None
        _k_max = _strikes_p[-1] if _strikes_p else None

        _info_parts = []
        if _f_current is not None:
            _info_parts.append(
                f"<span style='color:#1c5a7a; font-weight:700;'>"
                f"Текущая цена БА: {_f_current:,.2f} ₽</span>")
        if _central_p is not None:
            _info_parts.append(
                f"<span style='color:#4a6f8a;'>"
                f"Центральный страйк: <b>{int(_central_p)}</b></span>")
        if _k_min is not None and _k_max is not None:
            _info_parts.append(
                f"<span style='color:#4a6f8a;'>"
                f"Диапазон страйков: <b>{int(_k_min)} … {int(_k_max)}</b> "
                f"({len(_strikes_p)} шт.)</span>")
        if _info_parts:
            st.markdown(
                "<div style='background:#eef6fb; border-radius:12px; "
                "padding:10px 16px; margin-bottom:12px; font-size:.9rem; "
                "display:flex; gap:24px; flex-wrap:wrap; "
                "align-items:center;'>"
                + " · ".join(_info_parts) + "</div>",
                unsafe_allow_html=True)
    except Exception:
        pass

    highlight_on = st.toggle(
        "Раскрасить Bid/Offer (выгодные цены) и греки", value=True)

    try:
        board = fetch_optionboard(_board_asset, _board_cat, _active_series_code)
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

        def nearest_strike(level, strikes_list):
            if level is None or level <= 0 or not strikes_list:
                return None
            return min(strikes_list, key=lambda s: abs(float(s) - float(level)))

        buy_strike_match = nearest_strike(_board_buy_level, strikes)
        sell_strike_match = nearest_strike(_board_sell_level, strikes)

        strikes_iv = []
        for k in strikes:
            c = c_map.get(k, {})
            p = p_map.get(k, {})
            iv = c.get('volatility') or p.get('volatility')
            strikes_iv.append({
                "strike": int(k) if float(k).is_integer() else k,
                "iv": float(iv) if iv is not None else None})
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
                "Put_Ticker": p.get('secid', '—')})
        df = pd.DataFrame(rows)

        def _delta_color(delta):
            if delta is None or not isinstance(delta, (int, float)):
                return None
            d = abs(delta)
            if 0.25 <= d <= 0.45:
                return "#00ff0c"
            if (0.15 <= d < 0.25) or (0.45 < d <= 0.55):
                return "#fcff00"
            return "#ff0000"

        def _theta_color(theta, vega):
            if theta is None or vega is None:
                return None
            if not isinstance(theta, (int, float)) or \
               not isinstance(vega, (int, float)):
                return None
            if abs(vega) < 1e-9:
                return None
            ratio = abs(theta) / abs(vega)
            if ratio > 1.0:
                return "#00ff0c"
            if ratio > 0.5:
                return "#fcff00"
            return "#ff0000"

        def _bid_offer_color(price, theor, is_bid):
            if price is None or theor is None:
                return None
            if not isinstance(price, (int, float)) or \
               not isinstance(theor, (int, float)):
                return None
            if price <= 0 or theor <= 0:
                return None
            if is_bid:
                if price > theor:
                    return "#fb92f0"
            else:
                if price < theor:
                    return "#9c00ff"
            return None

        def style_row(row):
            strike = float(row["Strike"])
            is_central = central is not None and abs(strike - float(central)) < 0.01
            is_buy_strike = (buy_strike_match is not None
                             and abs(strike - float(buy_strike_match)) < 0.01)
            is_sell_strike = (sell_strike_match is not None
                              and abs(strike - float(sell_strike_match)) < 0.01)
            call_bg = "#e1e3fb" if is_central else "#dbf3df"
            put_bg  = "#fee5cd" if is_central else "#ffcdce"

            styles = []
            for col in row.index:
                style = ""
                if col.startswith("Call_"):
                    style = f"background-color: {call_bg}"
                elif col.startswith("Put_"):
                    style = f"background-color: {put_bg}"
                if col == "Strike":
                    if is_sell_strike:
                        style = ("background-color: #fb92f0; color: white; "
                                 "font-weight: bold")
                    elif is_buy_strike:
                        style = ("background-color: #9c00ff; color: white; "
                                 "font-weight: bold")
                    elif is_central:
                        style = "background-color: #e3e7ec; font-weight: bold"
                elif col == "IV_%" and is_central:
                    style = "background-color: #e3e7ec; font-weight: bold"

                if highlight_on:
                    if col in ("Call_Bid", "Put_Bid"):
                        theor_col = ("Call_Theor" if col.startswith("Call_")
                                     else "Put_Theor")
                        c = _bid_offer_color(row[col], row.get(theor_col),
                                              is_bid=True)
                        if c:
                            style = (f"background-color: {c}; "
                                     f"color: white; font-weight: 700")
                    elif col in ("Call_Offer", "Put_Offer"):
                        theor_col = ("Call_Theor" if col.startswith("Call_")
                                     else "Put_Theor")
                        c = _bid_offer_color(row[col], row.get(theor_col),
                                              is_bid=False)
                        if c:
                            style = (f"background-color: {c}; "
                                     f"color: white; font-weight: 700")
                    elif col in ("Call_Delta", "Put_Delta"):
                        c = _delta_color(row[col])
                        if c:
                            style = f"background-color: {c}; font-weight: 600"
                    elif col in ("Call_Theta", "Put_Theta"):
                        vega_col = ("Call_Vega" if col.startswith("Call_")
                                    else "Put_Vega")
                        c = _theta_color(row[col], row.get(vega_col))
                        if c:
                            style = f"background-color: {c}; font-weight: 600"

                styles.append(style)
            return styles

        column_display = {
            "Call_Ticker": "Тикер", "Call_Rho": "Ро",
            "Call_Theta": "Тета", "Call_Vega": "Вега",
            "Call_Gamma": "Гамма", "Call_Delta": "Дельта",
            "Call_Theor": "Теор.Ц", "Call_Last": "Посл.Ц",
            "Call_Offer": "Offer", "Call_Bid": "Bid",
            "Strike": "Страйк", "IV_%": "IV%",
            "Put_Bid": "Bid", "Put_Offer": "Offer",
            "Put_Last": "Посл.Ц", "Put_Theor": "Теор.Ц",
            "Put_Delta": "Дельта", "Put_Gamma": "Гамма",
            "Put_Vega": "Вега", "Put_Theta": "Тета",
            "Put_Rho": "Ро", "Put_Ticker": "Тикер"}

        caption_extra = ""
        if buy_strike_match is not None:
            caption_extra += (f" · страйк покупок ≈ **{buy_strike_match}**")
        if sell_strike_match is not None:
            caption_extra += (f" · страйк продаж ≈ **{sell_strike_match}**")
        st.caption(f"Центральный страйк: "
                   f"**{central if central is not None else 'не определён'}** · "
                   f"всего страйков: {len(df)}{caption_extra}")

        st.dataframe(
            df.style.apply(style_row, axis=1).format(
                {"Strike": "{:.0f}", "IV_%": "{:.2f}"},
                precision=4, na_rep="—"),
            column_config=column_display,
            use_container_width=True, height=600)

        # ---- Улыбка волатильности ----
        st.markdown("### Улыбка волатильности")
        try:
            points = fetch_volatility_graph(_board_asset, _active_series_code,
                                             _board_cat)
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
                name='IV, %'))
            fig.update_layout(
                title="Улыбка волатильности",
                xaxis_title="Страйк", yaxis_title="IV, %",
                height=380, margin=dict(l=20, r=20, t=50, b=20),
                xaxis=dict(tickformat=".0f", hoverformat=".0f"),
                yaxis=dict(tickformat=".2f", hoverformat=".2f"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Данные для улыбки волатильности недоступны.")
            # ==================================================================
# ============ ВКЛАДКА 3: ПОЗИЦИЯ ==================================
# ==================================================================
@st.fragment
def _render_position_tab():
    st.header("Управление позицией")

    col_ctrl, col_add = st.columns([1, 1.7], gap="medium")

    # ---------- ЛЕВАЯ КОЛОНКА: параметры ----------
    with col_ctrl:
        st.markdown("#### Параметры")
        with st.container(border=True):
            _r1c1, _r1c2 = st.columns(2)
            with _r1c1:
                deposit = st.number_input("Депозит, ₽", min_value=0.0,
                                           value=100000.0, step=1000.0,
                                           format="%.0f", key="dep_inp")
            with _r1c2:
                risk_pct = st.number_input("Риск, %", min_value=0.1,
                                            max_value=100.0, value=1.0,
                                            step=0.1, format="%.1f", key="rp_inp")

            st.markdown("**Комиссии**")
            _r2c1, _r2c2 = st.columns(2)
            with _r2c1:
                comm_options_pct = st.number_input(
                    "Опционы, %", min_value=0.0, max_value=20.0, value=3.0,
                    step=0.1, format="%.2f", key="cop_inp")
            with _r2c2:
                min_comm_options = st.number_input(
                    "Мин. опц., ₽", min_value=0.0, max_value=100.0, value=0.02,
                    step=0.01, format="%.4f", key="cmo_inp")
            _r3c1, _r3c2 = st.columns(2)
            with _r3c1:
                comm_futures_pct = st.number_input(
                    "Фьючерсы, %", min_value=0.0, max_value=5.0, value=0.1,
                    step=0.01, format="%.3f", key="cfp_inp")
            with _r3c2:
                comm_stocks_pct = st.number_input(
                    "Акции, %", min_value=0.0, max_value=5.0, value=0.3,
                    step=0.01, format="%.3f", key="csp_inp")

            st.markdown("---")
            with st.popover("📥 Импорт портфеля (CSV)", use_container_width=True):
                st.markdown("**Загрузить CSV**")
                _pf_file = st.file_uploader("CSV файл", type=["csv"],
                                              key="pf_csv_inp",
                                              label_visibility="collapsed")
                if _pf_file is not None:
                    try:
                        _pf_df = pd.read_csv(_pf_file)
                        _imported = []
                        for _, row in _pf_df.iterrows():
                            _imported.append({
                                "_id": _new_position_id(),
                                "Конструкция": str(row.get("Конструкция", "Без названия")),
                                "Тип инструмента": str(row.get("Тип", "Опцион")),
                                "Опцион": str(row.get("Опцион", "—")),
                                "Направление": str(row.get("Направление", "Buy")),
                                "Страйк": (float(row["Страйк"])
                                           if pd.notna(row.get("Страйк"))
                                           and str(row.get("Страйк")) != "—"
                                           else None),
                                "Эксп.": str(row.get("Эксп.", "—")),
                                "Тикер": str(row.get("Тикер", "—")),
                                "Кол-во": int(row.get("Кол-во", 0)),
                                "Цена": float(row.get("Цена", 0)),
                                "Теор.цена": float(row.get("Теор.цена", 0)),
                                "Дельта": (float(row["Дельта"])
                                           if pd.notna(row.get("Дельта")) else None),
                                "Гамма": (float(row["Гамма"])
                                          if pd.notna(row.get("Гамма")) else None),
                                "Вега": (float(row["Вега"])
                                         if pd.notna(row.get("Вега")) else None),
                                "Тета": (float(row["Тета"])
                                         if pd.notna(row.get("Тета")) else None),
                                "Ро": (float(row["Ро"])
                                       if pd.notna(row.get("Ро")) else None),
                                "visible": True,
                            })
                        if st.button("Применить", type="primary", key="pf_apply"):
                            for k in list(st.session_state.keys()):
                                if k.startswith(("qty_", "price_", "qp_", "qm_",
                                                  "pp_", "pm_")):
                                    del st.session_state[k]
                            st.session_state.positions = _imported
                            st.rerun()
                        st.caption(f"Строк: {len(_imported)}")
                    except Exception as e:
                        st.error(f"Ошибка чтения CSV: {e}")

        risk_amount = deposit * risk_pct / 100.0
        st.caption(f"💰 Доступно для сделки: **{risk_amount:,.2f} ₽** "
                   f"({risk_pct}% от {deposit:,.0f} ₽)")

    # ---------- Внутренние утилиты ----------
    def _calc_comm(premium, instr_type="Опцион"):
        return calc_commission(premium, instrument_type=instr_type,
                               min_comm_options=min_comm_options,
                               comm_options_pct=comm_options_pct,
                               comm_futures_pct=comm_futures_pct,
                               comm_stocks_pct=comm_stocks_pct)

    def _norm_cdf_py(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_py(S, K, T, r_pct, vol_pct, div_pct, opt_type):
        if T <= 0 or S <= 0 or K <= 0 or vol_pct <= 0:
            return max(0.0, S - K) if opt_type == "call" else max(0.0, K - S)
        r = r_pct / 100.0
        q = div_pct / 100.0
        sigma = vol_pct / 100.0
        d1 = (math.log(S / K) + (r - q + sigma * sigma / 2) * T) \
             / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        if opt_type == "call":
            return S * math.exp(-q * T) * _norm_cdf_py(d1) \
                   - K * math.exp(-r * T) * _norm_cdf_py(d2)
        return K * math.exp(-r * T) * _norm_cdf_py(-d2) \
               - S * math.exp(-q * T) * _norm_cdf_py(-d1)

    def _cb_qty_dec(key):
        st.session_state[key] = int(st.session_state.get(key, 1)) - 1

    def _cb_qty_inc(key):
        st.session_state[key] = int(st.session_state.get(key, 1)) + 1

    def _cb_price_dec(key):
        st.session_state[key] = round(float(st.session_state.get(key, 0.0)) - 0.01, 4)

    def _cb_price_inc(key):
        st.session_state[key] = round(float(st.session_state.get(key, 0.0)) + 0.01, 4)

    def _get_board_price(_strike, _opt_type, _side_internal, _c_map, _p_map):
        """Авто-цена для опциона:
           Покупка → offer, Продажа → bid (fallback: theorprice, last).
        """
        if _strike is None:
            return 0.0
        src = _c_map if _opt_type == "Call" else _p_map
        row = src.get(_strike, {})
        if not row:
            return 0.0
        v = row.get('offer') if _side_internal == "Buy" else row.get('bid')
        if v is None or v <= 0:
            v = row.get('theorprice')
        if v is None or v <= 0:
            v = row.get('last')
        try:
            return float(v) if v and v > 0 else 0.0
        except Exception:
            return 0.0

    def _fmt_board_label(_opt_type, _side_internal, _strike, _price):
        """«+C270 16,7500» — как в index.html."""
        if _price is None or _price <= 0 or _strike is None:
            return "—"
        _sign = "+" if _side_internal == "Buy" else "-"
        _letter = "C" if _opt_type == "Call" else "P"
        try:
            _kf = float(_strike)
            _k_str = str(int(_kf)) if _kf.is_integer() else f"{_kf:.2f}"
        except Exception:
            _k_str = str(_strike)
        _p_str = f"{_price:.4f}".replace('.', ',')
        return f"{_sign}{_letter}{_k_str} {_p_str}"

    # ---------- ПРАВАЯ КОЛОНКА: добавление позиции ----------
    with col_add:
        st.markdown("#### Добавить позицию")

        if "positions" not in st.session_state:
            st.session_state.positions = []

        # 🔧 Источник данных — вкладка «Доска» (board_*)
        _asset_now_all = st.session_state.get("board_asset", "")
        _atype_now_all = st.session_state.get("board_category", "")
        _series_now = st.session_state.get("board_series_code", "")
        _expiry_now = st.session_state.get("board_expiry", "")

        if not (_asset_now_all and _atype_now_all and _series_now):
            st.warning("Сначала выберите актив и серию на вкладке «Доска».")
        else:
            _all_series = fetch_all_series_for_asset(_asset_now_all, _atype_now_all)
            if not _all_series:
                _all_series = st.session_state.get("board_series_list", [])

            _series_labels = [format_series_label(s["expiry"]) for s in _all_series]
            _series_by_label = {lab: s for lab, s in zip(_series_labels, _all_series)}

            _default_series_idx = 0
            for i, s in enumerate(_all_series):
                if s.get("code") == _series_now:
                    _default_series_idx = i
                    break

            try:
                board = fetch_optionboard(_asset_now_all, _atype_now_all, _series_now)
            except Exception as e:
                st.error(f"Не удалось загрузить доску: {e}")
                board = None

            if board:
                calls = board.get('call') or []
                puts = board.get('put') or []
                central = board.get('central_strike')
                c_map = {c['strike']: c for c in calls if c.get('strike') is not None}
                p_map = {p['strike']: p for p in puts if p.get('strike') is not None}
                all_strikes = sorted(set(c_map.keys()) | set(p_map.keys()))
                asset_type_ui_now = _atype_now_all
                asset_now = _asset_now_all

                with st.container(border=True), st.form(
                        "add_position_form", clear_on_submit=False):
                    # Строка 1: тип инструмента | дата исполнения
                    _f1c1, _f1c2 = st.columns(2)
                    with _f1c1:
                        _instr_options = ["Опцион"]
                        if asset_type_ui_now in ("Фьючерс", "Валюта", "Товар"):
                            _instr_options.append("Фьючерс")
                        elif asset_type_ui_now == "Акция":
                            _instr_options.append("Акция")
                        else:
                            _instr_options.append("Индекс")
                        instrument_type = st.selectbox("Тип инструмента",
                                                        _instr_options,
                                                        key="form_instrument_type")
                    with _f1c2:
                        if instrument_type == "Опцион":
                            chosen_series_label = st.selectbox(
                                "Дата исполнения",
                                _series_labels,
                                index=_default_series_idx,
                                key="form_series")
                            chosen_series = _series_by_label[chosen_series_label]
                            expiry_now_form = chosen_series["expiry"]
                            chosen_series_code = chosen_series["code"]
                        else:
                            chosen_series_code = None
                            if instrument_type == "Фьючерс":
                                _contracts = fetch_futures_contracts_list(asset_now)
                                if _contracts:
                                    _contract_labels = [
                                        f"{c['expiration']} — {c['secid']}"
                                        for c in _contracts
                                    ]
                                    _chosen = st.selectbox(
                                        "Фьючерсный контракт",
                                        _contract_labels, index=0,
                                        key="form_futures_contract")
                                    _chosen_contract = _contracts[
                                        _contract_labels.index(_chosen)]
                                    expiry_now_form = _chosen_contract["expiration"]
                                    _futures_secid_form = _chosen_contract["secid"]
                                else:
                                    expiry_now_form = _expiry_now
                                    _futures_secid_form = asset_now
                                    st.text_input("Дата исполнения",
                                                   value=_expiry_now,
                                                   disabled=True,
                                                   key="form_fut_exp_disp")
                            else:
                                expiry_now_form = "—"
                                _futures_secid_form = None
                                st.text_input("Дата исполнения",
                                               value="—", disabled=True,
                                               key="form_no_exp_disp")

                    # Строка 2: страйк | опцион
                    _f2c1, _f2c2 = st.columns(2)
                    with _f2c1:
                        if instrument_type == "Опцион" and all_strikes:
                            default_idx = 0
                            if central is not None:
                                try:
                                    default_idx = all_strikes.index(
                                        min(all_strikes,
                                            key=lambda s: abs(float(s) - float(central))))
                                except ValueError:
                                    default_idx = 0
                            chosen_strike = st.selectbox("Страйк", all_strikes,
                                                          index=default_idx,
                                                          key="form_strike")
                        else:
                            chosen_strike = None
                            st.text_input("Страйк", value="—", disabled=True,
                                           key="form_strike_disabled")
                    with _f2c2:
                        if instrument_type == "Опцион":
                            opt_type = st.selectbox("Опцион", ["Call", "Put"],
                                                     key="form_opt_type")
                        else:
                            opt_type = "—"
                            st.text_input("Опцион", value="—", disabled=True,
                                           key="form_opt_type_disabled")

                    # Строка 3: направление | количество
                    _f3c1, _f3c2 = st.columns(2)
                    with _f3c1:
                        side_ui = st.selectbox("Направление",
                                                ["Покупка", "Продажа"],
                                                key="form_side")
                        side = _side_internal(side_ui)
                    with _f3c2:
                        qty_input = st.number_input("Кол-во", min_value=1, value=1,
                                                     step=1, key="form_qty")

                    # Строка 4: цена | тикер (авто)
                    _f4c1, _f4c2 = st.columns(2)
                    with _f4c1:
                        ref_opt = (c_map.get(chosen_strike, {}) if opt_type == "Call"
                                   else p_map.get(chosen_strike, {})) \
                                  if chosen_strike is not None else {}
                        # Авто-цена из доски: Покупка→offer, Продажа→bid
                        _auto_price = 0.0
                        if instrument_type == "Опцион" and chosen_strike is not None:
                            _auto_price = _get_board_price(chosen_strike, opt_type,
                                                            side, c_map, p_map)
                        # 🔧 Поле цены — только для ручного ввода,
                        # по умолчанию пустое; авто-цена подставится ниже
                        price_input = st.number_input(
                            "Цена, ₽ (0 = взять из доски)", min_value=0.0,
                            value=0.0, step=0.01, format="%.4f",
                            key="form_price")
                    with _f4c2:
                        if instrument_type == "Опцион" and chosen_strike is not None:
                            ticker_val = ref_opt.get('secid', '—')
                        elif instrument_type == "Фьючерс" and _futures_secid_form:
                            ticker_val = _futures_secid_form
                        else:
                            ticker_val = resolve_underlying_secid(
                                asset_now, asset_type_ui_now) or '—'
                        st.text_input("Тикер (авто)", value=ticker_val,
                                       disabled=True, key="form_ticker_disp")

                    # 🔧 НОВЫЙ ФОРМАТ: «+C270 16,7500»
                    use_auto_price = True
                    if instrument_type == "Опцион" and chosen_strike is not None:
                        if _auto_price > 0:
                            _label = _fmt_board_label(opt_type, side,
                                                       chosen_strike, _auto_price)
                            st.markdown(
                                f"<div style='background:#eef6fb; border-radius:10px; "
                                f"padding:8px 14px; font-size:.9rem; color:#1c5a7a; "
                                f"margin:6px 0;'>"
                                f"Цена из доски опционов: "
                                f"<b style='font-family:Consolas,monospace; "
                                f"font-size:1rem;'>{_label}</b>"
                                f"</div>",
                                unsafe_allow_html=True)
                            use_auto_price = st.checkbox(
                                "🎯 Использовать авто-цену из доски",
                                value=True, key="form_use_auto_price")
                        else:
                            st.caption("⚠ Авто-цена недоступна для выбранной "
                                       "комбинации (нет bid/offer/theorprice).")

                    submitted = st.form_submit_button("➕ Добавить позицию",
                                                      type="primary",
                                                      use_container_width=True)

                    if submitted:
                        if instrument_type == "Фьючерс":
                            _und_secid = _futures_secid_form or asset_now
                            _fut_info = fetch_futures_info_iss(_und_secid) or {}
                            _last_price = _fut_info.get("last")
                            _fut_exp = _fut_info.get("expiration") or expiry_now_form
                            final_price = float(price_input) if price_input > 0 else (
                                float(_last_price) if _last_price else 0.0)
                            if final_price > 0:
                                signed_qty = int(qty_input) if side == "Buy" \
                                             else -int(qty_input)
                                _pos = {
                                    "_id": _new_position_id(),
                                    "Конструкция": "Без названия",
                                    "Тип инструмента": "Фьючерс",
                                    "Опцион": "БА",
                                    "Направление": side,
                                    "Страйк": None,
                                    "Эксп.": _fut_exp,
                                    "Тикер": _und_secid,
                                    "Кол-во": signed_qty,
                                    "Цена": float(final_price),
                                    "Теор.цена": float(_last_price) if _last_price
                                                 else float(final_price),
                                    "Дельта": None, "Гамма": None, "Вега": None,
                                    "Тета": None, "Ро": None, "visible": True,
                                }
                                _pos = apply_parity_delta(_pos)
                                st.session_state.positions.append(_pos)
                                st.rerun()
                            else:
                                st.error("Не удалось определить цену фьючерса.")

                        elif instrument_type in ("Акция", "Индекс"):
                            _und_secid = resolve_underlying_secid(asset_now,
                                                                  asset_type_ui_now)
                            _ba_info = fetch_ba_iss_info(_und_secid,
                                                         asset_type_ui_now) or {}
                            _last_price = _ba_info.get("last")
                            final_price = float(price_input) if price_input > 0 else (
                                float(_last_price) if _last_price else 0.0)
                            if final_price > 0:
                                signed_qty = int(qty_input) if side == "Buy" \
                                             else -int(qty_input)
                                _pos = {
                                    "_id": _new_position_id(),
                                    "Конструкция": "Без названия",
                                    "Тип инструмента": instrument_type,
                                    "Опцион": "БА",
                                    "Направление": side,
                                    "Страйк": None,
                                    "Эксп.": "—",
                                    "Тикер": _und_secid or '—',
                                    "Кол-во": signed_qty,
                                    "Цена": float(final_price),
                                    "Теор.цена": float(_last_price) if _last_price
                                                 else float(final_price),
                                    "Дельта": None, "Гамма": None, "Вега": None,
                                    "Тета": None, "Ро": None, "visible": True,
                                }
                                _pos = apply_parity_delta(_pos)
                                st.session_state.positions.append(_pos)
                                st.rerun()
                            else:
                                st.error("Не удалось определить цену БА.")

                        else:  # Опцион
                            if chosen_strike is None:
                                st.error("Укажите страйк.")
                            else:
                                _sel_series_code = chosen_series_code or _series_now
                                if _sel_series_code != _series_now:
                                    try:
                                        _board_sel = fetch_optionboard(
                                            asset_now, asset_type_ui_now,
                                            _sel_series_code)
                                        _calls_sel = _board_sel.get('call') or []
                                        _puts_sel = _board_sel.get('put') or []
                                        _c_map_sel = {c['strike']: c
                                                       for c in _calls_sel
                                                       if c.get('strike') is not None}
                                        _p_map_sel = {p['strike']: p
                                                       for p in _puts_sel
                                                       if p.get('strike') is not None}
                                    except Exception:
                                        _c_map_sel = c_map
                                        _p_map_sel = p_map
                                else:
                                    _c_map_sel = c_map
                                    _p_map_sel = p_map

                                ref = _c_map_sel.get(chosen_strike, {}) \
                                      if opt_type == "Call" \
                                      else _p_map_sel.get(chosen_strike, {})
                                final_pos_price = None
                                _src_label = ""

                                if use_auto_price:
                                    _auto_p_sel = _get_board_price(
                                        chosen_strike, opt_type, side,
                                        _c_map_sel, _p_map_sel)
                                    if _auto_p_sel > 0:
                                        final_pos_price = float(_auto_p_sel)
                                        _src_label = " (из доски)"

                                if final_pos_price is None and price_input > 0:
                                    final_pos_price = float(price_input)
                                    _src_label = " (ручная)"

                                if final_pos_price is None or final_pos_price <= 0:
                                    st.error("Укажите цену > 0 или включите авто-цену.")
                                else:
                                    signed_qty = int(qty_input) if side == "Buy" \
                                                 else -int(qty_input)
                                    st.session_state.positions.append({
                                        "_id": _new_position_id(),
                                        "Конструкция": "Без названия",
                                        "Тип инструмента": "Опцион",
                                        "Опцион": opt_type,
                                        "Направление": side,
                                        "Страйк": chosen_strike,
                                        "Эксп.": expiry_now_form,
                                        "Тикер": ref.get('secid', '—'),
                                        "Кол-во": signed_qty,
                                        "Цена": float(final_pos_price),
                                        "Теор.цена": float(ref.get('theorprice') or 0),
                                        "Дельта": ref.get('delta'),
                                        "Гамма":  ref.get('gamma'),
                                        "Вега":   ref.get('vega'),
                                        "Тета":   ref.get('theta'),
                                        "Ро":     ref.get('rho'),
                                        "visible": True,
                                        "_vol": float(ref.get('volatility') or 20.0),
                                        "_r": float(st.session_state.get(
                                            "_calc_riskfree", 0.0) or 0.0),
                                        "_q": float(st.session_state.get(
                                            "_calc_dividend", 0.0) or 0.0),
                                        "_series_code": _sel_series_code,
                                        "_asset": asset_now,
                                        "_atype": asset_type_ui_now,
                                    })
                                    st.success(f"Добавлено: {side_ui} {opt_type} "
                                               f"{chosen_strike} × {qty_input} "
                                               f"[{expiry_now_form}]"
                                               f"{_src_label} "
                                               f"по {final_pos_price:.4f} ₽")
                                    st.rerun()

    # ==================================================================
    # ТЕКУЩИЕ ПОЗИЦИИ
    # ==================================================================
    st.markdown("---")
    st.markdown("### Текущие позиции")

    if not st.session_state.positions:
        st.caption("Портфель пуст.")
    else:
        _pos_container = st.container(border=True)
        with _pos_container:
            st.markdown("<div class='pos-row-wrap'>", unsafe_allow_html=True)
            COL_W = [0.28, 0.32, 0.85, 0.75, 0.85, 0.95, 0.65, 1.30,
                     1.05, 1.25, 1.15, 1.15, 0.95, 0.85, 0.85, 0.85, 0.75, 0.95]
            HEADERS = ["", "", "Тип", "Опцион", "Страйк", "Дата исп.", "До эксп.",
                       "Тикер", "Кол-во", "Цена", "Теор. цена", "P&L",
                       "Дельта", "Гамма", "Вега", "Тета", "Ро", "Комисс."]

            _hdr = st.columns(COL_W)
            for c, h in zip(_hdr, HEADERS):
                with c:
                    st.markdown(
                        f"<div style='font-size:.68rem; color:#2c506d; "
                        f"font-weight:700; text-transform:uppercase; "
                        f"letter-spacing:.02em; padding-top:4px;'>{h}</div>",
                        unsafe_allow_html=True)

            st.markdown("<hr style='margin:2px 0 4px 0; border:none; "
                        "border-top:1px solid #e6edf4;'>", unsafe_allow_html=True)

            _today = date.today()
            for idx, p in enumerate(st.session_state.positions):
                _id = p.get("_id", f"legacy_{idx}")
                visible = p.get("visible", True)
                gray = "opacity:0.45;" if not visible else ""

                row = st.columns(COL_W)

                with row[0]:
                    if st.button("✖", key=f"del_{_id}", help="Удалить строку",
                                 use_container_width=True):
                        st.session_state.positions.pop(idx)
                        for k in list(st.session_state.keys()):
                            if k.endswith(f"_{_id}"):
                                del st.session_state[k]
                        st.rerun()

                with row[1]:
                    icon = "👁" if visible else "🚫"
                    if st.button(icon, key=f"vis_{_id}",
                                 help="Скрыть/показать в профиле",
                                 use_container_width=True):
                        p["visible"] = not visible
                        st.rerun()

                with row[2]:
                    _t = p.get("Тип инструмента", "Опцион")
                    _short_t = {"Опцион": "Опцион", "Фьючерс": "Фьюч.",
                                "Акция": "Акция", "Индекс": "Индекс"}.get(_t, _t)
                    st.markdown(
                        f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                        f"{_short_t}</div>", unsafe_allow_html=True)

                with row[3]:
                    _opt = p.get("Опцион", "—")
                    _opt_html = _color_call_put(_opt) if _opt in ("Call", "Put") else _opt
                    st.markdown(f"<div style='padding-top:6px; {gray};'>{_opt_html}</div>",
                                unsafe_allow_html=True)

                with row[4]:
                    _k = p.get("Страйк")
                    _k_txt = f"<b>{int(_k)}</b>" if _k is not None else "—"
                    st.markdown(f"<div style='padding-top:6px; {gray};'>{_k_txt}</div>",
                                unsafe_allow_html=True)

                with row[5]:
                    _exp_disp = p.get("Эксп.", "—")
                    try:
                        _exp_disp_fmt = datetime.strptime(
                            _exp_disp, "%Y-%m-%d").strftime("%d.%m.%Y")
                    except Exception:
                        _exp_disp_fmt = _exp_disp
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.78rem;'>"
                                f"{_exp_disp_fmt}</div>", unsafe_allow_html=True)

                with row[6]:
                    _dte = "—"
                    _exp_str = p.get("Эксп.", "—")
                    if _exp_str and _exp_str != "—":
                        try:
                            _d = datetime.strptime(_exp_str, "%Y-%m-%d").date()
                            _dte = f"{(_d - _today).days}"
                        except Exception:
                            pass
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                                f"{_dte}</div>", unsafe_allow_html=True)

                with row[7]:
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.78rem;'>"
                                f"{p.get('Тикер', '—')}</div>", unsafe_allow_html=True)

                with row[8]:
                    kq = f"qty_{_id}"
                    if kq not in st.session_state:
                        st.session_state[kq] = int(p.get("Кол-во", 1))
                    qc = st.columns([1, 3, 1])
                    with qc[0]:
                        st.button("➖", key=f"qm_{_id}",
                                  on_click=_cb_qty_dec, args=(kq,),
                                  use_container_width=True)
                    with qc[1]:
                        st.number_input(
                            "qty", min_value=-10000, max_value=10000, step=1,
                            key=kq, label_visibility="collapsed")
                    with qc[2]:
                        st.button("➕", key=f"qp_{_id}",
                                  on_click=_cb_qty_inc, args=(kq,),
                                  use_container_width=True)

                with row[9]:
                    kp = f"price_{_id}"
                    if kp not in st.session_state:
                        st.session_state[kp] = float(p.get("Цена", 0.0))
                    pc = st.columns([1, 3, 1])
                    with pc[0]:
                        st.button("➖", key=f"pm_{_id}",
                                  on_click=_cb_price_dec, args=(kp,),
                                  use_container_width=True)
                    with pc[1]:
                        st.number_input(
                            "price", min_value=0.0,
                            step=0.01, format="%.4f",
                            key=kp, label_visibility="collapsed")
                    with pc[2]:
                        st.button("➕", key=f"pp_{_id}",
                                  on_click=_cb_price_inc, args=(kp,),
                                  use_container_width=True)

                _theor = float(p.get("Теор.цена", 0))
                _instr = p.get("Тип инструмента", "Опцион")
                _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
                _com = 0.0 if _isBA else _calc_comm(float(p.get("Цена", 0)), _instr)
                _qty = int(p.get("Кол-во", 0))
                _price = float(p.get("Цена", 0))
                _eff_price = _price + _com
                _pnl = ((_theor - _price) * _qty if _isBA
                        else (_theor - _eff_price) * _qty)

                with row[10]:
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                                f"{_theor:.4f}</div>", unsafe_allow_html=True)

                with row[11]:
                    _color = "#00a651" if _pnl > 0 else ("#d32f2f" if _pnl < 0 else "#333")
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-weight:700; "
                                f"color:{_color};'>{_pnl:+,.2f} ₽</div>",
                                unsafe_allow_html=True)

                for ri, gr in zip([12, 13, 14, 15, 16],
                                  ["Дельта", "Гамма", "Вега", "Тета", "Ро"]):
                    val = p.get(gr)
                    txt = f"{val:+.4f}" if isinstance(val, (int, float)) else "—"
                    with row[ri]:
                        st.markdown(f"<div style='padding-top:6px; {gray}; "
                                    f"font-size:.78rem;'>{txt}</div>",
                                    unsafe_allow_html=True)

                with row[17]:
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.78rem;'>"
                                f"{_com:.4f}</div>", unsafe_allow_html=True)

            st.markdown("<hr style='margin:4px 0 4px 0; border:none; "
                        "border-top:1px solid #e6edf4;'>", unsafe_allow_html=True)

            # ---- Итоговая строка ----
            _tot_com = _tot_pnl = _tot_delta = _tot_gamma = 0.0
            _tot_vega = _tot_theta = _tot_rho = 0.0
            for p in st.session_state.positions:
                _q = int(p.get("Кол-во", 0))
                _pr = float(p.get("Цена", 0))
                _th = float(p.get("Теор.цена", 0))
                _instr = p.get("Тип инструмента", "Опцион")
                _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
                if _isBA:
                    _c = 0.0; _pl = (_th - _pr) * _q
                else:
                    _c = _calc_comm(_pr, _instr)
                    _pl = (_th - _pr - _c) * _q
                _tot_com += _c * abs(_q)
                _tot_pnl += _pl
                _tot_delta += (p.get("Дельта") or 0) * _q
                _tot_gamma += (p.get("Гамма")  or 0) * _q
                _tot_vega  += (p.get("Вега")   or 0) * _q
                _tot_theta += (p.get("Тета")   or 0) * _q
                _tot_rho   += (p.get("Ро")     or 0) * _q

            tot_row = st.columns(COL_W)
            with tot_row[0]:
                if st.button("🗑", key="clear_all_positions",
                             help="Удалить все позиции",
                             use_container_width=True):
                    for k in list(st.session_state.keys()):
                        if k.startswith(("qty_", "price_", "qp_", "qm_",
                                          "pp_", "pm_")):
                            del st.session_state[k]
                    st.session_state.positions = []
                    st.rerun()
            with tot_row[2]:
                st.markdown("<div style='padding-top:6px; font-size:.8rem; "
                            "color:#2c506d; font-weight:700;'>ГО:</div>",
                            unsafe_allow_html=True)
            with tot_row[7]:
                st.markdown("<div style='padding-top:6px; font-size:.8rem; "
                            "color:#2c506d; font-weight:700;'>Итого:</div>",
                            unsafe_allow_html=True)

            _color_pnl_tot = "#00a651" if _tot_pnl > 0 else ("#d32f2f" if _tot_pnl < 0 else "#333")
            with tot_row[11]:
                st.markdown(f"<div style='padding-top:6px; font-weight:800; "
                            f"color:{_color_pnl_tot};'>{_tot_pnl:+,.2f} ₽</div>",
                            unsafe_allow_html=True)
            with tot_row[12]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_delta:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[13]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_gamma:+.4f}</div>", unsafe_allow_html=True)
            with tot_row[14]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_vega:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[15]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_theta:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[16]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_rho:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[17]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_com:,.4f}</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        # =========================================================
        # Кнопки «Обновить позицию» + «Экспорт CSV»
        # =========================================================
        _btn1, _btn2, _btn3 = st.columns([1, 1, 3])
        with _btn1:
            _refresh_clicked = st.button("🔄 Обновить позицию",
                                          use_container_width=True,
                                          type="primary",
                                          key="positions_refresh_btn")
        with _btn2:
            _export_rows = []
            for i, p in enumerate(st.session_state.positions):
                _q = int(p["Кол-во"]); _pr = float(p["Цена"]); _th = float(p["Теор.цена"])
                _instr = p.get("Тип инструмента", "Опцион")
                _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
                if _isBA:
                    _c = 0.0; _pl = (_th - _pr) * _q
                else:
                    _c = _calc_comm(_pr, _instr); _pl = (_th - _pr - _c) * _q
                _export_rows.append({
                    "#": i + 1, "Тип": _instr, "Опцион": p["Опцион"],
                    "Направление": _side_ui(p.get("Направление",
                                                    _side_from_qty(_q))),
                    "Страйк": p.get("Страйк", "—"), "Эксп.": p.get("Эксп.", "—"),
                    "Тикер": p.get("Тикер", "—"), "Кол-во": _q, "Цена": _pr,
                    "Комиссия": _c, "Эфф. цена": _pr + _c, "Теор.цена": _th,
                    "P&L": _pl, "Дельта": p.get("Дельта"), "Гамма": p.get("Гамма"),
                    "Вега": p.get("Вега"), "Тета": p.get("Тета"), "Ро": p.get("Ро"),
                })
            _df_export = pd.DataFrame(_export_rows)
            st.download_button("📤 Экспорт CSV",
                               data=_df_export.to_csv(index=False).encode("utf-8-sig"),
                               file_name="portfolio.csv", mime="text/csv",
                               use_container_width=True,
                               key="positions_export_btn")

        if _refresh_clicked:
            for _pi, _p in enumerate(st.session_state.positions):
                _instr_p = _p.get("Тип инструмента", "Опцион")
                if _instr_p != "Опцион":
                    continue
                _asset_p = _p.get("_asset") or st.session_state.get("board_asset", "")
                _atype_p = _p.get("_atype") or st.session_state.get("board_category", "")
                _scode_p = _p.get("_series_code") or st.session_state.get("board_series_code", "")
                if not (_asset_p and _atype_p and _scode_p):
                    continue
                try:
                    _board_p = fetch_optionboard(_asset_p, _atype_p, _scode_p)
                except Exception:
                    continue
                _side_p = "Call" if _p.get("Опцион") == "Call" else "Put"
                _src_p = _board_p.get("call") if _side_p == "Call" else _board_p.get("put")
                _row_p = next((x for x in (_src_p or [])
                                if x.get("strike") == _p.get("Страйк")), None)
                if _row_p is None:
                    continue
                _p["Теор.цена"] = float(_row_p.get("theorprice") or 0)
                _p["Дельта"] = _row_p.get("delta")
                _p["Гамма"]  = _row_p.get("gamma")
                _p["Вега"]   = _row_p.get("vega")
                _p["Тета"]   = _row_p.get("theta")
                _p["Ро"]     = _row_p.get("rho")
                _p["_vol"]   = float(_row_p.get("volatility") or 20.0)
                _kp_p = f"price_{_p.get('_id')}"
                _kq_p = f"qty_{_p.get('_id')}"
                if _kp_p in st.session_state:
                    _p["Цена"] = float(st.session_state[_kp_p])
                if _kq_p in st.session_state:
                    _p["Кол-во"] = int(st.session_state[_kq_p])
                    _p["Направление"] = _side_from_qty(int(_p["Кол-во"]))
            st.success("✅ Позиции обновлены из доски.")
            st.rerun()

        # =========================================================
        # Проверка риска
        # =========================================================
        _max_loss_prem = 0.0
        for p in st.session_state.positions:
            if p.get("Опцион") == "БА":
                continue
            _instr = p.get("Тип инструмента", "Опцион")
            _q = abs(int(p.get("Кол-во", 0)))
            _pr = float(p.get("Цена", 0))
            _c = _calc_comm(_pr, _instr)
            _max_loss_prem += (_pr + _c) * _q

        if _max_loss_prem > risk_amount:
            st.error(f"⚠ Превышен риск: {_max_loss_prem:,.2f} ₽ > "
                     f"{risk_amount:,.2f} ₽ допустимых")
        else:
            st.success(f"✓ Риск: {_max_loss_prem:,.2f} ₽ / "
                       f"{risk_amount:,.2f} ₽ "
                       f"({_max_loss_prem / risk_amount * 100:.1f}%)")

    # ==================================================================
    # ГРАФИК ПРОФИЛЯ + ГРАФИКИ D1/H1
    # ==================================================================
    st.markdown("---")
    st.markdown("### График профиля позиции")

    payoff_positions = [p for p in st.session_state.positions
                        if p.get("visible", True)]

    if not payoff_positions:
        st.caption("Нет видимых позиций для построения профиля.")
    else:
        _all_exp_dates = []
        for p in payoff_positions:
            _e = p.get("Эксп.", "—")
            if _e and _e != "—":
                try:
                    _all_exp_dates.append(
                        datetime.strptime(_e, "%Y-%m-%d").date())
                except Exception:
                    pass
        _anchor_date = max(_all_exp_dates) if _all_exp_dates else None
        _anchor_str = _anchor_date.strftime("%Y-%m-%d") if _anchor_date else None
        _has_multiple_exp = len(set(_all_exp_dates)) > 1

        if _has_multiple_exp:
            st.info(
                f"📅 В портфеле **разные даты исполнения**. "
                f"Payoff построен на **{_anchor_str}**.")

        F_current = st.session_state.get("_current_market_price", None)
        if F_current is None:
            try:
                _atype_f = st.session_state.get("board_category", "")
                _eng_f, _mkt_f = _get_engine_market(_atype_f)
                _secid_f = resolve_underlying_secid(
                    st.session_state.get("board_asset", ""), _atype_f)
                F_current = get_last_close_price(_secid_f, _eng_f, _mkt_f)
                if F_current is not None:
                    st.session_state["_current_market_price"] = F_current
            except Exception:
                pass

        all_pos_strikes = sorted({float(p["Страйк"]) for p in payoff_positions
                                   if p.get("Страйк") is not None})
        if not all_pos_strikes:
            _ba_prices = [float(p["Цена"]) for p in payoff_positions
                          if p.get("Тип инструмента") == "БА"
                          or p.get("Опцион") == "БА"]
            if _ba_prices:
                all_pos_strikes = _ba_prices

        if not all_pos_strikes:
            st.caption("Нет данных для построения графика профиля.")
        else:
            _range_pts = list(all_pos_strikes)
            if F_current is not None:
                _range_pts.append(F_current)
            s_min = min(_range_pts) * 0.85
            s_max = max(_range_pts) * 1.15
            S_arr = np.linspace(s_min, s_max, 500)

            def _payoff_at_expiry(S_vals, positions_subset):
                return compute_payoff(positions_subset, S_vals,
                                       comm_func=_calc_comm,
                                       anchor_expiry=_anchor_str)

            def _payoff_today(S_vals, positions_subset, T_years):
                S_vals = np.asarray(S_vals, dtype=float)
                pnl_arr = np.zeros_like(S_vals)
                if T_years <= 0:
                    return pnl_arr
                _r = float(st.session_state.get("_calc_riskfree", 0.0) or 0.0)
                _q = float(st.session_state.get("_calc_dividend", 0.0) or 0.0)
                _vol = float(st.session_state.get("_calc_volatility", 0.0) or 0.0)
                if _vol <= 0:
                    _vol = 20.0
                for p in positions_subset:
                    qty = int(p["Кол-во"]); entry = float(p["Цена"])
                    _instr = p.get("Тип инструмента", "Опцион")
                    com = _calc_comm(entry, _instr)
                    if p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА":
                        pnl_arr += (S_vals - entry) * qty
                        continue
                    K = float(p["Страйк"])
                    opt_type = "call" if p["Опцион"] == "Call" else "put"
                    price_now = np.array([
                        black_scholes_py(S, K, T_years, _r, _vol, _q, opt_type)
                        for S in S_vals])
                    pnl_arr += (price_now - entry - com) * qty
                return pnl_arr

            pnl_arr = _payoff_at_expiry(S_arr, payoff_positions)
            max_profit = float(np.max(pnl_arr))
            max_loss_pf = float(np.min(pnl_arr))

            be_points = []
            for i in range(1, len(S_arr)):
                if pnl_arr[i - 1] * pnl_arr[i] < 0:
                    denom = pnl_arr[i] - pnl_arr[i - 1]
                    if abs(denom) > 1e-12:
                        x0 = S_arr[i - 1] + (S_arr[i] - S_arr[i - 1]) \
                             * (-pnl_arr[i - 1]) / denom
                        be_points.append(float(x0))

            fig_pf = go.Figure()
            fig_pf.add_trace(go.Scatter(
                x=S_arr, y=np.where(pnl_arr >= 0, pnl_arr, 0),
                fill='tozeroy', fillcolor='rgba(0,255,12,0.20)',
                line=dict(width=0), mode='lines',
                name='Прибыль (эксп.)', hoverinfo='skip'))
            fig_pf.add_trace(go.Scatter(
                x=S_arr, y=np.where(pnl_arr <= 0, pnl_arr, 0),
                fill='tozeroy', fillcolor='rgba(255,0,0,0.20)',
                line=dict(width=0), mode='lines',
                name='Убыток (эксп.)', hoverinfo='skip'))
            fig_pf.add_trace(go.Scatter(
                x=S_arr, y=pnl_arr, mode='lines',
                line=dict(color='#1e5a7a', width=3),
                name=f'P&L на {_anchor_str or "эксп."}',
                hovertemplate='БА: %{x:.2f} ₽<br>P&L: %{y:.2f} ₽<extra></extra>'))

            _cur_pnl_today = None
            try:
                _exp_date_pt = _anchor_date or date.today()
                _T_now = max((_exp_date_pt - date.today()).days, 1) / 365.0
                pnl_today = _payoff_today(S_arr, payoff_positions, _T_now)
                fig_pf.add_trace(go.Scatter(
                    x=S_arr, y=pnl_today, mode='lines',
                    line=dict(color='#1e88e5', width=2, dash='dash'),
                    name='P&L на текущую дату',
                    hovertemplate='БА: %{x:.2f} ₽<br>P&L: %{y:.2f} ₽<extra></extra>'))

                if F_current is not None:
                    _cur_pnl_today = float(
                        _payoff_today(np.array([F_current]), payoff_positions,
                                      _T_now)[0])
                    _marker_color = "#00a651" if _cur_pnl_today > 0 else (
                        "#d32f2f" if _cur_pnl_today < 0 else "#1e88e5")
                    fig_pf.add_trace(go.Scatter(
                        x=[F_current], y=[_cur_pnl_today],
                        mode='markers',
                        marker=dict(size=16, color=_marker_color,
                                    symbol='circle',
                                    line=dict(color='white', width=2)),
                        name='Текущее состояние',
                        hovertemplate='Текущая цена: %{x:.2f} ₽<br>'
                                      'P&L: %{y:+,.2f} ₽<extra></extra>'))
            except Exception:
                pass

            fig_pf.add_hline(y=0, line_dash='dot', line_color='#7f9bb3', line_width=1)
            for k in all_pos_strikes:
                fig_pf.add_vline(x=k, line_dash='dash', line_color='#9c00ff',
                                 line_width=1, opacity=0.5,
                                 annotation_text=f"{k:.0f}",
                                 annotation_position="top",
                                 annotation_font_size=10)
            if F_current is not None:
                fig_pf.add_vline(x=F_current, line_dash='dot',
                                 line_color='#1e88e5', line_width=2,
                                 annotation_text=f"Тек. {F_current:.0f}",
                                 annotation_position="bottom right",
                                 annotation_font_size=11)
            for be in be_points:
                fig_pf.add_vline(x=be, line_dash='dot', line_color='#00a651',
                                 line_width=1.5, opacity=0.8)

            fig_pf.update_layout(
                title=f"Профиль позиции (anchor: {_anchor_str or '—'})",
                xaxis_title="Цена базового актива, ₽",
                yaxis_title="Прибыль / Убыток, ₽",
                height=500, margin=dict(l=20, r=20, t=60, b=20),
                xaxis=dict(tickformat=".0f", hoverformat=".2f"),
                yaxis=dict(tickformat=".2f", hoverformat=".2f"),
                legend=dict(orientation="h", yanchor="bottom",
                            y=1.02, xanchor="left", x=0),
                hovermode='x unified')

            fig_pf.update_xaxes(showspikes=True, spikemode='across',
                                spikesnap='cursor', spikecolor='#888888',
                                spikethickness=1, spikedash='dot')
            fig_pf.update_yaxes(showspikes=True, spikemode='across',
                                spikesnap='cursor', spikecolor='#888888',
                                spikethickness=1, spikedash='dot')

            st.plotly_chart(fig_pf, use_container_width=True)

            pm1, pm2, pm3 = st.columns(3)
            with pm1:
                st.metric("Макс. прибыль", f"{max_profit:+,.2f} ₽")
            with pm2:
                st.metric("Макс. убыток", f"{max_loss_pf:+,.2f} ₽")
            with pm3:
                if _cur_pnl_today is not None:
                    st.metric("Текущий P&L", f"{_cur_pnl_today:+,.2f} ₽")
                else:
                    st.metric("Текущий P&L", "—")

            if be_points:
                be_str = " · ".join(f"**{be:,.2f} ₽**" for be in be_points)
                st.caption(f"Точки безубыточности: {be_str}")

    # ==================================================================
    # БИРЖЕВЫЕ ГРАФИКИ D1 / H1
    # ==================================================================
    st.markdown("---")
    st.markdown("### Биржевые графики")

    _asset_ch = st.session_state.get("board_asset", "")
    _atype_ch = st.session_state.get("board_category", "")
    _series_ch = st.session_state.get("board_series_code", "")

    if not (_asset_ch and _series_ch):
        st.info("Выберите актив и серию на вкладке «Доска».")
    else:
        try:
            _eng, _mkt = _get_engine_market(_atype_ch)
            _secid_ch = resolve_underlying_secid(_asset_ch, _atype_ch) or _asset_ch

            _strikes_ch = []
            try:
                _board_ch = fetch_optionboard(_asset_ch, _atype_ch, _series_ch)
                _calls_ch = _board_ch.get('call') or []
                _puts_ch  = _board_ch.get('put')  or []
                _strikes_ch = sorted({
                    float(c['strike']) for c in _calls_ch
                    if c.get('strike') is not None
                } | {
                    float(p['strike']) for p in _puts_ch
                    if p.get('strike') is not None
                })
            except Exception:
                pass

            _df_d1 = fetch_bars(_secid_ch, interval=24, days=180,
                                engine=_eng, market=_mkt)
            _df_h1 = fetch_bars(_secid_ch, interval=60, days=25,
                                engine=_eng, market=_mkt)

            _levels_ch = find_alert_levels(_asset_ch, category=_atype_ch)
            _buy_ch = float(_levels_ch["buy"] or 0) if _levels_ch["found"] else 0.0
            _sell_ch = float(_levels_ch["sell"] or 0) if _levels_ch["found"] else 0.0

            _current_price_ch = None
            try:
                _current_price_ch = get_last_close_price(_secid_ch, _eng, _mkt)
            except Exception:
                pass

            render_exchange_chart(_df_d1, st.session_state.get("positions", []),
                                  _buy_ch, _sell_ch, _strikes_ch,
                                  f"D1 — {_asset_ch}", "chart_d1_tab",
                                  current_price=_current_price_ch,
                                  comm_func=_calc_comm_ui)
            render_exchange_chart(_df_h1, st.session_state.get("positions", []),
                                  _buy_ch, _sell_ch, _strikes_ch,
                                  f"H1 — {_asset_ch}", "chart_h1_tab",
                                  current_price=_current_price_ch,
                                  comm_func=_calc_comm_ui)
        except Exception as e:
            st.warning(f"Не удалось построить графики: {e}")
            # ==================================================================
# ============ ВКЛАДКА 4: ОПОВЕЩЕНИЯ ===============================
# ==================================================================
@st.fragment
def _render_alerts_tab():
    st.header("Оповещения по уровням")

    if "alerts_df" not in st.session_state:
        st.session_state.alerts_df = None
    if "alerts_source" not in st.session_state:
        st.session_state.alerts_source = "—"
    if "alerts_loaded_at" not in st.session_state:
        st.session_state.alerts_loaded_at = None
    if "alerts_error" not in st.session_state:
        st.session_state.alerts_error = None
    if "sheet_cache_buster" not in st.session_state:
        st.session_state.sheet_cache_buster = 0
    if "alerts_view_mode" not in st.session_state:
        st.session_state.alerts_view_mode = "Карточки"

    _ctrl1, _ctrl2, _ctrl3, _ctrl4 = st.columns([1, 1, 1.4, 1.6])

    with _ctrl1:
        if st.button("🔄 Обновить", use_container_width=True,
                     type="primary", key="alerts_manual_refresh"):
            st.session_state.sheet_cache_buster += 1
            st.session_state.alerts_loaded_at = None
            st.session_state["_alert_levels_cache"] = {}
            st.rerun()

    with _ctrl2:
        with st.popover("📂 Excel", use_container_width=True):
            st.markdown("**Загрузить Excel вручную**")
            _xls_file = st.file_uploader(
                "Excel-файл (.xlsx, .xls)",
                type=["xlsx", "xls"],
                key="alerts_excel_uploader",
                label_visibility="collapsed")
            if _xls_file is not None:
                try:
                    _xls_raw = pd.read_excel(_xls_file)
                    _df_norm, _err_norm = _normalize_alerts_df(_xls_raw)
                    if _err_norm:
                        st.error(_err_norm)
                    else:
                        st.session_state.alerts_df = _df_norm
                        st.session_state.alerts_source = "Excel (ручная загрузка)"
                        st.session_state.alerts_loaded_at = datetime.now().strftime("%H:%M:%S")
                        st.session_state.alerts_error = None
                        st.session_state["_alert_levels_cache"] = {}
                        st.success(f"Загружено: {len(_df_norm)} строк")
                        st.rerun()
                except Exception as _e:
                    st.error(f"Ошибка чтения Excel: {_e}")

    with _ctrl3:
        _view_mode = st.radio(
            "Вид", ["Карточки", "Таблица"],
            index=0 if st.session_state.alerts_view_mode == "Карточки" else 1,
            horizontal=True, label_visibility="collapsed",
            key="alerts_view_mode_radio")
        st.session_state.alerts_view_mode = _view_mode

    with _ctrl4:
        if st.session_state.alerts_loaded_at:
            _src_label = st.session_state.alerts_source
            st.caption(f"Источник: **{_src_label}** · "
                       f"обновлено: {st.session_state.alerts_loaded_at}")
        else:
            st.caption("Загрузка данных…")

    st.markdown("---")

    if st.session_state.alerts_source != "Excel (ручная загрузка)":
        _xls_gs, _err_gs = load_google_sheet_cached(
            ALERTS_SHEET_URL,
            st.session_state.sheet_cache_buster)

        if _err_gs:
            st.session_state.alerts_error = _err_gs
        elif not _xls_gs.empty:
            _df_norm_gs, _err_norm_gs = _normalize_alerts_df(_xls_gs)
            if _err_norm_gs:
                st.session_state.alerts_error = _err_norm_gs
            else:
                st.session_state.alerts_df = _df_norm_gs
                st.session_state.alerts_source = "Google Sheets"
                st.session_state.alerts_loaded_at = datetime.now().strftime("%H:%M:%S")
                st.session_state.alerts_error = None

    if st.session_state.alerts_error:
        st.warning(f"⚠ {st.session_state.alerts_error}")

    if st.session_state.alerts_df is None or st.session_state.alerts_df.empty:
        st.info("Нет данных для отображения. Загрузите Excel или проверьте "
                "доступность Google Sheets.")
    else:
        @st.fragment(run_every="30s")
        def _render_alerts_live():
            _df_alerts = st.session_state.get("alerts_df")
            if _df_alerts is None or _df_alerts.empty:
                return

            _rows_out = []
            for _, _row in _df_alerts.iterrows():
                _ticker = str(_row["Тикер БА"]).strip()
                _category = str(_row["Категория БА"]).strip()
                _lvl_buy = float(_row["Уровень покупок"])
                _lvl_sell = float(_row["Уровень продаж"])

                _last = None
                try:
                    _secid_alert = resolve_underlying_secid(_ticker.upper(),
                                                            _category)
                    if _secid_alert:
                        _eng_alert, _mkt_alert = _get_engine_market(_category)
                        _last = get_last_close_price(_secid_alert,
                                                     _eng_alert, _mkt_alert)
                except Exception:
                    pass

                if _last is None:
                    try:
                        _secid_alert = resolve_underlying_secid(
                            _ticker.upper(), _category)
                        if _secid_alert:
                            _info_fb = fetch_last_price_from_iss(_secid_alert,
                                                                 _category)
                            if _info_fb and _info_fb.get("last"):
                                _last = float(_info_fb["last"])
                    except Exception:
                        pass

                if _last and _last > 0:
                    _buy_dev = (_lvl_buy - _last) / _last * 100.0
                    _sell_dev = (_lvl_sell - _last) / _last * 100.0
                    _buy_active = _last <= _lvl_buy
                    _sell_active = _last >= _lvl_sell
                else:
                    _buy_dev = None
                    _sell_dev = None
                    _buy_active = False
                    _sell_active = False

                _rows_out.append({
                    "ticker": _ticker,
                    "category": _category,
                    "lvl_buy": _lvl_buy,
                    "lvl_sell": _lvl_sell,
                    "buy_dev_pct": _buy_dev,
                    "sell_dev_pct": _sell_dev,
                    "market_price": _last,
                    "buy_active": _buy_active,
                    "sell_active": _sell_active,
                })

            _n_total = len(_rows_out)
            _n_buy = sum(1 for _r in _rows_out if _r["buy_active"])
            _n_sell = sum(1 for _r in _rows_out if _r["sell_active"])
            _n_quotes = sum(1 for _r in _rows_out if _r["market_price"])

            _s1, _s2, _s3, _s4 = st.columns(4)
            with _s1:
                st.metric("Всего тикеров", _n_total)
            with _s2:
                st.metric("С котировкой", _n_quotes)
            with _s3:
                st.metric("Покупка активна", _n_buy)
            with _s4:
                st.metric("Продажа активна", _n_sell)

            st.caption("🔄 Автообновление каждые 30 секунд · "
                       "Цена = CLOSE последнего дневного бара (MOEX ISS)")

            st.markdown("---")

            if st.session_state.alerts_view_mode == "Карточки":
                _cards_per_row = 2
                for _i in range(0, len(_rows_out), _cards_per_row):
                    _cols = st.columns(_cards_per_row)
                    for _j, _r in enumerate(_rows_out[_i:_i + _cards_per_row]):
                        with _cols[_j]:
                            st.markdown(_render_alert_card(_r),
                                        unsafe_allow_html=True)
            else:
                _tbl_rows = []
                for _r in _rows_out:
                    _tbl_rows.append({
                        "Тикер БА": _r["ticker"],
                        "Категория БА": _r["category"],
                        "Уровень покупок": _r["lvl_buy"],
                        "Откл. покупок, %": _r["buy_dev_pct"],
                        "Уровень продаж": _r["lvl_sell"],
                        "Откл. продаж, %": _r["sell_dev_pct"],
                        "Рыночная цена": _r["market_price"],
                        "Покупка активна": _r["buy_active"],
                        "Продажа активна": _r["sell_active"],
                    })
                _df_out = pd.DataFrame(_tbl_rows)

                def _style_alert_row(_row):
                    _styles = []
                    for _col in _row.index:
                        _style = ""
                        if _col in ("Покупка активна", "Продажа активна"):
                            if _row[_col] is True:
                                _style = ("background-color:#0a8f3c; "
                                          "color:#ffffff; font-weight:700;")
                        elif _col == "Откл. покупок, %" and _row[_col] is not None:
                            _style = ("color:#00a651; font-weight:700;"
                                      if _row[_col] <= 0
                                      else "color:#d32f2f;")
                        elif _col == "Откл. продаж, %" and _row[_col] is not None:
                            _style = ("color:#00a651; font-weight:700;"
                                      if _row[_col] >= 0
                                      else "color:#d32f2f;")
                        _styles.append(_style)
                    return _styles

                st.dataframe(
                    _df_out.style.apply(_style_alert_row, axis=1).format({
                        "Уровень покупок":   "{:,.2f}",
                        "Уровень продаж":    "{:,.2f}",
                        "Откл. покупок, %":  "{:+.2f} %",
                        "Откл. продаж, %":   "{:+.2f} %",
                        "Рыночная цена":     "{:,.2f}",
                        "Покупка активна":   lambda v: "✓ АКТИВНО" if v else "·",
                        "Продажа активна":   lambda v: "✓ АКТИВНО" if v else "·"},
                        na_rep="—"),
                    use_container_width=True, hide_index=True, height=600)

            _df_export = pd.DataFrame(_rows_out)
            if not _df_export.empty:
                _df_export = _df_export.rename(columns={
                    "ticker": "Тикер БА", "category": "Категория БА",
                    "lvl_buy": "Уровень покупок",
                    "buy_dev_pct": "Откл. покупок, %",
                    "lvl_sell": "Уровень продаж",
                    "sell_dev_pct": "Откл. продаж, %",
                    "market_price": "Рыночная цена",
                    "buy_active": "Покупка активна",
                    "sell_active": "Продажа активна",
                })
                st.download_button(
                    "📤 Экспорт оповещений (CSV)",
                    data=_df_export.to_csv(index=False).encode("utf-8-sig"),
                    file_name="alerts.csv", mime="text/csv",
                    use_container_width=True,
                    key="alerts_export_csv")

        _render_alerts_live()


# ==================================================================
# ============ ВЫЗОВ РЕНДЕР-ФУНКЦИЙ ВНУТРИ st.tabs =================
# ==================================================================
# 🔧 Порядок: Калькулятор → Доска → Позиция → Оповещения
with tab_calc:
    _render_calc_tab()

with tab_board:
    _render_board_tab()

with tab_position:
    _render_position_tab()

with tab_alerts:
    _render_alerts_tab()
