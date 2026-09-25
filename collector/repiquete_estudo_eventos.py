import json

from datetime import timedelta
from pathlib import Path
from statistics import median


from repiquete import (
    load_barcelos_history,
    build_checkpoints,
    number,
    parse_datetime,
    format_datetime,
)


# ==========================================================
# ARQUIVOS
# ==========================================================

SENSITIVITY_FILE = Path(
    "data/repiquete_sensibilidade.json"
)

OUTPUT_FILE = Path(
    "data/repiquete_estudo_eventos.json"
)


# ==========================================================
# HORIZONTES ANALISADOS
# ==========================================================

HORIZONS_HOURS = [
    6,
    12,
    18,
    24,
    48,
    72,
    96,
    168,
]


# ==========================================================
# FUNÇÕES BÁSICAS
# ==========================================================

def load_json(path):

    if not path.exists():

        raise RuntimeError(
            f"{path} não encontrado."
        )

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


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


def level_m(
    value_cm
):

    if value_cm is None:
        return None

    return round(
        float(value_cm) / 100,
        2
    )


def change_from(
    series,
    start_time,
    hours
):

    start_level = series.get(
        start_time
    )

    future_level = series.get(
        start_time
        + timedelta(
            hours=hours
        )
    )

    if (
        start_level is None
        or future_level is None
    ):

        return None

    return (
        future_level
        - start_level
    )


def average_rate(
    change_cm,
    hours
):

    if (
        change_cm is None
        or not hours
    ):

        return None

    return (
        change_cm
        / hours
    )


# ==========================================================
# CONFIGURAÇÃO ATUAL
# ==========================================================

def get_current_configuration(
    sensitivity
):

    configurations = (
        sensitivity.get(
            "configuracoes"
        )
        or []
    )

    for item in configurations:

        if item.get(
            "configuracao_atual"
        ):

            return item

    raise RuntimeError(
        "Configuração atual não encontrada "
        "em repiquete_sensibilidade.json."
    )


# ==========================================================
# CHECKPOINTS
# ==========================================================

def build_checkpoint_index(
    checkpoints
):

    return {
        item[
            "timestamp"
        ]: item

        for item
        in checkpoints
    }


def checkpoint_snapshot(
    checkpoint
):

    if not checkpoint:
        return None

    return {

        "nivel_m":
            level_m(
                number(
                    checkpoint.get(
                        "nivel_cm"
                    )
                )
            ),

        "variacao_6h_cm":
            round_or_none(
                checkpoint.get(
                    "variacao_6h_cm"
                )
            ),

        "variacao_24h_cm":
            round_or_none(
                checkpoint.get(
                    "variacao_24h_cm"
                )
            ),

        "variacao_72h_cm":
            round_or_none(
                checkpoint.get(
                    "variacao_72h_cm"
                )
            ),

        "variacao_7d_cm":
            round_or_none(
                checkpoint.get(
                    "variacao_7d_cm"
                )
            ),
    }


# ==========================================================
# TRAJETÓRIA APÓS O PRIMEIRO SINAL
# ==========================================================

def build_trajectory(
    series,
    checkpoint_index,
    signal_time
):

    trajectory = []

    signal_level = series.get(
        signal_time
    )

    for hours in HORIZONS_HOURS:

        timestamp = (
            signal_time
            + timedelta(
                hours=hours
            )
        )

        level = series.get(
            timestamp
        )

        change = change_from(
            series,
            signal_time,
            hours
        )

        checkpoint = (
            checkpoint_index.get(
                timestamp
            )
        )

        trajectory.append(
            {

                "horas_apos_sinal":
                    hours,

                "data_manaus":
                    format_datetime(
                        timestamp
                    ),

                "nivel_m":
                    level_m(
                        level
                    ),

                "ganho_desde_sinal_cm":
                    round_or_none(
                        change
                    ),

                "taxa_media_desde_sinal_cm_h":
                    round_or_none(
                        average_rate(
                            change,
                            hours
                        ),
                        3
                    ),

                "checkpoint":
                    checkpoint_snapshot(
                        checkpoint
                    ),
            }
        )

    return {
        "nivel_inicial_m":
            level_m(
                signal_level
            ),

        "pontos":
            trajectory,
    }


