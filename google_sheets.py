import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import streamlit as st
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

USERS_HEADERS = ["username", "name", "password", "role"]

ENTRY_DATA_HEADERS = [
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
    "Uwagi",
]

ENTRIES_HEADERS = ["username", *ENTRY_DATA_HEADERS]

ENTRY_NUMERIC_COLUMNS = [
    "Nastrój (0-10)",
    "Poziom lęku/napięcia (0-10)",
    "Liczba wybudzeń w nocy",
    "Subiektywna jakość snu (0-10)",
    "Energia/motywacja (0-10)",
    "Apetyt (0-10)",
]

DEFAULT_ADMIN_USERNAME = "Kasper"
DEFAULT_ADMIN_NAME = "Lek. Aleksy Kasperowicz"
DEFAULT_ADMIN_HASH = "$2b$12$ei/CshYLjrjCx5xp0vKZ1.saL2avwM2mel1ySKKrxXjAJy6C3sEQC"


class GoogleSheetsError(Exception):
    """Base exception with a user-facing message for Streamlit."""


class GoogleSheetsConfigError(GoogleSheetsError):
    """Raised when Streamlit secrets are missing or incomplete."""


class GoogleSheetsHeaderError(GoogleSheetsError):
    """Raised when a worksheet has unexpected headers."""


def _api_error_message(action: str, exc: Exception) -> GoogleSheetsError:
    return GoogleSheetsError(
        f"Google Sheets API zwróciło błąd podczas operacji: {action}. "
        f"Szczegóły: {exc}"
    )


def _get_secret(key: str) -> Any:
    try:
        value = st.secrets[key]
    except KeyError:
        raise GoogleSheetsConfigError(f'Brakuje Streamlit secret: st.secrets["{key}"].')
    except FileNotFoundError:
        raise GoogleSheetsConfigError(
            "Brakuje pliku `.streamlit/secrets.toml` albo nie zawiera on wymaganych "
            f'danych: st.secrets["{key}"].'
        )
    except Exception as exc:
        raise GoogleSheetsConfigError(
            f'Nie udało się odczytać st.secrets["{key}"]. Szczegóły: {exc}'
        )

    if value in (None, ""):
        raise GoogleSheetsConfigError(f'Brakuje wartości w st.secrets["{key}"].')
    return value


def _get_service_account_info() -> Dict[str, Any]:
    raw_info = _get_secret("gcp_service_account")
    try:
        info = dict(raw_info)
    except Exception as exc:
        raise GoogleSheetsConfigError(
            'st.secrets["gcp_service_account"] musi być sekcją TOML z danymi '
            f"service account. Szczegóły: {exc}"
        )

    required_keys = {
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    }
    missing = sorted(key for key in required_keys if not info.get(key))
    if missing:
        missing_text = ", ".join(missing)
        raise GoogleSheetsConfigError(
            'Sekcja st.secrets["gcp_service_account"] jest niekompletna. '
            f"Brakujące pola: {missing_text}."
        )

    info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
    return info


def _sheet_id() -> str:
    return str(_get_secret("GOOGLE_SHEET_ID")).strip()


@st.cache_resource(show_spinner=False)
def get_google_client():
    try:
        credentials = Credentials.from_service_account_info(
            _get_service_account_info(),
            scopes=SCOPES,
        )
        return gspread.authorize(credentials)
    except GoogleSheetsConfigError:
        raise
    except GoogleAuthError as exc:
        raise GoogleSheetsConfigError(
            "Nie udało się uwierzytelnić service account. Sprawdź dane w "
            'st.secrets["gcp_service_account"]. '
            f"Szczegóły: {exc}"
        )
    except Exception as exc:
        raise GoogleSheetsConfigError(
            "Nie udało się utworzyć klienta Google Sheets z danych service account. "
            f"Szczegóły: {exc}"
        )


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    sheet_id = _sheet_id()
    try:
        return get_google_client().open_by_key(sheet_id)
    except SpreadsheetNotFound:
        raise GoogleSheetsError(
            "Nie mogę otworzyć Google Sheet. Sprawdź GOOGLE_SHEET_ID oraz czy "
            "client_email service account ma uprawnienie Editor do arkusza."
        )
    except APIError as exc:
        raise _api_error_message("otwieranie arkusza", exc)


