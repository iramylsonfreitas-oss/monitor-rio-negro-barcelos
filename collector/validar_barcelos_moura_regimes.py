import csv
import math

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

BARCELOS = "14480002"
MOURA = "14840000"

CHANGE_HOURS = 24
MAX_LAG_HOURS = 240
STEP_HOURS = 1

MIN_SAMPLES_HOURLY = 48
MIN_SAMPLES_DAILY = 20

TOP_RESULTS = 10
YEARS = (2024, 2025, 2026)
REGIMES = ("geral", "subida", "descida")

# Considera como faixa estável os lags cuja correlação fica
# no máximo 0,01 abaixo do pico.
PLATEAU_TOLERANCE = 0.01


def parse_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def load_series():
    if not HISTORY_FILE.exists():
        raise RuntimeError("Arquivo data/history/hourly.csv não encontrado.")

    series = {BARCELOS: {}, MOURA: {}}

    with HISTORY_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            code = row.get("estacao")
            if code not in series:
                continue

            time_value = row.get("hora_manaus")
            level_value = row.get("nivel_cm")

            if not time_value or not level_value:
                continue

            try:
                timestamp = parse_datetime(time_value)
                level = float(level_value)
            except (TypeError, ValueError):
                continue

            series[code][timestamp] = level

    return series


def build_changes(station_series, hours=CHANGE_HOURS):
    changes = {}
    delta = timedelta(hours=hours)

    for timestamp, level in station_series.items():
        previous_level = station_series.get(timestamp - delta)
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


def regime_ok(value, regime):
    if regime == "geral":
        return True
    if regime == "subida":
        return value > 0
    if regime == "descida":
        return value < 0
    raise ValueError(f"Regime inválido: {regime}")


def sampling_ok(timestamp, mode):
    if mode == "horario":
        return True

    if mode == "diario":
        # Uma observação por dia, ao meio-dia de Manaus.
        # Reduz bastante a pseudo-replicação causada por
        # janelas de 24h sobrepostas hora a hora.
        return timestamp.hour == 12

    raise ValueError(f"Modo inválido: {mode}")


def lag_correlation(
    barcelos_changes,
    moura_changes,
    lag_hours,
    regime="geral",
    year=None,
    sampling_mode="horario",
):
    x = []
    y = []

    lag = timedelta(hours=lag_hours)

    for barcelos_time, barcelos_change in barcelos_changes.items():
        if not regime_ok(barcelos_change, regime):
            continue

        if not sampling_ok(barcelos_time, sampling_mode):
            continue

        moura_time = barcelos_time + lag

        if year is not None:
            if barcelos_time.year != year or moura_time.year != year:
                continue

        moura_change = moura_changes.get(moura_time)
        if moura_change is None:
            continue

        x.append(barcelos_change)
        y.append(moura_change)

    return pearson(x, y), len(x)


def calculate_results(
    barcelos_changes,
    moura_changes,
    regime="geral",
    year=None,
    sampling_mode="horario",
):
    results = []

    min_samples = (
        MIN_SAMPLES_HOURLY
        if sampling_mode == "horario"
        else MIN_SAMPLES_DAILY
    )

    for lag in range(0, MAX_LAG_HOURS + 1, STEP_HOURS):
        correlation, samples = lag_correlation(
            barcelos_changes,
            moura_changes,
            lag_hours=lag,
            regime=regime,
            year=year,
            sampling_mode=sampling_mode,
        )

        if correlation is None or samples < min_samples:
            continue

        results.append(
            {
                "lag_h": lag,
                "r": correlation,
                "n": samples,
            }
        )

    results.sort(key=lambda item: item["r"], reverse=True)
    return results


def contiguous_plateau(results):
    if not results:
        return None

    best = results[0]
    threshold = best["r"] - PLATEAU_TOLERANCE

    by_lag = {
        item["lag_h"]: item
        for item in results
        if item["r"] >= threshold
    }

    best_lag = best["lag_h"]
    low = best_lag
    high = best_lag

    while (low - STEP_HOURS) in by_lag:
        low -= STEP_HOURS

    while (high + STEP_HOURS) in by_lag:
        high += STEP_HOURS

    return low, high, threshold