# ==========================================================
# PERSISTÊNCIA EM BLOCOS DE 6 HORAS
# ==========================================================

def block_persistence(
    checkpoint_index,
    signal_time,
    horizon_hours
):

    positive = 0
    neutral = 0
    negative = 0
    available = 0

    values = []

    for offset in range(
        6,
        horizon_hours + 1,
        6
    ):

        timestamp = (
            signal_time
            + timedelta(
                hours=offset
            )
        )

        checkpoint = (
            checkpoint_index.get(
                timestamp
            )
        )

        if not checkpoint:
            continue

        variation = number(
            checkpoint.get(
                "variacao_6h_cm"
            )
        )

        if variation is None:
            continue

        available += 1

        values.append(
            variation
        )

        if variation > 0:

            positive += 1

        elif variation < 0:

            negative += 1

        else:

            neutral += 1

    return {

        "horizonte_h":
            horizon_hours,

        "blocos_disponiveis":
            available,

        "blocos_positivos":
            positive,

        "blocos_neutros":
            neutral,

        "blocos_negativos":
            negative,

        "soma_variacoes_6h_cm":
            round_or_none(
                sum(values)
                if values
                else None
            ),

        "media_variacoes_6h_cm":
            round_or_none(
                (
                    sum(values)
                    / len(values)
                )
                if values
                else None,
                2
            ),
    }


# ==========================================================
# COMPORTAMENTO DA VARIAÇÃO DE 24 HORAS
# ==========================================================

def rise24_profile(
    checkpoint_index,
    signal_time,
    horizon_hours=24
):

    values = []

    points = []

    for offset in range(
        0,
        horizon_hours + 1,
        6
    ):

        timestamp = (
            signal_time
            + timedelta(
                hours=offset
            )
        )

        checkpoint = (
            checkpoint_index.get(
                timestamp
            )
        )

        if not checkpoint:
            continue

        rise_24h = number(
            checkpoint.get(
                "variacao_24h_cm"
            )
        )

        if rise_24h is None:
            continue

        values.append(
            rise_24h
        )

        points.append(
            {
                "horas_apos_sinal":
                    offset,

                "variacao_24h_cm":
                    round_or_none(
                        rise_24h
                    ),
            }
        )

    return {

        "pontos":
            points,

        "minimo_cm":
            round_or_none(
                min(values)
                if values
                else None
            ),

        "maximo_cm":
            round_or_none(
                max(values)
                if values
                else None
            ),

        "ultimo_cm":
            round_or_none(
                values[-1]
                if values
                else None
            ),
    }


# ==========================================================
# MARCADOR RETROSPECTIVO
# ==========================================================

def retrospective_marker(
    event
):

    max_gain = number(
        event.get(
            "ganho_maximo_apos_confirmacao_cm"
        )
    )

    gain_72h = number(
        event.get(
            "ganho_72h_apos_confirmacao_cm"
        )
    )

    weak_max_gain = (
        max_gain is not None
        and max_gain <= 2.0
    )

    weak_72h = (
        gain_72h is not None
        and gain_72h <= 0
    )

    if (
        weak_max_gain
        or weak_72h
    ):

        classification = (
            "fraco_pos_evento"
        )

    else:

        classification = (
            "continuidade_observada"
        )

    return {

        "classificacao":
            classification,

        "ganho_maximo_ate_2cm":
            weak_max_gain,

        "ganho_72h_nao_positivo":
            weak_72h,

        "observacao":
            (
                "Marcador retrospectivo usado apenas "
                "para estudo. Não deve ser usado "
                "diretamente em decisão em tempo real."
            ),
    }


# ==========================================================
# PROCURA VALOR EM UMA TRAJETÓRIA
# ==========================================================

