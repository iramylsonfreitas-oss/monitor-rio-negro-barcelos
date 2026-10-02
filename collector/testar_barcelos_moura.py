import csv
import math

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

BARCELOS = "14480002"
MOURA = "14840000"

MAX_LAG_HOURS = 240
STEP_HOURS = 1
MIN_SAMPLES = 48
TOP_RESULTS = 5
CHANGE_WINDOWS = (6, 12, 24)
YEARS = (2024, 2025, 2026)


def parse_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def load_series():
    if not HISTORY_FILE.exists():
        raise RuntimeError("Arquivo data/history/hourly.csv não encontrado.")

    series = {BARCELOS: {}, MOURA: {}}

    with HISTORY_FILE.open("r", encoding="utf-8", newline="") as file:
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


def build_changes(station_series, hours):
    changes = {}
    delta = timedelta(hours=hours)

    for timestamp, level in station_series.items():
        previous_time = timestamp - delta
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

    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denominator_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    denominator_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    denominator = denominator_x * denominator_y

    if denominator == 0:
        return None

    return numerator / denominator


def lag_correlation(barcelos_changes, moura_changes, lag_hours, year=None):
    barcelos_values = []
    moura_values = []
    lag = timedelta(hours=lag_hours)

    for barcelos_time, value in barcelos_changes.items():
        moura_time = barcelos_time + lag

        if year is not None:
            if barcelos_time.year != year or moura_time.year != year:
                continue

        moura_value = moura_changes.get(moura_time)
        if moura_value is None:
            continue

        barcelos_values.append(value)
        moura_values.append(moura_value)

    correlation = pearson(barcelos_values, moura_values)
    return correlation, len(barcelos_values)


def calculate_results(barcelos_changes, moura_changes, year=None):
    results = []

    for lag in range(0, MAX_LAG_HOURS + 1, STEP_HOURS):
        correlation, samples = lag_correlation(
            barcelos_changes,
            moura_changes,
            lag,
            year=year,
        )

        if correlation is None or samples < MIN_SAMPLES:
            continue

        results.append(
            {
                "defasagem_h": lag,
                "correlacao": correlation,
                "amostras": samples,
            }
        )

    results.sort(key=lambda item: item["correlacao"], reverse=True)
    return results


def coverage(station_series):
    if not station_series:
        return None, None
    timestamps = sorted(station_series)
    return timestamps[0], timestamps[-1]


def print_top_results(results):
    if not results:
        print("Sem amostras suficientes.")
        return

    for index, item in enumerate(results[:TOP_RESULTS], start=1):
        print(
            f"{index:>2}. "
            f"{item['defasagem_h']:>3} h  "
            f"r={item['correlacao']:.3f}  "
            f"n={item['amostras']}"
        )


def main():
    series = load_series()
    barcelos_series = series[BARCELOS]
    moura_series = series[MOURA]

    if not barcelos_series:
        raise RuntimeError("Histórico de Barcelos não encontrado.")
    if not moura_series:
        raise RuntimeError("Histórico de Moura não encontrado.")

    barcelos_start, barcelos_end = coverage(barcelos_series)
    moura_start, moura_end = coverage(moura_series)

    common_start = max(barcelos_start, moura_start)
    common_end = min(barcelos_end, moura_end)
    common_hours = max(
        0,
        int((common_end - common_start).total_seconds() // 3600),
    )

    print()
    print("======================================")
    print("TESTE BARCELOS -> MOURA")
    print("MULTIJANELA + DEFASAGEM HORARIA")
    print("======================================")
    print()
    print("Barcelos:", len(barcelos_series), "registros")
    print("Moura:", len(moura_series), "registros")
    print("Cobertura comum aproximada:", round(common_hours / 24, 1), "dias")
    print("Busca de defasagem:", f"0 a {MAX_LAG_HOURS} h,", f"passo de {STEP_HOURS} h")

    summary = []

    for window_hours in CHANGE_WINDOWS:
        barcelos_changes = build_changes(barcelos_series, window_hours)
        moura_changes = build_changes(moura_series, window_hours)

        print()
        print("======================================")
        print(f"VARIACAO DELTA {window_hours}h")
        print("======================================")

        overall_results = calculate_results(barcelos_changes, moura_changes)
        print()
        print("Historico completo - melhores resultados:")
        print_top_results(overall_results)

        if overall_results:
            best = overall_results[0]
            summary.append((
                f"Delta {window_hours}h - geral",
                best["defasagem_h"],
                best["correlacao"],
                best["amostras"],
            ))

        for year in YEARS:
            yearly_results = calculate_results(
                barcelos_changes,
                moura_changes,
                year=year,
            )

            print()
            print(f"{year} - melhores resultados:")
            print_top_results(yearly_results)

            if yearly_results:
                best = yearly_results[0]
                summary.append((
                    f"Delta {window_hours}h - {year}",
                    best["defasagem_h"],
                    best["correlacao"],
                    best["amostras"],
                ))

    print()
    print("======================================")
    print("RESUMO DOS PICOS")
    print("======================================")
    print()

    for label, lag, correlation, samples in summary:
        print(
            f"{label:<20} "
            f"lag={lag:>3} h  "
            f"({lag / 24:.2f} dias)  "
            f"r={correlation:.3f}  "
            f"n={samples}"
        )

    print()
    print("Resultado exploratorio. Nao altera nenhum arquivo do painel.")


if __name__ == "__main__":
    main()
