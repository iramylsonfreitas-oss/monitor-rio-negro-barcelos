import csv
import math

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

BARCELOS = "14480002"
MOURA = "14840000"

MAX_LAG_HOURS = 240
STEP_HOURS = 6
MIN_SAMPLES = 48
TOP_RESULTS = 10


def parse_datetime(value):
    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M:%S"
    )


def load_series():
    if not HISTORY_FILE.exists():
        raise RuntimeError(
            "Arquivo data/history/hourly.csv não encontrado."
        )

    series = {
        BARCELOS: {},
        MOURA: {},
    }

    with HISTORY_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            codigo = row.get("estacao")

            if codigo not in series:
                continue

            hora = row.get("hora_manaus")
            nivel = row.get("nivel_cm")

            if not hora or not nivel:
                continue

            try:
                timestamp = parse_datetime(hora)
                nivel_cm = float(nivel)
            except (TypeError, ValueError):
                continue

            series[codigo][timestamp] = nivel_cm

    return series


def build_24h_changes(station_series):
    changes = {}

    for timestamp, level in station_series.items():
        previous_time = timestamp - timedelta(hours=24)
        previous_level = station_series.get(previous_time)

        if previous_level is None:
            continue

        changes[timestamp] = level - previous_level

    return changes


def pearson(x, y):
    n = len(x)

    if n < 2:
        return None

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum(
        (a - mean_x) * (b - mean_y)
        for a, b in zip(x, y)
    )

    denominator_x = math.sqrt(
        sum((a - mean_x) ** 2 for a in x)
    )

    denominator_y = math.sqrt(
        sum((b - mean_y) ** 2 for b in y)
    )

    denominator = denominator_x * denominator_y

    if denominator == 0:
        return None

    return numerator / denominator


def lag_correlation(
    barcelos_changes,
    moura_changes,
    lag_hours
):
    barcelos_values = []
    moura_values = []

    lag = timedelta(hours=lag_hours)

    for barcelos_time, value in barcelos_changes.items():
        moura_time = barcelos_time + lag
        moura_value = moura_changes.get(moura_time)

        if moura_value is None:
            continue

        barcelos_values.append(value)
        moura_values.append(moura_value)

    correlation = pearson(
        barcelos_values,
        moura_values
    )

    return correlation, len(barcelos_values)


def coverage(station_series):
    if not station_series:
        return None, None

    timestamps = sorted(station_series)
    return timestamps[0], timestamps[-1]


def main():
    series = load_series()

    barcelos_series = series[BARCELOS]
    moura_series = series[MOURA]

    if not barcelos_series:
        raise RuntimeError(
            "Histórico de Barcelos não encontrado."
        )

    if not moura_series:
        raise RuntimeError(
            "Histórico de Moura não encontrado."
        )

    barcelos_changes = build_24h_changes(
        barcelos_series
    )

    moura_changes = build_24h_changes(
        moura_series
    )

    results = []

    for lag in range(
        0,
        MAX_LAG_HOURS + 1,
        STEP_HOURS
    ):
        correlation, samples = lag_correlation(
            barcelos_changes,
            moura_changes,
            lag
        )

        if correlation is None:
            continue

        if samples < MIN_SAMPLES:
            continue

        results.append(
            {
                "defasagem_h": lag,
                "correlacao": correlation,
                "amostras": samples,
            }
        )

    if not results:
        raise RuntimeError(
            "Não há amostras suficientes para testar "
            "Barcelos -> Moura."
        )

    results.sort(
        key=lambda item: item["correlacao"],
        reverse=True
    )

    best = results[0]

    barcelos_start, barcelos_end = coverage(
        barcelos_series
    )

    moura_start, moura_end = coverage(
        moura_series
    )

    common_start = max(
        barcelos_start,
        moura_start
    )

    common_end = min(
        barcelos_end,
        moura_end
    )

    common_hours = max(
        0,
        int(
            (
                common_end - common_start
            ).total_seconds() // 3600
        )
    )

    print()
    print("======================================")
    print("TESTE BARCELOS -> MOURA")
    print("======================================")
    print()

    print(
        "Barcelos:",
        len(barcelos_series),
        "registros"
    )

    print(
        "Moura:",
        len(moura_series),
        "registros"
    )

    print(
        "Cobertura comum aproximada:",
        round(common_hours / 24, 1),
        "dias"
    )

    print()
    print("Melhores resultados:")
    print()

    for index, item in enumerate(
        results[:TOP_RESULTS],
        start=1
    ):
        print(
            f"{index:>2}. "
            f"{item['defasagem_h']:>3} h  "
            f"r={item['correlacao']:.3f}  "
            f"n={item['amostras']}"
        )

    print()
    print("Melhor defasagem encontrada:")
    print(
        best["defasagem_h"],
        "horas =",
        round(best["defasagem_h"] / 24, 2),
        "dias"
    )

    print(
        "Correlação:",
        round(best["correlacao"], 3)
    )

    print(
        "Amostras:",
        best["amostras"]
    )

    print()
    print(
        "Resultado exploratório. "
        "Não altera nenhum arquivo do painel."
    )


if __name__ == "__main__":
    main()
