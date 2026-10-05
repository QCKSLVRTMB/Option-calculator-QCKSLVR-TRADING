import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import numpy as np
import json
import math
import re
import uuid
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
SECURITIES_URL = ("https://iss.moex.com/iss/engines/futures/markets/options/"
                  "securities.json?iss.meta=off")

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
    "Long Call": {
        "category": "Одиночные",
        "description": "Покупка опциона Call — ставка на рост",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Buy Call)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K"},
        ],
    },
    "Long Put": {
        "category": "Одиночные",
        "description": "Покупка опциона Put — ставка на падение",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Buy Put)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K"},
        ],
    },
    "Short Call": {
        "category": "Одиночные",
        "description": "Продажа опциона Call",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Sell Call)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K"},
        ],
    },
    "Short Put": {
        "category": "Одиночные",
        "description": "Продажа опциона Put",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Sell Put)", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K"},
        ],
    },
    "Bull Call Spread": {
        "category": "Вертикальные спреды",
        "description": "Buy Call (низ) + Sell Call (верх)",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Buy Call (низ)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K_low"},
            {"label": "Sell Call (верх)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Bear Call Spread": {
        "category": "Вертикальные спреды",
        "description": "Sell Call (низ) + Buy Call (верх)",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Sell Call (низ)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K_low"},
            {"label": "Buy Call (верх)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Bull Put Spread": {
        "category": "Вертикальные спреды",
        "description": "Sell Put (верх) + Buy Put (низ)",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Buy Put (низ)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K_low"},
            {"label": "Sell Put (верх)", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Bear Put Spread": {
        "category": "Вертикальные спреды",
        "description": "Buy Put (верх) + Sell Put (низ)",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Sell Put (низ)", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K_low"},
            {"label": "Buy Put (верх)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Long Butterfly (Call)": {
        "category": "Бабочки",
        "description": "Buy 1 Call (K1) + Sell 2 Call (K2) + Buy 1 Call (K3). K1<K2<K3",
        "strike_order": ["K1", "K2", "K3"],
        "legs": [
            {"label": "Buy Call (K1 — низ)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K1"},
            {"label": "Sell Call ×2 (K2 — центр)", "option": "Call",
             "side": "Sell", "qty": 2, "strike_group": "K2"},
            {"label": "Buy Call (K3 — верх)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K3"},
        ],
    },
    "Short Butterfly (Call)": {
        "category": "Бабочки",
        "description": "Sell 1 Call + Buy 2 Call + Sell 1 Call",
        "strike_order": ["K1", "K2", "K3"],
        "legs": [
            {"label": "Sell Call (K1)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K1"},
            {"label": "Buy Call ×2 (K2)", "option": "Call",
             "side": "Buy", "qty": 2, "strike_group": "K2"},
            {"label": "Sell Call (K3)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K3"},
        ],
    },
    "Long Butterfly (Put)": {
        "category": "Бабочки",
        "description": "Buy 1 Put + Sell 2 Put + Buy 1 Put",
        "strike_order": ["K1", "K2", "K3"],
        "legs": [
            {"label": "Buy Put (K1)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K1"},
            {"label": "Sell Put ×2 (K2)", "option": "Put",
             "side": "Sell", "qty": 2, "strike_group": "K2"},
            {"label": "Buy Put (K3)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K3"},
        ],
    },
    "Short Cat (Кошка)": {
        "category": "Кошка",
        "description": "Buy Put (K1) + Sell Put (K2) + Sell Call (K3) + Buy Call (K4)",
        "strike_order": ["K1", "K2", "K3", "K4"],
        "legs": [
            {"label": "Buy Put (K1)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K1"},
            {"label": "Sell Put (K2)", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K2"},
            {"label": "Sell Call (K3)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K3"},
            {"label": "Buy Call (K4)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K4"},
        ],
    },
    "Iron Condor": {
        "category": "Кондоры",
        "description": "Buy Put + Sell Put + Sell Call + Buy Call",
        "strike_order": ["K1", "K2", "K3", "K4"],
        "legs": [
            {"label": "Buy Put (K1)", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K1"},
            {"label": "Sell Put (K2)", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K2"},
            {"label": "Sell Call (K3)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K3"},
            {"label": "Buy Call (K4)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K4"},
        ],
    },
    "Long Straddle": {
        "category": "Straddle / Strangle",
        "description": "Buy Call + Buy Put на одном страйке",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Buy Call + Buy Put)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K"},
        ],
    },
    "Short Straddle": {
        "category": "Straddle / Strangle",
        "description": "Sell Call + Sell Put на одном страйке",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Sell Call + Sell Put)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K"},
        ],
    },
    "Long Strangle": {
        "category": "Straddle / Strangle",
        "description": "Buy OTM Put + Buy OTM Call",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Buy Put (нижний)",  "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K_low"},
            {"label": "Buy Call (верхний)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Short Strangle": {
        "category": "Straddle / Strangle",
        "description": "Sell OTM Put + Sell OTM Call",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Sell Put (нижний)",  "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K_low"},
            {"label": "Sell Call (верхний)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Call Ratio Spread": {
        "category": "Ratio / Backspread",
        "description": "Buy 1 Call + Sell 2 Call",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Buy Call (низ)",      "option": "Call",
             "side": "Buy",  "qty": 1, "strike_group": "K_low"},
            {"label": "Sell Call ×2 (верх)", "option": "Call",
             "side": "Sell", "qty": 2, "strike_group": "K_high"},
        ],
    },
    "Put Ratio Spread": {
        "category": "Ratio / Backspread",
        "description": "Buy 1 Put + Sell 2 Put",
        "strike_order": ["K_low", "K_high"],
        "legs": [
            {"label": "Sell Put ×2 (низ)",   "option": "Put",
             "side": "Sell", "qty": 2, "strike_group": "K_low"},
            {"label": "Buy Put (верх)",      "option": "Put",
             "side": "Buy",  "qty": 1, "strike_group": "K_high"},
        ],
    },
    "Synthetic Long Futures": {
        "category": "Синтетика",
        "description": "Buy Call + Sell Put на одном страйке",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Buy Call + Sell Put)", "option": "Call",
             "side": "Buy",  "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K"},
        ],
    },
    "Synthetic Short Futures": {
        "category": "Синтетика",
        "description": "Sell Call + Buy Put на одном страйке",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Sell Call + Buy Put)", "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put",
             "side": "Buy",  "qty": 1, "strike_group": "K"},
        ],
    },
    "Strap": {
        "category": "Strap / Strip",
        "description": "Buy 2 Call + Buy 1 Put на одном страйке",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Buy 2 Call + Buy 1 Put)", "option": "Call",
             "side": "Buy", "qty": 2, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put",
             "side": "Buy", "qty": 1, "strike_group": "K"},
        ],
    },
    "Strip": {
        "category": "Strap / Strip",
        "description": "Buy 1 Call + Buy 2 Put на одном страйке",
        "strike_order": [],
        "legs": [
            {"label": "Страйк (Buy 1 Call + Buy 2 Put)", "option": "Call",
             "side": "Buy", "qty": 1, "strike_group": "K"},
            {"label": "тот же страйк", "option": "Put",
             "side": "Buy", "qty": 2, "strike_group": "K"},
        ],
    },
    "Ladder Call": {
        "category": "Ladder",
        "description": "Buy 1 Call (K1) + Sell Call (K2) + Sell Call (K3)",
        "strike_order": ["K1", "K2", "K3"],
        "legs": [
            {"label": "Buy Call (K1)",     "option": "Call",
             "side": "Buy",  "qty": 1, "strike_group": "K1"},
            {"label": "Sell Call (K2)",    "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K2"},
            {"label": "Sell Call (K3)",    "option": "Call",
             "side": "Sell", "qty": 1, "strike_group": "K3"},
        ],
    },
    "Ladder Put": {
        "category": "Ladder",
        "description": "Buy 1 Put (K1) + Sell Put (K2) + Sell Put (K3)",
        "strike_order": ["K1", "K2", "K3"],
        "legs": [
            {"label": "Buy Put (K1)",      "option": "Put",
             "side": "Buy",  "qty": 1, "strike_group": "K1"},
            {"label": "Sell Put (K2)",     "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K2"},
            {"label": "Sell Put (K3)",     "option": "Put",
             "side": "Sell", "qty": 1, "strike_group": "K3"},
        ],
    },
}
# ================= Дивиденды (smart-lab.ru) =================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dividends_smartlab() -> pd.DataFrame:
    url = "https://smart-lab.ru/dividends/index/order_by_ticker/desc/"
    headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36")}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        st.warning(f"Не удалось загрузить таблицу дивидендов: {e}")
        return pd.DataFrame(columns=["ticker", "dividend_rub",
                                     "record_date", "stock_price"])

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text,
                      flags=re.DOTALL | re.IGNORECASE)
    records = []
    for row_html in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html,
                           flags=re.DOTALL | re.IGNORECASE)
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
        records.append({
            "ticker": ticker,
            "dividend_rub": dividend,
            "record_date": record_date,
            "stock_price": stock_price,
        })
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
    q = div / price
    return q, float(price), row["record_date"]


# ================= G-кривая (безрисковая ставка) =================

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_g_curve_params():
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
        }
    except Exception as e:
        st.warning(f"Ошибка разбора параметров G-кривой: {e}")
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
            term4 += g[i] * math.exp(-((t_years - _GC_A[i]) ** 2)
                                     / (_GC_B[i] ** 2))
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


