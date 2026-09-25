import json

from datetime import timedelta
from pathlib import Path
from statistics import median


from repiquete import (
    load_barcelos_history,
    build_checkpoints,
    number,
    format_datetime,
    PREVIOUS_DROP_7D_CM,
    PREVIOUS_DROP_72H_CM,
    SAMPLE_INTERVAL_HOURS,
    RESET_RISE_24H_CM,
    END_CONFIRMATION_POINTS,
)


# ==========================================================
# ARQUIVO
# ==========================================================

OUTPUT_FILE = Path(
    "data/repiquete_sensibilidade.json"
)


# ==========================================================
# CONFIGURAÇÕES TESTADAS
# ==========================================================

RISE_THRESHOLDS = [
    3.0,
    4.0,
    5.0,
]

CONFIRMATION_POINTS_OPTIONS = [
    2,
    3,
    4,
]


# ==========================================================
# FUNÇÕES BÁSICAS
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
# VAZANTE PRÉVIA
# ==========================================================

def had_previous_drop(
    record
):

    variation_7d = number(
        record.get(
            "variacao_7d_cm"
        )
    )

    variation_72h = number(
        record.get(
            "variacao_72h_cm"
        )
    )

    condition_7d = (
        variation_7d is not None
        and variation_7d
        <= PREVIOUS_DROP_7D_CM
    )

    condition_72h = (
        variation_72h is not None
        and variation_72h
        <= PREVIOUS_DROP_72H_CM
    )

    return (
        condition_7d
        or condition_72h
    )


# ==========================================================
# CONFIRMAÇÕES CONSECUTIVAS
# ==========================================================

def confirmation_records_for(
    record,
    by_time,
    rise_threshold,
    confirmation_points
):

    timestamp = record[
        "timestamp"
    ]

    records = []

    for offset in range(
        confirmation_points
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

        rise_24h = number(
            expected.get(
                "variacao_24h_cm"
            )
        )

        if (
            rise_24h is None
            or rise_24h
            < rise_threshold
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

    signal_time = (
        signal_record[
            "timestamp"
        ]
    )

    confirmation_record = (
        confirmation_records[-1]
    )

    confirmation_time = (
        confirmation_record[
            "timestamp"
        ]
    )

    signal_level = number(
        signal_record.get(
            "nivel_cm"
        )
    )

    confirmation_level = number(
        confirmation_record.get(
            "nivel_cm"
        )
    )

    confirmation_rises = [
        number(
            item.get(
                "variacao_24h_cm"
            )
        )
        for item
        in confirmation_records
    ]

    confirmation_rises = [
        value
        for value
        in confirmation_rises
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

        "nivel_pico_apos_confirmacao_cm":
            confirmation_level,

        "pico_apos_confirmacao_em":
            confirmation_time,

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
                    confirmation_rises
                )
                if confirmation_rises
                else None
            ),

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

        "confirmacoes_inicio":
            confirmation_records,
    }


# ==========================================================
# ATUALIZA EVENTO
# ==========================================================

def update_event(
    event,
    record
):

    timestamp = record[
        "timestamp"
    ]

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

    if (
        timestamp
        >= event[
            "confirmado_em"
        ]
        and level is not None
        and (
            event[
                "nivel_pico_apos_confirmacao_cm"
            ] is None
            or level
            > event[
                "nivel_pico_apos_confirmacao_cm"
            ]
        )
    ):

        event[
            "nivel_pico_apos_confirmacao_cm"
        ] = level

        event[
            "pico_apos_confirmacao_em"
        ] = timestamp


# ==========================================================
# FINALIZA EVENTO
# ==========================================================

def finish_event(
    event,
    record
):

    end_time = record[
        "timestamp"
    ]

    event[
        "fim"
    ] = end_time

    event[
        "ativo_no_fim_da_serie"
    ] = False

    event[
        "duracao_confirmada_h"
    ] = round(
        (
            end_time
            - event[
                "confirmado_em"
            ]
        ).total_seconds()
        / 3600,
        1
    )

    peak = (
        event[
            "nivel_pico_apos_confirmacao_cm"
        ]
    )

    confirmation_level = (
        event[
            "nivel_confirmacao_cm"
        ]
    )

    event[
        "ganho_maximo_apos_confirmacao_cm"
    ] = (
        peak
        - confirmation_level

        if (
            peak is not None
            and confirmation_level is not None
        )

        else None
    )

    return event


# ==========================================================
# FINALIZA EVENTO ABERTO
# ==========================================================

