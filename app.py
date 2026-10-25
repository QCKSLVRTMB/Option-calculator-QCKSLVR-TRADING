import streamlit as st
import os

# Определяем, запущены ли мы на Streamlit Cloud
_IS_CLOUD = os.path.exists("/mount/src") or os.path.exists("/app")

LAZY_TABS = True
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

# [PATCH 7] Удалён блок очистки кэша для каждой новой сессии —
# st.cache_data разделяется между сессиями, и новый пользователь
# не должен чистить кэш остальным.
# Было:
#   if "cache_cleared_v7" not in st.session_state:
#       st.cache_data.clear()
#       st.session_state["cache_cleared_v7"] = True
# Стало: блок полностью удалён.

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
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: sticky !important;
    top: 0 !important;
    z-index: 999 !important;
    background-color: #ffffff !important;
    border-bottom: 1px solid #e6edf4 !important;
    padding-top: 6px !important;
    padding-bottom: 4px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button {
    background-color: transparent !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button,
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button p,
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button div,
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button span {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    letter-spacing: .01em !important;
    line-height: 1.2 !important;
    padding-top: 6px !important;
    padding-bottom: 6px !important;
}
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    gap: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# [PATCH 5] Адаптивный CSS для остальных вкладок (не затрагивает доску)
st.markdown("""
<style>
/* Изменения ограничены контентом вне доски опционов.
   Цвета текста и акцентные цвета не переопределяются. */

.st-key-responsive_content [data-testid="stForm"] {
    border-radius: 8px !important;
}

.st-key-responsive_content [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 8px !important;
}

.st-key-responsive_content [data-testid="stButton"] button,
.st-key-responsive_content [data-testid="stDownloadButton"] button {
    border-radius: 6px !important;
}

.st-key-responsive_content input,
.st-key-responsive_content textarea {
    font-variant-numeric: tabular-nums;
}

@media (max-width: 760px) {
    .st-key-responsive_content [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.75rem !important;
    }

    .st-key-responsive_content [data-testid="stColumn"] {
        flex: 1 1 16rem !important;
        width: auto !important;
        min-width: 0 !important;
    }

    .st-key-responsive_content [data-testid="stForm"] {
        padding: 10px !important;
    }

    .st-key-responsive_content input,
    .st-key-responsive_content textarea,
    .st-key-responsive_content [data-baseweb="select"] input {
        font-size: 16px !important;
    }

    .st-key-responsive_content [data-testid="stButton"] button,
    .st-key-responsive_content [data-testid="stDownloadButton"] button,
    .st-key-responsive_content [data-testid="stPopover"] button {
        min-height: 44px !important;
    }

    .st-key-responsive_content [data-testid="stRadio"] [role="radiogroup"] {
        flex-wrap: wrap !important;
        row-gap: 8px !important;
    }

    .st-key-responsive_content [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
    }

    .st-key-responsive_content h2 {
        font-size: 1.35rem !important;
    }

    .st-key-responsive_content h3 {
        font-size: 1.12rem !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ================= MOEX API =================
API_BASE_URL = "https://iss.moex.com/iss/apps/option-calc/v1"

ASSET_TYPE_MAP = {
    'Фьючерс': 'futures', 'Акция': 'share', 'Валюта': 'currency',
    'Товар': 'commodity', 'Индекс': 'index',
}

# ================= Комиссии =================
DEFAULT_COMM_OPTIONS_PCT = 3.0
DEFAULT_COMM_OPTIONS_MIN = 0.02
DEFAULT_COMM_FUTURES_PCT = 0.1
DEFAULT_COMM_STOCKS_PCT  = 0.3
DEFAULT_COMM_METALS_PCT  = 1.9
DEFAULT_COMM_CURRENCY_PCT = 0.9
DEFAULT_COMM_MIN_OTHER   = 0.01

# ================= Чек-лист и настройки =================
CHECKLIST_RULES = {
    "min_business_days_to_expiry": 20,
    "min_qty": 2,
    "volume_spike_multiplier": 2.0,
    "volume_prev_days": 2,
    "fat_strike_min_points_monthly": 1000,
    "right_leg_min_profit_pct": 5.0,
    "right_leg_max_profit_pct": 10.0,
    "level_proximity_pct": 2.0,
    "skew_threshold_pct": 15.0,
    "touch_tolerance_pct": 0.1,
    "close_weekly_days_threshold": 10,
    "close_weekly_days_before": 1,
    "close_monthly_days_before": 2,
    "cache_volume_ttl_sec": 180,
    "cache_board_ttl_sec": 120,
    "cache_rvi_ttl_sec": 60,
    "cache_last_price_ttl_sec": 10,
    "cache_g_curve_ttl_sec": 600,
}

HTML_PLACEHOLDER = "/*__INJECT_PLACEHOLDER__*/{}"

ALERTS_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRKISFld2M8tFEEE1o1Fo5nQgHP6qMmOFu57JDmi-t-Y4Xj67N5SQP9uQ02JW2Ixyd663zewMYY1hfx"
    "/pub?output=xlsx"
)

# ================= Справочник инструментов MOEX =================
# (полностью без изменений — вставьте существующий словарь MOEX_INSTRUMENTS)
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
        "GAZP": ("Акция", "Газпром"), "SBER": ("Акция", "Сбербанк о.с."),
        "SBERP": ("Акция", "Сбербанк п.с."), "LKOH": ("Акция", "ЛУКОЙЛ"),
        "ROSN": ("Акция", "Роснефть"), "NOTK": ("Акция", "НОВАТЭК"),
        "TATN": ("Акция", "Татнефть о.с."), "TATNP": ("Акция", "Татнефть п.с."),
        "SNGSP": ("Акция", "Сургутнефтегаз п.с."), "MTSS": ("Акция", "МТС"),
        "MGNT": ("Акция", "Магнит"), "GMKN": ("Акция", "Норникель"),
        "NLMK": ("Акция", "НЛМК"), "CHMF": ("Акция", "Северсталь"),
        "ALRS": ("Акция", "АЛРОСА"), "VTBR": ("Акция", "ВТБ"),
        "MOEX": ("Акция", "Московская Биржа"), "AFKS": ("Акция", "АФК Система"),
        "IRAO": ("Акция", "Интер РАО"), "HYDR": ("Акция", "РусГидро"),
        "RTKM": ("Акция", "Ростелеком"), "PLZL": ("Акция", "Полюс"),
        "MAGN": ("Акция", "ММК"), "YDEX": ("Акция", "Яндекс"),
        "PHOR": ("Акция", "ФосАгро"), "RUAL": ("Акция", "РУСАЛ"),
        "FEES": ("Акция", "ФСК ЕЭС"), "TRNFP": ("Акция", "Транснефть п.с."),
        "AFLT": ("Акция", "Аэрофлот"), "SIBN": ("Акция", "Газпром нефть"),
        "PIKK": ("Акция", "ПИК"), "FLOT": ("Акция", "Совкомфлот"),
        "CBOM": ("Акция", "МКБ"), "SGZH": ("Акция", "Сегежа"),
        "BSPB": ("Акция", "Банк Санкт-Петербург"), "KMAZ": ("Акция", "КАМАЗ"),
        "ASTR": ("Акция", "Группа Астра"), "SVCB": ("Акция", "Совкомбанк"),
    },
    # ... (остальные категории MOEX_INSTRUMENTS без изменений) ...
}
# (Полные словари MOEX_INSTRUMENTS, TV_TICKER_MAP, PREDEFINED_STRATEGIES
#  остаются как в исходном app.py — они не менялись патчем.)

def resolve_tv_ticker(asset_code: str, asset_type_ui: str):
    return TV_TICKER_MAP.get(asset_type_ui, {}).get(asset_code)


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


# ================= Резолвер кода актива =================
def _load_option_calc_assets():
    global _OPTION_CALC_ASSETS, _OPTION_CALC_ASSETS_TS
    now = time.time()
    if _OPTION_CALC_ASSETS is not None and (now - _OPTION_CALC_ASSETS_TS) < 21600:
        return _OPTION_CALC_ASSETS
    data = iss_get_json(f"{API_BASE_URL}/assets", timeout=15)
    if isinstance(data, list):
        _OPTION_CALC_ASSETS = data
        _OPTION_CALC_ASSETS_TS = now
    return _OPTION_CALC_ASSETS or []


_OPTION_CALC_ASSETS = None
_OPTION_CALC_ASSETS_TS = 0.0

_SHARE_TO_FUTURE_ALIAS = {
    "GAZP": "GAZR", "SBER": "SBRF", "SBERP": "SBPR",
    "MTSS": "MTSI", "SNGS": "SNGR", "SNGSP": "SNGP", "TRNFP": "TRNF",
}

_UI_TO_ASSET_TYPES = {
    "Акция":   [("share",     None)],
    "Фьючерс": [("futures",   None)],
    "Индекс":  [("index",     None), ("futures", "index")],
    "Валюта":  [("currency",  None), ("futures", "currency")],
    "Товар":   [("commodity", None), ("futures", "commodity")],
}


def resolve_option_calc_code(asset_input: str, asset_type_ui: str):
    ticker = (asset_input or "").strip().upper()
    moex_type = ASSET_TYPE_MAP.get(asset_type_ui, "futures")
    if not ticker:
        return ticker, moex_type

    if asset_type_ui == "Индекс" and ticker == "RTSI":
        ticker = "RTS"

    if asset_type_ui == "Фьючерс":
        alias = _SHARE_TO_FUTURE_ALIAS.get(ticker)
        if alias:
            ticker = alias

    assets = _load_option_calc_assets()
    if assets:
        wanted = _UI_TO_ASSET_TYPES.get(asset_type_ui, [(moex_type, None)])
        supported = {
            (a.get("asset_code"), a.get("asset_type"), a.get("asset_subtype"))
            for a in assets
        }
        for atype, sub in wanted:
            if (ticker, atype, sub) in supported:
                return ticker, atype
        for atype, _sub in wanted:
            for a in assets:
                if a.get("asset_code") == ticker and a.get("asset_type") == atype:
                    return ticker, atype

    return ticker, moex_type


# ================= Комиссии =================
def calc_commission(premium, instrument_type="Опцион",
                    min_comm_options=0.02,
                    comm_options_pct=3.0,
                    comm_futures_pct=0.1,
                    comm_stocks_pct=0.3):
    if premium is None or premium <= 0:
        return 0.0

    t = (instrument_type or "").strip().lower()
    _MIN_OTHER = 0.01

    if t in ("опцион", "option"):
        _c = max((comm_options_pct / 100.0) * premium, min_comm_options)
    elif t in ("фьючерс", "futures"):
        _c = max((comm_futures_pct / 100.0) * premium, _MIN_OTHER)
    elif t in ("акция", "stock", "share", "облигация", "etf", "bond"):
        _c = max((comm_stocks_pct / 100.0) * premium, _MIN_OTHER)
    elif t in ("металл", "metal", "драгметалл", "золото", "серебро"):
        _c = max(0.019 * premium, _MIN_OTHER)
    elif t in ("валюта", "currency", "валютный"):
        _c = max(0.009 * premium, _MIN_OTHER)
    else:
        _c = 0.0

    return round(_c, 2)


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


# ================= Дивиденды =================
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_dividends_smartlab() -> pd.DataFrame:
    # ... (без изменений) ...
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
@st.cache_data(ttl=CHECKLIST_RULES["cache_g_curve_ttl_sec"], show_spinner=False)
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


# ================= RVI =================
@st.cache_data(ttl=CHECKLIST_RULES["cache_rvi_ttl_sec"], show_spinner=False)
def fetch_rvi_current():
    url = "https://iss.moex.com/iss/engines/stock/markets/index/securities/RVI.json"
    data = iss_get_json(url, params={"iss.meta": "off"}, timeout=15)
    if data is None:
        return {"value": None, "error": "Ошибка запроса ISS"}

    result = {
        "value": None, "open": None, "change": None, "change_pct": None,
        "high": None, "low": None, "annual_high": None, "annual_low": None,
        "update_time": None, "trade_date": None, "error": None,
    }

    sec = data.get("securities", {})
    if sec.get("data"):
        rd = dict(zip(sec["columns"], sec["data"][0]))
        result["annual_high"] = rd.get("ANNUALHIGH")
        result["annual_low"] = rd.get("ANNUALLOW")

    md = data.get("marketdata", {})
    if md.get("data"):
        rd = dict(zip(md["columns"], md["data"][0]))
        for key, rkey in [
            ("LASTVALUE", "value"), ("OPENVALUE", "open"),
            ("LASTCHANGE", "change"), ("LASTCHANGEPRC", "change_pct"),
            ("HIGH", "high"), ("LOW", "low"),
            ("UPDATETIME", "update_time"), ("TRADEDATE", "trade_date"),
        ]:
            v = rd.get(key)
            if v is None or v == "":
                continue
            if rkey in ("update_time", "trade_date"):
                result[rkey] = v
            else:
                try:
                    result[rkey] = float(v)
                except (TypeError, ValueError):
                    pass

    if result["value"] is None:
        result["error"] = "RVI не найден в ответе ISS"
    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_rvi_history(days=365):
    end = datetime.now()
    start = end - timedelta(days=days)
    url = ("https://iss.moex.com/iss/engines/stock/markets/index/"
           "securities/RVI/candles.json")
    params = {
        "from": start.strftime("%Y-%m-%d"),
        "till": end.strftime("%Y-%m-%d"),
        "interval": 24,
        "iss.meta": "off",
    }
    data = iss_get_json(url, params=params, timeout=20)
    if data is None:
        return pd.DataFrame()
    cols = data.get("candles", {}).get("columns", [])
    rows = data.get("candles", {}).get("data", [])
    if not rows or not cols:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=cols)
    df["begin"] = pd.to_datetime(df["begin"], errors="coerce")
    df = df.dropna(subset=["begin", "close"])
    df = df.sort_values("begin").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rvi_stats(days=365):
    df = fetch_rvi_history(days=days)
    if df.empty:
        return None
    values = df["close"].values
    current = values[-1] if len(values) > 0 else None
    if current is None:
        return None
    return {
        "min": float(np.min(values)), "max": float(np.max(values)),
        "mean": float(np.mean(values)), "median": float(np.median(values)),
        "current": float(current),
        "percentile": float(np.mean(values <= current) * 100),
        "count": len(values),
    }


def classify_iv_vs_rvi(iv, rvi):
    if iv is None or rvi is None or rvi <= 0:
        return None
    spread = iv - rvi
    ratio = iv / rvi
    if ratio > 2.0:
        zone, label, color = "very_high", "Очень высокая", "#d32f2f"
        action = "Продавать волатильность (проверить новости!)"
    elif ratio > 1.5:
        zone, label, color = "high", "Повышенная", "#e6a500"
        action = "Осторожно, проверить контекст"
    elif ratio > 0.7:
        zone, label, color = "normal", "Норма", "#7a7a7a"
        action = "Направленные стратегии"
    elif ratio > 0.5:
        zone, label, color = "low", "Пониженная", "#00a651"
        action = "Кандидат на покупку волатильности"
    else:
        zone, label, color = "very_low", "Очень низкая", "#1e88e5"
        action = "Покупать волатильность (дёшево)"
    return {
        "spread": round(spread, 2), "ratio": round(ratio, 3),
        "zone": zone, "zone_label": label, "zone_color": color,
        "action": action,
    }


def classify_strategy(total_gamma, total_theta, total_vega):
    if total_gamma > 0 and total_theta < 0 and total_vega > 0:
        return {"class": "long_vol", "label": "ПОКУПКА ВОЛАТИЛЬНОСТИ",
                "color": "#00a651",
                "description": "Платите временной распад, ждёте движения или роста IV"}
    elif total_gamma < 0 and total_theta > 0 and total_vega < 0:
        return {"class": "short_vol", "label": "ПРОДАЖА ВОЛАТИЛЬНОСТИ",
                "color": "#d32f2f",
                "description": "Получаете премию за счёт распада, несёте риск движения и роста IV"}
    else:
        return {"class": "mixed", "label": "СМЕШАННАЯ",
                "color": "#7a7a7a",
                "description": "Комбинированная стратегия (календарь, бабочка и т.п.)"}


# ================= Дата-маркеры и метки =================
def expiry_marker(expiry_str: str) -> str:
    try:
        d = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    except Exception:
        return ""
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
        marker = expiry_marker(expiry_str)
        prefix = f"{marker} " if marker else ""
        return f"{prefix}{d.strftime('%d.%m.%Y')}"
    except Exception:
        return f"{expiry_str}"


# ================= LAST-цена БА =================
@st.cache_data(ttl=CHECKLIST_RULES["cache_last_price_ttl_sec"], show_spinner=False)
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
        elif c_str == "тренд":
            _col_map[c] = "Тренд"
        elif c_str == "волна":
            _col_map[c] = "Волна"
        elif c_str == "тенденция":
            _col_map[c] = "Тенденция"
        elif c_str in ("тф уровня", "tf уровня", "tf", "timeframe"):
            _col_map[c] = "ТФ уровня"
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
    for _opt_col in ("Тренд", "Волна", "Тенденция", "ТФ уровня"):
        if _opt_col not in _xls.columns:
            _xls[_opt_col] = ""
        else:
            _xls[_opt_col] = _xls[_opt_col].fillna("").astype(str).str.strip()
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


# ================= Оповещения =================
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
def get_asset_code_and_type(asset_input: str, asset_type_ui: str):
    return resolve_option_calc_code(asset_input, asset_type_ui)


def _asset_code_candidates(asset: str, asset_type_ui: str):
    s_upper = (asset or "").strip().upper()
    code, _ = resolve_option_calc_code(asset, asset_type_ui)
    cands = [code] if code else []
    if s_upper and s_upper not in cands:
        cands.append(s_upper)
    if asset_type_ui == "Фьючерс":
        alias = _SHARE_TO_FUTURE_ALIAS.get(s_upper)
        if alias and alias not in cands:
            cands.append(alias)
    return cands or [s_upper]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_optionseries(asset: str, asset_type_ui: str):
    moex_type = ASSET_TYPE_MAP.get(asset_type_ui, 'futures')
    for asset_code in _asset_code_candidates(asset, asset_type_ui):
        url = f"{API_BASE_URL}/assets/{asset_code}/optionseries"
        data = iss_get_json(url, params={'asset_type': moex_type}, timeout=15)
        if data is None:
            continue
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
        if series:
            return series
    return []


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_series_for_asset(asset: str, asset_type_ui: str):
    series = fetch_optionseries(asset, asset_type_ui)
    if not series:
        return []
    return sorted(series, key=lambda x: x.get("expiry", ""))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_series_info(asset: str, asset_type_ui: str, series_code: str):
    moex_type = ASSET_TYPE_MAP.get(asset_type_ui, 'futures')
    data = None
    for asset_code in _asset_code_candidates(asset, asset_type_ui):
        url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}"
        r = iss_get(url, params={'asset_type': moex_type}, timeout=15)
        if r is None or r.status_code != 200:
            r = iss_get(url, timeout=15)
        if r is None:
            continue
        try:
            data = r.json()
        except Exception:
            continue
        if data:
            break
    if not data:
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


@st.cache_data(ttl=CHECKLIST_RULES["cache_board_ttl_sec"], show_spinner=False)
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


@st.cache_data(ttl=CHECKLIST_RULES["cache_board_ttl_sec"], show_spinner=False)
def fetch_optionboard(asset: str, asset_type_ui: str, series_code: str):
    board_data, used_asset_type, used_asset_code = None, None, None
    tried = []
    base_type = ASSET_TYPE_MAP.get(asset_type_ui, 'futures')
    for asset_code in _asset_code_candidates(asset, asset_type_ui):
        for at in [base_type, 'share', 'futures', 'index', 'currency', 'commodity']:
            key = (asset_code, at)
            if key in tried:
                continue
            tried.append(key)
            url = f"{API_BASE_URL}/assets/{asset_code}/optionseries/{series_code}/optionboard"
            data = iss_get_json(url, params={'asset_type': at}, timeout=15)
            if data is not None:
                board_data = data
                used_asset_type = at
                used_asset_code = asset_code
                break
        if board_data:
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
    if cs is None and used_asset_code:
        cs = fetch_central_strike(used_asset_code, series_code, used_asset_type)
    board_data['central_strike'] = cs
    board_data['series_code'] = series_code
    return board_data


@st.cache_data(ttl=300, show_spinner=False)
def fetch_volatility_graph(asset: str, series_code: str, asset_type_ui: str):
    asset_code, moex_type = get_asset_code_and_type(asset, asset_type_ui)
    url = (f"{API_BASE_URL}/assets/{asset_code}"
           f"/optionseries/{series_code}/volatility_graph")
    data = iss_get_json(url, params={'asset_type': moex_type}, timeout=15)
    return data if data is not None else []


from concurrent.futures import ThreadPoolExecutor, as_completed

@st.cache_data(ttl=300, show_spinner=False)
def fetch_series_overview(asset: str, asset_type_ui: str):
    series_list = fetch_optionseries(asset, asset_type_ui)
    if not series_list:
        return pd.DataFrame()

    _today = date.today()

    def _fetch_one(_s):
        try:
            return _s, fetch_series_info(asset, asset_type_ui, _s["code"])
        except Exception:
            return _s, None

    _results = {}
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _futs = [_ex.submit(_fetch_one, _s) for _s in series_list]
        for _f in as_completed(_futs):
            _s, _info = _f.result()
            if _info:
                _results[_s["code"]] = (_s, _info)

    rows = []
    for _s in sorted(series_list, key=lambda x: x.get("expiry", "")):
        if _s["code"] not in _results:
            continue
        _, info = _results[_s["code"]]
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
        expiry = info.get("Дата исполнения", _s.get("expiry", "—"))
        try:
            d = datetime.strptime(expiry, "%Y-%m-%d").date()
            days_to = (d - _today).days
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
            "_series_type":  series_type_short,
            "Объём, ₽":      vol_rub,
            "Об.контр.":     vol_contr,
            "Откр.поз.":     oi,
            "Изменение, ₽":  oi_change,
            "_series_code":  _s["code"],
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


@st.cache_data(ttl=CHECKLIST_RULES["cache_last_price_ttl_sec"], show_spinner=False)
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


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_board_cached_30s(asset: str, asset_type_ui: str, series_code: str):
    if not (asset and asset_type_ui and series_code):
        return None
    base_type = ASSET_TYPE_MAP.get(asset_type_ui, 'futures')
    type_order = [base_type, 'futures', 'share', 'index', 'currency', 'commodity']
    tried = []
    for asset_code in _asset_code_candidates(asset, asset_type_ui):
        for at in type_order:
            key = (asset_code, at)
            if key in tried:
                continue
            tried.append(key)
            url = (f"{API_BASE_URL}/assets/{asset_code}"
                   f"/optionseries/{series_code}/optionboard")
            data = iss_get_json(url, params={'asset_type': at}, timeout=15)
            if data is not None:
                return data
    return None
    # ================= Payoff-расчёты =================
# (без изменений — вставьте существующие функции:
#  _months_between, _bs_price_np, compute_payoff, find_breakevens)

# ================= Биржевой график =================
# (без изменений — вставьте существующую render_exchange_chart)

# ================= Вспомогательные =================
# (без изменений — _color_call_put, _side_from_qty, _side_ui,
#  _side_internal, _new_position_id, _fmt_strike,
#  _greek_delta_color, _greek_theta_color)


# ================= Карточка оповещения =================
def _render_alert_card(r: dict):
    """Карточка тикера: цена, уровни с плашками, чек-боксы, badges."""
    _ticker = r["ticker"]
    _category = r["category"]
    _last = r["market_price"]
    _lvl_buy = r["lvl_buy"]
    _lvl_sell = r["lvl_sell"]
    _buy_dev = r["buy_dev_pct"]
    _sell_dev = r["sell_dev_pct"]
    _buy_active = r["buy_active"]
    _sell_active = r["sell_active"]
    _at_buy = r.get("at_buy_today", False)
    _at_sell = r.get("at_sell_today", False)
    _high_vol = r.get("high_volume", False)
    _spike = r.get("intraday_spike", False)

    _checks_key = f"{_ticker.upper().strip()}|{_category.strip()}"
    _all_checks_card = st.session_state.get("_alert_checks", {})
    _stored_card = _all_checks_card.get(_checks_key) or {}

    _stored_buy_card = _stored_card.get("_lvl_buy")
    _stored_sell_card = _stored_card.get("_lvl_sell")
    _levels_changed_card = False
    if _stored_buy_card is not None and _stored_sell_card is not None:
        if (abs(float(_stored_buy_card) - float(_lvl_buy)) > 0.01
                or abs(float(_stored_sell_card) - float(_lvl_sell)) > 0.01):
            _levels_changed_card = True

    if _levels_changed_card:
        _all_checks_card[_checks_key] = {
            "buy": None, "sell": None,
            "_lvl_buy": _lvl_buy, "_lvl_sell": _lvl_sell,
        }
        st.session_state["_alert_checks"] = _all_checks_card
        st.session_state.pop(f"_alert_buy_check_{_checks_key}", None)
        st.session_state.pop(f"_alert_sell_check_{_checks_key}", None)
        _cur_checks = {"buy": None, "sell": None}
    else:
        _cur_checks = _stored_card or {"buy": None, "sell": None}

    _price_str = f"{_last:,.2f} ₽" if _last else "— ₽"
    _buy_dev_str = f"{_buy_dev:+.2f} %" if _buy_dev is not None else "—"
    _sell_dev_str = f"{_sell_dev:+.2f} %" if _sell_dev is not None else "—"

    _buy_bg = "#0a8f3c" if _buy_active else "#e6e9ec"
    _buy_fg = "#ffffff" if _buy_active else "#5a6b78"
    _sell_bg = "#d32f2f" if _sell_active else "#e6e9ec"
    _sell_fg = "#ffffff" if _sell_active else "#5a6b78"
    _buy_mark = "✓" if _buy_active else "·"
    _sell_mark = "✓" if _sell_active else "·"

    _lvl_buy_bg      = "rgba(156, 0, 255, 0.15)"
    _lvl_buy_border  = "rgba(156, 0, 255, 0.45)"
    _lvl_sell_bg     = "rgba(251, 146, 240, 0.30)"
    _lvl_sell_border = "rgba(251, 146, 240, 0.65)"

    _prox_buy  = _level_proximity(_last, _lvl_buy,  _lvl_sell)
    _prox_sell = _level_proximity(_last, _lvl_sell, _lvl_buy)

    _at_buy_badge  = ("<div style='margin-top:4px; padding:2px 8px; "
                      "display:inline-block; border-radius:10px; "
                      "background:#9c00ff; color:#fff; font-size:.62rem; "
                      "font-weight:700; letter-spacing:.04em;'>"
                      "ЦЕНА НА УРОВНЕ</div>") if _at_buy else ""
    _at_sell_badge = ("<div style='margin-top:4px; padding:2px 8px; "
                      "display:inline-block; border-radius:10px; "
                      "background:#d81b60; color:#fff; font-size:.62rem; "
                      "font-weight:700; letter-spacing:.04em;'>"
                      "ЦЕНА НА УРОВНЕ</div>") if _at_sell else ""

    def _prox_bar_html(prox, color):
        if prox is None:
            return ""
        _p = max(0.0, min(100.0, float(prox)))
        return (f"<div style='margin-top:5px; height:6px; "
                f"background:#e6e9ec; border-radius:3px; overflow:hidden;'>"
                f"<div style='height:100%; width:{_p:.0f}%; "
                f"background:{color}; transition:width .3s;'></div></div>"
                f"<div style='font-size:.6rem; color:#5a6b78; "
                f"margin-top:1px;'>Близость: {_p:.0f}%</div>")

    with st.container(border=True):
        st.markdown(
            f"<div style='display:flex; justify-content:space-between; "
            f"align-items:baseline;'>"
            f"<div style='font-size:1.15rem; font-weight:700; color:#111; "
            f"line-height:1.1;'>{_ticker} "
            f"<span style='font-size:.85rem; margin-left:6px;'>"
            f"{_trend_emoji_triplet(r.get('trend',''), r.get('wave',''), r.get('tendency',''))}"
            f"</span></div>"
            f"<div style='font-size:1.05rem; font-weight:700; color:#111;'>"
            f"{_price_str}</div></div>"
            f"<div style='font-size:.68rem; color:#5a6b78; margin-top:2px; "
            f"text-transform:uppercase; letter-spacing:.06em;'>"
            f"{_category}</div>",
            unsafe_allow_html=True)

        # G4: мини-бейдж рекомендации
        try:
            _strikes_card = []
            try:
                # [PATCH 7] Не запрашивать доску, если _series_code пустой —
                # иначе карточки делают заведомо бесполезный сетевой запрос.
                _card_series = r.get("_series_code")
                _b_chk = (
                    fetch_optionboard(r["ticker"], _category, _card_series)
                    if _card_series
                    else None
                )
                if _b_chk:
                    _strikes_card = sorted({
                        float(x["strike"]) for side_key in ("call", "put")
                        for x in (_b_chk.get(side_key) or [])
                        if x.get("strike") is not None
                    })
            except Exception:
                _strikes_card = []

            _range_strikes_card = _calc_range_strikes(
                _lvl_buy, _lvl_sell, _strikes_card)

            _sugg_card = _suggest_strategy(
                buy_check=_cur_checks.get("buy"),
                sell_check=_cur_checks.get("sell"),
                trend=r.get("trend", ""),
                wave=r.get("wave", ""),
                tendency=r.get("tendency", ""),
                range_strikes=_range_strikes_card,
                iv_zone=None, skew_type=None)

            if _sugg_card.get("strategy"):
                _conf_color = {"high": "#00a651",
                               "medium": "#e6a500",
                               "low": "#7a7a7a"}.get(
                    _sugg_card["confidence"], "#7a7a7a")
                st.markdown(
                    f"<div style='margin-top:6px; padding:4px 8px; "
                    f"border-radius:6px; background:#f0f4f8; "
                    f"border-left:3px solid {_conf_color}; "
                    f"font-size:.7rem; color:#2c506d;'>"
                    f"<b>Рекомендация:</b> {_sugg_card['direction_ui']}"
                    f"<span style='color:#5a6b78;'> — "
                    f"{_sugg_card['rationale']}</span></div>",
                    unsafe_allow_html=True)
        except Exception:
            pass

        _vol_badges = []
        if _high_vol:
            _vol_badges.append(
                "<div style='padding:3px 8px; border-radius:10px; "
                "background:#d32f2f; color:#fff; font-size:.68rem; "
                "font-weight:700; letter-spacing:.03em; display:inline-block; "
                "margin-right:6px;'>ВЫСОКИЙ ОБЪЁМ</div>")
        if _spike:
            _vol_badges.append(
                "<div style='padding:3px 8px; border-radius:10px; "
                "background:#ff6f00; color:#fff; font-size:.68rem; "
                "font-weight:700; letter-spacing:.03em; display:inline-block;'>"
                "ВСПЛЕСК ОБЪЁМА</div>")
        if _vol_badges:
            st.markdown(
                f"<div style='margin-top:6px;'>{''.join(_vol_badges)}</div>",
                unsafe_allow_html=True)

        st.markdown(
            "<div style='margin-top:8px; font-size:.66rem; color:#2c506d; "
            "font-weight:700; text-transform:uppercase; "
            "letter-spacing:.05em;'>Ожидание движения стрелой</div>",
            unsafe_allow_html=True)

        _cur_buy = _cur_checks.get("buy")
        _cur_sell = _cur_checks.get("sell")

        _buy_opts = ["—", "1", "2"]
        _buy_idx = 0
        if _cur_buy == "1":
            _buy_idx = 1
        elif _cur_buy == "2":
            _buy_idx = 2

        _sell_opts = ["—", "3", "4"]
        _sell_idx = 0
        if _cur_sell == "3":
            _sell_idx = 1
        elif _cur_sell == "4":
            _sell_idx = 2

        _opt_labels = {
            "—": "—",
            "1": "**1** покупка :green-background[**CALL**]",
            "2": "**2** продажа :red-background[**PUT**]",
            "3": "**3** продажа :green-background[**CALL**]",
            "4": "**4** покупка :red-background[**PUT**]",
        }

        def _fmt_opt(v):
            return _opt_labels.get(v, v)

        _lc1, _lc2 = st.columns(2)
        with _lc1:
            st.markdown(
                f"<div style='background:{_lvl_buy_bg}; "
                f"border:1px solid {_lvl_buy_border}; border-radius:6px; "
                f"padding:7px 9px;'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<div style='font-size:.6rem; color:#333; font-weight:700; "
                f"text-transform:uppercase; letter-spacing:.06em;'>Покупка</div>"
                f"<div style='font-size:.65rem; font-weight:700; "
                f"color:{_buy_fg}; background:{_buy_bg}; "
                f"padding:2px 6px; border-radius:10px;'>{_buy_mark}</div>"
                f"</div>"
                f"<div style='font-size:1.02rem; font-weight:700; color:#111; "
                f"line-height:1.2; margin-top:2px;'>{_lvl_buy:.2f}</div>"
                f"<div style='font-size:.76rem; color:#333; margin-top:1px;'>"
                f"{_buy_dev_str}</div>"
                f"{_at_buy_badge}"
                f"{_prox_bar_html(_prox_buy, '#9c00ff')}"
                f"</div>", unsafe_allow_html=True)

            _buy_choice = st.radio(
                "buy_group",
                _buy_opts,
                index=_buy_idx,
                key=f"_alert_buy_check_{_checks_key}",
                horizontal=True,
                format_func=_fmt_opt,
                label_visibility="collapsed")

        with _lc2:
            st.markdown(
                f"<div style='background:{_lvl_sell_bg}; "
                f"border:1px solid {_lvl_sell_border}; border-radius:6px; "
                f"padding:7px 9px;'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                f"<div style='font-size:.6rem; color:#333; font-weight:700; "
                f"text-transform:uppercase; letter-spacing:.06em;'>Продажа</div>"
                f"<div style='font-size:.65rem; font-weight:700; "
                f"color:{_sell_fg}; background:{_sell_bg}; "
                f"padding:2px 6px; border-radius:10px;'>{_sell_mark}</div>"
                f"</div>"
                f"<div style='font-size:1.02rem; font-weight:700; color:#111; "
                f"line-height:1.2; margin-top:2px;'>{_lvl_sell:.2f}</div>"
                f"<div style='font-size:.76rem; color:#333; margin-top:1px;'>"
                f"{_sell_dev_str}</div>"
                f"{_at_sell_badge}"
                f"{_prox_bar_html(_prox_sell, '#d81b60')}"
                f"</div>", unsafe_allow_html=True)

            _sell_choice = st.radio(
                "sell_group",
                _sell_opts,
                index=_sell_idx,
                key=f"_alert_sell_check_{_checks_key}",
                horizontal=True,
                format_func=_fmt_opt,
                label_visibility="collapsed")

        _new_checks = st.session_state.get("_alert_checks", {})
        if _checks_key not in _new_checks:
            _new_checks[_checks_key] = {}
        _new_checks[_checks_key]["buy"] = (
            None if _buy_choice == "—" else _buy_choice)
        _new_checks[_checks_key]["sell"] = (
            None if _sell_choice == "—" else _sell_choice)
        _new_checks[_checks_key]["_lvl_buy"] = _lvl_buy
        _new_checks[_checks_key]["_lvl_sell"] = _lvl_sell
        st.session_state["_alert_checks"] = _new_checks


# ================= alert_targets, postMessage-мост, аналитика =================
# (без изменений — _nearest_strike_above, _nearest_strike_below,
#  _get_board_price_for, build_alert_targets, _send_to_iframes,
#  push_expiry_to_calculator, push_strikes_to_calculator,
#  push_alert_levels, _weighted_avg_iv)


def _store_iv_snapshot(asset, atype, series, iv_value):
    if iv_value is None:
        return
    today_str = date.today().isoformat()
    key = f"{asset}|{atype}|{series}"
    history = st.session_state.get("_iv_history")
    if history is None:
        history = {}
        st.session_state["_iv_history"] = history
    bucket = history.setdefault(key, [])
    for d, _ in bucket:
        if d == today_str:
            return
    bucket.append((today_str, float(iv_value)))
    if len(bucket) > 500:
        history[key] = bucket[-500:]


# [PATCH 3] Новые функции для сохранения HV и RVI рядом с _store_iv_snapshot
def _merge_history_records(previous, incoming):
    """Объединение по дате без потери ранее накопленных значений."""
    merged = {
        row["date"]: dict(row)
        for row in previous
        if isinstance(row, dict) and row.get("date")
    }

    for row in incoming:
        day = row["date"]
        target = merged.setdefault(day, {"date": day})

        # Неполное новое окно расчёта не должно стирать старую HV.
        for key, value in row.items():
            if value is not None:
                target[key] = value

    return [merged[day] for day in sorted(merged)]


def _remember_volatility_history(asset, category, bars, rvi_frame=None):
    if isinstance(bars, pd.DataFrame) and not bars.empty:
        frame = bars[["begin", "close"]].copy()
        frame["begin"] = pd.to_datetime(frame["begin"], errors="coerce")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = (
            frame.dropna()
            .query("close > 0")
            .sort_values("begin")
            .drop_duplicates("begin", keep="last")
        )

        returns = np.log(frame["close"] / frame["close"].shift(1))

        history = pd.DataFrame({
            "date": frame["begin"].dt.strftime("%Y-%m-%d")
        })

        for window in (10, 20, 50, 100):
            history[f"hv{window}"] = (
                returns.rolling(window).std(ddof=1)
                * np.sqrt(252)
                * 100
            )

        fields = ["hv10", "hv20", "hv50", "hv100"]
        history = history.dropna(subset=fields, how="all")
        incoming = _backup_clean(history.to_dict(orient="records"))

        key = f"{asset}|{category}"
        all_hv = dict(st.session_state.get("_hv_history", {}))
        all_hv[key] = _merge_history_records(all_hv.get(key, []), incoming)
        st.session_state["_hv_history"] = all_hv

    if isinstance(rvi_frame, pd.DataFrame) and not rvi_frame.empty:
        frame = rvi_frame[["begin", "close"]].copy()
        frame["begin"] = pd.to_datetime(frame["begin"], errors="coerce")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame.dropna().sort_values("begin")

        incoming = [
            {
                "date": timestamp.date().isoformat(),
                "value": float(value),
            }
            for timestamp, value in zip(frame["begin"], frame["close"])
            if math.isfinite(float(value)) and float(value) >= 0
        ]

        st.session_state["_rvi_history"] = _merge_history_records(
            st.session_state.get("_rvi_history", []),
            incoming,
        )


# ================= _portfolio_value, _portfolio_value_with_rvi,
# _get_current_market_price_for_asset =================
# (без изменений)


# ================= Трендовые хелперы оповещений =================
# (без изменений — _ALERT_TREND_EMOJI, _ALERT_RECOMMENDATION_MAP,
#  _trend_emoji, _trend_emoji_triplet, _get_recommendation,
#  find_alert_full_info, analyze_level_activity, _level_proximity,
#  get_alert_checks, get_alert_recommendation_text,
#  _compute_r_q_for_leg, _migrate_positions_r_q,
#  _calc_range_strikes, _suggest_strategy, _suggestion_legs,
#  _apply_suggested_strategy,
#  _pretrade_checklist_state, _render_pretrade_checklist,
#  _validate_options_leg,
#  _planned_close_date, _planned_close_badge, _planned_close_date_str)


# ================= Кэш позиций и доски =================
# (без изменений — _fetch_board_nocache, _strike_eq, _find_board_row,
#  _find_board_row_by_secid, _get_board_for_analytics, _get_cache_file_path,
#  _cache_file, _load_cache, _save_cache, _positions_signature)


# ================= Хелперы для журнала =================
# (без изменений — _journal_closed_sorted, _journal_equity_series,
#  _journal_max_drawdown, _journal_profit_factor, _journal_streaks,
#  _journal_stats_by, _journal_get_deposit)


# ==================================================================
# [PATCH 1] Резервная копия состояния — ПОЛНАЯ ЗАМЕНА
# ==================================================================

_BACKUP_SETTINGS = {
    # Поле JSON: (ключ session_state, значение по умолчанию, min, max)
    "deposit": ("dep_inp", 100000.0, 0.0, None),
    "risk_pct": ("rp_inp", 1.0, 0.1, 100.0),
    "comm_options_pct": ("cop_inp", 3.0, 0.0, 20.0),
    "comm_options_min": ("cmo_inp", 0.02, 0.0, 100.0),
    "comm_futures_pct": ("cfp_inp", 0.1, 0.0, 5.0),
    "comm_stocks_pct": ("csp_inp", 0.3, 0.0, 5.0),
}


def _backup_clean(value):
    """Создаёт JSON-совместимую копию, не изменяя session_state."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, np.generic):
        return _backup_clean(value.item())

    if isinstance(value, np.ndarray):
        return _backup_clean(value.tolist())

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, dict):
        return {str(k): _backup_clean(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_backup_clean(v) for v in value]

    raise TypeError(
        f"Неподдерживаемый тип данных в резервной копии: "
        f"{type(value).__name__}"
    )


def _backup_number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValueError(f"{name}: ожидалось число, а не bool")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: неверное числовое значение") from None

    if not math.isfinite(number):
        raise ValueError(f"{name}: число должно быть конечным")

    if minimum is not None and number < minimum:
        raise ValueError(f"{name}: значение меньше {minimum}")

    if maximum is not None and number > maximum:
        raise ValueError(f"{name}: значение больше {maximum}")

    return number


def _validate_positions_cache(raw):
    if not isinstance(raw, dict):
        raise ValueError("positions_cache должен быть JSON-объектом")

    result = {}

    for key, rows in raw.items():
        if not isinstance(key, str) or "|" not in key:
            raise ValueError(f"Неверная привязка позиций к активу: {key!r}")

        asset, category = key.split("|", 1)

        if not asset.strip() or category not in ASSET_TYPE_MAP:
            raise ValueError(f"Неверный ключ актива: {key}")

        if not isinstance(rows, list):
            raise ValueError(f"{key}: ожидался список позиций")

        checked_rows = []
        seen_ids = set()

        for index, source in enumerate(rows):
            if not isinstance(source, dict):
                raise ValueError(f"{key}, строка {index + 1}: ожидался объект")

            row = _backup_clean(source)

            qty = _backup_number(
                row.get("Кол-во", 0),
                f"{key}: количество",
                -10000,
                10000,
            )
            if not qty.is_integer():
                raise ValueError(f"{key}: количество должно быть целым")

            row["Кол-во"] = int(qty)
            row["Цена"] = _backup_number(
                row.get("Цена", 0), f"{key}: цена", 0.0
            )

            numeric_fields = (
                "Страйк", "Теор.цена",
                "Дельта", "Гамма", "Вега", "Тета", "Ро",
                "_vol", "_r", "_q",
            )
            for field in numeric_fields:
                if row.get(field) is not None:
                    row[field] = _backup_number(
                        row[field], f"{key}: {field}"
                    )

            # Старым позициям добавляем отсутствующую привязку.
            if not row.get("_asset"):
                row["_asset"] = asset
            if not row.get("_atype"):
                row["_atype"] = category

            row["_id"] = str(row.get("_id") or _new_position_id())
            if row["_id"] in seen_ids:
                raise ValueError(f"{key}: повторяющийся ID позиции")

            seen_ids.add(row["_id"])
            checked_rows.append(row)

        result[key] = checked_rows

    return result


def _validate_iv_history(raw):
    if not isinstance(raw, dict):
        raise ValueError("iv_history должен быть JSON-объектом")

    result = {}

    for key, bucket in raw.items():
        if not isinstance(bucket, list):
            raise ValueError(f"История IV {key}: ожидался список")

        points = {}
        for point in bucket:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(f"История IV {key}: неверная точка")

            day = date.fromisoformat(str(point[0])).isoformat()
            iv = _backup_number(point[1], f"История IV {key}", 0.0)
            points[day] = iv

        result[key] = [[day, points[day]] for day in sorted(points)]

    return result


def _validate_history_records(raw, fields):
    if not isinstance(raw, list):
        raise ValueError("Исторические данные должны быть списком")

    result = {}
    for source in raw:
        if not isinstance(source, dict):
            raise ValueError("Неверная запись исторических данных")

        day = date.fromisoformat(str(source.get("date", ""))).isoformat()
        row = {"date": day}

        for field in fields:
            value = source.get(field)
            row[field] = (
                None if value is None
                else _backup_number(value, f"{day}: {field}", 0.0)
            )

        result[day] = row

    return [result[day] for day in sorted(result)]


def _export_full_cache():
    """Экспорт без сетевых запросов; активная позиция имеет приоритет."""
    cache = _backup_clean(st.session_state.get("positions_cache", {}))
    current = _backup_clean(st.session_state.get("positions", []))
    active_key = st.session_state.get("_pos_active_key")

    if current and not active_key:
        asset = st.session_state.get("pos_asset", "")
        category = st.session_state.get("pos_category", "")
        if not asset or category not in ASSET_TYPE_MAP:
            raise ValueError("Не определён базовый актив текущей позиции")
        active_key = f"{asset}|{category}"

    # Важно: сохраняем и пустой список — иначе удалённые сделки
    # могут остаться в старой копии positions_cache.
    if active_key:
        cache[active_key] = current

    alerts_df = st.session_state.get("alerts_df")
    alerts_snapshot = (
        alerts_df.to_dict(orient="records")
        if isinstance(alerts_df, pd.DataFrame) and not alerts_df.empty
        else []
    )

    payload = {
        "_meta": {
            "version": 3,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "app": "MOEX Options & Black-Scholes",
        },
        "positions_cache": cache,
        "positions_current": current,
        "positions_active_key": active_key,
        "journal_rows": st.session_state.get("journal_rows", []),
        "iv_history": st.session_state.get("_iv_history", {}),
        "hv_history": st.session_state.get("_hv_history", {}),
        "rvi_history": st.session_state.get("_rvi_history", []),
        "alert_checks": st.session_state.get("_alert_checks", {}),
        "alerts_snapshot": alerts_snapshot,
        "journal_deposit": {
            "initial": st.session_state.get(
                "journal_initial_deposit", 100000.0
            ),
            "current_manual": st.session_state.get(
                "journal_current_deposit_manual"
            ),
            "mode": st.session_state.get("journal_deposit_mode", "auto"),
        },
        "settings": {
            name: st.session_state.get(spec[0], spec[1])
            for name, spec in _BACKUP_SETTINGS.items()
        },
    }

    return json.dumps(
        _backup_clean(payload),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


def _import_full_cache(json_str):
    """
    Сначала проверяет данные, затем применяет их.

    Вызывать до отрисовки виджетов Позиции/Журнала/Оповещений,
    как показано в блоке управления резервной копией ниже.
    """
    try:
        data = _backup_clean(json.loads(json_str))

        if not isinstance(data, dict):
            raise ValueError("Ожидался JSON-объект")

        # Старый формат: {"SBER|Акция": [...], ...}
        if "_meta" not in data:
            cache = _validate_positions_cache(data)
            data = {
                "_meta": {"version": 1},
                "positions_cache": cache,
            }

        meta = data.get("_meta")
        if not isinstance(meta, dict):
            raise ValueError("Неверный блок _meta")

        version = meta.get("version")
        if version not in (1, 2, 3):
            raise ValueError(f"Неизвестная версия резервной копии: {version}")

        updates = {}
        loaded = []

        if "positions_cache" in data or "positions_current" in data:
            cache = _validate_positions_cache(
                data.get(
                    "positions_cache",
                    st.session_state.get("positions_cache", {}),
                )
            )
            active_key = data.get("positions_active_key")

            if active_key is not None:
                # Проверяем и ключ, и текущие позиции.
                current = data.get(
                    "positions_current", cache.get(active_key, [])
                )
                checked = _validate_positions_cache({active_key: current})
                cache[active_key] = checked[active_key]

            elif data.get("positions_current"):
                raise ValueError(
                    "У текущих позиций отсутствует привязка к базовому активу"
                )

            else:
                previous_key = st.session_state.get("_pos_active_key")
                active_key = (
                    previous_key if previous_key in cache
                    else next(
                        (key for key, rows in cache.items() if rows),
                        next(iter(cache), None),
                    )
                )

            updates["positions_cache"] = cache
            updates["positions"] = _backup_clean(cache.get(active_key, []))
            updates["_pos_active_key"] = active_key

            if active_key:
                asset, category = active_key.split("|", 1)
                updates.update({
                    "pos_asset": asset,
                    "pos_category": category,
                    "pos_asset_input": asset,
                    "pos_category_select": category,
                })

            updates.update({
                "pos_series_list": [],
                "pos_series_code": "",
                "pos_expiry": "",
                "pos_autoloaded_for": (None, None),
            })
            loaded.append("позиции по активам")

        if "journal_rows" in data:
            rows = data["journal_rows"]
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) for row in rows
            ):
                raise ValueError("Неверный формат журнала")

            updates["journal_rows"] = rows
            loaded.append("журнал")

        if "iv_history" in data:
            updates["_iv_history"] = _validate_iv_history(data["iv_history"])
            loaded.append("история IV")

        if "hv_history" in data:
            raw = data["hv_history"]
            if not isinstance(raw, dict):
                raise ValueError("hv_history должен быть JSON-объектом")

            updates["_hv_history"] = {
                key: _validate_history_records(
                    rows, ("hv10", "hv20", "hv50", "hv100")
                )
                for key, rows in raw.items()
            }
            loaded.append("история HV")

        if "rvi_history" in data:
            updates["_rvi_history"] = _validate_history_records(
                data["rvi_history"], ("value",)
            )
            loaded.append("история RVI")

        if "alert_checks" in data:
            checks = data["alert_checks"]
            if not isinstance(checks, dict):
                raise ValueError("Неверный формат выбора оповещений")

            for key, row in checks.items():
                if not isinstance(row, dict):
                    raise ValueError(f"Неверное оповещение: {key}")
                if row.get("buy") not in (None, "1", "2"):
                    raise ValueError(f"Неверный выбор покупки: {key}")
                if row.get("sell") not in (None, "3", "4"):
                    raise ValueError(f"Неверный выбор продажи: {key}")

                for field in ("_lvl_buy", "_lvl_sell"):
                    if row.get(field) is not None:
                        row[field] = _backup_number(
                            row[field], f"{key}: {field}"
                        )

            updates["_alert_checks"] = checks
            loaded.append("выбор оповещений")

        if "alerts_snapshot" in data:
            records = data["alerts_snapshot"]
            if not isinstance(records, list):
                raise ValueError("Неверный снимок таблицы оповещений")

            if records:
                frame, error = _normalize_alerts_df(pd.DataFrame(records))
                if error:
                    raise ValueError(error)

                updates.update({
                    "alerts_df": frame,
                    "alerts_source": "JSON (снимок)",
                    "alerts_loaded_at": datetime.now().strftime("%H:%M:%S"),
                    "alerts_error": None,
                })
                loaded.append("уровни оповещений")

        settings = data.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError("Неверный формат настроек")

        for name, (state_key, default, low, high) in _BACKUP_SETTINGS.items():
            if name in settings:
                updates[state_key] = _backup_number(
                    settings[name], name, low, high
                )

        deposit = data.get("journal_deposit", {})
        if not isinstance(deposit, dict):
            raise ValueError("Неверный формат депозита журнала")

        if "initial" in deposit:
            updates["journal_initial_deposit"] = _backup_number(
                deposit["initial"], "Начальный депозит журнала", 0.0
            )

        if "current_manual" in deposit:
            value = deposit["current_manual"]
            updates["journal_current_deposit_manual"] = (
                None if value is None else _backup_number(
                    value, "Текущий депозит журнала", 0.0
                )
            )

        if "mode" in deposit:
            if deposit["mode"] not in ("auto", "manual"):
                raise ValueError("Неверный режим депозита")
            updates["journal_deposit_mode"] = deposit["mode"]

        # Все проверки выше завершены. Только теперь меняем состояние.
        reset_prefixes = (
            "_alert_buy_check_", "_alert_sell_check_",
            "qty_", "price_", "qp_", "qm_", "pp_", "pm_",
            "form_", "journal_edit_",
            "_calc_html_", "_hm_cache_",
        )
        reset_keys = {
            "fallback_series_selector",
            "journal_initial_deposit_inp",
            "journal_current_deposit_inp",
            "journal_deposit_mode_select",
            "journal_edit_sel",
            "journal_del_sel",
            "_prepared_backup",
            "_prepared_backup_at",
        }

        for key in list(st.session_state):
            if isinstance(key, str) and (
                key.startswith(reset_prefixes) or key in reset_keys
            ):
                st.session_state.pop(key, None)

        st.session_state.update(updates)
        st.session_state.update({
            "_alert_levels_cache": {},
            "_g3_migrated": False,
            "_pos_signature": None,
            "_wt_last_asset": None,
            "_current_market_price": None,
            "_full_cache_loaded_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        })

        if "positions_cache" in updates:
            _save_cache(updates["positions_cache"])

        return True, "Восстановлено: " + ", ".join(loaded or ["настройки"])

    except (ValueError, TypeError, KeyError) as error:
        return False, f"Не удалось восстановить копию: {error}"


# ==================================================================
# [PATCH 2] Резервная копия доступна вне вкладки «Позиция»
# ==================================================================
def _render_backup_controls():
    with st.expander("Резервная копия · JSON", expanded=False):
        message = st.session_state.pop("_backup_flash", None)
        if message:
            st.success(message)

        st.caption(
            "Позиции по всем активам, журнал, история IV/HV/RVI, "
            "выбор оповещений, уровни и настройки."
        )

        if _IS_CLOUD:
            st.caption(
                "На Cloud данные текущей сессии не гарантированно "
                "сохранятся после её завершения. Скачивайте резервную копию."
            )

        # Явная подготовка исключает скачивание устаревших данных
        # из другого Streamlit-фрагмента.
        if st.button(
            "1. Подготовить актуальную копию",
            key="backup_prepare",
            use_container_width=True,
        ):
            try:
                st.session_state["_prepared_backup"] = (
                    _export_full_cache().encode("utf-8")
                )
                st.session_state["_prepared_backup_at"] = (
                    datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                )
            except Exception as error:
                st.session_state.pop("_prepared_backup", None)
                st.error(f"Ошибка подготовки JSON: {error}")

        prepared = st.session_state.get("_prepared_backup")

        if prepared is not None:
            st.download_button(
                "2. Скачать JSON",
                data=prepared,
                file_name=(
                    f"moex_backup_"
                    f"{st.session_state['_prepared_backup_at']}"
                    .replace(":", "-")
                    .replace(" ", "_")
                    + ".json"
                ),
                mime="application/json",
                key="backup_download",
                use_container_width=True,
            )
            st.caption(
                "Снимок подготовлен: "
                + st.session_state["_prepared_backup_at"]
                + ". После изменения данных подготовьте его заново."
            )

        uploaded = st.file_uploader(
            "Восстановить резервную копию",
            type=["json"],
            key="backup_upload",
        )

        if uploaded is not None:
            st.caption(
                "Восстановление заменит соответствующие данные "
                "текущей сессии."
            )

            confirmed = st.checkbox(
                "Подтверждаю восстановление",
                key="backup_restore_confirm",
            )

            if st.button(
                "Восстановить из JSON",
                key="backup_restore",
                disabled=not confirmed,
                use_container_width=True,
            ):
                try:
                    text = uploaded.getvalue().decode("utf-8-sig")
                    ok, message = _import_full_cache(text)
                except UnicodeError:
                    ok, message = False, "Файл должен иметь кодировку UTF-8"

                if ok:
                    st.session_state["_backup_flash"] = message
                    st.rerun()
                else:
                    st.error(message)
                    # ================= UI =================
st.title("MOEX Options & Black-Scholes")

# ================= RVI HEADER =================
_rvi_header = fetch_rvi_current()
if _rvi_header and _rvi_header.get("value") is not None:
    _rvi_v = _rvi_header["value"]
    _rvi_chg = _rvi_header.get("change") or 0.0
    _rvi_chg_pct = _rvi_header.get("change_pct") or 0.0

    if _rvi_v < 20:
        _rvi_color = "#00a651"
        _rvi_icon = "🟢"
    elif _rvi_v < 35:
        _rvi_color = "#e6a500"
        _rvi_icon = "🟡"
    else:
        _rvi_color = "#d32f2f"
        _rvi_icon = "🔴"

    st.markdown(
        f"<div style='display:flex; align-items:center; gap:12px; "
        f"padding:6px 14px; background:#f0f4f8; border-radius:8px; "
        f"margin-bottom:12px; font-size:.9rem;'>"
        f"<span style='font-weight:700; color:{_rvi_color};'>"
        f"{_rvi_icon} RVI: {_rvi_v:.2f}%</span>"
        f"<span style='color:{_rvi_color};'>"
        f"({_rvi_chg:+.2f} п.п. / {_rvi_chg_pct:+.2f}%)</span>"
        f"<span style='color:#5a6b78; font-size:.8rem;'>"
        f"обновлено: {_rvi_header.get('update_time', '—')}</span>"
        f"</div>",
        unsafe_allow_html=True)


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

# ==================================================================
# Инициализация pos_* на модульном уровне.
# ==================================================================
if "pos_asset" not in st.session_state:
    st.session_state.pos_asset = st.session_state.get("board_asset", "SBER")
if "pos_category" not in st.session_state:
    st.session_state.pos_category = st.session_state.get("board_category", "Акция")
if "positions_cache" not in st.session_state:
    st.session_state.positions_cache = _load_cache()
if "positions" not in st.session_state:
    st.session_state.positions = []
if "_pos_signature" not in st.session_state:
    st.session_state["_pos_signature"] = None
if "_g3_migrated" not in st.session_state:
    st.session_state["_g3_migrated"] = False

# [PATCH 5] Начальный вид карточек на мобильных — стартовое значение,
# пользователь может переключиться.
if "pos_view_mode" not in st.session_state:
    st.session_state.pos_view_mode = "Карточки (мобильный)"

# ==================================================================
# [PATCH 5] Компактная навигация: selectbox вместо длинного radio
# ==================================================================
_TAB_NAMES = [
    "Калькулятор",
    "Доска опционов",
    "Позиция",
    "What-if",
    "Heatmap IV",
    "IV Rank",
    "Skew",
    "Журнал",
    "Келли",
    "Оповещения",
]

_active_tab = st.selectbox(
    "Раздел",
    _TAB_NAMES,
    key="main_nav",
    label_visibility="collapsed",
)


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

    _alert_assets = get_alert_assets_list()

    with st.expander("Актив и опционная серия", expanded=True):
        if _alert_assets:
            _opts = ["— выберите актив из оповещений —"] + [
                f"{it['ticker']} · {it['category']}" for it in _alert_assets
            ]
            _sel_label = st.selectbox(
                "Актив из оповещений", _opts, index=0,
                key="calc_asset_select",
                help="Список формируется из листа оповещений.")
            if _sel_label and not _sel_label.startswith("—"):
                _parts = _sel_label.split(" · ", 1)
                if len(_parts) == 2:
                    _tk_sel, _cat_sel = _parts
                    if (st.session_state.calc_asset_ticker != _tk_sel
                            or st.session_state.calc_asset_category != _cat_sel):
                        st.session_state["calc_asset_input"] = _tk_sel
                        st.session_state["calc_asset_type_select"] = _cat_sel
                        st.session_state.calc_asset_ticker = _tk_sel
                        st.session_state.calc_asset_category = _cat_sel
                        st.session_state.calc_series_list = []
                        st.session_state.calc_autoloaded_for = (None, None)
        else:
            st.caption("Лист оповещений не загружен.")

        _pc1, _pc2 = st.columns([3, 2])
        with _pc1:
            _raw_asset = st.text_input(
                "Базовый актив (тикер)",
                value=st.session_state.calc_asset_ticker,
                key="calc_asset_input", placeholder="SBER, GAZP, RTS…").strip()
        with _pc2:
            _cat_opts = ["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"]
            _cat_idx = (_cat_opts.index(st.session_state.calc_asset_category)
                        if st.session_state.calc_asset_category in _cat_opts else 0)
            _asset_type_ui = st.selectbox("Категория БА", _cat_opts,
                                          index=_cat_idx,
                                          key="calc_asset_type_select")

        _asset_canon = resolve_canonical_asset_code(_raw_asset, _asset_type_ui)

        if (_asset_canon != st.session_state.calc_asset_ticker
                or _asset_type_ui != st.session_state.calc_asset_category):
            st.session_state.calc_asset_ticker = _asset_canon
            st.session_state.calc_asset_category = _asset_type_ui
            st.session_state.calc_series_list = []
            st.session_state.calc_autoloaded_for = (None, None)

        _loaded_for = st.session_state.get("calc_autoloaded_for", (None, None))
        if _asset_canon and (_asset_canon, _asset_type_ui) != _loaded_for:
            with st.spinner("Загрузка опционных серий…"):
                try:
                    _series_loaded = fetch_optionseries(_asset_canon, _asset_type_ui)
                    st.session_state.calc_series_list = _series_loaded or []
                    st.session_state.calc_autoloaded_for = (_asset_canon, _asset_type_ui)
                    if not _series_loaded:
                        st.warning(f"ISS не вернул серий для {_asset_canon}")
                except Exception as e:
                    st.error(f"Ошибка загрузки серий: {e}")
                    st.session_state.calc_series_list = []
        elif not _asset_canon:
            st.session_state.calc_series_list = []
            st.session_state.calc_selected_series = ""
            st.session_state.calc_selected_expiry = ""
            st.session_state.calc_autoloaded_for = (None, None)

        if st.session_state.calc_series_list:
            _sorted_series = sorted(st.session_state.calc_series_list,
                                     key=lambda x: x.get("expiry", ""))
            _option_labels = [format_series_label(s["expiry"]) for s in _sorted_series]
            _chosen = st.selectbox("Дата исполнения", _option_labels, index=0,
                                    key="calc_series_select")
            _chosen_idx = _option_labels.index(_chosen)
            _selected = _sorted_series[_chosen_idx]
            st.session_state.calc_selected_series = _selected["code"]
            st.session_state.calc_selected_expiry = _selected["expiry"]
            try:
                _info = fetch_series_info(_asset_canon, _asset_type_ui,
                                           _selected["code"])
                with st.expander("Об опционной серии", expanded=False):
                    st.json(_info, expanded=True)
            except Exception as _e:
                st.warning(f"Информация о серии недоступна: {_e}")

    _levels = find_alert_levels(_asset_canon, category=_asset_type_ui)
    if _levels["found"]:
        st.info(f"Уровни для {_asset_canon}: "
                f"покупка = {_levels['buy']:.2f} ₽ · "
                f"продажа = {_levels['sell']:.2f} ₽")
    else:
        st.caption("Уровни из оповещений не найдены.")

    _board_calc = None
    if st.session_state.calc_selected_series:
        try:
            _board_calc = fetch_optionboard(_asset_canon, _asset_type_ui,
                                             st.session_state.calc_selected_series)
        except Exception:
            _board_calc = None

    _current_price_for_targets = None
    try:
        if _asset_type_ui in ("Фьючерс", "Валюта", "Товар"):
            _eng_t, _mkt_t = "futures", "forts"
        elif _asset_type_ui == "Индекс":
            _eng_t, _mkt_t = "stock", "index"
        else:
            _eng_t, _mkt_t = "stock", "shares"
        _secid_t = resolve_underlying_secid(_asset_canon, _asset_type_ui)
        if _secid_t:
            _current_price_for_targets = get_last_close_price(_secid_t, _eng_t, _mkt_t)
    except Exception:
        _current_price_for_targets = None

    _alert_targets = None
    if _board_calc is not None:
        try:
            _alert_targets = build_alert_targets(
                _asset_canon, _asset_type_ui,
                st.session_state.calc_selected_series, _board_calc, _levels,
                current_price=_current_price_for_targets)
        except Exception:
            _alert_targets = None

    # G4: рекомендация для калькулятора
    try:
        if _board_calc and _levels.get("found"):
            _strikes_calc = sorted({
                float(x["strike"]) for side_key in ("call", "put")
                for x in (_board_calc.get(side_key) or [])
                if x.get("strike") is not None
            })
            _range_strikes_calc = _calc_range_strikes(
                _levels.get("buy"), _levels.get("sell"), _strikes_calc)

            _alert_info_calc = find_alert_full_info(_asset_canon, _asset_type_ui)
            _checks_calc = get_alert_checks(_asset_canon, _asset_type_ui)
            _sugg_calc = _suggest_strategy(
                buy_check=_checks_calc.get("buy"),
                sell_check=_checks_calc.get("sell"),
                trend=(_alert_info_calc or {}).get("trend", ""),
                wave=(_alert_info_calc or {}).get("wave", ""),
                tendency=(_alert_info_calc or {}).get("tendency", ""),
                range_strikes=_range_strikes_calc,
                iv_zone=None, skew_type=None)

            if _sugg_calc.get("strategy"):
                _at_calc = build_alert_targets(
                    _asset_canon, _asset_type_ui,
                    st.session_state.calc_selected_series,
                    _board_calc, _levels,
                    current_price=_current_price_for_targets)
                _legs_preview_calc = _suggestion_legs(
                    _sugg_calc["strategy"], _at_calc)
                _legs_html = " · ".join(
                    f"{leg['side']} {leg['option']} "
                    f"{_fmt_strike(leg['strike'], _asset_type_ui)}×{leg['qty']}"
                    for leg in _legs_preview_calc
                    if leg.get("strike") is not None)
                st.markdown(
                    f"<div style='padding:10px 14px; border-radius:8px; "
                    f"background:#eef6fb; border-left:4px solid #1e88e5; "
                    f"margin-top:6px; margin-bottom:6px; font-size:.85rem;'>"
                    f"<b>Рекомендация:</b> {_sugg_calc['direction_ui']}<br>"
                    f"<span style='color:#5a6b78; font-size:.8rem;'>"
                    f"{_sugg_calc['rationale']}</span><br>"
                    f"<span style='font-family:Consolas,monospace; "
                    f"font-size:.82rem; color:#1c5a7a;'>{_legs_html}</span>"
                    f"</div>",
                    unsafe_allow_html=True)
    except Exception:
        pass

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
        "alert_targets": _alert_targets,
        "market_price": None,
    }

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
                              if _strike_eq(c.get('strike'), _k)), None)
                _p_iv = next((p.get('volatility') for p in _puts_inj
                              if _strike_eq(p.get('strike'), _k)), None)
                _iv = _c_iv or _p_iv
                _k_val = float(_k)
                _strikes_iv_inj.append({
                    "strike": int(_k_val) if _k_val.is_integer() else _k_val,
                    "iv": float(_iv) if _iv is not None else None,
                })
            _inject["strikes"] = _strikes_iv_inj
        except Exception:
            pass

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
            st.warning("В index.html не найден плейсхолдер — калькулятор отключён.")
            calc_html = None
        else:
            _inject_json = json.dumps(_inject, ensure_ascii=False,
                                      default=str, sort_keys=True)
            _inject_hash = hashlib.md5(_inject_json.encode()).hexdigest()
            _cache_key = f"_calc_html_{_inject_hash}"
            if _cache_key not in st.session_state:
                for _old_k in list(st.session_state.keys()):
                    if (isinstance(_old_k, str) and _old_k.startswith("_calc_html_")
                            and _old_k != _cache_key):
                        st.session_state.pop(_old_k, None)
                st.session_state[_cache_key] = calc_html.replace(
                    HTML_PLACEHOLDER, _inject_json.replace("</", "<\\/"))
            calc_html = st.session_state[_cache_key]

    if calc_html is None:
        st.info("Калькулятор недоступен.")
    else:
        components.html(calc_html, height=1100, scrolling=True)


