import csv
import json
import statistics

from datetime import datetime, timedelta, timezone
from pathlib import Path


HISTORY_FILE = Path(
    "data/history/hourly.csv"
)

OUTPUT_FILE = Path(
    "data/eventos_propagacao_v2.json"
)


ESTACOES = {
    "14110000": "Cucuí",
    "14280001": "Taracuá",
    "14330000": "Curicuriari",
    "14420000": "Serrinha",
    "14480002": "Barcelos",
}


BARCELOS = "14480002"


# ==========================================================
# PARÂMETROS
# ==========================================================
#
# Um evento começa quando:
#
# 1. a variação de 24 h alcança +3 cm;
# 2. permanece >= +3 cm em 3 observações
#    consecutivas de 6 h;
#
# Depois disso o evento permanece ATIVO.
#
# Ele só termina quando:
#
# - a variação de 24 h cai para <= +1 cm;
# - e permanece assim por 4 observações
#   consecutivas de 6 h = 24 horas.
#
# Isso impede que uma longa fase de subida
# seja dividida artificialmente em vários eventos.
# ==========================================================


MIN_RISE_24H_CM = 3.0

RESET_RISE_24H_CM = 1.0

SAMPLE_INTERVAL_HOURS = 6

START_CONFIRMATION_POINTS = 3

END_CONFIRMATION_POINTS = 4


MIN_LAG_HOURS = {
    "14420000": 24,
    "14330000": 48,
    "14280001": 72,
    "14110000": 96,
}


MAX_LAG_HOURS = {
    "14420000": 192,
    "14330000": 288,
    "14280001": 384,
    "14110000": 480,
}


# ==========================================================
# DATAS
# ==========================================================

def parse_datetime(value):

    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S"
    )


def format_datetime(value):

    if value is None:
        return None

    return value.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ==========================================================
# HISTÓRICO
# ==========================================================

