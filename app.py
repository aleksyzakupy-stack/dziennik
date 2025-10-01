import streamlit as st
import pandas as pd
import datetime
import os
import yaml
from yaml.loader import SafeLoader
import matplotlib.pyplot as plt
import streamlit_authenticator as stauth

# --- Конфигурация страницы ---
st.set_page_config(page_title="📓 Dziennik nastroju", layout="wide")

# --- Plik użytkowników ---
USERS_FILE = "users.yaml"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        yaml.dump({"credentials": {"usernames": {}}}, f)

with open(USERS_FILE) as f:
    config = yaml.load(f, Loader=SafeLoader)

# --- Autoryzacja ---
authenticator = stauth.Authenticate(
    config['credentials'],
    "dziennik_cookie",
    "abcdef",
    cookie_expiry_days=1
)

# --- Rejestracja (tylko jeśli nie zalogowany) ---
if st.session_state.get("authentication_status") is None:
    st.sidebar.subheader("🆕 Rejestracja")
    with st.sidebar.form("register_form"):
        new_name = st.text_input("Imię i nazwisko")
        new_username = st.text_input("Login")
        new_password = st.text_input("Hasło", type="password")
        reg_submitted = st.form_submit_button("Zarejestruj")

        if reg_submitted:
            if new_username in config["credentials"]["usernames"]:
                st.sidebar.error("❌ Taki login już istnieje")
            elif not new_name or not new_username or not new_password:
                st.sidebar.error("⚠️ Wszystkie pola są wymagane")
            else:
                hashed = stauth.Hasher().generate([new_password])[0]
                config["credentials"]["usernames"][new_username] = {
                    "name": new_name,
                    "password": hashed,
                    "role": "user"
                }
                with open(USERS_FILE, "w") as f:
                    yaml.dump(config, f)
                st.sidebar.success("✅ Rejestracja udana! Możesz się zalogować.")

# --- Logowanie ---
name, authentication_status, username = authenticator.login("Login", "sidebar")

if authentication_status == False:
    st.error("❌ Nieprawidłowy login lub hasło")
if authentication_status == None:
    st.warning("🔑 Wprowadź login i hasło")