# ==================================================================
# ============ ВКЛАДКА 2: ДОСКА ОПЦИОНОВ ==========================
# ==================================================================
@st.fragment
def _render_board_tab():
    # (без изменений — полный код из исходного app.py остаётся как есть)
    st.header("Доска опционов и кривая волатильности")

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

    _bc1, _bc2, _bc3 = st.columns([3, 2, 2])
    with _bc1:
        _board_raw_asset = st.text_input(
            "Базовый актив", value=st.session_state.board_asset,
            key="board_asset_input", placeholder="SBER, GAZP, RTS…").strip()
    with _bc2:
        _cat_options = ["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"]
        _cat_idx = (_cat_options.index(st.session_state.board_category)
                    if st.session_state.board_category in _cat_options else 0)
        _board_cat = st.selectbox("Категория БА", _cat_options, index=_cat_idx,
                                   key="board_category_select")
    with _bc3:
        st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        _btn_reload = st.button("Обновить серии", use_container_width=True,
                                 key="board_reload_btn")

    _board_asset = resolve_canonical_asset_code(_board_raw_asset, _board_cat)

    if (_board_asset != st.session_state.board_asset
            or _board_cat != st.session_state.board_category):
        st.session_state.board_asset = _board_asset
        st.session_state.board_category = _board_cat
        st.session_state.board_series_list = []
        st.session_state.board_series_code = ""
        st.session_state.board_expiry = ""
        st.session_state.board_autoloaded_for = (None, None)

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
                if _new_series and not st.session_state.board_series_code:
                    _s_first = sorted(_new_series,
                                       key=lambda x: x.get("expiry", ""))[0]
                    st.session_state.board_series_code = _s_first["code"]
                    st.session_state.board_expiry = _s_first["expiry"]
                if not _new_series:
                    st.warning(f"ISS не вернул серий для {_board_asset}")
            except Exception as e:
                st.error(f"Ошибка загрузки серий: {e}")
                st.session_state.board_series_list = []

    st.markdown("---")

    if not st.session_state.board_series_list:
        st.info("Нет доступных серий.")
        return

    st.markdown(f"### Все серии опционов {_board_asset} ({_board_cat.lower()})")

    try:
        _df_overview = fetch_series_overview(_board_asset, _board_cat)
    except Exception as _e:
        _df_overview = pd.DataFrame()
        st.warning(f"Не удалось загрузить сводку серий: {_e}")

    if not _df_overview.empty:
        _cols_to_drop = [c for c in ("_series_code", "_expiry_raw", "_days_to",
                                      "_series_type") if c in _df_overview.columns]
        _df_show = _df_overview.drop(columns=_cols_to_drop)
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
            _df_styler, use_container_width=True, hide_index=True,
            height=min(120 + 35 * len(_df_show), 420),
            on_select="rerun", selection_mode="single-row",
            key="series_overview_table")

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
                if _new_code != st.session_state.board_series_code:
                    st.session_state.board_series_code = _new_code
                    st.session_state.board_expiry = _new_expiry
                    st.rerun()

    st.markdown("---")

    _active_series_code = st.session_state.board_series_code
    _active_expiry = st.session_state.board_expiry

    if not _active_series_code:
        st.info("Выберите серию из таблицы выше.")
        return

    st.markdown(f"### Доска опционов — {_board_asset} "
                f"(дата исполнения: {format_series_label(_active_expiry)})")

    # G4: рекомендация + toggle фильтра
    _sugg_board = None
    _alert_targets_board = None
    _board_for_sugg = None
    try:
        try:
            _board_for_sugg = fetch_optionboard(
                _board_asset, _board_cat, _active_series_code)
        except Exception:
            _board_for_sugg = None

        if _board_for_sugg:
            _strikes_sugg = sorted({
                float(x["strike"]) for side_key in ("call", "put")
                for x in (_board_for_sugg.get(side_key) or [])
                if x.get("strike") is not None
            })
            _lvl_sugg = find_alert_levels(_board_asset, _board_cat)
            _cp_sugg = _get_current_market_price_for_asset(
                _board_asset, _board_cat)
            _range_strikes_sugg = _calc_range_strikes(
                _lvl_sugg.get("buy"), _lvl_sugg.get("sell"), _strikes_sugg)
            _alert_info_sugg = find_alert_full_info(_board_asset, _board_cat)
            _checks_board = get_alert_checks(_board_asset, _board_cat)
            _sugg_board = _suggest_strategy(
                buy_check=_checks_board.get("buy"),
                sell_check=_checks_board.get("sell"),
                trend=(_alert_info_sugg or {}).get("trend", ""),
                wave=(_alert_info_sugg or {}).get("wave", ""),
                tendency=(_alert_info_sugg or {}).get("tendency", ""),
                range_strikes=_range_strikes_sugg,
                iv_zone=None, skew_type=None)

            if _sugg_board.get("strategy"):
                _alert_targets_board = build_alert_targets(
                    _board_asset, _board_cat, _active_series_code,
                    _board_for_sugg, _lvl_sugg, current_price=_cp_sugg)
    except Exception:
        _sugg_board = None

    _filter_by_sugg = False
    _sugg_strikes_set = set()
    if _sugg_board and _sugg_board.get("strategy") and _alert_targets_board:
        _legs_board = _suggestion_legs(
            _sugg_board["strategy"], _alert_targets_board)
        _sugg_strikes_set = {
            leg["strike"] for leg in _legs_board
            if leg.get("strike") is not None
        }

        _fc1, _fc2 = st.columns([3, 2])
        with _fc1:
            st.markdown(
                f"<div style='padding:10px 14px; border-radius:8px; "
                f"background:#eef6fb; border-left:4px solid #1e88e5; "
                f"font-size:.85rem;'>"
                f"<b>Рекомендация:</b> {_sugg_board['direction_ui']}<br>"
                f"<span style='color:#5a6b78; font-size:.8rem;'>"
                f"{_sugg_board['rationale']}</span></div>",
                unsafe_allow_html=True)
        with _fc2:
            _filter_by_sugg = st.toggle(
                "Показать только страйки под конструкцию",
                value=False,
                key="board_filter_by_sugg")

    _rvi_board_data = fetch_rvi_current()
    _rvi_board_val = _rvi_board_data.get("value") if _rvi_board_data else None

    if _rvi_board_val is not None:
        _rvi_b_chg = _rvi_board_data.get("change") or 0.0
        st.markdown(
            f"<div style='background:#f0f4f8; border-radius:8px; "
            f"padding:8px 14px; margin-bottom:6px; margin-top:6px; "
            f"font-size:.9rem;'>"
            f"<b>RVI (рыночный фон):</b> "
            f"<b>{_rvi_board_val:.2f}%</b> "
            f"({_rvi_b_chg:+.2f} п.п.) — "
            f"IV на доске сравнивается с этим уровнем"
            f"</div>",
            unsafe_allow_html=True)

        st.markdown(
            "<div style='background:#ffffff; border:1px solid #cfdfe9; "
            "border-radius:8px; padding:8px 14px; margin-bottom:12px; "
            "font-size:.82rem; display:flex; gap:18px; flex-wrap:wrap; "
            "align-items:center;'>"
            "<span style='color:#4a6f8a; font-weight:700;'>"
            "Легенда IV (IV / RVI):</span>"
            "<span><b style='color:#d32f2f;'>&gt; 2.0</b> "
            "<span style='color:#5a6b78;'>— продавать волатильность</span></span>"
            "<span><b style='color:#e6a500;'>1.5 … 2.0</b> "
            "<span style='color:#5a6b78;'>— осторожно</span></span>"
            "<span><b style='color:#7a7a7a;'>0.7 … 1.5</b> "
            "<span style='color:#5a6b78;'>— норма</span></span>"
            "<span><b style='color:#00a651;'>0.5 … 0.7</b> "
            "<span style='color:#5a6b78;'>— покупать волатильность</span></span>"
            "<span><b style='color:#1e88e5;'>&lt; 0.5</b> "
            "<span style='color:#5a6b78;'>— покупать (дёшево)</span></span>"
            "</div>",
            unsafe_allow_html=True)

    _board_levels = find_alert_levels(_board_asset, category=_board_cat)
    _board_buy_level = float(_board_levels["buy"] or 0) if _board_levels["found"] else 0.0
    _board_sell_level = float(_board_levels["sell"] or 0) if _board_levels["found"] else 0.0

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
                f"Центральный страйк: <b>{_fmt_strike(_central_p, _board_cat)}</b></span>")
        if _k_min is not None and _k_max is not None:
            _info_parts.append(
                f"<span style='color:#4a6f8a;'>"
                f"Диапазон страйков: <b>{_fmt_strike(_k_min, _board_cat)} … "
                f"{_fmt_strike(_k_max, _board_cat)}</b> "
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

        _all_gammas = []
        _all_vegas  = []
        for _k in strikes:
            for _src in (c_map.get(_k, {}), p_map.get(_k, {})):
                _g = _src.get("gamma")
                _v = _src.get("vega")
                if isinstance(_g, (int, float)) and _g > 0:
                    _all_gammas.append(abs(float(_g)))
                if isinstance(_v, (int, float)) and _v > 0:
                    _all_vegas.append(abs(float(_v)))
        _median_gamma = float(np.median(_all_gammas)) if _all_gammas else 0.0
        _median_vega  = float(np.median(_all_vegas))  if _all_vegas  else 0.0

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

        if _filter_by_sugg and _sugg_strikes_set:
            df = df[df["Strike"].isin(_sugg_strikes_set)].reset_index(drop=True)
            if df.empty:
                st.warning("Под рекомендованную конструкцию не найдено страйков")
                return

        def _greek_signal_color(greek_name, row, side, buy_active, sell_active):
            _COL_BUY  = "#9c00ff"
            _COL_SELL = "#fb92f0"
            _key_map = {"delta": "Delta", "gamma": "Gamma",
                        "vega": "Vega", "theta": "Theta"}
            _col_key = f"{side}_{_key_map.get(greek_name, '')}"
            _v = row.get(_col_key)
            if _v is None:
                return None
            try:
                _va = abs(float(_v))
            except (TypeError, ValueError):
                return None

            if greek_name == "delta":
                if buy_active and 0.20 <= _va <= 0.45:
                    return _COL_BUY
                if sell_active and 0.45 <= _va <= 0.70:
                    return _COL_SELL
                return None
            if greek_name == "gamma":
                if buy_active and _median_gamma > 0 and _va >= 1.5 * _median_gamma:
                    return _COL_BUY
                return None
            if greek_name == "vega":
                if _median_vega <= 0:
                    return None
                if buy_active and _va >= 1.2 * _median_vega:
                    return _COL_BUY
                if sell_active and _va <= 0.8 * _median_vega:
                    return _COL_SELL
                return None
            if greek_name == "theta":
                _vv = row.get(f"{side}_Vega")
                if _vv is None:
                    return None
                try:
                    _vva = abs(float(_vv))
                except (TypeError, ValueError):
                    return None
                if _vva < 1e-9:
                    return None
                _ratio = _va / _vva
                if buy_active and _ratio <= 0.7:
                    return _COL_BUY
                if sell_active and _ratio >= 1.2:
                    return _COL_SELL
                return None
            return None

        def _bid_offer_color(price, theor, is_bid):
            if price is None or theor is None:
                return None
            if not isinstance(price, (int, float)) or not isinstance(theor, (int, float)):
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
                    style = f"background-color: {call_bg};"
                elif col.startswith("Put_"):
                    style = f"background-color: {put_bg};"
                if col == "Strike":
                    if is_sell_strike:
                        style = "background-color: #fb92f0; color: white; font-weight: bold"
                    elif is_buy_strike:
                        style = "background-color: #9c00ff; color: white; font-weight: bold"
                    elif is_central:
                        style = "background-color: #e3e7ec; font-weight: bold"
                elif col == "IV_%":
                    if is_central:
                        style = "background-color: #e3e7ec; font-weight: bold"
                    else:
                        _iv_val = row.get("IV_%")
                        if _iv_val is not None and _rvi_board_val:
                            try:
                                _iv_f = float(_iv_val)
                                _zone = classify_iv_vs_rvi(_iv_f, _rvi_board_val)
                            except (TypeError, ValueError):
                                _zone = None
                            if _zone and _zone.get("zone") != "normal":
                                _zcolor = _zone.get("zone_color", "")
                                if _zcolor:
                                    style = (style
                                             + f" color: {_zcolor};"
                                             + " font-weight: 700;")

                if highlight_on:
                    try:
                        _c_val = float(central) if central is not None else None
                    except (TypeError, ValueError):
                        _c_val = None
                    _is_atm = (_c_val is not None and abs(strike - _c_val) < 0.01)

                    if col in ("Call_Bid", "Put_Bid"):
                        if _c_val is None or _is_atm:
                            _allow_bid = True
                        else:
                            _allow_bid = strike > _c_val
                        if _allow_bid:
                            theor_col = ("Call_Theor" if col.startswith("Call_") else "Put_Theor")
                            c = _bid_offer_color(row[col], row.get(theor_col), is_bid=True)
                            if c:
                                style = f"background-color: {c}; color: white; font-weight: 700"
                    elif col in ("Call_Offer", "Put_Offer"):
                        if _c_val is None or _is_atm:
                            _allow_offer = True
                        else:
                            _allow_offer = strike < _c_val
                        if _allow_offer:
                            theor_col = ("Call_Theor" if col.startswith("Call_") else "Put_Theor")
                            c = _bid_offer_color(row[col], row.get(theor_col), is_bid=False)
                            if c:
                                style = f"background-color: {c}; color: white; font-weight: 700"
                    elif col in ("Call_Delta", "Call_Gamma", "Call_Vega", "Call_Theta",
                                 "Put_Delta",  "Put_Gamma",  "Put_Vega",  "Put_Theta"):
                        _g_side = "Call" if col.startswith("Call_") else "Put"
                        _g_name = col.split("_", 1)[1].lower()
                        if _g_side == "Call":
                            _theor = row.get("Call_Theor")
                            _bid_val = row.get("Call_Bid")
                            _off_val = row.get("Call_Offer")
                        else:
                            _theor = row.get("Put_Theor")
                            _bid_val = row.get("Put_Bid")
                            _off_val = row.get("Put_Offer")
                        _buy_a = (_off_val is not None
                                  and _bid_offer_color(_off_val, _theor, is_bid=False) is not None
                                  and (_c_val is None or _is_atm or strike < _c_val))
                        _sell_a = (_bid_val is not None
                                   and _bid_offer_color(_bid_val, _theor, is_bid=True) is not None
                                   and (_c_val is None or _is_atm or strike > _c_val))
                        if _buy_a or _sell_a:
                            _gc = _greek_signal_color(_g_name, row, _g_side, _buy_a, _sell_a)
                            if _gc:
                                style = f"background-color: {_gc}; color: white; font-weight: 700"

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
            caption_extra += f" · страйк покупок ≈ {_fmt_strike(buy_strike_match, _board_cat)}"
        if sell_strike_match is not None:
            caption_extra += f" · страйк продаж ≈ {_fmt_strike(sell_strike_match, _board_cat)}"
        st.caption(f"Центральный страйк: "
                   f"{_fmt_strike(central, _board_cat) if central is not None else 'не определён'} · "
                   f"всего страйков: {len(df)}{caption_extra}")

        if "board_view_mode" not in st.session_state:
            st.session_state.board_view_mode = "Таблица"
        _view_mode_board = st.radio(
            "Вид доски",
            ["Таблица", "Карточки (мобильный)"],
            index=(0 if st.session_state.board_view_mode == "Таблица" else 1),
            horizontal=True,
            key="board_view_mode_radio",
            label_visibility="collapsed")
        st.session_state.board_view_mode = _view_mode_board

        _format_map = {
            "Strike": "{:.2f}",
            "IV_%": "{:.2f}",
            "Call_Rho": "{:.2f}", "Call_Theta": "{:.2f}",
            "Call_Vega": "{:.2f}", "Call_Gamma": "{:.2f}",
            "Call_Delta": "{:.2f}", "Call_Theor": "{:.2f}",
            "Call_Last": "{:.2f}", "Call_Offer": "{:.2f}",
            "Call_Bid": "{:.2f}",
            "Put_Bid": "{:.2f}", "Put_Offer": "{:.2f}",
            "Put_Last": "{:.2f}", "Put_Theor": "{:.2f}",
            "Put_Delta": "{:.2f}", "Put_Gamma": "{:.2f}",
            "Put_Vega": "{:.2f}", "Put_Theta": "{:.2f}",
            "Put_Rho": "{:.2f}",
        }

        if st.session_state.board_view_mode == "Карточки (мобильный)":
            # (карточки доски — без изменений, полный код из исходника)
            _is_atm = None
            if central is not None:
                try:
                    _is_atm = float(central)
                except (TypeError, ValueError):
                    _is_atm = None

            def _fmt_p(v):
                if v is None:
                    return "—"
                try:
                    return f"{float(v):.2f}"
                except (TypeError, ValueError):
                    return "—"

            def _fmt_g(v):
                if v is None:
                    return "—"
                try:
                    return f"{float(v):+.2f}"
                except (TypeError, ValueError):
                    return "—"

            def _greek_cls(gname, side, buy_active, sell_active, row_dict):
                _key_map = {"delta": "Delta", "gamma": "Gamma",
                            "vega": "Vega", "theta": "Theta"}
                _col = f"{side}_{_key_map.get(gname, '')}"
                _v = row_dict.get(_col)
                if _v is None:
                    return ""
                try:
                    _va = abs(float(_v))
                except (TypeError, ValueError):
                    return ""
                _BUY = "#9c00ff"
                _SELL = "#fb92f0"
                if gname == "delta":
                    if buy_active and 0.20 <= _va <= 0.45:
                        return _BUY
                    if sell_active and 0.45 <= _va <= 0.70:
                        return _SELL
                    return ""
                if gname == "gamma":
                    if buy_active and _median_gamma > 0 and _va >= 1.5 * _median_gamma:
                        return _BUY
                    return ""
                if gname == "vega":
                    if _median_vega <= 0:
                        return ""
                    if buy_active and _va >= 1.2 * _median_vega:
                        return _BUY
                    if sell_active and _va <= 0.8 * _median_vega:
                        return _SELL
                    return ""
                if gname == "theta":
                    _vv = row_dict.get(f"{side}_Vega")
                    if _vv is None:
                        return ""
                    try:
                        _vva = abs(float(_vv))
                    except (TypeError, ValueError):
                        return ""
                    if _vva < 1e-9:
                        return ""
                    _r = _va / _vva
                    if buy_active and _r <= 0.7:
                        return _BUY
                    if sell_active and _r >= 1.2:
                        return _SELL
                    return ""
                return ""

            for _idx_card, _row_card in df.iterrows():
                _rd = _row_card.to_dict()
                _k_val = _rd.get("Strike")
                _is_central = (_is_atm is not None
                               and _k_val is not None
                               and abs(float(_k_val) - _is_atm) < 0.01)
                _is_buy_strike = (buy_strike_match is not None
                                  and _k_val is not None
                                  and abs(float(_k_val) - float(buy_strike_match)) < 0.01)
                _is_sell_strike = (sell_strike_match is not None
                                   and _k_val is not None
                                   and abs(float(_k_val) - float(sell_strike_match)) < 0.01)

                _theor_c = _rd.get("Call_Theor")
                _bid_c = _rd.get("Call_Bid")
                _off_c = _rd.get("Call_Offer")
                _theor_p = _rd.get("Put_Theor")
                _bid_p = _rd.get("Put_Bid")
                _off_p = _rd.get("Put_Offer")

                _is_atm_val = (_is_atm is not None
                               and _k_val is not None
                               and abs(float(_k_val) - _is_atm) < 0.01)

                _buy_c = (_off_c is not None
                          and _bid_offer_color(_off_c, _theor_c, is_bid=False) is not None
                          and (_is_atm is None or _is_atm_val or float(_k_val) < _is_atm))
                _sell_c = (_bid_c is not None
                           and _bid_offer_color(_bid_c, _theor_c, is_bid=True) is not None
                           and (_is_atm is None or _is_atm_val or float(_k_val) > _is_atm))
                _buy_p = (_off_p is not None
                          and _bid_offer_color(_off_p, _theor_p, is_bid=False) is not None
                          and (_is_atm is None or _is_atm_val or float(_k_val) < _is_atm))
                _sell_p = (_bid_p is not None
                           and _bid_offer_color(_bid_p, _theor_p, is_bid=True) is not None
                           and (_is_atm is None or _is_atm_val or float(_k_val) > _is_atm))

                if _is_sell_strike:
                    _k_bg = "#fb92f0"
                    _k_fg = "white"
                elif _is_buy_strike:
                    _k_bg = "#9c00ff"
                    _k_fg = "white"
                elif _is_central:
                    _k_bg = "#e3e7ec"
                    _k_fg = "#111"
                else:
                    _k_bg = "#f6f9fc"
                    _k_fg = "#111"

                _k_disp = _fmt_strike(_k_val, _board_cat)
                _iv_val = _rd.get("IV_%")
                _iv_str = f"{float(_iv_val):.2f}%" if _iv_val is not None else "—"

                with st.container(border=True):
                    _hdr1, _hdr2 = st.columns([1, 2])
                    with _hdr1:
                        st.markdown(
                            f"<div style='background:{_k_bg}; color:{_k_fg}; "
                            f"padding:8px 12px; border-radius:6px; "
                            f"font-size:1.1rem; font-weight:800; "
                            f"text-align:center;'>"
                            f"{_k_disp}</div>",
                            unsafe_allow_html=True)
                    with _hdr2:
                        st.markdown(
                            f"<div style='font-size:.85rem; padding-top:4px;'>"
                            f"<b>IV:</b> {_iv_str}<br>"
                            f"<b>Call:</b> {_rd.get('Call_Ticker', '—')} · "
                            f"<b>Put:</b> {_rd.get('Put_Ticker', '—')}</div>",
                            unsafe_allow_html=True)

                    _cc, _cp = st.columns(2)
                    with _cc:
                        _c_bg = "#e1e3fb" if _is_central else "#dbf3df"
                        st.markdown(
                            f"<div style='background:{_c_bg}; "
                            f"padding:6px 10px; border-radius:6px 6px 0 0; "
                            f"font-weight:700; color:#00a651; "
                            f"font-size:.85rem;'>CALL</div>",
                            unsafe_allow_html=True)
                        _cbid_col = _bid_offer_color(_bid_c, _theor_c, is_bid=True)
                        _coff_col = _bid_offer_color(_off_c, _theor_c, is_bid=False)
                        _cbid_style = (f"background-color:{_cbid_col}; color:white; "
                                        f"font-weight:700;" if _cbid_col else "")
                        _coff_style = (f"background-color:{_coff_col}; color:white; "
                                        f"font-weight:700;" if _coff_col else "")
                        st.markdown(
                            f"<div style='font-size:.82rem; line-height:1.6;'>"
                            f"Bid: <b style='{_cbid_style}'>{_fmt_p(_bid_c)}</b> · "
                            f"Offer: <b style='{_coff_style}'>{_fmt_p(_off_c)}</b><br>"
                            f"Last: <b>{_fmt_p(_rd.get('Call_Last'))}</b> · "
                            f"Theor: <b>{_fmt_p(_theor_c)}</b></div>",
                            unsafe_allow_html=True)

                        def _g_cell(name, active_buy, active_sell):
                            _col = _greek_cls(name, "Call",
                                               active_buy, active_sell, _rd)
                            _val = _rd.get(f"Call_{name.capitalize()}")
                            _style = (f"background-color:{_col}; color:white; "
                                       f"font-weight:700;" if _col else "")
                            return f"<span style='{_style}'>{_fmt_g(_val)}</span>"

                        st.markdown(
                            f"<div style='font-size:.78rem; margin-top:4px; "
                            f"line-height:1.7;'>"
                            f"Δ: {_g_cell('delta', _buy_c, _sell_c)} "
                            f"Γ: {_g_cell('gamma', _buy_c, _sell_c)} "
                            f"ν: {_g_cell('vega', _buy_c, _sell_c)} "
                            f"Θ: {_g_cell('theta', _buy_c, _sell_c)}"
                            f"</div>",
                            unsafe_allow_html=True)

                    with _cp:
                        _p_bg = "#fee5cd" if _is_central else "#ffcdce"
                        st.markdown(
                            f"<div style='background:{_p_bg}; "
                            f"padding:6px 10px; border-radius:6px 6px 0 0; "
                            f"font-weight:700; color:#d32f2f; "
                            f"font-size:.85rem;'>PUT</div>",
                            unsafe_allow_html=True)
                        _pbid_col = _bid_offer_color(_bid_p, _theor_p, is_bid=True)
                        _poff_col = _bid_offer_color(_off_p, _theor_p, is_bid=False)
                        _pbid_style = (f"background-color:{_pbid_col}; color:white; "
                                        f"font-weight:700;" if _pbid_col else "")
                        _poff_style = (f"background-color:{_poff_col}; color:white; "
                                        f"font-weight:700;" if _poff_col else "")
                        st.markdown(
                            f"<div style='font-size:.82rem; line-height:1.6;'>"
                            f"Bid: <b style='{_pbid_style}'>{_fmt_p(_bid_p)}</b> · "
                            f"Offer: <b style='{_poff_style}'>{_fmt_p(_off_p)}</b><br>"
                            f"Last: <b>{_fmt_p(_rd.get('Put_Last'))}</b> · "
                            f"Theor: <b>{_fmt_p(_theor_p)}</b></div>",
                            unsafe_allow_html=True)

                        def _g_cell_p(name, active_buy, active_sell):
                            _col = _greek_cls(name, "Put",
                                               active_buy, active_sell, _rd)
                            _val = _rd.get(f"Put_{name.capitalize()}")
                            _style = (f"background-color:{_col}; color:white; "
                                       f"font-weight:700;" if _col else "")
                            return f"<span style='{_style}'>{_fmt_g(_val)}</span>"

                        st.markdown(
                            f"<div style='font-size:.78rem; margin-top:4px; "
                            f"line-height:1.7;'>"
                            f"Δ: {_g_cell_p('delta', _buy_p, _sell_p)} "
                            f"Γ: {_g_cell_p('gamma', _buy_p, _sell_p)} "
                            f"ν: {_g_cell_p('vega', _buy_p, _sell_p)} "
                            f"Θ: {_g_cell_p('theta', _buy_p, _sell_p)}"
                            f"</div>",
                            unsafe_allow_html=True)
        else:
            st.dataframe(
                df.style.apply(style_row, axis=1).format(
                    _format_map, precision=2, na_rep="—"),
                column_config=column_display,
                use_container_width=True, height=600)

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
            if _rvi_board_val is not None:
                fig.add_hline(
                    y=_rvi_board_val,
                    line=dict(color="#d32f2f", width=2, dash="dash"),
                    annotation_text=f"RVI = {_rvi_board_val:.2f}%",
                    annotation_position="top right",
                    annotation_font_color="#d32f2f")
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
    # [PATCH 1] Старый expander «Полный кеш (экспорт/импорт всех данных)»
    # УДАЛЁН — резервная копия теперь доступна вне вкладки «Позиция»
    # через _render_backup_controls() (см. диспетчер вкладок в конце файла).

    st.header("Управление позицией")

    # [PATCH 4] Сохраняем состояние предыдущего рендера до переключения
    # актива. Это также фиксирует удаление последней позиции.
    _active_key_to_sync = st.session_state.get("_pos_active_key")

    if _active_key_to_sync and "positions" in st.session_state:
        _current_positions = st.session_state["positions"]
        _signature = _positions_signature(_current_positions)

        if _signature != st.session_state.get("_pos_signature"):
            _cache = dict(st.session_state.get("positions_cache", {}))
            _cache[_active_key_to_sync] = _backup_clean(_current_positions)

            st.session_state["positions_cache"] = _cache
            _save_cache(_cache)
            st.session_state["_pos_signature"] = _signature

    if _IS_CLOUD:
        st.info(
            "☁️ **Streamlit Cloud:** файловый кеш отключён. Позиции "
            "живут только в текущей сессии. Для сохранения между "
            "сессиями — используйте **«Резервная копия · JSON»** "
            "вверху страницы.")

    # [PATCH 5] Начальный вид карточек на мобильных.
    if "pos_view_mode" not in st.session_state:
        st.session_state.pos_view_mode = "Карточки (мобильный)"

    _view_mode_pos = st.radio(
        "Вид позиций",
        ["Таблица", "Карточки (мобильный)"],
        index=0 if st.session_state.pos_view_mode == "Таблица" else 1,
        horizontal=True,
        key="pos_view_mode_radio",
        label_visibility="collapsed")
    st.session_state.pos_view_mode = _view_mode_pos

    if "pos_asset" not in st.session_state:
        st.session_state.pos_asset = st.session_state.get("board_asset", "SBER")
    if "pos_category" not in st.session_state:
        st.session_state.pos_category = st.session_state.get("board_category", "Акция")
    if "pos_series_list" not in st.session_state:
        st.session_state.pos_series_list = []
    if "pos_series_code" not in st.session_state:
        st.session_state.pos_series_code = ""
    if "pos_expiry" not in st.session_state:
        st.session_state.pos_expiry = ""
    if "pos_autoloaded_for" not in st.session_state:
        st.session_state.pos_autoloaded_for = (None, None)

    _pc1, _pc2 = st.columns([3, 2])
    with _pc1:
        _pos_raw_asset = st.text_input(
            "Базовый актив (для позиции)",
            value=st.session_state.pos_asset,
            key="pos_asset_input",
            placeholder="SBER, GAZP, RTS…",
        ).strip()
    with _pc2:
        _pos_cat_opts = ["Акция", "Фьючерс", "Валюта", "Товар", "Индекс"]
        _pos_cat_idx = (_pos_cat_opts.index(st.session_state.pos_category)
                        if st.session_state.pos_category in _pos_cat_opts else 0)
        _pos_cat = st.selectbox(
            "Категория БА",
            _pos_cat_opts,
            index=_pos_cat_idx,
            key="pos_category_select",
        )

    _pos_asset = resolve_canonical_asset_code(_pos_raw_asset, _pos_cat)

    # Тренд / Волна / Тенденция + расшифровка
    _alert_info_pos = find_alert_full_info(_pos_asset, _pos_cat)
    if _alert_info_pos:
        _pos_triplet = _trend_emoji_triplet(
            _alert_info_pos["trend"],
            _alert_info_pos["wave"],
            _alert_info_pos["tendency"])
        _pos_rec_side, _pos_rec_desc = _get_recommendation(
            _alert_info_pos["trend"],
            _alert_info_pos["wave"],
            _alert_info_pos["tendency"])

        if _pos_triplet:
            _pos_rec_color = ("#00a651" if _pos_rec_side == "CALL"
                              else "#d32f2f" if _pos_rec_side == "PUT"
                              else "#333")
            _pos_rec_badge = ""
            if _pos_rec_side:
                _pos_rec_badge = (
                    f"<span style='padding:2px 12px; border-radius:6px; "
                    f"background:{_pos_rec_color}; color:white; "
                    f"font-weight:700; font-size:.85rem; margin-left:12px; "
                    f"letter-spacing:.05em;'>{_pos_rec_side}</span>")
            _pos_desc_html = ""
            if _pos_rec_desc:
                _pos_desc_html = (
                    f"<div style='margin-top:8px; padding:10px 14px; "
                    f"background:#ffffff; border-radius:8px; "
                    f"border-left:4px solid {_pos_rec_color}; "
                    f"font-size:.85rem; color:#333; line-height:1.45;'>"
                    f"{_pos_rec_desc}</div>")

            st.markdown(
                f"<div style='padding:12px 16px; background:#eef6fb; "
                f"border-radius:10px; border:1px solid #cfdfe9; "
                f"margin-top:8px; margin-bottom:6px;'>"
                f"<div style='display:flex; align-items:center;'>"
                f"<span style='font-size:1.3rem; letter-spacing:2px;'>"
                f"{_pos_triplet}</span>"
                f"{_pos_rec_badge}</div>"
                f"{_pos_desc_html}"
                f"</div>",
                unsafe_allow_html=True)

    # Рекомендация по чек-боксам
    _rec_text = get_alert_recommendation_text(_pos_asset, _pos_cat)
    if _rec_text:
        st.markdown(
            f"<div style='padding:12px 16px; border-radius:10px; "
            f"background:#e8f5e9; border-left:6px solid #00a651; "
            f"margin-top:8px; margin-bottom:6px; font-size:.9rem; color:#0a4d20;'>"
            f"<b>Рекомендация по выбранным чек-боксам:</b><br>"
            f"{_rec_text}</div>",
            unsafe_allow_html=True)

    # G4: баннер рекомендованной конструкции с кнопкой «Применить»
    _sugg_pos = None
    _alert_targets_pos = None
    _board_pos = None
    try:
        if _pos_asset and _pos_cat and st.session_state.get("pos_series_code"):
            try:
                _board_pos = fetch_optionboard(
                    _pos_asset, _pos_cat,
                    st.session_state.pos_series_code)
            except Exception:
                _board_pos = None

            if _board_pos:
                _strikes_pos = sorted({
                    float(x["strike"]) for side_key in ("call", "put")
                    for x in (_board_pos.get(side_key) or [])
                    if x.get("strike") is not None
                })
                _lvl_pos = find_alert_levels(_pos_asset, _pos_cat)
                _cp_pos = _get_current_market_price_for_asset(_pos_asset, _pos_cat)
                _range_strikes_pos = _calc_range_strikes(
                    _lvl_pos.get("buy"), _lvl_pos.get("sell"), _strikes_pos)

                _checks_pos = get_alert_checks(_pos_asset, _pos_cat)
                _sugg_pos = _suggest_strategy(
                    buy_check=_checks_pos.get("buy"),
                    sell_check=_checks_pos.get("sell"),
                    trend=(_alert_info_pos or {}).get("trend", ""),
                    wave=(_alert_info_pos or {}).get("wave", ""),
                    tendency=(_alert_info_pos or {}).get("tendency", ""),
                    range_strikes=_range_strikes_pos,
                    iv_zone=None, skew_type=None)

                if _sugg_pos.get("strategy"):
                    _alert_targets_pos = build_alert_targets(
                        _pos_asset, _pos_cat,
                        st.session_state.pos_series_code,
                        _board_pos, _lvl_pos, current_price=_cp_pos)

                if _sugg_pos.get("strategy") and _alert_targets_pos:
                    _sugg_color = {"high": "#00a651",
                                   "medium": "#e6a500",
                                   "low": "#7a7a7a"}.get(
                        _sugg_pos["confidence"], "#7a7a7a")
                    _legs_preview = _suggestion_legs(
                        _sugg_pos["strategy"], _alert_targets_pos)
                    _legs_lines = "".join(
                        f"<div style='font-size:.82rem; color:#333;'>"
                        f"• {leg['label']}: {leg['side']} {leg['option']} "
                        f"{_fmt_strike(leg['strike'], _pos_cat)}"
                        f" × {leg['qty']}</div>"
                        for leg in _legs_preview
                        if leg.get("strike") is not None)
                    st.markdown(
                        f"<div style='padding:12px 16px; border-radius:10px; "
                        f"background:{_sugg_color}15; "
                        f"border-left:6px solid {_sugg_color}; "
                        f"margin-top:8px; margin-bottom:8px;'>"
                        f"<div style='font-size:1rem; font-weight:800; "
                        f"color:{_sugg_color};'>"
                        f"Рекомендация: {_sugg_pos['direction_ui']}</div>"
                        f"<div style='font-size:.82rem; color:#5a6b78; "
                        f"margin-top:4px;'>{_sugg_pos['rationale']}</div>"
                        f"<div style='margin-top:6px;'>{_legs_lines}</div>"
                        f"</div>",
                        unsafe_allow_html=True)

                    if st.button(
                            f"Применить конструкцию: {_sugg_pos['strategy']}",
                            type="primary",
                            use_container_width=True,
                            key="apply_sugg_strategy_btn"):
                        _created = _apply_suggested_strategy(
                            _sugg_pos["strategy"],
                            _pos_asset, _pos_cat,
                            st.session_state.pos_series_code,
                            st.session_state.pos_expiry,
                            _alert_targets_pos, _board_pos)
                        if _created:
                            for _np in _created:
                                st.session_state.positions.append(_np)
                            _ck_pos = st.session_state.get("_pos_active_key")
                            if _ck_pos:
                                st.session_state.positions_cache[_ck_pos] = list(
                                    st.session_state.positions)
                                _save_cache(st.session_state.positions_cache)
                                st.session_state["_pos_signature"] = \
                                    _positions_signature(st.session_state.positions)
                            st.success(
                                f"Добавлено ног: {len(_created)} "
                                f"({_sugg_pos['strategy']})")
                            st.rerun()
                        else:
                            st.warning(
                                "Не удалось создать позиции — "
                                "проверьте доску/страйки")
    except Exception:
        _sugg_pos = None

    # Кэш позиций
    if "positions_cache" not in st.session_state:
        st.session_state.positions_cache = _load_cache()
    if "positions" not in st.session_state:
        st.session_state.positions = []

    _new_key = f"{_pos_asset}|{_pos_cat}"
    _old_key = st.session_state.get("_pos_active_key")

    if _old_key is None:
        st.session_state["_pos_active_key"] = _new_key
        _cached = st.session_state.positions_cache.get(_new_key, [])
        if _cached and not st.session_state.positions:
            st.session_state.positions = list(_cached)
        else:
            st.session_state.positions_cache.setdefault(
                _new_key, list(st.session_state.positions))
        _save_cache(st.session_state.positions_cache)
        st.session_state["_pos_signature"] = \
            _positions_signature(st.session_state.positions)

    elif _new_key != _old_key:
        st.session_state.positions_cache[_old_key] = list(
            st.session_state.positions)
        st.session_state.positions = list(
            st.session_state.positions_cache.get(_new_key, []))
        st.session_state["_pos_active_key"] = _new_key
        for _k in list(st.session_state.keys()):
            if _k.startswith(("qty_", "price_", "qp_", "qm_",
                              "pp_", "pm_")):
                del st.session_state[_k]
        for _fk in ("form_series", "form_strike", "form_opt_type",
                    "form_side", "form_qty", "form_price",
                    "form_instrument_type", "form_futures_contract",
                    "form_use_auto_price", "fallback_series_selector"):
            st.session_state.pop(_fk, None)
        _save_cache(st.session_state.positions_cache)
        st.session_state["_pos_signature"] = \
            _positions_signature(st.session_state.positions)

    if (_pos_asset != st.session_state.pos_asset
            or _pos_cat != st.session_state.pos_category):
        st.session_state.pos_asset = _pos_asset
        st.session_state.pos_category = _pos_cat
        for _fk in ("form_series", "form_strike", "form_opt_type",
                    "form_side", "form_qty", "form_price",
                    "form_instrument_type", "form_futures_contract",
                    "form_use_auto_price", "fallback_series_selector"):
            st.session_state.pop(_fk, None)

    # G3: миграция r/q + гигиена полей у существующих позиций
    if st.session_state.get("_g3_migrated") is not True:
        try:
            if st.session_state.get("positions"):
                _ck_mig = st.session_state.get("_pos_active_key")
                _parts_mig = (_ck_mig.split("|", 1) if _ck_mig else [None, None])
                _asset_mig = _parts_mig[0] if len(_parts_mig) > 0 else None
                _atype_mig = _parts_mig[1] if len(_parts_mig) > 1 else None
                for _p_mig in st.session_state.positions:
                    if not _p_mig.get("_asset") and _asset_mig:
                        _p_mig["_asset"] = _asset_mig
                    if not _p_mig.get("_atype") and _atype_mig:
                        _p_mig["_atype"] = _atype_mig
                    if _p_mig.get("Тип инструмента") == "Опцион":
                        if "_vol" not in _p_mig or _p_mig.get("_vol") is None:
                            _p_mig["_vol"] = 20.0
                        if "_r" not in _p_mig:
                            _p_mig["_r"] = 0.0
                        if "_q" not in _p_mig:
                            _p_mig["_q"] = 0.0
                    if "_id" not in _p_mig:
                        _p_mig["_id"] = _new_position_id()

                _migrate_positions_r_q(st.session_state.positions)

                if _ck_mig:
                    st.session_state.positions_cache[_ck_mig] = list(
                        st.session_state.positions)
                    _save_cache(st.session_state.positions_cache)
                    st.session_state["_pos_signature"] = \
                        _positions_signature(st.session_state.positions)
            st.session_state["_g3_migrated"] = True
        except Exception:
            pass

    try:
        _iss_code_disp, _iss_type_disp = get_asset_code_and_type(
            _pos_asset, _pos_cat)
        if _iss_code_disp and _iss_code_disp.upper() != _pos_asset.upper():
            st.caption(
                f"Для категории {_pos_cat} запрашивается код "
                f"{_iss_code_disp} (тип: {_iss_type_disp})")
        else:
            st.caption(
                f"Запрос: код {_iss_code_disp} · тип: {_iss_type_disp}")
    except Exception:
        pass

    _cache_path = _cache_file()
    _cache_info = {
        k: len(v) for k, v in st.session_state.positions_cache.items()
        if isinstance(v, list) and len(v) > 0
    }

    _cache_label = (f"Кэш позиций — активов: {len(_cache_info)} · "
                    f"текущий: {_new_key} ({_cache_info.get(_new_key, 0)} шт.)")

    with st.expander(_cache_label, expanded=False):
        if _cache_path is not None:
            st.caption(f"Файл: {_cache_path}")
        else:
            st.caption("Файл недоступен — кэш работает только в памяти.")

        if not _cache_info:
            st.info("Кэш пуст. Собери позицию — она автоматически сохранится.")
        else:
            st.markdown("**Сохранённые активы:**")
            for _ck in sorted(_cache_info.keys()):
                _cn = _cache_info[_ck]
                _is_current = (_ck == _new_key)
                _cc1, _cc2, _cc3 = st.columns([4, 1, 1])
                with _cc1:
                    _mark = "🟢" if _is_current else "⚪"
                    st.markdown(f"{_mark} {_ck} — {_cn} шт.")
                with _cc2:
                    if not _is_current:
                        if st.button("Загрузить",
                                     key=f"pos_cache_load_{_ck}",
                                     use_container_width=True):
                            _cur_active = st.session_state.get("_pos_active_key")
                            if _cur_active:
                                st.session_state.positions_cache[_cur_active] = \
                                    list(st.session_state.positions)
                            _parts = _ck.split("|", 1)
                            if len(_parts) == 2:
                                st.session_state.pos_asset = _parts[0]
                                st.session_state.pos_category = _parts[1]
                                st.session_state["_pos_active_key"] = _ck
                                st.session_state.positions = list(
                                    st.session_state.positions_cache.get(_ck, []))
                                for _k in list(st.session_state.keys()):
                                    if _k.startswith(("qty_", "price_",
                                                      "qp_", "qm_",
                                                      "pp_", "pm_")):
                                        del st.session_state[_k]
                                for _fk in ("form_series", "form_strike",
                                            "form_opt_type", "form_side",
                                            "form_qty", "form_price",
                                            "form_instrument_type",
                                            "form_futures_contract",
                                            "form_use_auto_price",
                                            "fallback_series_selector"):
                                    st.session_state.pop(_fk, None)
                                st.session_state.pos_series_list = []
                                st.session_state.pos_series_code = ""
                                st.session_state.pos_expiry = ""
                                st.session_state.pos_autoloaded_for = (None, None)
                                for _wk in ("pos_asset_input",
                                            "pos_category_select"):
                                    if _wk in st.session_state:
                                        del st.session_state[_wk]
                                st.session_state["_wt_last_asset"] = None
                                st.session_state["_current_market_price"] = None
                                _save_cache(st.session_state.positions_cache)
                                st.session_state["_pos_signature"] = \
                                    _positions_signature(st.session_state.positions)
                                st.rerun()
                with _cc3:
                    if not _is_current:
                        if st.button("Удалить",
                                     key=f"pos_cache_del_{_ck}",
                                     use_container_width=True):
                            st.session_state.positions_cache.pop(_ck, None)
                            _save_cache(st.session_state.positions_cache)
                            st.rerun()

            st.markdown("---")
            _cb1, _cb2 = st.columns(2)
            with _cb1:
                if st.button("Сохранить сейчас",
                             key="pos_cache_save_now",
                             use_container_width=True):
                    st.session_state.positions_cache[_new_key] = \
                        list(st.session_state.positions)
                    _ok = _save_cache(st.session_state.positions_cache)
                    st.session_state["_pos_signature"] = \
                        _positions_signature(st.session_state.positions)
                    if _ok:
                        st.success("Кэш записан на диск")
                    else:
                        st.warning("Не удалось записать файл — кэш только в памяти")
                    st.rerun()
            with _cb2:
                if st.button("Очистить весь кэш",
                             key="pos_cache_clear_all",
                             use_container_width=True,
                             help="Удалить все сохранённые позиции (включая текущую)"):
                    st.session_state.positions_cache = {}
                    st.session_state.positions = []
                    _save_cache({})
                    st.session_state["_pos_signature"] = ""
                    st.success("Кэш очищен")
                    st.rerun()

    _pos_loaded_for = st.session_state.get("pos_autoloaded_for", (None, None))
    if _pos_asset and (_pos_asset, _pos_cat) != _pos_loaded_for:
        with st.spinner(f"Загрузка серий для {_pos_asset}…"):
            try:
                _pos_series_new = fetch_optionseries(_pos_asset, _pos_cat)
                st.session_state.pos_series_list = _pos_series_new or []
                st.session_state.pos_autoloaded_for = (_pos_asset, _pos_cat)
                if _pos_series_new and not st.session_state.pos_series_code:
                    _s_first = sorted(_pos_series_new,
                                       key=lambda x: x.get("expiry", ""))[0]
                    st.session_state.pos_series_code = _s_first["code"]
                    st.session_state.pos_expiry = _s_first["expiry"]
                if not _pos_series_new:
                    st.warning(f"ISS не вернул ни одной серии "
                               f"для {_pos_asset} ({_pos_cat}).")
            except Exception as e:
                st.error(f"Ошибка загрузки серий: {e}")
                st.session_state.pos_series_list = []

    st.markdown("---")

    col_ctrl, col_add = st.columns([1, 1.7], gap="medium")

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
            with st.popover("Импорт портфеля (CSV)", use_container_width=True):
                st.markdown("**Загрузить CSV**")
                _pf_file = st.file_uploader("CSV файл", type=["csv"],
                                              key="pf_csv_inp",
                                              label_visibility="collapsed")
                if _pf_file is not None:
                    try:
                        _pf_df = pd.read_csv(_pf_file)

                        _csv_asset = None
                        _csv_category = None
                        for _colname in ("Актив", "Тикер БА", "База", "Asset"):
                            if _colname in _pf_df.columns:
                                _vals = _pf_df[_colname].dropna().astype(str).unique()
                                if len(_vals) > 0:
                                    _csv_asset = _vals[0].strip()
                                    break
                        for _colname in ("Категория", "Категория БА", "Category"):
                            if _colname in _pf_df.columns:
                                _vals = _pf_df[_colname].dropna().astype(str).unique()
                                if len(_vals) > 0:
                                    _csv_category = _vals[0].strip()
                                    break

                        if _csv_asset:
                            st.info(f"В файле указан актив: {_csv_asset}"
                                    + (f" · Категория: {_csv_category}"
                                       if _csv_category else ""))

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
                                "visible": True,
                                "_asset": (_csv_asset
                                           or st.session_state.get("pos_asset", "")),
                                "_atype": (_csv_category
                                           or st.session_state.get("pos_category", "")),
                            })

                        if st.button("Применить", type="primary", key="pf_apply"):
                            for k in list(st.session_state.keys()):
                                if k.startswith(("qty_", "price_", "qp_", "qm_",
                                                  "pp_", "pm_")):
                                    del st.session_state[k]
                            st.session_state.positions = _imported

                            if _csv_asset:
                                _canon = resolve_canonical_asset_code(
                                    _csv_asset, _csv_category or None)
                                st.session_state.pos_asset = _canon
                            if _csv_category and _csv_category in (
                                    "Акция", "Фьючерс", "Валюта",
                                    "Товар", "Индекс"):
                                st.session_state.pos_category = _csv_category

                            _new_key_csv = (f"{st.session_state.pos_asset}|"
                                            f"{st.session_state.pos_category}")
                            st.session_state["_pos_active_key"] = _new_key_csv
                            st.session_state.positions_cache[_new_key_csv] = list(_imported)
                            _save_cache(st.session_state.positions_cache)

                            st.session_state.pos_series_list = []
                            st.session_state.pos_series_code = ""
                            st.session_state.pos_expiry = ""
                            st.session_state.pos_autoloaded_for = (None, None)

                            for _wk in ("pos_asset_input", "pos_category_select",
                                        "form_series", "form_strike",
                                        "form_opt_type", "form_side",
                                        "form_qty", "form_price",
                                        "form_instrument_type",
                                        "form_futures_contract",
                                        "form_use_auto_price",
                                        "fallback_series_selector"):
                                if _wk in st.session_state:
                                    del st.session_state[_wk]

                            st.session_state["_wt_last_asset"] = None
                            st.session_state["_current_market_price"] = None
                            st.session_state["_g3_migrated"] = False
                            st.session_state["_pos_signature"] = \
                                _positions_signature(st.session_state.positions)

                            st.rerun()
                        st.caption(f"Строк: {len(_imported)}")
                    except Exception as e:
                        st.error(f"Ошибка чтения CSV: {e}")

        risk_amount = deposit * risk_pct / 100.0
        st.caption(f"Доступно для сделки: {risk_amount:,.2f} ₽ "
                   f"({risk_pct}% от {deposit:,.0f} ₽)")

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

    def _sync_qty_to_position(key, pos_id):
        try:
            _new_val = int(st.session_state.get(key, 0))
        except (TypeError, ValueError):
            return
        for _p in st.session_state.get("positions", []):
            if _p.get("_id") == pos_id:
                _p["Кол-во"] = _new_val
                return

    def _sync_price_to_position(key, pos_id):
        try:
            _new_val = float(st.session_state.get(key, 0.0))
        except (TypeError, ValueError):
            return
        if _new_val < 0:
            _new_val = 0.0
        for _p in st.session_state.get("positions", []):
            if _p.get("_id") == pos_id:
                _p["Цена"] = _new_val
                return

    def _cb_qty_dec(key, pos_id):
        st.session_state[key] = int(st.session_state.get(key, 1)) - 1
        _sync_qty_to_position(key, pos_id)

    def _cb_qty_inc(key, pos_id):
        st.session_state[key] = int(st.session_state.get(key, 1)) + 1
        _sync_qty_to_position(key, pos_id)

    def _cb_price_dec(key, pos_id):
        st.session_state[key] = round(max(0.0, float(st.session_state.get(key, 0.0)) - 0.01), 4)
        _sync_price_to_position(key, pos_id)

    def _cb_price_inc(key, pos_id):
        st.session_state[key] = round(float(st.session_state.get(key, 0.0)) + 0.01, 4)
        _sync_price_to_position(key, pos_id)

    def _cb_qty_sync(key, pos_id):
        _sync_qty_to_position(key, pos_id)

    def _cb_price_sync(key, pos_id):
        _sync_price_to_position(key, pos_id)

    def _get_board_price(_strike, _opt_type, _side_internal, _c_map, _p_map):
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

    def _fmt_board_label(_opt_type, _side_internal, _strike, _price,
                         _asset_type=None):
        if _price is None or _price <= 0 or _strike is None:
            return "—"
        _sign = "+" if _side_internal == "Buy" else "-"
        _letter = "C" if _opt_type == "Call" else "P"
        _k_str = _fmt_strike(_strike, _asset_type)
        _p_str = f"{_price:.4f}".replace('.', ',')
        return f"{_sign}{_letter}{_k_str} {_p_str}"

    with col_add:
        st.markdown("#### Добавить позицию")

        _flash = st.session_state.pop("_position_add_flash", None)
        if _flash:
            if _flash.get("errors"):
                st.markdown(
                    "<div style='padding:10px 14px; border-radius:8px; "
                    "background:#ffebee; border-left:4px solid #d32f2f; "
                    "font-size:.85rem; color:#8b1e1e; margin-bottom:8px;'>"
                    "<b>Позиция добавлена с замечаниями:</b><br>"
                    + "<br>".join(f"• {_e}" for _e in _flash["errors"])
                    + "</div>",
                    unsafe_allow_html=True)
            if _flash.get("warnings"):
                st.markdown(
                    "<div style='padding:8px 12px; border-radius:8px; "
                    "background:#fff3e0; border-left:4px solid #e6a500; "
                    "font-size:.82rem; color:#8a6500; margin-bottom:8px;'>"
                    + "<br>".join(f"• {_w}" for _w in _flash["warnings"])
                    + "</div>",
                    unsafe_allow_html=True)
            if _flash.get("message"):
                st.success(_flash["message"])

        if "positions" not in st.session_state:
            st.session_state.positions = []

        _asset_now_all = st.session_state.get("pos_asset", "")
        _atype_now_all = st.session_state.get("pos_category", "")
        _series_now = st.session_state.get("pos_series_code", "")
        _expiry_now = st.session_state.get("pos_expiry", "")

        if not (_asset_now_all and _atype_now_all):
            st.warning("Сначала выберите базовый актив и категорию в блоке выше.")
        else:
            _all_series = []
            try:
                _all_series = fetch_all_series_for_asset(_asset_now_all, _atype_now_all) or []
            except Exception:
                _all_series = []
            if not _all_series:
                _all_series = st.session_state.get("pos_series_list", []) or []

            if not _all_series:
                st.error(
                    f"Не удалось получить опционные серии "
                    f"для {_asset_now_all} ({_atype_now_all})."
                )
                try:
                    _iss_code_dbg, _iss_type_dbg = get_asset_code_and_type(
                        _asset_now_all, _atype_now_all)
                    st.caption(
                        f"В ISS отправлялся запрос: код {_iss_code_dbg}, "
                        f"тип {_iss_type_dbg}"
                    )
                    if (_atype_now_all == "Фьючерс"
                            and _iss_code_dbg == _asset_now_all.upper()):
                        st.info(
                            "Похоже, для этого тикера alias не задан. "
                            "Попробуйте ввести код фьючерса напрямую: "
                            "GAZR (для Газпрома), SBRF (Сбер), "
                            "SBPR (Сбер-п), MTSI (МТС), "
                            "SNGR / SNGP (Сургут), TRNF (Транснефть)."
                        )
                except Exception:
                    pass
            else:
                _all_series_codes = {s["code"] for s in _all_series}
                if not _series_now or _series_now not in _all_series_codes:
                    _first = sorted(_all_series, key=lambda x: x.get("expiry", ""))[0]
                    st.session_state.pos_series_code = _first["code"]
                    st.session_state.pos_expiry = _first["expiry"]
                    _series_now = _first["code"]
                    _expiry_now = _first["expiry"]

                _series_labels = [format_series_label(s["expiry"]) for s in _all_series]
                _series_by_label = {lab: s for lab, s in zip(_series_labels, _all_series)}

                _default_series_idx = 0
                for i, s in enumerate(_all_series):
                    if s.get("code") == _series_now:
                        _default_series_idx = i
                        break

                _board_load_err = None
                try:
                    board = fetch_optionboard(_asset_now_all, _atype_now_all, _series_now)
                except Exception as e:
                    _board_load_err = str(e)
                    board = None

                if _board_load_err:
                    st.error(
                        f"Не удалось загрузить доску для серии "
                        f"{_series_now} (эксп. {_expiry_now})."
                    )
                    with st.expander("Подробнее", expanded=False):
                        st.code(_board_load_err)
                        st.caption(
                            f"Актив: {_asset_now_all} · "
                            f"Категория: {_atype_now_all} · "
                            f"Серия: {_series_now}"
                        )

                    st.markdown("**Попробуйте выбрать другую серию:**")
                    _fallback_label = st.selectbox(
                        "Серия опционов",
                        _series_labels,
                        index=_default_series_idx,
                        key="fallback_series_selector")
                    if st.button("Переключиться на эту серию",
                                  key="fallback_series_btn",
                                  type="primary"):
                        _fb = _series_by_label[_fallback_label]
                        st.session_state.pos_series_code = _fb["code"]
                        st.session_state.pos_expiry = _fb["expiry"]
                        st.session_state.pop("form_series", None)
                        st.session_state.pop("form_strike", None)
                        st.rerun()

                if not board:
                    st.error(
                        f"⚠️ Форма добавления недоступна: доска опционов "
                        f"не загружена для {_asset_now_all} ({_atype_now_all}), "
                        f"серия {_series_now}.")
                    with st.expander("Диагностика", expanded=False):
                        st.json({
                            "pos_asset": _asset_now_all,
                            "pos_category": _atype_now_all,
                            "pos_series_code": _series_now,
                            "pos_expiry": _expiry_now,
                            "all_series_count": len(_all_series),
                            "all_series_codes_first5":
                                [s["code"] for s in _all_series[:5]],
                            "board_load_err": _board_load_err,
                            "is_cloud": _IS_CLOUD,
                        })
                        if st.button("Сбросить серию и попробовать снова",
                                      key=f"reset_series_{_asset_now_all}"):
                            st.session_state.pos_series_code = ""
                            st.session_state.pos_autoloaded_for = (None, None)
                            try:
                                fetch_optionboard.clear()
                            except Exception:
                                pass
                            st.rerun()

                if board:
                    calls = board.get('call') or []
                    puts = board.get('put') or []
                    central = board.get('central_strike')
                    c_map = {c['strike']: c for c in calls if c.get('strike') is not None}
                    p_map = {p['strike']: p for p in puts if p.get('strike') is not None}
                    all_strikes = sorted(set(c_map.keys()) | set(p_map.keys()))
                    asset_type_ui_now = _atype_now_all
                    asset_now = _asset_now_all

                    _instr_options = ["Опцион"]
                    if asset_type_ui_now in ("Фьючерс", "Валюта", "Товар"):
                        _instr_options.append("Фьючерс")
                    elif asset_type_ui_now == "Акция":
                        _instr_options.append("Акция")
                    else:
                        _instr_options.append("Индекс")

                    with st.container(border=True):
                        instrument_type = st.selectbox(
                            "Тип инструмента", _instr_options,
                            key="form_instrument_type")

                        chosen_series_code = None
                        expiry_now_form = _expiry_now
                        _futures_secid_form = None

                        if instrument_type == "Опцион":
                            chosen_series_label = st.selectbox(
                                "Дата исполнения", _series_labels,
                                index=_default_series_idx, key="form_series")
                            chosen_series = _series_by_label[chosen_series_label]
                            expiry_now_form = chosen_series["expiry"]
                            chosen_series_code = chosen_series["code"]
                        elif instrument_type == "Фьючерс":
                            _contracts = fetch_futures_contracts_list(asset_now)
                            if _contracts:
                                _contract_labels = [
                                    f"{c['expiration']} — {c['secid']}"
                                    for c in _contracts]
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
                            st.text_input("Дата исполнения",
                                          value="—", disabled=True,
                                          key="form_no_exp_disp")

                        chosen_strike = None
                        opt_type = "—"

                        if instrument_type == "Опцион" and all_strikes:
                            default_idx = 0
                            if central is not None:
                                try:
                                    default_idx = all_strikes.index(
                                        min(all_strikes,
                                            key=lambda s: abs(float(s) - float(central))))
                                except ValueError:
                                    default_idx = 0
                            chosen_strike = st.selectbox(
                                "Страйк", all_strikes,
                                index=default_idx, key="form_strike",
                                format_func=lambda x: _fmt_strike(x, asset_type_ui_now))
                            opt_type = st.selectbox(
                                "Опцион", ["Call", "Put"], key="form_opt_type")

                        _f3c1, _f3c2 = st.columns(2)
                        with _f3c1:
                            side_ui = st.selectbox(
                                "Направление", ["Покупка", "Продажа"],
                                key="form_side")
                            side = _side_internal(side_ui)
                        with _f3c2:
                            qty_input = st.number_input(
                                "Кол-во", min_value=1, value=1,
                                step=1, key="form_qty")

                        if instrument_type == "Опцион" and opt_type == "Put":
                            st.caption(
                                "Справка: путы обычно открываются вдвое "
                                "меньшим объёмом, чем коллы")

                    if instrument_type == "Опцион":
                        _cur_price_for_check = _get_current_market_price_for_asset(
                            asset_now, asset_type_ui_now)

                        _tf_level = ""
                        try:
                            _df_al_chk = st.session_state.get("alerts_df")
                            if _df_al_chk is not None and "ТФ уровня" in _df_al_chk.columns:
                                _mask_chk = (
                                    _df_al_chk["Тикер БА"].astype(str)
                                    .str.upper().str.strip() == asset_now.upper())
                                _row_chk = _df_al_chk[_mask_chk].head(1)
                                if not _row_chk.empty:
                                    _tf_level = str(
                                        _row_chk.iloc[0].get("ТФ уровня", "") or "")
                        except Exception:
                            pass

                        _trend_v = _alert_info_pos.get("trend", "") if _alert_info_pos else ""
                        _wave_v = _alert_info_pos.get("wave", "") if _alert_info_pos else ""
                        _tend_v = _alert_info_pos.get("tendency", "") if _alert_info_pos else ""

                        _checklist_items = _pretrade_checklist_state(
                            trend=_trend_v, wave=_wave_v, tendency=_tend_v,
                            tf_level=_tf_level,
                            side=side, opt_type=opt_type,
                            strike=chosen_strike,
                            current_price=_cur_price_for_check,
                            expiry_str=expiry_now_form,
                            qty=int(qty_input))
                        _render_pretrade_checklist(_checklist_items)

                    with st.form("add_position_form", clear_on_submit=False):
                        ref_opt = {}
                        _auto_price = 0.0
                        if instrument_type == "Опцион" and chosen_strike is not None:
                            ref_opt = (c_map.get(chosen_strike, {})
                                       if opt_type == "Call"
                                       else p_map.get(chosen_strike, {}))
                            _auto_price = _get_board_price(
                                chosen_strike, opt_type, side, c_map, p_map)

                        price_input = st.number_input(
                            "Цена, ₽ (0 = взять из доски)", min_value=0.0,
                            value=0.0, step=0.01, format="%.4f",
                            key="form_price")

                        if instrument_type == "Опцион" and chosen_strike is not None:
                            ticker_val = ref_opt.get('secid', '—')
                        elif instrument_type == "Фьючерс" and _futures_secid_form:
                            ticker_val = _futures_secid_form
                        else:
                            ticker_val = resolve_underlying_secid(
                                asset_now, asset_type_ui_now) or '—'
                        st.text_input("Тикер (авто)", value=ticker_val,
                                      disabled=True, key="form_ticker_disp")

                        use_auto_price = True
                        if (instrument_type == "Опцион"
                                and chosen_strike is not None
                                and _auto_price > 0):
                            _label = _fmt_board_label(
                                opt_type, side, chosen_strike,
                                _auto_price, asset_type_ui_now)
                            st.markdown(
                                f"<div style='background:#eef6fb; "
                                f"border-radius:10px; padding:8px 14px; "
                                f"font-size:.9rem; color:#1c5a7a; margin:6px 0;'>"
                                f"Цена из доски: <b style='font-family:Consolas,"
                                f"monospace; font-size:1rem;'>{_label}</b></div>",
                                unsafe_allow_html=True)
                            use_auto_price = st.checkbox(
                                "Использовать авто-цену из доски",
                                value=True, key="form_use_auto_price")
                        elif (instrument_type == "Опцион"
                              and chosen_strike is not None):
                            st.caption("Авто-цена недоступна для выбранной "
                                       "комбинации")

                        submitted = st.form_submit_button(
                            "Добавить позицию", type="primary",
                            use_container_width=True)

                    if submitted:
                        if instrument_type == "Фьючерс":
                            _und_secid = _futures_secid_form or asset_now
                            _fut_info = fetch_futures_info_iss(_und_secid) or {}
                            _last_price = _fut_info.get("last")
                            _fut_exp = _fut_info.get("expiration") or expiry_now_form
                            final_price = (float(price_input) if price_input > 0
                                           else (float(_last_price) if _last_price else 0.0))
                            if final_price > 0:
                                signed_qty = (int(qty_input) if side == "Buy"
                                              else -int(qty_input))
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
                                    "Теор.цена": (float(_last_price)
                                                  if _last_price
                                                  else float(final_price)),
                                    "Дельта": None, "Гамма": None, "Вега": None,
                                    "Тета": None, "Ро": None, "visible": True,
                                }
                                _pos = apply_parity_delta(_pos)
                                st.session_state.positions.append(_pos)
                                st.session_state["_position_add_flash"] = {
                                    "errors": [], "warnings": [],
                                    "message": f"Добавлено: {side_ui} фьючерс "
                                               f"{_und_secid} × {qty_input} "
                                               f"по {final_price:.4f} ₽"}
                                st.rerun()
                            else:
                                st.error("Не удалось определить цену фьючерса.")

                        elif instrument_type in ("Акция", "Индекс"):
                            _und_secid = resolve_underlying_secid(
                                asset_now, asset_type_ui_now)
                            _ba_info = fetch_ba_iss_info(
                                _und_secid, asset_type_ui_now) or {}
                            _last_price = _ba_info.get("last")
                            final_price = (float(price_input) if price_input > 0
                                           else (float(_last_price) if _last_price else 0.0))
                            if final_price > 0:
                                signed_qty = (int(qty_input) if side == "Buy"
                                              else -int(qty_input))
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
                                    "Теор.цена": (float(_last_price)
                                                  if _last_price
                                                  else float(final_price)),
                                    "Дельта": None, "Гамма": None, "Вега": None,
                                    "Тета": None, "Ро": None, "visible": True,
                                }
                                _pos = apply_parity_delta(_pos)
                                st.session_state.positions.append(_pos)
                                st.session_state["_position_add_flash"] = {
                                    "errors": [], "warnings": [],
                                    "message": f"Добавлено: {side_ui} "
                                               f"{instrument_type} "
                                               f"{_und_secid} × {qty_input} "
                                               f"по {final_price:.4f} ₽"}
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

                                ref = (_c_map_sel.get(chosen_strike, {})
                                       if opt_type == "Call"
                                       else _p_map_sel.get(chosen_strike, {}))
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
                                    _cp_leg = _get_current_market_price_for_asset(
                                        asset_now, asset_type_ui_now)
                                    _errs, _warns = _validate_options_leg(
                                        side=side, opt_type=opt_type,
                                        strike=chosen_strike,
                                        expiry_str=expiry_now_form,
                                        qty=int(qty_input),
                                        current_price=_cp_leg)

                                    _r_leg_add, _q_leg_add = _compute_r_q_for_leg(
                                        asset_now, asset_type_ui_now,
                                        expiry_now_form)

                                    signed_qty = (int(qty_input) if side == "Buy"
                                                  else -int(qty_input))
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
                                        "Теор.цена": None,
                                        "Дельта": ref.get('delta'),
                                        "Гамма":  ref.get('gamma'),
                                        "Вега":   ref.get('vega'),
                                        "Тета":   ref.get('theta'),
                                        "Ро":     ref.get('rho'),
                                        "visible": True,
                                        "_vol": float(ref.get('volatility') or 20.0),
                                        "_r": float(_r_leg_add),
                                        "_q": float(_q_leg_add),
                                        "_series_code": _sel_series_code,
                                        "_asset": asset_now,
                                        "_atype": asset_type_ui_now,
                                    })

                                    _success_msg = (f"Добавлено: {side_ui} "
                                                    f"{opt_type} "
                                                    f"{chosen_strike} × {qty_input} "
                                                    f"[{expiry_now_form}]"
                                                    f"{_src_label} "
                                                    f"по {final_pos_price:.4f} ₽")
                                    st.session_state["_position_add_flash"] = {
                                        "errors": _errs,
                                        "warnings": _warns,
                                        "message": _success_msg,
                                    }
                                    st.rerun()

    # ==================================================================
    # ЖИВОЕ ОБНОВЛЕНИЕ ТЕОР. ЦЕНЫ И ГРЕКОВ
    # ==================================================================
    _pos_asset_r = st.session_state.get("pos_asset", "")
    _pos_atype_r = st.session_state.get("pos_category", "")
    _pos_series_r = st.session_state.get("pos_series_code", "")

    if _pos_asset_r and _pos_atype_r and st.session_state.positions:
        _series_to_fetch = set()
        for _lp in st.session_state.positions:
            if _lp.get("Тип инструмента") != "Опцион":
                continue
            _s = _lp.get("_series_code") or _pos_series_r
            if _s:
                _series_to_fetch.add(_s)

        _boards_live = {}
        for _s in _series_to_fetch:
            _boards_live[_s] = _fetch_board_cached_30s(
                _pos_asset_r, _pos_atype_r, _s)

        def _estimate_F(board):
            if not board:
                return None
            _calls = board.get("call") or []
            _puts  = board.get("put")  or []
            _c_map = {c["strike"]: c for c in _calls
                      if c.get("theorprice") and c.get("strike") is not None}
            _p_map = {p["strike"]: p for p in _puts
                      if p.get("theorprice") and p.get("strike") is not None}
            _commons = sorted(set(_c_map) & set(_p_map))
            _fs_est = []
            for _k in _commons:
                _ct = _c_map[_k]["theorprice"]
                _pt = _p_map[_k]["theorprice"]
                if _ct and _pt and _ct > 0 and _pt > 0:
                    _fs_est.append(_ct - _pt + float(_k))
            if _fs_est:
                _fs_est.sort()
                return _fs_est[len(_fs_est) // 2]
            return None

        _updated = 0
        for _lp in st.session_state.positions:
            if _lp.get("Тип инструмента") != "Опцион":
                continue
            _s = _lp.get("_series_code") or _pos_series_r
            _b = _boards_live.get(_s)
            if not _b:
                _lp["Теор.цена"] = None
                continue

            _row = _find_board_row_by_secid(_b, _lp.get("Тикер"))
            if _row is None:
                _side = "call" if _lp.get("Опцион") == "Call" else "put"
                _row = _find_board_row(_b, _side, _lp.get("Страйк"))
            if _row is None:
                _lp["Теор.цена"] = None
                continue

            _lp["Дельта"] = _row.get("delta")
            _lp["Гамма"]  = _row.get("gamma")
            _lp["Вега"]   = _row.get("vega")
            _lp["Тета"]   = _row.get("theta")
            _lp["Ро"]     = _row.get("rho")
            _iv = _row.get("volatility")
            if _iv is not None:
                try:
                    _lp["_vol"] = float(_iv)
                except (TypeError, ValueError):
                    pass

            _th = _row.get("theorprice")
            _th_ok = False
            if _th is not None:
                try:
                    _th_f = float(_th)
                    if _th_f > 0:
                        _lp["Теор.цена"] = _th_f
                        _th_ok = True
                        _updated += 1
                except (TypeError, ValueError):
                    pass

            if not _th_ok:
                _opp_side = "put" if _lp.get("Опцион") == "Call" else "call"
                _opp_list = _b.get(_opp_side) or []
                _opp = next((x for x in _opp_list
                             if _strike_eq(x.get("strike"), _lp.get("Страйк"))), None)
                _th_opp = (_opp or {}).get("theorprice")
                _k_f = float(_lp.get("Страйк") or 0)
                _F = _estimate_F(_b)
                if _th_opp is not None and _F is not None:
                    try:
                        _th_opp_f = float(_th_opp)
                        if _th_opp_f > 0:
                            if _lp.get("Опцион") == "Call":
                                _th_calc = _th_opp_f + (_F - _k_f)
                            else:
                                _th_calc = _th_opp_f + (_k_f - _F)
                            if _th_calc > 0:
                                _lp["Теор.цена"] = float(_th_calc)
                                _updated += 1
                            else:
                                _lp["Теор.цена"] = None
                        else:
                            _lp["Теор.цена"] = None
                    except (TypeError, ValueError):
                        _lp["Теор.цена"] = None
                else:
                    _lp["Теор.цена"] = None

        _ck = st.session_state.get("_pos_active_key")
        if _ck:
            _new_sig = _positions_signature(st.session_state.positions)
            if _new_sig != st.session_state.get("_pos_signature"):
                st.session_state.positions_cache[_ck] = list(st.session_state.positions)
                _ok_save = _save_cache(st.session_state.positions_cache)
                if _ok_save:
                    st.session_state["_last_save_ts"] = datetime.now().strftime("%H:%M:%S")
                    st.session_state["_last_save_count"] = _updated
                st.session_state["_pos_signature"] = _new_sig

    # ==================================================================
    # ТЕКУЩИЕ ПОЗИЦИИ
    # ==================================================================
    st.markdown("---")
    st.markdown("### Текущие позиции")

    _pos_cat_for_fmt = st.session_state.get("pos_category", "")

    if not st.session_state.positions:
        st.caption("Портфель пуст.")
    elif st.session_state.get("pos_view_mode") == "Карточки (мобильный)":
        # ================= Мобильный вид — карточки =================
        for idx, p in enumerate(st.session_state.positions):
            _id = p.get("_id", f"legacy_{idx}")
            _visible = p.get("visible", True)
            _gray = "opacity:0.45;" if not _visible else ""

            _instr = p.get("Тип инструмента", "Опцион")
            _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
            _qty = int(p.get("Кол-во", 0))
            _price = float(p.get("Цена", 0))
            _theor = float(p.get("Теор.цена") or 0)
            _com = 0.0 if _isBA else _calc_comm(_price, _instr)
            _pnl = ((_theor - _price) * _qty if _isBA
                    else (_theor - _price - _com) * _qty)
            _color_pnl = "#00a651" if _pnl > 0 else ("#d32f2f" if _pnl < 0 else "#333")

            _exp_str = p.get("Эксп.", "—")
            _dte = "—"
            if _exp_str and _exp_str != "—":
                try:
                    _d = datetime.strptime(_exp_str, "%Y-%m-%d").date()
                    _dte = f"{(_d - date.today()).days}"
                except Exception:
                    pass
            _plan_badge = _planned_close_badge(_exp_str)
            _plan_date = _planned_close_date_str(_exp_str)

            _opt = p.get("Опцион", "—")
            _opt_color = ("#00a651" if _opt == "Call"
                          else "#d32f2f" if _opt == "Put" else "#333")
            _atype_row = p.get("_atype", _pos_cat_for_fmt)
            _k_str = _fmt_strike(p.get("Страйк"), _atype_row)

            with st.container(border=True):
                _h1c1, _h1c2, _h1c3 = st.columns([3, 2, 1])
                with _h1c1:
                    st.markdown(
                        f"<div style='{_gray}'>"
                        f"<span style='font-size:1.1rem; font-weight:700;'>"
                        f"{p.get('Тикер', '—')}</span> "
                        f"<span style='color:{_opt_color}; font-weight:700;'>"
                        f"{_opt}</span> "
                        f"<span style='font-weight:700;'>"
                        f"{_k_str}</span></div>",
                        unsafe_allow_html=True)
                with _h1c2:
                    st.markdown(
                        f"<div style='{_gray}; font-size:.85rem; "
                        f"text-align:right;'>"
                        f"<b>{_instr}</b><br>"
                        f"до эксп.: {_dte} дн.</div>",
                        unsafe_allow_html=True)
                with _h1c3:
                    if st.button("✖", key=f"m_del_{_id}",
                                 use_container_width=True):
                        st.session_state.positions.pop(idx)
                        for k in list(st.session_state.keys()):
                            if k.endswith(f"_{_id}"):
                                del st.session_state[k]
                        st.rerun()

                _m_row1, _m_row2 = st.columns(2)
                with _m_row1:
                    st.markdown(
                        f"<div style='{_gray}; font-size:.82rem;'>"
                        f"Экспирация: <b>{_exp_str}</b><br>"
                        f"План. закрытие: <b>{_plan_date}</b>"
                        f"{_plan_badge}</div>",
                        unsafe_allow_html=True)
                with _m_row2:
                    st.markdown(
                        f"<div style='{_gray}; font-size:.82rem;'>"
                        f"Кол-во: <b>{_qty}</b><br>"
                        f"Цена: <b>{_price:.4f}</b><br>"
                        f"Теор.: <b>{_theor:.4f}</b></div>",
                        unsafe_allow_html=True)

                _d_val = p.get('Дельта')
                _g_val = p.get('Гамма')
                _v_val = p.get('Вега')
                _t_val = p.get('Тета')
                st.markdown(
                    f"<div style='margin-top:6px; padding:8px 10px; "
                    f"background:#f6f9fc; border-radius:6px; "
                    f"font-size:.85rem;'>"
                    f"P&L: <b style='color:{_color_pnl};'>"
                    f"{_pnl:+,.2f} ₽</b> &nbsp;·&nbsp; "
                    f"Δ={_d_val if isinstance(_d_val, (int, float)) else '—'} "
                    f"Γ={_g_val if isinstance(_g_val, (int, float)) else '—'} "
                    f"ν={_v_val if isinstance(_v_val, (int, float)) else '—'} "
                    f"Θ={_t_val if isinstance(_t_val, (int, float)) else '—'}"
                    f"</div>",
                    unsafe_allow_html=True)

                _m_qty_col, _m_price_col, _m_vis_col = st.columns([2, 2, 1])
                with _m_qty_col:
                    kq = f"qty_{_id}"
                    if kq not in st.session_state:
                        st.session_state[kq] = int(p.get("Кол-во", 1))
                    st.number_input(
                        "Кол-во", min_value=-10000, max_value=10000,
                        step=1, key=kq,
                        on_change=_cb_qty_sync, args=(kq, _id))
                with _m_price_col:
                    kp = f"price_{_id}"
                    if kp not in st.session_state:
                        st.session_state[kp] = float(p.get("Цена", 0.0))
                    st.number_input(
                        "Цена", min_value=0.0, step=0.01,
                        format="%.4f", key=kp,
                        on_change=_cb_price_sync, args=(kp, _id))
                with _m_vis_col:
                    st.markdown("<div style='height:1.5rem;'></div>",
                                unsafe_allow_html=True)
                    _icon = "👁" if _visible else "🚫"
                    if st.button(_icon, key=f"m_vis_{_id}",
                                 use_container_width=True):
                        p["visible"] = not _visible
                        st.rerun()

        st.markdown("---")
        _m_sum1, _m_sum2 = st.columns(2)
        with _m_sum1:
            _tot_pnl_mobile = 0.0
            for p in st.session_state.positions:
                if not p.get("visible", True):
                    continue
                _q = int(p.get("Кол-во", 0))
                _pr = float(p.get("Цена", 0))
                _th = float(p.get("Теор.цена") or 0)
                _instr = p.get("Тип инструмента", "Опцион")
                _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
                if _isBA:
                    _tot_pnl_mobile += (_th - _pr) * _q
                else:
                    _c = _calc_comm(_pr, _instr)
                    _tot_pnl_mobile += (_th - _pr - _c) * _q
            _c_pnl_m = ("#00a651" if _tot_pnl_mobile > 0
                        else "#d32f2f" if _tot_pnl_mobile < 0 else "#333")
            st.markdown(
                f"<div style='font-size:1rem;'>"
                f"<b>Итого P&L:</b> "
                f"<span style='color:{_c_pnl_m}; font-weight:800;'>"
                f"{_tot_pnl_mobile:+,.2f} ₽</span></div>",
                unsafe_allow_html=True)
        with _m_sum2:
            if st.button("Обновить позиции",
                         type="primary", use_container_width=True,
                         key="m_refresh_positions"):
                st.rerun()
    else:
        # ================= Таблица (как раньше) =================
        _pos_container = st.container(border=True)
        with _pos_container:
            st.markdown("<div class='pos-row-wrap'>", unsafe_allow_html=True)
            COL_W = [0.28, 0.32, 0.85, 0.75, 0.85, 0.95, 0.65, 1.10, 1.30,
                     1.05, 1.20, 1.15, 1.15, 1.15, 0.95, 0.85, 0.85, 0.85, 0.75, 0.95]
            HEADERS = ["", "", "Тип", "Опцион", "Страйк", "Дата исп.", "До эксп.",
                       "План. закрытие", "Тикер", "Кол-во", "Цена", "Ср. цена",
                       "Теор. цена", "P&L", "Дельта", "Гамма", "Вега", "Тета",
                       "Ро", "Комисс."]

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
                                 help="Скрыть/показать в профиле и расчётах",
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
                    _atype_row = p.get("_atype", _pos_cat_for_fmt)
                    _k_txt = (f"<b>{_fmt_strike(_k, _atype_row)}</b>"
                              if _k is not None else "—")
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
                    _exp_str = p.get("Эксп.", "—")
                    _plan_date_str = _planned_close_date_str(_exp_str)
                    _plan_badge = _planned_close_badge(_exp_str)
                    st.markdown(
                        f"<div style='padding-top:6px; {gray}; font-size:.78rem;'>"
                        f"{_plan_date_str}</div>"
                        f"{_plan_badge}",
                        unsafe_allow_html=True)

                with row[8]:
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.78rem;'>"
                                f"{p.get('Тикер', '—')}</div>", unsafe_allow_html=True)

                with row[9]:
                    kq = f"qty_{_id}"
                    if kq not in st.session_state:
                        st.session_state[kq] = int(p.get("Кол-во", 1))
                    qc = st.columns([1, 3, 1])
                    with qc[0]:
                        st.button("➖", key=f"qm_{_id}",
                                  on_click=_cb_qty_dec, args=(kq, _id),
                                  use_container_width=True)
                    with qc[1]:
                        st.number_input(
                            "qty", min_value=-10000, max_value=10000, step=1,
                            key=kq, label_visibility="collapsed",
                            on_change=_cb_qty_sync, args=(kq, _id))
                    with qc[2]:
                        st.button("➕", key=f"qp_{_id}",
                                  on_click=_cb_qty_inc, args=(kq, _id),
                                  use_container_width=True)

                with row[10]:
                    kp = f"price_{_id}"
                    if kp not in st.session_state:
                        st.session_state[kp] = float(p.get("Цена", 0.0))
                    pc = st.columns([1, 3, 1])
                    with pc[0]:
                        st.button("➖", key=f"pm_{_id}",
                                  on_click=_cb_price_dec, args=(kp, _id),
                                  use_container_width=True)
                    with pc[1]:
                        st.number_input(
                            "price", min_value=0.0,
                            step=0.01, format="%.4f",
                            key=kp, label_visibility="collapsed",
                            on_change=_cb_price_sync, args=(kp, _id))
                    with pc[2]:
                        st.button("➕", key=f"pp_{_id}",
                                  on_click=_cb_price_inc, args=(kp, _id),
                                  use_container_width=True)

                _theor = float(p.get("Теор.цена") or 0)
                _instr = p.get("Тип инструмента", "Опцион")
                _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
                _com = 0.0 if _isBA else _calc_comm(float(p.get("Цена", 0)), _instr)
                _qty = int(p.get("Кол-во", 0))
                _price = float(p.get("Цена", 0))
                _eff_price = _price + _com
                _pnl = ((_theor - _price) * _qty if _isBA
                        else (_theor - _eff_price) * _qty)

                with row[11]:
                    st.markdown(
                        f"<div style='padding-top:6px; {gray}; font-size:.82rem; "
                        f"font-weight:600; color:#7c4dff;'>"
                        f"{_eff_price:.4f}</div>",
                        unsafe_allow_html=True)

                with row[12]:
                    _theor_disp = f"{_theor:.4f}" if _theor and _theor > 0 else "—"
                    st.markdown(
                        f"<div style='padding-top:6px; {gray}; font-size:.82rem;'>"
                        f"{_theor_disp}</div>",
                        unsafe_allow_html=True)

                with row[13]:
                    _color = "#00a651" if _pnl > 0 else ("#d32f2f" if _pnl < 0 else "#333")
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-weight:700; "
                                f"color:{_color};'>{_pnl:+,.2f} ₽</div>",
                                unsafe_allow_html=True)

                for ri, gr in zip([14, 15, 16, 17, 18],
                                  ["Дельта", "Гамма", "Вега", "Тета", "Ро"]):
                    val = p.get(gr)
                    txt = f"{val:+.4f}" if isinstance(val, (int, float)) else "—"
                    _greek_color = ""
                    if gr == "Дельта":
                        _greek_color = _greek_delta_color(val)
                    elif gr == "Тета":
                        _greek_color = _greek_theta_color(val, p.get("Вега"))
                    _style_color = f"color:{_greek_color}; font-weight:700;" \
                                   if _greek_color else ""
                    with row[ri]:
                        st.markdown(
                            f"<div style='padding-top:6px; {gray}; "
                            f"font-size:.78rem; {_style_color}'>{txt}</div>",
                            unsafe_allow_html=True)

                with row[19]:
                    st.markdown(f"<div style='padding-top:6px; {gray}; font-size:.78rem;'>"
                                f"{_com:.2f}</div>", unsafe_allow_html=True)

            st.markdown("<hr style='margin:4px 0 4px 0; border:none; "
                        "border-top:1px solid #e6edf4;'>", unsafe_allow_html=True)

            _tot_com = _tot_pnl = _tot_delta = _tot_gamma = 0.0
            _tot_vega = _tot_theta = _tot_rho = 0.0
            for p in st.session_state.positions:
                if not p.get("visible", True):
                    continue
                _q = int(p.get("Кол-во", 0))
                _pr = float(p.get("Цена", 0))
                _th = float(p.get("Теор.цена") or 0)
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
            with tot_row[8]:
                st.markdown("<div style='padding-top:6px; font-size:.8rem; "
                            "color:#2c506d; font-weight:700;'>Итого (видимые):</div>",
                            unsafe_allow_html=True)

            _color_pnl_tot = "#00a651" if _tot_pnl > 0 else ("#d32f2f" if _tot_pnl < 0 else "#333")
            with tot_row[13]:
                st.markdown(f"<div style='padding-top:6px; font-weight:800; "
                            f"color:{_color_pnl_tot};'>{_tot_pnl:+,.2f} ₽</div>",
                            unsafe_allow_html=True)
            with tot_row[14]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_delta:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[15]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_gamma:+.4f}</div>", unsafe_allow_html=True)
            with tot_row[16]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_vega:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[17]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_theta:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[18]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_rho:+.3f}</div>", unsafe_allow_html=True)
            with tot_row[19]:
                st.markdown(f"<div style='padding-top:6px; font-weight:700;'>"
                            f"{_tot_com:,.4f}</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        _save_ts = st.session_state.get("_last_save_ts", "—")
        _save_cnt = st.session_state.get("_last_save_count", 0)
        _cache_file_now = _cache_file()
        _cache_file_str = str(_cache_file_now) if _cache_file_now else "—"
        st.caption(
            f"Автосохранение включено · "
            f"последняя запись: {_save_ts} · "
            f"обновлено цен: {_save_cnt} · "
            f"файл: {_cache_file_str}"
        )

        _btn1, _btn2, _btn3, _btn4 = st.columns([1, 1, 1, 2])
        with _btn1:
            _refresh_clicked = st.button("Обновить позицию",
                                          use_container_width=True,
                                          type="primary",
                                          key="positions_refresh_btn")
        with _btn2:
            if "positions_cache" in st.session_state:
                _cur_active = st.session_state.get("_pos_active_key")
                if _cur_active:
                    st.session_state.positions_cache[_cur_active] = \
                        list(st.session_state.positions)
                    _save_cache(st.session_state.positions_cache)

            _cache_json_bytes = json.dumps(
                st.session_state.get("positions_cache", {}),
                ensure_ascii=False, indent=2, default=str,
            ).encode("utf-8")
            st.download_button(
                # [PATCH 1] Переименовано: «Только позиции · JSON»
                "Только позиции · JSON",
                data=_cache_json_bytes,
                file_name=f"positions_{date.today().isoformat()}.json",
                mime="application/json",
                use_container_width=True,
                key="positions_export_json_btn",
                help="Скачать файл только с позициями (без журнала и настроек). "
                     "Для полной резервной копии используйте «Резервная копия · JSON».",
            )
        with _btn3:
            _export_rows = []
            for i, p in enumerate(st.session_state.positions):
                _q = int(p.get("Кол-во", 0))
                _pr = float(p.get("Цена", 0))
                _instr = p.get("Тип инструмента", "Опцион")
                _isBA = (_instr == "БА" or p.get("Опцион") == "БА")
                _c = 0.0 if _isBA else _calc_comm(_pr, _instr)
                _export_rows.append({
                    "Актив": st.session_state.get("pos_asset", ""),
                    "Категория": st.session_state.get("pos_category", ""),
                    "#": i + 1, "Тип": _instr, "Опцион": p.get("Опцион", "—"),
                    "Направление": _side_ui(p.get("Направление",
                                                    _side_from_qty(_q))),
                    "Страйк": p.get("Страйк", "—"),
                    "Эксп.": p.get("Эксп.", "—"),
                    "Тикер": p.get("Тикер", "—"),
                    "Кол-во": _q,
                    "Цена": _pr,
                    "Комиссия": round(_c, 2),
                    "Эфф. цена": round(_pr + _c, 4),
                })
            _df_export = pd.DataFrame(_export_rows)
            st.download_button(
                "Экспорт CSV",
                data=_df_export.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"portfolio_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
                key="positions_export_btn",
                help="Только кол-во и цена входа — без live-полей",
            )
        with _btn4:
            # [PATCH 1] Старый автоматический импорт _json_up УДАЛЁН —
            # он мог повторно применяться после st.rerun() и не синхронизировал
            # текущую позицию с восстановленным кешем. Вместо этого — ссылка
            # на общий блок «Резервная копия · JSON».
            st.caption(
                "Для восстановления полного состояния или старого JSON "
                "позиций используйте «Резервная копия · JSON»."
            )

        if _refresh_clicked:
            st.rerun()

    # ==================================================================
    # АНАЛИЗ ПОЗИЦИИ (ДЕБЕТ/КРЕДИТ, РИСК, КЛАССИФИКАЦИЯ СТРАТЕГИИ)
    # ==================================================================
    if st.session_state.positions:
        _visible_positions = [p for p in st.session_state.positions
                              if p.get("visible", True)]

        _net_cash_flow = 0.0
        for p in _visible_positions:
            if p.get("Опцион") == "БА":
                continue
            _q = int(p.get("Кол-во", 0))
            _pr = float(p.get("Цена", 0))
            _instr = p.get("Тип инструмента", "Опцион")
            _c = _calc_comm(_pr, _instr)
            if _q > 0:
                _net_cash_flow -= (_pr * _q + _c * abs(_q))
            else:
                _net_cash_flow += (_pr * abs(_q) - _c * abs(_q))

        if _net_cash_flow < -0.01:
            _position_type = "ДЕБЕТОВАЯ"
            _position_bg = "rgba(0,166,81,0.10)"
            _position_border = "#00a651"
            _position_fg = "#0a6b32"
        elif _net_cash_flow > 0.01:
            _position_type = "КРЕДИТОВАЯ"
            _position_bg = "rgba(211,47,47,0.10)"
            _position_border = "#d32f2f"
            _position_fg = "#8b1e1e"
        else:
            _position_type = "НУЛЕВАЯ"
            _position_bg = "rgba(122,122,122,0.10)"
            _position_border = "#7a7a7a"
            _position_fg = "#4a4a4a"

        _short_calls_list = []
        _long_calls_list = []
        _short_puts_list = []
        _long_puts_list = []
        _ba_long_qty = 0
        _ba_short_qty = 0

        for p in _visible_positions:
            _opt = p.get("Опцион", "—")
            _q = int(p.get("Кол-во", 0))
            if _q == 0:
                continue
            if _opt in ("Call", "Put"):
                _k = float(p.get("Страйк", 0) or 0)
                if _opt == "Call":
                    if _q < 0:
                        _short_calls_list.append((_k, abs(_q)))
                    else:
                        _long_calls_list.append((_k, abs(_q)))
                else:
                    if _q < 0:
                        _short_puts_list.append((_k, abs(_q)))
                    else:
                        _long_puts_list.append((_k, abs(_q)))
            elif _opt == "БА" or p.get("Тип инструмента") == "БА":
                if _q > 0:
                    _ba_long_qty += _q
                else:
                    _ba_short_qty += abs(_q)

        _short_calls_uncovered = 0
        for _k_s, _q_s in _short_calls_list:
            _covered = _ba_long_qty
            for _k_l, _q_l in _long_calls_list:
                if _k_l <= _k_s:
                    _covered += _q_l
            _short_calls_uncovered += max(0, _q_s - _covered)

        _short_puts_uncovered = 0
        for _k_s, _q_s in _short_puts_list:
            _covered = _ba_short_qty
            for _k_l, _q_l in _long_puts_list:
                if _k_l >= _k_s:
                    _covered += _q_l
            _short_puts_uncovered += max(0, _q_s - _covered)

        _risk_is_unlimited = (_short_calls_uncovered > 0
                              or _short_puts_uncovered > 0)

        _risk_value = 0.0
        try:
            _strikes_all_r = [float(p["Страйк"]) for p in _visible_positions
                              if p.get("Страйк") is not None]
            _ba_prices_r = [float(p["Цена"]) for p in _visible_positions
                            if p.get("Опцион") == "БА"
                            or p.get("Тип инструмента") == "БА"]
            _all_ref_r = _strikes_all_r + _ba_prices_r

            if _all_ref_r:
                _s_low_r = max(0.01, min(_all_ref_r) * 0.5)
                _s_high_r = max(_all_ref_r) * 1.5
                _S_eval_r = np.linspace(_s_low_r, _s_high_r, 800)
                _pnl_eval_r = compute_payoff(
                    _visible_positions, _S_eval_r,
                    comm_func=_calc_comm)
                _min_pnl_r = float(np.min(_pnl_eval_r))
                _risk_value = max(0.0, -_min_pnl_r)
        except Exception:
            _risk_value = abs(_net_cash_flow) if _net_cash_flow < 0 else 0.0

        if _risk_is_unlimited:
            _risk_display = "∞"
            _uncovered_details = []
            if _short_calls_uncovered > 0:
                _uncovered_details.append(f"{_short_calls_uncovered} Call")
            if _short_puts_uncovered > 0:
                _uncovered_details.append(f"{_short_puts_uncovered} Put")
            _risk_extra = f"(непокрытых: {', '.join(_uncovered_details)})"
        else:
            _risk_display = f"{_risk_value:,.2f} ₽"
            _risk_extra = ""

        _pct_risk = (_risk_value / risk_amount * 100) if risk_amount > 0 else 0
        _net_label = "кредит" if _net_cash_flow > 0 else "дебет"
        _net_value = abs(_net_cash_flow)

        if _risk_is_unlimited:
            _status_icon = "!"
        elif _risk_value > risk_amount:
            _status_icon = "!"
        else:
            _status_icon = "OK"

        st.markdown(
            f"""<div style='padding:12px 16px; border-radius:10px;
            background:{_position_bg}; border-left:6px solid {_position_border};
            margin-bottom:10px;'>
            <div style='font-size:1.02rem; font-weight:800; color:{_position_fg};'>
            {_status_icon} — Позиция <b>{_position_type}</b></div>
            <div style='font-size:.92rem; color:#333; margin-top:6px;'>
            Риск: <b>{_risk_display}</b> {_risk_extra} / {risk_amount:,.2f} ₽
            ({_pct_risk:.1f}%) &nbsp;·&nbsp;
            Net {_net_label}: <b>{_net_value:,.2f} ₽</b>
            </div></div>""",
            unsafe_allow_html=True)

        if _risk_is_unlimited:
            st.error(f"Позиция содержит непокрытые короткие опционы. "
                     f"Теоретический риск не ограничен. "
                     f"Допустимый риск: {risk_amount:,.2f} ₽")
        elif _risk_value > risk_amount:
            st.error(f"Превышен допустимый риск: "
                     f"{_risk_value:,.2f} ₽ > {risk_amount:,.2f} ₽")

        _cls_gamma = _cls_theta = _cls_vega = 0.0
        for _cp in _visible_positions:
            _cq = int(_cp.get("Кол-во", 0))
            _cls_gamma += (_cp.get("Гамма") or 0) * _cq
            _cls_theta += (_cp.get("Тета")  or 0) * _cq
            _cls_vega  += (_cp.get("Вега")  or 0) * _cq

        _strategy_cls = classify_strategy(_cls_gamma, _cls_theta, _cls_vega)

        _rvi_strat_data = fetch_rvi_current()
        _rvi_strat_val = _rvi_strat_data.get("value") if _rvi_strat_data else None

        _panel_lines = [
            f"<div style='padding:14px 18px; border-radius:12px; "
            f"background:{_strategy_cls['color']}15; "
            f"border-left:6px solid {_strategy_cls['color']}; margin:10px 0;'>",
            f"<div style='font-size:1.05rem; font-weight:800; "
            f"color:{_strategy_cls['color']};'>{_strategy_cls['label']}</div>",
            f"<div style='font-size:.85rem; color:#5a6b78; margin-top:4px;'>"
            f"Γ = {_cls_gamma:+.4f} · Θ = {_cls_theta:+.2f} · ν = {_cls_vega:+.2f}</div>",
            f"<div style='font-size:.82rem; color:#333; margin-top:6px;'>"
            f"{_strategy_cls['description']}</div>",
        ]

        if _rvi_strat_val is not None:
            if _strategy_cls["class"] == "long_vol":
                if _rvi_strat_val < 20:
                    _panel_lines.append(
                        f"<div style='margin-top:8px; padding:8px 12px; "
                        f"background:#e8f5e9; border-radius:6px; font-size:.82rem;'>"
                        f"RVI = {_rvi_strat_val:.2f}% (низкий) — "
                        f"хороший момент для покупки ν</div>")
                elif _rvi_strat_val > 40:
                    _panel_lines.append(
                        f"<div style='margin-top:8px; padding:8px 12px; "
                        f"background:#fff3e0; border-radius:6px; font-size:.82rem;'>"
                        f"RVI = {_rvi_strat_val:.2f}% (высокий) — "
                        f"волатильность дорогая, покупка рискованна</div>")
            elif _strategy_cls["class"] == "short_vol":
                if _rvi_strat_val > 40:
                    _panel_lines.append(
                        f"<div style='margin-top:8px; padding:8px 12px; "
                        f"background:#ffebee; border-radius:6px; font-size:.82rem;'>"
                        f"RVI = {_rvi_strat_val:.2f}% (высокий) — "
                        f"рынок в панике, продажа ν опасна</div>")
                elif _rvi_strat_val < 20:
                    _panel_lines.append(
                        f"<div style='margin-top:8px; padding:8px 12px; "
                        f"background:#e8f5e9; border-radius:6px; font-size:.82rem;'>"
                        f"RVI = {_rvi_strat_val:.2f}% (низкий) — "
                        f"хороший момент для продажи ν</div>")

        _panel_lines.append("</div>")
        st.markdown("".join(_panel_lines), unsafe_allow_html=True)

    # ==================================================================
    # ГРАФИК ПРОФИЛЯ ПОЗИЦИИ
    # ==================================================================
    st.markdown("---")
    st.markdown("### График профиля позиции")

    _pos_asset_now = st.session_state.get("pos_asset", "")
    _pos_cat_now = st.session_state.get("pos_category", "")
    payoff_positions = [
        p for p in st.session_state.positions
        if p.get("visible", True)
        and (p.get("_asset") or _pos_asset_now) == _pos_asset_now
        and (p.get("_atype") or _pos_cat_now) == _pos_cat_now
    ]

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
                f"В портфеле разные даты исполнения. "
                f"Payoff построен на {_anchor_str}.")

        F_current = None
        try:
            _atype_f = st.session_state.get("pos_category", "")
            _eng_f, _mkt_f = _get_engine_market(_atype_f)
            _secid_f = resolve_underlying_secid(
                st.session_state.get("pos_asset", ""), _atype_f)
            F_current = get_last_close_price(_secid_f, _eng_f, _mkt_f)
        except Exception:
            F_current = None

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

            # [PATCH 7] Число расчётов больше не зависит от номинальной
            # цены актива. Страйки включаются отдельно, чтобы сохранить
            # изломы payoff.
            _reference_points = list(all_pos_strikes)

            if F_current is not None:
                _reference_points.append(float(F_current))

            S_arr = np.unique(np.concatenate([
                np.linspace(s_min, s_max, 1200),
                np.asarray(_reference_points, dtype=float),
            ]))

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
                                 annotation_text=_fmt_strike(k, _pos_cat_now),
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
                be_str = " · ".join(f"{be:,.2f} ₽" for be in be_points)
                st.caption(f"Точки безубыточности: {be_str}")

    # ==================================================================
    # БИРЖЕВЫЕ ГРАФИКИ D1 / H1
    # ==================================================================
    st.markdown("---")
    st.markdown("### Биржевые графики")

    _asset_ch = st.session_state.get("pos_asset", "")
    _atype_ch = st.session_state.get("pos_category", "")
    _series_ch = st.session_state.get("pos_series_code", "")

    if not (_asset_ch and _series_ch):
        st.info("Выберите актив и серию в блоке выше.")
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
                                  comm_func=_calc_comm_ui,
                                  interval=24)
            render_exchange_chart(_df_h1, st.session_state.get("positions", []),
                                  _buy_ch, _sell_ch, _strikes_ch,
                                  f"H1 — {_asset_ch}", "chart_h1_tab",
                                  current_price=_current_price_ch,
                                  comm_func=_calc_comm_ui,
                                  interval=60)
        except Exception as e:
            st.warning(f"Не удалось построить графики: {e}")
            # ==================================================================