def trajectory_value(
    trajectory,
    hours
):

    points = (
        trajectory.get(
            "pontos"
        )
        or []
    )

    for point in points:

        if (
            point.get(
                "horas_apos_sinal"
            )
            == hours
        ):

            return point.get(
                "ganho_desde_sinal_cm"
            )

    return None


# ==========================================================
# ANALISA EVENTO
# ==========================================================

def analyze_event(
    event,
    sequence,
    series,
    checkpoint_index
):

    signal_time = parse_datetime(
        event[
            "inicio_sinal_manaus"
        ]
    )

    confirmation_time = parse_datetime(
        event[
            "confirmado_em_manaus"
        ]
    )

    confirmation_delay_h = (
        confirmation_time
        - signal_time
    ).total_seconds() / 3600

    signal_checkpoint = (
        checkpoint_index.get(
            signal_time
        )
    )

    confirmation_checkpoint = (
        checkpoint_index.get(
            confirmation_time
        )
    )

    trajectory = build_trajectory(
        series,
        checkpoint_index,
        signal_time
    )

    persistence_24h = block_persistence(
        checkpoint_index,
        signal_time,
        24
    )

    persistence_48h = block_persistence(
        checkpoint_index,
        signal_time,
        48
    )

    persistence_72h = block_persistence(
        checkpoint_index,
        signal_time,
        72
    )

    marker = retrospective_marker(
        event
    )

    return {

        "evento":
            sequence,

        "inicio_sinal_manaus":
            format_datetime(
                signal_time
            ),

        "confirmado_em_manaus":
            format_datetime(
                confirmation_time
            ),

        "atraso_confirmacao_h":
            round_or_none(
                confirmation_delay_h
            ),

        "checkpoint_inicio":
            checkpoint_snapshot(
                signal_checkpoint
            ),

        "checkpoint_confirmacao":
            checkpoint_snapshot(
                confirmation_checkpoint
            ),

        "trajetoria":
            trajectory,

        "persistencia_24h":
            persistence_24h,

        "persistencia_48h":
            persistence_48h,

        "persistencia_72h":
            persistence_72h,

        "perfil_variacao_24h_primeiras_24h":
            rise24_profile(
                checkpoint_index,
                signal_time,
                24
            ),

        "resultado_pos_evento": {

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

            "duracao_confirmada_h":
                round_or_none(
                    event.get(
                        "duracao_confirmada_h"
                    )
                ),
        },

        "marcador_retrospectivo":
            marker,
    }


# ==========================================================
# RESUMO DOS GRUPOS
# ==========================================================

def summarize_group(
    events,
    classification
):

    group = [
        item
        for item
        in events
        if (
            item.get(
                "marcador_retrospectivo",
                {}
            ).get(
                "classificacao"
            )
            == classification
        )
    ]

    def values_from_trajectory(
        hours
    ):

        return [
            trajectory_value(
                item.get(
                    "trajetoria",
                    {}
                ),
                hours
            )
            for item
            in group
        ]

    return {

        "classificacao":
            classification,

        "eventos":
            len(
                group
            ),

        "mediana_ganho_desde_sinal_12h_cm":
            median_or_none(
                values_from_trajectory(
                    12
                )
            ),

        "mediana_ganho_desde_sinal_24h_cm":
            median_or_none(
                values_from_trajectory(
                    24
                )
            ),

        "mediana_ganho_desde_sinal_48h_cm":
            median_or_none(
                values_from_trajectory(
                    48
                )
            ),

        "mediana_ganho_desde_sinal_72h_cm":
            median_or_none(
                values_from_trajectory(
                    72
                )
            ),

        "mediana_ganho_desde_sinal_96h_cm":
            median_or_none(
                values_from_trajectory(
                    96
                )
            ),

        "mediana_ganho_desde_sinal_7d_cm":
            median_or_none(
                values_from_trajectory(
                    168
                )
            ),

        "mediana_blocos_6h_positivos_primeiras_24h":
            median_or_none(
                [
                    item.get(
                        "persistencia_24h",
                        {}
                    ).get(
                        "blocos_positivos"
                    )
                    for item
                    in group
                ]
            ),

        "mediana_blocos_6h_positivos_primeiras_48h":
            median_or_none(
                [
                    item.get(
                        "persistencia_48h",
                        {}
                    ).get(
                        "blocos_positivos"
                    )
                    for item
                    in group
                ]
            ),

        "mediana_max_variacao_24h_primeiras_24h_cm":
            median_or_none(
                [
                    item.get(
                        "perfil_variacao_24h_primeiras_24h",
                        {}
                    ).get(
                        "maximo_cm"
                    )
                    for item
                    in group
                ]
            ),
    }