def print_results(title, results):
    print()
    print(title)

    if not results:
        print("  Sem amostras suficientes.")
        return None

    for idx, item in enumerate(results[:TOP_RESULTS], start=1):
        print(
            f"  {idx:>2}. "
            f"{item['lag_h']:>3} h  "
            f"({item['lag_h']/24:.2f} d)  "
            f"r={item['r']:.3f}  "
            f"n={item['n']}"
        )

    best = results[0]
    plateau = contiguous_plateau(results)

    if plateau:
        low, high, threshold = plateau
        print(
            f"  Faixa estável do pico: "
            f"{low}-{high} h "
            f"({low/24:.2f}-{high/24:.2f} d), "
            f"r >= {threshold:.3f}"
        )

    return best


def coverage(series):
    if not series:
        return None, None

    times = sorted(series)
    return times[0], times[-1]


def main():
    series = load_series()

    barcelos = series[BARCELOS]
    moura = series[MOURA]

    if not barcelos:
        raise RuntimeError("Histórico de Barcelos não encontrado.")

    if not moura:
        raise RuntimeError("Histórico de Moura não encontrado.")

    b_start, b_end = coverage(barcelos)
    m_start, m_end = coverage(moura)

    common_start = max(b_start, m_start)
    common_end = min(b_end, m_end)

    common_days = max(
        0.0,
        (common_end - common_start).total_seconds() / 86400,
    )

    barcelos_changes = build_changes(barcelos)
    moura_changes = build_changes(moura)

    print()
    print("==============================================")
    print("VALIDACAO BARCELOS -> MOURA")
    print("REGIMES + AMOSTRAGEM REDUZIDA")
    print("==============================================")
    print()
    print("Barcelos:", len(barcelos), "registros")
    print("Moura:", len(moura), "registros")
    print("Cobertura comum:", round(common_days, 1), "dias")
    print("Variação analisada: delta 24h")
    print("Defasagem testada: 0 a 240 h, passo de 1 h")
    print()

    summary = []

    for sampling_mode in ("horario", "diario"):
        print()
        print("==============================================")
        print("AMOSTRAGEM:", sampling_mode.upper())
        print("==============================================")

        for regime in REGIMES:
            results = calculate_results(
                barcelos_changes,
                moura_changes,
                regime=regime,
                sampling_mode=sampling_mode,
            )

            best = print_results(
                f"Histórico completo | {regime.upper()}",
                results,
            )

            if best:
                summary.append(
                    (
                        sampling_mode,
                        "geral",
                        regime,
                        best["lag_h"],
                        best["r"],
                        best["n"],
                    )
                )

            for year in YEARS:
                yearly_results = calculate_results(
                    barcelos_changes,
                    moura_changes,
                    regime=regime,
                    year=year,
                    sampling_mode=sampling_mode,
                )

                best_year = print_results(
                    f"{year} | {regime.upper()}",
                    yearly_results,
                )

                if best_year:
                    summary.append(
                        (
                            sampling_mode,
                            str(year),
                            regime,
                            best_year["lag_h"],
                            best_year["r"],
                            best_year["n"],
                        )
                    )

    print()
    print("==============================================")
    print("RESUMO DOS MELHORES PICOS")
    print("==============================================")
    print()

    for mode, period, regime, lag, corr, samples in summary:
        print(
            f"{mode:<8} "
            f"{period:<5} "
            f"{regime:<8} "
            f"lag={lag:>3} h "
            f"({lag/24:.2f} d) "
            f"r={corr:.3f} "
            f"n={samples}"
        )

    print()
    print(
        "Leitura recomendada: procurar consistência entre "
        "amostragem horária e diária, e entre subida e descida. "
        "Uma faixa estável é mais confiável do que um único horário de pico."
    )
    print()
    print("Este teste não altera nenhum arquivo do painel.")


if __name__ == "__main__":
    main()