def finish_open_event(
    event
):

    event[
        "duracao_confirmada_h"
    ] = None

    peak = (
        event[
            "nivel_pico_apos_confirmacao_cm"
        ]
    )

    confirmation_level = (
        event[
            "nivel_confirmacao_cm"
        ]
    )

    event[
        "ganho_maximo_apos_confirmacao_cm"
    ] = (
        peak
        - confirmation_level

        if (
            peak is not None
            and confirmation_level is not None
        )

        else None
    )

    return event


# ==========================================================
# DETECTOR PARAMETRIZADO
# ==========================================================

def detect_events(
    checkpoints,
    series,
    rise_threshold,
    confirmation_points
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

    threshold_hits = 0

    for record in checkpoints:

        rise_24h = number(
            record.get(
                "variacao_24h_cm"
            )
        )

        if rise_24h is None:
            continue

        # ==============================================
        # FORA DE EVENTO
        # ==============================================

        if not active:

            if (
                rise_24h
                < rise_threshold
            ):

                continue

            if not had_previous_drop(
                record
            ):

                continue

            threshold_hits += 1

            confirmation_records = (
                confirmation_records_for(
                    record,
                    by_time,
                    rise_threshold,
                    confirmation_points
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

        # ==============================================
        # EVENTO ATIVO
        # ==============================================

        else:

            update_event(
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
        threshold_hits
    )


# ==========================================================
# EVENTO SERIALIZADO
# ==========================================================

def serialize_event(
    event,
    sequence
):

    confirmation_level = (
        event.get(
            "nivel_confirmacao_cm"
        )
    )

    peak_level = (
        event.get(
            "nivel_pico_apos_confirmacao_cm"
        )
    )

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
                )
            ),

        "nivel_confirmacao_m":
            (
                round(
                    confirmation_level
                    / 100,
                    2
                )
                if confirmation_level is not None
                else None
            ),

        "nivel_pico_apos_confirmacao_m":
            (
                round(
                    peak_level
                    / 100,
                    2
                )
                if peak_level is not None
                else None
            ),

        "pico_apos_confirmacao_em_manaus":
            format_datetime(
                event.get(
                    "pico_apos_confirmacao_em"
                )
            ),

        "queda_72h_inicio_cm":
            round_or_none(
                event.get(
                    "queda_72h_inicio_cm"
                )
            ),

        "queda_7d_inicio_cm":
            round_or_none(
                event.get(
                    "queda_7d_inicio_cm"
                )
            ),

        "variacao_24h_inicio_cm":
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

        "ganho_maximo_apos_confirmacao_cm":
            round_or_none(
                event.get(
                    "ganho_maximo_apos_confirmacao_cm"
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
    }


# ==========================================================
# RESUMO DA CONFIGURAÇÃO
# ==========================================================

def summarize_configuration(
    rise_threshold,
    confirmation_points,
    events,
    threshold_hits
):

    closed = [
        event
        for event
        in events
        if not event[
            "ativo_no_fim_da_serie"
        ]
    ]

    max_gains = [
        event.get(
            "ganho_maximo_apos_confirmacao_cm"
        )
        for event
        in events
    ]

    gains_24h = [
        event.get(
            "ganho_24h_apos_confirmacao_cm"
        )
        for event
        in events
    ]

    gains_48h = [
        event.get(
            "ganho_48h_apos_confirmacao_cm"
        )
        for event
        in events
    ]

    gains_72h = [
        event.get(
            "ganho_72h_apos_confirmacao_cm"
        )
        for event
        in events
    ]

    weak_max_gain = sum(
        1
        for event
        in events
        if (
            event.get(
                "ganho_maximo_apos_confirmacao_cm"
            )
            is not None
            and event.get(
                "ganho_maximo_apos_confirmacao_cm"
            )
            <= 2.0
        )
    )

    non_positive_72h = sum(
        1
        for event
        in events
        if (
            event.get(
                "ganho_72h_apos_confirmacao_cm"
            )
            is not None
            and event.get(
                "ganho_72h_apos_confirmacao_cm"
            )
            <= 0
        )
    )

    both_conditions = sum(
        1
        for event
        in events
        if (
            event.get(
                "ganho_maximo_apos_confirmacao_cm"
            )
            is not None
            and event.get(
                "ganho_maximo_apos_confirmacao_cm"
            )
            <= 2.0
            and event.get(
                "ganho_72h_apos_confirmacao_cm"
            )
            is not None
            and event.get(
                "ganho_72h_apos_confirmacao_cm"
            )
            <= 0
        )
    )

    return {

        "id":
            (
                f"alta_{int(rise_threshold)}"
                f"_conf_{confirmation_points}"
            ),

        "configuracao_atual":
            (
                rise_threshold == 3.0
                and confirmation_points == 3
            ),

        "alta_minima_24h_cm":
            rise_threshold,

        "confirmacoes_consecutivas":
            confirmation_points,

        "intervalo_h":
            SAMPLE_INTERVAL_HOURS,

        "atraso_minimo_confirmacao_h":
            (
                confirmation_points
                - 1
            )
            * SAMPLE_INTERVAL_HOURS,

        "ocorrencias_primeiro_limiar":
            threshold_hits,

        "eventos_confirmados":
            len(
                events
            ),

        "eventos_encerrados":
            len(
                closed
            ),

        "ganho_maximo_mediano_apos_confirmacao_cm":
            median_or_none(
                max_gains
            ),

        "ganho_mediano_24h_cm":
            median_or_none(
                gains_24h
            ),

        "ganho_mediano_48h_cm":
            median_or_none(
                gains_48h
            ),

        "ganho_mediano_72h_cm":
            median_or_none(
                gains_72h
            ),

        "duracao_mediana_h":
            median_or_none(
                [
                    event.get(
                        "duracao_confirmada_h"
                    )
                    for event
                    in closed
                ]
            ),

        "eventos_com_ganho_maximo_ate_2cm":
            weak_max_gain,

        "eventos_com_ganho_72h_nao_positivo":
            non_positive_72h,

        "eventos_com_ambas_as_condicoes":
            both_conditions,

        "eventos":
            [
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
            ],
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
            "foi encontrado."
        )

    results = []

    for rise_threshold in (
        RISE_THRESHOLDS
    ):

        for confirmation_points in (
            CONFIRMATION_POINTS_OPTIONS
        ):

            (
                events,
                threshold_hits
            ) = detect_events(
                checkpoints,
                series,
                rise_threshold,
                confirmation_points
            )

            summary = (
                summarize_configuration(
                    rise_threshold,
                    confirmation_points,
                    events,
                    threshold_hits
                )
            )

            results.append(
                summary
            )

    output = {

        "metodologia": {

            "descricao":
                (
                    "Teste exploratório de sensibilidade "
                    "do detector de mudança de tendência "
                    "em Barcelos."
                ),

            "periodo_inicio_manaus":
                format_datetime(
                    checkpoints[0][
                        "timestamp"
                    ]
                ),

            "periodo_fim_manaus":
                format_datetime(
                    checkpoints[-1][
                        "timestamp"
                    ]
                ),

            "checkpoints_analisados":
                len(
                    checkpoints
                ),

            "queda_previa_7d_cm_mantida":
                PREVIOUS_DROP_7D_CM,

            "queda_previa_72h_cm_mantida":
                PREVIOUS_DROP_72H_CM,

            "criterio_encerramento_24h_cm_mantido":
                RESET_RISE_24H_CM,

            "confirmacoes_encerramento_mantidas":
                END_CONFIRMATION_POINTS,

            "altas_testadas_24h_cm":
                RISE_THRESHOLDS,

            "confirmacoes_testadas":
                CONFIRMATION_POINTS_OPTIONS,

            "observacao":
                (
                    "O teste não escolhe uma configuração "
                    "vencedora. Ele compara o comportamento "
                    "histórico de cada combinação. "
                    "As métricas de ganho máximo <= 2 cm "
                    "e ganho em 72 h <= 0 são apenas "
                    "marcadores objetivos para identificar "
                    "eventos pequenos ou sem continuidade."
                ),
        },

        "configuracoes":
            results,
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
        "======================================"
    )

    print(
        "TESTE DE SENSIBILIDADE DO REPIQUETE"
    )

    print(
        "======================================"
    )

    print(
        "Período:",
        output[
            "metodologia"
        ][
            "periodo_inicio_manaus"
        ],
        "até",
        output[
            "metodologia"
        ][
            "periodo_fim_manaus"
        ],
    )

    print()

    for result in results:

        marker = (
            "  <-- ATUAL"
            if result[
                "configuracao_atual"
            ]
            else ""
        )

        print(
            (
                f"+{result['alta_minima_24h_cm']:.0f} cm/24h"
                f" | {result['confirmacoes_consecutivas']} confirmações"
                f" | eventos: {result['eventos_confirmados']}"
                f" | <=2 cm: "
                f"{result['eventos_com_ganho_maximo_ate_2cm']}"
                f" | 72h <=0: "
                f"{result['eventos_com_ganho_72h_nao_positivo']}"
                f"{marker}"
            )
        )

    print()

    print(
        "Saída:",
        OUTPUT_FILE
    )

    print(
        "======================================"
    )


if __name__ == "__main__":

    main()
