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
# SAÍDA
# ==========================================================

OUTPUT_FILE = Path(
    "data/repiquete_backtest_candidato.json"
)


# ==========================================================
# NOVO CRITÉRIO CANDIDATO
# ==========================================================

MIN_NET_GAIN_CONFIRMATION_CM = 1.0


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


def exact_consecutive(
    previous,
    current
):

    if previous is None:
        return True

    return (
        current["timestamp"]
        - previous["timestamp"]
        == timedelta(
            hours=SAMPLE_INTERVAL_HOURS
        )
    )


# ==========================================================
# CRIA EVENTO CONFIRMADO
# ==========================================================

def create_event(
    confirmation_window,
    series
):

    signal_record = (
        confirmation_window[0]
    )

    confirmation_record = (
        confirmation_window[-1]
    )

    signal_time = (
        signal_record[
            "timestamp"
        ]
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

    net_gain = (
        confirmation_level
        - signal_level
    )

    peak_record = max(
        confirmation_window,
        key=lambda item:
            number(
                item.get(
                    "nivel_cm"
                )
            )
    )

    variation_24h_values = [

        number(
            item.get(
                "variacao_24h_cm"
            )
        )

        for item
        in confirmation_window
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

        "ganho_liquido_confirmacao_cm":
            net_gain,

        "nivel_pico_cm":
            number(
                peak_record.get(
                    "nivel_cm"
                )
            ),

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
                in confirmation_window
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

def calculate_event_gains(
    event
):

    start_level = (
        event.get(
            "nivel_inicio_cm"
        )
    )

    confirmation_level = (
        event.get(
            "nivel_confirmacao_cm"
        )
    )

    peak_level = (
        event.get(
            "nivel_pico_cm"
        )
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


def finish_event(
    event,
    end_record
):

    end_time = (
        end_record[
            "timestamp"
        ]
    )

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

    calculate_event_gains(
        event
    )

    return event


def finish_open_event(
    event
):

    event[
        "duracao_confirmada_h"
    ] = None

    calculate_event_gains(
        event
    )

    return event


# ==========================================================
# DETECTOR CANDIDATO
# ==========================================================

def detect_candidate_events(
    checkpoints,
    series
):

    events = []

    active = False

    current_event = None

    end_counter = 0

    qualifying_streak = []

    base_windows_evaluated = 0

    rejected_by_net_gain = []

    for record in checkpoints:

        rise_24h = number(
            record.get(
                "variacao_24h_cm"
            )
        )

        # ==================================================
        # EVENTO ATIVO
        # ==================================================

        if active:

            if rise_24h is None:
                continue

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

                qualifying_streak = []

            continue

        # ==================================================
        # FORA DE EVENTO
        # ==================================================

        if (
            rise_24h is None
            or rise_24h
            < CONFIRMED_RISE_24H_CM
        ):

            qualifying_streak = []

            continue

        if (
            qualifying_streak
            and not exact_consecutive(
                qualifying_streak[-1],
                record
            )
        ):

            qualifying_streak = []

        qualifying_streak.append(
            record
        )

        if (
            len(
                qualifying_streak
            )
            < CONFIRMATION_POINTS
        ):

            continue

        confirmation_window = (
            qualifying_streak[
                -CONFIRMATION_POINTS:
            ]
        )

        signal_record = (
            confirmation_window[0]
        )

        confirmation_record = (
            confirmation_window[-1]
        )

        if not had_previous_drop(
            signal_record
        ):

            continue

        base_windows_evaluated += 1

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

        if (
            signal_level is None
            or confirmation_level is None
        ):

            continue

        net_gain = (
            confirmation_level
            - signal_level
        )

        if (
            net_gain
            < MIN_NET_GAIN_CONFIRMATION_CM
        ):

            rejected_by_net_gain.append(
                {

                    "inicio_sinal_manaus":
                        format_datetime(
                            signal_record[
                                "timestamp"
                            ]
                        ),

                    "avaliado_em_manaus":
                        format_datetime(
                            confirmation_record[
                                "timestamp"
                            ]
                        ),

                    "nivel_inicio_m":
                        round(
                            signal_level
                            / 100,
                            2
                        ),

                    "nivel_avaliacao_m":
                        round(
                            confirmation_level
                            / 100,
                            2
                        ),

                    "ganho_liquido_cm":
                        round(
                            net_gain,
                            1
                        ),

                    "variacao_24h_inicio_cm":
                        round_or_none(
                            signal_record.get(
                                "variacao_24h_cm"
                            )
                        ),

                    "variacao_72h_inicio_cm":
                        round_or_none(
                            signal_record.get(
                                "variacao_72h_cm"
                            )
                        ),

                    "variacao_7d_inicio_cm":
                        round_or_none(
                            signal_record.get(
                                "variacao_7d_cm"
                            )
                        ),
                }
            )

            continue

        current_event = (
            create_event(
                confirmation_window,
                series
            )
        )

        active = True

        end_counter = 0

        qualifying_streak = []

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
        base_windows_evaluated,
        rejected_by_net_gain
    )


# ==========================================================
# SERIALIZA EVENTOS
# ==========================================================

def serialize_event(
    event,
    sequence
):

    confirmations = []

    for item in event.get(
        "confirmacoes_inicio",
        []
    ):

        confirmations.append(
            {

                "hora_manaus":
                    format_datetime(
                        item.get(
                            "hora_manaus"
                        )
                    ),

                "nivel_m":
                    (
                        round(
                            item[
                                "nivel_cm"
                            ]
                            / 100,
                            2
                        )

                        if item.get(
                            "nivel_cm"
                        ) is not None

                        else None
                    ),

                "variacao_24h_cm":
                    round_or_none(
                        item.get(
                            "variacao_24h_cm"
                        )
                    ),
            }
        )

    return {

        "evento":
            sequence,

        "inicio_sinal_manaus":
            format_datetime(
                event.get(
                    "inicio_sinal"
                )
            ),

        "confirmado_em_manaus":
            format_datetime(
                event.get(
                    "confirmado_em"
                )
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

        "ganho_liquido_na_confirmacao_cm":
            round_or_none(
                event.get(
                    "ganho_liquido_confirmacao_cm"
                )
            ),

        "fim_manaus":
            format_datetime(
                event.get(
                    "fim"
                )
            ),

        "ativo_no_fim_da_serie":
            event.get(
                "ativo_no_fim_da_serie"
            ),

        "duracao_confirmada_h":
            round_or_none(
                event.get(
                    "duracao_confirmada_h"
                )
            ),

        "nivel_inicio_m":
            (
                round(
                    event[
                        "nivel_inicio_cm"
                    ]
                    / 100,
                    2
                )

                if event.get(
                    "nivel_inicio_cm"
                ) is not None

                else None
            ),

        "nivel_confirmacao_m":
            (
                round(
                    event[
                        "nivel_confirmacao_cm"
                    ]
                    / 100,
                    2
                )

                if event.get(
                    "nivel_confirmacao_cm"
                ) is not None

                else None
            ),

        "nivel_pico_m":
            (
                round(
                    event[
                        "nivel_pico_cm"
                    ]
                    / 100,
                    2
                )

                if event.get(
                    "nivel_pico_cm"
                ) is not None

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
            confirmations,
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
            "Nenhum checkpoint histórico encontrado."
        )

    (
        events,
        base_windows_evaluated,
        rejected_by_net_gain
    ) = detect_candidate_events(
        checkpoints,
        series
    )

    serialized_events = [

        serialize_event(
            event,
            index
        )

        for index, event
        in enumerate(
            events,
            start=1
        )
    ]

    events_by_year = Counter(

        event[
            "inicio_sinal"
        ].year

        for event
        in events
    )

    durations = [
        event.get(
            "duracao_confirmada_h"
        )
        for event
        in events
        if event.get(
            "duracao_confirmada_h"
        ) is not None
    ]

    maximum_gains = [
        event.get(
            "ganho_maximo_desde_confirmacao_cm"
        )
        for event
        in events
        if event.get(
            "ganho_maximo_desde_confirmacao_cm"
        ) is not None
    ]

    gains_24h = [
        event.get(
            "ganho_24h_apos_confirmacao_cm"
        )
        for event
        in events
        if event.get(
            "ganho_24h_apos_confirmacao_cm"
        ) is not None
    ]

    gains_48h = [
        event.get(
            "ganho_48h_apos_confirmacao_cm"
        )
        for event
        in events
        if event.get(
            "ganho_48h_apos_confirmacao_cm"
        ) is not None
    ]

    gains_72h = [
        event.get(
            "ganho_72h_apos_confirmacao_cm"
        )
        for event
        in events
        if event.get(
            "ganho_72h_apos_confirmacao_cm"
        ) is not None
    ]

    output = {

        "metodologia": {

            "descricao":
                (
                    "Backtest independente do detector "
                    "candidato em toda a série histórica "
                    "de Barcelos. Os eventos são detectados "
                    "novamente desde o início da série; "
                    "não são filtrados a partir dos seis "
                    "eventos do detector anterior."
                ),

            "queda_previa_7d_cm":
                PREVIOUS_DROP_7D_CM,

            "queda_previa_72h_cm":
                PREVIOUS_DROP_72H_CM,

            "alta_minima_24h_cm":
                CONFIRMED_RISE_24H_CM,

            "confirmacoes_consecutivas":
                CONFIRMATION_POINTS,

            "intervalo_checkpoints_h":
                SAMPLE_INTERVAL_HOURS,

            "ganho_liquido_minimo_confirmacao_cm":
                MIN_NET_GAIN_CONFIRMATION_CM,

            "criterio_encerramento_24h_cm":
                RESET_RISE_24H_CM,

            "confirmacoes_para_encerrar":
                END_CONFIRMATION_POINTS,

            "observacao":
                (
                    "A confirmação somente ocorre quando "
                    "os três checkpoints consecutivos "
                    "atendem ao limiar de alta de 24 h "
                    "e o nível no terceiro checkpoint está "
                    "pelo menos 1 cm acima do nível no "
                    "primeiro checkpoint do sinal."
                ),
        },

        "periodo": {

            "inicio_manaus":
                format_datetime(
                    checkpoints[0][
                        "timestamp"
                    ]
                ),

            "fim_manaus":
                format_datetime(
                    checkpoints[-1][
                        "timestamp"
                    ]
                ),

            "checkpoints_analisados":
                len(
                    checkpoints
                ),
        },

        "resumo": {

            "janelas_base_avaliadas":
                base_windows_evaluated,

            "janelas_rejeitadas_por_ganho_liquido":
                len(
                    rejected_by_net_gain
                ),

            "eventos_confirmados":
                len(
                    events
                ),

            "eventos_encerrados":
                sum(
                    1
                    for event
                    in events
                    if not event.get(
                        "ativo_no_fim_da_serie"
                    )
                ),

            "eventos_ativos_no_fim":
                sum(
                    1
                    for event
                    in events
                    if event.get(
                        "ativo_no_fim_da_serie"
                    )
                ),

            "eventos_por_ano":
                dict(
                    sorted(
                        events_by_year.items()
                    )
                ),

            "mediana_duracao_confirmada_h":
                median_or_none(
                    durations
                ),

            "mediana_ganho_maximo_apos_confirmacao_cm":
                median_or_none(
                    maximum_gains
                ),

            "mediana_ganho_24h_apos_confirmacao_cm":
                median_or_none(
                    gains_24h
                ),

            "mediana_ganho_48h_apos_confirmacao_cm":
                median_or_none(
                    gains_48h
                ),

            "mediana_ganho_72h_apos_confirmacao_cm":
                median_or_none(
                    gains_72h
                ),
        },

        "janelas_rejeitadas_por_ganho_liquido":
            rejected_by_net_gain,

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

    print()
    print(
        "======================================"
    )

    print(
        "BACKTEST DO DETECTOR CANDIDATO"
    )

    print(
        "======================================"
    )

    print(
        "Checkpoints analisados:",
        len(
            checkpoints
        )
    )

    print(
        "Janelas base avaliadas:",
        base_windows_evaluated
    )

    print(
        "Janelas rejeitadas pelo ganho:",
        len(
            rejected_by_net_gain
        )
    )

    print(
        "Eventos confirmados:",
        len(
            events
        )
    )

    print()

    for event in serialized_events:

        print(
            (
                f"Evento {event['evento']}"
                f" | sinal="
                f"{event['inicio_sinal_manaus']}"
                f" | confirmado="
                f"{event['confirmado_em_manaus']}"
                f" | ganho confirmacao="
                f"{event['ganho_liquido_na_confirmacao_cm']} cm"
                f" | +72h="
                f"{event['ganho_72h_apos_confirmacao_cm']} cm"
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
