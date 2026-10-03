import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import json
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta

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

ENGINE_MARKET_MAP = {
    'Фьючерс': ('futures', 'forts'),
    'Акция':   ('stock', 'shares'),
    'Индекс':  ('stock', 'index'),
    'Валюта':  ('futures', 'forts'),
    'Товар':   ('futures', 'forts'),
}

# ================= Справочник инструментов MOEX =================
MOEX_INSTRUMENTS = {
    "Индексы": {
        "RTS":      "Индекс РТС",
        "MIX":      "Индекс МосБиржи",
        "RVI":      "Индекс волатильности RVI",
        "MOEXCNY":  "Индекс МосБиржи в юанях",
        "RGBI":     "Индекс RGBI",
        "MMI":      "Индекс металлов и добычи",
        "FNI":      "Индекс финансов",
        "OGI":      "Индекс нефти и газа",
        "MXI":      "Индекс МосБиржи (мини)",
        "RTSM":     "Индекс РТС (мини)",
    },
    "Акции": {
        "GAZR": "Газпром",
        "SBRF": "Сбербанк (о.с.)",
        "SBPR": "Сбербанк (п.с.)",
        "LKOH": "ЛУКОЙЛ",
        "ROSN": "Роснефть",
        "NOTK": "НОВАТЭК",
        "TATN": "Татнефть (о.с.)",
        "TATP": "Татнефть (п.с.)",
        "SNGR": "Сургутнефтегаз (о.с.)",
        "SNGP": "Сургутнефтегаз (п.с.)",
        "MTSS": "МТС",
        "MGNT": "Магнит",
        "GMKN": "Норникель",
        "NLMK": "НЛМК",
        "CHMF": "Северсталь",
        "ALRS": "АЛРОСА",
        "VTBR": "ВТБ",
        "MOEX": "Московская Биржа",
        "AFKS": "АФК Система",
        "IRAO": "Интер РАО",
        "HYDR": "РусГидро",
        "RTKM": "Ростелеком",
        "PLZL": "Полюс",
        "MAGN": "ММК",
        "YDEX": "Яндекс",
        "PHOR": "ФосАгро",
        "RUAL": "РУСАЛ",
        "FEES": "ФСК ЕЭС",
        "TRNF": "Транснефть (п.с.)",
        "AFLT": "Аэрофлот",
        "SIBN": "Газпром нефть",
        "PIKK": "ПИК",
        "FLOT": "Совкомфлот",
        "CBOM": "МКБ",
        "SGZH": "Сегежа",
        "BSPB": "Банк Санкт-Петербург",
        "KMAZ": "КАМАЗ",
        "ASTR": "Группа Астра",
        "SVCB": "Совкомбанк",
    },
    "Валюты": {
        "Si":   "Доллар США / Рубль",
        "Eu":   "Евро / Рубль",
        "CNY":  "Юань / Рубль",
        "TRY":  "Турецкая лира / Рубль",
        "HKD":  "Гонконгский доллар / Рубль",
        "AED":  "Дирхам ОАЭ / Рубль",
        "KZT":  "Казахстанский тенге / Рубль",
        "AMD":  "Армянский драм / Рубль",
        "BYN":  "Белорусский рубль / Рубль",
        "ED":   "Евро / Доллар",
        "AUDU": "Австралийский доллар / Доллар",
        "GBPU": "Фунт стерлингов / Доллар",
        "UCAD": "Доллар / Канадский доллар",
        "UCHF": "Доллар / Швейцарский франк",
        "UJPY": "Доллар / Японская йена",
        "UCNY": "Доллар / Юань",
    },
    "Товары": {
        "BR":    "Нефть Brent",
        "CL":    "Нефть Light Sweet",
        "GOLD":  "Золото",
        "SILV":  "Серебро",
        "PLD":   "Палладий",
        "PLT":   "Платина",
        "ALMN":  "Алюминий",
        "Co":    "Медь",
        "Nl":    "Никель",
        "Zn":    "Цинк",
        "NG":    "Природный газ",
        "WHEAT": "Пшеница",
        "SUGR":  "Сахар",
    },
}

CATEGORY_TO_ASSET_TYPE = {
    "Индексы": "Индекс",
    "Акции":   "Акция",
    "Валюты":  "Валюта",
    "Товары":  "Товар",
}

# Справочные тикеры TradingView для непрерывных фьючерсов.
# Используются только для документирования. Графики строятся на данных MOEX ISS.
TV_TICKER_REFERENCE = {
    "RTS": "RI1!", "MIX": "MIX1!", "RVI": "VI1!", "RGBI": "RB1!",
    "Si": "SI1!", "Eu": "EU1!", "CNY": "CR1!", "BR": "BR1!",
    "GOLD": "GD1!", "SILV": "SV1!", "NG": "NG1!",
}


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


