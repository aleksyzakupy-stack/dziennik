import io
import streamlit as st
import pandas as pd
import datetime
import os
from typing import Any, Dict

import bcrypt
import yaml
from yaml.loader import SafeLoader
import matplotlib.pyplot as plt
import streamlit_authenticator as stauth

# --- Конфигурация страницы ---
st.set_page_config(page_title="📓 Dziennik nastroju", layout="wide")

# --- Файл пользователей ---
USERS_FILE = "users.yaml"
DEFAULT_ADMIN_USERNAME = "Kasper"
DEFAULT_ADMIN_NAME = "Lek. Aleksy Kasperowicz"
DEFAULT_ADMIN_HASH = "$2b$12$ei/CshYLjrjCx5xp0vKZ1.saL2avwM2mel1ySKKrxXjAJy6C3sEQC"


def load_users_config() -> Dict[str, Any]:
    """Ensure the users file exists and return its configuration."""

    def _load_file() -> Dict[str, Any]:
        if not os.path.exists(USERS_FILE):
            return {"credentials": {"usernames": {}}}
        with open(USERS_FILE) as fh:
            data = yaml.load(fh, Loader=SafeLoader) or {}
        return data

    config_data: Dict[str, Any] = _load_file()
    credentials: Dict[str, Any] = config_data.setdefault("credentials", {}).setdefault("usernames", {})

    def get_secret(key: str):
        try:
            return st.secrets[key]
        except Exception:
            return os.getenv(key)

    admin_username = get_secret("ADMIN_USERNAME")
    admin_password = get_secret("ADMIN_PASSWORD")
    admin_display_name = get_secret("ADMIN_DISPLAY_NAME")

    updated = False

    if admin_username and admin_password:
        entry = credentials.setdefault(admin_username, {})
        stored_hash = entry.get("password")
        if (
            stored_hash is None
            or not bcrypt.checkpw(admin_password.encode(), stored_hash.encode())
        ):
            entry["password"] = stauth.Hasher([admin_password]).generate()[0]
            updated = True
        entry_name = admin_display_name or entry.get("name") or admin_username
        if entry.get("name") != entry_name:
            entry["name"] = entry_name
            updated = True
        if entry.get("role") != "admin":
            entry["role"] = "admin"
            updated = True
    else:
        entry = credentials.setdefault(
            DEFAULT_ADMIN_USERNAME,
            {
                "name": DEFAULT_ADMIN_NAME,
                "password": DEFAULT_ADMIN_HASH,
                "role": "admin",
            },
        )
        if entry.get("password") is None:
            entry["password"] = DEFAULT_ADMIN_HASH
            updated = True
        if entry.get("role") != "admin":
            entry["role"] = "admin"
            updated = True
        if not entry.get("name"):
            entry["name"] = DEFAULT_ADMIN_NAME
            updated = True

    if updated or not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as fh:
            yaml.dump(config_data, fh)

    return config_data


config = load_users_config()

# --- Авторизация ---
authenticator = stauth.Authenticate(
    config['credentials'],
    "dziennik_cookie",
    "abcdef",
    cookie_expiry_days=1
)

# --- Стандартные значения состояния ---
st.session_state.setdefault("authentication_status", None)
st.session_state.setdefault("name", None)
st.session_state.setdefault("username", None)
st.session_state.setdefault("logout", False)

# --- Логин/регистрация ---
if st.session_state.get("authentication_status") is not True:
    st.title("📓 Dziennik nastroju")
    st.markdown("Wybierz odpowiednią opcję, aby kontynuować.")

    choice = st.radio(
        "Co chcesz zrobić?",
        ("🔐 Logowanie", "🆕 Rejestracja"),
        horizontal=True
    )

    if choice == "🔐 Logowanie":
        name, authentication_status, username = authenticator.login(
            "Logowanie",
            location="main"
        )

        if authentication_status:
            st.session_state.update(
                {
                    "authentication_status": True,
                    "name": name,
                    "username": username
                }
            )
            st.rerun()
        elif authentication_status is False:
            st.error("❌ Nieprawidłowy login lub hasło")
        else:
            st.warning("🔑 Wprowadź login i hasło")
    else:
        with st.form("register_form"):
            new_name = st.text_input("Imię i pierwsze 3 litery nazwiska")
            new_username = st.text_input("Login")
            new_password = st.text_input("Hasło", type="password")
            reg_submitted = st.form_submit_button("Zarejestruj")

        if reg_submitted:
            if new_username in config["credentials"]["usernames"]:
                st.error("❌ Taki login już istnieje")
            elif not new_name or not new_username or not new_password:
                st.error("⚠️ Wszystkie pola są wymagane")
            else:
                hashed = stauth.Hasher([new_password]).generate()[0]
                config["credentials"]["usernames"][new_username] = {
                    "name": new_name,
                    "password": hashed,
                    "role": "user"
                }
                with open(USERS_FILE, "w") as f:
                    yaml.dump(config, f)

                st.session_state.update(
                    {
                        "authentication_status": True,
                        "name": new_name,
                        "username": new_username,
                        "auto_login_message": "✅ Rejestracja udana! Zalogowano automatycznie."
                    }
                )
                st.rerun()

# --- Aktualne wartości z sesji ---
authentication_status = st.session_state.get("authentication_status")
name = st.session_state.get("name")
username = st.session_state.get("username")

