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

ANA_IDENTIFIER = os.environ[
    "ANA_IDENTIFIER"
]

ANA_PASSWORD = os.environ[
    "ANA_PASSWORD"
]


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


# 24/09/2023 em diante.
# Usamos uma data fixa para termos uma
# base histórica consistente.

TARGET_START = datetime(
    2023,
    9,
    24
).date()


DATA_DIR = Path(
    "data"
)

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
    attempts=5,
    timeout=180
):

    last_error = None


    for attempt in range(
        1,
        attempts + 1
    ):

        request = (
            urllib.request.Request(
                url,
                headers=headers
            )
        )


        try:

            with urllib.request.urlopen(
                request,
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
                "Tentativa",
                attempt,
                "falhou:",
                error
            )


            if attempt == attempts:
                raise


            wait_seconds = (
                15 * attempt
            )


            print(
                "Aguardando",
                wait_seconds,
                "segundos..."
            )


            time.sleep(
                wait_seconds
            )


    raise RuntimeError(
        f"Falha na consulta: {last_error}"
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
            "Token ANA não encontrado."
        )


    return token


# ==========================================================
# DATAS
# ==========================================================

def parse_ana_datetime(
    value
):

    return datetime.fromisoformat(
        value.replace(
            " ",
            "T"
        )
    ).replace(
        tzinfo=ANA_TIMEZONE
    )


def to_manaus_datetime(
    value
):

    return (
        parse_ana_datetime(
            value
        )
        .astimezone(
            MANAUS_TIMEZONE
        )
    )


def level_cm(
    row
):

    return float(
        str(
            row[
                "Cota_Adotada"
            ]
        ).replace(
            ",",
            "."
        )
    )


# ==========================================================
# CONSULTA ANA
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


    return (
        response.get("items")
        or []
    )