# ================= MOEX Candles + склейка фьючерсов =================

MSK_OFFSET_SECONDS = 3 * 3600


@st.cache_data(ttl=3600, show_spinner=False)
def list_moex_securities(engine: str, market: str) -> pd.DataFrame:
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/securities.json"
    try:
        r = requests.get(url, params={"iss.meta": "off", "iss.only": "securities"}, timeout=20)
        r.raise_for_status()
        data = r.json()["securities"]
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame(data["data"], columns=data["columns"])


@st.cache_data(ttl=3600, show_spinner=False)
def get_futures_contracts(asset_code: str) -> list:
    """Список контрактов одного базового актива, отсортированных по дате экспирации."""
    df = list_moex_securities("futures", "forts")
    if df.empty or "ASSETCODE" not in df.columns or "LASTTRADEDATE" not in df.columns:
        return []
    df = df[df["ASSETCODE"] == asset_code].dropna(subset=["LASTTRADEDATE", "SECID"])
    df = df.sort_values("LASTTRADEDATE").reset_index(drop=True)
    return [
        {"secid": row.SECID, "lasttradedate": row.LASTTRADEDATE}
        for row in df.itertuples()
    ]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_bars(secid: str, interval: int = 24, days: int = 365,
               engine: str = "futures", market: str = "forts"):
    end = datetime.now()
    start = end - timedelta(days=days)
    url = (
        f"https://iss.moex.com/iss/engines/{engine}/markets/{market}"
        f"/securities/{secid}/candles.json"
    )
    params = {
        "from": start.strftime("%Y-%m-%d"),
        "till": end.strftime("%Y-%m-%d"),
        "interval": interval,
        "iss.meta": "off",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return pd.DataFrame()
    cols = data.get("candles", {}).get("columns", [])
    rows = data.get("candles", {}).get("data", [])
    if not rows or not cols:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=cols)
    df["begin"] = pd.to_datetime(df["begin"])
    return df.sort_values("begin").reset_index(drop=True)


def build_continuous_series(asset_code: str, interval: int, days: int,
                            rollover_days_before: int = 5) -> pd.DataFrame:
    """Склейка фьючерсов: последовательное сшивание контрактов с коррекцией цен."""
    contracts = get_futures_contracts(asset_code)
    if not contracts:
        return pd.DataFrame()

    now = datetime.now()
    start_dt = now - timedelta(days=days)

    relevant = []
    for i, c in enumerate(contracts):
        ltd = pd.to_datetime(c["lasttradedate"]).to_pydatetime()
        if ltd >= start_dt:
            if i > 0 and not relevant:
                prev = contracts[i - 1]
                prev_ltd = pd.to_datetime(prev["lasttradedate"]).to_pydatetime()
                if prev_ltd >= start_dt:
                    relevant.append(prev)
            relevant.append(c)
    if not relevant:
        relevant = [contracts[-1]]

    pieces = []
    for c in relevant:
        ltd = pd.to_datetime(c["lasttradedate"]).to_pydatetime()
        rollover_dt = ltd - timedelta(days=rollover_days_before)
        df = fetch_bars(c["secid"], interval=interval, days=days,
                        engine="futures", market="forts")
        if df.empty:
            continue
        df = df[df["begin"] <= pd.Timestamp(rollover_dt)].copy()
        if df.empty:
            continue
        df["_rollover_dt"] = rollover_dt
        pieces.append(df)

    if not pieces:
        return pd.DataFrame()

    pieces.sort(key=lambda d: d["_rollover_dt"].iloc[0])

    result_parts = []
    for piece in pieces:
        if not result_parts:
            result_parts.append(piece)
            continue
        prev_close = result_parts[-1]["close"].iloc[-1]
        curr_open = piece["open"].iloc[0]
        shift = curr_open - prev_close
        for rp in result_parts:
            for col in ("open", "high", "low", "close"):
                rp[col] = rp[col] + shift
        result_parts.append(piece)

    df = pd.concat(result_parts, ignore_index=True)
    df = df.sort_values("begin").drop_duplicates(subset=["begin"], keep="last")
    return df.reset_index(drop=True)