# ============ ВКЛАДКА 4: WHAT-IF СИМУЛЯТОР =======================
# ==================================================================
@st.fragment
def _render_whatif_tab():
    st.header("What-if симулятор")
    st.caption("Симуляция P&L текущей позиции при изменении цены БА, "
               "волатильности и даты сценария. "
               "Позиция берётся с вкладки «Позиция».")

    _asset = st.session_state.get("pos_asset", "")
    _atype = st.session_state.get("pos_category", "")

    if not _asset or not _atype:
        st.warning("Сначала выберите актив и категорию на вкладке «Позиция».")
        return

    positions = [
        p for p in st.session_state.get("positions", [])
        if p.get("visible", True)
        and (p.get("_asset") or _asset) == _asset
        and (p.get("_atype") or _atype) == _atype
    ]

    if not positions:
        st.info(f"Нет видимых позиций для {_asset} ({_atype}).")
        return

    current_price = _get_current_market_price_for_asset(_asset, _atype)
    if current_price is None:
        current_price = st.session_state.get("_current_market_price")
    if current_price is None:
        st.warning("Не удалось получить текущую цену БА — задайте вручную.")
        current_price = st.number_input(
            "Текущая цена БА (₽)", min_value=0.01, value=100.0,
            step=1.0, format="%.4f", key="whatif_current_price_manual")
    else:
        st.success(f"Текущая цена {_asset}: {current_price:,.4f} ₽")

    _iv_list = [float(p.get("_vol", 0)) for p in positions
                if p.get("_vol") is not None and float(p.get("_vol", 0)) > 0]
    base_iv = float(np.mean(_iv_list)) if _iv_list else 20.0

    st.markdown("---")

    _wt_exp_dates = []
    for _p in positions:
        _e = _p.get("Эксп.", "—")
        if _e and _e != "—":
            try:
                _wt_exp_dates.append(datetime.strptime(_e, "%Y-%m-%d").date())
            except Exception:
                pass
    _wt_min_date = date.today()
    _wt_max_exp = (max(_wt_exp_dates)
                   if _wt_exp_dates else (_wt_min_date + timedelta(days=180)))
    _wt_max_date = _wt_max_exp + timedelta(days=30)

    _wt_asset_key = f"{_asset}|{_atype}"
    if st.session_state.get("_wt_last_asset") != _wt_asset_key:
        st.session_state.wt_price_abs = float(current_price)
        st.session_state.wt_price_pct = 0.0
        st.session_state.wt_iv_abs = float(base_iv)
        st.session_state.wt_iv_pp = 0.0
        st.session_state.wt_scenario_date = _wt_min_date
        st.session_state.wt_price_ver = st.session_state.get("wt_price_ver", 0) + 1
        st.session_state.wt_iv_ver = st.session_state.get("wt_iv_ver", 0) + 1
        st.session_state["_wt_last_asset"] = _wt_asset_key

    for _k, _def in [("wt_price_abs", float(current_price)),
                     ("wt_price_pct", 0.0),
                     ("wt_iv_abs", float(base_iv)),
                     ("wt_iv_pp", 0.0),
                     ("wt_price_ver", 0),
                     ("wt_iv_ver", 0)]:
        if _k not in st.session_state:
            st.session_state[_k] = _def
    if "wt_scenario_date" not in st.session_state:
        st.session_state.wt_scenario_date = _wt_min_date

    _sd = st.session_state.wt_scenario_date
    if _sd < _wt_min_date:
        st.session_state.wt_scenario_date = _wt_min_date
    elif _sd > _wt_max_date:
        st.session_state.wt_scenario_date = _wt_max_date

    _p_ver = st.session_state.wt_price_ver
    _i_ver = st.session_state.wt_iv_ver
    _p_abs_key = f"wt_p_abs_{_p_ver}"
    _p_pct_key = f"wt_p_pct_{_p_ver}"
    _i_abs_key = f"wt_i_abs_{_i_ver}"
    _i_pp_key  = f"wt_i_pp_{_i_ver}"

    def _wt_price_reset():
        st.session_state.wt_price_abs = float(current_price)
        st.session_state.wt_price_pct = 0.0
        st.session_state.wt_price_ver += 1

    def _wt_iv_reset():
        st.session_state.wt_iv_abs = float(base_iv)
        st.session_state.wt_iv_pp = 0.0
        st.session_state.wt_iv_ver += 1

    def _wt_date_reset():
        st.session_state.wt_scenario_date = _wt_min_date

    def _wt_reset_all():
        st.session_state.wt_price_abs = float(current_price)
        st.session_state.wt_price_pct = 0.0
        st.session_state.wt_price_ver += 1
        st.session_state.wt_iv_abs = float(base_iv)
        st.session_state.wt_iv_pp = 0.0
        st.session_state.wt_iv_ver += 1
        st.session_state.wt_scenario_date = _wt_min_date

    _hdr1, _hdr2 = st.columns([5, 1])
    with _hdr1:
        st.markdown("### Параметры сценария")
    with _hdr2:
        st.button("Сбросить всё", key="wt_reset_all_btn",
                  on_click=_wt_reset_all,
                  use_container_width=True,
                  help="Сбросить цену, IV и дату")

    st.markdown(
        "<div style='font-size:.75rem; color:#2c506d; "
        "font-weight:700; text-transform:uppercase; "
        "letter-spacing:.03em; margin-bottom:2px;'>Цена БА</div>",
        unsafe_allow_html=True)
    _pc1, _pc2, _pc3 = st.columns([1.6, 3.5, 0.6])
    with _pc1:
        _p_abs_val = st.number_input(
            "Цена, ₽",
            min_value=0.01, max_value=1e9,
            value=float(st.session_state.wt_price_abs),
            step=0.5, format="%.4f",
            key=_p_abs_key,
            label_visibility="collapsed")
    with _pc2:
        _p_pct_val = st.slider(
            "Изменение цены, %",
            min_value=-50.0, max_value=50.0,
            value=float(st.session_state.wt_price_pct),
            step=0.5,
            key=_p_pct_key,
            label_visibility="collapsed")
    with _pc3:
        st.button("↺", key="wt_price_reset_btn",
                  on_click=_wt_price_reset,
                  use_container_width=True,
                  help="Сбросить цену")

    if abs(_p_abs_val - st.session_state.wt_price_abs) > 1e-9:
        st.session_state.wt_price_abs = _p_abs_val
        _pct_calc = ((_p_abs_val / current_price - 1) * 100.0
                     if current_price > 0 else 0.0)
        st.session_state.wt_price_pct = max(-50.0, min(50.0, _pct_calc))
        st.session_state.wt_price_ver += 1
        st.session_state.pop(f"wt_p_abs_{_p_ver - 1}", None)
        st.session_state.pop(f"wt_p_pct_{_p_ver - 1}", None)
        st.rerun()
    elif abs(_p_pct_val - st.session_state.wt_price_pct) > 1e-9:
        st.session_state.wt_price_pct = _p_pct_val
        st.session_state.wt_price_abs = current_price * (1 + _p_pct_val / 100.0)
        st.session_state.wt_price_ver += 1
        st.session_state.pop(f"wt_p_abs_{_p_ver - 1}", None)
        st.session_state.pop(f"wt_p_pct_{_p_ver - 1}", None)
        st.rerun()

    st.markdown(
        "<div style='font-size:.75rem; color:#2c506d; "
        "font-weight:700; text-transform:uppercase; "
        "letter-spacing:.03em; margin-top:6px; margin-bottom:2px;'>"
        "Волатильность (IV)</div>",
        unsafe_allow_html=True)
    _ic1, _ic2, _ic3 = st.columns([1.6, 3.5, 0.6])
    with _ic1:
        _i_abs_val = st.number_input(
            "IV, %",
            min_value=0.1, max_value=500.0,
            value=float(st.session_state.wt_iv_abs),
            step=0.5, format="%.2f",
            key=_i_abs_key,
            label_visibility="collapsed")
    with _ic2:
        _i_pp_val = st.slider(
            "Изменение IV, п.п.",
            min_value=-30.0, max_value=30.0,
            value=float(st.session_state.wt_iv_pp),
            step=0.5,
            key=_i_pp_key,
            label_visibility="collapsed")
    with _ic3:
        st.button("↺", key="wt_iv_reset_btn",
                  on_click=_wt_iv_reset,
                  use_container_width=True,
                  help="Сбросить IV")

    if abs(_i_abs_val - st.session_state.wt_iv_abs) > 1e-9:
        st.session_state.wt_iv_abs = max(0.1, _i_abs_val)
        st.session_state.wt_iv_pp = max(-30.0, min(30.0, _i_abs_val - base_iv))
        st.session_state.wt_iv_ver += 1
        st.session_state.pop(f"wt_i_abs_{_i_ver - 1}", None)
        st.session_state.pop(f"wt_i_pp_{_i_ver - 1}", None)
        st.rerun()
    elif abs(_i_pp_val - st.session_state.wt_iv_pp) > 1e-9:
        st.session_state.wt_iv_pp = _i_pp_val
        st.session_state.wt_iv_abs = max(0.1, base_iv + _i_pp_val)
        st.session_state.wt_iv_ver += 1
        st.session_state.pop(f"wt_i_abs_{_i_ver - 1}", None)
        st.session_state.pop(f"wt_i_pp_{_i_ver - 1}", None)
        st.rerun()

    st.markdown(
        "<div style='font-size:.75rem; color:#2c506d; "
        "font-weight:700; text-transform:uppercase; "
        "letter-spacing:.03em; margin-top:6px; margin-bottom:2px;'>"
        "Дата сценария</div>",
        unsafe_allow_html=True)
    _dc1, _dc2, _dc3 = st.columns([1.6, 3.5, 0.6])
    with _dc1:
        st.date_input(
            "Дата",
            min_value=_wt_min_date,
            max_value=_wt_max_date,
            key="wt_scenario_date",
            label_visibility="collapsed")
    with _dc2:
        _days_delta = (st.session_state.wt_scenario_date - _wt_min_date).days
        if _wt_exp_dates:
            _alive_cnt = sum(1 for _d in _wt_exp_dates
                             if _d > st.session_state.wt_scenario_date)
            _expired_cnt = len(_wt_exp_dates) - _alive_cnt
            st.markdown(
                f"<div style='padding:6px 12px; background:#eef6fb; "
                f"border-radius:8px; font-size:.85rem; color:#1c5a7a; "
                f"border:1px solid #cfdfe9;'>"
                f"<b>{st.session_state.wt_scenario_date.strftime('%d.%m.%Y')}</b> "
                f"(+{_days_delta} дн.) &nbsp;·&nbsp; "
                f"живых опционов: <b style='color:#00a651;'>{_alive_cnt}</b> "
                f"/ истекших: <b style='color:#d32f2f;'>{_expired_cnt}</b>"
                f"</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div style='padding:6px 12px; background:#eef6fb; "
                f"border-radius:8px; font-size:.85rem; color:#1c5a7a; "
                f"border:1px solid #cfdfe9;'>"
                f"<b>{st.session_state.wt_scenario_date.strftime('%d.%m.%Y')}</b> "
                f"(+{_days_delta} дн.)"
                f"</div>",
                unsafe_allow_html=True)
    with _dc3:
        st.button("↺", key="wt_date_reset_btn",
                  on_click=_wt_date_reset,
                  use_container_width=True,
                  help="Сбросить дату на сегодня")

    st.markdown("---")
    st.markdown("### Рыночный сценарий (RVI)")

    _rvi_wt_data = fetch_rvi_current()
    _rvi_base = (_rvi_wt_data.get("value")
                 if _rvi_wt_data and _rvi_wt_data.get("value") is not None
                 else 30.0)
    _rvi_base_is_fallback = not (_rvi_wt_data and _rvi_wt_data.get("value") is not None)

    _wt_rvi_c1, _wt_rvi_c2 = st.columns(2)
    with _wt_rvi_c1:
        _rvi_shift = st.slider(
            "Изменение RVI, п.п.",
            min_value=-30.0, max_value=30.0, value=0.0, step=1.0,
            key="whatif_rvi_shift",
            help="Имитация рыночного стресса: +10 п.п. = паника, "
                 "−10 п.п. = успокоение")
    with _wt_rvi_c2:
        _rvi_correlation = st.slider(
            "Корреляция IV с RVI",
            min_value=0.0, max_value=1.0, value=0.7, step=0.05,
            key="whatif_rvi_correlation",
            help="Насколько сильно IV вашего инструмента следует за RVI. "
                 "0 = независимо, 1 = полностью коррелировано")

    _rvi_scenario = _rvi_base + _rvi_shift

    _rvi_baseline_note = " (fallback, ISS недоступен)" if _rvi_base_is_fallback else ""
    st.caption(
        f"RVI: {_rvi_base:.2f}%{_rvi_baseline_note} → "
        f"сценарий: {_rvi_scenario:.2f}% "
        f"({_rvi_shift:+.1f} п.п.) · "
        f"корреляция IV-RVI: {_rvi_correlation:.2f}"
    )

    st.markdown("---")

    new_price = float(st.session_state.wt_price_abs)
    new_iv = float(st.session_state.wt_iv_abs)
    days_shift = (st.session_state.wt_scenario_date - date.today()).days
    price_shift_pct = ((new_price / current_price - 1) * 100
                       if current_price > 0 else 0.0)
    iv_shift_pp = new_iv - base_iv

    comm_func = _calc_comm_ui

    pnl_now = _portfolio_value(
        positions, np.array([current_price]), 0, base_iv, comm_func)[0]
    pnl_new = _portfolio_value(
        positions, np.array([new_price]), days_shift, new_iv, comm_func)[0]
    pnl_delta = pnl_new - pnl_now

    _pnl_now_rvi = _portfolio_value_with_rvi(
        positions, np.array([current_price]), 0,
        base_iv, 0.0, _rvi_correlation, comm_func)[0]
    _pnl_new_rvi = _portfolio_value_with_rvi(
        positions, np.array([new_price]), days_shift,
        base_iv, _rvi_shift, _rvi_correlation, comm_func)[0]
    _pnl_delta_rvi = _pnl_new_rvi - _pnl_now_rvi

    st.markdown("### Результат сценария")
    _m1, _m2, _m3, _m4 = st.columns(4)
    with _m1:
        st.metric("Цена БА", f"{new_price:,.4f} ₽",
                  delta=f"{new_price - current_price:+,.4f} ₽")
    with _m2:
        st.metric("IV, %", f"{new_iv:.2f}%", delta=f"{iv_shift_pp:+.2f} п.п.")
    with _m3:
        st.metric("P&L сейчас", f"{pnl_now:+,.2f} ₽")
    with _m4:
        st.metric("P&L по сценарию", f"{pnl_new:+,.2f} ₽",
                  delta=f"{pnl_delta:+,.2f} ₽")

    _rvi_color_delta = "#00a651" if _pnl_delta_rvi >= 0 else "#d32f2f"
    st.markdown(
        f"<div style='background:#f0f4f8; border-radius:10px; "
        f"padding:10px 16px; margin-top:10px; font-size:.9rem; "
        f"display:flex; gap:24px; flex-wrap:wrap; align-items:center;'>"
        f"<span style='font-weight:700;'>С учётом RVI "
        f"({_rvi_shift:+.1f} п.п. × {_rvi_correlation:.2f}):</span>"
        f"<span>P&L по сценарию: <b>{_pnl_new_rvi:+,.2f} ₽</b></span>"
        f"<span style='color:{_rvi_color_delta};'>"
        f"Дельта: <b>{_pnl_delta_rvi:+,.2f} ₽</b></span>"
        f"</div>",
        unsafe_allow_html=True)

    _tot_delta = _tot_gamma = _tot_vega = _tot_theta = 0.0
    for p in positions:
        q = int(p.get("Кол-во", 0))
        _tot_delta += (p.get("Дельта") or 0) * q
        _tot_gamma += (p.get("Гамма")  or 0) * q
        _tot_vega  += (p.get("Вега")   or 0) * q
        _tot_theta += (p.get("Тета")   or 0) * q

    _dS = new_price - current_price
    contrib_delta = _tot_delta * _dS
    contrib_vega  = _tot_vega * iv_shift_pp
    contrib_theta = _tot_theta * days_shift
    contrib_gamma = 0.5 * _tot_gamma * (_dS ** 2)

    st.markdown("#### Компоненты изменения P&L (первое приближение)")
    _c1, _c2, _c3, _c4 = st.columns(4)
    _c1.metric("От Δ-цены (delta)", f"{contrib_delta:+,.2f} ₽")
    _c2.metric("От Γ (gamma)",      f"{contrib_gamma:+,.2f} ₽")
    _c3.metric("От IV (vega)",      f"{contrib_vega:+,.2f} ₽")
    _c4.metric("От времени (theta)", f"{contrib_theta:+,.2f} ₽")

    st.markdown("---")

    st.markdown("### Профиль P&L на выбранный сценарий")
    _strikes_wa = sorted({float(p["Страйк"]) for p in positions
                           if p.get("Страйк") is not None})
    if not _strikes_wa:
        _strikes_wa = [current_price]
    _s_min_wa = min(_strikes_wa + [current_price]) * 0.75
    _s_max_wa = max(_strikes_wa + [current_price]) * 1.25
    S_wa = np.linspace(_s_min_wa, _s_max_wa, 400)

    pnl_base_curve = _portfolio_value(
        positions, S_wa, 0, base_iv, comm_func)
    pnl_scen_curve = _portfolio_value(
        positions, S_wa, days_shift, new_iv, comm_func)
    pnl_rvi_curve = _portfolio_value_with_rvi(
        positions, S_wa, days_shift, base_iv,
        _rvi_shift, _rvi_correlation, comm_func)

    fig_wa = go.Figure()
    fig_wa.add_trace(go.Scatter(
        x=S_wa, y=pnl_base_curve, mode="lines",
        name="Текущий IV и время",
        line=dict(color="#9aa7b3", width=2, dash="dot"),
        hovertemplate="S: %{x:.2f}<br>P&L: %{y:+,.2f} ₽<extra></extra>"))
    fig_wa.add_trace(go.Scatter(
        x=S_wa, y=pnl_scen_curve, mode="lines",
        name=f"Сценарий (ΔS={price_shift_pct:+.1f}%, ΔIV={iv_shift_pp:+.1f}пп, +{days_shift}д)",
        line=dict(color="#1e5a7a", width=3),
        hovertemplate="S: %{x:.2f}<br>P&L: %{y:+,.2f} ₽<extra></extra>"))
    if abs(_rvi_shift) > 0.01:
        fig_wa.add_trace(go.Scatter(
            x=S_wa, y=pnl_rvi_curve, mode="lines",
            name=f"RVI-сценарий (ΔRVI={_rvi_shift:+.1f}пп, corr={_rvi_correlation:.2f})",
            line=dict(color="#9c27b0", width=2, dash="dash"),
            hovertemplate="S: %{x:.2f}<br>P&L: %{y:+,.2f} ₽<extra></extra>"))
    fig_wa.add_hline(y=0, line_dash="dot", line_color="#7f9bb3", line_width=1)
    fig_wa.add_vline(x=current_price, line_dash="dash",
                     line_color="#1e88e5", line_width=1.5,
                     annotation_text=f"Тек. {current_price:.2f}",
                     annotation_position="top")
    fig_wa.add_vline(x=new_price, line_dash="dash",
                     line_color="#00a651", line_width=1.5,
                     annotation_text=f"Сцен. {new_price:.2f}",
                     annotation_position="bottom")
    fig_wa.add_trace(go.Scatter(
        x=[current_price], y=[pnl_now], mode="markers",
        marker=dict(size=14, color="#1e88e5", symbol="circle",
                    line=dict(color="white", width=2)),
        name="Сейчас",
        hovertemplate="Сейчас<br>S: %{x:.2f}<br>P&L: %{y:+,.2f} ₽<extra></extra>"))
    fig_wa.add_trace(go.Scatter(
        x=[new_price], y=[pnl_new], mode="markers",
        marker=dict(size=14, color="#00a651", symbol="diamond",
                    line=dict(color="white", width=2)),
        name="По сценарию",
        hovertemplate="Сценарий<br>S: %{x:.2f}<br>P&L: %{y:+,.2f} ₽<extra></extra>"))

    fig_wa.update_layout(
        title=f"P&L позиции — {_asset}",
        xaxis_title="Цена БА, ₽", yaxis_title="P&L, ₽",
        height=460, margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="left", x=0),
        hovermode="x unified")
    st.plotly_chart(fig_wa, use_container_width=True)

    st.markdown("---")

    st.markdown("### Тепловая карта P&L (цена БА × IV)")
    _h_c1, _h_c2 = st.columns(2)
    with _h_c1:
        _grid_pct = st.slider("Диапазон цены ±, %", 5, 50, 20, 5,
                              key="whatif_grid_pct")
    with _h_c2:
        _grid_iv = st.slider("Диапазон IV ±, п.п.", 2, 30, 10, 1,
                              key="whatif_grid_iv")

    S_grid = np.linspace(current_price * (1 - _grid_pct / 100),
                         current_price * (1 + _grid_pct / 100), 41)
    IV_grid = np.linspace(max(0.5, base_iv - _grid_iv),
                          base_iv + _grid_iv, 41)

    Z = np.zeros((len(IV_grid), len(S_grid)))
    for _i, _ivv in enumerate(IV_grid):
        Z[_i, :] = _portfolio_value(
            positions, S_grid, days_shift, _ivv, comm_func)

    fig_hm = go.Figure(data=go.Heatmap(
        x=S_grid, y=IV_grid, z=Z,
        colorscale=[
            [0.0, "#7b0d0d"], [0.35, "#d32f2f"],
            [0.5, "#ffffff"],
            [0.65, "#00a651"], [1.0, "#064d23"],
        ],
        zmid=0,
        colorbar=dict(title="P&L, ₽"),
        hovertemplate="Цена: %{x:.2f} ₽<br>IV: %{y:.2f}%<br>P&L: %{z:+,.2f} ₽<extra></extra>"))
    fig_hm.add_trace(go.Scatter(
        x=[current_price], y=[base_iv], mode="markers",
        marker=dict(size=14, color="#1e88e5", symbol="x",
                    line=dict(color="white", width=2)),
        name="Сейчас",
        hovertemplate="Сейчас<br>Цена: %{x:.2f}<br>IV: %{y:.2f}%<extra></extra>"))
    if price_shift_pct != 0 or iv_shift_pp != 0:
        fig_hm.add_trace(go.Scatter(
            x=[new_price], y=[new_iv], mode="markers",
            marker=dict(size=14, color="#00a651", symbol="diamond",
                        line=dict(color="white", width=2)),
            name="Сценарий",
            hovertemplate="Сценарий<br>Цена: %{x:.2f}<br>IV: %{y:.2f}%<extra></extra>"))
    fig_hm.update_layout(
        title=f"P&L позиции — {_asset} (+{days_shift} дней)",
        xaxis_title="Цена БА, ₽", yaxis_title="IV, %",
        height=520, margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="left", x=0))
    st.plotly_chart(fig_hm, use_container_width=True)

    st.caption("Тепловая карта показывает P&L по всей комбинации "
               "«цена × IV» при фиксированном сдвиге времени.")


