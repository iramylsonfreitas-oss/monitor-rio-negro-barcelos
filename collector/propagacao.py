import csv
import json
import math

from datetime import datetime, timedelta, timezone
from pathlib import Path


HISTORY_FILE = Path(
    "data/history/hourly.csv"
)

STATIONS_FILE = Path(
    "data/estacoes.json"
)

OUTPUT_FILE = Path(
    "data/propagacao.json"
)


BARCELOS = "14480002"

ESTACOES = {
    "14110000": "Cucuí",
    "14280001": "Taracuá",
    "14330000": "Curicuriari",
    "14420000": "Serrinha",
    "14480002": "Barcelos",
}


# Limites exploratórios de busca.
# Quanto mais distante de Barcelos,
# maior a janela permitida.

MAX_LAG_HOURS = {
    "14420000": 168,  # Serrinha
    "14330000": 240,  # Curicuriari
    "14280001": 336,  # Taracuá
    "14110000": 480,  # Cucuí
}


# ==========================================================
# LEITURA
# ==========================================================

def parse_datetime(value):
    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S"
    )


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
                row["hora_manaus"]
            )

            nivel_cm = float(
                row["nivel_cm"]
            )

            series[
                codigo
            ][timestamp] = nivel_cm

    return series


def load_current_stations():
    if not STATIONS_FILE.exists():
        return {}

    with STATIONS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )

    return {
        station["estacao"]: station
        for station in data.get(
            "estacoes",
            []
        )
    }


# ==========================================================
# ESTATÍSTICA
# ==========================================================

def pearson(x, y):
    n = len(x)

    if n < 2:
        return None

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum(
        (a - mean_x)
        * (b - mean_y)

        for a, b in zip(
            x,
            y
        )
    )

    denominator_x = math.sqrt(
        sum(
            (a - mean_x) ** 2
            for a in x
        )
    )

    denominator_y = math.sqrt(
        sum(
            (b - mean_y) ** 2
            for b in y
        )
    )

    denominator = (
        denominator_x
        * denominator_y
    )

    if denominator == 0:
        return None

    return numerator / denominator


# ==========================================================
# VARIAÇÃO DE 24 HORAS
# ==========================================================

def build_24h_changes(
    station_series
):
    changes = {}

    for timestamp, level in (
        station_series.items()
    ):

        previous_time = (
            timestamp
            - timedelta(hours=24)
        )

        previous_level = (
            station_series.get(
                previous_time
            )
        )

        if previous_level is None:
            continue

        changes[timestamp] = (
            level
            - previous_level
        )

    return changes


# ==========================================================
# CORRELAÇÃO COM DEFASAGEM
# ==========================================================

def lag_correlation(
    upstream_changes,
    barcelos_changes,
    lag_hours
):
    upstream_values = []
    barcelos_values = []

    lag = timedelta(
        hours=lag_hours
    )

    for upstream_time, value in (
        upstream_changes.items()
    ):

        downstream_time = (
            upstream_time
            + lag
        )

        downstream_value = (
            barcelos_changes.get(
                downstream_time
            )
        )

        if downstream_value is None:
            continue

        upstream_values.append(
            value
        )

        barcelos_values.append(
            downstream_value
        )

    correlation = pearson(
        upstream_values,
        barcelos_values
    )

    return (
        correlation,
        len(upstream_values)
    )


