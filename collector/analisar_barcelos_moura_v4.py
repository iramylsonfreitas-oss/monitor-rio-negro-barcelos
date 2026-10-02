import csv
import json
import math
import statistics

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

BARCELOS = "14480002"
MOURA = "14840000"

# Detector de eventos em Barcelos
CHANGE_WINDOW_HOURS = 24
THRESHOLD_CM_24H = 5.0
MAX_NEUTRAL_GAP_HOURS = 12
MIN_EVENT_DURATION_HOURS = 18
MIN_EVENT_AMPLITUDE_CM = 10.0

# Busca direta da resposta em Moura
MIN_LAG_HOURS = 24
MAX_LAG_HOURS = 168
LAG_STEP_HOURS = 1

# Janela móvel usada para comparar a forma da onda
PRE_EVENT_HOURS = 12
POST_EVENT_HOURS = 24
MIN_COMPARE_HOURS = 48
MAX_COMPARE_HOURS = 120
MIN_SHAPE_SAMPLES = 24

# Critérios de aceitação
MIN_SHAPE_R = 0.55
HIGH_SHAPE_R = 0.75

MIN_AMPLITUDE_RATIO = 0.15
MAX_AMPLITUDE_RATIO = 5.0

HIGH_SCORE = 76.0
MEDIUM_SCORE = 60.0

# Evita que dois eventos de Barcelos usem praticamente a mesma resposta em Moura
MIN_RESPONSE_SEPARATION_H = 36

OUTPUT_DIR = Path("artifacts")
ACCEPTED_CSV = OUTPUT_DIR / "barcelos_moura_v4_aceitos.csv"
REJECTED_CSV = OUTPUT_DIR / "barcelos_moura_v4_rejeitados.csv"
CURVES_CSV = OUTPUT_DIR / "barcelos_moura_v4_curvas_lag.csv"
SUMMARY_JSON = OUTPUT_DIR / "resumo_barcelos_moura_v4.json"


def parse_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def load_series():
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


def build_changes(station_series, hours=CHANGE_WINDOW_HOURS):
    changes = {}
    delta = timedelta(hours=hours)

    for timestamp, level in station_series.items():
        previous = station_series.get(timestamp - delta)
        if previous is not None:
            changes[timestamp] = level - previous

    return changes


def classify(change):
    if change >= THRESHOLD_CM_24H:
        return 1

    if change <= -THRESHOLD_CM_24H:
        return -1

    return 0


def detect_barcelos_events(station_series):
    changes = build_changes(station_series)

    active = sorted(
        (timestamp, classify(change))
        for timestamp, change in changes.items()
    )

    events = []
    current = None

    def close_current():
        nonlocal current

        if current is None:
            return

        direction = current["direction"]
        start = current["start"]
        end = current["last_active"]

        duration_h = (end - start).total_seconds() / 3600

        if duration_h < MIN_EVENT_DURATION_HOURS:
            current = None
            return

        times = sorted(
            timestamp
            for timestamp in station_series
            if start <= timestamp <= end
        )

        if not times:
            current = None
            return

        start_level = station_series.get(start)

        if start_level is None:
            current = None
            return

        if direction == 1:
            extremum_time = max(
                times,
                key=lambda t: station_series[t],
            )
        else:
            extremum_time = min(
                times,
                key=lambda t: station_series[t],
            )

        extremum_level = station_series[extremum_time]

        amplitude = (
            extremum_level - start_level
            if direction == 1
            else start_level - extremum_level
        )

        if amplitude < MIN_EVENT_AMPLITUDE_CM:
            current = None
            return

        events.append(
            {
                "event_index": len(events) + 1,
                "direction": direction,
                "type": "subida" if direction == 1 else "descida",
                "start": start,
                "end": end,
                "extremum_time": extremum_time,
                "start_level_cm": start_level,
                "extremum_level_cm": extremum_level,
                "amplitude_cm": amplitude,
                "duration_h": duration_h,
            }
        )

        current = None

    for timestamp, state in active:
        if state == 0:
            if current is not None:
                gap_h = (
                    timestamp - current["last_active"]
                ).total_seconds() / 3600

                if gap_h > MAX_NEUTRAL_GAP_HOURS:
                    close_current()

            continue

        if current is None:
            current = {
                "direction": state,
                "start": timestamp,
                "last_active": timestamp,
            }
            continue

        if state == current["direction"]:
            current["last_active"] = timestamp
            continue

        close_current()

        current = {
            "direction": state,
            "start": timestamp,
            "last_active": timestamp,
        }

    close_current()

    return events


