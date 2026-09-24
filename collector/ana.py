import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


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

BARCELOS = "14480002"

ANA_TIMEZONE = ZoneInfo(
    "America/Sao_Paulo"
)

MANAUS_TIMEZONE = ZoneInfo(
    "America/Manaus"
)


def request_json(
    url,
    headers,
    attempts=3,
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

                return json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace"
                    )
                )

        except urllib.error.HTTPError as error:
            last_error = error

            if (
                error.code not in
                (429, 502, 503, 504)
                or attempt == attempts
            ):
                body = error.read().decode(
                    "utf-8",
                    errors="replace"
                )

                raise RuntimeError(
                    f"ANA retornou HTTP "
                    f"{error.code}: "
                    f"{body[:1000]}"
                ) from error

        except urllib.error.URLError as error:
            last_error = error

            if attempt == attempts:
                raise

        time.sleep(
            8 * attempt
        )

    raise RuntimeError(
        f"Falha ao consultar ANA: "
        f"{last_error}"
    )


def parse_time(value):
    return datetime.fromisoformat(
        value.replace(
            " ",
            "T"
        )
    )


def ana_time_with_timezone(value):
    return parse_time(
        value
    ).replace(
        tzinfo=ANA_TIMEZONE
    )


def to_manaus(value):
    if not value:
        return None

    dt = ana_time_with_timezone(
        value
    ).astimezone(
        MANAUS_TIMEZONE
    )

    return dt.strftime(
        "%Y-%m-%d %H:%M:%S"
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


def find_reference(
    series,
    target,
    max_gap_hours=3
):
    anteriores = [
        row
        for row in series

        if parse_time(
            row["Data_Hora_Medicao"]
        ) <= target
    ]

    if not anteriores:
        return None

    reference = max(
        anteriores,
        key=lambda row:
            parse_time(
                row[
                    "Data_Hora_Medicao"
                ]
            )
    )

    reference_time = parse_time(
        reference[
            "Data_Hora_Medicao"
        ]
    )

    gap = target - reference_time

    if gap > timedelta(
        hours=max_gap_hours
    ):
        return None

    return reference


def variation(
    latest,
    reference
):
    if reference is None:
        return None

    return round(
        level_cm(latest)
        - level_cm(reference),
        1
    )


def station_metrics(
    codigo,
    nome,
    rows
):
    valid = [
        row
        for row in rows

        if str(
            row.get(
                "codigoestacao"
            )
        ) == codigo

        and row.get(
            "Data_Hora_Medicao"
        )

        and row.get(
            "Cota_Adotada"
        ) not in (
            None,
            ""
        )
    ]

    if not valid:
        return None, []

    by_time = {
        row[
            "Data_Hora_Medicao"
        ]: row

        for row in valid
    }

    series = sorted(
        by_time.values(),
        key=lambda row:
            parse_time(
                row[
                    "Data_Hora_Medicao"
                ]
            )
    )

    latest = series[-1]

    latest_time = parse_time(
        latest[
            "Data_Hora_Medicao"
        ]
    )

    current_cm = level_cm(
        latest
    )

    ref_6h = find_reference(
        series,
        latest_time
        - timedelta(hours=6)
    )

    ref_24h = find_reference(
        series,
        latest_time
        - timedelta(hours=24)
    )

    ref_72h = find_reference(
        series,
        latest_time
        - timedelta(hours=72)
    )

    ref_7d = find_reference(
        series,
        latest_time
        - timedelta(days=7)
    )

    var_6h = variation(
        latest,
        ref_6h
    )

    var_24h = variation(
        latest,
        ref_24h
    )

    var_72h = variation(
        latest,
        ref_72h
    )

    var_7d = variation(
        latest,
        ref_7d
    )

    if var_6h is None:
        tendencia = "indisponivel"

    elif var_6h > 0:
        tendencia = "subindo"

    elif var_6h < 0:
        tendencia = "descendo"

    else:
        tendencia = "estavel"

    measurement_ana = (
        latest[
            "Data_Hora_Medicao"
        ]
    )

    measurement_tz = (
        ana_time_with_timezone(
            measurement_ana
        )
    )

    now_utc = datetime.now(
        timezone.utc
    )

    age_minutes = int(
        (
            now_utc
            - measurement_tz.astimezone(
                timezone.utc
            )
        ).total_seconds()
        / 60
    )

    age_minutes = max(
        age_minutes,
        0
    )

    result = {
        "estacao": codigo,
        "nome": nome,

        "nivel_cm":
            current_cm,

        "nivel_m":
            round(
                current_cm / 100,
                2
            ),

        "data_medicao":
            measurement_ana,

        "data_medicao_manaus":
            to_manaus(
                measurement_ana
            ),

        "data_atualizacao_ana":
            latest.get(
                "Data_Atualizacao"
            ),

        "data_atualizacao_manaus":
            to_manaus(
                latest.get(
                    "Data_Atualizacao"
                )
            ),

        "variacao_6h_cm":
            var_6h,

        "variacao_24h_cm":
            var_24h,

        "variacao_72h_cm":
            var_72h,

        "variacao_7d_cm":
            var_7d,

        "tendencia":
            tendencia,

        "idade_dado_min":
            age_minutes,

        "dado_desatualizado":
            age_minutes > 180,

        "status_cota":
            latest.get(
                "Cota_Adotada_Status"
            ),

        "registros_30d":
            len(series),

        "fonte":
            "ANA - HidroWebService",
    }

    return result, series


def main():

    # AUTENTICAÇÃO

    auth = request_json(
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
        },
    )

    token = (
        auth.get("items") or {}
    ).get(
        "tokenautenticacao"
    )

    if not token:
        raise RuntimeError(
            "Token não encontrado."
        )


    # CONSULTA ÚNICA DAS 5 ESTAÇÕES

    query = urllib.parse.urlencode(
        {
            "Codigos_Estacoes":
                ",".join(
                    ESTACOES.keys()
                ),

            "Tipo Filtro Data":
                "DATA_LEITURA",

            "Range Intervalo de busca":
                "DIAS_30",
        }
    )

    response = request_json(
        f"{DATA_URL}?{query}",
        headers={
            "Authorization":
                f"Bearer {token}",

            "Accept":
                "application/json",

            "User-Agent":
                "Monitor-Rio-Negro/1.0",
        },
    )

    items = (
        response.get("items")
        or []
    )

    if not items:
        raise RuntimeError(
            "ANA retornou zero registros."
        )


    # PROCESSAMENTO

    resultados = []

    barcelos_series = []

    for codigo, nome in (
        ESTACOES.items()
    ):
        metrics, series = (
            station_metrics(
                codigo,
                nome,
                items
            )
        )

        if metrics is None:
            print(
                f"AVISO: {nome} "
                "sem dados válidos."
            )

            continue

        resultados.append(
            metrics
        )

        if codigo == BARCELOS:
            barcelos_series = series


    if not barcelos_series:
        raise RuntimeError(
            "Série de Barcelos "
            "não encontrada."
        )


    # LOCALIZA BARCELOS

    barcelos = next(
        item
        for item in resultados

        if item[
            "estacao"
        ] == BARCELOS
    )

    barcelos[
        "coletado_em_utc"
    ] = datetime.now(
        timezone.utc
    ).isoformat()


    # SÉRIE DE BARCELOS

    output_series = [
        {
            "data_medicao":
                row[
                    "Data_Hora_Medicao"
                ],

            "data_medicao_manaus":
                to_manaus(
                    row[
                        "Data_Hora_Medicao"
                    ]
                ),

            "nivel_cm":
                level_cm(row),

            "nivel_m":
                round(
                    level_cm(row)
                    / 100,
                    2
                ),

            "status_cota":
                row.get(
                    "Cota_Adotada_Status"
                ),

            "data_atualizacao_ana":
                row.get(
                    "Data_Atualizacao"
                ),
        }

        for row in barcelos_series
    ]


    # ARQUIVO MULTIESTAÇÃO

    output_estacoes = {
        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "fonte":
            "ANA - HidroWebService",

        "timezone_exibicao":
            "America/Manaus",

        "estacoes":
            resultados,
    }


    # GRAVAÇÃO

    data_dir = Path(
        "data"
    )

    data_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    with (
        data_dir / "latest.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            barcelos,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")


    with (
        data_dir /
        "series_30d.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_series,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")


    with (
        data_dir /
        "estacoes.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output_estacoes,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")


    # LOG

    print(
        "Coleta multiestação concluída."
    )

    print()

    for station in resultados:

        print(
            station["nome"],
            "|",
            f'{station["nivel_m"]:.2f} m',
            "| 6h:",
            station[
                "variacao_6h_cm"
            ],
            "cm",
            "| 24h:",
            station[
                "variacao_24h_cm"
            ],
            "cm",
            "| tendência:",
            station[
                "tendencia"
            ]
        )

    print()

    print(
        "Total recebido da ANA:",
        len(items),
        "registros"
    )


if __name__ == "__main__":
    main()