# ==================================================================
# ============ ВКЛАДКА 5: HEATMAP IV ==============================
# ==================================================================
@st.fragment
def _render_heatmap_tab():
    st.header("Heatmap IV по сериям и страйкам")
    st.caption("Тепловая карта подразумеваемой волатильности по всем "
               "доступным сериям и страйкам выбранного БА. "
               "Помогает увидеть структуру срочной волатильности "
               "(term structure) и улыбку.")

    _hm_asset = st.session_state.get("pos_asset", "")
    _hm_cat = st.session_state.get("pos_category", "")

    if not _hm_asset:
        st.warning("Сначала выберите актив и категорию на вкладке «Позиция».")
        return

    _hm1, _hm2 = st.columns([4, 2])
    with _hm1:
        st.info(f"Актив: {_hm_asset} · Категория: {_hm_cat} "
                f"(из вкладки «Позиция»)")
    with _hm2:
        _hm_build = st.button("Построить Heatmap",
                               type="primary",
                               use_container_width=True,
                               key="hm_build_btn")

    _hm_cache_key_base = f"_hm_cache_{_hm_asset}_{_hm_cat}"

    if not _hm_build and _hm_cache_key_base not in st.session_state:
        st.info("Нажмите «Построить Heatmap» для загрузки данных "
                "(может занять 10–30 секунд).")
        return

    _cache_key = _hm_cache_key_base

    if _hm_build or _cache_key not in st.session_state:
        with st.spinner(f"Загрузка серий и досок для {_hm_asset}…"):
            try:
                _series_all = fetch_optionseries(_hm_asset, _hm_cat) or []
            except Exception as e:
                st.error(f"Не удалось получить серии: {e}")
                return
            if not _series_all:
                st.warning(f"ISS не вернул серий для {_hm_asset}")
                return

            _series_sorted = sorted(_series_all, key=lambda x: x.get("expiry", ""))[:12]

            _hm_rows = []
            _progress = st.progress(0.0, text="Загрузка досок…")
            _n = len(_series_sorted)
            _today = date.today()
            for _i, _s in enumerate(_series_sorted):
                try:
                    _b = fetch_optionboard(_hm_asset, _hm_cat, _s["code"])
                except Exception:
                    _b = None
                if _b:
                    try:
                        _d = datetime.strptime(_s["expiry"], "%Y-%m-%d").date()
                        _days = (_d - _today).days
                    except Exception:
                        _days = None
                    _seen_strikes = {}
                    for _side_key in ("call", "put"):
                        for _row in (_b.get(_side_key) or []):
                            _k = _row.get("strike")
                            _iv = _row.get("volatility")
                            if _k is None or _iv is None:
                                continue
                            try:
                                _kf = float(_k)
                                _ivf = float(_iv)
                            except (TypeError, ValueError):
                                continue
                            if not (0 < _ivf < 500):
                                continue
                            if _kf in _seen_strikes:
                                _seen_strikes[_kf] = (_seen_strikes[_kf] + _ivf) / 2.0
                            else:
                                _seen_strikes[_kf] = _ivf
                    for _kf, _ivf in _seen_strikes.items():
                        _hm_rows.append({
                            "expiry": _s["expiry"],
                            "days_to": _days,
                            "strike": _kf,
                            "iv": _ivf,
                        })
                _progress.progress((_i + 1) / _n,
                                    text=f"Серия {_i+1}/{_n}…")
            _progress.empty()

            st.session_state[_cache_key] = _hm_rows
            st.session_state[f"{_cache_key}_series"] = _series_sorted

    _hm_rows = st.session_state.get(_cache_key, [])
    _series_sorted = st.session_state.get(f"{_cache_key}_series", [])

    if not _hm_rows:
        st.warning("Не удалось получить данные IV ни по одной серии.")
        return

    _df_hm = pd.DataFrame(_hm_rows)

    _current_price_hm = _get_current_market_price_for_asset(_hm_asset, _hm_cat)

    st.markdown("---")
    _oc1, _oc2, _oc3 = st.columns(3)
    with _oc1:
        _limit_strikes_around = st.slider(
            "Страйков вокруг центрального (0 = все)",
            min_value=0, max_value=30, value=12, step=1,
            key="hm_limit_strikes",
            help="Ограничить диапазон страйков вокруг текущей цены БА.")
    with _oc2:
        _show_values = st.toggle("Показывать значения IV в ячейках",
                                  value=True, key="hm_show_values")
    with _oc3:
        _hm_color_scale = st.selectbox(
            "Цветовая шкала",
            ["RdYlGn_r", "Viridis", "Cividis", "Turbo", "Plasma"],
            index=0, key="hm_colorscale")

    if _limit_strikes_around > 0 and _current_price_hm is not None:
        _all_strikes_hm = sorted(_df_hm["strike"].unique())
        _nearest_idx = min(
            range(len(_all_strikes_hm)),
            key=lambda i: abs(_all_strikes_hm[i] - _current_price_hm))
        _lo = max(0, _nearest_idx - _limit_strikes_around)
        _hi = min(len(_all_strikes_hm),
                  _nearest_idx + _limit_strikes_around + 1)
        _strikes_keep = _all_strikes_hm[_lo:_hi]
        _df_hm = _df_hm[_df_hm["strike"].isin(_strikes_keep)]

    if _df_hm.empty:
        st.warning("После фильтрации не осталось данных.")
        return

    _expiries_sorted = sorted(_df_hm["expiry"].unique())
    _strikes_sorted = sorted(_df_hm["strike"].unique())

    _Z = np.full((len(_expiries_sorted), len(_strikes_sorted)), np.nan)
    for _i, _exp in enumerate(_expiries_sorted):
        _sub = _df_hm[_df_hm["expiry"] == _exp]
        for _j, _k in enumerate(_strikes_sorted):
            _v = _sub.loc[_sub["strike"] == _k, "iv"]
            if not _v.empty:
                _Z[_i, _j] = float(_v.iloc[0])

    _exp_labels = []
    _today = date.today()
    for _e in _expiries_sorted:
        try:
            _d = datetime.strptime(_e, "%Y-%m-%d").date()
            _dd = (_d - _today).days
            _exp_labels.append(f"{_d.strftime('%d.%m.%y')} ({_dd})")
        except Exception:
            _exp_labels.append(str(_e))

    _strike_labels = [_fmt_strike(k, _hm_cat) for k in _strikes_sorted]

    _hover_text = []
    for _i, _exp in enumerate(_expiries_sorted):
        _row_hover = []
        for _j, _k in enumerate(_strikes_sorted):
            _v = _Z[_i, _j]
            _v_str = f"{_v:.2f}%" if not np.isnan(_v) else "—"
            _row_hover.append(
                f"Серия: {_exp_labels[_i]}<br>"
                f"Страйк: {_strike_labels[_j]}<br>"
                f"IV: {_v_str}")
        _hover_text.append(_row_hover)

    fig_hm = go.Figure(data=go.Heatmap(
        z=_Z,
        x=_strike_labels,
        y=_exp_labels,
        colorscale=_hm_color_scale,
        hovertemplate="%{text}<extra></extra>",
        text=_hover_text,
        colorbar=dict(title="IV, %"),
        zmin=float(np.nanmin(_Z)) if not np.all(np.isnan(_Z)) else None,
        zmax=float(np.nanmax(_Z)) if not np.all(np.isnan(_Z)) else None,
    ))

    if _show_values:
        _annotations = []
        for _i in range(len(_expiries_sorted)):
            for _j in range(len(_strikes_sorted)):
                _v = _Z[_i, _j]
                if np.isnan(_v):
                    _txt = "—"
                else:
                    _txt = f"{_v:.1f}"
                _annotations.append(dict(
                    x=_strike_labels[_j], y=_exp_labels[_i],
                    text=_txt, showarrow=False,
                    font=dict(size=10, color="#111")))
        fig_hm.update_layout(annotations=_annotations)

    if _current_price_hm is not None:
        try:
            _nearest_strike_label = min(
                _strike_labels,
                key=lambda s: abs(float(s) - _current_price_hm))
        except Exception:
            _nearest_strike_label = None

        if _nearest_strike_label is not None:
            fig_hm.add_shape(
                type="line",
                xref="x", yref="paper",
                x0=_nearest_strike_label, x1=_nearest_strike_label,
                y0=0, y1=1,
                line=dict(color="#1e88e5", width=2, dash="dash"),
                layer="above")
            fig_hm.add_annotation(
                x=_nearest_strike_label, y=1,
                xref="x", yref="paper",
                text=f"БА≈{_current_price_hm:.2f}",
                showarrow=False,
                yshift=12,
                font=dict(color="#1e88e5", size=11,
                          family="Arial Black"),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#1e88e5", borderwidth=1)
    _fig_h = max(400, 40 + 42 * len(_expiries_sorted))
    fig_hm.update_layout(
        title=f"Heatmap IV — {_hm_asset} ({_hm_cat})",
        xaxis_title="Страйк",
        yaxis_title="Серия (дата исп.)",
        height=_fig_h,
        margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig_hm, use_container_width=True)

    _rvi_hm_data = fetch_rvi_current()
    _rvi_hm = _rvi_hm_data.get("value") if _rvi_hm_data else None

    if _rvi_hm is not None and not _df_hm.empty:
        _hm_avg_iv = float(_df_hm["iv"].mean())
        _hm_ratio = _hm_avg_iv / _rvi_hm if _rvi_hm > 0 else None
        _hm_zone = classify_iv_vs_rvi(_hm_avg_iv, _rvi_hm)

        _hm_zone_label = _hm_zone["zone_label"] if _hm_zone else "—"
        _hm_zone_color = _hm_zone["zone_color"] if _hm_zone else "#7a7a7a"

        _ratio_str = f"{_hm_ratio:.2f}×" if _hm_ratio is not None else "—"
        st.markdown(
            f"<div style='background:#f0f4f8; border-radius:8px; "
            f"padding:10px 14px; margin:10px 0; font-size:.9rem; "
            f"display:flex; gap:24px; flex-wrap:wrap; align-items:center;'>"
            f"<span><b>RVI:</b> {_rvi_hm:.2f}%</span>"
            f"<span><b>Средняя IV на доске:</b> {_hm_avg_iv:.2f}%</span>"
            f"<span><b>Ratio:</b> {_ratio_str}</span>"
            f"<span style='color:{_hm_zone_color}; font-weight:700;'>"
            f"{_hm_zone_label}</span>"
            f"</div>",
            unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Сводные метрики по сериям")

    _summary_rows = []
    for _exp in _expiries_sorted:
        _sub = _df_hm[_df_hm["expiry"] == _exp]
        _iv_min = _sub["iv"].min() if not _sub.empty else np.nan
        _iv_max = _sub["iv"].max() if not _sub.empty else np.nan
        _iv_mean = _sub["iv"].mean() if not _sub.empty else np.nan
        _iv_std = _sub["iv"].std() if len(_sub) > 1 else 0.0
        try:
            _d = datetime.strptime(_exp, "%Y-%m-%d").date()
            _dd = (_d - _today).days
        except Exception:
            _dd = None
        _summary_rows.append({
            "Серия": _exp,
            "До эксп., дн.": _dd,
            "IV min, %": round(_iv_min, 2) if not np.isnan(_iv_min) else None,
            "IV max, %": round(_iv_max, 2) if not np.isnan(_iv_max) else None,
            "IV сред., %": round(_iv_mean, 2) if not np.isnan(_iv_mean) else None,
            "σ IV": round(_iv_std, 2),
            "Страйков": len(_sub),
        })

    _df_summary = pd.DataFrame(_summary_rows)
    st.dataframe(_df_summary, use_container_width=True, hide_index=True,
                  height=min(120 + 35 * len(_df_summary), 400))

    st.caption("Как читать: строки — серии (чем ниже, тем дальше "
               "экспирация), столбцы — страйки. Вертикальный градиент "
               "показывает term structure (срочную структуру) IV; "
               "горизонтальный — улыбку волатильности внутри серии.")


# ==================================================================
# ============ ВКЛАДКА 6: IV RANK / ДЕЦИЛИ ========================
# ==================================================================
@st.fragment
def _render_ivrank_tab():
    st.header("IV Rank / Децили и рекомендации")
    st.caption("Оценка текущей подразумеваемой волатильности относительно "
               "её исторического диапазона.")

    _iv_asset = st.session_state.get("pos_asset", "")
    _iv_cat = st.session_state.get("pos_category", "")

    if not _iv_asset:
        st.warning("Сначала выберите актив и категорию на вкладке «Позиция».")
        return

    st.info(f"Актив: {_iv_asset} · Категория: {_iv_cat} "
            f"(из вкладки «Позиция»)")

    _series_for_iv = []
    try:
        _series_for_iv = fetch_optionseries(_iv_asset, _iv_cat) or []
    except Exception as e:
        st.error(f"Не удалось получить серии: {e}")
        return

    if not _series_for_iv:
        st.warning(f"ISS не вернул серий для {_iv_asset}")
        return

    _series_sorted_iv = sorted(_series_for_iv, key=lambda x: x.get("expiry", ""))
    _iv_series_labels = [format_series_label(s["expiry"])
                          for s in _series_sorted_iv]
    _iv_series_chosen_label = st.selectbox(
        "Опционная серия", _iv_series_labels, index=0, key="ivr_series_select")
    _iv_chosen_idx = _iv_series_labels.index(_iv_series_chosen_label)
    _iv_chosen = _series_sorted_iv[_iv_chosen_idx]
    _iv_chosen_code = _iv_chosen["code"]
    _iv_chosen_expiry = _iv_chosen["expiry"]

    st.markdown("---")

    with st.spinner("Загрузка доски опционов…"):
        _board_iv = _get_board_for_analytics(_iv_asset, _iv_cat, _iv_chosen_code)

    if not _board_iv:
        st.warning("Не удалось загрузить доску опционов для этой серии.")
        return

    _iv_central = _board_iv.get("central_strike")
    _current_iv = _weighted_avg_iv(_board_iv, _iv_central)
    if _current_iv is None:
        st.warning("Не удалось вычислить текущую IV (нет данных).")
        return

    _store_iv_snapshot(_iv_asset, _iv_cat, _iv_chosen_code, _current_iv)

    st.markdown("### 1) Текущая IV vs. историческая волатильность")

    # [PATCH 3] Инициализируем _df_bars_iv пустым DataFrame —
    # он будет использоваться в _remember_volatility_history ниже,
    # даже если запрос баров почему-то не выполнится.
    _hist_vol_map = {}
    _df_bars_iv = pd.DataFrame()

    try:
        _iv_eng, _iv_mkt = _get_engine_market(_iv_cat)
        _iv_secid = resolve_underlying_secid(_iv_asset, _iv_cat)
        if _iv_secid:
            _df_bars_iv = fetch_bars(_iv_secid, interval=24, days=180,
                                      engine=_iv_eng, market=_iv_mkt)
            if not _df_bars_iv.empty:
                _ret = np.log(_df_bars_iv["close"] /
                              _df_bars_iv["close"].shift(1)).dropna()
                for _win, _key in [(10, "hv10"), (20, "hv20"),
                                   (50, "hv50"), (100, "hv100")]:
                    if len(_ret) >= _win:
                        _hv = float(_ret.tail(_win).std() * np.sqrt(252) * 100)
                        _hist_vol_map[_key] = _hv
    except Exception:
        pass

    # [PATCH 3] История RVI загружается отдельно и кешируется существующей
    # функцией. Ошибка RVI не должна мешать сохранению рассчитанной HV.
    try:
        _rvi_history_frame = fetch_rvi_history(days=365)
    except Exception:
        _rvi_history_frame = None

    _remember_volatility_history(
        _iv_asset,
        _iv_cat,
        _df_bars_iv,
        _rvi_history_frame,
    )

    _m1, _m2, _m3, _m4, _m5 = st.columns(5)
    _m1.metric("Текущая IV", f"{_current_iv:.2f}%")
    _m2.metric("HV 10д", f"{_hist_vol_map.get('hv10', float('nan')):.2f}%"
               if "hv10" in _hist_vol_map else "—")
    _m3.metric("HV 20д", f"{_hist_vol_map.get('hv20', float('nan')):.2f}%"
               if "hv20" in _hist_vol_map else "—")
    _m4.metric("HV 50д", f"{_hist_vol_map.get('hv50', float('nan')):.2f}%"
               if "hv50" in _hist_vol_map else "—")
    _m5.metric("HV 100д", f"{_hist_vol_map.get('hv100', float('nan')):.2f}%"
               if "hv100" in _hist_vol_map else "—")

    _hv_avg = np.mean(list(_hist_vol_map.values())) if _hist_vol_map else None
    if _hv_avg is not None:
        _iv_hv_spread = _current_iv - _hv_avg
        if _iv_hv_spread > 3:
            st.warning(f"IV заметно выше средней HV на "
                        f"{_iv_hv_spread:+.2f} п.п. — "
                        f"опционы дорогие, кандидат на продажу волатильности.")
        elif _iv_hv_spread < -3:
            st.info(f"IV заметно ниже средней HV на "
                     f"{_iv_hv_spread:+.2f} п.п. — "
                     f"опционы дешёвые, кандидат на покупку волатильности.")
        else:
            st.success(f"IV около средней HV (дифференциал "
                        f"{_iv_hv_spread:+.2f} п.п.) — "
                        f"явного преимущества нет.")

    _rvi_rank_data = fetch_rvi_current()
    _rvi_rank = _rvi_rank_data.get("value") if _rvi_rank_data else None

    if _rvi_rank is not None:
        st.markdown("### 1b) IV vs RVI (рыночный фон)")
        _col_r1, _col_r2, _col_r3 = st.columns(3)
        with _col_r1:
            st.metric("RVI (рынок)", f"{_rvi_rank:.2f}%")
        with _col_r2:
            st.metric("IV инструмента", f"{_current_iv:.2f}%")
        with _col_r3:
            _spread_rvi = _current_iv - _rvi_rank
            _ratio_rvi = (_current_iv / _rvi_rank) if _rvi_rank > 0 else 0.0
            st.metric("Спред / Ratio",
                      f"{_spread_rvi:+.2f} п.п. / {_ratio_rvi:.2f}×")

        _zone_rvi = classify_iv_vs_rvi(_current_iv, _rvi_rank)
        if _zone_rvi:
            st.markdown(
                f"<div style='padding:10px 14px; border-radius:8px; "
                f"background:{_zone_rvi['zone_color']}20; "
                f"border-left:4px solid {_zone_rvi['zone_color']}; margin:8px 0;'>"
                f"<b>{_zone_rvi['zone_label']}</b> — {_zone_rvi['action']}</div>",
                unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("### 2) IV Rank / IV Percentile")

    _hist_key = f"{_iv_asset}|{_iv_cat}|{_iv_chosen_code}"
    _hist_bucket = st.session_state.get("_iv_history", {}).get(_hist_key, [])

    if len(_hist_bucket) < 5:
        st.warning(
            f"Недостаточно исторических данных по IV для этой серии: "
            f"собрано {len(_hist_bucket)} точек. "
            f"Данные накапливаются автоматически при каждом открытии "
            f"этой вкладки. Для полноценного IV Rank нужно ≥ 20 точек. "
            f"Пока используется только сравнение с HV.")
        if _hist_vol_map:
            _hv_min = min(_hist_vol_map.values())
            _hv_max = max(_hist_vol_map.values())
            if _hv_max > _hv_min:
                _iv_rank_fb = (_current_iv - _hv_min) / (_hv_max - _hv_min) * 100
                st.info(f"Ориентировочный IV Rank (по диапазону HV): "
                         f"{_iv_rank_fb:.1f}%")
        _render_iv_recommendations(
            iv_rank=None, iv_pct=None, iv_current=_current_iv,
            hv_avg=_hv_avg, hist_available=False)
        return

    _iv_values = np.array([v for _, v in _hist_bucket], dtype=float)
    _iv_min = float(np.min(_iv_values))
    _iv_max = float(np.max(_iv_values))
    _iv_rank = ((_current_iv - _iv_min) / (_iv_max - _iv_min) * 100) \
        if _iv_max > _iv_min else 50.0
    _iv_pct = float(np.mean(_iv_values <= _current_iv) * 100)

    try:
        _deciles = np.percentile(_iv_values, np.arange(0, 101, 10))
        _decile_of_iv = int(np.searchsorted(_deciles, _current_iv, side="right") - 1)
        _decile_of_iv = max(0, min(9, _decile_of_iv))
    except Exception:
        _deciles = None
        _decile_of_iv = None

    _r1, _r2, _r3, _r4 = st.columns(4)
    _r1.metric("IV Rank", f"{_iv_rank:.1f}%")
    _r2.metric("IV Percentile", f"{_iv_pct:.1f}%")
    _r3.metric("Мин IV (истор.)", f"{_iv_min:.2f}%")
    _r4.metric("Макс IV (истор.)", f"{_iv_max:.2f}%")

    if _deciles is not None:
        st.markdown("#### Положение текущей IV в децилях")
        _fig_dec = go.Figure()
        _fig_dec.add_trace(go.Bar(
            x=[f"D{i+1}" for i in range(10)],
            y=np.diff(_deciles),
            marker_color=[
                "#00a651" if i == _decile_of_iv else "#b0c4d4"
                for i in range(10)
            ],
            text=[f"{_deciles[i]:.1f}–{_deciles[i+1]:.1f}%"
                  for i in range(10)],
            textposition="outside",
            hovertemplate="Дециль %{x}<br>Диапазон: %{text}<extra></extra>"))
        _fig_dec.add_hline(
            y=float(_current_iv - _deciles[_decile_of_iv]),
            line=dict(color="#d32f2f", width=3, dash="dash"),
            annotation_text=f"Текущая IV = {_current_iv:.2f}%",
            annotation_position="top right")
        _fig_dec.update_layout(
            title=f"Распределение IV по децилям ({len(_iv_values)} наблюдений)",
            xaxis_title="Дециль", yaxis_title="Ширина дециля, п.п.",
            height=360, margin=dict(l=20, r=20, t=60, b=20),
            showlegend=False)
        st.plotly_chart(_fig_dec, use_container_width=True)

        st.caption(
            f"Текущая IV {_current_iv:.2f}% попадает в "
            f"{_decile_of_iv+1}-й дециль "
            f"(диапазон {_deciles[_decile_of_iv]:.2f}–"
            f"{_deciles[_decile_of_iv+1]:.2f}%).")

    st.markdown("---")

    _render_iv_recommendations(
        iv_rank=_iv_rank, iv_pct=_iv_pct, iv_current=_current_iv,
        hv_avg=_hv_avg, hist_available=True,
        decile_of_iv=_decile_of_iv)


def _render_iv_recommendations(iv_rank, iv_pct, iv_current, hv_avg,
                                hist_available=True, decile_of_iv=None):
    st.markdown("### 3) Рекомендации")

    _zone = None
    _zone_color = "#333"
    _zone_label = "—"

    if hist_available and iv_rank is not None:
        if iv_rank <= 20:
            _zone = "low"
            _zone_label = "НИЗКАЯ IV (IV Rank ≤ 20%)"
            _zone_color = "#1e88e5"
        elif iv_rank <= 40:
            _zone = "low_mid"
            _zone_label = "НИЖЕ СРЕДНЕГО (IV Rank 20–40%)"
            _zone_color = "#00a651"
        elif iv_rank <= 60:
            _zone = "mid"
            _zone_label = "СРЕДНЯЯ IV (IV Rank 40–60%)"
            _zone_color = "#7a7a7a"
        elif iv_rank <= 80:
            _zone = "high_mid"
            _zone_label = "ВЫШЕ СРЕДНЕГО (IV Rank 60–80%)"
            _zone_color = "#e6a500"
        else:
            _zone = "high"
            _zone_label = "ВЫСОКАЯ IV (IV Rank > 80%)"
            _zone_color = "#d32f2f"

    if _zone is None and hv_avg is not None:
        _spread = iv_current - hv_avg
        if _spread <= -3:
            _zone = "low"
            _zone_label = "IV НИЖЕ HV (по дифф.)"
            _zone_color = "#1e88e5"
        elif _spread >= 3:
            _zone = "high"
            _zone_label = "IV ВЫШЕ HV (по дифф.)"
            _zone_color = "#d32f2f"
        else:
            _zone = "mid"
            _zone_label = "IV около HV"
            _zone_color = "#7a7a7a"

    st.markdown(
        f"<div style='padding:14px 18px; border-radius:12px; "
        f"background:{_zone_color}20; border-left:6px solid {_zone_color}; "
        f"margin-bottom:14px;'>"
        f"<div style='font-size:1.05rem; font-weight:800; color:{_zone_color};'>"
        f"{_zone_label}</div></div>",
        unsafe_allow_html=True)

    if _zone == "low":
        st.markdown("#### Стратегии: покупка волатильности")
        st.markdown("""
**Логика:** IV в нижней части исторического диапазона — опционы
относительно дешёвые. Ожидаем роста IV → выгодны длинные опционные
позиции.

**Стратегии:**
| Стратегия | Комментарий |
|---|---|
| **Long Straddle** | Buy Call + Buy Put на одном страйке. |
| **Long Strangle** | Дешевле стрэддла, но требует большего движения. |
| **Обратный спрэд (Call / Put)** | Неограниченный потенциал с одной стороны. |
| **Календарный спрэд** | Продажа короткого, покупка длинного на том же страйке. |

**Стопы:** для стрэддлов — 50–60% от уплаченной премии.
""")
    elif _zone == "low_mid":
        st.markdown("#### Стратегии: умеренная покупка волатильности")
        st.markdown("""
IV ниже среднего, но не на дне диапазона. Возможны осторожные
покупки волатильности при наличии катализатора.

**Подходящие инструменты:**
- Long Straddle — с приоритетом на событийные опционы;
- Long Call / Long Put;
- Bull/Bear спреды с перевесом длинной стороны.

**Не рекомендуется:** продажа волатильности (мало премии).
""")
    elif _zone == "mid":
        st.markdown("#### Стратегии: нейтральная зона")
        st.markdown("""
IV в середине диапазона — явного преимущества ни у покупателя,
ни у продавца волатильности нет.

**Рекомендуется:**
- Направленные стратегии;
- Работать по технической картине БА;
- Искать наклон волатильности (вкладка «Детектор Skew»).

**Не рекомендуется:** ставить только на движение IV.
""")
    elif _zone == "high_mid":
        st.markdown("#### Стратегии: умеренная продажа волатильности")
        st.markdown("""
IV выше среднего — опционы относительно дорогие.

**Стратегии:**
| Стратегия | Комментарий |
|---|---|
| **Short Strangle** | Продажа Call и Put «вне денег». |
| **Short Straddle** | Максимум премии, узкий диапазон прибыли. |
| **Iron Condor** | Ограниченный риск. |
| **Пропорциональный спрэд** | Продажа 2 опционов + покупка 1 (1-к-2). |

Проверьте вкладку «Детектор Skew» — нет ли события.
""")
    elif _zone == "high":
        st.warning(
            "Высокая IV может отражать реальное ожидание "
            "крупного события (поглощение, суд, FDA, отчёт). Перед продажей "
            "волатильности проверьте новости и посмотрите наклон IV "
            "(вкладка «Детектор Skew»).")
        st.markdown("#### Стратегии: продажа волатильности (с осторожностью)")
        st.markdown("""
**Стратегии:**
- **Short Strangle / Short Straddle** — с контролем риска;
- **Iron Condor** — ограниченный риск;
- **Крылья** — покупка дешёвых OTM для защиты.

**Правила:**
- Продавайте IV, когда она у верхней границы диапазона;
- Если IV пробивает диапазон на новые максимумы — прекращайте;
- Используйте дельта- и гамма-нейтральные позиции.
""")


# ==================================================================
# ============ ВКЛАДКА 7: ДЕТЕКТОР SKEW ===========================
# ==================================================================
@st.fragment
def _render_skew_tab():
    st.header("Детектор Skew и рекомендации")
    st.caption("Анализ наклона волатильности (volatility skew). "
               "Критерий наличия наклона: σ/μ ≥ 15%.")

    _sk_asset = st.session_state.get("pos_asset", "")
    _sk_cat = st.session_state.get("pos_category", "")

    if not _sk_asset:
        st.warning("Сначала выберите актив и категорию на вкладке «Позиция».")
        return

    st.info(f"Актив: {_sk_asset} · Категория: {_sk_cat} "
            f"(из вкладки «Позиция»)")

    try:
        _sk_series_all = fetch_optionseries(_sk_asset, _sk_cat) or []
    except Exception as e:
        st.error(f"Не удалось получить серии: {e}")
        return

    if not _sk_series_all:
        st.warning(f"ISS не вернул серий для {_sk_asset}")
        return

    _sk_series_sorted = sorted(_sk_series_all, key=lambda x: x.get("expiry", ""))
    _sk_series_labels = [format_series_label(s["expiry"])
                          for s in _sk_series_sorted]
    _sk_chosen_label = st.selectbox(
        "Опционная серия", _sk_series_labels, index=0, key="sk_series_select")
    _sk_chosen_idx = _sk_series_labels.index(_sk_chosen_label)
    _sk_chosen = _sk_series_sorted[_sk_chosen_idx]
    _sk_chosen_code = _sk_chosen["code"]

    st.markdown("---")

    with st.spinner("Загрузка доски опционов…"):
        _board_sk = _get_board_for_analytics(_sk_asset, _sk_cat, _sk_chosen_code)

    if not _board_sk:
        st.warning("Не удалось загрузить доску опционов.")
        return

    _sk_rows = []
    _calls_sk = _board_sk.get("call") or []
    _puts_sk = _board_sk.get("put") or []

    _calls_sk_map = {c.get("strike"): c for c in _calls_sk
                     if c.get("strike") is not None}
    _puts_sk_map = {p.get("strike"): p for p in _puts_sk
                    if p.get("strike") is not None}
    _all_strikes_sk = sorted(set(_calls_sk_map.keys()) | set(_puts_sk_map.keys()))

    for _k in _all_strikes_sk:
        _c = _calls_sk_map.get(_k, {})
        _p = _puts_sk_map.get(_k, {})
        _iv_c = _c.get("volatility")
        _iv_p = _p.get("volatility")
        _iv_avg = None
        _ivs = [x for x in (_iv_c, _iv_p) if x is not None]
        if _ivs:
            _iv_avg = float(np.mean([float(x) for x in _ivs]))
        _sk_rows.append({
            "strike": float(_k),
            "iv_call": float(_iv_c) if _iv_c is not None else None,
            "iv_put": float(_iv_p) if _iv_p is not None else None,
            "iv_avg": _iv_avg,
        })

    _df_sk = pd.DataFrame(_sk_rows).dropna(subset=["iv_avg"])
    if _df_sk.empty:
        st.warning("Не удалось получить IV ни по одному страйку.")
        return

    _df_sk = _df_sk.sort_values("strike").reset_index(drop=True)
    _central_sk = _board_sk.get("central_strike")
    _current_price_sk = _get_current_market_price_for_asset(_sk_asset, _sk_cat)

    _iv_vals = _df_sk["iv_avg"].values
    _iv_mean = float(np.mean(_iv_vals))
    _iv_std = float(np.std(_iv_vals, ddof=1)) if len(_iv_vals) > 1 else 0.0
    _skew_ratio = (_iv_std / _iv_mean * 100) if _iv_mean > 0 else 0.0

    st.markdown("### 1) Метрики наклона волатильности")
    _sm1, _sm2, _sm3, _sm4 = st.columns(4)
    _sm1.metric("Среднее IV", f"{_iv_mean:.2f}%")
    _sm2.metric("σ IV", f"{_iv_std:.2f}%")
    _sm3.metric("σ/μ", f"{_skew_ratio:.2f}%")
    _sm4.metric("Страйков в анализе", len(_df_sk))

    if _skew_ratio < CHECKLIST_RULES["skew_threshold_pct"]:
        st.success(f"σ/μ = {_skew_ratio:.2f}% < 15% — "
                    f"наклон волатильности отсутствует. "
                    f"Стратегии на skew не имеют статистического преимущества.")
    else:
        st.warning(f"σ/μ = {_skew_ratio:.2f}% ≥ 15% — "
                    f"обнаружен наклон волатильности. "
                    f"Есть статистический эдж.")

    _slope = 0.0
    _skew_type = "—"
    _skew_type_label = "—"
    _skew_color = "#7a7a7a"

    if len(_df_sk) >= 3:
        _x = _df_sk["strike"].values
        _y = _df_sk["iv_avg"].values
        try:
            _slope = float(np.polyfit(_x, _y, 1)[0])
        except Exception:
            _slope = 0.0

        _central_ref = float(_central_sk) if _central_sk is not None \
            else float(_current_price_sk) if _current_price_sk is not None \
            else float(np.median(_x))

        _left_mask = _df_sk["strike"] < _central_ref
        _right_mask = _df_sk["strike"] > _central_ref

        _iv_left_avg = _df_sk.loc[_left_mask, "iv_avg"].mean() \
            if _left_mask.any() else np.nan
        _iv_right_avg = _df_sk.loc[_right_mask, "iv_avg"].mean() \
            if _right_mask.any() else np.nan

        if not np.isnan(_iv_left_avg) and not np.isnan(_iv_right_avg):
            _delta_lr = _iv_left_avg - _iv_right_avg
            if _delta_lr > 2:
                _skew_type = "reverse"
                _skew_type_label = "ОБРАТНЫЙ (Reverse) — Put-skew"
                _skew_color = "#1e88e5"
            elif _delta_lr < -2:
                _skew_type = "forward"
                _skew_type_label = "ПРЯМОЙ (Forward) — Call-skew"
                _skew_color = "#e6a500"
            else:
                if (not np.isnan(_iv_left_avg) and not np.isnan(_iv_right_avg)
                        and _iv_left_avg > _iv_mean + 1
                        and _iv_right_avg > _iv_mean + 1):
                    _skew_type = "dual"
                    _skew_type_label = "ДВОЙНОЙ (Dual)"
                    _skew_color = "#9c27b0"
                else:
                    _skew_type = "flat"
                    _skew_type_label = "Плоский / симметричный"
                    _skew_color = "#7a7a7a"

    st.markdown("### 2) Тип наклона")
    st.markdown(
        f"<div style='padding:14px 18px; border-radius:12px; "
        f"background:{_skew_color}20; border-left:6px solid {_skew_color}; "
        f"margin-bottom:14px;'>"
        f"<div style='font-size:1.05rem; font-weight:800; color:{_skew_color};'>"
        f"{_skew_type_label}</div>"
        f"<div style='font-size:.82rem; color:#5a6b78; margin-top:6px;'>"
        f"Наклон регрессии (IV по страйку): "
        f"<b>{_slope:+.4f} %/пункт</b></div></div>",
        unsafe_allow_html=True)

    st.markdown("### 3) Улыбка волатильности и линия регрессии")
    _fig_sk = go.Figure()

    _df_c = _df_sk.dropna(subset=["iv_call"])
    if not _df_c.empty:
        _fig_sk.add_trace(go.Scatter(
            x=_df_c["strike"], y=_df_c["iv_call"],
            mode="markers+lines", name="IV Call",
            line=dict(color="#00a651", width=1.5, dash="dot"),
            marker=dict(size=8, color="#00a651"),
            hovertemplate="Страйк: %{x}<br>IV Call: %{y:.2f}%<extra></extra>"))

    _df_p = _df_sk.dropna(subset=["iv_put"])
    if not _df_p.empty:
        _fig_sk.add_trace(go.Scatter(
            x=_df_p["strike"], y=_df_p["iv_put"],
            mode="markers+lines", name="IV Put",
            line=dict(color="#d32f2f", width=1.5, dash="dot"),
            marker=dict(size=8, color="#d32f2f"),
            hovertemplate="Страйк: %{x}<br>IV Put: %{y:.2f}%<extra></extra>"))

    _fig_sk.add_trace(go.Scatter(
        x=_df_sk["strike"], y=_df_sk["iv_avg"],
        mode="lines", name="IV сред.",
        line=dict(color="#1e5a7a", width=3),
        hovertemplate="Страйк: %{x}<br>IV: %{y:.2f}%<extra></extra>"))

    if len(_df_sk) >= 3:
        _xr = np.array([_df_sk["strike"].min(), _df_sk["strike"].max()])
        try:
            _coef = np.polyfit(_df_sk["strike"], _df_sk["iv_avg"], 1)
            _yr = np.polyval(_coef, _xr)
            _fig_sk.add_trace(go.Scatter(
                x=_xr, y=_yr, mode="lines", name="Регрессия",
                line=dict(color="#9c27b0", width=2, dash="dash"),
                hovertemplate="Регрессия<br>%{x:.0f}: %{y:.2f}%<extra></extra>"))
        except Exception:
            pass

    if _central_sk is not None:
        _fig_sk.add_vline(x=float(_central_sk),
                          line=dict(color="#4a6f8a", width=1.5, dash="dot"),
                          annotation_text=f"Центр {_fmt_strike(_central_sk, _sk_cat)}",
                          annotation_position="top")
    if _current_price_sk is not None:
        _fig_sk.add_vline(x=float(_current_price_sk),
                          line=dict(color="#1e88e5", width=2, dash="dash"),
                          annotation_text=f"БА {_current_price_sk:.2f}",
                          annotation_position="bottom")

    _fig_sk.update_layout(
        title=f"Улыбка волатильности — {_sk_asset} "
              f"({format_series_label(_sk_chosen['expiry'])})",
        xaxis_title="Страйк", yaxis_title="IV, %",
        height=460, margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom",
                    y=1.02, xanchor="left", x=0),
        hovermode="x unified")
    st.plotly_chart(_fig_sk, use_container_width=True)

    st.markdown("---")

    st.markdown("### 4) Рекомендации по стратегиям")

    if _skew_ratio < CHECKLIST_RULES["skew_threshold_pct"]:
        st.info("Наклон волатильности отсутствует (σ/μ < 15%). "
                 "Стратегии, основанные на skew, не имеют статистического "
                 "преимущества. Ориентируйтесь на направленные стратегии "
                 "или на общий уровень IV (вкладка «IV Rank / Децили»).")
    elif _skew_type == "forward":
        st.success(
            "Прямой наклон — IV на высоких страйках выше, "
            "чем на низких. Опционы Call 'вне денег' относительно дорогие, "
            "Put 'вне денег' — дешёвые.")
        st.markdown("""
**Рекомендуемые стратегии:**

| Стратегия | Комментарий |
|---|---|
| **Пропорциональный Call-спрэд** (1-к-2) | Купить 1 OTM Call + продать 2 дальних OTM Call. |
| **Обратный Put-спрэд** | Купить 2 дешёвых OTM Put + продать 1 дорогой OTM Put. |

**Правила:**
- На длинной стороне — «около денег», на короткой — «вне денег»;
- IV низкая → **обратный Put-спрэд**;
- IV высокая → **пропорциональный Call-спрэд**;
- Обязательно — ментальные стопы.
""")
    elif _skew_type == "reverse":
        st.success(
            "Обратный наклон — IV на низких страйках выше, "
            "чем на высоких. Опционы Put 'вне денег' относительно дорогие, "
            "Call 'вне денег' — дешёвые. Характерен для широких индексов.")
        st.markdown("""
**Рекомендуемые стратегии:**

| Стратегия | Комментарий |
|---|---|
| **Обратный Call-спрэд** | Продать 1 Call «в деньгах» + купить 2 OTM Call. |
| **Пропорциональный Put-спрэд** (1-к-2) | Купить 1 ATM Put + продать 2 дальних OTM Put. |

**Особенности для индексов:**
- Наклон устойчив годами;
- При росте БА — роллируйте длинные Call вверх;
- Только дельта-хеджированные позиции.
""")
    elif _skew_type == "dual":
        st.info("Двойной наклон — IV повышена и на нижних, и на "
                 "верхних страйках. Обычно возникает на рынках металлов.")
        st.markdown("""
**Рекомендуемые стратегии:**
- **Короткий стрэддл** на центральном страйке;
- **Продажа Iron Condor** — с защитными крыльями;
- Покупка дешёвых ATM + продажа дорогих OTM на обоих крыльях.
""")
    else:
        st.info("Плоский наклон — статистического преимущества нет. "
                 "Работайте по направленным стратегиям или по IV Rank.")

    st.markdown("---")

    with st.expander("Детальная таблица IV по страйкам", expanded=False):
        _df_show_sk = _df_sk.copy()
        _df_show_sk = _df_show_sk.rename(columns={
            "strike": "Страйк",
            "iv_call": "IV Call, %",
            "iv_put": "IV Put, %",
            "iv_avg": "IV сред., %",
        })
        st.dataframe(
            _df_show_sk.style.format({
                "Страйк": "{:.2f}",
                "IV Call, %": "{:.2f}",
                "IV Put, %": "{:.2f}",
                "IV сред., %": "{:.2f}",
            }, na_rep="—"),
            use_container_width=True, hide_index=True,
            height=min(120 + 35 * len(_df_show_sk), 500))

    st.caption("Критерий наличия наклона: σ/μ ≥ 15%.")
    # ==================================================================
# ============ ВКЛАДКА 8: ЖУРНАЛ ==================================
# ==================================================================
@st.fragment
def _render_journal_tab():
    st.header("Журнал сделок")
    st.caption("Учёт закрытых и открытых сделок. Экспорт/импорт CSV. "
               "Служит источником статистики для Калькулятора Келли.")

    if "journal_rows" not in st.session_state:
        st.session_state.journal_rows = []

    # [PATCH 5] Начальный вид карточек на мобильных.
    if "journal_view_mode" not in st.session_state:
        st.session_state.journal_view_mode = "Карточки (мобильный)"

    if "journal_initial_deposit" not in st.session_state:
        st.session_state.journal_initial_deposit = 100000.0
    if "journal_deposit_mode" not in st.session_state:
        st.session_state.journal_deposit_mode = "auto"
    if "journal_current_deposit_manual" not in st.session_state:
        st.session_state.journal_current_deposit_manual = None
    if "journal_period_filter" not in st.session_state:
        st.session_state.journal_period_filter = "Всё время"

    # ==========================================================
    # ШАПКА: депозит + метрики баланса
    # ==========================================================
    _init_dep, _cur_dep, _dep_mode = _journal_get_deposit()

    with st.container(border=True):
        st.markdown("#### Депозит")
        _dep_c1, _dep_c2, _dep_c3 = st.columns([2, 2, 2])
        with _dep_c1:
            _new_init = st.number_input(
                "Начальный депозит, ₽",
                min_value=0.0,
                value=float(_init_dep),
                step=1000.0,
                format="%.0f",
                key="journal_initial_deposit_inp")
            if abs(_new_init - float(_init_dep)) > 0.01:
                st.session_state.journal_initial_deposit = float(_new_init)
                st.rerun()
        with _dep_c2:
            _mode_options = ["Авто (по P&L сделок)", "Вручную"]
            _mode_idx = 0 if _dep_mode == "auto" else 1
            _new_mode = st.selectbox(
                "Режим",
                _mode_options,
                index=_mode_idx,
                key="journal_deposit_mode_select")
            _new_mode_key = "auto" if _new_mode.startswith("Авто") else "manual"
            if _new_mode_key != _dep_mode:
                st.session_state.journal_deposit_mode = _new_mode_key
                st.rerun()
        with _dep_c3:
            if _dep_mode == "manual":
                _cur_manual_val = (st.session_state.get(
                    "journal_current_deposit_manual") or _init_dep)
                _new_manual = st.number_input(
                    "Текущий депозит, ₽",
                    min_value=0.0,
                    value=float(_cur_manual_val),
                    step=1000.0,
                    format="%.0f",
                    key="journal_current_deposit_inp")
                if abs(_new_manual - float(_cur_manual_val)) > 0.01:
                    st.session_state.journal_current_deposit_manual = float(_new_manual)
                    st.rerun()
            else:
                st.metric(
                    "Текущий баланс (авто)",
                    f"{_cur_dep:,.0f} ₽")

        _growth_abs = _cur_dep - _init_dep
        _growth_pct = (_growth_abs / _init_dep * 100.0) if _init_dep > 0 else 0.0
        _growth_color = "#00a651" if _growth_abs > 0 else (
            "#d32f2f" if _growth_abs < 0 else "#333")
        st.markdown(
            f"<div style='padding:8px 14px; background:#f6f9fc; "
            f"border-radius:8px; font-size:.9rem; margin-top:6px;'>"
            f"<b>Прирост:</b> "
            f"<span style='color:{_growth_color}; font-weight:800; "
            f"font-size:1.05rem;'>{_growth_abs:+,.2f} ₽</span> "
            f"<span style='color:{_growth_color};'>"
            f"({_growth_pct:+.2f}%)</span></div>",
            unsafe_allow_html=True)

    # ==========================================================
    # ДОБАВИТЬ СДЕЛКУ
    # ==========================================================
    with st.expander("Добавить сделку", expanded=False):
        with st.form("journal_add_form", clear_on_submit=True):
            _jc1, _jc2, _jc3 = st.columns(3)
            with _jc1:
                j_date = st.date_input("Дата входа", value=date.today(),
                                        key="jf_date")
                j_ticker = st.text_input("Тикер", value="SBER",
                                          key="jf_ticker").strip().upper()
            with _jc2:
                j_cat = st.selectbox("Категория",
                                      ["Акция", "Фьючерс", "Валюта",
                                       "Товар", "Индекс"],
                                      key="jf_cat")
                j_instr = st.selectbox("Инструмент",
                                       ["Опцион", "Фьючерс", "Акция", "Индекс"],
                                       key="jf_instr")
            with _jc3:
                j_opt = st.selectbox("Опцион", ["Call", "Put", "—"],
                                      key="jf_opt")
                j_side = st.selectbox("Направление",
                                       ["Покупка", "Продажа"],
                                       key="jf_side")

            _jd1, _jd2, _jd3 = st.columns(3)
            with _jd1:
                j_strike = st.number_input("Страйк", min_value=0.0, value=0.0,
                                            step=1.0, format="%.4f",
                                            key="jf_strike")
                j_qty = st.number_input("Кол-во", min_value=1, value=1,
                                         step=1, key="jf_qty")
            with _jd2:
                j_expiry = st.date_input("Экспирация",
                                          value=date.today() + timedelta(days=30),
                                          key="jf_expiry")
                j_entry = st.number_input("Цена входа", min_value=0.0, value=0.0,
                                           step=0.01, format="%.4f",
                                           key="jf_entry")
            with _jd3:
                j_exit = st.number_input("Цена выхода", min_value=0.0, value=0.0,
                                          step=0.01, format="%.4f",
                                          key="jf_exit",
                                          help="0 — сделка ещё открыта")
                j_comm = st.number_input("Комиссия, ₽", min_value=0.0,
                                          value=0.0, step=0.01, format="%.4f",
                                          key="jf_comm")

            j_burned = st.checkbox("Опцион сгорел (потеря премии)",
                                    value=False, key="jf_burned")

            j_note = st.text_input("Заметка", value="", key="jf_note")

            _jsubmit = st.form_submit_button("Добавить в журнал",
                                              type="primary",
                                              use_container_width=True)
            if _jsubmit:
                _sign = 1 if j_side == "Покупка" else -1
                if j_burned:
                    _status = "Сгорел"
                    _exit_val = None
                    _pnl = -_sign * (j_entry * j_qty) - j_comm
                elif j_exit > 0:
                    _status = "Закрыта"
                    _exit_val = float(j_exit)
                    _pnl = (_sign * (j_exit - j_entry) * j_qty) - j_comm
                else:
                    _status = "Открыта"
                    _exit_val = None
                    _pnl = 0.0
                st.session_state.journal_rows.append({
                    "_id": _new_position_id(),
                    "Дата входа": j_date.isoformat(),
                    "Тикер": j_ticker,
                    "Категория": j_cat,
                    "Инструмент": j_instr,
                    "Опцион": j_opt,
                    "Направление": j_side,
                    "Страйк": j_strike if j_strike > 0 else None,
                    "Экспирация": j_expiry.isoformat(),
                    "Кол-во": int(j_qty),
                    "Цена входа": float(j_entry),
                    "Цена выхода": _exit_val,
                    "Комиссия": float(j_comm),
                    "P&L": float(_pnl),
                    "Статус": _status,
                    "Заметка": j_note,
                })
                _msg = f"Сделка добавлена: {j_ticker} {j_opt} {j_strike} " \
                       f"({j_side} × {j_qty})"
                if j_burned:
                    _msg += " (сгорел)"
                st.success(_msg)
                st.rerun()

    # ==========================================================
    # УПРАВЛЕНИЕ
    # ==========================================================
    st.markdown("### Управление")
    _e1, _e2, _e3 = st.columns(3)
    with _e1:
        if st.session_state.journal_rows:
            _df_j = pd.DataFrame(st.session_state.journal_rows)
            _df_j = _df_j.drop(columns=["_id"], errors="ignore")
            st.download_button(
                "Экспорт CSV",
                data=_df_j.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"journal_{date.today().isoformat()}.csv",
                mime="text/csv", use_container_width=True,
                key="journal_export_btn")
        else:
            st.button("Экспорт CSV", disabled=True,
                      use_container_width=True, key="journal_export_disabled")
    with _e2:
        _up = st.file_uploader("Импорт CSV", type=["csv"],
                                key="journal_import",
                                label_visibility="collapsed")
        if _up is not None:
            try:
                _df_imp = pd.read_csv(_up)
                _imp_rows = []
                for _, r in _df_imp.iterrows():
                    _row = {
                        "_id": _new_position_id(),
                        "Дата входа": str(r.get("Дата входа", date.today().isoformat())),
                        "Тикер": str(r.get("Тикер", "—")).upper(),
                        "Категория": str(r.get("Категория", "Акция")),
                        "Инструмент": str(r.get("Инструмент", "Опцион")),
                        "Опцион": str(r.get("Опцион", "—")),
                        "Направление": str(r.get("Направление", "Покупка")),
                        "Страйк": (float(r["Страйк"])
                                   if pd.notna(r.get("Страйк")) else None),
                        "Экспирация": str(r.get("Экспирация", "—")),
                        "Кол-во": int(r.get("Кол-во", 0) or 0),
                        "Цена входа": float(r.get("Цена входа", 0) or 0),
                        "Цена выхода": (float(r["Цена выхода"])
                                        if pd.notna(r.get("Цена выхода"))
                                        else None),
                        "Комиссия": float(r.get("Комиссия", 0) or 0),
                        "P&L": float(r.get("P&L", 0) or 0),
                        "Статус": str(r.get("Статус", "Открыта")),
                        "Заметка": str(r.get("Заметка", "")),
                    }
                    _imp_rows.append(_row)
                if st.button("Применить импорт", type="primary",
                              key="journal_apply_import",
                              use_container_width=True):
                    st.session_state.journal_rows = _imp_rows
                    st.success(f"Импортировано {len(_imp_rows)} сделок.")
                    st.rerun()
                st.caption(f"Файл: {len(_imp_rows)} строк")
            except Exception as e:
                st.error(f"Ошибка чтения CSV: {e}")
    with _e3:
        if st.button("Очистить журнал", use_container_width=True,
                      key="journal_clear_all"):
            st.session_state.journal_rows = []
            st.rerun()

    st.markdown("---")

    # ==========================================================
    # ФИЛЬТР ПО ПЕРИОДУ
    # ==========================================================
    _period_options = ["Всё время", "Последний месяц",
                        "Последние 3 месяца", "Последние 6 месяцев",
                        "Последний год"]
    _period_chosen = st.radio(
        "Период",
        _period_options,
        index=_period_options.index(st.session_state.journal_period_filter)
              if st.session_state.journal_period_filter in _period_options else 0,
        horizontal=True,
        key="journal_period_radio",
        label_visibility="collapsed")
    st.session_state.journal_period_filter = _period_chosen

    _period_days_map = {
        "Всё время": None,
        "Последний месяц": 30,
        "Последние 3 месяца": 90,
        "Последние 6 месяцев": 180,
        "Последний год": 365,
    }
    _period_days = _period_days_map.get(_period_chosen)

    _rows_all = st.session_state.journal_rows
    if _period_days is not None and _rows_all:
        _cutoff = date.today() - timedelta(days=_period_days)
        _rows_filtered = []
        for r in _rows_all:
            try:
                _rd = datetime.strptime(
                    str(r.get("Дата входа", "")), "%Y-%m-%d").date()
                if _rd >= _cutoff:
                    _rows_filtered.append(r)
            except Exception:
                _rows_filtered.append(r)
    else:
        _rows_filtered = list(_rows_all)

    # ==========================================================
    # СТАТИСТИКА
    # ==========================================================
    st.markdown("### Статистика")

    if not _rows_filtered:
        if _period_days is not None:
            st.info(f"Нет сделок за период «{_period_chosen}». "
                    f"Выберите «Всё время» или добавьте сделки.")
        else:
            st.info("Журнал пуст. Добавьте первую сделку.")
        return

    _closed = [r for r in _rows_filtered
               if r.get("Статус") in ("Закрыта", "Сгорел")]
    _wins = [r for r in _closed if (r.get("P&L") or 0) > 0]
    _losses = [r for r in _closed if (r.get("P&L") or 0) < 0]
    _total_pnl = sum((r.get("P&L") or 0) for r in _closed)
    _gross_win = sum((r.get("P&L") or 0) for r in _wins)
    _gross_loss = abs(sum((r.get("P&L") or 0) for r in _losses))
    _avg_win = (_gross_win / len(_wins)) if _wins else 0.0
    _avg_loss = (_gross_loss / len(_losses)) if _losses else 0.0
    _win_rate = (len(_wins) / len(_closed) * 100) if _closed else 0.0

    _profit_factor = _journal_profit_factor(_closed)

    _equity_df = _journal_equity_series(_rows_all, _init_dep)
    _max_dd_abs, _max_dd_pct = _journal_max_drawdown(_equity_df)

    _streaks = _journal_streaks(_closed)

    _s1, _s2, _s3, _s4 = st.columns(4)
    _s1.metric("Всего сделок", len(_rows_filtered),
               delta=f"закрыто {len(_closed)}")
    _s2.metric("Win-rate", f"{_win_rate:.1f}%",
               delta=f"{len(_wins)}W / {len(_losses)}L")
    _s3.metric("Total P&L (фильтр)", f"{_total_pnl:+,.2f} ₽")
    if _profit_factor is None:
        _pf_str = "—"
    elif _profit_factor == float("inf"):
        _pf_str = "∞"
    else:
        _pf_str = f"{_profit_factor:.2f}"
    _s4.metric("Profit Factor", _pf_str)

    _s5, _s6, _s7, _s8 = st.columns(4)
    _s5.metric("Ср. выигрыш", f"{_avg_win:+,.2f} ₽")
    _s6.metric("Ср. убыток", f"{-_avg_loss:+,.2f} ₽")
    if _closed and _avg_loss > 0:
        _expectancy = ((_win_rate / 100.0) * _avg_win
                        - (1 - _win_rate / 100.0) * _avg_loss)
        _s7.metric("Expectancy", f"{_expectancy:+,.2f} ₽")
    else:
        _s7.metric("Expectancy", "—")
    _s8.metric("Max Drawdown",
                f"{_max_dd_abs:,.0f} ₽" if _max_dd_abs > 0 else "—",
                delta=f"−{_max_dd_pct:.1f}%" if _max_dd_pct > 0 else None,
                delta_color="inverse")

    _s9, _s10, _s11, _s12 = st.columns(4)
    _s9.metric("Max серия W", _streaks["max_wins"],
               delta=f"ср. {_streaks['avg_wins']:.1f}")
    _s10.metric("Max серия L", _streaks["max_losses"],
                 delta=f"ср. {_streaks['avg_losses']:.1f}")
    _open_trades = [r for r in _rows_filtered
                    if r.get("Статус") == "Открыта"]
    _s11.metric("Открыто сейчас", len(_open_trades))
    _max_loss_single = 0.0
    if _losses:
        _max_loss_single = abs(min((r.get("P&L") or 0) for r in _losses))
    _risk_pct_per_trade = (_max_loss_single / _init_dep * 100.0) \
                          if _init_dep > 0 else 0.0
    _s12.metric("Макс. убыток / сделка", f"{_max_loss_single:,.0f} ₽",
                 delta=f"{_risk_pct_per_trade:.1f}% депо",
                 delta_color="inverse")

    # ==========================================================
    # EQUITY CURVE
    # ==========================================================
    if not _equity_df.empty:
        st.markdown("---")
        st.markdown("### Кривая капитала")

        _eq_plot = _equity_df.copy()
        _eq_plot["idx"] = range(1, len(_eq_plot) + 1)
        _eq_plot["label"] = _eq_plot["date"] + " #" + _eq_plot["idx"].astype(str)

        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            x=_eq_plot["idx"],
            y=_eq_plot["balance"],
            mode="lines+markers",
            name="Баланс",
            line=dict(color="#1e5a7a", width=3),
            marker=dict(size=6, color="#1e88e5"),
            customdata=_eq_plot[["date", "pnl"]].values,
            hovertemplate=(
                "Сделка #%{x}<br>"
                "Дата: %{customdata[0]}<br>"
                "P&L: %{customdata[1]:+,.2f} ₽<br>"
                "Баланс: %{y:,.2f} ₽<extra></extra>"
            )))
        fig_eq.add_hline(
            y=float(_init_dep),
            line=dict(color="#7a7a7a", width=1.5, dash="dash"),
            annotation_text=f"Начальный депозит = {_init_dep:,.0f} ₽",
            annotation_position="top left",
            annotation_font_color="#7a7a7a")
        fig_eq.update_layout(
            title="Кривая капитала",
            xaxis_title="№ сделки (закрытые)",
            yaxis_title="Баланс, ₽",
            height=380,
            margin=dict(l=20, r=20, t=50, b=20),
            plot_bgcolor="white", paper_bgcolor="white",
            hovermode="x unified",
            showlegend=False)
        st.plotly_chart(fig_eq, use_container_width=True)

    # ==========================================================
    # СТАТИСТИКА ПО ТИКЕРАМ
    # ==========================================================
    with st.expander("Статистика по тикерам и стратегиям", expanded=False):
        _stat_tab1, _stat_tab2 = st.tabs(["По тикерам", "По конструкциям"])

        with _stat_tab1:
            _df_by_ticker = _journal_stats_by(_closed, "Тикер")
            if not _df_by_ticker.empty:
                st.dataframe(
                    _df_by_ticker.style.format({
                        "Win-rate, %": "{:.1f}",
                        "P&L, ₽": "{:+,.2f}",
                    }, na_rep="—"),
                    use_container_width=True, hide_index=True,
                    height=min(120 + 35 * len(_df_by_ticker), 400))
            else:
                st.caption("Нет закрытых сделок")

        with _stat_tab2:
            _df_by_constr = _journal_stats_by(_closed, "Опцион")
            if not _df_by_constr.empty:
                st.dataframe(
                    _df_by_constr.style.format({
                        "Win-rate, %": "{:.1f}",
                        "P&L, ₽": "{:+,.2f}",
                    }, na_rep="—"),
                    use_container_width=True, hide_index=True,
                    height=min(120 + 35 * len(_df_by_constr), 400))
            else:
                st.caption("Нет закрытых сделок")

    # ==========================================================
    # ТАБЛИЦА / КАРТОЧКИ
    # ==========================================================
    st.markdown("---")
    st.markdown("### Список сделок")

    _balance_by_id = {}
    _pct_by_id = {}
    _running_balance = _init_dep
    for r in _journal_closed_sorted(_rows_all):
        _p = float(r.get("P&L") or 0.0)
        _bal_before = _running_balance
        _running_balance += _p
        _rid = r.get("_id")
        if _rid:
            _balance_by_id[_rid] = _running_balance
            _pct_by_id[_rid] = (_p / _bal_before * 100.0) if _bal_before > 0 else 0.0

    _rows_for_table = []
    for r in _rows_filtered:
        _rr = dict(r)
        _rid = r.get("_id")
        if r.get("Статус") in ("Закрыта", "Сгорел"):
            _rr["_balance"] = _balance_by_id.get(_rid)
            _rr["_pct_deposit"] = _pct_by_id.get(_rid)
        else:
            _rr["_balance"] = None
            _rr["_pct_deposit"] = None
        _rows_for_table.append(_rr)

    _df_journal = pd.DataFrame(_rows_for_table)
    _df_display = _df_journal.drop(
        columns=["_id", "_balance", "_pct_deposit"], errors="ignore")

    def _style_journal_row(row):
        _styles = []
        for col in row.index:
            s = ""
            if col == "P&L":
                v = row[col]
                if isinstance(v, (int, float)):
                    if v > 0:
                        s = "color: #00a651; font-weight: 700;"
                    elif v < 0:
                        s = "color: #d32f2f; font-weight: 700;"
            elif col == "Направление":
                if row[col] == "Покупка":
                    s = "color: #00a651; font-weight: 600;"
                elif row[col] == "Продажа":
                    s = "color: #d32f2f; font-weight: 600;"
            elif col == "Статус":
                if row[col] == "Сгорел":
                    s = ("background-color: #ffe6e6; color: #8b1e1e; "
                         "font-weight: 700;")
                elif row[col] == "Закрыта":
                    s = "color: #5a6b78;"
                elif row[col] == "Открыта":
                    s = "color: #1e88e5; font-weight: 600;"
            _styles.append(s)
        return _styles

    _view_mode_journal = st.radio(
        "Вид журнала",
        ["Таблица", "Карточки (мобильный)"],
        index=(0 if st.session_state.journal_view_mode == "Таблица" else 1),
        horizontal=True,
        key="journal_view_mode_radio",
        label_visibility="collapsed")
    st.session_state.journal_view_mode = _view_mode_journal

    if st.session_state.journal_view_mode == "Карточки (мобильный)":
        for _idx_j, _row_j in _df_journal.iterrows():
            _rd_j = _row_j.to_dict()
            _status = _rd_j.get("Статус", "")
            _pnl_j = _rd_j.get("P&L") or 0
            _side = _rd_j.get("Направление", "—")
            _opt = _rd_j.get("Опцион", "—")
            _ticker_j = _rd_j.get("Тикер", "—")
            _strike_j = _rd_j.get("Страйк")
            _qty_j = _rd_j.get("Кол-во", 0)
            _entry_j = _rd_j.get("Цена входа", 0)
            _exit_j = _rd_j.get("Цена выхода")
            _comm_j = _rd_j.get("Комиссия", 0)
            _date_j = _rd_j.get("Дата входа", "—")
            _exp_j = _rd_j.get("Экспирация", "—")
            _note_j = _rd_j.get("Заметка", "")
            _bal_j = _rd_j.get("_balance")
            _pct_j = _rd_j.get("_pct_deposit")

            _status_color = {
                "Сгорел": "#8b1e1e", "Закрыта": "#5a6b78",
                "Открыта": "#1e88e5",
            }.get(_status, "#333")
            _status_bg = {
                "Сгорел": "#ffe6e6", "Закрыта": "#eef2f5",
                "Открыта": "#e3f2fd",
            }.get(_status, "#f2f4f6")

            _opt_color = ("#00a651" if _opt == "Call"
                          else "#d32f2f" if _opt == "Put" else "#333")
            _side_color = ("#00a651" if _side == "Покупка"
                            else "#d32f2f" if _side == "Продажа" else "#333")
            _pnl_color = ("#00a651" if _pnl_j > 0
                           else "#d32f2f" if _pnl_j < 0 else "#333")
            _strike_str = _fmt_strike(_strike_j, _rd_j.get("Категория"))
            _exit_str = f"{_exit_j:.4f}" if _exit_j is not None else "—"

            with st.container(border=True):
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; "
                    f"align-items:baseline;'>"
                    f"<div style='font-size:1.05rem; font-weight:700;'>"
                    f"{_ticker_j} "
                    f"<span style='color:{_opt_color};'>{_opt}</span> "
                    f"<span>{_strike_str}</span></div>"
                    f"<div style='background:{_status_bg}; color:{_status_color}; "
                    f"padding:2px 8px; border-radius:8px; "
                    f"font-size:.7rem; font-weight:700;'>"
                    f"{_status}</div></div>",
                    unsafe_allow_html=True)

                st.markdown(
                    f"<div style='font-size:.78rem; color:#5a6b78; "
                    f"margin-top:2px;'>"
                    f"<span style='color:{_side_color}; font-weight:700;'>"
                    f"{_side}</span> · "
                    f"{_date_j} → {_exp_j}</div>",
                    unsafe_allow_html=True)

                st.markdown(
                    f"<div style='margin-top:8px; padding:8px 10px; "
                    f"background:#f6f9fc; border-radius:6px; "
                    f"font-size:.88rem;'>"
                    f"<b>P&L:</b> <span style='color:{_pnl_color}; "
                    f"font-weight:800; font-size:1rem;'>{_pnl_j:+,.2f} ₽</span>"
                    f"</div>",
                    unsafe_allow_html=True)

                if _bal_j is not None:
                    st.markdown(
                        f"<div style='margin-top:4px; padding:6px 10px; "
                        f"background:#f0f4f8; border-radius:6px; "
                        f"font-size:.82rem;'>"
                        f"<b>Баланс после:</b> "
                        f"<span style='color:#1a3b4f; font-weight:700;'>"
                        f"{_bal_j:,.2f} ₽</span>"
                        f"{(' · ' + f'{_pct_j:+.2f}% депо') if _pct_j is not None else ''}"
                        f"</div>",
                        unsafe_allow_html=True)

                _dc1, _dc2 = st.columns(2)
                with _dc1:
                    st.markdown(
                        f"<div style='font-size:.78rem;'>"
                        f"Кол-во: <b>{_qty_j}</b><br>"
                        f"Цена входа: <b>{_entry_j:.4f}</b></div>",
                        unsafe_allow_html=True)
                with _dc2:
                    st.markdown(
                        f"<div style='font-size:.78rem;'>"
                        f"Цена выхода: <b>{_exit_str}</b><br>"
                        f"Комиссия: <b>{_comm_j:.2f} ₽</b></div>",
                        unsafe_allow_html=True)

                if _note_j:
                    st.caption(f"Заметка: {_note_j}")

    else:
        _df_for_show = _df_display.copy()
        _df_for_show["Баланс, ₽"] = _df_journal["_balance"].values
        _df_for_show["% депо"] = _df_journal["_pct_deposit"].values

        st.dataframe(
            _df_for_show.style.apply(_style_journal_row, axis=1).format({
                "Страйк":       lambda v: f"{v:.2f}" if pd.notna(v) else "—",
                "Цена входа":   "{:.4f}",
                "Цена выхода":  lambda v: f"{v:.4f}" if pd.notna(v) else "—",
                "Комиссия":     "{:.2f}",
                "P&L":          "{:+,.2f}",
                "Баланс, ₽":    lambda v: f"{v:,.2f}" if pd.notna(v) else "—",
                "% депо":       lambda v: f"{v:+.2f}%" if pd.notna(v) else "—",
            }, na_rep="—"),
            use_container_width=True, hide_index=True, height=400)

    # ==========================================================
    # РЕДАКТИРОВАНИЕ
    # ==========================================================
    with st.expander("Редактировать / закрыть сделку", expanded=False):
        if not st.session_state.journal_rows:
            st.info("Журнал пуст.")
        else:
            _edit_opts = [
                f"{i}: {r.get('Дата входа','?')} · {r.get('Тикер','?')} · "
                f"{r.get('Опцион','?')} {r.get('Страйк','—')} · "
                f"{r.get('Статус','?')} · P&L {r.get('P&L',0):+.2f} ₽"
                for i, r in enumerate(st.session_state.journal_rows)
            ]
            _edit_sel = st.selectbox("Выберите запись", _edit_opts,
                                      key="journal_edit_sel")
            if _edit_sel:
                _edit_idx = int(_edit_sel.split(":", 1)[0])
                _edit_row = st.session_state.journal_rows[_edit_idx]
                _cur_status = _edit_row.get("Статус", "Открыта")
                _cur_exit = _edit_row.get("Цена выхода")
                _cur_comm = float(_edit_row.get("Комиссия", 0.0) or 0.0)

                st.markdown(
                    f"**Редактируется:** {_edit_row.get('Тикер','?')} · "
                    f"{_edit_row.get('Направление','?')} "
                    f"{_edit_row.get('Опцион','?')} "
                    f"{_edit_row.get('Страйк','—')} × "
                    f"{_edit_row.get('Кол-во', 0)} "
                    f"по {_edit_row.get('Цена входа', 0):.4f} ₽")

                _ec1, _ec2, _ec3 = st.columns(3)
                with _ec1:
                    _e_exit = st.number_input(
                        "Цена выхода",
                        min_value=0.0,
                        value=float(_cur_exit) if _cur_exit is not None else 0.0,
                        step=0.01, format="%.4f",
                        key=f"journal_edit_exit_{_edit_idx}")
                    _e_burned = st.checkbox(
                        "Сгорел (потеря премии)",
                        value=(_cur_status == "Сгорел"),
                        key=f"journal_edit_burned_{_edit_idx}")
                with _ec2:
                    _e_comm = st.number_input(
                        "Комиссия, ₽",
                        min_value=0.0, value=_cur_comm,
                        step=0.01, format="%.4f",
                        key=f"journal_edit_comm_{_edit_idx}")
                with _ec3:
                    _e_note = st.text_input(
                        "Заметка",
                        value=str(_edit_row.get("Заметка", "")),
                        key=f"journal_edit_note_{_edit_idx}")

                _bc1, _bc2, _bc3 = st.columns([1, 1, 1])
                with _bc1:
                    if st.button("Сохранить", type="primary",
                                 use_container_width=True,
                                 key="journal_edit_save"):
                        _sign = 1 if _edit_row["Направление"] == "Покупка" else -1
                        _entry = float(_edit_row["Цена входа"] or 0)
                        _qty = int(_edit_row["Кол-во"] or 0)

                        if _e_burned:
                            _new_status = "Сгорел"
                            _new_exit = None
                            _new_pnl = -_sign * _entry * _qty - _e_comm
                        elif _e_exit > 0:
                            _new_status = "Закрыта"
                            _new_exit = float(_e_exit)
                            _new_pnl = _sign * (_e_exit - _entry) * _qty - _e_comm
                        else:
                            _new_status = "Открыта"
                            _new_exit = None
                            _new_pnl = 0.0

                        _edit_row["Цена выхода"] = _new_exit
                        _edit_row["Комиссия"] = float(_e_comm)
                        _edit_row["P&L"] = float(_new_pnl)
                        _edit_row["Статус"] = _new_status
                        _edit_row["Заметка"] = _e_note
                        st.success(f"Запись обновлена: {_new_status}, "
                                   f"P&L = {_new_pnl:+.2f} ₽")
                        st.rerun()
                with _bc2:
                    if st.button("Пометить как «сгорел»",
                                 use_container_width=True,
                                 key="journal_burn_quick"):
                        _sign = 1 if _edit_row["Направление"] == "Покупка" else -1
                        _entry = float(_edit_row["Цена входа"] or 0)
                        _qty = int(_edit_row["Кол-во"] or 0)
                        _edit_row["Цена выхода"] = None
                        _edit_row["P&L"] = -_sign * _entry * _qty - _cur_comm
                        _edit_row["Статус"] = "Сгорел"
                        st.success("Помечено как сгоревший")
                        st.rerun()
                with _bc3:
                    if st.button("Открыть снова",
                                 use_container_width=True,
                                 key="journal_reopen_quick"):
                        _edit_row["Цена выхода"] = None
                        _edit_row["P&L"] = 0.0
                        _edit_row["Статус"] = "Открыта"
                        st.success("Запись снова открыта")
                        st.rerun()

    with st.expander("Удалить сделки", expanded=False):
        _del_opts = [
            f"{i}: {r.get('Дата входа','?')} · {r.get('Тикер','?')} · "
            f"{r.get('Опцион','?')} {r.get('Страйк','—')} · "
            f"{r.get('P&L',0):+.2f} ₽"
            for i, r in enumerate(st.session_state.journal_rows)
        ]
        _del_sel = st.multiselect("Выберите для удаления", _del_opts,
                                   key="journal_del_sel")
        if st.button("Удалить выбранные", type="secondary",
                      key="journal_del_btn"):
            _idx_to_del = set(int(s.split(":", 1)[0]) for s in _del_sel)
            st.session_state.journal_rows = [
                r for i, r in enumerate(st.session_state.journal_rows)
                if i not in _idx_to_del
            ]
            st.rerun()


