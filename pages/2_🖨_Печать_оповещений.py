"""
Дополнительная страница «Печать оповещений».
Streamlit автоматически добавляет её в сайдбар при наличии папки pages/.
app.py НЕ МОДИФИЦИРУЕТСЯ.

Читает session_state текущей сессии (alerts_df, _alert_checks) и вшивает
их в alerts_print.html перед рендером в iframe. Если session_state пуст
(пользователь открыл страницу раньше, чем вкладку «Оповещения» в app.py),
данные подтягиваются из Google Sheets на сервере.
"""

import json
import io
from pathlib import Path
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests

st.set_page_config(
    page_title="Печать оповещений — A4",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# URL тот же, что в app.py
ALERTS_SHEET_CSV = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRKISFld2M8tFEEE1o1Fo5nQgHP6qMmOFu57JDmi-t-Y4Xj67N5SQP9uQ02JW2Ixyd663zewMYY1hfx"
    "/pub?output=csv"
)

HTML_PATH = Path(__file__).resolve().parent.parent / "alerts_print.html"


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_alerts_from_gsheets() -> pd.DataFrame:
    """Серверная загрузка Google Sheets (без CORS-проблем)."""
    r = requests.get(ALERTS_SHEET_CSV, timeout=15,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def _normalize_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Приводим сырые заголовки листа к каноническим (как в app.py)."""
    col_map = {}
    for c in df.columns:
        cs = str(c).strip().lower()
        if "тикер" in cs:
            col_map[c] = "Тикер БА"
        elif "категор" in cs:
            col_map[c] = "Категория БА"
        elif cs == "тренд":
            col_map[c] = "Тренд"
        elif cs == "волна":
            col_map[c] = "Волна"
        elif cs == "тенденция":
            col_map[c] = "Тенденция"
        elif cs in ("тф уровня", "tf уровня", "tf", "timeframe"):
            col_map[c] = "ТФ уровня"
        elif "покуп" in cs:
            col_map[c] = "Уровень покупок"
        elif "продаж" in cs:
            col_map[c] = "Уровень продаж"
    return df.rename(columns=col_map)


def _build_inject() -> dict:
    """Собираем INJECT: сначала session_state, затем Google Sheets, иначе пусто."""
    inject = {"alerts": [], "checks": {}, "source": "none"}

    # 1) session_state (если пользователь уже заходил на «Оповещения» в app.py)
    df_ss = st.session_state.get("alerts_df")
    if isinstance(df_ss, pd.DataFrame) and not df_ss.empty:
        # отбрасываем несериализуемые / лишние колонки
        keep = [c for c in (
            "Тикер БА", "Категория БА", "Тренд", "Волна",
            "Тенденция", "ТФ уровня", "Уровень покупок", "Уровень продаж",
        ) if c in df_ss.columns]
        try:
            inject["alerts"] = df_ss[keep].to_dict(orient="records")
            inject["source"] = "app.py → session_state"
        except Exception:
            inject["alerts"] = []

    # 2) если session_state пуст — серверный запрос к Google Sheets
    if not inject["alerts"]:
        try:
            raw = _fetch_alerts_from_gsheets()
            norm = _normalize_alerts(raw)
            keep = [c for c in (
                "Тикер БА", "Категория БА", "Тренд", "Волна",
                "Тенденция", "ТФ уровня", "Уровень покупок", "Уровень продаж",
            ) if c in norm.columns]
            inject["alerts"] = norm[keep].to_dict(orient="records")
            inject["source"] = "Google Sheets (сервер)"
        except Exception as e:
            inject["source"] = f"ошибка загрузки: {e}"

    # 3) чек-боксы из app.py
    checks = st.session_state.get("_alert_checks") or {}
    inject["checks"] = checks

    return inject


st.title("🖨 Печать оповещений (A4)")

if not HTML_PATH.exists():
    st.error(
        f"Файл `{HTML_PATH.name}` не найден рядом с `app.py`.\n\n"
        f"Положите `alerts_print.html` в папку проекта."
    )
    st.stop()

raw_html = HTML_PATH.read_text(encoding="utf-8")
inject = _build_inject()
inject_json = json.dumps(inject, ensure_ascii=False, default=str).replace("</", "<\\/")

# Подставляем данные в плейсхолдер
html_final = raw_html.replace("/*__INJECT_ALERTS__*/null", inject_json)

# Немного статуса
_st = inject.get("source", "—")
_n = len(inject.get("alerts") or [])
_cap = (
    f"Загружено **{_n}** строк · источник: `{_st}` · "
    f"обновлено в {datetime.now().strftime('%H:%M:%S')}"
)
st.caption(_cap)

# Рендер внутри iframe
components.html(html_final, height=1500, scrolling=True)
