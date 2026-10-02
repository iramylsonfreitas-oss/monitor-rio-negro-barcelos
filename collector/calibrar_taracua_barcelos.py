import csv
import json
import math
import statistics

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

TARACUA = "14280001"
BARCELOS = "14480002"

# Eventos detectados em Taracuá usando delta 24h.
DETECT_WINDOW_HOURS = 24
THRESHOLD_CM_24H = 5.0
MAX_NEUTRAL_GAP_HOURS = 12
MIN_EVENT_DURATION_HOURS = 18
MIN_EVENT_AMPLITUDE_CM = 10.0

# Robustez multiescala.
CHANGE_WINDOWS = (12, 24, 48)

# Busca Taracuá -> Barcelos.
# Taracuá está mais a montante que Curicuriari.
MIN_LAG_HOURS = 6
MAX_LAG_HOURS = 336
LAG_STEP_HOURS = 1

# Não confiar em soluções grudadas nas bordas.
BOUNDARY_MARGIN_HOURS = 6

# Janela de comparação da forma da onda.
PRE_EVENT_HOURS = 12
POST_EVENT_HOURS = 24
MIN_COMPARE_HOURS = 48
MAX_COMPARE_HOURS = 120
MIN_SHAPE_SAMPLES = 18

# Critérios por escala.
MIN_SCALE_R = 0.50

# Critérios finais.
HIGH_MAX_LAG_SPREAD_H = 18
MEDIUM_MAX_LAG_SPREAD_H = 30
HIGH_MEAN_R = 0.70
MEDIUM_MEAN_R = 0.60

MIN_AMPLITUDE_RATIO = 0.15
MAX_AMPLITUDE_RATIO = 5.0

MIN_RESPONSE_SEPARATION_H = 36

OUTPUT_DIR = Path("artifacts")
ACCEPTED_CSV = OUTPUT_DIR / "taracua_barcelos_robustos.csv"
REJECTED_CSV = OUTPUT_DIR / "taracua_barcelos_rejeitados.csv"
SCALES_CSV = OUTPUT_DIR / "taracua_barcelos_escalas.csv"
SUMMARY_JSON = OUTPUT_DIR / "resumo_taracua_barcelos.json"


def parse_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def load_series():
    series = {TARACUA: {}, BARCELOS: {}}

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


def build_changes(station_series, hours):
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


def detect_source_events(station_series):
    changes = build_changes(
        station_series,
        DETECT_WINDOW_HOURS,
    )

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

        duration_h = (
            end - start
        ).total_seconds() / 3600

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


def event_compare_window(event):
    event_h = max(
        MIN_COMPARE_HOURS,
        min(
            MAX_COMPARE_HOURS,
            int(
                event["duration_h"]
                + PRE_EVENT_HOURS
                + POST_EVENT_HOURS
            ),
        ),
    )

    start = (
        event["start"]
        - timedelta(hours=PRE_EVENT_HOURS)
    )
    end = start + timedelta(hours=event_h)

    return start, end


def best_lag_for_scale(
    event,
    source_changes,
    target_changes,
):
    window_start, window_end = event_compare_window(event)

    best = None

    for lag_h in range(
        MIN_LAG_HOURS,
        MAX_LAG_HOURS + 1,
        LAG_STEP_HOURS,
    ):
        lag = timedelta(hours=lag_h)

        x = []
        y = []

        for timestamp, source_value in source_changes.items():
            if not (
                window_start <= timestamp <= window_end
            ):
                continue

            target_value = target_changes.get(timestamp + lag)

            if target_value is None:
                continue

            x.append(source_value)
            y.append(target_value)

        if len(x) < MIN_SHAPE_SAMPLES:
            continue

        corr = pearson(x, y)

        if corr is None:
            continue

        if best is None or corr > best["r"]:
            best = {
                "lag_h": lag_h,
                "r": corr,
                "n": len(x),
            }

    return best


