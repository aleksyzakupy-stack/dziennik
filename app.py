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
        timestamps = pd.to_datetime(df_time["Data i czas"], errors="coerce")
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
        filtered["Data i czas"] = pd.to_datetime(filtered["Data i czas"], errors="coerce")
        mask = filtered["Data i czas"].dt.date.between(start_date, end_date)
        return filtered.loc[mask]

    def compute_daily_totals(df_time: pd.DataFrame, column: str) -> pd.Series:
        if column not in df_time or df_time.empty:
            return pd.Series(dtype="int64")
        working = df_time[["Data i czas", column]].copy()
        working["Data i czas"] = pd.to_datetime(working["Data i czas"], errors="coerce")
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

    # --- Layout вкладок ---
    tabs = ["✍️ Formularz", "📑 Historia", "📈 Wykresy", "📅 Dane za dzień"]
    if role == "admin":
        tabs.append("👨‍⚕️ Panel admina")

    tab1, tab2, tab3, tab4, *extra = st.tabs(tabs)

    # --- TAB 1: Formularz ---
    with tab1:
        with st.form("nowy_wpis"):
            nastrój = st.slider("Nastrój", 0, 10, 5)
            lęk = st.slider("Poziom lęku/napięcia", 0, 10, 5)

            st.markdown("**Objawy somatyczne**")
            wybrane_objawy = [n for k, n in OBJAWY.items() if st.checkbox(n, key=f"objaw_{k}")]

            zasniecie = st.time_input("Godzina zaśnięcia", datetime.time(23,0))
            pobudka = st.time_input("Godzina wybudzenia", datetime.time(7,0))
            wybudzenia = st.number_input("Liczba wybudzeń w nocy", 0, 20, 0)
            jakosc_snu = st.slider("Subiektywna jakość snu", 0, 10, 5)
            energia = st.slider("Energia/motywacja do działania", 0, 10, 5)
            apetyt = st.slider("Apetyt", 0, 10, 5)

            st.markdown("**Wykonane aktywności**")
            wybrane_aktywnosci = [n for k, n in AKTYWNOSCI.items() if st.checkbox(n, key=f"aktywnosc_{k}")]

            st.markdown("**Zachowania impulsywne**")
            wybrane_impulsy = [n for k, n in IMPULSY.items() if st.checkbox(n, key=f"impuls_{k}")]

            uwagi = st.text_area("Uwagi dodatkowe")

            submitted = st.form_submit_button("💾 Zapisz wpis")

        if submitted:
            new_row = {
                "Data i czas": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
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
                "Uwagi": uwagi
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(user_file, index=False)
            st.success("✅ Wpis dodany!")

    # --- TAB 2: Historia ---
    with tab2:
        st.subheader("Historia wpisów")
        st.dataframe(df, use_container_width=True)

        st.markdown("### 📤 Eksport danych")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Pobierz CSV", data=csv, file_name=f"{username}_dziennik.csv", mime="text/csv")

    # --- TAB 3: Wykresy ---
    with tab3:
        if not df.empty:
            df["Data i czas"] = pd.to_datetime(df["Data i czas"], errors="coerce")
            date_range = select_date_range(df, f"{username}_main")
            if date_range:
                start_date, end_date = date_range
                df_filtered = filter_by_range(df, start_date, end_date)
            else:
                df_filtered = df

            if df_filtered.empty:
                st.info("Brak danych w wybranym okresie.")
            else:
                st.subheader("📈 Trendy w czasie")

                fig, ax = plt.subplots()
                for col, label in [
                    ("Nastrój (0-10)", "Nastrój"),
                    ("Poziom lęku/napięcia (0-10)", "Lęk"),
                    ("Energia/motywacja (0-10)", "Energia"),
                    ("Apetyt (0-10)", "Apetyt")
                ]:
                    if col in df_filtered:
                        ax.plot(df_filtered["Data i czas"], df_filtered[col], marker="o", label=label)

                low = df_filtered[df_filtered["Nastrój (0-10)"] < 3]
                if not low.empty:
                    ax.scatter(low["Data i czas"], low["Nastrój (0-10)"], color="red", s=60, zorder=5, label="Bardzo niski nastrój")

                ax.set_ylabel("Poziom (0–10)")
                ax.set_xlabel("Data")
                ax.legend()
                plt.xticks(rotation=45)

                st.pyplot(fig)

                # --- Wykresy snu ---
                st.subheader("🌙 Sen")

                df_sleep = df_filtered.copy()
                df_sleep["Zaśnięcie_dt"] = pd.to_datetime(df_sleep["Godzina zaśnięcia"], format="%H:%M", errors="coerce")
                df_sleep["Pobudka_dt"] = pd.to_datetime(df_sleep["Godzina wybudzenia"], format="%H:%M", errors="coerce")

                df_sleep["Godzina zaśnięcia (h)"] = df_sleep["Zaśnięcie_dt"].dt.hour + df_sleep["Zaśnięcie_dt"].dt.minute / 60
                df_sleep["Godzina wybudzenia (h)"] = df_sleep["Pobudka_dt"].dt.hour + df_sleep["Pobudka_dt"].dt.minute / 60
                df_sleep["Długość snu (h)"] = (df_sleep["Pobudka_dt"] - df_sleep["Zaśnięcie_dt"]).dt.total_seconds() / 3600

                fig, ax = plt.subplots()
                ax.plot(df_sleep["Data i czas"], df_sleep["Godzina zaśnięcia (h)"], marker="o", label="Zaśnięcie (godz.)")
                ax.plot(df_sleep["Data i czas"], df_sleep["Godzina wybudzenia (h)"], marker="o", label="Pobudka (godz.)")

                if "Liczba wybudzeń w nocy" in df_sleep:
                    ax.plot(df_sleep["Data i czas"], df_sleep["Liczba wybudzeń w nocy"], marker="x", label="Wybudzenia w nocy")

                if "Subiektywna jakość snu (0-10)" in df_sleep:
                    ax.plot(df_sleep["Data i czas"], df_sleep["Subiektywna jakość snu (0-10)"], marker="s", label="Jakość snu (0-10)")

                if "Długość snu (h)" in df_sleep:
                    ax.plot(df_sleep["Data i czas"], df_sleep["Długość snu (h)"], marker="d", label="Długość snu (h)")

                ax.set_ylabel("Wartości snu")
                ax.set_xlabel("Data")
                ax.legend()
                plt.xticks(rotation=45)

                st.pyplot(fig)

                st.subheader("📉 Objawy somatyczne i impulsywne zachowania")
                somatic_series = compute_daily_totals(df_filtered, "Objawy somatyczne")
                impulsive_series = compute_daily_totals(df_filtered, "Zachowania impulsywne")
                render_daily_totals_chart(somatic_series, "Objawy somatyczne na dzień", "Liczba objawów")
                render_daily_totals_chart(impulsive_series, "Zachowania impulsywne na dzień", "Liczba zachowań")

                # --- Statystyki aktywności i objawów ---
                st.subheader("📊 Przegląd aktywności i objawów")
                col1, col2, col3 = st.columns(3)
                render_counts("Objawy somatyczne", prepare_counts(df_filtered["Objawy somatyczne"]), col1)
                render_counts("Wykonane aktywności", prepare_counts(df_filtered["Wykonane aktywności"]), col2)
                render_counts("Zachowania impulsywne", prepare_counts(df_filtered["Zachowania impulsywne"]), col3)

        else:
            st.info("Brak danych do wizualizacji.")

    # --- TAB 4: Dane za dzień ---
    with tab4:
        st.subheader("📅 Dane za wybrany dzień")
        if df.empty:
            st.info("Brak zapisanych wpisów.")
        else:
            df_dates = df.copy()
            df_dates["Data i czas"] = pd.to_datetime(df_dates["Data i czas"], errors="coerce")
            df_dates = df_dates.dropna(subset=["Data i czas"])
            if df_dates.empty:
                st.info("Brak prawidłowych dat w zapisach.")
            else:
                available_dates = sorted(df_dates["Data i czas"].dt.date.unique())
                default_date = available_dates[-1]
                selected_day = st.date_input(
                    "Wybierz dzień",
                    value=default_date,
                    min_value=available_dates[0],
                    max_value=available_dates[-1],
                    key=f"{username}_daily_view",
                )
                daily_df = df_dates[df_dates["Data i czas"].dt.date == selected_day]
                if daily_df.empty:
                    st.warning("Brak wpisów dla wybranego dnia.")
                else:
                    st.markdown("### Zapisane dane")
                    st.dataframe(daily_df.drop(columns=["Uwagi"]), use_container_width=True)

                    st.markdown("### Uwagi pacjenta")
                    notes = daily_df["Uwagi"].fillna("").str.strip()
                    notes = notes[notes != ""]
                    if notes.empty:
                        st.write("Brak uwag dla wybranego dnia.")
                    else:
                        for note in notes:
                            st.markdown(f"- {note}")

    # --- TAB 5: Panel admina ---
    if role == "admin" and extra:
        with extra[0]:
            st.subheader("👨‍⚕️ Panel admina – dane pacjentów")

            files = [f for f in os.listdir("data") if f.endswith(".csv")]
            patients = [f.replace(".csv", "") for f in files]

            selected_user = st.selectbox("Wybierz pacjenta", patients)

            if selected_user:
                file_path = os.path.join("data", f"{selected_user}.csv")
                if os.path.exists(file_path):
                    df_patient = pd.read_csv(file_path)

                    if not df_patient.empty:
                        st.write(f"📄 Dane pacjenta: **{selected_user}**")
                        st.dataframe(df_patient, use_container_width=True)

                        df_patient["Data i czas"] = pd.to_datetime(df_patient["Data i czas"], errors="coerce")

                        # --- Skrót: objawy + impulsy ---
                        st.markdown("### 📊 Objawy somatyczne i zachowania impulsywne (wszystkie dane)")
                        table_summary = df_patient[["Data i czas", "Objawy somatyczne", "Zachowania impulsywne"]]
                        st.dataframe(table_summary, use_container_width=True)

                        # --- Eksport ---
                        st.markdown("### 📤 Eksport danych pacjenta")
                        csv = df_patient.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "⬇️ Pobierz CSV",
                            data=csv,
                            file_name=f"{selected_user}_dziennik.csv",
                            mime="text/csv"
                        )

                        try:
                            import io, openpyxl
                            buffer = io.BytesIO()
                            df_patient.to_excel(buffer, index=False, engine="openpyxl")
                            st.download_button(
                                "⬇️ Pobierz XLSX",
                                data=buffer.getvalue(),
                                file_name=f"{selected_user}_dziennik.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        except ImportError:
                            st.info("📎 Eksport do XLSX wymaga pakietu `openpyxl`.")

                        st.subheader("📈 Trendy pacjenta")
                        date_range = select_date_range(df_patient, f"{selected_user}_admin")
                        if date_range:
                            start_date, end_date = date_range
                            df_patient_filtered = filter_by_range(df_patient, start_date, end_date)
                        else:
                            df_patient_filtered = df_patient

                        if df_patient_filtered.empty:
                            st.info("Brak danych pacjenta w wybranym okresie.")
                        else:
                            fig, ax = plt.subplots()
                            for col, label in [
                                ("Nastrój (0-10)", "Nastrój"),
                                ("Poziom lęku/napięcia (0-10)", "Lęk"),
                                ("Energia/motywacja (0-10)", "Energia"),
                                ("Apetyt (0-10)", "Apetyt")
                            ]:
                                if col in df_patient_filtered:
                                    ax.plot(df_patient_filtered["Data i czas"], df_patient_filtered[col], marker="o", label=label)

                            low = df_patient_filtered[df_patient_filtered["Nastrój (0-10)"] < 3]
                            if not low.empty:
                                ax.scatter(
                                    low["Data i czas"],
                                    low["Nastrój (0-10)"],
                                    color="red",
                                    s=60,
                                    zorder=5,
                                    label="Bardzo niski nastrój"
                                )

                            ax.set_ylabel("Poziom (0–10)")
                            ax.set_xlabel("Data")
                            ax.legend()
                            plt.xticks(rotation=45)

                            st.pyplot(fig)

                            # --- Wykresy snu ---
                            st.subheader("🌙 Sen pacjenta")

                            df_patient_sleep = df_patient_filtered.copy()
                            df_patient_sleep["Zaśnięcie_dt"] = pd.to_datetime(
                                df_patient_sleep["Godzina zaśnięcia"], format="%H:%M", errors="coerce"
                            )
                            df_patient_sleep["Pobudka_dt"] = pd.to_datetime(
                                df_patient_sleep["Godzina wybudzenia"], format="%H:%M", errors="coerce"
                            )

                            df_patient_sleep["Godzina zaśnięcia (h)"] = (
                                df_patient_sleep["Zaśnięcie_dt"].dt.hour + df_patient_sleep["Zaśnięcie_dt"].dt.minute / 60
                            )
                            df_patient_sleep["Godzina wybudzenia (h)"] = (
                                df_patient_sleep["Pobudka_dt"].dt.hour + df_patient_sleep["Pobudka_dt"].dt.minute / 60
                            )
                            df_patient_sleep["Długość snu (h)"] = (
                                (df_patient_sleep["Pobudka_dt"] - df_patient_sleep["Zaśnięcie_dt"]).dt.total_seconds() / 3600
                            )

                            fig, ax = plt.subplots()
                            if "Godzina zaśnięcia (h)" in df_patient_sleep:
                                ax.plot(
                                    df_patient_sleep["Data i czas"],
                                    df_patient_sleep["Godzina zaśnięcia (h)"],
                                    marker="o",
                                    label="Zaśnięcie (godz.)"
                                )
                            if "Godzina wybudzenia (h)" in df_patient_sleep:
                                ax.plot(
                                    df_patient_sleep["Data i czas"],
                                    df_patient_sleep["Godzina wybudzenia (h)"],
                                    marker="o",
                                    label="Pobudka (godz.)"
                                )
                            if "Liczba wybudzeń w nocy" in df_patient_sleep:
                                ax.plot(
                                    df_patient_sleep["Data i czas"],
                                    df_patient_sleep["Liczba wybudzeń w nocy"],
                                    marker="x",
                                    label="Wybudzenia w nocy"
                                )
                            if "Subiektywna jakość snu (0-10)" in df_patient_sleep:
                                ax.plot(
                                    df_patient_sleep["Data i czas"],
                                    df_patient_sleep["Subiektywna jakość snu (0-10)"],
                                    marker="s",
                                    label="Jakość snu (0-10)"
                                )
                            if "Długość snu (h)" in df_patient_sleep:
                                ax.plot(
                                    df_patient_sleep["Data i czas"],
                                    df_patient_sleep["Długość snu (h)"],
                                    marker="d",
                                    label="Długość snu (h)"
                                )

                            ax.set_ylabel("Parametry snu")
                            ax.set_xlabel("Data")
                            ax.legend()
                            plt.xticks(rotation=45)

                            st.pyplot(fig)

                            st.subheader("📉 Objawy somatyczne i impulsywne zachowania")
                            render_daily_totals_chart(
                                compute_daily_totals(df_patient_filtered, "Objawy somatyczne"),
                                "Objawy somatyczne na dzień",
                                "Liczba objawów",
                            )
                            render_daily_totals_chart(
                                compute_daily_totals(df_patient_filtered, "Zachowania impulsywne"),
                                "Zachowania impulsywne na dzień",
                                "Liczba zachowań",
                            )

                            # --- statystyki snu ---
                            st.markdown("### 📊 Statystyki snu")
                            avg_sleep = df_patient_sleep["Długość snu (h)"].mean(skipna=True)
                            avg_wakeups = df_patient_sleep["Liczba wybudzeń w nocy"].mean(skipna=True)
                            avg_quality = df_patient_sleep["Subiektywna jakość snu (0-10)"].mean(skipna=True)

                            col1, col2, col3 = st.columns(3)
                            col1.metric(
                                "Średnia długość snu",
                                f"{avg_sleep:.1f} h" if not pd.isna(avg_sleep) else "–"
                            )
                            col2.metric(
                                "Średnia liczba wybudzeń",
                                f"{avg_wakeups:.1f}" if not pd.isna(avg_wakeups) else "–"
                            )
                            col3.metric(
                                "Średnia jakość snu",
                                f"{avg_quality:.1f}/10" if not pd.isna(avg_quality) else "–"
                            )

                            st.markdown("### 📋 Aktywności i objawy")
                            c1, c2, c3 = st.columns(3)
                            render_counts(
                                "Objawy somatyczne",
                                prepare_counts(df_patient_filtered["Objawy somatyczne"]),
                                c1,
                            )
                            render_counts(
                                "Wykonane aktywności",
                                prepare_counts(df_patient_filtered["Wykonane aktywności"]),
                                c2,
                            )
                            render_counts(
                                "Zachowania impulsywne",
                                prepare_counts(df_patient_filtered["Zachowania impulsywne"]),
                                c3,
                            )



                    else:
                        st.info("Brak zapisanych wpisów dla tego pacjenta.")
                else:
                    st.info("Brak danych dla tego pacjenta.")

st.markdown("---")
st.markdown(
    "**Lek. Aleksy Kasperowicz** · specjalista psychiatra · "
    "[www.drkasperowicz.pl](https://www.drkasperowicz.pl)"
)