def load_history():

    if not HISTORY_FILE.exists():

        raise RuntimeError(
            "Arquivo data/history/hourly.csv "
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


            nivel_cm = float(
                row[
                    "nivel_cm"
                ]
            )


            series[
                codigo
            ][timestamp] = nivel_cm


    return series


# ==========================================================
# VARIAÇÃO DE 24 HORAS
# ==========================================================

def build_24h_changes(
    station_series
):

    changes = {}


    for timestamp in sorted(
        station_series.keys()
    ):

        if (
            timestamp.minute != 0
            or timestamp.second != 0
        ):
            continue


        if (
            timestamp.hour
            % SAMPLE_INTERVAL_HOURS
            != 0
        ):
            continue


        previous_time = (
            timestamp
            - timedelta(
                hours=24
            )
        )


        if (
            previous_time
            not in station_series
        ):
            continue


        changes[
            timestamp
        ] = (
            station_series[
                timestamp
            ]
            - station_series[
                previous_time
            ]
        )


    return changes


# ==========================================================
# DETECTOR V2
# ==========================================================

def detect_events_v2(
    changes
):

    timestamps = sorted(
        changes.keys()
    )


    events = []


    active = False

    current_event = None

    end_counter = 0


    index = 0


    while index < len(
        timestamps
    ):

        timestamp = (
            timestamps[
                index
            ]
        )

        value = (
            changes[
                timestamp
            ]
        )


        # --------------------------------------------------
        # NÃO ESTAMOS DENTRO DE UM EVENTO
        # --------------------------------------------------

        if not active:

            if (
                value
                >= MIN_RISE_24H_CM
            ):

                confirmation_times = [
                    timestamp
                ]

                confirmation_values = [
                    value
                ]


                valid_start = True


                for offset in range(
                    1,
                    START_CONFIRMATION_POINTS
                ):

                    expected_time = (
                        timestamp
                        + timedelta(
                            hours=
                                SAMPLE_INTERVAL_HOURS
                                * offset
                        )
                    )


                    next_value = (
                        changes.get(
                            expected_time
                        )
                    )


                    if (
                        next_value is None
                        or next_value
                        < MIN_RISE_24H_CM
                    ):

                        valid_start = False
                        break


                    confirmation_times.append(
                        expected_time
                    )

                    confirmation_values.append(
                        next_value
                    )


                if valid_start:

                    active = True

                    end_counter = 0


                    current_event = {
                        "inicio":
                            timestamp,

                        "fim":
                            None,

                        "variacao_inicial_cm":
                            round(
                                value,
                                1
                            ),

                        "variacao_maxima_24h_cm":
                            round(
                                max(
                                    confirmation_values
                                ),
                                1
                            ),

                        "confirmacoes_inicio":
                            [
                                round(
                                    item,
                                    1
                                )
                                for item
                                in confirmation_values
                            ],
                    }


        # --------------------------------------------------
        # EVENTO ATIVO
        # --------------------------------------------------

        else:

            current_event[
                "variacao_maxima_24h_cm"
            ] = max(
                current_event[
                    "variacao_maxima_24h_cm"
                ],
                round(
                    value,
                    1
                )
            )


            if (
                value
                <= RESET_RISE_24H_CM
            ):

                end_counter += 1

            else:

                end_counter = 0


            if (
                end_counter
                >= END_CONFIRMATION_POINTS
            ):

                first_low_time = (
                    timestamp
                    - timedelta(
                        hours=
                            SAMPLE_INTERVAL_HOURS
                            * (
                                END_CONFIRMATION_POINTS
                                - 1
                            )
                    )
                )


                current_event[
                    "fim"
                ] = first_low_time


                duration_hours = (
                    (
                        first_low_time
                        - current_event[
                            "inicio"
                        ]
                    )
                    .total_seconds()
                    / 3600
                )


                current_event[
                    "duracao_h"
                ] = round(
                    duration_hours,
                    1
                )


                current_event[
                    "duracao_dias"
                ] = round(
                    duration_hours
                    / 24,
                    2
                )


                events.append(
                    current_event
                )


                active = False

                current_event = None

                end_counter = 0


        index += 1


    # ------------------------------------------------------
    # EVENTO AINDA ATIVO NO FIM DA SÉRIE
    # ------------------------------------------------------

    if (
        active
        and current_event
        is not None
    ):

        current_event[
            "fim"
        ] = None

        current_event[
            "duracao_h"
        ] = None

        current_event[
            "duracao_dias"
        ] = None

        current_event[
            "aberto"
        ] = True

        events.append(
            current_event
        )


    return events


# ==========================================================
# CASAMENTO DOS EVENTOS
# ==========================================================

def match_events(
    codigo,
    upstream_events,
    barcelos_events
):

    minimum_lag = timedelta(
        hours=
            MIN_LAG_HOURS[
                codigo
            ]
    )


    maximum_lag = timedelta(
        hours=
            MAX_LAG_HOURS[
                codigo
            ]
    )


    matches = []

    used_barcelos = set()


    for upstream in upstream_events:

        upstream_start = (
            upstream[
                "inicio"
            ]
        )


        candidates = []


        for index, downstream in enumerate(
            barcelos_events
        ):

            if index in used_barcelos:
                continue


            downstream_start = (
                downstream[
                    "inicio"
                ]
            )


            lag = (
                downstream_start
                - upstream_start
            )


            if (
                lag >= minimum_lag
                and lag <= maximum_lag
            ):

                candidates.append(
                    (
                        lag,
                        index,
                        downstream
                    )
                )


        if not candidates:
            continue


        lag, index, downstream = min(
            candidates,
            key=lambda item:
                item[0]
        )


        used_barcelos.add(
            index
        )


        lag_hours = (
            lag.total_seconds()
            / 3600
        )


        matches.append(
            {
                "inicio_montante":
                    format_datetime(
                        upstream_start
                    ),

                "fim_montante":
                    format_datetime(
                        upstream.get(
                            "fim"
                        )
                    ),

                "inicio_barcelos":
                    format_datetime(
                        downstream[
                            "inicio"
                        ]
                    ),

                "fim_barcelos":
                    format_datetime(
                        downstream.get(
                            "fim"
                        )
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

                "variacao_inicial_montante_cm":
                    upstream.get(
                        "variacao_inicial_cm"
                    ),

                "variacao_maxima_montante_cm":
                    upstream.get(
                        "variacao_maxima_24h_cm"
                    ),

                "variacao_inicial_barcelos_cm":
                    downstream.get(
                        "variacao_inicial_cm"
                    ),

                "variacao_maxima_barcelos_cm":
                    downstream.get(
                        "variacao_maxima_24h_cm"
                    ),
            }
        )


    return matches


# ==========================================================
# ESTATÍSTICA
# ==========================================================

def percentile(
    values,
    probability
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
        * probability
    )


    lower = int(
        position
    )


    upper = min(
        lower + 1,
        len(ordered) - 1
    )


    fraction = (
        position
        - lower
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
        item[
            "defasagem_h"
        ]
        for item in matches
    ]


    total_upstream = len(
        upstream_events
    )


    matched = len(
        matches
    )


    if total_upstream:

        match_rate = (
            matched
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
            matched,

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

                "q25_dias":
                    None,

                "q75_dias":
                    None,

                "min_h":
                    None,

                "max_h":
                    None,

                "min_dias":
                    None,

                "max_dias":
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
                    min(lags)
                    / 24,
                    2
                ),

            "max_dias":
                round(
                    max(lags)
                    / 24,
                    2
                ),
        }
    )


    return result