def get_worksheet(sheet_name: str):
    try:
        return get_spreadsheet().worksheet(sheet_name)
    except WorksheetNotFound:
        raise GoogleSheetsError(f'Worksheet "{sheet_name}" nie istnieje w arkuszu.')
    except APIError as exc:
        raise _api_error_message(f'odczyt worksheet "{sheet_name}"', exc)


def ensure_worksheet(sheet_name: str, headers: Sequence[str]):
    try:
        spreadsheet = get_spreadsheet()
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except WorksheetNotFound:
            try:
                worksheet = spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=max(len(headers), 1),
                )
            except APIError as exc:
                raise GoogleSheetsError(
                    f'Nie udało się utworzyć worksheet "{sheet_name}". '
                    f"Szczegóły: {exc}"
                )

        current_headers = worksheet.row_values(1)
        if not current_headers:
            worksheet.append_row(list(headers), value_input_option="RAW")
            return worksheet

        if current_headers != list(headers):
            expected = ", ".join(headers)
            found = ", ".join(current_headers)
            raise GoogleSheetsHeaderError(
                f'Worksheet "{sheet_name}" ma nieprawidłowe nagłówki. '
                f"Oczekiwane: {expected}. Obecne: {found}."
            )

        return worksheet
    except GoogleSheetsError:
        raise
    except APIError as exc:
        raise _api_error_message(f'przygotowanie worksheet "{sheet_name}"', exc)


def load_users_config() -> Dict[str, Any]:
    worksheet = ensure_worksheet("users", USERS_HEADERS)
    try:
        records = worksheet.get_all_records()
    except APIError as exc:
        raise _api_error_message('odczyt worksheet "users"', exc)

    usernames: Dict[str, Dict[str, str]] = {}
    for record in records:
        username = str(record.get("username", "")).strip()
        if not username:
            continue
        usernames[username] = {
            "name": str(record.get("name", "")).strip(),
            "password": str(record.get("password", "")).strip(),
            "role": str(record.get("role", "")).strip() or "pacjent",
        }

    if not usernames:
        usernames[DEFAULT_ADMIN_USERNAME] = {
            "name": DEFAULT_ADMIN_NAME,
            "password": DEFAULT_ADMIN_HASH,
            "role": "admin",
        }
        try:
            worksheet.append_row(
                [
                    DEFAULT_ADMIN_USERNAME,
                    DEFAULT_ADMIN_NAME,
                    DEFAULT_ADMIN_HASH,
                    "admin",
                ],
                value_input_option="RAW",
            )
        except APIError as exc:
            raise _api_error_message('utworzenie domyślnego admina w "users"', exc)

    return {"credentials": {"usernames": usernames}}


def save_users_config(config: Dict[str, Any]) -> None:
    worksheet = ensure_worksheet("users", USERS_HEADERS)
    usernames = (
        config.get("credentials", {})
        .get("usernames", {})
    )
    rows = [USERS_HEADERS]
    for username, user_data in usernames.items():
        rows.append(
            [
                username,
                user_data.get("name", ""),
                user_data.get("password", ""),
                user_data.get("role", "pacjent"),
            ]
        )

    try:
        worksheet.update(
            range_name=f"A1:D{len(rows)}",
            values=rows,
            value_input_option="RAW",
        )
        existing_rows = len(worksheet.get_all_values())
        if existing_rows > len(rows):
            worksheet.batch_clear([f"A{len(rows) + 1}:D{existing_rows}"])
    except APIError as exc:
        raise _api_error_message('zapis worksheet "users"', exc)


def _normalize_entry_value(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, datetime.time):
        return value.strftime("%H:%M")
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _entry_row(username: str, entry_dict: Dict[str, Any]) -> List[Any]:
    return [
        username,
        *[_normalize_entry_value(entry_dict.get(column, "")) for column in ENTRY_DATA_HEADERS],
    ]


def _entries_dataframe(records: Iterable[Dict[str, Any]], include_username: bool) -> pd.DataFrame:
    headers = ENTRIES_HEADERS if include_username else ENTRY_DATA_HEADERS
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=headers)

    df = df.reindex(columns=ENTRIES_HEADERS)
    for column in ENTRY_NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["_sort_key"] = pd.to_datetime(df["Data i czas"], errors="coerce")
    df = df.sort_values("_sort_key", na_position="last").drop(columns="_sort_key")
    df = df.reset_index(drop=True)

    if include_username:
        return df.reindex(columns=ENTRIES_HEADERS)
    return df.reindex(columns=ENTRY_DATA_HEADERS)


