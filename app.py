import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import streamlit_authenticator as stauth

# --- Autoryzacja ---
names = ["Pacjent"]
usernames = ["pacjent1"]
passwords = ["haslo123"]  # ← здесь можно задать своё

hashed_passwords = stauth.Hasher(passwords).generate()

authenticator = stauth.Authenticate(
    names,
    usernames,
    hashed_passwords,
    "dziennik_cookie",  # identyfikator sesji
    "abcdef",           # klucz losowy do podpisu cookie
    cookie_expiry_days=1
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status == False:
    st.error("❌ Nieprawidłowy login lub hasło")
if authentication_status == None:
    st.warning("🔑 Wprowadź login i hasło")

# --- Jeśli zalogowano ---
if authentication_status:

    authenticator.logout("Wyloguj", "sidebar")
    st.sidebar.success(f"Zalogowano: {name}")

CSV_FILE = "dziennik.csv"

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

# --- Ładowanie danych ---
try:
    df = pd.read_csv(CSV_FILE)
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

# --- Layout z zakładkami ---
st.set_page_config(page_title="Dziennik nastroju", layout="wide")
st.title("📓 Dziennik nastroju i objawów")

tab1, tab2, tab3 = st.tabs(["✍️ Formularz", "📑 Historia", "📈 Wykresy"])

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
        df.to_csv(CSV_FILE, index=False)
        st.success("✅ Wpis dodany!")

# --- TAB 2: Historia ---
with tab2:
    st.subheader("Historia wpisów")
    st.dataframe(df, use_container_width=True)

    # Eksport danych
    st.markdown("### 📤 Eksport danych")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Pobierz CSV", data=csv, file_name="dziennik.csv", mime="text/csv")

    try:
        import io, openpyxl
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            "⬇️ Pobierz XLSX",
            data=buffer.getvalue(),
            file_name="dziennik.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ImportError:
        st.info("📎 Eksport do XLSX wymaga pakietu `openpyxl` (`pip install openpyxl`).")

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
    else:
        st.info("Brak danych do wizualizacji.")