def pearson(x, y):
    if len(x) < 2:
        return None

    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)

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


def ratio_score(ratio):
    if ratio <= 0:
        return 0.0

    return math.exp(-abs(math.log(ratio)))


def event_compare_window(event):
    event_h = max(
        MIN_COMPARE_HOURS,
        min(
            MAX_COMPARE_HOURS,
            int(event["duration_h"] + PRE_EVENT_HOURS + POST_EVENT_HOURS),
        ),
    )

    start = event["start"] - timedelta(hours=PRE_EVENT_HOURS)
    end = start + timedelta(hours=event_h)

    return start, end


def lag_curve(event, b_changes, m_changes):
    window_start, window_end = event_compare_window(event)
    curve = []

    for lag_h in range(
        MIN_LAG_HOURS,
        MAX_LAG_HOURS + 1,
        LAG_STEP_HOURS,
    ):
        lag = timedelta(hours=lag_h)

        x = []
        y = []

        for timestamp, b_value in b_changes.items():
            if not (
                window_start <= timestamp <= window_end
            ):
                continue

            m_value = m_changes.get(timestamp + lag)

            if m_value is None:
                continue

            x.append(b_value)
            y.append(m_value)

        if len(x) < MIN_SHAPE_SAMPLES:
            continue

        corr = pearson(x, y)

        if corr is None:
            continue

        curve.append(
            {
                "lag_h": lag_h,
                "r": corr,
                "n": len(x),
            }
        )

    curve.sort(
        key=lambda item: item["r"],
        reverse=True,
    )

    return curve


def plateau_for_best(curve, tolerance=0.03):
    if not curve:
        return None

    best = curve[0]
    threshold = best["r"] - tolerance

    by_lag = {
        item["lag_h"]: item
        for item in curve
        if item["r"] >= threshold
    }

    low = best["lag_h"]
    high = best["lag_h"]

    while (low - 1) in by_lag:
        low -= 1

    while (high + 1) in by_lag:
        high += 1

    return low, high


def peak_prominence(curve):
    if not curve:
        return 0.0

    best = curve[0]
    best_lag = best["lag_h"]

    separated = [
        item["r"]
        for item in curve
        if abs(item["lag_h"] - best_lag) >= 18
    ]

    if not separated:
        return 0.0

    second = max(separated)

    return max(
        0.0,
        min(
            1.0,
            (best["r"] - second) / 0.12,
        ),
    )


def response_amplitude(
    event,
    lag_h,
    moura_levels,
):
    shifted_start = event["start"] + timedelta(hours=lag_h)
    shifted_end = event["end"] + timedelta(hours=lag_h)

    times = sorted(
        timestamp
        for timestamp in moura_levels
        if shifted_start <= timestamp <= shifted_end
    )

    if not times:
        return None

    start_level = moura_levels.get(shifted_start)

    if start_level is None:
        # Usa o primeiro ponto disponível dentro da janela.
        start_level = moura_levels[times[0]]
        shifted_start = times[0]

    if event["direction"] == 1:
        extremum_time = max(
            times,
            key=lambda t: moura_levels[t],
        )
        amplitude = (
            moura_levels[extremum_time] - start_level
        )
    else:
        extremum_time = min(
            times,
            key=lambda t: moura_levels[t],
        )
        amplitude = (
            start_level - moura_levels[extremum_time]
        )

    return {
        "response_start": shifted_start,
        "response_extremum": extremum_time,
        "response_amplitude_cm": amplitude,
    }


