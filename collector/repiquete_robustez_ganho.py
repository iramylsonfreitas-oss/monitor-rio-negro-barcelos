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

STUDY_FILE = Path(
    "data/repiquete_estudo_eventos.json"
)

OUTPUT_FILE = Path(
    "data/repiquete_robustez_ganho.json"
)


# ==========================================================
# LIMITES TESTADOS
# ==========================================================

GAIN_THRESHOLDS = [

    {
        "id": "maior_que_0",
        "rotulo": "> 0 cm",
        "valor_cm": 0.0,
        "operador": "gt",
    },

    {
        "id": "minimo_0_5",
        "rotulo": "≥ 0,5 cm",
        "valor_cm": 0.5,
        "operador": "ge",
    },

    {
        "id": "minimo_1",
        "rotulo": "≥ 1 cm",
        "valor_cm": 1.0,
        "operador": "ge",
    },
]


# ==========================================================
# MARGENS DE ESTRESSE
# ==========================================================

STRESS_MARGINS_CM = [
    0.0,
    0.5,
    1.0,
]


# ==========================================================
# JANELAS DE ESPERA APÓS A CONFIRMAÇÃO BASE
# ==========================================================

EXTRA_WAIT_HOURS = [
    0,
    6,
    12,
    24,
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


def level_change(
    series,
    start_time,
    current_time
):

    start_level = series.get(
        start_time
    )

    current_level = series.get(
        current_time
    )

    if (
        start_level is None
        or current_level is None
    ):

        return None

    return (
        current_level
        - start_level
    )


# ==========================================================
# TESTE DO LIMIAR
# ==========================================================

def passes_threshold(
    adjusted_gain,
    threshold
):

    if adjusted_gain is None:
        return False

    value = float(
        threshold[
            "valor_cm"
        ]
    )

    operator = threshold[
        "operador"
    ]

    if operator == "gt":

        return (
            adjusted_gain > value
        )

    return (
        adjusted_gain >= value
    )


# ==========================================================
# CLASSIFICAÇÃO RETROSPECTIVA
# ==========================================================

def retrospective_class(
    event
):

    marker = (
        event.get(
            "marcador_retrospectivo"
        )
        or {}
    )

    return marker.get(
        "classificacao"
    )


# ==========================================================
# PROCURA A PRIMEIRA CONFIRMAÇÃO POSSÍVEL
# ==========================================================

def find_confirmation(
    event,
    series,
    threshold,
    stress_margin_cm,
    extra_wait_hours
):

    signal_time = parse_datetime(
        event[
            "inicio_sinal_manaus"
        ]
    )

    base_confirmation_time = (
        parse_datetime(
            event[
                "confirmado_em_manaus"
            ]
        )
    )

    last_time = (
        base_confirmation_time
        + timedelta(
            hours=extra_wait_hours
        )
    )

    current_time = (
        base_confirmation_time
    )

    attempts = []

    while (
        current_time
        <= last_time
    ):

        observed_gain = (
            level_change(
                series,
                signal_time,
                current_time
            )
        )

        adjusted_gain = (
            observed_gain
            - stress_margin_cm
            if observed_gain is not None
            else None
        )

        passed = passes_threshold(
            adjusted_gain,
            threshold
        )

        attempts.append(
            {

                "data_manaus":
                    format_datetime(
                        current_time
                    ),

                "horas_desde_sinal":
                    round(
                        (
                            current_time
                            - signal_time
                        ).total_seconds()
                        / 3600,
                        1
                    ),

                "espera_extra_h":
                    round(
                        (
                            current_time
                            - base_confirmation_time
                        ).total_seconds()
                        / 3600,
                        1
                    ),

                "ganho_observado_cm":
                    round_or_none(
                        observed_gain
                    ),

                "margem_estresse_cm":
                    stress_margin_cm,

                "ganho_ajustado_cm":
                    round_or_none(
                        adjusted_gain
                    ),

                "passou":
                    passed,
            }
        )

        if passed:

            return {

                "confirmado":
                    True,

                "confirmado_em_manaus":
                    format_datetime(
                        current_time
                    ),

                "horas_desde_sinal":
                    round(
                        (
                            current_time
                            - signal_time
                        ).total_seconds()
                        / 3600,
                        1
                    ),

                "espera_extra_h":
                    round(
                        (
                            current_time
                            - base_confirmation_time
                        ).total_seconds()
                        / 3600,
                        1
                    ),

                "ganho_observado_cm":
                    round_or_none(
                        observed_gain
                    ),

                "ganho_ajustado_cm":
                    round_or_none(
                        adjusted_gain
                    ),

                "tentativas":
                    attempts,
            }

        current_time += timedelta(
            hours=6
        )

    return {

        "confirmado":
            False,

        "confirmado_em_manaus":
            None,

        "horas_desde_sinal":
            None,

        "espera_extra_h":
            None,

        "ganho_observado_cm":
            None,

        "ganho_ajustado_cm":
            None,

        "tentativas":
            attempts,
    }


# ==========================================================
# ANALISA UMA CONFIGURAÇÃO
# ==========================================================

def analyze_configuration(
    events,
    series,
    threshold,
    stress_margin_cm,
    extra_wait_hours
):

    accepted = []

    rejected = []

    weak_accepted = []

    continuity_accepted = []

    weak_rejected = []

    continuity_rejected = []

    extra_waits = []

    for event in events:

        classification = (
            retrospective_class(
                event
            )
        )

        result = find_confirmation(
            event,
            series,
            threshold,
            stress_margin_cm,
            extra_wait_hours
        )

        record = {

            "evento":
                event.get(
                    "evento"
                ),

            "inicio_sinal_manaus":
                event.get(
                    "inicio_sinal_manaus"
                ),

            "confirmacao_base_manaus":
                event.get(
                    "confirmado_em_manaus"
                ),

            "classificacao_retrospectiva":
                classification,

            "confirmado":
                result[
                    "confirmado"
                ],

            "confirmado_em_manaus":
                result[
                    "confirmado_em_manaus"
                ],

            "horas_desde_sinal":
                result[
                    "horas_desde_sinal"
                ],

            "espera_extra_h":
                result[
                    "espera_extra_h"
                ],

            "ganho_observado_cm":
                result[
                    "ganho_observado_cm"
                ],

            "ganho_ajustado_cm":
                result[
                    "ganho_ajustado_cm"
                ],

            "tentativas":
                result[
                    "tentativas"
                ],
        }

        if result[
            "confirmado"
        ]:

            accepted.append(
                record
            )

            extra_waits.append(
                result[
                    "espera_extra_h"
                ]
            )

            if (
                classification
                == "fraco_pos_evento"
            ):

                weak_accepted.append(
                    record
                )

            elif (
                classification
                == "continuidade_observada"
            ):

                continuity_accepted.append(
                    record
                )

        else:

            rejected.append(
                record
            )

            if (
                classification
                == "fraco_pos_evento"
            ):

                weak_rejected.append(
                    record
                )

            elif (
                classification
                == "continuidade_observada"
            ):

                continuity_rejected.append(
                    record
                )

    total_weak = (
        len(
            weak_accepted
        )
        + len(
            weak_rejected
        )
    )

    total_continuity = (
        len(
            continuity_accepted
        )
        + len(
            continuity_rejected
        )
    )

    return {

        "id":
            (
                f"{threshold['id']}"
                f"_margem_{str(stress_margin_cm).replace('.', '_')}"
                f"_espera_{extra_wait_hours}h"
            ),

        "criterio_ganho":
            threshold[
                "rotulo"
            ],

        "valor_limiar_cm":
            threshold[
                "valor_cm"
            ],

        "operador":
            threshold[
                "operador"
            ],

        "margem_estresse_cm":
            stress_margin_cm,

        "espera_extra_maxima_h":
            extra_wait_hours,

        "eventos_totais":
            len(
                events
            ),

        "eventos_aceitos":
            len(
                accepted
            ),

        "eventos_rejeitados":
            len(
                rejected
            ),

        "eventos_fracos_totais":
            total_weak,

        "eventos_fracos_aceitos":
            len(
                weak_accepted
            ),

        "eventos_fracos_rejeitados":
            len(
                weak_rejected
            ),

        "eventos_continuidade_totais":
            total_continuity,

        "eventos_continuidade_aceitos":
            len(
                continuity_accepted
            ),

        "eventos_continuidade_rejeitados":
            len(
                continuity_rejected
            ),

        "elimina_todos_fracos":
            (
                len(
                    weak_accepted
                )
                == 0
            ),

        "preserva_todos_continuidade":
            (
                len(
                    continuity_rejected
                )
                == 0
            ),

        "separacao_observada_no_historico":
            (
                len(
                    weak_accepted
                )
                == 0
                and len(
                    continuity_rejected
                )
                == 0
            ),

        "mediana_espera_extra_h":
            median_or_none(
                extra_waits
            ),

        "aceitos":
            accepted,

        "rejeitados":
            rejected,
    }


# ==========================================================
# MAIN
# ==========================================================

def main():

    study = load_json(
        STUDY_FILE
    )

    events = (
        study.get(
            "eventos"
        )
        or []
    )

    if not events:

        raise RuntimeError(
            "Nenhum evento encontrado "
            "em repiquete_estudo_eventos.json."
        )

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

    for threshold in GAIN_THRESHOLDS:

        for stress_margin_cm in (
            STRESS_MARGINS_CM
        ):

            for extra_wait_hours in (
                EXTRA_WAIT_HOURS
            ):

                results.append(
                    analyze_configuration(
                        events,
                        series,
                        threshold,
                        stress_margin_cm,
                        extra_wait_hours
                    )
                )

    configurations_with_separation = [
        result
        for result
        in results
        if result[
            "separacao_observada_no_historico"
        ]
    ]

    output = {

        "metodologia": {

            "descricao":
                (
                    "Teste retrospectivo de robustez "
                    "do critério de ganho líquido na "
                    "confirmação do repiquete."
                ),

            "configuracao_base":
                (
                    study.get(
                        "metodologia",
                        {}
                    ).get(
                        "configuracao_analisada"
                    )
                ),

            "eventos_analisados":
                len(
                    events
                ),

            "limiares_testados":
                [
                    item[
                        "rotulo"
                    ]
                    for item
                    in GAIN_THRESHOLDS
                ],

            "margens_estresse_cm":
                STRESS_MARGINS_CM,

            "esperas_extras_h":
                EXTRA_WAIT_HOURS,

            "total_configuracoes":
                len(
                    results
                ),

            "observacao_margem":
                (
                    "A margem de estresse é uma "
                    "simulação analítica conservadora. "
                    "Ela não representa precisão oficial "
                    "ou erro declarado da estação ANA."
                ),

            "observacao_tempo_real":
                (
                    "Cada confirmação simulada utiliza "
                    "somente dados disponíveis até aquele "
                    "checkpoint. A classificação "
                    "fraco/continuidade é retrospectiva "
                    "e usada apenas para avaliar os "
                    "resultados históricos."
                ),
        },

        "resumo": {

            "configuracoes_testadas":
                len(
                    results
                ),

            "configuracoes_com_separacao_observada":
                len(
                    configurations_with_separation
                ),

            "ids_com_separacao_observada":
                [
                    item[
                        "id"
                    ]
                    for item
                    in configurations_with_separation
                ],
        },

        "resultados":
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
        "ROBUSTEZ DO GANHO NA CONFIRMACAO"
    )

    print(
        "======================================"
    )

    print(
        "Configuracoes testadas:",
        len(
            results
        )
    )

    print(
        "Com separacao observada:",
        len(
            configurations_with_separation
        )
    )

    print()

    for result in results:

        if not result[
            "separacao_observada_no_historico"
        ]:
            continue

        print(
            (
                f"{result['criterio_ganho']}"
                f" | margem="
                f"{result['margem_estresse_cm']} cm"
                f" | espera="
                f"{result['espera_extra_maxima_h']} h"
                f" | continuidade="
                f"{result['eventos_continuidade_aceitos']}"
                f"/"
                f"{result['eventos_continuidade_totais']}"
                f" | fracos aceitos="
                f"{result['eventos_fracos_aceitos']}"
            )
        )

    print()

    print(
        "Saida:",
        OUTPUT_FILE
    )

    print(
        "======================================"
    )


if __name__ == "__main__":
    main()