def df_to_bars(df: pd.DataFrame, intraday: bool):
    bars, vols = [], []
    for _, row in df.iterrows():
        if intraday:
            t = int(row["begin"].value // 10**9) - MSK_OFFSET_SECONDS
        else:
            t = row["begin"].strftime("%Y-%m-%d")
        bars.append({
            "time": t,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })
        vols.append({"time": t, "value": float(row["volume"]), "color": "black"})
    return bars, vols


# ================= Мост HTML ↔ Python =================

def push_expiry_to_calculator(expiry_str: str, series_code: str = ""):
    js = f"""
    <script>
    (function() {{
      const payload = {{ type: 'setExpiry', value: {expiry_str!r}, series_code: {series_code!r} }};
      function send() {{
        try {{
          const frames = window.parent.document.querySelectorAll('iframe');
          frames.forEach(f => {{
            try {{ f.contentWindow.postMessage(payload, '*'); }} catch (e) {{}}
          }});
        }} catch (e) {{}}
      }}
      send();
      setTimeout(send, 300);
      setTimeout(send, 1000);
      setTimeout(send, 2500);
    }})();
    </script>
    """
    components.html(js, height=0)


def push_bars_to_calculator(ticker, d1_bars, d1_vols, h1_bars, h1_vols):
    payload = {
        "type": "setBars",
        "ticker": ticker,
        "d1": d1_bars,
        "d1_vol": d1_vols,
        "h1": h1_bars,
        "h1_vol": h1_vols,
    }
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
      setTimeout(send, 300);
      setTimeout(send, 1000);
      setTimeout(send, 2500);
    }})();
    </script>
    """
    components.html(js, height=0)


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
                 "чтобы подставить его в поле «Базовый актив»", expanded=False):
    filter_text = st.text_input(
        "🔍 Поиск по коду или названию",
        key="dict_filter",
        placeholder="GAZP, Сбер, золото…",
    ).strip().lower()

    dict_tabs = st.tabs(list(MOEX_INSTRUMENTS.keys()))
    for tab, (category, items) in zip(dict_tabs, MOEX_INSTRUMENTS.items()):
        with tab:
            filtered = {
                code: name for code, name in items.items()
                if not filter_text
                or filter_text in code.lower()
                or filter_text in name.lower()
            }
            if not filtered:
                st.caption("Ничего не найдено.")
                continue
            n_cols = 4
            cols = st.columns(n_cols)
            for i, (code, name) in enumerate(filtered.items()):
                with cols[i % n_cols]:
                    if st.button(
                        code,
                        key=f"dict_{category}_{code}",
                        use_container_width=True,
                        help=f"{name} — нажмите, чтобы подставить",
                    ):
                        st.session_state.asset_input = code
                        st.session_state.asset_type_ui = CATEGORY_TO_ASSET_TYPE[category]
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
    options = [f"{s['expiry']} — {s['code']}" for s in st.session_state.series_list]
    chosen = st.selectbox("Дата экспирации (серия)", options, index=0)
    selected = st.session_state.series_list[options.index(chosen)]
    series_code = selected["code"]
    expiry_str = selected["expiry"]

    push_expiry_to_calculator(expiry_str, series_code)

    st.caption(f"Выбрана дата экспирации: **{expiry_str}** "
               f"(серия `{series_code}`)")

    # --- Биржевые графики ---
    if asset_type_ui == "Фьючерс":
        with st.spinner(f"Построение склейки фьючерса {asset} (D1)..."):
            df_d1 = build_continuous_series(asset, interval=24, days=365)
        with st.spinner(f"Построение склейки фьючерса {asset} (H1)..."):
            df_h1 = build_continuous_series(asset, interval=60, days=60)
        chart_label = f"{asset} (склейка)"
    else:
        engine, market = ENGINE_MARKET_MAP.get(asset_type_ui, ("futures", "forts"))
        with st.spinner(f"Загрузка баров для графиков ({asset})..."):
            df_d1 = fetch_bars(asset, interval=24, days=365,
                               engine=engine, market=market)
            df_h1 = fetch_bars(asset, interval=60, days=60,
                               engine=engine, market=market)
        chart_label = asset

    d1_bars, d1_vols = ([], [])
    h1_bars, h1_vols = ([], [])
    if not df_d1.empty:
        d1_bars, d1_vols = df_to_bars(df_d1, intraday=False)
    if not df_h1.empty:
        h1_bars, h1_vols = df_to_bars(df_h1, intraday=True)

    push_bars_to_calculator(chart_label, d1_bars, d1_vols, h1_bars, h1_vols)

    if df_d1.empty and df_h1.empty:
        st.info(f"Не удалось загрузить бары для графика «{chart_label}». "
                f"Проверьте, что инструмент торгуется на MOEX.")

    # --- Информация о серии ---
    try:
        info = fetch_series_info(asset, asset_type_ui, series_code)
        with st.expander("Об опционной серии", expanded=False):
            st.json(info, expanded=True)
    except Exception as e:
        st.warning(f"Не удалось загрузить информацию о серии: {e}")

    # --- Доска опционов ---
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
            strike_bg = "#e3e7ec"
            styles = []
            for col in row.index:
                if col.startswith("Call_"):
                    styles.append(f"background-color: {call_bg}")
                elif col.startswith("Put_"):
                    styles.append(f"background-color: {put_bg}")
                elif col in ("Strike", "IV_%"):
                    styles.append(f"background-color: {strike_bg}; font-weight: bold")
                else:
                    styles.append("")
            return styles

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
