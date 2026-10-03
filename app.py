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

# ---------- Немного CSS, чтобы iframe не «прилипал» ----------
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

# Соответствие UI-категории → engine/market для MOEX ISS candles
ENGINE_MARKET_MAP = {
    'Фьючерс': ('futures', 'forts'),
    'Акция':   ('stock', 'shares'),
    'Индекс':  ('stock', 'index'),
    'Валюта':  ('futures', 'forts'),  # опционы на валюту — это опционы на фьючерс
    'Товар':   ('futures', 'forts'),
}


@st.cache_data(ttl=1800, show_spinner=False)
def get_asset_code_and_type(asset_input: str, asset_type_ui: str):
    """Определяем код актива и его тип для MOEX ISS. Кэш — 30 минут."""
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


# ================= MOEX Candles (для графиков) =================

# Москва — UTC+3 (без перехода на летнее время с 2014 г.)
MSK_OFFSET_SECONDS = 3 * 3600


@st.cache_data(ttl=300, show_spinner=False)
def fetch_bars(secid: str, interval: int = 24, days: int = 365,
               engine: str = "futures", market: str = "forts"):
    """Загружает бары (OHLCV) с MOEX ISS.

    interval: 1 (мин), 10, 60 (H1), 24 (D1), 7 (неделя), 31 (месяц)
    """
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
    except Exception as e:
        st.warning(f"Ошибка загрузки баров {secid} (interval={interval}): {e}")
        return pd.DataFrame()

    cols = data.get("candles", {}).get("columns", [])
    rows = data.get("candles", {}).get("data", [])
    if not rows or not cols:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=cols)
    df["begin"] = pd.to_datetime(df["begin"])
    df = df.sort_values("begin").reset_index(drop=True)
    return df


def df_to_bars(df: pd.DataFrame, intraday: bool):
    """Преобразует DataFrame со свечами в формат Lightweight Charts.

    Для дневного таймфрейма time = 'YYYY-MM-DD' (business day).
    Для часового — UNIX-таймстемп в секундах (MSK → UTC).
    """
    bars, vols = [], []
    for _, row in df.iterrows():
        if intraday:
            # pandas .value — наносекунды от эпохи (naive = UTC).
            # MOEX отдаёт время в MSK, поэтому вычитаем смещение,
            # чтобы получить настоящий UTC.
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
        vols.append({
            "time": t,
            "value": float(row["volume"]),
            "color": "black",
        })
    return bars, vols


# ================= Мост HTML ↔ Python =================

def push_expiry_to_calculator(expiry_str: str, series_code: str = ""):
    """Отправляет дату экспирации в iframe калькулятора через postMessage."""
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


def push_bars_to_calculator(ticker: str,
                            d1_bars, d1_vols,
                            h1_bars, h1_vols):
    """Отправляет бары в iframe калькулятора через postMessage."""
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

# --- Верхний блок: калькулятор (iframe) ---
calc_html = Path("index.html").read_text(encoding="utf-8")
components.html(calc_html, height=900, scrolling=True)

st.markdown("---")
st.header("Выберите опционную серию")

col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    asset = st.text_input("Базовый актив", value="RTS",
                          placeholder="SI, GAZP, SBRF...").strip().upper()
with col2:
    asset_type_ui = st.selectbox(
        "Категория базового актива",
        ["Фьючерс", "Акция", "Валюта", "Товар", "Индекс"],
    )
with col3:
    st.write("")
    load_btn = st.button("Загрузить доску опционов", use_container_width=True)

# Кнопка ручного обновления (сброс кэша)
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
    expiry_str = selected["expiry"]          # ожидается формат YYYY-MM-DD

    # >>> Передаём дату в калькулятор через postMessage <<<
    push_expiry_to_calculator(expiry_str, series_code)

    st.caption(f"Выбрана дата экспирации: **{expiry_str}** "
               f"(серия `{series_code}`)")

    # --- Биржевые графики: грузим бары и отправляем в iframe ---
    engine, market = ENGINE_MARKET_MAP.get(asset_type_ui, ("futures", "forts"))
    with st.spinner("Загрузка баров для графиков..."):
        df_d1 = fetch_bars(asset, interval=24, days=365,
                           engine=engine, market=market)
        df_h1 = fetch_bars(asset, interval=60, days=60,
                           engine=engine, market=market)

    d1_bars, d1_vols = ([], [])
    h1_bars, h1_vols = ([], [])
    if not df_d1.empty:
        d1_bars, d1_vols = df_to_bars(df_d1, intraday=False)
    if not df_h1.empty:
        h1_bars, h1_vols = df_to_bars(df_h1, intraday=True)

    push_bars_to_calculator(asset, d1_bars, d1_vols, h1_bars, h1_vols)

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
                  {
                      "Strike": "{:.0f}",   # целое число
                      "IV_%":   "{:.2f}",   # 2 знака после точки
                  },
                  precision=4,
                  na_rep="—",
              ),
            use_container_width=True,
            height=600,
        )

        # --- Улыбка волатильности ---
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