# ==================================================================
# ============ ВКЛАДКА 9: КАЛЬКУЛЯТОР КЕЛЛИ =======================
# ==================================================================
@st.fragment
def _render_kelly_tab():
    st.header("Калькулятор Келли")
    st.caption("Расчёт оптимального размера ставки (доли капитала) "
               "по критерию Келли.")

    with st.expander("Инструкция по использованию", expanded=False):
        st.markdown(r"""
**Что такое критерий Келли?**

Критерий Келли (Kelly Criterion) — математическая формула для определения
оптимальной доли капитала, которую следует рисковать в каждой сделке,
чтобы максимизировать долгосрочный рост капитала.

**Базовая формула (для бинарных исходов):**

$$f^* = \frac{(r + 1) \cdot p - 1}{r}$$

где:
- $f^*$ — доля капитала для ставки (в % от депозита);
- $p$ — вероятность выигрыша (0…1);
- $r$ — отношение среднего выигрыша к среднему убытку.

**Пример:** если $p = 0.44$ и $r = 2$, то
$f^* = \frac{(2+1) \cdot 0.44 - 1}{2} = 0.16$ → ставка **16%** капитала.

**Правила осторожности:**

1. Используйте дробный Келли (½ или ¼ от расчётной величины), потому
   что ваша оценка $p$ и $r$ может быть завышена, а сделки коррелированы.
2. Если $f^* \leq 0$ — система убыточна, торговать по ней нельзя.
3. Формула предполагает последовательные независимые сделки. При
   одновременных сделках используйте метод корректировки риска.
4. Критерий Келли агрессивен.
""")

    st.markdown("### 1) Источник статистики")
    _src = st.radio(
        "Откуда взять p, avg_win, avg_loss?",
        ["Из журнала", "Ввести вручную"],
        horizontal=True, key="kelly_source")

    if _src == "Из журнала":
        _rows = st.session_state.get("journal_rows", [])
        _closed = [r for r in _rows
                   if r.get("Статус") in ("Закрыта", "Сгорел")]
        if not _closed:
            st.warning("В журнале нет закрытых сделок. "
                       "Переключитесь на ручной ввод или добавьте сделки.")
            return
        _wins = [r for r in _closed if (r.get("P&L") or 0) > 0]
        _losses = [r for r in _closed if (r.get("P&L") or 0) < 0]
        _p = len(_wins) / len(_closed) if _closed else 0.0
        _avg_w = (sum((r.get("P&L") or 0) for r in _wins) / len(_wins)) \
                 if _wins else 0.0
        _avg_l = abs(sum((r.get("P&L") or 0) for r in _losses) / len(_losses)) \
                 if _losses else 0.0
        if _avg_l <= 0:
            st.error("Средний убыток = 0. Невозможно вычислить r.")
            return
        _r_ratio = _avg_w / _avg_l
        st.success(
            f"Из журнала ({len(_closed)} закрытых сделок): "
            f"p = {_p:.3f}, avg_win = {_avg_w:,.2f} ₽, "
            f"avg_loss = {_avg_l:,.2f} ₽, r = {_r_ratio:.3f}")

        _manual_p = _p
        _manual_avg_w = _avg_w
        _manual_avg_l = _avg_l
    else:
        _manual_p = st.number_input(
            "Вероятность выигрыша p (0…1)",
            min_value=0.0, max_value=1.0, value=0.50, step=0.01,
            format="%.3f", key="kelly_p")
        _manual_avg_w = st.number_input(
            "Средний выигрыш, ₽",
            min_value=0.0, value=1000.0, step=50.0, format="%.2f",
            key="kelly_avg_w")
        _manual_avg_l = st.number_input(
            "Средний убыток, ₽",
            min_value=0.01, value=500.0, step=50.0, format="%.2f",
            key="kelly_avg_l")

    st.markdown("### 2) Депозит")
    _init_dep_k, _cur_dep_k, _dep_mode_k = _journal_get_deposit()
    _journal_has_rows = bool(st.session_state.get("journal_rows"))
    _use_journal_dep = _dep_mode_k == "manual" or _journal_has_rows

    if _use_journal_dep and _cur_dep_k > 0:
        _deposit = float(_cur_dep_k)
        _dep_src = ("текущий депозит журнала ("
                     + ("ручной" if _dep_mode_k == "manual" else "авто по P&L")
                     + ")")
    else:
        _deposit = float(st.session_state.get("dep_inp", 100000.0))
        _dep_src = "вкладка «Позиция»"

    st.info(f"Депозит берётся из: {_dep_src} — **{_deposit:,.2f} ₽**")

    if _src == "Из журнала":
        _closed_count = len([r for r in st.session_state.get("journal_rows", [])
                             if r.get("Статус") in ("Закрыта", "Сгорел")])
        if _closed_count < 20:
            st.warning(
                f"Закрытых сделок в журнале: {_closed_count}. "
                f"Для достоверной оценки p и r рекомендуется ≥ 20 сделок. "
                f"Текущие результаты Kelly могут быть ненадёжны — "
                f"продолжайте собирать статистику.")
        elif _closed_count < 50:
            st.info(
                f"Закрытых сделок в журнале: {_closed_count}. "
                f"Статистика достаточная, но при 50+ сделках точность будет выше.")
        else:
            st.success(
                f"Закрытых сделок в журнале: {_closed_count} — "
                f"статистика надёжна, Kelly-оценки устойчивы.")

    st.markdown("### 3) Результат")
    _f_full = None
    _f_half = _f_quarter = None

    if _manual_avg_l > 0 and _manual_avg_w > 0:
        _r_ratio = _manual_avg_w / _manual_avg_l
        _f_full = ((_r_ratio + 1.0) * _manual_p - 1.0) / _r_ratio
        _f_half = _f_full * 0.5
        _f_quarter = _f_full * 0.25

    if _f_full is None:
        st.error("Некорректные входные данные для расчёта.")
        return

    _color_f = ("#00a651" if _f_full > 0
                else "#d32f2f" if _f_full < 0 else "#333")

    _k1, _k2, _k3, _k4 = st.columns(4)
    with _k1:
        st.markdown(
            f"<div style='padding:12px; border-radius:10px; "
            f"background:#f0f4f8;'>"
            f"<div style='font-size:.72rem; color:#4a6f8a; "
            f"font-weight:700; text-transform:uppercase;'>"
            f"Полный Келли</div>"
            f"<div style='font-size:1.5rem; font-weight:800; "
            f"color:{_color_f}; margin-top:6px;'>"
            f"{_f_full*100:+.2f} %</div>"
            f"<div style='font-size:.8rem; color:#5a6b78; margin-top:4px;'>"
            f"{_f_full*_deposit:+,.2f} ₽</div>"
            f"</div>", unsafe_allow_html=True)
    with _k2:
        st.markdown(
            f"<div style='padding:12px; border-radius:10px; "
            f"background:#f0f4f8;'>"
            f"<div style='font-size:.72rem; color:#4a6f8a; "
            f"font-weight:700; text-transform:uppercase;'>"
            f"½ Келли</div>"
            f"<div style='font-size:1.5rem; font-weight:800; "
            f"color:{_color_f}; margin-top:6px;'>"
            f"{_f_half*100:+.2f} %</div>"
            f"<div style='font-size:.8rem; color:#5a6b78; margin-top:4px;'>"
            f"{_f_half*_deposit:+,.2f} ₽</div>"
            f"</div>", unsafe_allow_html=True)
    with _k3:
        st.markdown(
            f"<div style='padding:12px; border-radius:10px; "
            f"background:#f0f4f8;'>"
            f"<div style='font-size:.72rem; color:#4a6f8a; "
            f"font-weight:700; text-transform:uppercase;'>"
            f"¼ Келли</div>"
            f"<div style='font-size:1.5rem; font-weight:800; "
            f"color:{_color_f}; margin-top:6px;'>"
            f"{_f_quarter*100:+.2f} %</div>"
            f"<div style='font-size:.8rem; color:#5a6b78; margin-top:4px;'>"
            f"{_f_quarter*_deposit:+,.2f} ₽</div>"
            f"</div>", unsafe_allow_html=True)
    with _k4:
        st.markdown(
            f"<div style='padding:12px; border-radius:10px; "
            f"background:#f0f4f8;'>"
            f"<div style='font-size:.72rem; color:#4a6f8a; "
            f"font-weight:700; text-transform:uppercase;'>"
            f"r (win/loss)</div>"
            f"<div style='font-size:1.5rem; font-weight:800; "
            f"color:#1a3b4f; margin-top:6px;'>{_r_ratio:.3f}</div>"
            f"<div style='font-size:.8rem; color:#5a6b78; margin-top:4px;'>"
            f"avg_win / avg_loss</div>"
            f"</div>", unsafe_allow_html=True)

    _rvi_kelly_data = fetch_rvi_current()
    _rvi_kelly = _rvi_kelly_data.get("value") if _rvi_kelly_data else None

    if _rvi_kelly is not None and _f_full is not None:
        _rvi_factor = max(0.3, 1.0 - _rvi_kelly / 100.0)

        _f_full_rvi    = _f_full    * _rvi_factor
        _f_half_rvi    = _f_half    * _rvi_factor
        _f_quarter_rvi = _f_quarter * _rvi_factor

        st.markdown("---")
        st.markdown("### RVI-поправка")
        st.markdown(
            f"<div style='padding:14px 18px; border-radius:12px; "
            f"background:#fff3e0; border-left:6px solid #e6a500; margin:10px 0;'>"
            f"<div style='font-size:.9rem; font-weight:700; color:#e6a500;'>"
            f"RVI = {_rvi_kelly:.2f}%</div>"
            f"<div style='font-size:.82rem; color:#5a6b78; margin-top:4px;'>"
            f"Множитель: ×{_rvi_factor:.2f} "
            f"(снижение доли из-за корреляции сделок)</div>"
            f"</div>",
            unsafe_allow_html=True)

        _rk1, _rk2, _rk3 = st.columns(3)
        with _rk1:
            st.metric("Полный Келли (RVI)", f"{_f_full_rvi*100:+.2f} %",
                      delta=f"{_f_full_rvi*_deposit:+,.2f} ₽")
        with _rk2:
            st.metric("½ Келли (RVI)", f"{_f_half_rvi*100:+.2f} %",
                      delta=f"{_f_half_rvi*_deposit:+,.2f} ₽")
        with _rk3:
            st.metric("¼ Келли (RVI)", f"{_f_quarter_rvi*100:+.2f} %",
                      delta=f"{_f_quarter_rvi*_deposit:+,.2f} ₽")

        st.caption(
            "Формула: f_RVI = f_Келли × max(0.3, 1 − RVI/100). "
            "При высоком RVI сделки коррелированы — размер ставки снижается.")

    st.markdown("---")
    if _f_full <= 0:
        st.error("f* ≤ 0 — при текущих p и r система убыточна. "
                 "Критерий Келли рекомендует не торговать по этой стратегии.")
    elif _f_full > 0.25:
        st.warning(f"Доля Келли {_f_full*100:.1f}% очень высокая. "
                   f"Рассмотрите ½ или ¼ Келли.")
    else:
        st.success(f"Доля Келли {_f_full*100:.1f}% укладывается в разумные рамки. "
                   f"Для консервативной торговли используйте ½ или ¼ Келли.")

    with st.expander("Метод корректировки риска", expanded=False):
        _n_sim = st.number_input("Число одновременных сделок",
                                  min_value=1, max_value=20, value=5,
                                  step=1, key="kelly_n_sim")
        _f_used = st.selectbox("Использовать долю Келли",
                                ["Полный", "½", "¼"],
                                index=1, key="kelly_frac_sel")
        _f_map = {"Полный": _f_full, "½": _f_half, "¼": _f_quarter}
        _f_use = _f_map[_f_used]

        _rows_risk = []
        _capital = 1.0
        for i in range(int(_n_sim)):
            _invest = _capital * _f_use
            _rows_risk.append({
                "#": i + 1,
                "Доступный капитал, %": round(_capital * 100, 2),
                "Инвестировано, %": round(_invest * 100, 2),
                "Остаток, %": round((_capital - _invest) * 100, 2),
                "Сумма, ₽": round(_invest * _deposit, 2),
            })
            _capital -= _invest
        _df_risk = pd.DataFrame(_rows_risk)

        # [PATCH 5] Начальный вид карточек на мобильных.
        if "kelly_view_mode" not in st.session_state:
            st.session_state.kelly_view_mode = "Карточки (мобильный)"

        _view_mode_kelly = st.radio(
            "Вид таблицы риска",
            ["Таблица", "Карточки (мобильный)"],
            index=(0 if st.session_state.kelly_view_mode == "Таблица" else 1),
            horizontal=True,
            key="kelly_view_mode_radio",
            label_visibility="collapsed")
        st.session_state.kelly_view_mode = _view_mode_kelly

        if st.session_state.kelly_view_mode == "Карточки (мобильный)":
            for _, _row_r in _df_risk.iterrows():
                _num = int(_row_r["#"])
                _cap = float(_row_r["Доступный капитал, %"])
                _inv = float(_row_r["Инвестировано, %"])
                _rest = float(_row_r["Остаток, %"])
                _sum = float(_row_r["Сумма, ₽"])

                with st.container(border=True):
                    st.markdown(
                        f"<div style='font-size:.95rem; font-weight:700; "
                        f"color:#1a3b4f; margin-bottom:4px;'>"
                        f"Сделка #{_num}</div>"
                        f"<div style='font-size:.85rem; line-height:1.7;'>"
                        f"Доступно: <b>{_cap:.2f} %</b><br>"
                        f"Инвестировано: <b style='color:#1e88e5;'>"
                        f"{_inv:.2f} %</b><br>"
                        f"Остаток: <b>{_rest:.2f} %</b><br>"
                        f"Сумма ставки: <b style='color:#00a651;'>"
                        f"{_sum:,.2f} ₽</b>"
                        f"</div>",
                        unsafe_allow_html=True)
        else:
            st.dataframe(_df_risk, use_container_width=True, hide_index=True,
                         height=min(120 + 35 * len(_df_risk), 400))

        st.caption(f"Итоговая экспозиция при {_n_sim} сделках: "
                   f"{(1 - _capital) * 100:.2f}% "
                   f"= {(1 - _capital) * _deposit:,.2f} ₽")