def load_user_entries(username: str) -> pd.DataFrame:
    worksheet = ensure_worksheet("entries", ENTRIES_HEADERS)
    try:
        records = worksheet.get_all_records()
    except APIError as exc:
        raise _api_error_message('odczyt worksheet "entries"', exc)

    filtered_records = [
        record
        for record in records
        if str(record.get("username", "")).strip() == username
    ]
    return _entries_dataframe(filtered_records, include_username=False)


def load_all_entries() -> pd.DataFrame:
    worksheet = ensure_worksheet("entries", ENTRIES_HEADERS)
    try:
        records = worksheet.get_all_records()
    except APIError as exc:
        raise _api_error_message('odczyt wszystkich wpisów z worksheet "entries"', exc)

    return _entries_dataframe(records, include_username=True)


def append_user_entry(username: str, entry_dict: Dict[str, Any]) -> None:
    worksheet = ensure_worksheet("entries", ENTRIES_HEADERS)
    try:
        worksheet.append_row(
            _entry_row(username, entry_dict),
            value_input_option="RAW",
        )
    except APIError as exc:
        raise _api_error_message('dopisywanie wpisu do worksheet "entries"', exc)


def _parse_entry_datetime(value: Any) -> Tuple[Optional[datetime.datetime], Optional[datetime.date]]:
    if isinstance(value, datetime.datetime):
        return value.replace(second=0, microsecond=0), None
    if isinstance(value, datetime.date):
        return None, value

    value_text = str(value).strip()
    if not value_text:
        return None, None
    parsed = pd.to_datetime(value_text, errors="coerce")
    if pd.isna(parsed):
        return None, None
    parsed_datetime = parsed.to_pydatetime().replace(second=0, microsecond=0)
    if len(value_text) <= 10:
        return None, parsed_datetime.date()
    return parsed_datetime, None


def _matching_entry_rows(
    rows: Sequence[Sequence[Any]],
    username: str,
    entry_datetime: Any,
) -> Tuple[List[int], bool]:
    target_datetime, target_date = _parse_entry_datetime(entry_datetime)
    if target_datetime is None and target_date is None:
        return [], False

    matched_rows: List[int] = []
    date_match = target_date is not None
    for row_number, row in enumerate(rows[1:], start=2):
        row_username = str(row[0]).strip() if len(row) > 0 else ""
        row_datetime = str(row[1]).strip() if len(row) > 1 else ""
        if row_username != username or not row_datetime:
            continue

        parsed = pd.to_datetime(row_datetime, errors="coerce")
        if pd.isna(parsed):
            continue
        parsed_datetime = parsed.to_pydatetime().replace(second=0, microsecond=0)

        if target_date is not None and parsed_datetime.date() == target_date:
            matched_rows.append(row_number)
        elif target_datetime is not None and parsed_datetime == target_datetime:
            matched_rows.append(row_number)

    return matched_rows, date_match


def update_user_entry(username: str, entry_datetime: Any, entry_dict: Dict[str, Any]) -> None:
    worksheet = ensure_worksheet("entries", ENTRIES_HEADERS)
    try:
        rows = worksheet.get_all_values()
        matched_rows, date_match = _matching_entry_rows(rows, username, entry_datetime)
        new_row = _entry_row(username, entry_dict)

        if not matched_rows:
            worksheet.append_row(new_row, value_input_option="RAW")
            return

        if len(matched_rows) == 1 and not date_match:
            row_number = matched_rows[0]
            worksheet.update(
                range_name=f"A{row_number}:N{row_number}",
                values=[new_row],
                value_input_option="RAW",
            )
            return

        for row_number in sorted(matched_rows, reverse=True):
            worksheet.delete_rows(row_number)
        worksheet.append_row(new_row, value_input_option="RAW")
    except APIError as exc:
        raise _api_error_message('aktualizacja wpisu w worksheet "entries"', exc)


def delete_user_entry(username: str, entry_datetime: Any) -> None:
    worksheet = ensure_worksheet("entries", ENTRIES_HEADERS)
    try:
        rows = worksheet.get_all_values()
        matched_rows, date_match = _matching_entry_rows(rows, username, entry_datetime)
        if not matched_rows:
            return

        rows_to_delete = matched_rows if date_match else matched_rows[:1]
        for row_number in sorted(rows_to_delete, reverse=True):
            worksheet.delete_rows(row_number)
    except APIError as exc:
        raise _api_error_message('usuwanie wpisu z worksheet "entries"', exc)
