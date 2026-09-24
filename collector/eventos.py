import csv
import json
import statistics

from datetime import datetime, timedelta, timezone
from pathlib import Path


HISTORY_FILE = Path(
    "data/history/hourly.csv"
)

OUTPUT_FILE = Path(
    "data/eventos_propagacao.json"
)


ESTACOES = {
    "14110000": "Cucuí",
    "14280001": "Taracuá",
    "14330000": "Curicuriari",
    "14420000": "Serrinha",
    "14480002": "Barcelos",
}


BARCELOS = "14480002"


# ----------------------------------------------------------
# Parâmetros experimentais
# ----------------------------------------------------------
#
# Procuramos início de alta sustentada:
#
# - variação de pelo menos +3 cm em 24 horas
# - confirmação em três observações consecutivas
#   espaçadas em 6 horas
# - eventos muito próximos são tratados como
#   parte do mesmo movimento
#
# Esses valores ainda serão validados com os resultados.
# ----------------------------------------------------------

MIN_RISE_24H_CM = 3.0

SAMPLE_INTERVAL_HOURS = 6

CONFIRMATION_POINTS = 3

MIN_EVENT_SEPARATION_HOURS = 72


MAX_LAG_HOURS = {
    "14420000": 192,   # Serrinha -> Barcelos: até 8 dias
    "14330000": 288,   # Curicuriari: até 12 dias
    "14280001": 384,   # Taracuá: até 16 dias
    "14110000": 480,   # Cucuí: até 20 dias
}


MIN_LAG_HOURS = {
    "14420000": 24,
    "14330000": 48,
    "14280001": 72,
    "14110000": 96,
}


def parse_datetime(value):

    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S"
    )


# ==========================================================
# CARREGAR HISTÓRICO
# ==========================================================

def load_history():

    if not HISTORY_FILE.exists():

        raise RuntimeError(
            "data/history/hourly.csv "
            "não encontrado."
        )


    series = {
        codigo: {}
        for codigo in ESTACOES
    }


    with HISTORY_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file
        )


        for row in reader:

            codigo = row.get(
                "estacao"
            )

            if codigo not in series:
                continue


            timestamp = parse_datetime(
                row[
                    "hora_manaus"
                ]
            )


            nivel = float(
                row[
                    "nivel_cm"
                ]
            )


            series[
                codigo
            ][timestamp] = nivel


    return series


# ==========================================================
# AMOSTRAGEM DE 6 HORAS
# ==========================================================

def sample_every_6h(
    station_series
):

    sampled = {}


    for timestamp, level in (
        station_series.items()
    ):

        if (
            timestamp.minute == 0
            and timestamp.second == 0
            and timestamp.hour
            % SAMPLE_INTERVAL_HOURS == 0
        ):

            sampled[
                timestamp
            ] = level


    return sampled


# ==========================================================
# VARIAÇÃO DE 24 HORAS
# ==========================================================

def build_24h_changes(
    station_series
):

    sampled = sample_every_6h(
        station_series
    )


    changes = {}


    for timestamp, level in (
        sampled.items()
    ):

        previous_time = (
            timestamp
            - timedelta(
                hours=24
            )
        )


        previous_level = (
            station_series.get(
                previous_time
            )
        )


        if previous_level is None:
            continue


        changes[
            timestamp
        ] = (
            level
            - previous_level
        )


    return changes


# ==========================================================
# DETECÇÃO DE INÍCIO DE ALTA
# ==========================================================