# ==================================================================
# ============ ВКЛАДКА 10: ОПОВЕЩЕНИЯ =============================
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
        if st.button("Обновить", use_container_width=True,
                     type="primary", key="alerts_manual_refresh"):
            st.session_state.sheet_cache_buster += 1
            st.session_state.alerts_loaded_at = None
            st.session_state["_alert_levels_cache"] = {}
            st.rerun()

    with _ctrl2:
        with st.popover("Excel", use_container_width=True):
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
        st.warning(f"{st.session_state.alerts_error}")

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

                _prox = CHECKLIST_RULES["level_proximity_pct"]
                _need_volume_analysis = (
                    _buy_active or _sell_active
                    or (_buy_dev is not None and abs(_buy_dev) <= _prox)
                    or (_sell_dev is not None and abs(_sell_dev) <= _prox)
                )

                _vol_an = {}
                if _need_volume_analysis:
                    try:
                        _secid_an = resolve_underlying_secid(_ticker.upper(),
                                                              _category)
                        if _secid_an:
                            _eng_an, _mkt_an = _get_engine_market(_category)
                            _vol_an = analyze_level_activity(
                                _secid_an, _eng_an, _mkt_an,
                                _lvl_buy, _lvl_sell) or {}
                    except Exception:
                        _vol_an = {}

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
                    "trend": str(_row.get("Тренд", "")).strip(),
                    "wave": str(_row.get("Волна", "")).strip(),
                    "tendency": str(_row.get("Тенденция", "")).strip(),
                    "at_buy_today": bool(_vol_an.get("at_buy_today")),
                    "at_sell_today": bool(_vol_an.get("at_sell_today")),
                    "high_volume": bool(_vol_an.get("high_volume")),
                    "intraday_spike": bool(_vol_an.get("intraday_spike")),
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

            st.caption("Автообновление каждые 30 секунд · "
                       "Цена = CLOSE последнего дневного бара (MOEX ISS)")

            st.markdown("---")

            if st.session_state.alerts_view_mode == "Карточки":
                _cards_per_row = 2
                for _i in range(0, len(_rows_out), _cards_per_row):
                    _cols = st.columns(_cards_per_row)
                    for _j, _r in enumerate(_rows_out[_i:_i + _cards_per_row]):
                        with _cols[_j]:
                            _render_alert_card(_r)
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
                        "Покупка активна":   lambda v: "АКТИВНО" if v else "·",
                        "Продажа активна":   lambda v: "АКТИВНО" if v else "·"},
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
                    "Экспорт оповещений (CSV)",
                    data=_df_export.to_csv(index=False).encode("utf-8-sig"),
                    file_name="alerts.csv", mime="text/csv",
                    use_container_width=True,
                    key="alerts_export_csv")

        _render_alerts_live()