# --- Jeśli zalogowano ---
if authentication_status:

    authenticator.logout("🚪 Wyloguj", "sidebar")
    st.sidebar.success(f"Zalogowano: {name}")

    # --- Rola użytkownika ---
    role = config["credentials"]["usernames"][username].get("role", "user")

    # --- Dane użytkownika ---
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

    # --- Definicje checkboxów ---
    OBJAWY = {
        "ks": "kołatanie serca", "d": "drżenie", "p": "nadmierne pocenie się",
        "bb": "bóle brzucha", "w": "wymioty", "ś": "ścisk w klatce/duszność",
        "zg": "zawroty głowy", "gwg": "gula w gardle", "nm": "napięcie mięśni",
        "m": "mrowienia", "bg": "ból głowy", "bkl": "ból w klatce piersiowej",
        "swu": "suchość w ustach"
    }
    AKTYWNOSCI = {"p": "praca", "n": "nauka", "d": "obowiązki domowe", "wf": "aktywność fizyczna"}
    IMPULSY = {"oż": "kompulsywne objadanie się", "su": "samouszkodzenia", "z": "zakupy kompulsywne", "h": "hazard", "s": "seks ryzykowny"}

    # --- Layout zakładek ---
    tabs = ["✍️ Formularz", "📑 Historia", "📈 Wykresy"]
    if role == "admin":
        tabs.append("👨‍⚕️ Panel admina")

    tab1, tab2, tab3, *extra = st.tabs(tabs)

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
            df["Data i czas"] = pd.to_datetime(df["Data i czas"])
            st.subheader("📈 Trendy w czasie")

            fig, ax = plt.subplots()
            for col, label in [
                ("Nastrój (0-10)", "Nastrój"),
                ("Poziom lęku/napięcia (0-10)", "Lęk"),
                ("Energia/motywacja (0-10)", "Energia"),
                ("Apetyt (0-10)", "Apetyt")
            ]:
                if col in df:
                    ax.plot(df["Data i czas"], df[col], marker="o", label=label)

            low = df[df["Nastrój (0-10)"] < 3]
            if not low.empty:
                ax.scatter(low["Data i czas"], low["Nastrój (0-10)"], color="red", s=60, zorder=5, label="Bardzo niski nastrój")

            ax.set_ylabel("Poziom (0–10)")
            ax.set_xlabel("Data")
            ax.legend()
            plt.xticks(rotation=45)

            st.pyplot(fig)

            # --- Wykresy snu ---
            st.subheader("🌙 Sen")
            df["Zaśnięcie_dt"] = pd.to_datetime(df["Godzina zaśnięcia"], format="%H:%M", errors="coerce")
            df["Pobudka_dt"] = pd.to_datetime(df["Godzina wybudzenia"], format="%H:%M", errors="coerce")
            df["Godzina zaśnięcia (h)"] = df["Zaśnięcie_dt"].dt.hour + df["Zaśnięcie_dt"].dt.minute/60
            df["Godzina wybudzenia (h)"] = df["Pobudka_dt"].dt.hour + df["Pobudka_dt"].dt.minute/60
            df["Długość snu (h)"] = (df["Pobudka_dt"] - df["Zaśnięcie_dt"]).dt.total_seconds() / 3600

            fig2, ax2 = plt.subplots()
            ax2.plot(df["Data i czas"], df["Godzina zaśnięcia (h)"], marker="o", label="Zaśnięcie (godz.)")
            ax2.plot(df["Data i czas"], df["Godzina wybudzenia (h)"], marker="o", label="Pobudka (godz.)")
            ax2.plot(df["Data i czas"], df["Liczba wybudzeń w nocy"], marker="x", label="Wybudzenia w nocy")
            ax2.plot(df["Data i czas"], df["Subiektywna jakość snu (0-10)"], marker="s", label="Jakość snu (0-10)")
            ax2.plot(df["Data i czas"], df["Długość snu (h)"], marker="d", label="Długość snu (h)")

            ax2.set_ylabel("Parametry snu")
            ax2.set_xlabel("Data")
            ax2.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig2)
        else:
            st.info("Brak danych do wizualizacji.")

    # --- TAB 4: Panel admina ---
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

                        st.markdown("### 📊 Objawy i impulsy")
                        table_summary = df_patient[["Data i czas", "Objawy somatyczne", "Zachowania impulsywne"]]
                        st.dataframe(table_summary, use_container_width=True)

                        # --- Eksport ---
                        st.markdown("### 📤 Eksport danych pacjenta")
                        csv = df_patient.to_csv(index=False).encode("utf-8")
                        st.download_button("⬇️ Pobierz CSV", data=csv, file_name=f"{selected_user}_dziennik.csv", mime="text/csv")

                        # --- Wykresy ---
                        df_patient["Data i czas"] = pd.to_datetime(df_patient["Data i czas"])
                        st.subheader("📈 Trendy pacjenta")

                        fig, ax = plt.subplots()
                        for col, label in [
                            ("Nastrój (0-10)", "Nastrój"),
                            ("Poziom lęku/napięcia (0-10)", "Lęk"),
                            ("Energia/motywacja (0-10)", "Energia"),
                            ("Apetyt (0-10)", "Apetyt")
                        ]:
                            if col in df_patient:
                                ax.plot(df_patient["Data i czas"], df_patient[col], marker="o", label=label)

                        low = df_patient[df_patient["Nastrój (0-10)"] < 3]
                        if not low.empty:
                            ax.scatter(low["Data i czas"], low["Nastrój (0-10)"], color="red", s=60, zorder=5, label="Bardzo niski nastrój")

                        ax.set_ylabel("Poziom (0–10)")
                        ax.set_xlabel("Data")
                        ax.legend()
                        plt.xticks(rotation=45)
                        st.pyplot(fig)

                        # --- Wykresy snu ---
                        st.subheader("🌙 Sen pacjenta")
                        df_patient["Zaśnięcie_dt"] = pd.to_datetime(df_patient["Godzina zaśnięcia"], format="%H:%M", errors="coerce")
                        df_patient["Pobudka_dt"] = pd.to_datetime(df_patient["Godzina wybudzenia"], format="%H:%M", errors="coerce")
                        df_patient["Godzina zaśnięcia (h)"] = df_patient["Zaśnięcie_dt"].dt.hour + df_patient["Zaśnięcie_dt"].dt.minute/60
                        df_patient["Godzina wybudzenia (h)"] = df_patient["Pobudka_dt"].dt.hour + df_patient["Pobudka_dt"].dt.minute/60
                        df_patient["Długość snu (h)"] = (df_patient["Pobudka_dt"] - df_patient["Zaśnięcie_dt"]).dt.total_seconds() / 3600

                        fig2, ax2 = plt.subplots()
                        ax2.plot(df_patient["Data i czas"], df_patient["Godzina zaśnięcia (h)"], marker="o", label="Zaśnięcie (godz.)")
                        ax2.plot(df_patient["Data i czas"], df_patient["Godzina wybudzenia (h)"], marker="o", label="Pobudka (godz.)")
                        ax2.plot(df_patient["Data i czas"], df_patient["Liczba wybudzeń w nocy"], marker="x", label="Wybudzenia w nocy")
                        ax2.plot(df_patient["Data i czas"], df_patient["Subiektywna jakość snu (0-10)"], marker="s", label="Jakość snu (0-10)")
                        ax2.plot(df_patient["Data i czas"], df_patient["Długość snu (h)"], marker="d", label="Długość snu (h)")

                        ax2.set_ylabel("Parametry snu")
                        ax2.set_xlabel("Data")
                        ax2.legend()
                        plt.xticks(rotation=45)
                        st.pyplot(fig2)

                        # --- Statystyki snu ---
                        st.markdown("### 📊 Statystyki snu")
                        avg_sleep = df_patient["Długość snu (h)"].mean(skipna=True)
                        avg_wakeups = df_patient["Liczba wybudzeń w nocy"].mean(skipna=True)
                        avg_quality = df_patient["Subiektywna jakość snu (0-10)"].mean(skipna=True)

                        col1, col2, col3 = st.columns(3)
                        col1.metric("Średnia długość snu", f"{avg_sleep:.1f} h" if not pd.isna(avg_sleep) else "–")
                        col2.metric("Średnia liczba wybudzeń", f"{avg_wakeups:.1f}" if not pd.isna(avg_wakeups) else "–")
                        col3.metric("Średnia jakość snu", f"{avg_quality:.1f}/10" if not pd.isna(avg_quality) else "–")
