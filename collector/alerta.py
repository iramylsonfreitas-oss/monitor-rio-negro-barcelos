import csv
import json

from datetime import datetime, timedelta, timezone
from pathlib import Path


# ==========================================================
# ARQUIVOS
# ==========================================================

HISTORY_FILE = Path(
    "data/history/hourly.csv"
)

STATIONS_FILE = Path(
    "data/estacoes.json"
)

EVENTS_FILE = Path(
    "data/eventos_propagacao_v2.json"
)

OUTPUT_FILE = Path(
    "data/alerta.json"
)


# ==========================================================
# ESTAÇÕES
# ==========================================================

CURICURIARI = "14330000"
SERRINHA = "14420000"
BARCELOS = "14480002"


# ==========================================================
# CRITÉRIOS DO DETECTOR V2
# ==========================================================

MIN_RISE_24H_CM = 3.0

RESET_RISE_24H_CM = 1.0

SAMPLE_INTERVAL_HOURS = 6

START_CONFIRMATION_POINTS = 3

END_CONFIRMATION_POINTS = 4


# ==========================================================
# FUNÇÕES AUXILIARES
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


def number(value):

    if value is None:
        return None

    try:

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return None


# ==========================================================
# ESTAÇÕES ATUAIS
# ==========================================================

def load_stations():

    if not STATIONS_FILE.exists():

        raise RuntimeError(
            "data/estacoes.json "
            "não encontrado."
        )


    with STATIONS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )


    return {
        station[
            "estacao"
        ]: station

        for station in data.get(
            "estacoes",
            []
        )
    }


# ==========================================================
# HISTÓRICO DE SERRINHA
# ==========================================================

def load_serrinha_history():

    if not HISTORY_FILE.exists():

        raise RuntimeError(
            "data/history/hourly.csv "
            "não encontrado."
        )


    series = {}


    with HISTORY_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file
        )


        for row in reader:

            if (
                row.get(
                    "estacao"
                )
                != SERRINHA
            ):

                continue


            timestamp = parse_datetime(
                row[
                    "hora_manaus"
                ]
            )


            level = float(
                row[
                    "nivel_cm"
                ]
            )


            series[
                timestamp
            ] = level


    return series


# ==========================================================
# ESTATÍSTICA HISTÓRICA V2
# ==========================================================

def load_historical_statistics():

    if not EVENTS_FILE.exists():

        return {
            "disponivel":
                False
        }


    with EVENTS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )


    pair = next(
        (
            item

            for item in data.get(
                "pares",
                []
            )

            if item.get(
                "origem"
            ) == SERRINHA
        ),
        None
    )


    if not pair:

        return {
            "disponivel":
                False
        }


    return {
        "disponivel":
            True,

        "eventos_serrinha":
            pair.get(
                "eventos_montante"
            ),

        "eventos_barcelos":
            pair.get(
                "eventos_barcelos"
            ),

        "eventos_correspondentes":
            pair.get(
                "eventos_correspondentes"
            ),

        "taxa_correspondencia":
            pair.get(
                "taxa_correspondencia"
            ),

        "mediana_dias":
            pair.get(
                "mediana_dias"
            ),

        "q25_dias":
            pair.get(
                "q25_dias"
            ),

        "q75_dias":
            pair.get(
                "q75_dias"
            ),

        "min_dias":
            pair.get(
                "min_dias"
            ),

        "max_dias":
            pair.get(
                "max_dias"
            ),
    }


# ==========================================================
# VARIAÇÕES DE 24 HORAS DE SERRINHA
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


        previous = (
            timestamp
            - timedelta(
                hours=24
            )
        )


        if (
            previous
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
                previous
            ]
        )


    return changes


# ==========================================================
# EVENTO ATUAL DE SERRINHA
# ==========================================================

