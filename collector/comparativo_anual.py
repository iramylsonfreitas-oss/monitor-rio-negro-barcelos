import csv
import json
import statistics

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


BARCELOS = "14480002"

HISTORY_FILE = Path(
    "data/history/hourly.csv"
)

OUTPUT_FILE = Path(
    "data/barcelos_anual.json"
)


def carregar_dados():

    grupos_diarios = defaultdict(
        list
    )

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
                row.get("estacao")
                != BARCELOS
            ):
                continue


            hora = (
                row.get(
                    "hora_manaus"
                )
                or ""
            )


            nivel = (
                row.get(
                    "nivel_m"
                )
                or ""
            )


            if (
                not hora
                or not nivel
            ):
                continue


            try:

                data = datetime.strptime(
                    hora,
                    "%Y-%m-%d %H:%M:%S"
                )

                nivel_m = float(
                    nivel
                )

            except (
                ValueError,
                TypeError
            ):

                continue


            dia = data.strftime(
                "%Y-%m-%d"
            )


            grupos_diarios[
                dia
            ].append(
                nivel_m
            )


    return grupos_diarios


def gerar_series(
    grupos_diarios
):

    series_por_ano = defaultdict(
        list
    )


    for dia in sorted(
        grupos_diarios
    ):

        niveis = (
            grupos_diarios[
                dia
            ]
        )


        if not niveis:
            continue


        data = datetime.strptime(
            dia,
            "%Y-%m-%d"
        )


        ano = str(
            data.year
        )


        nivel_mediano = (
            statistics.median(
                niveis
            )
        )


        series_por_ano[
            ano
        ].append(
            {
                "data":
                    dia,

                "dia_mes":
                    data.strftime(
                        "%m-%d"
                    ),

                "nivel_m":
                    round(
                        nivel_mediano,
                        3
                    ),

                "amostras_horarias":
                    len(
                        niveis
                    )
            }
        )


    return dict(
        sorted(
            series_por_ano.items()
        )
    )


def gerar_resumo(
    series_por_ano
):

    resumo = {}


    for ano, pontos in (
        series_por_ano.items()
    ):

        if not pontos:
            continue


        niveis = [
            ponto[
                "nivel_m"
            ]
            for ponto in pontos
        ]


        resumo[
            ano
        ] = {

            "dias_disponiveis":
                len(
                    pontos
                ),

            "primeira_data":
                pontos[
                    0
                ][
                    "data"
                ],

            "ultima_data":
                pontos[
                    -1
                ][
                    "data"
                ],

            "nivel_min_m":
                round(
                    min(
                        niveis
                    ),
                    3
                ),

            "nivel_max_m":
                round(
                    max(
                        niveis
                    ),
                    3
                )
        }


    return resumo


def main():

    if not HISTORY_FILE.exists():

        raise FileNotFoundError(
            "Histórico não encontrado: "
            f"{HISTORY_FILE}"
        )


    grupos_diarios = (
        carregar_dados()
    )


    series_por_ano = (
        gerar_series(
            grupos_diarios
        )
    )


    resumo = (
        gerar_resumo(
            series_por_ano
        )
    )


    payload = {

        "estacao":
            BARCELOS,

        "nome":
            "Barcelos",

        "unidade":
            "m",

        "agregacao":
            (
                "mediana diária "
                "dos níveis horários"
            ),

        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "anos":
            list(
                series_por_ano.keys()
            ),

        "resumo":
            resumo,

        "series":
            series_por_ano
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
            payload,
            file,
            ensure_ascii=False,
            indent=2
        )


    print(
        "======================================"
    )

    print(
        "COMPARATIVO ANUAL DE BARCELOS"
    )

    print(
        "======================================"
    )


    for ano, info in (
        resumo.items()
    ):

        print()

        print(
            ano
        )

        print(
            "Dias disponíveis:",
            info[
                "dias_disponiveis"
            ]
        )

        print(
            "Período:",
            info[
                "primeira_data"
            ],
            "até",
            info[
                "ultima_data"
            ]
        )

        print(
            "Mínimo:",
            info[
                "nivel_min_m"
            ],
            "m"
        )

        print(
            "Máximo:",
            info[
                "nivel_max_m"
            ],
            "m"
        )


    print()

    print(
        "Arquivo criado:",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