def detect_rise_events(
    changes
):

    timestamps = sorted(
        changes.keys()
    )


    candidates = []


    for i in range(
        len(timestamps)
        - CONFIRMATION_POINTS
        + 1
    ):

        block = (
            timestamps[
                i:
                i
                + CONFIRMATION_POINTS
            ]
        )


        expected = True


        for j in range(
            1,
            len(block)
        ):

            difference = (
                block[j]
                - block[j - 1]
            )


            if difference != timedelta(
                hours=
                    SAMPLE_INTERVAL_HOURS
            ):

                expected = False
                break


        if not expected:
            continue


        values = [
            changes[t]
            for t in block
        ]


        if all(
            value
            >= MIN_RISE_24H_CM
            for value in values
        ):

            candidates.append(
                {
                    "inicio":
                        block[0],

                    "variacao_inicial_cm":
                        changes[
                            block[0]
                        ],

                    "confirmacoes":
                        values,
                }
            )


    if not candidates:

        return []


    # Evita que a mesma longa subida
    # gere dezenas de "novos eventos".

    events = []


    for candidate in candidates:

        if not events:

            events.append(
                candidate
            )

            continue


        gap = (
            candidate[
                "inicio"
            ]
            - events[-1][
                "inicio"
            ]
        )


        if gap >= timedelta(
            hours=
                MIN_EVENT_SEPARATION_HOURS
        ):

            events.append(
                candidate
            )


    return events


# ==========================================================
# CASAMENTO MONTANTE -> BARCELOS
# ==========================================================

def match_events(
    codigo,
    upstream_events,
    barcelos_events
):

    minimum = timedelta(
        hours=
            MIN_LAG_HOURS[
                codigo
            ]
    )


    maximum = timedelta(
        hours=
            MAX_LAG_HOURS[
                codigo
            ]
    )


    matches = []


    used_downstream = set()


    for upstream in (
        upstream_events
    ):

        start = (
            upstream[
                "inicio"
            ]
        )


        possibilities = []


        for index, downstream in (
            enumerate(
                barcelos_events
            )
        ):

            if index in used_downstream:
                continue


            lag = (
                downstream[
                    "inicio"
                ]
                - start
            )


            if (
                lag >= minimum
                and lag <= maximum
            ):

                possibilities.append(
                    (
                        lag,
                        index,
                        downstream
                    )
                )


        if not possibilities:
            continue


        lag, index, downstream = min(
            possibilities,
            key=lambda item:
                item[0]
        )


        used_downstream.add(
            index
        )


        lag_hours = (
            lag.total_seconds()
            / 3600
        )


        matches.append(
            {
                "inicio_montante":
                    start.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),

                "inicio_barcelos":
                    downstream[
                        "inicio"
                    ].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),

                "defasagem_h":
                    round(
                        lag_hours,
                        1
                    ),

                "defasagem_dias":
                    round(
                        lag_hours / 24,
                        2
                    ),

                "variacao_24h_montante_cm":
                    upstream[
                        "variacao_inicial_cm"
                    ],

                "variacao_24h_barcelos_cm":
                    downstream[
                        "variacao_inicial_cm"
                    ],
            }
        )


    return matches


# ==========================================================
# ESTATÍSTICAS
# ==========================================================

def percentile(
    values,
    percentile_value
):

    if not values:
        return None


    ordered = sorted(
        values
    )


    if len(ordered) == 1:
        return ordered[0]


    position = (
        (len(ordered) - 1)
        * percentile_value
    )


    lower = int(
        position
    )

    upper = min(
        lower + 1,
        len(ordered) - 1
    )


    fraction = (
        position - lower
    )


    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def summarize_pair(
    codigo,
    upstream_events,
    barcelos_events
):

    matches = match_events(
        codigo,
        upstream_events,
        barcelos_events
    )


    lags = [
        match[
            "defasagem_h"
        ]
        for match in matches
    ]


    total_upstream = len(
        upstream_events
    )


    matched_count = len(
        matches
    )


    if total_upstream:

        match_rate = (
            matched_count
            / total_upstream
        )

    else:

        match_rate = 0


    result = {
        "origem":
            codigo,

        "nome_origem":
            ESTACOES[
                codigo
            ],

        "destino":
            BARCELOS,

        "nome_destino":
            "Barcelos",

        "eventos_montante":
            total_upstream,

        "eventos_barcelos":
            len(
                barcelos_events
            ),

        "eventos_correspondentes":
            matched_count,

        "taxa_correspondencia":
            round(
                match_rate,
                3
            ),

        "eventos":
            matches,
    }


    if not lags:

        result.update(
            {
                "mediana_h":
                    None,

                "mediana_dias":
                    None,

                "q25_h":
                    None,

                "q75_h":
                    None,

                "min_h":
                    None,

                "max_h":
                    None,
            }
        )

        return result


    median = statistics.median(
        lags
    )


    q25 = percentile(
        lags,
        0.25
    )


    q75 = percentile(
        lags,
        0.75
    )


    result.update(
        {
            "mediana_h":
                round(
                    median,
                    1
                ),

            "mediana_dias":
                round(
                    median / 24,
                    2
                ),

            "q25_h":
                round(
                    q25,
                    1
                ),

            "q75_h":
                round(
                    q75,
                    1
                ),

            "q25_dias":
                round(
                    q25 / 24,
                    2
                ),

            "q75_dias":
                round(
                    q75 / 24,
                    2
                ),

            "min_h":
                round(
                    min(lags),
                    1
                ),

            "max_h":
                round(
                    max(lags),
                    1
                ),

            "min_dias":
                round(
                    min(lags) / 24,
                    2
                ),

            "max_dias":
                round(
                    max(lags) / 24,
                    2
                ),
        }
    )


    return result