# ==========================================================
# TEXTO PARA CONSOLE
# ==========================================================

def text_value(
    value
):

    if value is None:
        return "n/d"

    return str(
        value
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    sensitivity = load_json(
        SENSITIVITY_FILE
    )

    current = get_current_configuration(
        sensitivity
    )

    original_events = (
        current.get(
            "eventos"
        )
        or []
    )

    if not original_events:

        raise RuntimeError(
            "Nenhum evento encontrado "
            "na configuração atual."
        )

    series = load_barcelos_history()

    checkpoints = build_checkpoints(
        series
    )

    checkpoint_index = (
        build_checkpoint_index(
            checkpoints
        )
    )

    analyzed_events = []

    for sequence, event in enumerate(
        original_events,
        start=1
    ):

        analyzed_events.append(
            analyze_event(
                event,
                sequence,
                series,
                checkpoint_index
            )
        )

    output = {

        "metodologia": {

            "descricao":
                (
                    "Comparação retrospectiva dos eventos "
                    "detectados pela configuração atual "
                    "do detector de repiquete."
                ),

            "configuracao_analisada":
                current.get(
                    "id"
                ),

            "alta_minima_24h_cm":
                current.get(
                    "alta_minima_24h_cm"
                ),

            "confirmacoes_consecutivas":
                current.get(
                    "confirmacoes_consecutivas"
                ),

            "eventos_analisados":
                len(
                    analyzed_events
                ),

            "horizontes_apos_primeiro_sinal_h":
                HORIZONS_HOURS,

            "observacao_importante":
                (
                    "A separação entre evento fraco e "
                    "evento com continuidade usa o que "
                    "aconteceu depois do sinal e serve "
                    "somente para estudo retrospectivo. "
                    "Essas informações futuras não podem "
                    "ser usadas diretamente pelo detector "
                    "em operação."
                ),
        },

        "resumo_grupos": [

            summarize_group(
                analyzed_events,
                "fraco_pos_evento"
            ),

            summarize_group(
                analyzed_events,
                "continuidade_observada"
            ),
        ],

        "eventos":
            analyzed_events,
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

    print()
    print(
        "======================================"
    )
    print(
        "ESTUDO DOS EVENTOS DE REPIQUETE"
    )
    print(
        "======================================"
    )

    print(
        "Configuração:",
        current.get(
            "id"
        )
    )

    print(
        "Eventos:",
        len(
            analyzed_events
        )
    )

    print()

    for item in analyzed_events:

        marker = (
            item.get(
                "marcador_retrospectivo",
                {}
            ).get(
                "classificacao"
            )
        )

        trajectory = (
            item.get(
                "trajetoria"
            )
            or {}
        )

        print(
            (
                f"Evento {item.get('evento')} | "
                f"{item.get('inicio_sinal_manaus')} | "
                f"{marker} | "
                f"12h="
                f"{text_value(trajectory_value(trajectory, 12))} cm | "
                f"24h="
                f"{text_value(trajectory_value(trajectory, 24))} cm | "
                f"48h="
                f"{text_value(trajectory_value(trajectory, 48))} cm | "
                f"72h="
                f"{text_value(trajectory_value(trajectory, 72))} cm | "
                f"positivos 24h="
                f"{item.get('persistencia_24h', {}).get('blocos_positivos')}"
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