# ==================================================================
# ФИНАЛЬНЫЙ ДИСПЕТЧЕР ВКЛАДОК
# ==================================================================
# [PATCH 2] Резервная копия вызывается ОДИН РАЗ до рендера выбранной
# вкладки. Функция НЕ обёрнута в @st.fragment — импорт должен
# применяться до создания виджетов вкладки.
#
# [PATCH 5] Доска опционов остаётся ВНЕ адаптивного контейнера —
# чтобы не затронуть её CSS. Остальные вкладки — внутри
# st.container(key="responsive_content"), стилизованного через CSS
# в начале файла (класс .st-key-responsive_content).
# ==================================================================
_render_backup_controls()

_RENDERERS = {
    "Калькулятор":    _render_calc_tab,
    "Позиция":        _render_position_tab,
    "What-if":        _render_whatif_tab,
    "Heatmap IV":     _render_heatmap_tab,
    "IV Rank":        _render_ivrank_tab,
    "Skew":           _render_skew_tab,
    "Журнал":         _render_journal_tab,
    "Келли":          _render_kelly_tab,
    "Оповещения":     _render_alerts_tab,
}

if _active_tab == "Доска опционов":
    # Доска остаётся вне адаптивного контейнера.
    _render_board_tab()
else:
    with st.container(key="responsive_content"):
        _RENDERERS[_active_tab]()
