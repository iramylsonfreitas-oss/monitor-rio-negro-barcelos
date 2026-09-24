import csv
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# ==========================================================
# CONFIGURAÇÃO
# ==========================================================

ANA_IDENTIFIER = os.environ["ANA_IDENTIFIER"]
ANA_PASSWORD = os.environ["ANA_PASSWORD"]

AUTH_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas/OAUth/v1"
)

DATA_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas/"
    "HidroinfoanaSerieTelemetricaAdotada/v2"
)

ESTACOES = {
    "14110000": "Cucuí",
    "14280001": "Taracuá",
    "14330000": "Curicuriari",
    "14420000": "Serrinha",
    "14480002": "Barcelos",
}

ANA_TIMEZONE = ZoneInfo(
    "America/Sao_Paulo"
)

MANAUS_TIMEZONE = ZoneInfo(
    "America/Manaus"
)

BACKFILL_DAYS = 365

DATA_DIR = Path("data")

HISTORY_DIR = (
    DATA_DIR / "history"
)

HISTORY_FILE = (
    HISTORY_DIR / "hourly.csv"
)

HISTORY_FIELDS = [
    "estacao",
    "nome",
    "hora_manaus",
    "nivel_cm",
    "nivel_m",
    "nivel_min_cm",
    "nivel_max_cm",
    "medicoes",
    "ultima_medicao_manaus",
]


# ==========================================================
# HTTP
# ==========================================================

def request_json(
    url,
    headers,
    attempts=4,
    timeout=180
):
    last_error = None

    for attempt in range(
        1,
        attempts + 1
    ):

        req = urllib.request.Request(
            url,
            headers=headers
        )

        try:

            with urllib.request.urlopen(
                req,
                timeout=timeout
            ) as response:

                body = (
                    response
                    .read()
                    .decode(
                        "utf-8",
                        errors="replace"
                    )
                )

                return json.loads(
                    body
                )

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError
        ) as error:

            last_error = error

            print(
                f"Tentativa {attempt} "
                f"falhou: {error}"
            )

            if attempt == attempts:
                raise

            wait_seconds = (
                15 * attempt
            )

            print(
                f"Aguardando "
                f"{wait_seconds}s..."
            )

            time.sleep(
                wait_seconds
            )

    raise RuntimeError(
        f"Falha na consulta: "
        f"{last_error}"
    )


# ==========================================================
# AUTENTICAÇÃO
# ==========================================================

def authenticate():

    response = request_json(
        AUTH_URL,
        headers={
            "Identificador":
                ANA_IDENTIFIER,

            "Senha":
                ANA_PASSWORD,

            "Accept":
                "application/json",

            "User-Agent":
                "Monitor-Rio-Negro/1.0",
        }
    )

    token = (
        response.get("items")
        or {}
    ).get(
        "tokenautenticacao"
    )

    if not token:

        raise RuntimeError(
            "Token de autenticação "
            "não encontrado."
        )

    return token


# ==========================================================
# DATAS E NÍVEIS
# ==========================================================

def parse_ana_datetime(value):

    return datetime.fromisoformat(
        value.replace(
            " ",
            "T"
        )
    ).replace(
        tzinfo=ANA_TIMEZONE
    )


def to_manaus_datetime(value):

    return (
        parse_ana_datetime(
            value
        )
        .astimezone(
            MANAUS_TIMEZONE
        )
    )


def level_cm(row):

    return float(
        str(
            row["Cota_Adotada"]
        ).replace(
            ",",
            "."
        )
    )


# ==========================================================
# CONSULTA DE UMA JANELA DE 30 DIAS
# ==========================================================

def fetch_window(
    token,
    end_date
):

    parameters = {

        "Codigos_Estacoes":
            ",".join(
                ESTACOES.keys()
            ),

        "Tipo Filtro Data":
            "DATA_LEITURA",

        "Data de Busca (yyyy-MM-dd)":
            end_date.strftime(
                "%Y-%m-%d"
            ),

        "Range Intervalo de busca":
            "DIAS_30",
    }

    query = (
        urllib.parse.urlencode(
            parameters
        )
    )

    url = (
        DATA_URL
        + "?"
        + query
    )

    response = request_json(
        url,
        headers={
            "Authorization":
                "Bearer " + token,

            "Accept":
                "application/json",

            "User-Agent":
                "Monitor-Rio-Negro/1.0",
        }
    )

    items = (
        response.get("items")
        or []
    )

    print(
        "Mensagem ANA:",
        response.get(
            "message"
        )
    )

    return items


# ==========================================================
# CONVERSÃO PARA SÉRIE HORÁRIA
# ==========================================================