# ================= Получение LAST-цены БА с ISS MOEX =================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_last_price_from_iss(secid: str, asset_type_ui: str):
    """Возвращает последнюю цену сделки (LAST) с ISS MOEX."""
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
    params = {"iss.meta": "off", "iss.only": "marketdata"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
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


@st.cache_data(ttl=3600, show_spinner=False)
def resolve_underlying_secid(asset_code: str, asset_type_ui: str):
    """Определяет SECID базового актива для запроса LAST."""
    if asset_type_ui == "Акция":
        return asset_code.upper()
    if asset_type_ui == "Индекс":
        idx_map = {"RTS": "RTSI", "MIX": "IMOEX"}
        return idx_map.get(asset_code.upper(), asset_code.upper())

    if asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
        try:
            url = ("https://iss.moex.com/iss/engines/futures/markets/forts/"
                   "securities.json")
            r = requests.get(url,
                             params={"iss.meta": "off", "iss.only": "securities"},
                             timeout=15)
            r.raise_for_status()
            data = r.json()
            cols = data["securities"]["columns"]
            rows = data["securities"]["data"]
            df = pd.DataFrame(rows, columns=cols)
            if "ASSETCODE" not in df.columns:
                return None
            df = df[df["ASSETCODE"] == asset_code.upper()]
            if df.empty:
                return None
            if "LASTTRADEDATE" in df.columns:
                df = df.dropna(subset=["LASTTRADEDATE"])
                df = df.sort_values("LASTTRADEDATE")
            return df.iloc[0]["SECID"] if not df.empty else None
        except Exception:
            return None

    return asset_code.upper()


# ================= MOEX fetch =================

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
                series.append({'code': item['optionseries_code'],
                               'expiry': item['expiration_date']})
    elif isinstance(data, dict) and 'data' in data:
        for item in data['data']:
            if 'optionseries_code' in item and 'expiration_date' in item:
                series.append({'code': item['optionseries_code'],
                               'expiry': item['expiration_date']})
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


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_optionboard_raw(asset_code: str, series_code: str, asset_type: str):
    """Прямой запрос optionboard без постобработки (внутреннее)."""
    for at in [asset_type, 'share', 'futures', 'index', 'currency', 'commodity']:
        url = (f"{API_BASE_URL}/assets/{asset_code}"
               f"/optionseries/{series_code}/optionboard")
        try:
            r = requests.get(url, params={'asset_type': at}, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None


def fetch_central_strike(asset_code, series_code, asset_type):
    """Пытается получить central_strike:
       1) из MOEX ISS;
       2) если пусто — из ближайшего страйка к теоретической цене БА
          (через паритет call-put).
    """
    # ---- Попытка 1: ISS ----
    url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}"
    try:
        r = requests.get(url, params={'asset_type': asset_type}, timeout=10)
        if r.status_code == 200:
            cs = r.json().get('central_strike')
            if cs:
                try:
                    return float(cs)
                except (TypeError, ValueError):
                    pass
    except Exception:
        pass

    # ---- Попытка 2: вычисление через паритет ----
    try:
        board = _fetch_optionboard_raw(asset_code, series_code, asset_type)
        if board:
            calls = board.get('call') or []
            puts = board.get('put') or []
            c_map = {
                c['strike']: c for c in calls
                if c.get('theorprice') and c.get('strike') is not None
            }
            p_map = {
                p['strike']: p for p in puts
                if p.get('theorprice') and p.get('strike') is not None
            }
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
    asset_code, _ = get_asset_code_and_type(asset, asset_type_ui)
    board_data, used_asset_type = None, None
    for at in ['share', 'futures', 'index', 'currency', 'commodity']:
        url = (f"{API_BASE_URL}/assets/{asset_code}"
               f"/optionseries/{series_code}/optionboard")
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
    board_data['central_strike'] = fetch_central_strike(asset_code,
                                                        series_code,
                                                        used_asset_type)
    board_data['series_code'] = series_code
    return board_data


@st.cache_data(ttl=300, show_spinner=False)
def fetch_volatility_graph(asset: str, series_code: str, asset_type_ui: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = (f"{API_BASE_URL}/assets/{asset_code}"
           f"/optionseries/{series_code}/volatility_graph")
    try:
        r = requests.get(url, params={'asset_type': moex_type}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


# ================= Вспомогательные функции =================

def _color_call_put(option: str) -> str:
    """HTML-строка для опциона: Call — зелёный, Put — красный."""
    if option == "Call":
        return f"<span style='color:#00a651; font-weight:700;'>{option}</span>"
    if option == "Put":
        return f"<span style='color:#d32f2f; font-weight:700;'>{option}</span>"
    return option


def _color_side(side: str) -> str:
    """HTML-строка для направления: Buy — зелёный, Sell — красный."""
    if side == "Buy":
        return f"<span style='color:#00a651; font-weight:700;'>Buy</span>"
    if side == "Sell":
        return f"<span style='color:#d32f2f; font-weight:700;'>Sell</span>"
    return side


def _side_from_qty(qty: int) -> str:
    return "Buy" if qty >= 0 else "Sell"


def _new_position_id() -> str:
    return uuid.uuid4().hex[:8]


# ================= Цветовые маркеры дат =================

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


# ================= Матчинг стратегий с текущими позициями =================

def _leg_matches_position(leg, pos):
    if not pos.get("visible", True):
        return False
    if pos.get("Опцион") != leg["option"]:
        return False
    pos_side = "Buy" if int(pos.get("Кол-во", 0)) >= 0 else "Sell"
    if pos_side != leg["side"]:
        return False
    return True


def match_strategy_with_positions(strategy_def, positions):
    matched = {}
    used_positions = set()
    matched_strikes_by_group = {}
    total_required = 0
    total_covered = 0

    for li, leg in enumerate(strategy_def["legs"]):
        req_qty = leg["qty"]
        total_required += req_qty
        best_pi = None
        best_cover = 0

        for pi, p in enumerate(positions):
            if pi in used_positions:
                continue
            if not _leg_matches_position(leg, p):
                continue
            have = abs(int(p.get("Кол-во", 0)))
            cover = min(have, req_qty)
            if cover > best_cover:
                best_cover = cover
                best_pi = pi

        if best_pi is not None:
            used_positions.add(best_pi)
            matched[li] = {
                "pos_index": best_pi,
                "qty_covered": best_cover,
                "qty_required": req_qty,
                "full": best_cover >= req_qty,
            }
            total_covered += best_cover
            grp = leg["strike_group"]
            if grp not in matched_strikes_by_group:
                matched_strikes_by_group[grp] = float(
                    positions[best_pi]["Страйк"]
                )

    missing = [i for i in range(len(strategy_def["legs"]))
               if i not in matched]
    weight = total_covered / total_required if total_required else 0.0

    return {
        "matched": matched,
        "missing": missing,
        "matched_strikes_by_group": matched_strikes_by_group,
        "weight": weight,
        "is_full": all(m["full"] for m in matched.values())
                  and not missing,
    }


def validate_strike_order(strategy_def, strike_values):
    order = strategy_def.get("strike_order", [])
    if len(order) < 2:
        return True, ""

    vals = []
    for grp in order:
        v = strike_values.get(grp)
        if v is None:
            return False, f"Не задан страйк для группы «{grp}»"
        vals.append(float(v))

    for i in range(1, len(vals)):
        if vals[i] <= vals[i - 1]:
            grps_txt = " < ".join(order)
            return False, (f"Нарушен порядок страйков: требуется "
                           f"{grps_txt}. Сейчас: "
                           + " < ".join(f"{order[j]}={int(vals[j])}"
                                        for j in range(len(vals))))
    return True, ""


def suggest_strike_for_group(grp, strategy_def, matched_strikes,
                              strike_order, all_strikes, central):
    if grp in matched_strikes:
        return matched_strikes[grp]

    order = [g for g in strike_order] if strike_order else []
    if grp not in order or not all_strikes:
        return central

    idx = order.index(grp)
    left_grp = None
    for j in range(idx - 1, -1, -1):
        if order[j] in matched_strikes:
            left_grp = order[j]
            break
    right_grp = None
    for j in range(idx + 1, len(order)):
        if order[j] in matched_strikes:
            right_grp = order[j]
            break

    if left_grp is not None and right_grp is not None:
        K_left = float(matched_strikes[left_grp])
        K_right = float(matched_strikes[right_grp])
        n_steps = (order.index(right_grp) - order.index(left_grp))
        step = (K_right - K_left) / max(n_steps, 1)
        target = K_left + step * (idx - order.index(left_grp))
        return min(all_strikes, key=lambda k: abs(float(k) - target))

    if left_grp is not None:
        K_left = float(matched_strikes[left_grp])
        return min(all_strikes, key=lambda k: abs(float(k) - K_left))

    if right_grp is not None:
        K_right = float(matched_strikes[right_grp])
        return min(all_strikes, key=lambda k: abs(float(k) - K_right))

    return central


def compute_strategy_debit_credit(strategy_def, strike_values, price_getter):
    total = 0.0
    for leg in strategy_def["legs"]:
        grp = leg["strike_group"]
        K = strike_values.get(grp)
        if K is None:
            return None
        price = price_getter(leg["option"], K)
        if price is None or price <= 0:
            return None
        sign = 1 if leg["side"] == "Buy" else -1
        total += sign * leg["qty"] * price
    return total


def _card_style_full():
    return "border:2px solid #00a651;"


def _card_style_partial():
    return "border:1px solid #e2edf4;"


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
    }, delays=(200, 500, 1000, 1500, 2200, 3000, 4000, 5500, 7000))


def push_tv_ticker(ticker_label: str, tv_symbol: str):
    _send_to_iframes({
        "type": "setTicker",
        "ticker": ticker_label,
        "symbol": tv_symbol,
    }, delays=(300, 700, 1200, 2000, 3500, 5000))


def push_strikes_to_calculator(strikes_iv: list, central_strike):
    _send_to_iframes({
        "type": "setStrikes",
        "strikes": strikes_iv,
        "central": central_strike,
    }, delays=(200, 500, 1000, 1500, 2200, 3000, 4000, 5500, 7000))


def push_risk_free_rate(rate_value):
    payload_value = float(rate_value) if rate_value is not None else 0.0
    _send_to_iframes({
        "type": "setRiskFree",
        "value": payload_value,
    }, delays=(500, 1500, 3000))


def push_dividend_yield(q_value):
    payload_value = float(q_value) if q_value is not None else 0.0
    _send_to_iframes({
        "type": "setDividend",
        "value": payload_value,
    }, delays=(700, 1700, 3200))
# ================= UI =================

st.title("MOEX Options & Black-Scholes")

# ---------- Читаем параметры калькулятора из URL один раз ----------
try:
    st.session_state["_calc_level_buy"] = float(
        st.query_params.get("level_buy", 0) or 0)
except (TypeError, ValueError):
    st.session_state["_calc_level_buy"] = 0.0

try:
    st.session_state["_calc_level_sell"] = float(
        st.query_params.get("level_sell", 0) or 0)
except (TypeError, ValueError):
    st.session_state["_calc_level_sell"] = 0.0

try:
    st.session_state["_calc_riskfree"] = float(
        st.query_params.get("rf", 0) or 0)
except (TypeError, ValueError):
    st.session_state["_calc_riskfree"] = 0.0

try:
    st.session_state["_calc_volatility"] = float(
        st.query_params.get("vol", 0) or 0)
except (TypeError, ValueError):
    st.session_state["_calc_volatility"] = 0.0

try:
    st.session_state["_calc_dividend"] = float(
        st.query_params.get("div", 0) or 0)
except (TypeError, ValueError):
    st.session_state["_calc_dividend"] = 0.0


tab_calc, tab_position, tab_board, tab_alerts = st.tabs([
    "Калькулятор",
    "Позиция",
    "Доска опционов и кривая волатильности",
    "Оповещения",
])


# ==================================================================
# ============ ВКЛАДКА 1: КАЛЬКУЛЯТОР =============================
# ==================================================================
with tab_calc:
    st.header("Выберите опционную серию")

    if "asset_input" not in st.session_state:
        st.session_state.asset_input = "RTS"
    if "asset_type_ui" not in st.session_state:
        st.session_state.asset_type_ui = "Фьючерс"

    with st.expander("Справочник инструментов MOEX — кликните по тикеру, "
                     "чтобы подставить его и категорию в поля ниже",
                     expanded=False):
        filter_text = st.text_input(
            "Поиск по коду или названию",
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
                st.session_state.series_list = fetch_optionseries(asset,
                                                                  asset_type_ui)
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

        st.session_state.selected_asset = asset
        st.session_state.selected_asset_type_ui = asset_type_ui
        st.session_state.selected_series_code = series_code
        st.session_state.selected_expiry = expiry_str

        st.caption(f"Выбрана дата экспирации: **{expiry_str}** "
                   f"(серия `{series_code}`)")

        # --- Безрисковая ставка ---
        if asset_type_ui == "Акция":
            rfr = get_risk_free_rate_for_expiry(expiry_str)
            if rfr is not None:
                st.caption(f"Безрисковая ставка (G-кривая ОФЗ MOEX): "
                           f"**{rfr:.4f} %**")
            else:
                st.caption("Не удалось получить ставку из G-кривой — оставлено 0.")
        else:
            rfr = None

        # --- Дивидендная доходность ---
        if asset_type_ui == "Акция":
            q, stock_price, rec_date = get_dividend_yield_for_ticker(
                asset, expiry_str
            )
            if q is not None and stock_price is not None:
                st.caption(
                    f"Дивидендная доходность (smart-lab.ru): "
                    f"q = **{q:.4f}** ({q*100:.2f} %) · "
                    f"цена акции = {stock_price:.2f} ₽ · "
                    f"закрытие реестра: {rec_date.strftime('%d.%m.%Y')}"
                )
            else:
                st.caption("Дивиденды по этому тикеру до экспирации "
                           "не найдены — q = 0.")
                q = None
        else:
            q = None

        tv_symbol = resolve_tv_ticker(asset, asset_type_ui)
        if tv_symbol:
            st.caption(f"Тикер TradingView: `{tv_symbol}`")
        else:
            st.warning(
                f"Для «{asset}» ({asset_type_ui}) не задан тикер TradingView. "
                f"Добавьте его в `TV_TICKER_MAP[\"{asset_type_ui}\"]` в `app.py`."
            )

        try:
            info = fetch_series_info(asset, asset_type_ui, series_code)
            with st.expander("Об опционной серии", expanded=False):
                st.json(info, expanded=True)
        except Exception as e:
            st.warning(f"Не удалось загрузить информацию о серии: {e}")

    else:
        st.info("Введите тикер базового актива и нажмите «Загрузить доску опционов».")

    # ---------- Калькулятор ----------
    st.markdown("---")
    calc_html = Path("index.html").read_text(encoding="utf-8")
    components.html(calc_html, height=1100, scrolling=True)

    # ---------- Push'и в калькулятор (после iframe) ----------
    if st.session_state.series_list and "selected_expiry" in st.session_state:
        _expiry_str = st.session_state.selected_expiry
        _series_code = st.session_state.selected_series_code

        push_expiry_to_calculator(_expiry_str, _series_code)

        if asset_type_ui == "Акция":
            push_risk_free_rate(rfr)
        else:
            push_risk_free_rate(0.0)

        if asset_type_ui == "Акция":
            push_dividend_yield(q)
        else:
            push_dividend_yield(0.0)

        tv_symbol = resolve_tv_ticker(asset, asset_type_ui)
        if tv_symbol:
            push_tv_ticker(asset, tv_symbol)


# ==================================================================
# ============ ВКЛАДКА 2: ПОЗИЦИЯ ==================================
# ==================================================================
with tab_position:
    st.header("Управление позицией")

    c1, c2, c3 = st.columns(3)
    with c1:
        deposit = st.number_input("Депозит, ₽",
                                  min_value=0.0, value=100000.0,
                                  step=1000.0, format="%.2f")
    with c2:
        risk_pct = st.number_input("Риск, %",
                                   min_value=1.0, max_value=100.0,
                                   value=1.0, step=1.0, format="%.0f")
    with c3:
        min_comm = st.number_input("Мин. комиссия, ₽/контракт",
                                   min_value=0.0, value=0.02,
                                   step=0.01, format="%.4f")

    risk_amount = deposit * risk_pct / 100.0
    st.info(
        f"**Доступно для сделки:** {risk_amount:,.2f} ₽ "
        f"({risk_pct}% от {deposit:,.0f} ₽) · "
        f"комиссия по тарифу «Инвестор»: "
        f"`max(3% × премия, {min_comm} ₽)`"
    )

    COMMISSION_RATE = 0.03

    def calc_commission(premium, minc):
        if premium is None or premium <= 0:
            return 0.0
        return max(COMMISSION_RATE * premium, minc)

    def _norm_cdf_py(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_py(S, K, T, r_pct, vol_pct, div_pct, opt_type):
        if T <= 0 or S <= 0 or K <= 0 or vol_pct <= 0:
            if opt_type == "call":
                return max(0.0, S - K)
            else:
                return max(0.0, K - S)
        r = r_pct / 100.0
        q = div_pct / 100.0
        sigma = vol_pct / 100.0
        d1 = (math.log(S / K) + (r - q + sigma * sigma / 2) * T) \
             / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        if opt_type == "call":
            return S * math.exp(-q * T) * _norm_cdf_py(d1) \
                   - K * math.exp(-r * T) * _norm_cdf_py(d2)
        else:
            return K * math.exp(-r * T) * _norm_cdf_py(-d2) \
                   - S * math.exp(-q * T) * _norm_cdf_py(-d1)

    # ---------- Билдер позиций ----------
    st.markdown("### Добавить позицию")

    if "positions" not in st.session_state:
        st.session_state.positions = []

    _existing_constructions = []
    for _p in st.session_state.positions:
        _c = _p.get("Конструкция", "Без названия")
        if _c not in _existing_constructions:
            _existing_constructions.append(_c)

    can_build = (
        st.session_state.get("series_list")
        and "selected_series_code" in st.session_state
    )

    if not can_build:
        st.warning("Сначала выберите серию на вкладке «Калькулятор» "
                   "и загрузите доску.")
    else:
        try:
            board = fetch_optionboard(
                st.session_state.get("selected_asset", ""),
                st.session_state.get("selected_asset_type_ui", ""),
                st.session_state.get("selected_series_code", ""),
            )
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
            expiry_now = st.session_state.get("selected_expiry", "—")

            # ---------- Быстрая вставка БА ----------
            st.markdown("**Добавить БА (фьючерс/акцию) одним кликом:**")
            qa1, qa2, qa3, qa4 = st.columns([2, 1.2, 1.6, 1.5])

            _und_label = (
                "Фьючерс" if asset_type_ui in ("Фьючерс", "Валюта", "Товар")
                else ("Акция" if asset_type_ui == "Акция" else "Индекс")
            )

            with qa1:
                _und_secid_quick = resolve_underlying_secid(asset, asset_type_ui)
                st.text_input(
                    f"SECID {_und_label}",
                    value=_und_secid_quick or "—",
                    disabled=True,
                    key="quick_und_secid_disp",
                )
            with qa2:
                _side_quick = st.selectbox("Направление",
                                           ["Buy", "Sell"],
                                           key="quick_und_side")
            with qa3:
                _qty_quick = st.number_input("Кол-во",
                                             min_value=1, value=1, step=1,
                                             key="quick_und_qty")
            with qa4:
                st.write("")
                if st.button("Подтянуть LAST", use_container_width=True):
                    _info = fetch_last_price_from_iss(_und_secid_quick,
                                                     asset_type_ui)
                    if _info["last"]:
                        st.session_state["quick_und_last_price"] = _info["last"]
                        st.success(
                            f"LAST = {_info['last']:.4f} ₽ "
                            f"(источник: {_info['source']})"
                        )
                    else:
                        st.error(
                            f"Не удалось получить LAST "
                            f"({_info['source']})."
                        )

            st.write("")

            # ---------- Форма добавления ----------
            with st.form("add_position_form", clear_on_submit=False):
                f1, f2, f3, f4 = st.columns([2, 2, 2, 1.6])
                with f1:
                    instrument_type = st.selectbox(
                        "Тип инструмента",
                        ["Опцион", asset_type_ui if asset_type_ui
                         in ("Фьючерс", "Валюта", "Товар") else
                         ("Акция" if asset_type_ui == "Акция" else "Индекс")],
                        key="form_instrument_type",
                    )
                with f2:
                    st.markdown(
                        "<div style='font-size:.72rem; font-weight:700; "
                        "color:#2c506d; margin-bottom:6px;'>Исполнение</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='padding:8px 14px; border:1px solid #cfdfe9; "
                        f"border-radius:18px; background:#fff; font-size:.9rem;'>"
                        f"{expiry_now}</div>",
                        unsafe_allow_html=True,
                    )
                with f3:
                    if all_strikes:
                        default_idx = 0
                        if central is not None:
                            try:
                                default_idx = all_strikes.index(
                                    min(all_strikes,
                                        key=lambda s: abs(float(s) - float(central)))
                                )
                            except ValueError:
                                default_idx = 0
                        chosen_strike = st.selectbox("Страйк", all_strikes,
                                                     index=default_idx,
                                                     key="form_strike")
                    else:
                        chosen_strike = None
                        st.selectbox("Страйк", ["—"], key="form_strike_empty")
                with f4:
                    opt_type = st.selectbox("Опцион", ["Call", "Put"],
                                            key="form_opt_type")

                f5, f6, f7, f8 = st.columns([2.4, 1.4, 1.2, 1.6])
                with f5:
                    ref_opt_for_ticker = (
                        (c_map.get(chosen_strike, {}) if opt_type == "Call"
                         else p_map.get(chosen_strike, {}))
                        if chosen_strike is not None else {}
                    )
                    ticker_val = ref_opt_for_ticker.get('secid', '—')
                    st.markdown(
                        "<div style='font-size:.72rem; font-weight:700; "
                        "color:#2c506d; margin-bottom:6px;'>Тикер</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='padding:8px 14px; border:1px solid #cfdfe9; "
                        f"border-radius:18px; background:#f9fbfd; font-size:.9rem;'>"
                        f"{ticker_val}</div>",
                        unsafe_allow_html=True,
                    )
                with f6:
                    side = st.selectbox("Направление", ["Buy", "Sell"],
                                        key="form_side")
                with f7:
                    qty_input = st.number_input("Кол-во", min_value=1, value=1,
                                                step=1, key="form_qty")
                with f8:
                    ref_opt = (c_map.get(chosen_strike, {}) if opt_type == "Call"
                               else p_map.get(chosen_strike, {})) if chosen_strike is not None else {}
                    _qs_last = st.session_state.get("quick_und_last_price", 0.0)
                    default_price = (
                        float(_qs_last) if instrument_type != "Опцион"
                        and _qs_last
                        else (float(ref_opt.get('theorprice') or 0)
                              or float(ref_opt.get('last') or 0) or 0.0)
                    )
                    price_input = st.number_input("Цена, ₽",
                                                  min_value=0.0,
                                                  value=float(default_price),
                                                  step=0.01,
                                                  format="%.4f",
                                                  key="form_price")

                # Конструкция
                fc1, fc2 = st.columns([2, 4])
                with fc1:
                    NEW_LABEL = "— Новая конструкция —"
                    constr_choice = st.selectbox(
                        "Конструкция",
                        [NEW_LABEL] + _existing_constructions,
                        key="form_constr_choice",
                    )
                with fc2:
                    if constr_choice == NEW_LABEL:
                        constr_name_input = st.text_input(
                            "Название новой конструкции",
                            value="",
                            placeholder="Например: Butterfly 87500/90000/92500",
                            key="form_constr_name",
                        )
                        construction_name = constr_name_input.strip() or "Без названия"
                    else:
                        construction_name = constr_choice
                        st.text_input("Название", value=construction_name,
                                      disabled=True, key="form_constr_disp")

                submitted = st.form_submit_button("Добавить позицию",
                                                  type="primary")

                if submitted:
                    if instrument_type != "Опцион":
                        _und_secid = resolve_underlying_secid(asset, asset_type_ui)
                        _last_info = fetch_last_price_from_iss(_und_secid,
                                                              asset_type_ui)
                        _last_price = _last_info["last"]

                        final_price = float(price_input) if price_input > 0 else (
                            float(_last_price) if _last_price else 0.0
                        )

                        if final_price > 0:
                            signed_qty = int(qty_input) if side == "Buy" \
                                         else -int(qty_input)
                            st.session_state.positions.append({
                                "_id": _new_position_id(),
                                "Конструкция": construction_name,
                                "Тип инструмента": instrument_type,
                                "Опцион": "БА",
                                "Направление": side,
                                "Страйк": None,
                                "Эксп.": "—",
                                "Тикер": _und_secid or '—',
                                "Кол-во": signed_qty,
                                "Цена": float(final_price),
                                "Теор.цена": float(_last_price) if _last_price else float(final_price),
                                "Дельта": None,
                                "Гамма":  None,
                                "Вега":   None,
                                "Тета":   None,
                                "Ро":     None,
                                "visible": True,
                            })
                            st.success(
                                f"Добавлено: {side} {instrument_type} "
                                f"{_und_secid} × {qty_input} по {final_price:.4f} ₽"
                            )
                            st.rerun()
                        else:
                            st.error("Не удалось определить цену БА. "
                                     "Введите вручную в поле «Цена, ₽».")
                    else:
                        if chosen_strike is not None and price_input > 0:
                            c_data = c_map.get(chosen_strike, {})
                            p_data = p_map.get(chosen_strike, {})
                            ref = c_data if opt_type == "Call" else p_data
                            signed_qty = int(qty_input) if side == "Buy" \
                                         else -int(qty_input)
                            st.session_state.positions.append({
                                "_id": _new_position_id(),
                                "Конструкция": construction_name,
                                "Тип инструмента": "Опцион",
                                "Опцион": opt_type,
                                "Направление": side,
                                "Страйк": chosen_strike,
                                "Эксп.": expiry_now,
                                "Тикер": ref.get('secid', '—'),
                                "Кол-во": signed_qty,
                                "Цена": float(price_input),
                                "Теор.цена": float(ref.get('theorprice') or 0),
                                "Дельта": ref.get('delta'),
                                "Гамма":  ref.get('gamma'),
                                "Вега":   ref.get('vega'),
                                "Тета":   ref.get('theta'),
                                "Ро":     ref.get('rho'),
                                "visible": True,
                            })
                            st.success(
                                f"Добавлено: {side} {opt_type} "
                                f"{chosen_strike} × {qty_input}"
                            )
                            st.rerun()
                        else:
                            st.error("Укажите страйк и цену > 0.")

            # ---------- Expander «Готовые стратегии» ----------
            with st.expander("Готовые стратегии (сборка в один клик)",
                             expanded=False):
                strat_names = list(PREDEFINED_STRATEGIES.keys())
                strat_choice = st.selectbox("Стратегия", strat_names,
                                            key="pos_strategy_choice")
                strat_def = PREDEFINED_STRATEGIES[strat_choice]
                st.caption(strat_def["description"])

                if not all_strikes:
                    st.error("Нет страйков в доске.")
                else:
                    strike_groups = []
                    for leg in strat_def["legs"]:
                        g = leg["strike_group"]
                        if g not in strike_groups:
                            strike_groups.append(g)

                    strike_values = {}
                    cols_strikes = st.columns(len(strike_groups))
                    for i, grp in enumerate(strike_groups):
                        with cols_strikes[i]:
                            grp_label = next(
                                (leg["label"] for leg in strat_def["legs"]
                                 if leg["strike_group"] == grp),
                                grp
                            )
                            default_idx = 0
                            if central is not None:
                                try:
                                    default_idx = all_strikes.index(
                                        min(all_strikes,
                                            key=lambda s: abs(float(s) - float(central)))
                                    )
                                except ValueError:
                                    default_idx = 0
                            strike_values[grp] = st.selectbox(
                                grp_label,
                                all_strikes,
                                index=default_idx,
                                key=f"strat_strike_{grp}",
                            )

                    # ---------- Множитель комплекта ----------
                    st.markdown("**Множитель комплекта (×):**")
                    mult_col1, mult_col2 = st.columns([1, 4])
                    with mult_col1:
                        multiplier = st.number_input(
                            "×", min_value=1, max_value=100,
                            value=1, step=1,
                            key=f"strat_mult_{strat_choice}",
                            label_visibility="collapsed",
                        )
                    with mult_col2:
                        st.caption(
                            "Все количества ног будут умножены на это число "
                            "(например ×2 → 2/4/2 для бабочки)."
                        )

                    # ---------- Цены и количества ----------
                    st.markdown("**Цены и количества ног:**")
                    leg_prices = {}
                    leg_qtys = {}
                    cols_legs = st.columns(len(strat_def["legs"]))
                    for i, leg in enumerate(strat_def["legs"]):
                        grp = leg["strike_group"]
                        K = strike_values[grp]
                        ref = c_map.get(K, {}) if leg["option"] == "Call" \
                              else p_map.get(K, {})
                        default_p = float(ref.get('theorprice') or 0) or \
                                    float(ref.get('last') or 0) or 0.0
                        with cols_legs[i]:
                            st.markdown(
                                f"<div style='font-size:.78rem; "
                                f"margin-bottom:4px;'>"
                                f"{_color_side(leg['side'])} "
                                f"{_color_call_put(leg['option'])} "
                                f"K={K}</div>",
                                unsafe_allow_html=True,
                            )
                            leg_prices[i] = st.number_input(
                                "Цена, ₽",
                                min_value=0.0,
                                value=float(default_p),
                                step=0.01, format="%.4f",
                                key=f"strat_price_{i}_{strat_choice}",
                            )
                            leg_qtys[i] = st.number_input(
                                "Кол-во",
                                min_value=1, max_value=1000,
                                value=int(leg["qty"]) * int(multiplier),
                                step=1,
                                key=f"strat_qty_{i}_{strat_choice}",
                            )

                    strike_suffix = "/".join(
                        str(int(strike_values[g]))
                        if float(strike_values[g]).is_integer()
                        else str(strike_values[g])
                        for g in strike_groups
                    )
                    auto_name = f"{strat_choice} {strike_suffix}"
                    if multiplier > 1:
                        auto_name += f" ×{int(multiplier)}"
                    final_strategy_name = st.text_input(
                        "Имя конструкции",
                        value=auto_name,
                        key="strat_final_name",
                    ).strip() or auto_name

                    if st.button("Собрать конструкцию", type="primary",
                                 key="strat_build_btn"):
                        added = 0
                        for i, leg in enumerate(strat_def["legs"]):
                            grp = leg["strike_group"]
                            K = strike_values[grp]
                            price = leg_prices[i]
                            qty_leg = int(leg_qtys[i])
                            if price <= 0 or qty_leg <= 0:
                                continue
                            ref = c_map.get(K, {}) if leg["option"] == "Call" \
                                  else p_map.get(K, {})
                            signed_qty = qty_leg if leg["side"] == "Buy" \
                                         else -qty_leg
                            st.session_state.positions.append({
                                "_id": _new_position_id(),
                                "Конструкция": final_strategy_name,
                                "Тип инструмента": "Опцион",
                                "Опцион": leg["option"],
                                "Направление": leg["side"],
                                "Страйк": K,
                                "Эксп.": expiry_now,
                                "Тикер": ref.get('secid', '—'),
                                "Кол-во": int(signed_qty),
                                "Цена": float(price),
                                "Теор.цена": float(ref.get('theorprice') or 0),
                                "Дельта": ref.get('delta'),
                                "Гамма":  ref.get('gamma'),
                                "Вега":   ref.get('vega'),
                                "Тета":   ref.get('theta'),
                                "Ро":     ref.get('rho'),
                                "visible": True,
                            })
                            added += 1
                        if added:
                            st.success(
                                f"Собрано {added} ног в «{final_strategy_name}»"
                            )
                            st.rerun()
                        else:
                            st.error("Укажите цену и количество > 0.")
    # ---------- Текущие позиции (с редактированием) ----------
    st.markdown("### Текущие позиции")

    if not st.session_state.positions:
        st.caption("Портфель пуст.")
    else:
        # Заголовок таблицы
        hdr = st.columns([0.4, 0.4, 1.2, 0.9, 1.0, 1.6, 1.6, 0.8, 1.0, 1.0,
                          0.8, 0.8, 0.8, 0.8, 0.8])
        headers = ["", "", "Опцион", "Страйк", "Тикер", "Кол-во", "Цена",
                   "Комис.", "Эфф. цена", "Теор.цена", "Δ", "Γ", "ν", "Θ", "P&L"]
        for c, h in zip(hdr, headers):
            with c:
                st.markdown(
                    f"<div style='font-size:.7rem; color:#2c506d; "
                    f"font-weight:700; text-transform:uppercase; "
                    f"letter-spacing:.03em; padding-top:2px;'>{h}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown(
            "<hr style='margin:4px 0 8px 0; border:none; "
            "border-top:1px solid #e6edf4;'>",
            unsafe_allow_html=True,
        )

        for idx, p in enumerate(st.session_state.positions):
            _id = p.get("_id", f"legacy_{idx}")
            visible = p.get("visible", True)
            gray = "opacity:0.45;" if not visible else ""

            row = st.columns([0.4, 0.4, 1.2, 0.9, 1.0, 1.6, 1.6, 0.8, 1.0,
                              1.0, 0.8, 0.8, 0.8, 0.8, 0.8])

            # ❌ Удалить
            with row[0]:
                if st.button("✖", key=f"del_{_id}",
                             help="Удалить позицию"):
                    st.session_state.positions.pop(idx)
                    for k in list(st.session_state.keys()):
                        if k.endswith(f"_{_id}"):
                            del st.session_state[k]
                    st.rerun()

            # 👁 Скрыть/показать
            with row[1]:
                icon = "👁" if visible else "🚫"
                if st.button(icon, key=f"vis_{_id}",
                             help="Скрыть/показать в профиле"):
                    p["visible"] = not visible
                    st.rerun()

            # Опцион
            with row[2]:
                st.markdown(
                    f"<div style='padding-top:6px; {gray}'>"
                    f"{_color_call_put(p['Опцион'])}</div>",
                    unsafe_allow_html=True,
                )

            # Страйк
            with row[3]:
                _strike_txt = (f"<b>{int(p['Страйк'])}</b>"
                               if p.get("Страйк") is not None else "—")
                st.markdown(
                    f"<div style='padding-top:6px; {gray}'>"
                    f"{_strike_txt}</div>",
                    unsafe_allow_html=True,
                )

            # Тикер
            with row[4]:
                st.markdown(
                    f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                    f"{p.get('Тикер', '—')}</div>",
                    unsafe_allow_html=True,
                )

            # Количество — с кнопками − / +
            with row[5]:
                kq = f"qty_{_id}"
                if kq not in st.session_state:
                    st.session_state[kq] = int(p.get("Кол-во", 1))

                qcol1, qcol2, qcol3 = st.columns([1, 2, 1])
                with qcol1:
                    if st.button("−", key=f"qminus_{_id}",
                                 help="Уменьшить количество"):
                        st.session_state[kq] = int(st.session_state[kq]) - 1
                        p["Кол-во"] = int(st.session_state[kq])
                        p["Направление"] = _side_from_qty(int(st.session_state[kq]))
                        st.rerun()
                with qcol2:
                    new_qty = st.number_input(
                        "qty", min_value=-10000, max_value=10000,
                        value=int(st.session_state[kq]),
                        step=1, key=kq, label_visibility="collapsed",
                    )
                with qcol3:
                    if st.button("+", key=f"qplus_{_id}",
                                 help="Увеличить количество"):
                        st.session_state[kq] = int(st.session_state[kq]) + 1
                        p["Кол-во"] = int(st.session_state[kq])
                        p["Направление"] = _side_from_qty(int(st.session_state[kq]))
                        st.rerun()

                if new_qty != p.get("Кол-во"):
                    p["Кол-во"] = int(new_qty)
                    p["Направление"] = _side_from_qty(int(new_qty))

            # Цена — с кнопками − / + (шаг 0.01)
            with row[6]:
                kp = f"price_{_id}"
                if kp not in st.session_state:
                    st.session_state[kp] = float(p.get("Цена", 0.0))

                pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
                with pcol1:
                    if st.button("−", key=f"pminus_{_id}",
                                 help="Уменьшить цену на 0.01"):
                        st.session_state[kp] = round(
                            float(st.session_state[kp]) - 0.01, 4)
                        p["Цена"] = float(st.session_state[kp])
                        st.rerun()
                with pcol2:
                    new_price = st.number_input(
                        "price",
                        min_value=0.0,
                        value=float(st.session_state[kp]),
                        step=0.01, format="%.4f",
                        key=kp, label_visibility="collapsed",
                    )
                with pcol3:
                    if st.button("+", key=f"pplus_{_id}",
                                 help="Увеличить цену на 0.01"):
                        st.session_state[kp] = round(
                            float(st.session_state[kp]) + 0.01, 4)
                        p["Цена"] = float(st.session_state[kp])
                        st.rerun()

                if new_price != p.get("Цена"):
                    p["Цена"] = float(new_price)

            com = calc_commission(float(p.get("Цена", 0)), min_comm)
            eff_price = float(p.get("Цена", 0)) + com
            theor = float(p.get("Теор.цена", 0))
            qty = int(p.get("Кол-во", 0))
            if p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА":
                pnl = (theor - float(p.get("Цена", 0))) * qty
            else:
                pnl = (theor - eff_price) * qty

            with row[7]:
                st.markdown(
                    f"<div style='padding-top:6px; {gray}; "
                    f"font-size:.8rem;'>{com:.4f}</div>",
                    unsafe_allow_html=True,
                )
            with row[8]:
                st.markdown(
                    f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                    f"<b>{eff_price:.4f}</b></div>",
                    unsafe_allow_html=True,
                )
            with row[9]:
                st.markdown(
                    f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                    f"{theor:.4f}</div>",
                    unsafe_allow_html=True,
                )
            for ri, gr in zip([10, 11, 12, 13],
                              ["Дельта", "Гамма", "Вега", "Тета"]):
                val = p.get(gr)
                txt = f"{val:+.4f}" if isinstance(val, (int, float)) else "—"
                with row[ri]:
                    st.markdown(
                        f"<div style='padding-top:6px; {gray}; "
                        f"font-size:.78rem;'>{txt}</div>",
                        unsafe_allow_html=True,
                    )
            with row[14]:
                color = "#00a651" if pnl > 0 else ("#d32f2f" if pnl < 0 else "#333")
                st.markdown(
                    f"<div style='padding-top:6px; {gray}; font-weight:700; "
                    f"color:{color};'>{pnl:+,.2f} ₽</div>",
                    unsafe_allow_html=True,
                )

        # ---------- Итоги портфеля ----------
        st.markdown("### Итоги портфеля")

        total_com = 0.0
        total_pnl = 0.0
        total_delta = 0.0
        total_gamma = 0.0
        total_vega  = 0.0
        total_theta = 0.0
        total_rho   = 0.0

        for p in st.session_state.positions:
            qty = int(p.get("Кол-во", 0))
            price = float(p.get("Цена", 0))
            theor = float(p.get("Теор.цена", 0))
            com = calc_commission(price, min_comm)
            isBA = p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА"
            pnl = (theor - price) * qty if isBA else (theor - price - com) * qty
            total_com   += com * abs(qty)
            total_pnl   += pnl
            total_delta += (p.get("Дельта") or 0) * qty
            total_gamma += (p.get("Гамма")  or 0) * qty
            total_vega  += (p.get("Вега")   or 0) * qty
            total_theta += (p.get("Тета")   or 0) * qty
            total_rho   += (p.get("Ро")     or 0) * qty

        p1, p2 = st.columns(2)
        with p1:
            st.metric("P&L", f"{total_pnl:,.2f} ₽")
        with p2:
            st.metric("Комиссии", f"{total_com:,.4f} ₽")

        def _color_delta(d):
            d = abs(d)
            if 0.25 <= d <= 0.45:
                return "#00ff0c"
            if (0.15 <= d < 0.25) or (0.45 < d <= 0.55):
                return "#fcff00"
            return "#ff0000"

        def _color_gamma(g):
            g = abs(g)
            if g < 0.001:
                return "#00ff0c"
            if g < 0.005:
                return "#fcff00"
            return "#ff0000"

        def _color_vega(v):
            v = abs(v)
            if v < 20:
                return "#00ff0c"
            if v < 60:
                return "#fcff00"
            return "#ff0000"

        def _color_theta(theta, vega):
            if abs(vega) < 1e-9:
                return "#4a6f8a"
            ratio = abs(theta) / abs(vega)
            if ratio > 1.0:
                return "#00ff0c"
            if ratio > 0.5:
                return "#fcff00"
            return "#ff0000"

        def _greek_card(title, value, color):
            st.markdown(
                f"""
                <div style="background:#ffffff; border-radius:16px;
                            padding:14px 16px; border:1px solid #e2edf4;
                            height:100%;">
                    <div style="font-size:.72rem; font-weight:700;
                                color:#2c506d; text-transform:uppercase;
                                letter-spacing:.05em; margin-bottom:6px;">
                        {title}
                    </div>
                    <div style="font-size:1.6rem; font-weight:800;
                                color:{color};
                                text-shadow: 0 0 1px #000,
                                             1px 1px 0 rgba(0,0,0,0.45),
                                             -1px -1px 0 rgba(0,0,0,0.45);">
                        {value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        c_delta = _color_delta(total_delta)
        c_gamma = _color_gamma(total_gamma)
        c_vega  = _color_vega(total_vega)
        c_theta = _color_theta(total_theta, total_vega)

        g1, g2, g3, g4 = st.columns(4)
        with g1:
            _greek_card("Дельта (Σ)", f"{total_delta:+.3f}", c_delta)
        with g2:
            _greek_card("Гамма (Σ)", f"{total_gamma:+.4f}", c_gamma)
        with g3:
            _greek_card("Вега (Σ)", f"{total_vega:+.3f}", c_vega)
        with g4:
            _greek_card("Тета (Σ)", f"{total_theta:+.3f}", c_theta)

        # ---------- Проверка риска ----------
        max_loss = sum(calc_commission(p["Цена"], min_comm) * abs(p["Кол-во"])
                       + p["Цена"] * abs(p["Кол-во"])
                       for p in st.session_state.positions
                       if p.get("Опцион") != "БА")
        if max_loss > risk_amount:
            st.error(
                f"Превышен риск: потенциальный макс. убыток "
                f"**{max_loss:,.2f} ₽** > допустимых **{risk_amount:,.2f} ₽**"
            )
        else:
            st.success(
                f"Риск в пределах нормы: "
                f"{max_loss:,.2f} ₽ / {risk_amount:,.2f} ₽ "
                f"({max_loss / risk_amount * 100:.1f}% от допустимого)"
            )

        # ---------- Управление портфелем ----------
        st.markdown("#### Управление")
        d1, d2 = st.columns([1, 1])
        with d1:
            if st.button("Удалить последнюю позицию"):
                st.session_state.positions.pop()
                st.rerun()
        with d2:
            if st.button("Очистить весь портфель"):
                st.session_state.positions = []
                st.rerun()

        # Экспорт CSV
        _export_rows = []
        for i, p in enumerate(st.session_state.positions):
            qty = int(p["Кол-во"])
            price = float(p["Цена"])
            theor = float(p["Теор.цена"])
            com = calc_commission(price, min_comm)
            pnl = (theor - price) * qty if p.get("Опцион") == "БА" \
                  else (theor - price - com) * qty
            _export_rows.append({
                "#":           i + 1,
                "Конструкция": p.get("Конструкция", "Без названия"),
                "Тип":         p.get("Тип инструмента", "Опцион"),
                "Опцион":      p["Опцион"],
                "Направление": p.get("Направление", _side_from_qty(qty)),
                "Страйк":      p.get("Страйк", "—"),
                "Эксп.":       p.get("Эксп.", "—"),
                "Тикер":       p.get("Тикер", "—"),
                "Кол-во":      qty,
                "Цена":        price,
                "Комиссия":    com,
                "Эфф. цена":   price + com,
                "Теор.цена":   theor,
                "P&L":         pnl,
                "Дельта":      p.get("Дельта"),
                "Гамма":       p.get("Гамма"),
                "Вега":        p.get("Вега"),
                "Тета":        p.get("Тета"),
                "Ро":          p.get("Ро"),
            })
        df_export = pd.DataFrame(_export_rows)

        st.download_button(
            "Экспорт портфеля (CSV)",
            data=df_export.to_csv(index=False).encode("utf-8-sig"),
            file_name="portfolio.csv",
            mime="text/csv",
        )

        # =========================================================
        # СПРАВОЧНИК ОПЦИОННЫХ СТРАТЕГИЙ
        # =========================================================
        st.markdown("---")
        st.markdown("### Справочник опционных стратегий")

        try:
            _board_for_ref = fetch_optionboard(
                st.session_state.get("selected_asset", ""),
                st.session_state.get("selected_asset_type_ui", ""),
                st.session_state.get("selected_series_code", ""),
            )
            _all_strikes_for_ref = sorted({
                c['strike'] for c in (_board_for_ref.get('call') or [])
                if c.get('strike') is not None
            } | {
                p2['strike'] for p2 in (_board_for_ref.get('put') or [])
                if p2.get('strike') is not None
            })
            _central_for_ref = _board_for_ref.get('central_strike')
        except Exception:
            _board_for_ref = {'call': [], 'put': []}
            _all_strikes_for_ref = []
            _central_for_ref = None

        def _price_getter(option, K):
            src = _board_for_ref.get('call', []) if option == "Call" \
                  else _board_for_ref.get('put', [])
            row = next((x for x in src if x.get('strike') == K), None)
            if row is None:
                return None
            return float(row.get('theorprice') or 0) or \
                   float(row.get('last') or 0) or 0.0

        _suggestions = []
        for strat_name, strat_def in PREDEFINED_STRATEGIES.items():
            m = match_strategy_with_positions(strat_def,
                                              st.session_state.positions)
            if m["weight"] <= 0:
                continue
            _suggestions.append({
                "name": strat_name,
                "def": strat_def,
                "matched": m["matched"],
                "missing": m["missing"],
                "matched_strikes": m["matched_strikes_by_group"],
                "weight": m["weight"],
                "is_full": m["is_full"],
            })

        if not _suggestions:
            st.info("Из ваших позиций пока не собирается ни одна "
                    "стандартная конструкция.")
        else:
            categories = {}
            for s in _suggestions:
                cat = s["def"].get("category", "Прочие")
                categories.setdefault(cat, []).append(s)

            for cat in categories:
                categories[cat].sort(
                    key=lambda s: (-s["weight"], -int(s["is_full"]))
                )

            cat_order = [
                "Одиночные", "Вертикальные спреды", "Бабочки",
                "Кошка", "Кондоры", "Straddle / Strangle",
                "Ratio / Backspread", "Ladder",
                "Синтетика", "Strap / Strip", "Прочие",
            ]
            ordered_cats = [c for c in cat_order if c in categories] + \
                           [c for c in categories if c not in cat_order]

            for cat in ordered_cats:
                items = categories[cat]
                n_full = sum(1 for s in items if s["is_full"])
                with st.expander(
                    f"**{cat}** — {len(items)} стратегий "
                    f"({'в т.ч. готова ' + str(n_full) if n_full else 'ни одна не собрана'})",
                    expanded=(n_full > 0),
                ):
                    for s in items:
                        strat_name = s["name"]
                        strat_def = s["def"]
                        pct = int(100 * s["weight"])
                        full = s["is_full"]

                        header_color = "#00a651" if full else "#1e5a7a"
                        if full:
                            status = "Готова"
                            badge_bg = "#d4f7d8"
                            badge_color = "#0a5d29"
                        else:
                            status = f"{pct} %"
                            badge_bg = "#fff3cd"
                            badge_color = "#8a5a00"

                        card_border = (
                            _card_style_full() if full
                            else _card_style_partial()
                        )

                        st.markdown(
                            f"""
                            <div style="{card_border}
                                        border-radius:14px;
                                        padding:12px 16px;
                                        margin-bottom:10px;
                                        background:#ffffff;">
                              <div style="display:flex;
                                          justify-content:space-between;
                                          align-items:center;
                                          margin-bottom:6px;">
                                <div style="font-size:1.05rem;
                                            font-weight:700;
                                            color:{header_color};">
                                  {strat_name}
                                </div>
                                <div style="background:{badge_bg};
                                            color:{badge_color};
                                            border-radius:20px;
                                            padding:3px 12px;
                                            font-size:.78rem;
                                            font-weight:700;">
                                  {status}
                                </div>
                              </div>
                              <div style="font-size:.85rem;
                                          color:#4a6f8a;
                                          margin-bottom:8px;">
                                {strat_def['description']}
                              </div>
                              <div style="background:#f9fbfd;
                                          border-radius:10px;
                                          padding:8px 12px;
                                          font-size:.82rem;
                                          line-height:1.6;">
                            """,
                            unsafe_allow_html=True,
                        )

                        for li, leg in enumerate(strat_def["legs"]):
                            m_info = s["matched"].get(li)
                            if m_info:
                                pos = st.session_state.positions[
                                    m_info["pos_index"]
                                ]
                                strike_txt = f"страйк {int(pos['Страйк'])}" \
                                             if pos.get("Страйк") is not None \
                                             else "БА"
                                qty_txt = (f"{m_info['qty_covered']} / "
                                           f"{m_info['qty_required']}")
                                if m_info["full"]:
                                    icon = "✓"
                                    icon_color = "#00a651"
                                else:
                                    icon = "◐"
                                    icon_color = "#b8860b"
                            else:
                                strike_txt = "нужно добавить"
                                qty_txt = f"× {leg['qty']}"
                                icon = "○"
                                icon_color = "#b8860b"

                            st.markdown(
                                f"<div style='margin-left:6px;'>"
                                f"<span style='color:{icon_color}; "
                                f"font-weight:700;'>{icon}</span> "
                                f"{_color_side(leg['side'])} "
                                f"{_color_call_put(leg['option'])} "
                                f"<span style='color:#4a6f8a;'>"
                                f"{strike_txt} "
                                f"<b>{qty_txt}</b></span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                        st.markdown("</div></div>", unsafe_allow_html=True)

                        # Кнопка «Дописать недостающие ноги»
                        if not full:
                            matched_strikes = s["matched_strikes"]
                            strike_order = strat_def.get("strike_order", [])

                            all_groups = []
                            for leg in strat_def["legs"]:
                                g = leg["strike_group"]
                                if g not in all_groups:
                                    all_groups.append(g)

                            strike_choices = {}
                            for g in all_groups:
                                if g in matched_strikes:
                                    strike_choices[g] = matched_strikes[g]
                                else:
                                    strike_choices[g] = suggest_strike_for_group(
                                        g, strat_def, matched_strikes,
                                        strike_order,
                                        _all_strikes_for_ref,
                                        _central_for_ref,
                                    )

                            debit = compute_strategy_debit_credit(
                                strat_def, strike_choices, _price_getter
                            )

                            with st.expander(
                                "Показать/изменить план добавления ног",
                                expanded=False,
                            ):
                                if debit is not None:
                                    if debit >= 0:
                                        st.markdown(
                                            f"<div style='font-size:.85rem; "
                                            f"color:#d32f2f; background:#fdecec; "
                                            f"border-radius:10px; padding:6px 12px; "
                                            f"margin-bottom:8px;'>"
                                            f"<b>Дебет конструкции:</b> "
                                            f"{debit:+,.4f} ₽ за 1 комплект"
                                            f"</div>",
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        st.markdown(
                                            f"<div style='font-size:.85rem; "
                                            f"color:#0a5d29; background:#d4f7d8; "
                                            f"border-radius:10px; padding:6px 12px; "
                                            f"margin-bottom:8px;'>"
                                            f"<b>Кредит конструкции:</b> "
                                            f"{abs(debit):,.4f} ₽ за 1 комплект"
                                            f"</div>",
                                            unsafe_allow_html=True,
                                        )

                                groups_with_missing = []
                                for li in s["missing"]:
                                    g = strat_def["legs"][li]["strike_group"]
                                    if g not in groups_with_missing:
                                        groups_with_missing.append(g)

                                cols_g = st.columns(len(groups_with_missing))
                                for gi, grp in enumerate(groups_with_missing):
                                    with cols_g[gi]:
                                        current = strike_choices.get(grp)
                                        default_idx = 0
                                        if current is not None and _all_strikes_for_ref:
                                            try:
                                                default_idx = _all_strikes_for_ref.index(
                                                    min(_all_strikes_for_ref,
                                                        key=lambda k: abs(float(k) - float(current)))
                                                )
                                            except ValueError:
                                                default_idx = 0
                                        strike_choices[grp] = st.selectbox(
                                            f"Страйк «{grp}»",
                                            _all_strikes_for_ref or ["—"],
                                            index=default_idx,
                                            key=f"ref_grp_{strat_name}_{grp}",
                                        )

                                order_ok, order_msg = validate_strike_order(
                                    strat_def, strike_choices
                                )
                                if not order_ok:
                                    st.error(f"⚠ {order_msg}")

                                price_choices = {}
                                for li in s["missing"]:
                                    leg = strat_def["legs"][li]
                                    grp = leg["strike_group"]
                                    K = strike_choices[grp]
                                    default_p = _price_getter(leg["option"], K) or 0.0
                                    price_choices[li] = st.number_input(
                                        f"{leg['side']} {leg['option']} "
                                        f"{K} — цена, ₽",
                                        min_value=0.0,
                                        value=float(default_p),
                                        step=0.01, format="%.4f",
                                        key=f"ref_price_{strat_name}_{li}",
                                    )

                                _auto_name = strat_name
                                _final_name = st.text_input(
                                    "Имя конструкции",
                                    value=_auto_name,
                                    key=f"ref_name_{strat_name}",
                                ).strip() or _auto_name

                                if order_ok:
                                    if st.button(
                                        f"Дописать {len(s['missing'])} ног(у) "
                                        f"в «{_final_name}»",
                                        key=f"ref_add_{strat_name}",
                                        type="primary",
                                    ):
                                        added = 0
                                        for li in s["missing"]:
                                            leg = strat_def["legs"][li]
                                            grp = leg["strike_group"]
                                            K = strike_choices[grp]
                                            price = price_choices[li]
                                            if price <= 0 or K in (None, "—"):
                                                continue
                                            src = _board_for_ref.get('call', []) \
                                                  if leg["option"] == "Call" \
                                                  else _board_for_ref.get('put', [])
                                            ref_row = next(
                                                (x for x in src
                                                 if x.get('strike') == K),
                                                {}
                                            )
                                            signed_qty = leg["qty"] \
                                                         if leg["side"] == "Buy" \
                                                         else -leg["qty"]
                                            st.session_state.positions.append({
                                                "_id": _new_position_id(),
                                                "Конструкция": _final_name,
                                                "Тип инструмента": "Опцион",
                                                "Опцион": leg["option"],
                                                "Направление": leg["side"],
                                                "Страйк": K,
                                                "Эксп.": st.session_state.get(
                                                    "selected_expiry", "—"
                                                ),
                                                "Тикер": ref_row.get('secid', '—'),
                                                "Кол-во": int(signed_qty),
                                                "Цена": float(price),
                                                "Теор.цена": float(
                                                    ref_row.get('theorprice') or 0
                                                ),
                                                "Дельта": ref_row.get('delta'),
                                                "Гамма":  ref_row.get('gamma'),
                                                "Вега":   ref_row.get('vega'),
                                                "Тета":   ref_row.get('theta'),
                                                "Ро":     ref_row.get('rho'),
                                                "visible": True,
                                            })
                                            added += 1
                                        if added:
                                            st.success(
                                                f"Добавлено {added} ног "
                                                f"в «{_final_name}»"
                                            )
                                            st.rerun()
                                        else:
                                            st.error(
                                                "Укажите цены > 0 для всех ног."
                                            )
                                else:
                                    st.button(
                                        "Исправьте порядок страйков",
                                        disabled=True,
                                        key=f"ref_add_dis_{strat_name}",
                                    )

        # =========================================================
        # ГРАФИК ПРОФИЛЯ ПОЗИЦИИ (Payoff)
        # =========================================================
        st.markdown("---")
        st.markdown("### График профиля позиции")

        payoff_scope = st.selectbox(
            "Что показать",
            ["Все конструкции"] + _existing_constructions,
            key="payoff_scope",
        )

        if payoff_scope == "Все конструкции":
            payoff_positions = [p for p in st.session_state.positions
                                if p.get("visible", True)]
        else:
            payoff_positions = [
                p for p in st.session_state.positions
                if p.get("Конструкция", "Без названия") == payoff_scope
                and p.get("visible", True)
            ]

        all_pos_strikes = sorted({
            float(p["Страйк"]) for p in payoff_positions
            if p.get("Страйк") is not None
        })

        if not all_pos_strikes:
            _ba_prices = [
                float(p["Цена"]) for p in payoff_positions
                if p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА"
            ]
            if _ba_prices:
                all_pos_strikes = _ba_prices

        if not all_pos_strikes:
            st.caption("Нет данных для построения графика профиля.")
        else:
            s_min = min(all_pos_strikes) * 0.85
            s_max = max(all_pos_strikes) * 1.15
            S_arr = np.linspace(s_min, s_max, 500)

            def _payoff_at_expiry(S_vals, positions_subset):
                S_vals = np.asarray(S_vals, dtype=float)
                pnl_arr = np.zeros_like(S_vals)
                for p in positions_subset:
                    qty = int(p["Кол-во"])
                    price = float(p["Цена"])
                    com = calc_commission(price, min_comm)

                    if p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА":
                        pnl_arr += (S_vals - price) * qty
                        continue

                    K = float(p["Страйк"])
                    if p["Опцион"] == "Call":
                        intrinsic = np.maximum(0.0, S_vals - K)
                    else:
                        intrinsic = np.maximum(0.0, K - S_vals)
                    pnl_arr += (intrinsic - price - com) * qty
                return pnl_arr

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
                    qty = int(p["Кол-во"])
                    entry = float(p["Цена"])
                    com = calc_commission(entry, min_comm)

                    if p.get("Тип инструмента") == "БА" or p.get("Опцион") == "БА":
                        pnl_arr += (S_vals - entry) * qty
                        continue

                    K = float(p["Страйк"])
                    opt_type = "call" if p["Опцион"] == "Call" else "put"

                    price_now = np.array([
                        black_scholes_py(S, K, T_years, _r, _vol, _q, opt_type)
                        for S in S_vals
                    ])
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
                        x0 = (S_arr[i - 1]
                              + (S_arr[i] - S_arr[i - 1])
                              * (-pnl_arr[i - 1]) / denom)
                        be_points.append(float(x0))

            # Current price БА — 3 источника
            F_current = None
            try:
                _secid_und = resolve_underlying_secid(
                    st.session_state.get("selected_asset", ""),
                    st.session_state.get("selected_asset_type_ui", ""),
                )
                _info_last = fetch_last_price_from_iss(
                    _secid_und,
                    st.session_state.get("selected_asset_type_ui", ""),
                )
                if _info_last and _info_last.get("last"):
                    F_current = float(_info_last["last"])
            except Exception:
                pass

            if F_current is None:
                try:
                    board_pf = fetch_optionboard(
                        st.session_state.get("selected_asset", ""),
                        st.session_state.get("selected_asset_type_ui", ""),
                        st.session_state.get("selected_series_code", ""),
                    )
                    c_map_p = {
                        c['strike']: c
                        for c in (board_pf.get('call') or [])
                        if c.get('theorprice') and c.get('strike') is not None
                    }
                    p_map_p = {
                        p2['strike']: p2
                        for p2 in (board_pf.get('put') or [])
                        if p2.get('theorprice') and p2.get('strike') is not None
                    }
                    common_p = sorted(set(c_map_p.keys()) & set(p_map_p.keys()))
                    fs_est = []
                    for k in common_p:
                        ct = c_map_p[k]['theorprice']
                        pt = p_map_p[k]['theorprice']
                        if ct and pt and ct > 0 and pt > 0:
                            fs_est.append(ct - pt + float(k))
                    if fs_est:
                        fs_est.sort()
                        F_current = fs_est[len(fs_est) // 2]
                except Exception:
                    pass

            if F_current is None:
                try:
                    _board_c = fetch_optionboard(
                        st.session_state.get("selected_asset", ""),
                        st.session_state.get("selected_asset_type_ui", ""),
                        st.session_state.get("selected_series_code", ""),
                    )
                    _cs = _board_c.get("central_strike")
                    if _cs:
                        F_current = float(_cs)
                except Exception:
                    pass

            # График
            fig_pf = go.Figure()

            fig_pf.add_trace(go.Scatter(
                x=S_arr,
                y=np.where(pnl_arr >= 0, pnl_arr, 0),
                fill='tozeroy',
                fillcolor='rgba(0,255,12,0.20)',
                line=dict(width=0),
                mode='lines',
                name='Прибыль (эксп.)',
                hoverinfo='skip',
            ))
            fig_pf.add_trace(go.Scatter(
                x=S_arr,
                y=np.where(pnl_arr <= 0, pnl_arr, 0),
                fill='tozeroy',
                fillcolor='rgba(255,0,0,0.20)',
                line=dict(width=0),
                mode='lines',
                name='Убыток (эксп.)',
                hoverinfo='skip',
            ))

            fig_pf.add_trace(go.Scatter(
                x=S_arr,
                y=pnl_arr,
                mode='lines',
                line=dict(color='#1e5a7a', width=3),
                name='P&L на экспирации',
                hovertemplate='БА: %{x:.2f} ₽<br>P&L: %{y:.2f} ₽<extra></extra>',
            ))

            # Линия P&L на текущую дату
            try:
                _exp_date_pt = datetime.strptime(
                    st.session_state.get("selected_expiry", ""),
                    "%Y-%m-%d"
                ).date()
                _T_now = max((_exp_date_pt - date.today()).days, 1) / 365.0
                pnl_today = _payoff_today(S_arr, payoff_positions, _T_now)
                fig_pf.add_trace(go.Scatter(
                    x=S_arr,
                    y=pnl_today,
                    mode='lines',
                    line=dict(color='#1e88e5', width=2, dash='dash'),
                    name='P&L на текущую дату',
                    hovertemplate='БА: %{x:.2f} ₽<br>P&L сегодня: %{y:.2f} ₽<extra></extra>',
                ))
            except Exception:
                pass

            fig_pf.add_hline(y=0, line_dash='dot',
                             line_color='#7f9bb3', line_width=1)

            for k in all_pos_strikes:
                fig_pf.add_vline(
                    x=k,
                    line_dash='dash',
                    line_color='#9c00ff',
                    line_width=1,
                    opacity=0.5,
                    annotation_text=f"{k:.0f}",
                    annotation_position="top",
                    annotation_font_size=10,
                )

            if F_current is not None:
                fig_pf.add_vline(
                    x=F_current,
                    line_dash='dot',
                    line_color='#1e88e5',
                    line_width=2,
                    annotation_text=f"Тек. {F_current:.0f}",
                    annotation_position="bottom right",
                    annotation_font_size=11,
                )

            for be in be_points:
                fig_pf.add_vline(
                    x=be,
                    line_dash='dot',
                    line_color='#00a651',
                    line_width=1.5,
                    opacity=0.8,
                )

            fig_pf.update_layout(
                title=f"Профиль позиции: {payoff_scope}",
                xaxis_title="Цена базового актива, ₽",
                yaxis_title="Прибыль / Убыток, ₽",
                height=500,
                margin=dict(l=20, r=20, t=60, b=20),
                xaxis=dict(tickformat=".0f", hoverformat=".2f"),
                yaxis=dict(tickformat=".2f", hoverformat=".2f"),
                legend=dict(orientation="h", yanchor="bottom",
                            y=1.02, xanchor="left", x=0),
                hovermode='x unified',
            )
            st.plotly_chart(fig_pf, use_container_width=True)

            pm1, pm2 = st.columns(2)
            with pm1:
                st.metric("Макс. прибыль (в диапазоне)", f"{max_profit:+,.2f} ₽")
            with pm2:
                st.metric("Макс. убыток (в диапазоне)", f"{max_loss_pf:+,.2f} ₽")

            if be_points:
                be_str = " · ".join(f"**{be:,.2f} ₽**" for be in be_points)
                st.caption(f"Точки безубыточности: {be_str}")
            else:
                st.caption("Точки безубыточности в выбранном диапазоне не найдены.")


# ==================================================================
# ============ ВКЛАДКА 3: ДОСКА ОПЦИОНОВ ===========================
# ==================================================================
with tab_board:
    if not st.session_state.get("series_list"):
        st.info("Сначала выберите опционную серию на вкладке «Калькулятор».")
    elif "selected_series_code" not in st.session_state:
        st.info("Выберите конкретную дату экспирации на вкладке «Калькулятор».")
    else:
        asset = st.session_state.get("selected_asset", "")
        asset_type_ui = st.session_state.get("selected_asset_type_ui", "")
        series_code = st.session_state.get("selected_series_code", "")
        expiry_str = st.session_state.get("selected_expiry", "")

        try:
            buy_level = float(st.session_state.get("_calc_level_buy", 0) or 0)
        except (TypeError, ValueError):
            buy_level = 0.0
        try:
            sell_level = float(st.session_state.get("_calc_level_sell", 0) or 0)
        except (TypeError, ValueError):
            sell_level = 0.0

        st.markdown(f"### Доска опционов — **{asset}** "
                    f"(серия `{series_code}`, экспирация {expiry_str})")

        # Информационная строка: текущая цена БА + центральный страйк + диапазон
        try:
            _board_for_price = fetch_optionboard(asset, asset_type_ui, series_code)
            _calls_p = _board_for_price.get('call') or []
            _puts_p  = _board_for_price.get('put') or []

            _c_map_p = {
                c['strike']: c for c in _calls_p
                if c.get('theorprice') and c.get('strike') is not None
            }
            _p_map_p = {
                p2['strike']: p2 for p2 in _puts_p
                if p2.get('theorprice') and p2.get('strike') is not None
            }
            _common_p = sorted(set(_c_map_p.keys()) & set(_p_map_p.keys()))
            _fs_est = []
            for k in _common_p:
                ct = _c_map_p[k]['theorprice']
                pt = _p_map_p[k]['theorprice']
                if ct and pt and ct > 0 and pt > 0:
                    _fs_est.append(ct - pt + float(k))
            if _fs_est:
                _fs_est.sort()
                _f_current = _fs_est[len(_fs_est) // 2]
            else:
                _f_current = None

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
                    f"Текущая цена БА: {_f_current:,.2f} ₽</span>"
                )
            if _central_p is not None:
                _info_parts.append(
                    f"<span style='color:#4a6f8a;'>"
                    f"Центральный страйк: <b>{int(_central_p)}</b></span>"
                )
            if _k_min is not None and _k_max is not None:
                _info_parts.append(
                    f"<span style='color:#4a6f8a;'>"
                    f"Диапазон страйков: <b>{int(_k_min)} … {int(_k_max)}</b> "
                    f"({len(_strikes_p)} шт.)</span>"
                )
            if _info_parts:
                st.markdown(
                    "<div style='background:#eef6fb; border-radius:12px; "
                    "padding:10px 16px; margin-bottom:12px; "
                    "font-size:.9rem; display:flex; gap:24px; "
                    "flex-wrap:wrap; align-items:center;'>"
                    + " · ".join(_info_parts)
                    + "</div>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

        col_t1, col_t2 = st.columns([3, 2])
        with col_t1:
            highlight_on = st.toggle(
                "Раскрасить ячейки по грекам и ликвидности",
                value=False,
            )
        with col_t2:
            if highlight_on:
                st.markdown(
                    "<div style='font-size:.78rem; color:#4a6f8a; "
                    "padding-top:.4rem;'>"
                    "Зелёный — норма · Жёлтый — пограничное · Красный — "
                    "не по стратегии</div>",
                    unsafe_allow_html=True,
                )

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

            def nearest_strike(level, strikes_list):
                if level is None or level <= 0 or not strikes_list:
                    return None
                return min(strikes_list, key=lambda s: abs(float(s) - float(level)))

            buy_strike_match = nearest_strike(buy_level, strikes)
            sell_strike_match = nearest_strike(sell_level, strikes)

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
                if not isinstance(theta, (int, float)) or not isinstance(vega, (int, float)):
                    return None
                if abs(vega) < 1e-9:
                    return None
                ratio = abs(theta) / abs(vega)
                if ratio > 1.0:
                    return "#00ff0c"
                if ratio > 0.5:
                    return "#fcff00"
                return "#ff0000"

            def _liquidity_color(bid, ask, theor):
                if bid is None or ask is None or theor is None:
                    return None
                if not all(isinstance(x, (int, float)) for x in (bid, ask, theor)):
                    return None
                if bid <= 0 or ask <= 0 or theor <= 0:
                    return None
                spread_pct = (ask - bid) / theor * 100
                if spread_pct < 5:
                    return "#00ff0c"
                if spread_pct < 15:
                    return "#fcff00"
                return "#ff0000"

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
                            style = ("background-color: #fb92f0; "
                                     "color: white; font-weight: bold")
                        elif is_buy_strike:
                            style = ("background-color: #9c00ff; "
                                     "color: white; font-weight: bold")
                        elif is_central:
                            style = "background-color: #e3e7ec; font-weight: bold"
                    elif col == "IV_%" and is_central:
                        style = "background-color: #e3e7ec; font-weight: bold"

                    if highlight_on:
                        if col in ("Call_Delta", "Put_Delta"):
                            c = _delta_color(row[col])
                            if c:
                                style = f"background-color: {c}; font-weight: 600"
                        elif col in ("Call_Theta", "Put_Theta"):
                            vega_col = "Call_Vega" if col.startswith("Call_") else "Put_Vega"
                            c = _theta_color(row[col], row.get(vega_col))
                            if c:
                                style = f"background-color: {c}; font-weight: 600"
                        elif col in ("Call_Bid", "Call_Offer",
                                     "Put_Bid", "Put_Offer"):
                            if col.startswith("Call_"):
                                theor_col = "Call_Theor"
                            else:
                                theor_col = "Put_Theor"
                            if col.endswith("_Bid"):
                                pair_col = col.replace("_Bid", "_Offer")
                            else:
                                pair_col = col.replace("_Offer", "_Bid")
                            c = _liquidity_color(row[col], row.get(pair_col),
                                                 row.get(theor_col))
                            if c:
                                style = f"background-color: {c}"

                    styles.append(style)
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

            caption_extra = ""
            if buy_strike_match is not None:
                caption_extra += (f" · страйк покупок ≈ **{buy_strike_match}** "
                                  f"(уровень {buy_level})")
            if sell_strike_match is not None:
                caption_extra += (f" · страйк продаж ≈ **{sell_strike_match}** "
                                  f"(уровень {sell_level})")
            st.caption(f"Центральный страйк: "
                       f"**{central if central is not None else 'не определён'}** · "
                       f"всего страйков: {len(df)}{caption_extra}")

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

            # Улыбка волатильности
            st.markdown("### Улыбка волатильности")
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
                st.info("Данные для улыбки волатильности недоступны.")


# ==================================================================
# ============ ВКЛАДКА 4: ОПОВЕЩЕНИЯ ===============================
# ==================================================================
with tab_alerts:
    st.header("Оповещения по уровням")

    st.markdown(
        "Загрузите Excel-файл с уровнями. Ожидаемые колонки: "
        "**Тикер БА · Категория БА · Уровень покупок · Уровень продаж**. "
        "Сравнение идёт с последней рыночной ценой (LAST) с MOEX ISS."
    )

    uploaded = st.file_uploader(
        "Excel-файл (.xlsx)",
        type=["xlsx", "xls"],
        key="alerts_xlsx_uploader",
    )

    if "alerts_df" not in st.session_state:
        st.session_state.alerts_df = None

    if uploaded is not None:
        try:
            _xls = pd.read_excel(uploaded)
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

            required = ["Тикер БА", "Категория БА",
                        "Уровень покупок", "Уровень продаж"]
            missing = [c for c in required if c not in _xls.columns]
            if missing:
                st.error(f"В файле нет колонок: {', '.join(missing)}")
            else:
                _xls["Уровень покупок"] = pd.to_numeric(
                    _xls["Уровень покупок"], errors="coerce")
                _xls["Уровень продаж"] = pd.to_numeric(
                    _xls["Уровень продаж"], errors="coerce")
                _xls = _xls.dropna(subset=["Тикер БА", "Уровень покупок",
                                           "Уровень продаж"])
                st.session_state.alerts_df = _xls
                st.success(f"Загружено {len(_xls)} строк.")
        except Exception as e:
            st.error(f"Не удалось прочитать файл: {e}")

    if st.session_state.alerts_df is not None:
        if st.button("Очистить таблицу оповещений"):
            st.session_state.alerts_df = None
            st.rerun()

    if st.session_state.alerts_df is None:
        st.info("Загрузите Excel-файл, чтобы увидеть оповещения.")
    else:
        df_alerts = st.session_state.alerts_df.copy()

        if "alerts_price_cache" not in st.session_state:
            st.session_state.alerts_price_cache = {}

        def _get_price_for_alert(ticker, category):
            key = (ticker.upper(), category)
            cache = st.session_state.alerts_price_cache
            if key in cache:
                return cache[key]
            secid = resolve_underlying_secid(ticker.upper(), category)
            info = fetch_last_price_from_iss(secid, category)
            cache[key] = info
            return info

        out_rows = []
        for _, row in df_alerts.iterrows():
            ticker = str(row["Тикер БА"]).strip()
            category = str(row["Категория БА"]).strip()
            lvl_buy = float(row["Уровень покупок"])
            lvl_sell = float(row["Уровень продаж"])

            info = _get_price_for_alert(ticker, category)
            last = info.get("last") if info else None

            if last and last > 0:
                buy_dev_pct = (lvl_buy - last) / last * 100.0
                sell_dev_pct = (lvl_sell - last) / last * 100.0
                buy_active = lvl_buy <= last
                sell_active = lvl_sell >= last
            else:
                buy_dev_pct = None
                sell_dev_pct = None
                buy_active = False
                sell_active = False

            out_rows.append({
                "Тикер БА": ticker,
                "Категория БА": category,
                "Уровень покупок": lvl_buy,
                "Откл. покупок, %": buy_dev_pct,
                "Уровень продаж": lvl_sell,
                "Откл. продаж, %": sell_dev_pct,
                "Рыночная цена": last,
                "Покупка активна": buy_active,
                "Продажа активна": sell_active,
            })

        df_out = pd.DataFrame(out_rows)

        def _style_alert_row(row):
            styles = []
            for col in row.index:
                style = ""
                if col == "Покупка активна" and row[col]:
                    style = ("background-color:#00ff0c; "
                             "color:#0a3d0e; font-weight:700;")
                elif col == "Продажа активна" and row[col]:
                    style = ("background-color:#00ff0c; "
                             "color:#0a3d0e; font-weight:700;")
                elif col == "Откл. покупок, %" and row[col] is not None:
                    if row[col] <= 0:
                        style = "color:#00a651; font-weight:700;"
                    else:
                        style = "color:#d32f2f;"
                elif col == "Откл. продаж, %" and row[col] is not None:
                    if row[col] >= 0:
                        style = "color:#00a651; font-weight:700;"
                    else:
                        style = "color:#d32f2f;"
                styles.append(style)
            return styles

        st.dataframe(
            df_out.style
                 .apply(_style_alert_row, axis=1)
                 .format({
                     "Уровень покупок":   "{:,.2f}",
                     "Уровень продаж":    "{:,.2f}",
                     "Откл. покупок, %":  "{:+.2f} %",
                     "Откл. продаж, %":   "{:+.2f} %",
                     "Рыночная цена":     "{:,.2f}",
                     "Покупка активна":   lambda v: "АКТИВНО" if v else "—",
                     "Продажа активна":   lambda v: "АКТИВНО" if v else "—",
                 }, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )

        n_buy = int(df_out["Покупка активна"].sum())
        n_sell = int(df_out["Продажа активна"].sum())
        n_total = len(df_out)

        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("Всего тикеров", n_total)
        with s2:
            st.metric("Покупка активна", n_buy)
        with s3:
            st.metric("Продажа активна", n_sell)

        if st.button("Обновить рыночные цены", type="primary"):
            st.session_state.alerts_price_cache = {}
            st.rerun()

        st.download_button(
            "Экспорт таблицы оповещений (CSV)",
            data=df_out.to_csv(index=False).encode("utf-8-sig"),
            file_name="alerts.csv",
            mime="text/csv",
        )