# --- Если вошёл ---
if authentication_status:

    auto_message = st.session_state.pop("auto_login_message", None)
    if auto_message:
        st.success(auto_message)

    cookie_manager = getattr(authenticator, "cookie_manager", None)
    cookie_name = getattr(authenticator, "cookie_name", None)
    cookies_available = {}
    if cookie_manager is not None:
        getter = getattr(cookie_manager, "get_all", None)
        if callable(getter):
            try:
                cookies_available = getter() or {}
            except Exception:
                cookies_available = {}
        if not cookies_available and hasattr(cookie_manager, "cookies"):
            cookies_available = getattr(cookie_manager, "cookies", {})

    if cookie_name and cookie_name in cookies_available:
        try:
            authenticator.logout("🚪 Wyloguj", "sidebar")
        except KeyError:
            cookies_available.pop(cookie_name, None)
            if cookie_manager is not None and hasattr(cookie_manager, "cookies"):
                cookie_manager.cookies.pop(cookie_name, None)
            st.session_state["authentication_status"] = None
            st.session_state["name"] = None
            st.session_state["username"] = None
            st.session_state["logout"] = True
            st.session_state.pop("auto_login_message", None)
            st.rerun()
    else:
        if st.sidebar.button("🚪 Wyloguj", key="fallback_logout"):
            st.session_state["authentication_status"] = None
            st.session_state["name"] = None
            st.session_state["username"] = None
            st.session_state["logout"] = True
            st.session_state.pop("auto_login_message", None)
            st.rerun()

    st.sidebar.success(f"Zalogowano: {name}")

    # --- Роль пользователя ---
    user_record = config["credentials"]["usernames"].get(username)
    if not user_record:
        st.error("Nie znaleziono danych użytkownika. Prosimy zalogować się ponownie.")
        st.session_state["authentication_status"] = None
        st.session_state["name"] = None
        st.session_state["username"] = None
        st.session_state["logout"] = True
        st.rerun()
    role = user_record.get("role", "user")

    # --- Файл CSV пользователя ---
    os.makedirs("data", exist_ok=True)
    user_file = f"data/{username}.csv"

    COLUMNS = [
        "Data i czas",
        "Nastrój (0-10)",
        "Poziom lęku/napięcia (0-10)",
        "Objawy somatyczne",
        "Godzina zaśnięcia",
        "Godzina wybudzenia",
        "Liczba wybudzeń w nocy",
        "Subiektywna jakość snu (0-10)",
        "Energia/motywacja (0-10)",
        "Apetyt (0-10)",
        "Wykonane aktywności",
        "Zachowania impulsywne",
        "Uwagi"
    ]

    try:
        df = pd.read_csv(user_file)
    except FileNotFoundError:
        df = pd.DataFrame(columns=COLUMNS)

    def ensure_datetime(series: pd.Series) -> pd.Series:
        return pd.to_datetime(series, errors="coerce")

    # --- Определения чекбоксов ---
    OBJAWY = {
        "ks": "kołatanie serca", "d": "drżenie", "p": "nadmierne pocenie się",
        "bb": "bóle brzucha", "w": "wymioty", "ś": "ścisk w klatce/duszność",
        "zg": "zawroty głowy", "gwg": "gula w gardle", "nm": "napięcie mięśni",
        "m": "mrowienia", "bg": "ból głowy", "bkl": "ból w klatce piersiowej",
        "swu": "suchość w ustach"
    }
    AKTYWNOSCI = {"p": "praca", "n": "nauka", "d": "obowiązki domowe", "wf": "aktywność fizyczna"}
    IMPULSY = {"oż": "kompulsywne objadanie się", "su": "samouszkodzenia", "z": "zakupy kompulsywne", "h": "hazard", "s": "seks ryzykowny"}

    def prepare_counts(column: pd.Series) -> pd.Series:
        tokens = (
            column.dropna()
            .astype(str)
            .str.split(r",\s*")
            .explode()
            .str.strip()
        )
        if tokens.empty:
            return pd.Series(dtype="int64")
        tokens = tokens[tokens != ""]
        if tokens.empty:
            return pd.Series(dtype="int64")
        return tokens.value_counts().sort_values(ascending=False)

    def render_counts(title: str, counts: pd.Series, container) -> None:
        container.markdown(f"**{title}**")
        if counts.empty:
            container.write("Brak danych")
            return
        for item, count in counts.items():
            container.write(f"- **{item}** – {count}")

    def select_date_range(df_time: pd.DataFrame, key_prefix: str):
        if df_time.empty or "Data i czas" not in df_time:
            return None
        timestamps = ensure_datetime(df_time["Data i czas"])
        timestamps = timestamps.dropna()
        if timestamps.empty:
            return None
        min_date = timestamps.min().date()
        max_date = timestamps.max().date()
        selection = st.date_input(
            "Zakres dat",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{key_prefix}_date_range",
        )
        if isinstance(selection, tuple):
            start_date, end_date = selection
        else:
            start_date = selection
            end_date = selection
        start_date = start_date or min_date
        end_date = end_date or max_date
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        return start_date, end_date

    def filter_by_range(df_time: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
        if start_date is None or end_date is None or df_time.empty:
            return df_time
        filtered = df_time.copy()
        filtered["Data i czas"] = ensure_datetime(filtered["Data i czas"])
        mask = filtered["Data i czas"].dt.date.between(start_date, end_date)
        return filtered.loc[mask]

    def compute_daily_totals(df_time: pd.DataFrame, column: str) -> pd.Series:
        if column not in df_time or df_time.empty:
            return pd.Series(dtype="int64")
        working = df_time[["Data i czas", column]].copy()
        working["Data i czas"] = ensure_datetime(working["Data i czas"])
        working = working.dropna(subset=["Data i czas"])
        if working.empty:
            return pd.Series(dtype="int64")
        working[column] = (
            working[column]
            .fillna("")
            .astype(str)
            .apply(lambda value: sum(1 for item in value.split(",") if item.strip()))
        )
        working["Data"] = working["Data i czas"].dt.date
        grouped = working.groupby("Data")[column].sum().sort_index()
        grouped.name = column
        return grouped

    def render_daily_totals_chart(series: pd.Series, title: str, ylabel: str):
        st.markdown(f"**{title}**")
        if series.empty:
            st.info("Brak danych w wybranym okresie.")
            return
        fig, ax = plt.subplots()
        ax.plot(series.index, series.values, marker="o")
        ax.set_xlabel("Data")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        plt.xticks(rotation=45)
        st.pyplot(fig)

    def prepare_sleep_dataframe(df_time: pd.DataFrame) -> pd.DataFrame:
        if df_time.empty or "Data i czas" not in df_time:
            return pd.DataFrame()
        working = df_time.copy()
        working["Data i czas"] = ensure_datetime(working["Data i czas"])
        working = working.dropna(subset=["Data i czas"])
        if working.empty:
            return pd.DataFrame()
        working["Zaśnięcie_dt"] = pd.to_datetime(
            working.get("Godzina zaśnięcia"), format="%H:%M", errors="coerce"
        )
        working["Pobudka_dt"] = pd.to_datetime(
            working.get("Godzina wybudzenia"), format="%H:%M", errors="coerce"
        )
        working["Godzina zaśnięcia (h)"] = (
            working["Zaśnięcie_dt"].dt.hour + working["Zaśnięcie_dt"].dt.minute / 60
        )
        working["Godzina wybudzenia (h)"] = (
            working["Pobudka_dt"].dt.hour + working["Pobudka_dt"].dt.minute / 60
        )
        working["Długość snu (h)"] = (
            working["Pobudka_dt"] - working["Zaśnięcie_dt"]
        ).dt.total_seconds() / 3600
        if "Długość snu (h)" in working:
            working.loc[working["Długość snu (h)"] < 0, "Długość snu (h)"] += 24
        return working

    def get_numeric_series(df_input: pd.DataFrame, column: str) -> pd.Series:
        if column not in df_input:
            return pd.Series(dtype="float64")
        return pd.to_numeric(df_input[column], errors="coerce")

    def clear_pending_entry():
        for key in [
            "pending_entry",
            "pending_entry_date",
            "pending_entry_user",
        ]:
            st.session_state.pop(key, None)

    if role == "admin":
        st.title("👨‍⚕️ Panel admina")

        patient_files = sorted(f for f in os.listdir("data") if f.endswith(".csv"))
        if not patient_files:
            st.info("Brak zapisów pacjentów do wyświetlenia.")
        else:
            patients = [f.replace(".csv", "") for f in patient_files]
            tab_range, tab_day = st.tabs(["📈 Pacjent / zakres", "🗓 Pacjent / dzień"])

            with tab_range:
                selected_user_range = st.selectbox(
                    "Wybierz pacjenta",
                    patients,
                    key="admin_range_patient",
                )

                if selected_user_range:
                    file_path = os.path.join("data", f"{selected_user_range}.csv")
                    if os.path.exists(file_path):
                        df_patient = pd.read_csv(file_path)
                        if df_patient.empty:
                            st.info("Brak zapisów dla wybranego pacjenta.")
                        else:
                            st.markdown("### 📄 Wszystkie wpisy")
                            st.dataframe(df_patient, use_container_width=True)

                            st.markdown("### 📤 Eksport danych pacjenta")
                            csv_data = df_patient.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                "⬇️ Pobierz CSV",
                                data=csv_data,
                                file_name=f"{selected_user_range}_dziennik.csv",
                                mime="text/csv",
                            )

                            try:
                                import openpyxl  # type: ignore
                            except ImportError:
                                st.info("📎 Eksport do XLSX wymaga pakietu `openpyxl`.")
                            else:
                                buffer = io.BytesIO()
                                df_patient.to_excel(
                                    buffer, index=False, engine="openpyxl"
                                )
                                st.download_button(
                                    "⬇️ Pobierz XLSX",
                                    data=buffer.getvalue(),
                                    file_name=f"{selected_user_range}_dziennik.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                )

                            st.markdown("### 🗑 Usuń wpis pacjenta")
                            if not df_patient.empty:
                                admin_timestamps = (
                                    ensure_datetime(df_patient["Data i czas"])
                                    if "Data i czas" in df_patient
                                    else pd.Series(
                                        pd.NaT,
                                        index=df_patient.index,
                                        dtype="datetime64[ns]",
                                    )
                                )

                                def format_admin_entry(idx: int) -> str:
                                    ts = admin_timestamps.loc[idx]
                                    ts_display = (
                                        ts.strftime("%Y-%m-%d %H:%M")
                                        if not pd.isna(ts)
                                        else "Brak daty"
                                    )
                                    mood_display = (
                                        df_patient.at[idx, "Nastrój (0-10)"]
                                        if "Nastrój (0-10)" in df_patient
                                        else "–"
                                    )
                                    return f"{ts_display} · Nastrój: {mood_display}"

                                entry_to_delete = st.selectbox(
                                    "Wybierz wpis do usunięcia",
                                    options=list(df_patient.index),
                                    format_func=format_admin_entry,
                                    key=f"admin_delete_option_{selected_user_range}",
                                )

                                if st.button(
                                    "🗑 Usuń wybrany wpis",
                                    key=f"admin_delete_button_{selected_user_range}",
                                ):
                                    updated_df = (
                                        df_patient.drop(index=entry_to_delete)
                                        .reset_index(drop=True)
                                    )
                                    updated_df.to_csv(file_path, index=False)
                                    st.success("Wpis został usunięty.")
                                    st.rerun()
                            else:
                                st.info("Brak wpisów do usunięcia.")

                            st.markdown("### 📊 Najczęstsze wpisy (całość)")
                            col_all1, col_all2, col_all3 = st.columns(3)
                            render_counts(
                                "Objawy somatyczne",
                                prepare_counts(df_patient.get("Objawy somatyczne", pd.Series(dtype="object"))),
                                col_all1,
                            )
                            render_counts(
                                "Wykonane aktywności",
                                prepare_counts(df_patient.get("Wykonane aktywności", pd.Series(dtype="object"))),
                                col_all2,
                            )
                            render_counts(
                                "Zachowania impulsywne",
                                prepare_counts(df_patient.get("Zachowania impulsywne", pd.Series(dtype="object"))),
                                col_all3,
                            )

                            df_patient_time = df_patient.copy()
                            df_patient_time["Data i czas"] = ensure_datetime(
                                df_patient_time["Data i czas"]
                            )
                            df_patient_time = df_patient_time.dropna(subset=["Data i czas"])

                            if df_patient_time.empty:
                                st.info("Brak prawidłowych dat do analizy zakresu.")
                            else:
                                date_range = select_date_range(
                                    df_patient_time, f"{selected_user_range}_admin_range"
                                )
                                if date_range:
                                    start_date, end_date = date_range
                                    df_patient_filtered = filter_by_range(
                                        df_patient_time, start_date, end_date
                                    )
                                else:
                                    df_patient_filtered = df_patient_time

                                if df_patient_filtered.empty:
                                    st.info("Brak danych pacjenta w wybranym okresie.")
                                else:
                                    st.subheader("📈 Trendy pacjenta (wybrany zakres)")
                                    fig, ax = plt.subplots()
                                    for col, label in [
                                        ("Nastrój (0-10)", "Nastrój"),
                                        ("Poziom lęku/napięcia (0-10)", "Lęk"),
                                        ("Energia/motywacja (0-10)", "Energia"),
                                        ("Apetyt (0-10)", "Apetyt"),
                                    ]:
                                        if col in df_patient_filtered:
                                            ax.plot(
                                                df_patient_filtered["Data i czas"],
                                                df_patient_filtered[col],
                                                marker="o",
                                                label=label,
                                            )

                                    low = df_patient_filtered[
                                        df_patient_filtered["Nastrój (0-10)"] < 3
                                    ]
                                    if not low.empty:
                                        ax.scatter(
                                            low["Data i czas"],
                                            low["Nastrój (0-10)"],
                                            color="red",
                                            s=60,
                                            zorder=5,
                                            label="Bardzo niski nastrój",
                                        )

                                    ax.set_ylabel("Poziom (0–10)")
                                    ax.set_xlabel("Data")
                                    ax.legend()
                                    plt.xticks(rotation=45)
                                    st.pyplot(fig)

                                    st.subheader("🌙 Sen pacjenta")
                                    df_patient_sleep = prepare_sleep_dataframe(
                                        df_patient_filtered
                                    )
                                    if df_patient_sleep.empty:
                                        st.info(
                                            "Brak danych o śnie w wybranym okresie."
                                        )
                                    else:
                                        fig, ax = plt.subplots()
                                        if "Godzina zaśnięcia (h)" in df_patient_sleep:
                                            ax.plot(
                                                df_patient_sleep["Data i czas"],
                                                df_patient_sleep["Godzina zaśnięcia (h)"],
                                                marker="o",
                                                label="Zaśnięcie (godz.)",
                                            )
                                        if "Godzina wybudzenia (h)" in df_patient_sleep:
                                            ax.plot(
                                                df_patient_sleep["Data i czas"],
                                                df_patient_sleep["Godzina wybudzenia (h)"],
                                                marker="o",
                                                label="Pobudka (godz.)",
                                            )
                                        if "Liczba wybudzeń w nocy" in df_patient_sleep:
                                            ax.plot(
                                                df_patient_sleep["Data i czas"],
                                                df_patient_sleep["Liczba wybudzeń w nocy"],
                                                marker="x",
                                                label="Wybudzenia w nocy",
                                            )
                                        if "Subiektywna jakość snu (0-10)" in df_patient_sleep:
                                            ax.plot(
                                                df_patient_sleep["Data i czas"],
                                                df_patient_sleep["Subiektywna jakość snu (0-10)"],
                                                marker="s",
                                                label="Jakość snu (0-10)",
                                            )
                                        if "Długość snu (h)" in df_patient_sleep:
                                            ax.plot(
                                                df_patient_sleep["Data i czas"],
                                                df_patient_sleep["Długość snu (h)"],
                                                marker="d",
                                                label="Długość snu (h)",
                                            )

                                        ax.set_ylabel("Parametry snu")
                                        ax.set_xlabel("Data")
                                        ax.legend()
                                        plt.xticks(rotation=45)
                                        st.pyplot(fig)

                                        st.markdown("### 📊 Statystyki snu")
                                        numeric_sleep = get_numeric_series(
                                            df_patient_sleep,
                                            "Długość snu (h)",
                                        )
                                        numeric_wakeups = get_numeric_series(
                                            df_patient_sleep,
                                            "Liczba wybudzeń w nocy",
                                        )
                                        numeric_quality = get_numeric_series(
                                            df_patient_sleep,
                                            "Subiektywna jakość snu (0-10)",
                                        )

                                        avg_sleep = numeric_sleep.dropna().mean()
                                        avg_wakeups = numeric_wakeups.dropna().mean()
                                        avg_quality = numeric_quality.dropna().mean()
                                        total_wakeups = numeric_wakeups.dropna().sum()

                                        col1, col2, col3, col4 = st.columns(4)
                                        col1.metric(
                                            "Średnia długość snu",
                                            f"{avg_sleep:.1f} h"
                                            if not pd.isna(avg_sleep)
                                            else "–",
                                        )
                                        col2.metric(
                                            "Średnia liczba wybudzeń",
                                            f"{avg_wakeups:.1f}"
                                            if not pd.isna(avg_wakeups)
                                            else "–",
                                        )
                                        col3.metric(
                                            "Średnia jakość snu",
                                            f"{avg_quality:.1f}/10"
                                            if not pd.isna(avg_quality)
                                            else "–",
                                        )
                                        col4.metric(
                                            "Łączna liczba wybudzeń",
                                            f"{int(total_wakeups)}",
                                        )

                                        st.markdown("### 📋 Dane snu (wybrany zakres)")
                                        sleep_columns = [
                                            "Data i czas",
                                            "Godzina zaśnięcia",
                                            "Godzina wybudzenia",
                                            "Liczba wybudzeń w nocy",
                                            "Subiektywna jakość snu (0-10)",
                                            "Długość snu (h)",
                                        ]
                                        available_sleep_columns = [
                                            column
                                            for column in sleep_columns
                                            if column in df_patient_sleep
                                        ]
                                        if available_sleep_columns:
                                            sleep_table = df_patient_sleep[
                                                available_sleep_columns
                                            ]
                                            st.dataframe(
                                                sleep_table,
                                                use_container_width=True,
                                            )
                                        else:
                                            st.info(
                                                "Brak szczegółowych danych o śnie w wybranym okresie."
                                            )

                                    st.subheader(
                                        "📉 Objawy somatyczne i impulsywne zachowania"
                                    )
                                    render_daily_totals_chart(
                                        compute_daily_totals(
                                            df_patient_filtered,
                                            "Objawy somatyczne",
                                        ),
                                        "Objawy somatyczne na dzień",
                                        "Liczba objawów",
                                    )
                                    render_daily_totals_chart(
                                        compute_daily_totals(
                                            df_patient_filtered,
                                            "Zachowania impulsywne",
                                        ),
                                        "Zachowania impulsywne na dzień",
                                        "Liczba zachowań",
                                    )

                                    st.markdown("### 📋 Aktywności i objawy (zakres)")
                                    c1, c2, c3 = st.columns(3)
                                    render_counts(
                                        "Objawy somatyczne",
                                        prepare_counts(
                                            df_patient_filtered["Objawy somatyczne"]
                                        ),
                                        c1,
                                    )
                                    render_counts(
                                        "Wykonane aktywności",
                                        prepare_counts(
                                            df_patient_filtered["Wykonane aktywności"]
                                        ),
                                        c2,
                                    )
                                    render_counts(
                                        "Zachowania impulsywne",
                                        prepare_counts(
                                            df_patient_filtered["Zachowania impulsywne"]
                                        ),
                                        c3,
                                    )
                    else:
                        st.info("Brak danych dla wskazanego pacjenta.")

            with tab_day:
                selected_user_day = st.selectbox(
                    "Wybierz pacjenta",
                    patients,
                    key="admin_day_patient",
                )

                if selected_user_day:
                    file_path = os.path.join("data", f"{selected_user_day}.csv")
                    if os.path.exists(file_path):
                        df_patient_day = pd.read_csv(file_path)
                        if df_patient_day.empty:
                            st.info("Brak zapisów dla wybranego pacjenta.")
                        else:
                            df_patient_day["Data i czas"] = ensure_datetime(
                                df_patient_day["Data i czas"]
                            )
                            df_patient_day = df_patient_day.dropna(subset=["Data i czas"])

                            if df_patient_day.empty:
                                st.info("Brak prawidłowych dat do wyświetlenia.")
                            else:
                                available_dates = sorted(
                                    df_patient_day["Data i czas"].dt.date.unique()
                                )
                                selected_day = st.date_input(
                                    "Wybierz dzień",
                                    value=available_dates[-1],
                                    min_value=available_dates[0],
                                    max_value=available_dates[-1],
                                    key=f"admin_daily_{selected_user_day}",
                                )

                                daily_df = df_patient_day[
                                    df_patient_day["Data i czas"].dt.date
                                    == selected_day
                                ]
                                if daily_df.empty:
                                    st.warning(
                                        "Brak wpisów pacjenta dla wybranego dnia."
                                    )
                                else:
                                    st.markdown("### Wpisy z wybranego dnia")
                                    st.dataframe(
                                        daily_df.drop(columns=["Uwagi"]),
                                        use_container_width=True,
                                    )

                                    st.markdown("### Uwagi pacjenta")
                                    notes = (
                                        daily_df["Uwagi"].fillna("").str.strip()
                                    )
                                    notes = notes[notes != ""]
                                    if notes.empty:
                                        st.write("Brak uwag dla wybranego dnia.")
                                    else:
                                        for note in notes:
                                            st.markdown(f"- {note}")

                                    st.markdown("### Podsumowanie dnia")
                                    day_cols = [
                                        "Nastrój (0-10)",
                                        "Poziom lęku/napięcia (0-10)",
                                        "Energia/motywacja (0-10)",
                                        "Apetyt (0-10)",
                                    ]
                                    metrics_cols = st.columns(len(day_cols))
                                    for idx, column in enumerate(day_cols):
                                        numeric = pd.to_numeric(
                                            daily_df[column], errors="coerce"
                                        )
                                        value = numeric.dropna().mean()
                                        metrics_cols[idx].metric(
                                            column,
                                            f"{value:.1f}/10"
                                            if not pd.isna(value)
                                            else "–",
                                        )

                                    st.markdown("### Aktywności i objawy (dzień)")
                                    d1, d2, d3 = st.columns(3)
                                    render_counts(
                                        "Objawy somatyczne",
                                        prepare_counts(
                                            daily_df["Objawy somatyczne"]
                                        ),
                                        d1,
                                    )
                                    render_counts(
                                        "Wykonane aktywności",
                                        prepare_counts(
                                            daily_df["Wykonane aktywności"]
                                        ),
                                        d2,
                                    )
                                    render_counts(
                                        "Zachowania impulsywne",
                                        prepare_counts(
                                            daily_df["Zachowania impulsywne"]
                                        ),
                                        d3,
                                    )
                    else:
                        st.info("Brak danych dla wskazanego pacjenta.")
    else:
        user_tabs = [
            "✍️ Formularz",
            "📑 Historia",
            "📈 Wykresy",
            "🌙 Sen",
            "📅 Dane za dzień",
        ]
        tab_form, tab_history, tab_charts, tab_sleep, tab_day = st.tabs(user_tabs)

        with tab_form:
            with st.form("nowy_wpis"):
                nastrój = st.slider("Nastrój", 0, 10, 5)
                lęk = st.slider("Poziom lęku/napięcia", 0, 10, 5)

                st.markdown("**Objawy somatyczne**")
                wybrane_objawy = [
                    n for k, n in OBJAWY.items() if st.checkbox(n, key=f"objaw_{k}")
                ]

                zasniecie = st.time_input("Godzina zaśnięcia", datetime.time(23, 0))
                pobudka = st.time_input("Godzina wybudzenia", datetime.time(7, 0))
                wybudzenia = st.number_input("Liczba wybudzeń w nocy", 0, 20, 0)
                jakosc_snu = st.slider("Subiektywna jakość snu", 0, 10, 5)
                energia = st.slider("Energia/motywacja do działania", 0, 10, 5)
                apetyt = st.slider("Apetyt", 0, 10, 5)

                st.markdown("**Wykonane aktywności**")
                wybrane_aktywnosci = [
                    n
                    for k, n in AKTYWNOSCI.items()
                    if st.checkbox(n, key=f"aktywnosc_{k}")
                ]

                st.markdown("**Zachowania impulsywne**")
                wybrane_impulsy = [
                    n for k, n in IMPULSY.items() if st.checkbox(n, key=f"impuls_{k}")
                ]

                uwagi = st.text_area("Uwagi dodatkowe")

                submitted = st.form_submit_button("💾 Zapisz wpis")

            if submitted:
                now = datetime.datetime.now()
                new_row = {
                    "Data i czas": now.strftime("%Y-%m-%d %H:%M"),
                    "Nastrój (0-10)": nastrój,
                    "Poziom lęku/napięcia (0-10)": lęk,
                    "Objawy somatyczne": ", ".join(wybrane_objawy),
                    "Godzina zaśnięcia": zasniecie.strftime("%H:%M"),
                    "Godzina wybudzenia": pobudka.strftime("%H:%M"),
                    "Liczba wybudzeń w nocy": wybudzenia,
                    "Subiektywna jakość snu (0-10)": jakosc_snu,
                    "Energia/motywacja (0-10)": energia,
                    "Apetyt (0-10)": apetyt,
                    "Wykonane aktywności": ", ".join(wybrane_aktywnosci),
                    "Zachowania impulsywne": ", ".join(wybrane_impulsy),
                    "Uwagi": uwagi,
                }

                existing_today = pd.DataFrame()
                if not df.empty and "Data i czas" in df:
                    df_with_dates = df.copy()
                    df_with_dates["Data i czas"] = ensure_datetime(
                        df_with_dates["Data i czas"]
                    )
                    mask_today = (
                        df_with_dates["Data i czas"].dt.date == now.date()
                    )
                    existing_today = df_with_dates.loc[mask_today]

                if not existing_today.empty:
                    st.session_state["pending_entry"] = new_row
                    st.session_state["pending_entry_date"] = now.date().isoformat()
                    st.session_state["pending_entry_user"] = username
                else:
                    clear_pending_entry()
                    df = pd.concat(
                        [df, pd.DataFrame([new_row])], ignore_index=True
                    )
                    df.to_csv(user_file, index=False)
                    st.success("✅ Wpis dodany!")

        pending_entry = st.session_state.get("pending_entry")
        pending_user = st.session_state.get("pending_entry_user")
        pending_date_str = st.session_state.get("pending_entry_date")

        if pending_entry and pending_user == username and pending_date_str:
            try:
                pending_date = datetime.date.fromisoformat(pending_date_str)
            except ValueError:
                clear_pending_entry()
            else:
                st.warning(
                    "Wpis na dzisiejszą datę już istnieje. "
                    "Czy chcesz usunąć poprzedni i zapisać nowy?"
                )
                confirm_col, cancel_col = st.columns(2)
                if confirm_col.button(
                    "Usuń poprzedni i zapisz nowy wpis",
                    key=f"confirm_replace_{username}",
                ):
                    df_replacement = df.copy()
                    if not df_replacement.empty and "Data i czas" in df_replacement:
                        df_replacement["Data i czas"] = ensure_datetime(
                            df_replacement["Data i czas"]
                        )
                        df_replacement = df_replacement.loc[
                            df_replacement["Data i czas"].dt.date != pending_date
                        ]
                    df_replacement = pd.concat(
                        [
                            df_replacement,
                            pd.DataFrame([pending_entry]),
                        ],
                        ignore_index=True,
                    )
                    df_replacement.to_csv(user_file, index=False)
                    clear_pending_entry()
                    st.success("Wpis został zaktualizowany.")
                    st.rerun()
                if cancel_col.button(
                    "Anuluj zapis",
                    key=f"cancel_pending_{username}",
                ):
                    clear_pending_entry()
                    st.info("Nowy wpis nie został zapisany.")
                    st.rerun()
        elif pending_entry:
            clear_pending_entry()

        with tab_history:
            st.subheader("Historia wpisów")
            if df.empty:
                st.info("Brak zapisanych wpisów.")
            else:
                st.dataframe(df, use_container_width=True)

                st.markdown("### 🗑 Usuń wpis")
                user_timestamps = (
                    ensure_datetime(df["Data i czas"])
                    if "Data i czas" in df
                    else pd.Series(
                        pd.NaT, index=df.index, dtype="datetime64[ns]"
                    )
                )

                def format_user_entry(idx: int) -> str:
                    ts = user_timestamps.loc[idx]
                    ts_display = (
                        ts.strftime("%Y-%m-%d %H:%M")
                        if not pd.isna(ts)
                        else "Brak daty"
                    )
                    mood_display = (
                        df.at[idx, "Nastrój (0-10)"]
                        if "Nastrój (0-10)" in df
                        else "–"
                    )
                    return f"{ts_display} · Nastrój: {mood_display}"

                entry_to_delete_user = st.selectbox(
                    "Wybierz wpis do usunięcia",
                    options=list(df.index),
                    format_func=format_user_entry,
                    key=f"user_delete_option_{username}",
                )

                if st.button(
                    "🗑 Usuń wybrany wpis",
                    key=f"user_delete_button_{username}",
                ):
                    updated_df = df.drop(index=entry_to_delete_user).reset_index(
                        drop=True
                    )
                    updated_df.to_csv(user_file, index=False)
                    st.success("Wpis został usunięty.")
                    st.rerun()

                st.markdown("### 📤 Eksport danych")
                csv_data = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Pobierz CSV",
                    data=csv_data,
                    file_name=f"{username}_dziennik.csv",
                    mime="text/csv",
                )

        with tab_charts:
            if df.empty:
                st.info("Brak danych do wizualizacji.")
            else:
                chart_df = df.copy()
                chart_df["Data i czas"] = ensure_datetime(chart_df["Data i czas"])
                chart_df = chart_df.dropna(subset=["Data i czas"])

                if chart_df.empty:
                    st.info("Brak prawidłowych dat w zapisach.")
                else:
                    date_range = select_date_range(
                        chart_df, f"{username}_main_range"
                    )
                    if date_range:
                        start_date, end_date = date_range
                        chart_filtered = filter_by_range(
                            chart_df, start_date, end_date
                        )
                    else:
                        chart_filtered = chart_df

                    if chart_filtered.empty:
                        st.info("Brak danych w wybranym okresie.")
                    else:
                        st.subheader("📈 Trendy w czasie")
                        fig, ax = plt.subplots()
                        for col, label in [
                            ("Nastrój (0-10)", "Nastrój"),
                            ("Poziom lęku/napięcia (0-10)", "Lęk"),
                            ("Energia/motywacja (0-10)", "Energia"),
                            ("Apetyt (0-10)", "Apetyt"),
                        ]:
                            if col in chart_filtered:
                                ax.plot(
                                    chart_filtered["Data i czas"],
                                    chart_filtered[col],
                                    marker="o",
                                    label=label,
                                )

                        low = chart_filtered[
                            chart_filtered["Nastrój (0-10)"] < 3
                        ]
                        if not low.empty:
                            ax.scatter(
                                low["Data i czas"],
                                low["Nastrój (0-10)"],
                                color="red",
                                s=60,
                                zorder=5,
                                label="Bardzo niski nastrój",
                            )

                        ax.set_ylabel("Poziom (0–10)")
                        ax.set_xlabel("Data")
                        ax.legend()
                        plt.xticks(rotation=45)
                        st.pyplot(fig)

                        st.subheader(
                            "📉 Objawy somatyczne i impulsywne zachowania"
                        )
                        render_daily_totals_chart(
                            compute_daily_totals(
                                chart_filtered, "Objawy somatyczne"
                            ),
                            "Objawy somatyczne na dzień",
                            "Liczba objawów",
                        )
                        render_daily_totals_chart(
                            compute_daily_totals(
                                chart_filtered, "Zachowania impulsywne"
                            ),
                            "Zachowania impulsywne na dzień",
                            "Liczba zachowań",
                        )

                        st.subheader("📊 Przegląd aktywności i objawów")
                        col1, col2, col3 = st.columns(3)
                        render_counts(
                            "Objawy somatyczne",
                            prepare_counts(
                                chart_filtered["Objawy somatyczne"]
                            ),
                            col1,
                        )
                        render_counts(
                            "Wykonane aktywności",
                            prepare_counts(
                                chart_filtered["Wykonane aktywności"]
                            ),
                            col2,
                        )
                        render_counts(
                            "Zachowania impulsywne",
                            prepare_counts(
                                chart_filtered["Zachowania impulsywne"]
                            ),
                            col3,
                        )

        with tab_sleep:
            st.subheader("🌙 Dane o śnie")
            if df.empty:
                st.info("Brak zapisów dotyczących snu.")
            else:
                sleep_df = prepare_sleep_dataframe(df)
                if sleep_df.empty:
                    st.info("Brak prawidłowych danych o śnie.")
                else:
                    date_range = select_date_range(
                        sleep_df, f"{username}_sleep_range"
                    )
                    if date_range:
                        start_date, end_date = date_range
                        sleep_filtered = filter_by_range(
                            sleep_df, start_date, end_date
                        )
                    else:
                        sleep_filtered = sleep_df

                    if sleep_filtered.empty:
                        st.info("Brak danych o śnie w wybranym okresie.")
                    else:
                        fig, ax = plt.subplots()
                        if "Godzina zaśnięcia (h)" in sleep_filtered:
                            ax.plot(
                                sleep_filtered["Data i czas"],
                                sleep_filtered["Godzina zaśnięcia (h)"],
                                marker="o",
                                label="Zaśnięcie (godz.)",
                            )
                        if "Godzina wybudzenia (h)" in sleep_filtered:
                            ax.plot(
                                sleep_filtered["Data i czas"],
                                sleep_filtered["Godzina wybudzenia (h)"],
                                marker="o",
                                label="Pobudka (godz.)",
                            )
                        if "Liczba wybudzeń w nocy" in sleep_filtered:
                            ax.plot(
                                sleep_filtered["Data i czas"],
                                sleep_filtered["Liczba wybudzeń w nocy"],
                                marker="x",
                                label="Wybudzenia w nocy",
                            )
                        if "Subiektywna jakość snu (0-10)" in sleep_filtered:
                            ax.plot(
                                sleep_filtered["Data i czas"],
                                sleep_filtered["Subiektywna jakość snu (0-10)"],
                                marker="s",
                                label="Jakość snu (0-10)",
                            )
                        if "Długość snu (h)" in sleep_filtered:
                            ax.plot(
                                sleep_filtered["Data i czas"],
                                sleep_filtered["Długość snu (h)"],
                                marker="d",
                                label="Długość snu (h)",
                            )

                        ax.set_ylabel("Parametry snu")
                        ax.set_xlabel("Data")
                        ax.legend()
                        plt.xticks(rotation=45)
                        st.pyplot(fig)

                        numeric_sleep = get_numeric_series(
                            sleep_filtered, "Długość snu (h)"
                        )
                        numeric_wakeups = get_numeric_series(
                            sleep_filtered, "Liczba wybudzeń w nocy"
                        )
                        numeric_quality = get_numeric_series(
                            sleep_filtered,
                            "Subiektywna jakość snu (0-10)",
                        )

                        avg_sleep = numeric_sleep.dropna().mean()
                        avg_wakeups = numeric_wakeups.dropna().mean()
                        avg_quality = numeric_quality.dropna().mean()
                        total_wakeups = numeric_wakeups.dropna().sum()

                        st.markdown("### 📊 Statystyki snu (okres)")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric(
                            "Średnia długość snu",
                            f"{avg_sleep:.1f} h"
                            if not pd.isna(avg_sleep)
                            else "–",
                        )
                        c2.metric(
                            "Średnia liczba wybudzeń",
                            f"{avg_wakeups:.1f}"
                            if not pd.isna(avg_wakeups)
                            else "–",
                        )
                        c3.metric(
                            "Średnia jakość snu",
                            f"{avg_quality:.1f}/10"
                            if not pd.isna(avg_quality)
                            else "–",
                        )
                        c4.metric(
                            "Łączna liczba wybudzeń",
                            f"{int(total_wakeups)}",
                        )

                        st.markdown("### 📋 Dane snu")
                        sleep_columns = [
                            "Data i czas",
                            "Godzina zaśnięcia",
                            "Godzina wybudzenia",
                            "Liczba wybudzeń w nocy",
                            "Subiektywna jakość snu (0-10)",
                            "Długość snu (h)",
                        ]
                        available_sleep_columns = [
                            column
                            for column in sleep_columns
                            if column in sleep_filtered
                        ]
                        if available_sleep_columns:
                            sleep_table = sleep_filtered[available_sleep_columns]
                            st.dataframe(
                                sleep_table, use_container_width=True
                            )
                        else:
                            st.info(
                                "Brak szczegółowych danych o śnie w wybranym okresie."
                            )

        with tab_day:
            st.subheader("📅 Dane za wybrany dzień")
            if df.empty:
                st.info("Brak zapisanych wpisów.")
            else:
                df_dates = df.copy()
                df_dates["Data i czas"] = ensure_datetime(df_dates["Data i czas"])
                df_dates = df_dates.dropna(subset=["Data i czas"])

                if df_dates.empty:
                    st.info("Brak prawidłowych dat w zapisach.")
                else:
                    available_dates = sorted(
                        df_dates["Data i czas"].dt.date.unique()
                    )
                    selected_day = st.date_input(
                        "Wybierz dzień",
                        value=available_dates[-1],
                        min_value=available_dates[0],
                        max_value=available_dates[-1],
                        key=f"{username}_daily_view",
                    )

                    daily_df = df_dates[
                        df_dates["Data i czas"].dt.date == selected_day
                    ]
                    if daily_df.empty:
                        st.warning("Brak wpisów dla wybranego dnia.")
                    else:
                        st.markdown("### Zapisane dane")
                        st.dataframe(
                            daily_df.drop(columns=["Uwagi"]),
                            use_container_width=True,
                        )

                        st.markdown("### Uwagi pacjenta")
                        notes = daily_df["Uwagi"].fillna("").str.strip()
                        notes = notes[notes != ""]
                        if notes.empty:
                            st.write("Brak uwag dla wybranego dnia.")
                        else:
                            for note in notes:
                                st.markdown(f"- {note}")

                        st.markdown("### Podsumowanie dnia")
                        summary_cols = [
                            "Nastrój (0-10)",
                            "Poziom lęku/napięcia (0-10)",
                            "Energia/motywacja (0-10)",
                            "Apetyt (0-10)",
                        ]
                        summary_metrics = st.columns(len(summary_cols))
                        for idx, column in enumerate(summary_cols):
                            numeric = pd.to_numeric(
                                daily_df[column], errors="coerce"
                            )
                            value = numeric.dropna().mean()
                            summary_metrics[idx].metric(
                                column,
                                f"{value:.1f}/10"
                                if not pd.isna(value)
                                else "–",
                            )

                        st.markdown("### Aktywności i objawy")
                        d1, d2, d3 = st.columns(3)
                        render_counts(
                            "Objawy somatyczne",
                            prepare_counts(daily_df["Objawy somatyczne"]),
                            d1,
                        )
                        render_counts(
                            "Wykonane aktywności",
                            prepare_counts(daily_df["Wykonane aktywności"]),
                            d2,
                        )
                        render_counts(
                            "Zachowania impulsywne",
                            prepare_counts(daily_df["Zachowania impulsywne"]),
                            d3,
                        )

st.markdown("---")
st.markdown(
    "**Lek. Aleksy Kasperowicz** · specjalista psychiatra · "
    "[www.drkasperowicz.pl](https://www.drkasperowicz.pl)"
)