def evaluate_event(
    event,
    b_changes,
    m_changes,
    moura_levels,
):
    curve = lag_curve(
        event,
        b_changes,
        m_changes,
    )

    if not curve:
        return {
            "accepted": False,
            "reason": "sem_amostras",
            "event_index": event["event_index"],
        }, curve

    best = curve[0]
    best_lag = best["lag_h"]
    best_r = best["r"]

    response = response_amplitude(
        event,
        best_lag,
        moura_levels,
    )

    if response is None:
        return {
            "accepted": False,
            "reason": "sem_resposta_nivel",
            "event_index": event["event_index"],
        }, curve

    response_amplitude_cm = response["response_amplitude_cm"]

    amplitude_ratio = (
        response_amplitude_cm
        / event["amplitude_cm"]
        if event["amplitude_cm"] > 0
        else math.nan
    )

    direction_ok = response_amplitude_cm > 0

    amplitude_ok = (
        MIN_AMPLITUDE_RATIO
        <= amplitude_ratio
        <= MAX_AMPLITUDE_RATIO
    )

    plateau = plateau_for_best(curve)
    if plateau is None:
        plateau_low = best_lag
        plateau_high = best_lag
    else:
        plateau_low, plateau_high = plateau

    plateau_width_h = plateau_high - plateau_low

    prominence = peak_prominence(curve)

    shape_component = max(
        0.0,
        min(1.0, best_r),
    )

    amp_component = (
        ratio_score(amplitude_ratio)
        if amplitude_ratio > 0
        else 0.0
    )

    plateau_component = max(
        0.0,
        min(
            1.0,
            1.0 - plateau_width_h / 96.0,
        ),
    )

    direction_component = 1.0 if direction_ok else 0.0

    score = (
        55.0 * shape_component
        + 20.0 * amp_component
        + 10.0 * prominence
        + 10.0 * plateau_component
        + 5.0 * direction_component
    )

    if (
        best_r < MIN_SHAPE_R
        or not direction_ok
        or not amplitude_ok
    ):
        confidence = "rejeitado"
        accepted = False
    elif (
        score >= HIGH_SCORE
        and best_r >= HIGH_SHAPE_R
    ):
        confidence = "alta"
        accepted = True
    elif score >= MEDIUM_SCORE:
        confidence = "media"
        accepted = True
    else:
        confidence = "rejeitado"
        accepted = False

    reason = ""
    if not accepted:
        reasons = []

        if best_r < MIN_SHAPE_R:
            reasons.append("correlacao_baixa")

        if not direction_ok:
            reasons.append("direcao_incompativel")

        if not amplitude_ok:
            reasons.append("amplitude_incompativel")

        if score < MEDIUM_SCORE:
            reasons.append("score_baixo")

        reason = ",".join(reasons) or "rejeitado_score"

    result = {
        "accepted": accepted,
        "reason": reason,
        "event_index": event["event_index"],
        "type": event["type"],
        "year": event["start"].year,
        "barcelos_start": event["start"],
        "barcelos_extremum": event["extremum_time"],
        "barcelos_end": event["end"],
        "barcelos_amplitude_cm": event["amplitude_cm"],
        "barcelos_duration_h": event["duration_h"],
        "best_lag_h": best_lag,
        "best_r": best_r,
        "shape_n": best["n"],
        "plateau_low_h": plateau_low,
        "plateau_high_h": plateau_high,
        "plateau_width_h": plateau_width_h,
        "peak_prominence": prominence,
        "moura_response_start": response["response_start"],
        "moura_response_extremum": response["response_extremum"],
        "moura_amplitude_cm": response_amplitude_cm,
        "amplitude_ratio": amplitude_ratio,
        "score": score,
        "confidence": confidence,
    }

    return result, curve