def near_boundary(lag_h):
    return (
        lag_h <= MIN_LAG_HOURS + BOUNDARY_MARGIN_HOURS
        or lag_h >= MAX_LAG_HOURS - BOUNDARY_MARGIN_HOURS
    )


def response_amplitude(
    event,
    lag_h,
    target_levels,
):
    shifted_start = (
        event["start"]
        + timedelta(hours=lag_h)
    )
    shifted_end = (
        event["end"]
        + timedelta(hours=lag_h)
    )

    times = sorted(
        timestamp
        for timestamp in target_levels
        if shifted_start <= timestamp <= shifted_end
    )

    if not times:
        return None

    start_time = (
        shifted_start
        if shifted_start in target_levels
        else times[0]
    )

    start_level = target_levels[start_time]

    if event["direction"] == 1:
        extremum_time = max(
            times,
            key=lambda t: target_levels[t],
        )
        amplitude = (
            target_levels[extremum_time]
            - start_level
        )
    else:
        extremum_time = min(
            times,
            key=lambda t: target_levels[t],
        )
        amplitude = (
            start_level
            - target_levels[extremum_time]
        )

    return {
        "response_start": start_time,
        "response_extremum": extremum_time,
        "response_amplitude_cm": amplitude,
    }


def evaluate_event(
    event,
    changes_by_scale,
    target_levels,
):
    scale_results = []

    for window_h in CHANGE_WINDOWS:
        source_changes = changes_by_scale[window_h][TARACUA]
        target_changes = changes_by_scale[window_h][BARCELOS]

        best = best_lag_for_scale(
            event,
            source_changes,
            target_changes,
        )

        if best is None:
            scale_results.append(
                {
                    "window_h": window_h,
                    "valid": False,
                    "reason": "sem_amostras",
                }
            )
            continue

        boundary = near_boundary(best["lag_h"])

        valid = (
            best["r"] >= MIN_SCALE_R
            and not boundary
        )

        reason = ""

        if best["r"] < MIN_SCALE_R:
            reason = "correlacao_baixa"
        elif boundary:
            reason = "lag_na_borda"

        scale_results.append(
            {
                "window_h": window_h,
                "valid": valid,
                "reason": reason,
                "lag_h": best["lag_h"],
                "r": best["r"],
                "n": best["n"],
                "boundary": boundary,
            }
        )

    valid_scales = [
        item
        for item in scale_results
        if item.get("valid")
    ]

    result = {
        "event_index": event["event_index"],
        "type": event["type"],
        "year": event["start"].year,
        "taracua_start": event["start"],
        "taracua_extremum": event["extremum_time"],
        "taracua_end": event["end"],
        "taracua_amplitude_cm": event["amplitude_cm"],
        "taracua_duration_h": event["duration_h"],
        "scales_valid": len(valid_scales),
    }

    if len(valid_scales) < 2:
        result.update(
            {
                "accepted": False,
                "confidence": "rejeitado",
                "reason": "menos_de_2_escalas_validas",
            }
        )
        return result, scale_results

    lags = [
        item["lag_h"]
        for item in valid_scales
    ]

    correlations = [
        item["r"]
        for item in valid_scales
    ]

    median_lag = statistics.median(lags)
    lag_spread = max(lags) - min(lags)
    mean_r = statistics.mean(correlations)

    response = response_amplitude(
        event,
        median_lag,
        target_levels,
    )

    if response is None:
        result.update(
            {
                "accepted": False,
                "confidence": "rejeitado",
                "reason": "sem_resposta_nivel",
                "median_lag_h": median_lag,
                "lag_spread_h": lag_spread,
                "mean_r": mean_r,
            }
        )
        return result, scale_results

    amplitude_ratio = (
        response["response_amplitude_cm"]
        / event["amplitude_cm"]
        if event["amplitude_cm"] > 0
        else math.nan
    )

    amplitude_ok = (
        response["response_amplitude_cm"] > 0
        and MIN_AMPLITUDE_RATIO
        <= amplitude_ratio
        <= MAX_AMPLITUDE_RATIO
    )

    all_three = len(valid_scales) == 3

    if (
        all_three
        and lag_spread <= HIGH_MAX_LAG_SPREAD_H
        and mean_r >= HIGH_MEAN_R
        and amplitude_ok
    ):
        confidence = "alta"
        accepted = True
        reason = ""
    elif (
        lag_spread <= MEDIUM_MAX_LAG_SPREAD_H
        and mean_r >= MEDIUM_MEAN_R
        and amplitude_ok
    ):
        confidence = "media"
        accepted = True
        reason = ""
    else:
        confidence = "rejeitado"
        accepted = False

        reasons = []

        if lag_spread > MEDIUM_MAX_LAG_SPREAD_H:
            reasons.append("lags_inconsistentes")

        if mean_r < MEDIUM_MEAN_R:
            reasons.append("correlacao_media_baixa")

        if not amplitude_ok:
            reasons.append("amplitude_incompativel")

        reason = ",".join(reasons) or "criterios_nao_atendidos"

    result.update(
        {
            "accepted": accepted,
            "confidence": confidence,
            "reason": reason,
            "median_lag_h": median_lag,
            "lag_spread_h": lag_spread,
            "mean_r": mean_r,
            "barcelos_response_start": response["response_start"],
            "barcelos_response_extremum": response["response_extremum"],
            "barcelos_amplitude_cm": response["response_amplitude_cm"],
            "amplitude_ratio": amplitude_ratio,
            "lag_12h": next(
                (
                    item.get("lag_h")
                    for item in scale_results
                    if item["window_h"] == 12 and item.get("valid")
                ),
                None,
            ),
            "r_12h": next(
                (
                    item.get("r")
                    for item in scale_results
                    if item["window_h"] == 12 and item.get("valid")
                ),
                None,
            ),
            "lag_24h": next(
                (
                    item.get("lag_h")
                    for item in scale_results
                    if item["window_h"] == 24 and item.get("valid")
                ),
                None,
            ),
            "r_24h": next(
                (
                    item.get("r")
                    for item in scale_results
                    if item["window_h"] == 24 and item.get("valid")
                ),
                None,
            ),
            "lag_48h": next(
                (
                    item.get("lag_h")
                    for item in scale_results
                    if item["window_h"] == 48 and item.get("valid")
                ),
                None,
            ),
            "r_48h": next(
                (
                    item.get("r")
                    for item in scale_results
                    if item["window_h"] == 48 and item.get("valid")
                ),
                None,
            ),
        }
    )

    return result, scale_results


