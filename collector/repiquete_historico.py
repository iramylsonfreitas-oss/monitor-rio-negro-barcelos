import json

from collections import Counter
from datetime import timedelta
from pathlib import Path
from statistics import median


from repiquete import (
    load_barcelos_history,
    build_checkpoints,
    had_previous_drop,
    number,
    format_datetime,
    PREVIOUS_DROP_7D_CM,
    PREVIOUS_DROP_72H_CM,
    CONFIRMED_RISE_24H_CM,
    CONFIRMATION_POINTS,
    SAMPLE_INTERVAL_HOURS,
    RESET_RISE_24H_CM,
    END_CONFIRMATION_POINTS,
)


# ==========================================================
# ARQUIVO DE SAÍDA
# ==========================================================

OUTPUT_FILE = Path(
    "data/repiquete_backtest.json"
)


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def round_or_none(
    value,
    digits=1
):

    if value is None:
        return None

    try:

        return round(
            float(value),
            digits
        )

    except (
        TypeError,
        ValueError
    ):

        return None


def median_or_none(
    values,
    digits=1
):

    valid = [
        float(value)
        for value
        in values
        if value is not None
    ]

    if not valid:
        return None

    return round(
        median(valid),
        digits
    )


def future_change(
    series,
    timestamp,
    hours
):

    current = series.get(
        timestamp
    )

    future = series.get(
        timestamp
        + timedelta(
            hours=hours
        )
    )

    if (
        current is None
        or future is None
    ):

        return None

    return (
        future
        - current
    )


# ==========================================================
# CONFIRMAÇÃO DO EVENTO
# ==========================================================

def confirmation_records_for(
    record,
    by_time
):

    timestamp = record[
        "timestamp"
    ]

    records = []

    for offset in range(
        CONFIRMATION_POINTS
    ):

        expected_time = (
            timestamp
            + timedelta(
                hours=(
                    SAMPLE_INTERVAL_HOURS
                    * offset
                )
            )
        )

        expected = (
            by_time.get(
                expected_time
            )
        )

        if not expected:

            return None

        expected_rise = number(
            expected.get(
                "variacao_24h_cm"
            )
        )

        if (
            expected_rise is None
            or expected_rise
            < CONFIRMED_RISE_24H_CM
        ):

            return None

        records.append(
            expected
        )

    return records


# ==========================================================
# CRIA EVENTO
# ==========================================================

def create_event(
    signal_record,
    confirmation_records,
    series
):

    first_confirmation = (
        confirmation_records[0]
    )

    last_confirmation = (
        confirmation_records[-1]
    )

    peak_record = max(
        confirmation_records,
        key=lambda item:
            item["nivel_cm"]
    )

    signal_time = (
        signal_record[
            "timestamp"
        ]
    )

    confirmation_time = (
        last_confirmation[
            "timestamp"
        ]
    )

    signal_level = number(
        signal_record.get(
            "nivel_cm"
        )
    )

    confirmation_level = number(
        last_confirmation.get(
            "nivel_cm"
        )
    )

    peak_level = number(
        peak_record.get(
            "nivel_cm"
        )
    )

    variation_24h_values = [

        number(
            item.get(
                "variacao_24h_cm"
            )
        )

        for item
        in confirmation_records
    ]

    variation_24h_values = [

        value
        for value
        in variation_24h_values
        if value is not None
    ]

    return {

        "inicio_sinal":
            signal_time,

        "confirmado_em":
            confirmation_time,

        "fim":
            None,

        "ativo_no_fim_da_serie":
            True,

        "nivel_inicio_cm":
            signal_level,

        "nivel_confirmacao_cm":
            confirmation_level,

        "nivel_pico_cm":
            peak_level,

        "pico_em":
            peak_record[
                "timestamp"
            ],

        "queda_72h_inicio_cm":
            number(
                signal_record.get(
                    "variacao_72h_cm"
                )
            ),

        "queda_7d_inicio_cm":
            number(
                signal_record.get(
                    "variacao_7d_cm"
                )
            ),

        "variacao_24h_inicio_cm":
            number(
                signal_record.get(
                    "variacao_24h_cm"
                )
            ),

        "variacao_maxima_24h_cm":
            (
                max(
                    variation_24h_values
                )
                if variation_24h_values
                else None
            ),

        "confirmacoes_inicio":
            [

                {
                    "hora_manaus":
                        item[
                            "timestamp"
                        ],

                    "nivel_cm":
                        number(
                            item.get(
                                "nivel_cm"
                            )
                        ),

                    "variacao_24h_cm":
                        number(
                            item.get(
                                "variacao_24h_cm"
                            )
                        ),
                }

                for item
                in confirmation_records
            ],

        "ganho_24h_apos_confirmacao_cm":
            future_change(
                series,
                confirmation_time,
                24
            ),

        "ganho_48h_apos_confirmacao_cm":
            future_change(
                series,
                confirmation_time,
                48
            ),

        "ganho_72h_apos_confirmacao_cm":
            future_change(
                series,
                confirmation_time,
                72
            ),
    }