def deduplicate_accepted(results):
    accepted = [
        item
        for item in results
        if item["accepted"]
    ]

    accepted.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    selected = []
    rejected_duplicates = []

    for item in accepted:
        response_time = item["moura_response_start"]

        conflict = False

        for chosen in selected:
            if item["type"] != chosen["type"]:
                continue

            diff_h = abs(
                (
                    response_time
                    - chosen["moura_response_start"]
                ).total_seconds()
                / 3600
            )

            if diff_h < MIN_RESPONSE_SEPARATION_H:
                conflict = True
                break

        if conflict:
            copy = dict(item)
            copy["accepted"] = False
            copy["confidence"] = "rejeitado"
            copy["reason"] = "resposta_moura_duplicada"
            rejected_duplicates.append(copy)
        else:
            selected.append(item)

    selected.sort(
        key=lambda item: item["barcelos_start"]
    )

    for index, item in enumerate(selected, start=1):
        item["pair_id"] = index

    return selected, rejected_duplicates


def percentile(values, fraction):
    values = sorted(values)

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)

    if low == high:
        return values[low]

    weight = position - low

    return (
        values[low] * (1 - weight)
        + values[high] * weight
    )


def summarize(items, label):
    if not items:
        return {"label": label, "n": 0}

    lags = [
        item["best_lag_h"]
        for item in items
    ]

    return {
        "label": label,
        "n": len(items),
        "median_h": statistics.median(lags),
        "q25_h": percentile(lags, 0.25),
        "q75_h": percentile(lags, 0.75),
        "mean_h": statistics.mean(lags),
        "min_h": min(lags),
        "max_h": max(lags),
    }