# ==========================================================
# SERIALIZAÇÃO DOS EVENTOS
# ==========================================================

def serialize_event(
    event
):

    return {
        "inicio":
            format_datetime(
                event.get(
                    "inicio"
                )
            ),

        "fim":
            format_datetime(
                event.get(
                    "fim"
                )
            ),

        "duracao_h":
            event.get(
                "duracao_h"
            ),

        "duracao_dias":
            event.get(
                "duracao_dias"
            ),

        "variacao_inicial_cm":
            event.get(
                "variacao_inicial_cm"
            ),

        "variacao_maxima_24h_cm":
            event.get(
                "variacao_maxima_24h_cm"
            ),

        "aberto":
            event.get(
                "aberto",
                False
            ),
    }


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    history = load_history()


    events_by_station = {}


    print()
    print(
        "===================================="
    )

    print(
        "DETECTOR DE EVENTOS V2"
    )

    print(
        "===================================="
    )


    for codigo, nome in (
        ESTACOES.items()
    ):

        changes = build_24h_changes(
            history[
                codigo
            ]
        )


        events = detect_events_v2(
            changes
        )


        events_by_station[
            codigo
        ] = events


        print()
        print(
            nome,
            "- eventos independentes:",
            len(events)
        )


        for index, event in enumerate(
            events,
            start=1
        ):

            print(
                f"  {index}.",
                format_datetime(
                    event[
                        "inicio"
                    ]
                ),
                "até",
                format_datetime(
                    event.get(
                        "fim"
                    )
                ),
                "| máx. 24h:",
                event.get(
                    "variacao_maxima_24h_cm"
                ),
                "cm"
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

        pairs.append(
            summarize_pair(
                codigo,
                events_by_station[
                    codigo
                ],
                barcelos_events
            )
        )


    serialized_stations = {}


    for codigo, events in (
        events_by_station.items()
    ):

        serialized_stations[
            codigo
        ] = {
            "nome":
                ESTACOES[
                    codigo
                ],

            "quantidade":
                len(
                    events
                ),

            "eventos":
                [
                    serialize_event(
                        event
                    )
                    for event in events
                ],
        }


    output = {
        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "versao":
            2,

        "status":
            "experimental",

        "metodo":
            (
                "Detector por mudança de estado. "
                "Uma alta começa após três "
                "observações consecutivas com "
                "variação de 24 horas >= 3 cm "
                "e termina somente após quatro "
                "observações consecutivas com "
                "variação de 24 horas <= 1 cm."
            ),

        "parametros": {
            "alta_minima_24h_cm":
                MIN_RISE_24H_CM,

            "limite_encerramento_24h_cm":
                RESET_RISE_24H_CM,

            "intervalo_amostragem_h":
                SAMPLE_INTERVAL_HOURS,

            "confirmacoes_inicio":
                START_CONFIRMATION_POINTS,

            "confirmacoes_fim":
                END_CONFIRMATION_POINTS,
        },

        "eventos_por_estacao":
            serialized_stations,

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
        "PROPAGAÇÃO V2"
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
            "Eventos Barcelos:",
            pair[
                "eventos_barcelos"
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
        "===================================="
    )

    print(
        "SERRINHA → BARCELOS"
    )

    print(
        "===================================="
    )


    serrinha = next(
        pair
        for pair in pairs
        if pair[
            "origem"
        ] == "14420000"
    )


    for index, event in enumerate(
        serrinha[
            "eventos"
        ],
        start=1
    ):

        print()

        print(
            "Evento",
            index
        )

        print(
            "Serrinha:",
            event[
                "inicio_montante"
            ]
        )

        print(
            "Barcelos:",
            event[
                "inicio_barcelos"
            ]
        )

        print(
            "Defasagem:",
            event[
                "defasagem_h"
            ],
            "h |",
            event[
                "defasagem_dias"
            ],
            "dias"
        )

        print(
            "Máxima Serrinha:",
            event[
                "variacao_maxima_montante_cm"
            ],
            "cm/24h"
        )

        print(
            "Máxima Barcelos:",
            event[
                "variacao_maxima_barcelos_cm"
            ],
            "cm/24h"
        )


    print()
    print(
        "Arquivo gerado:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