# ==========================================================
# COBERTURA
# ==========================================================

def coverage(
    history
):

    result = {}


    for codigo, station_series in (
        history.items()
    ):

        timestamps = sorted(
            station_series.keys()
        )


        if not timestamps:
            continue


        result[
            codigo
        ] = {
            "nome":
                ESTACOES[
                    codigo
                ],

            "inicio":
                timestamps[0]
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "fim":
                timestamps[-1]
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "registros":
                len(
                    timestamps
                ),
        }


    return result


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    history = load_history()


    events_by_station = {}


    for codigo in ESTACOES:

        changes = (
            build_24h_changes(
                history[
                    codigo
                ]
            )
        )


        events = (
            detect_rise_events(
                changes
            )
        )


        events_by_station[
            codigo
        ] = events


        print()
        print(
            ESTACOES[
                codigo
            ],
            "- eventos de alta:",
            len(events)
        )


    barcelos_events = (
        events_by_station[
            BARCELOS
        ]
    )


    pairs = []


    for codigo in [
        "14420000",
        "14330000",
        "14280001",
        "14110000",
    ]:

        summary = (
            summarize_pair(
                codigo,
                events_by_station[
                    codigo
                ],
                barcelos_events
            )
        )


        pairs.append(
            summary
        )


    output = {

        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            "experimental",

        "metodo":
            (
                "Detecção de início de alta "
                "sustentada com variação de "
                "24 horas, amostragem a cada "
                "6 horas e casamento temporal "
                "entre eventos de montante "
                "e Barcelos."
            ),

        "parametros": {

            "alta_minima_24h_cm":
                MIN_RISE_24H_CM,

            "intervalo_amostragem_h":
                SAMPLE_INTERVAL_HOURS,

            "confirmacoes":
                CONFIRMATION_POINTS,

            "separacao_eventos_h":
                MIN_EVENT_SEPARATION_HOURS,
        },

        "cobertura":
            coverage(
                history
            ),

        "pares":
            pairs,
    }


    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")


    print()
    print(
        "===================================="
    )

    print(
        "ANÁLISE DE EVENTOS"
    )

    print(
        "===================================="
    )


    for pair in pairs:

        print()
        print(
            pair[
                "nome_origem"
            ],
            "→ Barcelos"
        )

        print(
            "Eventos montante:",
            pair[
                "eventos_montante"
            ]
        )

        print(
            "Correspondentes:",
            pair[
                "eventos_correspondentes"
            ]
        )

        print(
            "Taxa:",
            pair[
                "taxa_correspondencia"
            ]
        )

        print(
            "Mediana:",
            pair.get(
                "mediana_h"
            ),
            "h /",
            pair.get(
                "mediana_dias"
            ),
            "dias"
        )

        print(
            "Faixa central:",
            pair.get(
                "q25_dias"
            ),
            "a",
            pair.get(
                "q75_dias"
            ),
            "dias"
        )

        print(
            "Mínimo / máximo:",
            pair.get(
                "min_dias"
            ),
            "/",
            pair.get(
                "max_dias"
            ),
            "dias"
        )


    print()
    print(
        "Arquivo gerado:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