def format_dt(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def write_csv(path, rows, fields):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for item in rows:
            row = dict(item)

            for key, value in list(row.items()):
                row[key] = format_dt(value)

            writer.writerow(
                {
                    field: row.get(field)
                    for field in fields
                }
            )


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError(
            "data/history/hourly.csv não encontrado."
        )

    series = load_series()

    barcelos_levels = series[BARCELOS]
    moura_levels = series[MOURA]

    if not barcelos_levels or not moura_levels:
        raise RuntimeError(
            "Histórico de Barcelos ou Moura ausente."
        )

    b_changes = build_changes(
        barcelos_levels
    )
    m_changes = build_changes(
        moura_levels
    )

    events = detect_barcelos_events(
        barcelos_levels
    )

    results = []
    lag_rows = []

    for event in events:
        result, curve = evaluate_event(
            event,
            b_changes,
            m_changes,
            moura_levels,
        )

        results.append(result)

        for point in curve:
            lag_rows.append(
                {
                    "event_index": event["event_index"],
                    "type": event["type"],
                    "year": event["start"].year,
                    "barcelos_start": event["start"],
                    "lag_h": point["lag_h"],
                    "r": point["r"],
                    "n": point["n"],
                }
            )

    accepted, duplicate_rejects = deduplicate_accepted(
        results
    )

    rejected = [
        item
        for item in results
        if not item["accepted"]
    ] + duplicate_rejects

    counts = {
        "alta": sum(
            1
            for item in accepted
            if item["confidence"] == "alta"
        ),
        "media": sum(
            1
            for item in accepted
            if item["confidence"] == "media"
        ),
    }

    print()
    print("============================================")
    print("BARCELOS -> MOURA V4")
    print("JANELAS MOVEIS DE FORMA DE ONDA")
    print("============================================")
    print()
    print("Eventos Barcelos:", len(events))
    print("Aceitos:", len(accepted))
    print("Rejeitados:", len(rejected))
    print(
        "Confiança:",
        f"alta={counts['alta']}",
        f"media={counts['media']}",
    )
    print(
        "Busca de lag:",
        f"{MIN_LAG_HOURS}-{MAX_LAG_HOURS} h",
    )
    print()

    print("============================================")
    print("PARES ACEITOS")
    print("============================================")
    print()

    for item in accepted:
        print(
            f"#{item['pair_id']:02d} "
            f"{item['type']:<7} "
            f"B {item['barcelos_start']:%Y-%m-%d %H:%M} | "
            f"lag={item['best_lag_h']:>3} h "
            f"({item['best_lag_h']/24:.2f} d) | "
            f"r={item['best_r']:.3f} | "
            f"amp={item['amplitude_ratio']:.2f}x | "
            f"plateau={item['plateau_low_h']}-"
            f"{item['plateau_high_h']} h | "
            f"score={item['score']:.1f} | "
            f"{item['confidence'].upper()}"
        )

    summaries = [
        summarize(accepted, "Todos"),
        summarize(
            [
                item
                for item in accepted
                if item["type"] == "subida"
            ],
            "Subida",
        ),
        summarize(
            [
                item
                for item in accepted
                if item["type"] == "descida"
            ],
            "Descida",
        ),
    ]

    for year in (2024, 2025, 2026):
        summaries.append(
            summarize(
                [
                    item
                    for item in accepted
                    if item["year"] == year
                ],
                str(year),
            )
        )

    print()
    print("============================================")
    print("RESUMO DOS LAGS")
    print("============================================")
    print()

    for summary in summaries:
        if summary["n"] == 0:
            print(
                f"{summary['label']:<18} n=0"
            )
            continue

        print(
            f"{summary['label']:<18} "
            f"n={summary['n']:<3} "
            f"mediana={summary['median_h']:.1f} h "
            f"({summary['median_h']/24:.2f} d)  "
            f"IQR={summary['q25_h']:.1f}-"
            f"{summary['q75_h']:.1f} h"
        )

    result_fields = [
        "pair_id",
        "event_index",
        "type",
        "year",
        "barcelos_start",
        "barcelos_extremum",
        "barcelos_end",
        "barcelos_amplitude_cm",
        "barcelos_duration_h",
        "best_lag_h",
        "best_r",
        "shape_n",
        "plateau_low_h",
        "plateau_high_h",
        "plateau_width_h",
        "peak_prominence",
        "moura_response_start",
        "moura_response_extremum",
        "moura_amplitude_cm",
        "amplitude_ratio",
        "score",
        "confidence",
        "reason",
    ]

    rejected_fields = [
        field
        for field in result_fields
        if field != "pair_id"
    ]

    curve_fields = [
        "event_index",
        "type",
        "year",
        "barcelos_start",
        "lag_h",
        "r",
        "n",
    ]

    write_csv(
        ACCEPTED_CSV,
        accepted,
        result_fields,
    )

    write_csv(
        REJECTED_CSV,
        rejected,
        rejected_fields,
    )

    write_csv(
        CURVES_CSV,
        lag_rows,
        curve_fields,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SUMMARY_JSON.write_text(
        json.dumps(
            {
                "config": {
                    "min_lag_h": MIN_LAG_HOURS,
                    "max_lag_h": MAX_LAG_HOURS,
                    "min_shape_r": MIN_SHAPE_R,
                    "high_shape_r": HIGH_SHAPE_R,
                    "high_score": HIGH_SCORE,
                    "medium_score": MEDIUM_SCORE,
                    "min_amplitude_ratio":
                        MIN_AMPLITUDE_RATIO,
                    "max_amplitude_ratio":
                        MAX_AMPLITUDE_RATIO,
                },
                "counts": {
                    "events": len(events),
                    "accepted": len(accepted),
                    "rejected": len(rejected),
                    "confidence": counts,
                },
                "summaries": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Arquivos gerados:")
    print(ACCEPTED_CSV)
    print(REJECTED_CSV)
    print(CURVES_CSV)
    print(SUMMARY_JSON)
    print()
    print(
        "Teste histórico. Nenhum arquivo do painel foi alterado."
    )


if __name__ == "__main__":
    main()