def build_hourly_rows(
    items
):

    groups = defaultdict(
        list
    )

    for row in items:

        codigo = str(
            row.get(
                "codigoestacao"
            )
        )

        if codigo not in ESTACOES:
            continue

        measurement_raw = (
            row.get(
                "Data_Hora_Medicao"
            )
        )

        cota = row.get(
            "Cota_Adotada"
        )

        if (
            not measurement_raw
            or cota in (
                None,
                ""
            )
        ):
            continue

        measurement = (
            to_manaus_datetime(
                measurement_raw
            )
        )

        hour = measurement.replace(
            minute=0,
            second=0,
            microsecond=0
        )

        groups[
            (
                codigo,
                hour
            )
        ].append(
            {
                "nivel_cm":
                    level_cm(row),

                "medicao":
                    measurement,
            }
        )

    rows = []

    for (
        codigo,
        hour
    ), values in sorted(
        groups.items(),
        key=lambda item: (
            item[0][1],
            item[0][0]
        )
    ):

        levels = [
            item["nivel_cm"]
            for item in values
        ]

        median_cm = float(
            statistics.median(
                levels
            )
        )

        latest_measurement = max(
            item["medicao"]
            for item in values
        )

        rows.append(
            {
                "estacao":
                    codigo,

                "nome":
                    ESTACOES[
                        codigo
                    ],

                "hora_manaus":
                    hour.strftime(
                        "%Y-%m-%d %H:00:00"
                    ),

                "nivel_cm":
                    f"{median_cm:.1f}",

                "nivel_m":
                    f"{median_cm / 100:.3f}",

                "nivel_min_cm":
                    f"{min(levels):.1f}",

                "nivel_max_cm":
                    f"{max(levels):.1f}",

                "medicoes":
                    str(
                        len(levels)
                    ),

                "ultima_medicao_manaus":
                    latest_measurement.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
            }
        )

    return rows


# ==========================================================
# HISTÓRICO EXISTENTE
# ==========================================================

def load_existing_history():

    history = {}

    if not HISTORY_FILE.exists():

        return history

    with HISTORY_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            key = (
                row["estacao"],
                row["hora_manaus"]
            )

            history[
                key
            ] = row

    return history


def save_history(
    history
):

    HISTORY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    ordered = sorted(
        history.values(),
        key=lambda row: (
            row[
                "hora_manaus"
            ],
            row[
                "estacao"
            ]
        )
    )

    with HISTORY_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=
                HISTORY_FIELDS
        )

        writer.writeheader()

        writer.writerows(
            ordered
        )

    return len(
        ordered
    )


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    print(
        "===================================="
    )

    print(
        "BACKFILL HISTÓRICO RIO NEGRO"
    )

    print(
        "===================================="
    )

    print()

    print(
        "Autenticando na ANA..."
    )

    token = authenticate()

    print(
        "Autenticação OK."
    )

    print()


    today_manaus = (
        datetime.now(
            MANAUS_TIMEZONE
        ).date()
    )

    target_start = (
        today_manaus
        - timedelta(
            days=BACKFILL_DAYS
        )
    )


    print(
        "Data final:",
        today_manaus
    )

    print(
        "Data inicial desejada:",
        target_start
    )

    print(
        "Dias desejados:",
        BACKFILL_DAYS
    )

    print()


    history = (
        load_existing_history()
    )

    initial_count = len(
        history
    )


    print(
        "Linhas existentes:",
        initial_count
    )

    print()


    end_date = (
        today_manaus
    )

    window_number = 0

    total_raw = 0

    total_hourly_generated = 0


    while (
        end_date
        >= target_start
    ):

        window_number += 1

        expected_start = (
            end_date
            - timedelta(
                days=29
            )
        )


        print(
            "===================================="
        )

        print(
            f"JANELA {window_number}"
        )

        print(
            "===================================="
        )

        print(
            "Período esperado:",
            expected_start,
            "até",
            end_date
        )


        items = fetch_window(
            token,
            end_date
        )


        print(
            "Registros brutos:",
            len(items)
        )


        total_raw += len(
            items
        )


        hourly_rows = (
            build_hourly_rows(
                items
            )
        )


        print(
            "Registros horários:",
            len(
                hourly_rows
            )
        )


        total_hourly_generated += (
            len(
                hourly_rows
            )
        )


        for row in hourly_rows:

            hour_date = (
                datetime.strptime(
                    row[
                        "hora_manaus"
                    ],
                    "%Y-%m-%d %H:%M:%S"
                ).date()
            )


            if (
                hour_date
                < target_start
            ):
                continue


            key = (
                row[
                    "estacao"
                ],
                row[
                    "hora_manaus"
                ]
            )


            history[
                key
            ] = row


        print(
            "Total acumulado "
            "no histórico:",
            len(history)
        )


        end_date = (
            end_date
            - timedelta(
                days=30
            )
        )


        if (
            end_date
            >= target_start
        ):
            print()
            print(
                "Aguardando 8 segundos "
                "antes da próxima consulta..."
            )

            time.sleep(
                8
            )

        print()


    final_count = save_history(
        history
    )


    print(
        "===================================="
    )

    print(
        "BACKFILL CONCLUÍDO"
    )

    print(
        "===================================="
    )

    print(
        "Linhas antes:",
        initial_count
    )

    print(
        "Linhas depois:",
        final_count
    )

    print(
        "Novas linhas líquidas:",
        final_count
        - initial_count
    )

    print(
        "Registros brutos processados:",
        total_raw
    )

    print(
        "Registros horários processados:",
        total_hourly_generated
    )

    print(
        "Arquivo:",
        HISTORY_FILE
    )

    print()


    if final_count:

        first_row = min(
            history.values(),
            key=lambda row:
                row[
                    "hora_manaus"
                ]
        )

        last_row = max(
            history.values(),
            key=lambda row:
                row[
                    "hora_manaus"
                ]
        )


        print(
            "Primeira hora armazenada:",
            first_row[
                "hora_manaus"
            ]
        )

        print(
            "Última hora armazenada:",
            last_row[
                "hora_manaus"
            ]
        )


if __name__ == "__main__":
    main()