# ==========================================================
# ATUALIZA EVENTO ATIVO
# ==========================================================

def update_active_event(
    event,
    record
):

    level = number(
        record.get(
            "nivel_cm"
        )
    )

    rise_24h = number(
        record.get(
            "variacao_24h_cm"
        )
    )

    if (
        level is not None
        and (
            event[
                "nivel_pico_cm"
            ] is None
            or level
            > event[
                "nivel_pico_cm"
            ]
        )
    ):

        event[
            "nivel_pico_cm"
        ] = level

        event[
            "pico_em"
        ] = record[
            "timestamp"
        ]

    if (
        rise_24h is not None
        and (
            event[
                "variacao_maxima_24h_cm"
            ] is None
            or rise_24h
            > event[
                "variacao_maxima_24h_cm"
            ]
        )
    ):

        event[
            "variacao_maxima_24h_cm"
        ] = rise_24h


# ==========================================================
# FINALIZA EVENTO
# ==========================================================

def finish_event(
    event,
    end_record
):

    end_time = end_record[
        "timestamp"
    ]

    event[
        "fim"
    ] = end_time

    event[
        "ativo_no_fim_da_serie"
    ] = False

    confirmation_time = (
        event[
            "confirmado_em"
        ]
    )

    event[
        "duracao_confirmada_h"
    ] = round(
        (
            end_time
            - confirmation_time
        ).total_seconds()
        / 3600,
        1
    )

    start_level = (
        event[
            "nivel_inicio_cm"
        ]
    )

    confirmation_level = (
        event[
            "nivel_confirmacao_cm"
        ]
    )

    peak_level = (
        event[
            "nivel_pico_cm"
        ]
    )

    event[
        "ganho_maximo_desde_sinal_cm"
    ] = (
        peak_level
        - start_level

        if (
            peak_level is not None
            and start_level is not None
        )

        else None
    )

    event[
        "ganho_maximo_desde_confirmacao_cm"
    ] = (
        peak_level
        - confirmation_level

        if (
            peak_level is not None
            and confirmation_level is not None
        )

        else None
    )

    return event


# ==========================================================
# FINALIZA EVENTO AINDA ATIVO
# ==========================================================

def finish_open_event(
    event
):

    start_level = (
        event[
            "nivel_inicio_cm"
        ]
    )

    confirmation_level = (
        event[
            "nivel_confirmacao_cm"
        ]
    )

    peak_level = (
        event[
            "nivel_pico_cm"
        ]
    )

    event[
        "duracao_confirmada_h"
    ] = None

    event[
        "ganho_maximo_desde_sinal_cm"
    ] = (
        peak_level
        - start_level

        if (
            peak_level is not None
            and start_level is not None
        )

        else None
    )

    event[
        "ganho_maximo_desde_confirmacao_cm"
    ] = (
        peak_level
        - confirmation_level

        if (
            peak_level is not None
            and confirmation_level is not None
        )

        else None
    )

    return event


