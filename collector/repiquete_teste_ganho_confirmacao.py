import json

from pathlib import Path
from statistics import median


# ==========================================================
# ARQUIVOS
# ==========================================================

STUDY_FILE = Path(
    "data/repiquete_estudo_eventos.json"
)

OUTPUT_FILE = Path(
    "data/repiquete_teste_ganho_confirmacao.json"
)


# ==========================================================
# LIMIARES TESTADOS
# ==========================================================

THRESHOLDS = [

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

    {
        "id": "minimo_2",
        "rotulo": "≥ 2 cm",
        "valor_cm": 2.0,
        "operador": "ge",
    },

    {
        "id": "minimo_3",
        "rotulo": "≥ 3 cm",
        "valor_cm": 3.0,
        "operador": "ge",
    },
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


# ==========================================================
# GANHO ATÉ A CONFIRMAÇÃO
# ==========================================================

def confirmation_gain(
    event
):

    delay = event.get(
        "atraso_confirmacao_h"
    )

    trajectory = (
        event.get(
            "trajetoria"
        )
        or {}
    )

    points = (
        trajectory.get(
            "pontos"
        )
        or []
    )

    for point in points:

        hours = point.get(
            "horas_apos_sinal"
        )

        if (
            hours is not None
            and delay is not None
            and float(hours)
            == float(delay)
        ):

            return round_or_none(
                point.get(
                    "ganho_desde_sinal_cm"
                )
            )

    return None


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
# TESTE DO LIMIAR
# ==========================================================

def passes_threshold(
    gain,
    threshold
):

    if gain is None:
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
            gain > value
        )

    return (
        gain >= value
    )


# ==========================================================
# RESUMO DE UM LIMIAR
# ==========================================================

def analyze_threshold(
    events,
    threshold
):

    accepted = []

    rejected = []

    weak_accepted = []

    weak_rejected = []

    continuity_accepted = []

    continuity_rejected = []

    for event in events:

        gain = confirmation_gain(
            event
        )

        classification = (
            retrospective_class(
                event
            )
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

            "confirmado_em_manaus":
                event.get(
                    "confirmado_em_manaus"
                ),

            "ganho_liquido_na_confirmacao_cm":
                gain,

            "classificacao_retrospectiva":
                classification,
        }

        passed = passes_threshold(
            gain,
            threshold
        )

        record[
            "passaria_novo_criterio"
        ] = passed

        if passed:

            accepted.append(
                record
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

    total_weak = sum(
        1
        for event
        in events
        if (
            retrospective_class(
                event
            )
            == "fraco_pos_evento"
        )
    )

    total_continuity = sum(
        1
        for event
        in events
        if (
            retrospective_class(
                event
            )
            == "continuidade_observada"
        )
    )

    return {

        "id":
            threshold[
                "id"
            ],

        "rotulo":
            threshold[
                "rotulo"
            ],

        "valor_cm":
            threshold[
                "valor_cm"
            ],

        "operador":
            threshold[
                "operador"
            ],

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

        "eventos_com_continuidade_totais":
            total_continuity,

        "eventos_com_continuidade_aceitos":
            len(
                continuity_accepted
            ),

        "eventos_com_continuidade_rejeitados":
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

        "preserva_todos_com_continuidade":
            (
                len(
                    continuity_rejected
                )
                == 0
            ),

        "elimina_fracos_e_preserva_continuidade":
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

        "ganho_mediano_confirmacao_aceitos_cm":
            median_or_none(
                [
                    item[
                        "ganho_liquido_na_confirmacao_cm"
                    ]
                    for item
                    in accepted
                ]
            ),

        "aceitos":
            accepted,

        "rejeitados":
            rejected,
    }


# ==========================================================
# RESUMO DOS EVENTOS
# ==========================================================

def build_event_summary(
    events
):

    result = []

    for event in events:

        result.append(
            {

                "evento":
                    event.get(
                        "evento"
                    ),

                "inicio_sinal_manaus":
                    event.get(
                        "inicio_sinal_manaus"
                    ),

                "confirmado_em_manaus":
                    event.get(
                        "confirmado_em_manaus"
                    ),

                "atraso_confirmacao_h":
                    event.get(
                        "atraso_confirmacao_h"
                    ),

                "ganho_liquido_na_confirmacao_cm":
                    confirmation_gain(
                        event
                    ),

                "classificacao_retrospectiva":
                    retrospective_class(
                        event
                    ),
            }
        )

    return result


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

    results = []

    for threshold in THRESHOLDS:

        results.append(
            analyze_threshold(
                events,
                threshold
            )
        )

    output = {

        "metodologia": {

            "descricao":
                (
                    "Teste retrospectivo de um critério "
                    "adicional de ganho líquido entre o "
                    "primeiro sinal e o momento da "
                    "confirmação do detector."
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
                    in THRESHOLDS
                ],

            "informacao_disponivel_em_tempo_real":
                True,

            "observacao":
                (
                    "O ganho líquido até a confirmação "
                    "usa apenas níveis já observados entre "
                    "o primeiro sinal e o checkpoint de "
                    "confirmação. A classificação "
                    "retrospectiva fraco/continuidade é "
                    "utilizada somente para avaliar o "
                    "desempenho histórico dos limiares."
                ),
        },

        "eventos":
            build_event_summary(
                events
            ),

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
        "TESTE DE GANHO NA CONFIRMAÇÃO"
    )

    print(
        "======================================"
    )

    print()

    print(
        "EVENTOS"
    )

    for event in output[
        "eventos"
    ]:

        print(
            (
                f"Evento {event['evento']}"
                f" | ganho="
                f"{event['ganho_liquido_na_confirmacao_cm']} cm"
                f" | "
                f"{event['classificacao_retrospectiva']}"
            )
        )

    print()

    print(
        "LIMIARES"
    )

    for result in results:

        print(
            (
                f"{result['rotulo']}"
                f" | aceitos="
                f"{result['eventos_aceitos']}"
                f" | fracos aceitos="
                f"{result['eventos_fracos_aceitos']}"
                f" | continuidade preservada="
                f"{result['eventos_com_continuidade_aceitos']}"
                f"/"
                f"{result['eventos_com_continuidade_totais']}"
                f" | separação perfeita="
                f"{result['elimina_fracos_e_preserva_continuidade']}"
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