def detect_current_serrinha_event(
    changes
):

    timestamps = sorted(
        changes.keys()
    )


    active = False

    current_event = None

    end_counter = 0


    for timestamp in timestamps:

        value = changes[
            timestamp
        ]


        # --------------------------------------------------
        # FORA DE EVENTO
        # --------------------------------------------------

        if not active:

            if (
                value
                < MIN_RISE_24H_CM
            ):

                continue


            confirmation_values = []

            valid = True


            for offset in range(
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


                expected_value = (
                    changes.get(
                        expected_time
                    )
                )


                if (
                    expected_value is None
                    or expected_value
                    < MIN_RISE_24H_CM
                ):

                    valid = False

                    break


                confirmation_values.append(
                    expected_value
                )


            if valid:

                active = True

                end_counter = 0


                current_event = {
                    "inicio":
                        timestamp,

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

                active = False

                current_event = None

                end_counter = 0


    return (
        active,
        current_event
    )


# ==========================================================
# ÚLTIMAS AMOSTRAS DE SERRINHA
# ==========================================================

def latest_serrinha_samples(
    changes,
    quantity=6
):

    timestamps = sorted(
        changes.keys()
    )


    selected = (
        timestamps[
            -quantity:
        ]
    )


    return [
        {
            "hora_manaus":
                format_datetime(
                    timestamp
                ),

            "variacao_24h_cm":
                round(
                    changes[
                        timestamp
                    ],
                    1
                ),
        }

        for timestamp in selected
    ]


# ==========================================================
# JANELA HISTÓRICA
# ==========================================================

def build_historical_window(
    event,
    historical
):

    if (
        not event
        or not historical.get(
            "disponivel"
        )
    ):

        return {
            "aplicavel":
                False
        }


    start = event[
        "inicio"
    ]


    q25 = number(
        historical.get(
            "q25_dias"
        )
    )

    median = number(
        historical.get(
            "mediana_dias"
        )
    )

    q75 = number(
        historical.get(
            "q75_dias"
        )
    )


    if (
        q25 is None
        or median is None
        or q75 is None
    ):

        return {
            "aplicavel":
                False
        }


    return {
        "aplicavel":
            True,

        "referencia":
            (
                "Intervalo histórico observado "
                "entre o início de eventos "
                "correspondentes em Serrinha "
                "e Barcelos."
            ),

        "inicio_evento_serrinha_manaus":
            format_datetime(
                start
            ),

        "inicio_janela_manaus":
            format_datetime(
                start
                + timedelta(
                    days=q25
                )
            ),

        "mediana_manaus":
            format_datetime(
                start
                + timedelta(
                    days=median
                )
            ),

        "fim_janela_manaus":
            format_datetime(
                start
                + timedelta(
                    days=q75
                )
            ),

        "inicio_dias":
            q25,

        "mediana_dias":
            median,

        "fim_dias":
            q75,

        "aviso":
            (
                "Janela histórica, não previsão. "
                "Nem todo evento de Serrinha "
                "produziu posteriormente um evento "
                "detectável em Barcelos."
            ),
    }


# ==========================================================
# SNAPSHOT
# ==========================================================

def station_snapshot(
    station
):

    if not station:

        return None


    return {
        "nome":
            station.get(
                "nome"
            ),

        "nivel_m":
            station.get(
                "nivel_m"
            ),

        "variacao_6h_cm":
            station.get(
                "variacao_6h_cm"
            ),

        "variacao_24h_cm":
            station.get(
                "variacao_24h_cm"
            ),

        "variacao_72h_cm":
            station.get(
                "variacao_72h_cm"
            ),

        "variacao_7d_cm":
            station.get(
                "variacao_7d_cm"
            ),

        "tendencia":
            station.get(
                "tendencia"
            ),

        "data_medicao_manaus":
            station.get(
                "data_medicao_manaus"
            ),
    }


# ==========================================================
# CLASSIFICAÇÃO DO ALERTA
# ==========================================================

def classify(
    stations,
    event_active
):

    serrinha = stations.get(
        SERRINHA,
        {}
    )

    curicuriari = stations.get(
        CURICURIARI,
        {}
    )

    barcelos = stations.get(
        BARCELOS,
        {}
    )


    s24 = number(
        serrinha.get(
            "variacao_24h_cm"
        )
    )

    s72 = number(
        serrinha.get(
            "variacao_72h_cm"
        )
    )

    c72 = number(
        curicuriari.get(
            "variacao_72h_cm"
        )
    )

    b24 = number(
        barcelos.get(
            "variacao_24h_cm"
        )
    )

    b72 = number(
        barcelos.get(
            "variacao_72h_cm"
        )
    )


    reasons = []


    # ======================================================
    # NÍVEL 2
    # ======================================================

    if event_active:

        reasons.append(
            (
                "Serrinha atende ao critério "
                "de alta sustentada."
            )
        )


        if (
            b24 is not None
            and b24 > 0
        ):

            reasons.append(
                (
                    "Barcelos já apresenta "
                    "variação positiva em 24 h."
                )
            )


        return {
            "nivel":
                2,

            "status":
                "alta_confirmada_montante",

            "rotulo":
                "ALTA CONFIRMADA EM SERRINHA",

            "titulo":
                (
                    "Evento de alta confirmado "
                    "a montante"
                ),

            "mensagem":
                (
                    "Serrinha atende ao critério "
                    "de alta sustentada. "
                    "A janela histórica de resposta "
                    "de Barcelos deve ser acompanhada."
                ),

            "motivos":
                reasons,
        }


    # ======================================================
    # NÍVEL 1
    # ======================================================

    condition_1 = (
        s24 is not None
        and s72 is not None
        and b24 is not None
        and s24 > 0
        and s72 > 0
        and b24 <= 0
    )


    condition_2 = (
        s72 is not None
        and c72 is not None
        and b72 is not None
        and s72 >= 3
        and c72 > 0
        and b72 < 0
    )


    if (
        condition_1
        or condition_2
    ):

        if (
            s24 is not None
            and s24 > 0
        ):

            reasons.append(
                (
                    "Serrinha apresenta "
                    f"{s24:+.1f} cm em 24 h."
                )
            )


        if (
            s72 is not None
            and s72 > 0
        ):

            reasons.append(
                (
                    "Serrinha acumula "
                    f"{s72:+.1f} cm em 72 h."
                )
            )


        if (
            c72 is not None
            and c72 > 0
        ):

            reasons.append(
                (
                    "Curicuriari acumula "
                    f"{c72:+.1f} cm em 72 h."
                )
            )


        if (
            b72 is not None
            and b72 < 0
        ):

            reasons.append(
                (
                    "Barcelos ainda acumula "
                    f"{b72:+.1f} cm em 72 h."
                )
            )


        return {
            "nivel":
                1,

            "status":
                "observacao",

            "rotulo":
                "EM OBSERVAÇÃO",

            "titulo":
                (
                    "Mudança a montante "
                    "em acompanhamento"
                ),

            "mensagem":
                (
                    "Há sinais de elevação "
                    "a montante, mas Serrinha "
                    "ainda não atende ao critério "
                    "de alta sustentada usado "
                    "pelo detector histórico."
                ),

            "motivos":
                reasons,
        }


    # ======================================================
    # NÍVEL 0
    # ======================================================

    return {
        "nivel":
            0,

        "status":
            "sem_sinal",

        "rotulo":
            "SEM SINAL",

        "titulo":
            (
                "Sem sinal de alta "
                "confirmada a montante"
            ),

        "mensagem":
            (
                "Os critérios atuais não indicam "
                "um evento de alta confirmado "
                "em Serrinha."
            ),

        "motivos":
            reasons,
    }


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    stations = load_stations()

    history = (
        load_serrinha_history()
    )

    historical = (
        load_historical_statistics()
    )


    changes = (
        build_24h_changes(
            history
        )
    )


    event_active, event = (
        detect_current_serrinha_event(
            changes
        )
    )


    classification = (
        classify(
            stations,
            event_active
        )
    )


    historical_window = (
        build_historical_window(
            event
            if event_active
            else None,
            historical
        )
    )


    output = {
        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "timezone":
            "America/Manaus",

        "nivel":
            classification[
                "nivel"
            ],

        "status":
            classification[
                "status"
            ],

        "rotulo":
            classification[
                "rotulo"
            ],

        "titulo":
            classification[
                "titulo"
            ],

        "mensagem":
            classification[
                "mensagem"
            ],

        "motivos":
            classification[
                "motivos"
            ],

        "criterio_evento_serrinha": {
            "variacao_minima_24h_cm":
                MIN_RISE_24H_CM,

            "confirmacoes":
                START_CONFIRMATION_POINTS,

            "intervalo_confirmacoes_h":
                SAMPLE_INTERVAL_HOURS,

            "criterio_encerramento_24h_cm":
                RESET_RISE_24H_CM,

            "confirmacoes_encerramento":
                END_CONFIRMATION_POINTS,
        },

        "evento_serrinha": {
            "confirmado":
                event_active,

            "inicio_manaus":
                (
                    format_datetime(
                        event[
                            "inicio"
                        ]
                    )

                    if event_active
                    else None
                ),

            "variacao_inicial_cm":
                (
                    event.get(
                        "variacao_inicial_cm"
                    )

                    if event_active
                    else None
                ),

            "variacao_maxima_24h_cm":
                (
                    event.get(
                        "variacao_maxima_24h_cm"
                    )

                    if event_active
                    else None
                ),

            "confirmacoes_inicio":
                (
                    event.get(
                        "confirmacoes_inicio"
                    )

                    if event_active
                    else []
                ),
        },

        "ultimas_amostras_serrinha":
            latest_serrinha_samples(
                changes
            ),

        "historico_serrinha_barcelos":
            historical,

        "janela_historica":
            historical_window,

        "situacao_atual": {
            "curicuriari":
                station_snapshot(
                    stations.get(
                        CURICURIARI
                    )
                ),

            "serrinha":
                station_snapshot(
                    stations.get(
                        SERRINHA
                    )
                ),

            "barcelos":
                station_snapshot(
                    stations.get(
                        BARCELOS
                    )
                ),
        },

        "aviso":
            (
                "O alerta é experimental e utiliza "
                "relações históricas entre estações. "
                "Uma alta em Serrinha não garante "
                "uma alta posterior em Barcelos."
            ),
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

        file.write(
            "\n"
        )


    print()
    print(
        "===================================="
    )

    print(
        "MOTOR DE ALERTA"
    )

    print(
        "===================================="
    )

    print()

    print(
        "Status:",
        output[
            "rotulo"
        ]
    )

    print(
        "Nível:",
        output[
            "nivel"
        ]
    )

    print(
        "Título:",
        output[
            "titulo"
        ]
    )

    print()

    print(
        "Evento confirmado em Serrinha:",
        output[
            "evento_serrinha"
        ][
            "confirmado"
        ]
    )

    print()

    print(
        "Histórico Serrinha → Barcelos:"
    )

    print(
        "Eventos em Serrinha:",
        historical.get(
            "eventos_serrinha"
        )
    )

    print(
        "Correspondentes:",
        historical.get(
            "eventos_correspondentes"
        )
    )

    print(
        "Mediana:",
        historical.get(
            "mediana_dias"
        ),
        "dias"
    )

    print(
        "Faixa central:",
        historical.get(
            "q25_dias"
        ),
        "a",
        historical.get(
            "q75_dias"
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