# ==========================================================
# BACKTEST
# ==========================================================

def detect_all_events(
    checkpoints,
    series
):

    by_time = {

        record[
            "timestamp"
        ]:
            record

        for record
        in checkpoints
    }

    events = []

    active = False

    current_event = None

    end_counter = 0

    raw_threshold_hits = 0

    for record in checkpoints:

        rise_24h = number(
            record.get(
                "variacao_24h_cm"
            )
        )

        if rise_24h is None:

            continue

        # ==================================================
        # FORA DE EVENTO
        # ==================================================

        if not active:

            if (
                rise_24h
                < CONFIRMED_RISE_24H_CM
            ):

                continue

            if not had_previous_drop(
                record
            ):

                continue

            raw_threshold_hits += 1

            confirmation_records = (
                confirmation_records_for(
                    record,
                    by_time
                )
            )

            if not confirmation_records:

                continue

            active = True

            end_counter = 0

            current_event = (
                create_event(
                    record,
                    confirmation_records,
                    series
                )
            )

        # ==================================================
        # EVENTO ATIVO
        # ==================================================

        else:

            update_active_event(
                current_event,
                record
            )

            if (
                rise_24h
                <= RESET_RISE_24H_CM
            ):

                end_counter += 1

            else:

                end_counter = 0

            if (
                end_counter
                >= END_CONFIRMATION_POINTS
            ):

                events.append(
                    finish_event(
                        current_event,
                        record
                    )
                )

                active = False

                current_event = None

                end_counter = 0

    if (
        active
        and current_event
    ):

        events.append(
            finish_open_event(
                current_event
            )
        )

    return (
        events,
        raw_threshold_hits
    )


# ==========================================================
# SERIALIZA EVENTO
# ==========================================================

def serialize_event(
    event,
    sequence
):

    return {

        "evento":
            sequence,

        "inicio_sinal_manaus":
            format_datetime(
                event[
                    "inicio_sinal"
                ]
            ),

        "confirmado_em_manaus":
            format_datetime(
                event[
                    "confirmado_em"
                ]
            ),

        "atraso_confirmacao_h":
            round(
                (
                    event[
                        "confirmado_em"
                    ]
                    - event[
                        "inicio_sinal"
                    ]
                ).total_seconds()
                / 3600,
                1
            ),

        "fim_manaus":
            format_datetime(
                event.get(
                    "fim"
                )
            ),

        "ativo_no_fim_da_serie":
            event[
                "ativo_no_fim_da_serie"
            ],

        "duracao_confirmada_h":
            round_or_none(
                event.get(
                    "duracao_confirmada_h"
                ),
                1
            ),

        "nivel_inicio_m":
            (
                round(
                    event[
                        "nivel_inicio_cm"
                    ] / 100,
                    2
                )

                if event[
                    "nivel_inicio_cm"
                ] is not None

                else None
            ),

        "nivel_confirmacao_m":
            (
                round(
                    event[
                        "nivel_confirmacao_cm"
                    ] / 100,
                    2
                )

                if event[
                    "nivel_confirmacao_cm"
                ] is not None

                else None
            ),

        "nivel_pico_m":
            (
                round(
                    event[
                        "nivel_pico_cm"
                    ] / 100,
                    2
                )

                if event[
                    "nivel_pico_cm"
                ] is not None

                else None
            ),

        "pico_em_manaus":
            format_datetime(
                event.get(
                    "pico_em"
                )
            ),

        "queda_72h_no_inicio_cm":
            round_or_none(
                event.get(
                    "queda_72h_inicio_cm"
                )
            ),

        "queda_7d_no_inicio_cm":
            round_or_none(
                event.get(
                    "queda_7d_inicio_cm"
                )
            ),

        "variacao_24h_no_inicio_cm":
            round_or_none(
                event.get(
                    "variacao_24h_inicio_cm"
                )
            ),

        "variacao_maxima_24h_cm":
            round_or_none(
                event.get(
                    "variacao_maxima_24h_cm"
                )
            ),

        "ganho_maximo_desde_sinal_cm":
            round_or_none(
                event.get(
                    "ganho_maximo_desde_sinal_cm"
                )
            ),

        "ganho_maximo_desde_confirmacao_cm":
            round_or_none(
                event.get(
                    "ganho_maximo_desde_confirmacao_cm"
                )
            ),

        "ganho_24h_apos_confirmacao_cm":
            round_or_none(
                event.get(
                    "ganho_24h_apos_confirmacao_cm"
                )
            ),

        "ganho_48h_apos_confirmacao_cm":
            round_or_none(
                event.get(
                    "ganho_48h_apos_confirmacao_cm"
                )
            ),

        "ganho_72h_apos_confirmacao_cm":
            round_or_none(
                event.get(
                    "ganho_72h_apos_confirmacao_cm"
                )
            ),

        "confirmacoes_inicio":
            [

                {
                    "hora_manaus":
                        format_datetime(
                            item[
                                "hora_manaus"
                            ]
                        ),

                    "nivel_m":
                        (
                            round(
                                item[
                                    "nivel_cm"
                                ] / 100,
                                2
                            )

                            if item[
                                "nivel_cm"
                            ] is not None

                            else None
                        ),

                    "variacao_24h_cm":
                        round_or_none(
                            item[
                                "variacao_24h_cm"
                            ]
                        ),
                }

                for item
                in event[
                    "confirmacoes_inicio"
                ]
            ],
    }