def deduplicate(results):
    accepted = [
        item
        for item in results
        if item["accepted"]
    ]

    accepted.sort(
        key=lambda item: (
            1 if item["confidence"] == "alta" else 0,
            item.get("mean_r", 0),
            -item.get("lag_spread_h", 999),
        ),
        reverse=True,
    )

    selected = []
    duplicate_rejects = []

    for item in accepted:
        conflict = False

        for chosen in selected:
            if item["type"] != chosen["type"]:
                continue

            diff_h = abs(
                (
                    item["barcelos_response_start"]
                    - chosen["barcelos_response_start"]
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
            copy["reason"] = "resposta_barcelos_duplicada"
            duplicate_rejects.append(copy)
        else:
            selected.append(item)

    selected.sort(
        key=lambda item: item["taracua_start"]
    )

    for index, item in enumerate(selected, start=1):
        item["pair_id"] = index

    return selected, duplicate_rejects


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
        return {
            "label": label,
            "n": 0,
        }

    lags = [
        item["median_lag_h"]
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
            row = {
                key: format_dt(value)
                for key, value in item.items()
            }

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

    taracua_levels = series[TARACUA]
    barcelos_levels = series[BARCELOS]

    if not taracua_levels or not barcelos_levels:
        raise RuntimeError(
            "Histórico de Taracuá ou Barcelos ausente."
        )

    events = detect_source_events(
        taracua_levels
    )

    changes_by_scale = {}

    for window_h in CHANGE_WINDOWS:
        changes_by_scale[window_h] = {
            TARACUA: build_changes(
                taracua_levels,
                window_h,
            ),
            BARCELOS: build_changes(
                barcelos_levels,
                window_h,
            ),
        }

    results = []
    scale_rows = []

    for event in events:
        result, scales = evaluate_event(
            event,
            changes_by_scale,
            barcelos_levels,
        )

        results.append(result)

        for scale in scales:
            scale_rows.append(
                {
                    "event_index": event["event_index"],
                    "type": event["type"],
                    "year": event["start"].year,
                    "taracua_start": event["start"],
                    **scale,
                }
            )

    accepted, duplicate_rejects = deduplicate(results)

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
    print("TARACUA -> BARCELOS")
    print("CALIBRAÇÃO PREDITIVA MULTIESCALA")
    print("============================================")
    print()
    print("Eventos Taracuá:", len(events))
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
    print("EVENTOS ROBUSTOS")
    print("============================================")
    print()

    for item in accepted:
        print(
            f"#{item['pair_id']:02d} "
            f"{item['type']:<7} "
            f"T {item['taracua_start']:%Y-%m-%d %H:%M} | "
            f"12h={item.get('lag_12h')} "
            f"24h={item.get('lag_24h')} "
            f"48h={item.get('lag_48h')} | "
            f"mediana={item['median_lag_h']:.0f} h "
            f"({item['median_lag_h']/24:.2f} d) | "
            f"spread={item['lag_spread_h']:.0f} h | "
            f"r médio={item['mean_r']:.3f} | "
            f"{item['confidence'].upper()}"
        )

    print()
    print("============================================")
    print("RESUMO")
    print("============================================")
    print()

    for summary in summaries:
        if summary["n"] == 0:
            print(f"{summary['label']:<18} n=0")
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
        "taracua_start",
        "taracua_extremum",
        "taracua_end",
        "taracua_amplitude_cm",
        "taracua_duration_h",
        "scales_valid",
        "lag_12h",
        "r_12h",
        "lag_24h",
        "r_24h",
        "lag_48h",
        "r_48h",
        "median_lag_h",
        "lag_spread_h",
        "mean_r",
        "barcelos_response_start",
        "barcelos_response_extremum",
        "barcelos_amplitude_cm",
        "amplitude_ratio",
        "confidence",
        "reason",
    ]

    rejected_fields = [
        field
        for field in result_fields
        if field != "pair_id"
    ]

    scale_fields = [
        "event_index",
        "type",
        "year",
        "taracua_start",
        "window_h",
        "valid",
        "reason",
        "lag_h",
        "r",
        "n",
        "boundary",
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
        SCALES_CSV,
        scale_rows,
        scale_fields,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SUMMARY_JSON.write_text(
        json.dumps(
            {
                "route": {
                    "source": {
                        "code": TARACUA,
                        "name": "Taracua",
                    },
                    "target": {
                        "code": BARCELOS,
                        "name": "Barcelos",
                    },
                },
                "config": {
                    "change_windows": CHANGE_WINDOWS,
                    "min_lag_h": MIN_LAG_HOURS,
                    "max_lag_h": MAX_LAG_HOURS,
                    "boundary_margin_h": BOUNDARY_MARGIN_HOURS,
                    "min_scale_r": MIN_SCALE_R,
                    "high_max_lag_spread_h":
                        HIGH_MAX_LAG_SPREAD_H,
                    "medium_max_lag_spread_h":
                        MEDIUM_MAX_LAG_SPREAD_H,
                    "high_mean_r": HIGH_MEAN_R,
                    "medium_mean_r": MEDIUM_MEAN_R,
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
    print(SCALES_CSV)
    print(SUMMARY_JSON)
    print()
    print(
        "Calibração histórica. Nenhum arquivo do painel foi alterado."
    )


if __name__ == "__main__":
    main()
