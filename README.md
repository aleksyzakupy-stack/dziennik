# Dziennik nastroju i objawów

Aplikacja Streamlit do monitorowania nastroju, objawów somatycznych, snu i aktywności pacjenta. Dane użytkowników oraz wpisy dziennika są przechowywane w Google Sheets.

## Przygotowanie Google Sheet

1. Utwórz arkusz Google Sheets.
2. Skopiuj ID arkusza z adresu URL:
   `https://docs.google.com/spreadsheets/d/ID_ARKUSZA/edit`
3. Aplikacja sama utworzy i sprawdzi dwa worksheety:
   - `users`
   - `entries`
4. Jeśli worksheety istnieją już wcześniej, ich pierwszy wiersz musi mieć dokładnie wymagane nagłówki. W przeciwnym razie aplikacja pokaże czytelny błąd.

Nagłówki `users`: `username`, `name`, `password`, `role`.

Nagłówki `entries`: `username`, `Data i czas`, `Nastrój (0-10)`, `Poziom lęku/napięcia (0-10)`, `Objawy somatyczne`, `Godzina zaśnięcia`, `Godzina wybudzenia`, `Liczba wybudzeń w nocy`, `Subiektywna jakość snu (0-10)`, `Energia/motywacja (0-10)`, `Apetyt (0-10)`, `Wykonane aktywności`, `Zachowania impulsywne`, `Uwagi`.

## Service Account

1. W Google Cloud włącz:
   - Google Sheets API
   - Google Drive API
2. Utwórz service account i wygeneruj klucz JSON.
3. Skopiuj `client_email` z klucza service account.
4. W Google Sheets kliknij `Udostępnij` i dodaj ten `client_email` jako `Editor`.

## Sekrety lokalne

1. Utwórz plik `.streamlit/secrets.toml` na podstawie przykładu:
   ```bash
   mkdir -p .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
2. Uzupełnij:
   - `GOOGLE_SHEET_ID`
   - sekcję `[gcp_service_account]` danymi z klucza JSON service account

Nie używaj `credentials.json` w kodzie aplikacji. Pliki `.streamlit/secrets.toml`, `credentials.json`, `users.yaml` i katalog `data/` są ignorowane przez Git i nie mogą trafić do GitHub.

## Streamlit Cloud

1. Po wdrożeniu aplikacji w Streamlit Cloud otwórz ustawienia aplikacji.
2. Wejdź w `Secrets`.
3. Wklej zawartość lokalnego `.streamlit/secrets.toml`.
4. Upewnij się, że service account nadal ma uprawnienie `Editor` do Google Sheet.

## Uruchomienie lokalne

1. Utwórz i aktywuj środowisko:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Zainstaluj zależności:
   ```bash
   pip install -r requirements.txt
   ```
3. Uruchom aplikację:
   ```bash
   streamlit run app.py
   ```

Jeśli worksheet `users` jest pusty, aplikacja utworzy domyślnego admina:

- username: `Kasper`
- name: `Lek. Aleksy Kasperowicz`
- role: `admin`