# ==========================================================
# RESUMO
# ==========================================================

def build_summary(
    events,
    checkpoints,
    raw_threshold_hits
):

    by_year = Counter(

        event[
            "confirmado_em"
        ].year

        for event
        in events
    )

    closed = [

        event
        for event
        in events
        if not event[
            "ativo_no_fim_da_serie"
        ]
    ]

    active = [

        event
        for event
        in events
        if event[
            "ativo_no_fim_da_serie"
        ]
    ]

    first_time = (
        checkpoints[0][
            "timestamp"
        ]
        if checkpoints
        else None
    )

    last_time = (
        checkpoints[-1][
            "timestamp"
        ]
        if checkpoints
        else None
    )

    return {

        "periodo_inicio_manaus":
            format_datetime(
                first_time
            ),

        "periodo_fim_manaus":
            format_datetime(
                last_time
            ),

        "checkpoints_analisados":
            len(
                checkpoints
            ),

        "ocorrencias_primeiro_limiar":
            raw_threshold_hits,

        "eventos_confirmados":
            len(
                events
            ),

        "eventos_encerrados":
            len(
                closed
            ),

        "eventos_ativos_no_fim":
            len(
                active
            ),

        "eventos_por_ano":
            {
                str(year):
                    count

                for year,
                count
                in sorted(
                    by_year.items()
                )
            },

        "atraso_confirmacao_h":
            (
                CONFIRMATION_POINTS
                - 1
            )
            * SAMPLE_INTERVAL_HOURS,

        "duracao_mediana_confirmada_h":
            median_or_none(
                [
                    event.get(
                        "duracao_confirmada_h"
                    )

                    for event
                    in closed
                ],
                1
            ),

        "ganho_maximo_mediano_desde_confirmacao_cm":
            median_or_none(
                [
                    event.get(
                        "ganho_maximo_desde_confirmacao_cm"
                    )

                    for event
                    in events
                ],
                1
            ),

        "ganho_mediano_24h_apos_confirmacao_cm":
            median_or_none(
                [
                    event.get(
                        "ganho_24h_apos_confirmacao_cm"
                    )

                    for event
                    in events
                ],
                1
            ),

        "ganho_mediano_48h_apos_confirmacao_cm":
            median_or_none(
                [
                    event.get(
                        "ganho_48h_apos_confirmacao_cm"
                    )

                    for event
                    in events
                ],
                1
            ),

        "ganho_mediano_72h_apos_confirmacao_cm":
            median_or_none(
                [
                    event.get(
                        "ganho_72h_apos_confirmacao_cm"
                    )

                    for event
                    in events
                ],
                1
            ),

        "variacao_maxima_24h_mediana_cm":
            median_or_none(
                [
                    event.get(
                        "variacao_maxima_24h_cm"
                    )

                    for event
                    in events
                ],
                1
            ),
    }