def analyze_pair(
    codigo,
    upstream_series,
    barcelos_series
):
    upstream_changes = (
        build_24h_changes(
            upstream_series
        )
    )

    barcelos_changes = (
        build_24h_changes(
            barcelos_series
        )
    )

    maximum_lag = (
        MAX_LAG_HOURS[
            codigo
        ]
    )

    results = []

    for lag in range(
        0,
        maximum_lag + 1,
        6
    ):

        correlation, samples = (
            lag_correlation(
                upstream_changes,
                barcelos_changes,
                lag
            )
        )

        if (
            correlation is None
            or samples < 48
        ):
            continue

        results.append(
            {
                "defasagem_h":
                    lag,

                "correlacao":
                    correlation,

                "amostras":
                    samples,
            }
        )

    if not results:
        return {
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

            "resultado":
                "dados_insuficientes",

            "melhor_defasagem_h":
                None,

            "correlacao":
                None,

            "amostras":
                0,
        }

    best = max(
        results,
        key=lambda item:
            item[
                "correlacao"
            ]
    )

    correlation = (
        best[
            "correlacao"
        ]
    )

    if correlation >= 0.70:
        strength = "alta"

    elif correlation >= 0.50:
        strength = "moderada"

    elif correlation >= 0.30:
        strength = "baixa"

    else:
        strength = "muito_baixa"

    return {
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

        "resultado":
            "exploratorio",

        "melhor_defasagem_h":
            best[
                "defasagem_h"
            ],

        "melhor_defasagem_dias":
            round(
                best[
                    "defasagem_h"
                ] / 24,
                2
            ),

        "correlacao":
            round(
                correlation,
                3
            ),

        "forca_correlacao":
            strength,

        "amostras":
            best[
                "amostras"
            ],

        "passo_testado_h":
            6,

        "defasagem_maxima_testada_h":
            maximum_lag,
    }


# ==========================================================
# SITUAÇÃO ATUAL
# ==========================================================

def current_snapshot(
    stations
):
    result = []

    for codigo, nome in (
        ESTACOES.items()
    ):

        station = stations.get(
            codigo
        )

        if not station:
            continue

        result.append(
            {
                "estacao":
                    codigo,

                "nome":
                    nome,

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
        )

    return result


# ==========================================================
# COBERTURA DO HISTÓRICO
# ==========================================================

def history_coverage(
    series
):
    timestamps = []

    for station_series in (
        series.values()
    ):
        timestamps.extend(
            station_series.keys()
        )

    if not timestamps:
        return None

    start = min(
        timestamps
    )

    end = max(
        timestamps
    )

    hours = (
        end - start
    ).total_seconds() / 3600

    return {
        "inicio_manaus":
            start.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "fim_manaus":
            end.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "horas":
            round(
                hours,
                1
            ),

        "dias":
            round(
                hours / 24,
                1
            ),
    }


# ==========================================================
# EXECUÇÃO
# ==========================================================

def main():

    history = load_history()

    stations = (
        load_current_stations()
    )

    barcelos_series = (
        history.get(
            BARCELOS,
            {}
        )
    )

    if not barcelos_series:
        raise RuntimeError(
            "Histórico de Barcelos "
            "não encontrado."
        )

    pairs = []

    for codigo in [
        "14420000",
        "14330000",
        "14280001",
        "14110000",
    ]:

        upstream_series = (
            history.get(
                codigo,
                {}
            )
        )

        if not upstream_series:
            continue

        pairs.append(
            analyze_pair(
                codigo,
                upstream_series,
                barcelos_series
            )
        )


    coverage = (
        history_coverage(
            history
        )
    )


    output = {
        "gerado_em_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "metodo":
            (
                "Correlação de Pearson entre "
                "variações horárias acumuladas "
                "de 24 horas, testando "
                "defasagens em passos de 6 horas."
            ),

        "status":
            "experimental",

        "uso":
            (
                "Diagnóstico histórico exploratório. "
                "Não representa previsão hidrológica "
                "nem confirma repiquete."
            ),

        "cobertura_historica":
            coverage,

        "pares":
            pairs,

        "situacao_atual":
            current_snapshot(
                stations
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

        file.write("\n")


    print(
        "Análise de propagação concluída."
    )

    print()

    print(
        "Cobertura histórica:",
        coverage
    )

    print()

    for pair in pairs:

        print(
            pair[
                "nome_origem"
            ],
            "→ Barcelos"
        )

        print(
            "Defasagem:",
            pair.get(
                "melhor_defasagem_h"
            ),
            "h"
        )

        print(
            "Correlação:",
            pair.get(
                "correlacao"
            )
        )

        print(
            "Força:",
            pair.get(
                "forca_correlacao"
            )
        )

        print(
            "Amostras:",
            pair.get(
                "amostras"
            )
        )

        print()


if __name__ == "__main__":
    main()