# ==========================================================
# TRANSFORMAÇÃO PARA HORÁRIO
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


        try:

            measurement = (
                to_manaus_datetime(
                    measurement_raw
                )
            )


            level = level_cm(
                row
            )


        except Exception as error:

            print(
                "Registro ignorado:",
                codigo,
                measurement_raw,
                error
            )

            continue


        hour = (
            measurement.replace(
                minute=0,
                second=0,
                microsecond=0
            )
        )


        groups[
            (
                codigo,
                hour
            )
        ].append(
            {
                "nivel_cm":
                    level,

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
            item[
                "nivel_cm"
            ]
            for item in values
        ]


        median_cm = float(
            statistics.median(
                levels
            )
        )


        latest_measurement = max(
            item[
                "medicao"
            ]
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
# HISTÓRICO ATUAL
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


    return history


# ==========================================================
# SALVAR HISTÓRICO
# ==========================================================

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
# ESTATÍSTICAS POR ESTAÇÃO
# ==========================================================

def station_statistics(
    history
):

    grouped = defaultdict(
        list
    )


    for row in history.values():

        grouped[
            row[
                "estacao"
            ]
        ].append(
            row[
                "hora_manaus"
            ]
        )


    result = {}


    for codigo, nome in (
        ESTACOES.items()
    ):

        timestamps = (
            grouped.get(
                codigo,
                []
            )
        )


        if not timestamps:

            result[
                codigo
            ] = {
                "nome":
                    nome,

                "registros":
                    0,

                "inicio":
                    None,

                "fim":
                    None,
            }

            continue


        result[
            codigo
        ] = {
            "nome":
                nome,

            "registros":
                len(
                    timestamps
                ),

            "inicio":
                min(
                    timestamps
                ),

            "fim":
                max(
                    timestamps
                ),
        }


    return result


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    print()
    print(
        "===================================="
    )

    print(
        "BACKFILL RIO NEGRO - 3 ANOS"
    )

    print(
        "===================================="
    )

    print()


    today = (
        datetime.now(
            MANAUS_TIMEZONE
        ).date()
    )


    print(
        "Data inicial:",
        TARGET_START
    )

    print(
        "Data final:",
        today
    )

    print()


    print(
        "Autenticando..."
    )


    token = authenticate()


    print(
        "Autenticação OK."
    )

    print()


    history = (
        load_existing_history()
    )


    initial_count = len(
        history
    )


    print(
        "Registros existentes:",
        initial_count
    )

    print()


    end_date = today

    window_number = 0

    success_windows = 0

    failed_windows = []

    total_raw = 0

    total_hourly = 0


    while (
        end_date
        >= TARGET_START
    ):

        window_number += 1


        expected_start = (
            end_date
            - timedelta(
                days=29
            )
        )


        print()
        print(
            "===================================="
        )

        print(
            "JANELA",
            window_number
        )

        print(
            "===================================="
        )

        print(
            "Período:",
            expected_start,
            "até",
            end_date
        )


        try:

            items = fetch_window(
                token,
                end_date
            )


            print(
                "Registros brutos:",
                len(items)
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


            total_raw += len(
                items
            )


            total_hourly += len(
                hourly_rows
            )


            added_or_updated = 0


            for row in hourly_rows:

                row_date = (
                    datetime.strptime(
                        row[
                            "hora_manaus"
                        ],
                        "%Y-%m-%d %H:%M:%S"
                    ).date()
                )


                if (
                    row_date
                    < TARGET_START
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


                added_or_updated += 1


            success_windows += 1


            print(
                "Linhas incorporadas:",
                added_or_updated
            )


            print(
                "Total acumulado:",
                len(history)
            )


            # Salva a cada janela para
            # preservar o progresso dentro
            # da execução.

            save_history(
                history
            )


        except Exception as error:

            failed_windows.append(
                {
                    "data_final":
                        end_date.strftime(
                            "%Y-%m-%d"
                        ),

                    "erro":
                        str(error),
                }
            )


            print()
            print(
                "ATENÇÃO:"
            )

            print(
                "A janela falhou, "
                "mas o backfill continuará."
            )

            print(
                "Data final:",
                end_date
            )

            print(
                "Erro:",
                error
            )


            # Refaz autenticação para
            # a próxima janela.

            try:

                print(
                    "Renovando token..."
                )

                token = authenticate()

                print(
                    "Novo token obtido."
                )

            except Exception as auth_error:

                print(
                    "Não foi possível "
                    "renovar o token:",
                    auth_error
                )


        end_date = (
            end_date
            - timedelta(
                days=30
            )
        )


        if (
            end_date
            >= TARGET_START
        ):

            print()
            print(
                "Aguardando 8 segundos..."
            )

            time.sleep(
                8
            )


    final_count = save_history(
        history
    )


    statistics_by_station = (
        station_statistics(
            history
        )
    )


    print()
    print(
        "===================================="
    )

    print(
        "BACKFILL CONCLUÍDO"
    )

    print(
        "===================================="
    )

    print()


    print(
        "Janelas tentadas:",
        window_number
    )

    print(
        "Janelas concluídas:",
        success_windows
    )

    print(
        "Janelas com falha:",
        len(
            failed_windows
        )
    )

    print()


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

    print()


    print(
        "Registros brutos processados:",
        total_raw
    )

    print(
        "Registros horários processados:",
        total_hourly
    )

    print()


    print(
        "===================================="
    )

    print(
        "COBERTURA FINAL POR ESTAÇÃO"
    )

    print(
        "===================================="
    )


    for codigo, nome in (
        ESTACOES.items()
    ):

        stats = (
            statistics_by_station[
                codigo
            ]
        )


        print()
        print(
            nome,
            codigo
        )

        print(
            "Registros:",
            stats[
                "registros"
            ]
        )

        print(
            "Início:",
            stats[
                "inicio"
            ]
        )

        print(
            "Fim:",
            stats[
                "fim"
            ]
        )


    if failed_windows:

        print()
        print(
            "===================================="
        )

        print(
            "JANELAS QUE PRECISAM SER REPETIDAS"
        )

        print(
            "===================================="
        )


        for failure in (
            failed_windows
        ):

            print()

            print(
                "Data final:",
                failure[
                    "data_final"
                ]
            )

            print(
                "Erro:",
                failure[
                    "erro"
                ]
            )


        print()
        print(
            "O workflow pode ser executado "
            "novamente para preencher "
            "essas lacunas."
        )


    print()
    print(
        "Arquivo:",
        HISTORY_FILE
    )


if __name__ == "__main__":
    main()