# ==========================================================
# MAIN
# ==========================================================

def main():

    series = (
        load_barcelos_history()
    )

    checkpoints = (
        build_checkpoints(
            series
        )
    )

    if not checkpoints:

        raise RuntimeError(
            "Nenhum checkpoint histórico "
            "foi encontrado para Barcelos."
        )

    (
        events,
        raw_threshold_hits
    ) = detect_all_events(
        checkpoints,
        series
    )

    summary = (
        build_summary(
            events,
            checkpoints,
            raw_threshold_hits
        )
    )

    serialized_events = [

        serialize_event(
            event,
            index
        )

        for index,
        event
        in enumerate(
            events,
            start=1
        )
    ]

    output = {

        "metodologia": {

            "descricao":
                (
                    "Backtest do detector atual de "
                    "repiquete de Barcelos. "
                    "A lógica espelha os critérios "
                    "usados pelo detector em produção."
                ),

            "observacao_importante":
                (
                    "A queda prévia é avaliada no "
                    "primeiro checkpoint que já possui "
                    "alta mínima de 24 h. Esta é a "
                    "mesma lógica do detector atual e "
                    "será avaliada antes de qualquer "
                    "alteração metodológica."
                ),

            "queda_previa_7d_cm":
                PREVIOUS_DROP_7D_CM,

            "queda_previa_72h_cm":
                PREVIOUS_DROP_72H_CM,

            "alta_confirmacao_24h_cm":
                CONFIRMED_RISE_24H_CM,

            "confirmacoes":
                CONFIRMATION_POINTS,

            "intervalo_confirmacoes_h":
                SAMPLE_INTERVAL_HOURS,

            "criterio_encerramento_24h_cm":
                RESET_RISE_24H_CM,

            "confirmacoes_encerramento":
                END_CONFIRMATION_POINTS,

            "momento_real_da_confirmacao":
                (
                    "O evento só é considerado "
                    "conhecido pelo sistema no terceiro "
                    "checkpoint. Por isso o arquivo "
                    "separa inicio_sinal de confirmado_em."
                ),
        },

        "resumo":
            summary,

        "eventos":
            serialized_events,
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

    print(
        "\n"
        "======================================"
    )

    print(
        "BACKTEST DO DETECTOR DE REPIQUETE"
    )

    print(
        "======================================"
    )

    print(
        "Período:",
        summary[
            "periodo_inicio_manaus"
        ],
        "até",
        summary[
            "periodo_fim_manaus"
        ],
    )

    print(
        "Checkpoints analisados:",
        summary[
            "checkpoints_analisados"
        ],
    )

    print(
        "Eventos confirmados:",
        summary[
            "eventos_confirmados"
        ],
    )

    print(
        "Eventos por ano:",
        summary[
            "eventos_por_ano"
        ],
    )

    print(
        "Atraso mínimo de confirmação:",
        summary[
            "atraso_confirmacao_h"
        ],
        "h",
    )

    print(
        "Ganho mediano em 24 h após confirmação:",
        summary[
            "ganho_mediano_24h_apos_confirmacao_cm"
        ],
        "cm",
    )

    print(
        "Ganho mediano em 48 h após confirmação:",
        summary[
            "ganho_mediano_48h_apos_confirmacao_cm"
        ],
        "cm",
    )

    print(
        "Ganho mediano em 72 h após confirmação:",
        summary[
            "ganho_mediano_72h_apos_confirmacao_cm"
        ],
        "cm",
    )

    print(
        "Saída:",
        OUTPUT_FILE,
    )

    print(
        "======================================"
    )


if __name__ == "__main__":

    main()
