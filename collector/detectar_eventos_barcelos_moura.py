import csv
import json
import math
import statistics

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

BARCELOS = "14480002"
MOURA = "14840000"

# Detector de evento
CHANGE_WINDOW_HOURS = 24
THRESHOLD_CM_24H = 5.0
MAX_NEUTRAL_GAP_HOURS = 12
MIN_EVENT_DURATION_HOURS = 18
MIN_EVENT_AMPLITUDE_CM = 10.0

# Pareamento Barcelos -> Moura
MIN_LAG_HOURS = 24
MAX_LAG_HOURS = 240

OUTPUT_DIR = Path("artifacts")
EVENTS_CSV = OUTPUT_DIR / "eventos_barcelos_moura.csv"
SUMMARY_JSON = OUTPUT_DIR / "resumo_eventos_barcelos_moura.json"


def parse_datetime(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def load_series():
    series = {
        BARCELOS: {},
        MOURA: {},
    }

    with HISTORY_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
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


def build_changes(station_series):
    changes = {}
    delta = timedelta(hours=CHANGE_WINDOW_HOURS)

    for timestamp, level in station_series.items():
        previous = station_series.get(timestamp - delta)

        if previous is None:
            continue

        changes[timestamp] = level - previous

    return changes


def classify(change):
    if change >= THRESHOLD_CM_24H:
        return 1

    if change <= -THRESHOLD_CM_24H:
        return -1

    return 0


def detect_events(station_series, station_name):
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

        duration_h = (
            end - start
        ).total_seconds() / 3600

        if duration_h < MIN_EVENT_DURATION_HOURS:
            current = None
            return

        relevant_times = sorted(
            timestamp
            for timestamp in station_series
            if start <= timestamp <= end
        )

        if not relevant_times:
            current = None
            return

        start_level = station_series.get(start)

        if start_level is None:
            current = None
            return

        if direction == 1:
            extremum_time = max(
                relevant_times,
                key=lambda t: station_series[t],
            )
        else:
            extremum_time = min(
                relevant_times,
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
                "station": station_name,
                "direction": direction,
                "type": (
                    "subida"
                    if direction == 1
                    else "descida"
                ),
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

        # Mudança real de direção.
        close_current()

        current = {
            "direction": state,
            "start": timestamp,
            "last_active": timestamp,
        }

    close_current()

    return events


def hours_between(start, end):
    return (
        end - start
    ).total_seconds() / 3600


def confidence_for_pair(
    lag_start_h,
    lag_extremum_h,
    amplitude_ratio,
):
    if not (
        MIN_LAG_HOURS
        <= lag_extremum_h
        <= MAX_LAG_HOURS
    ):
        return "baixa"

    lag_difference = abs(
        lag_start_h - lag_extremum_h
    )

    amplitude_ok = (
        0.30 <= amplitude_ratio <= 3.00
    )

    if (
        lag_difference <= 48
        and amplitude_ok
    ):
        return "alta"

    if (
        lag_difference <= 96
        and 0.15 <= amplitude_ratio <= 5.00
    ):
        return "media"

    return "baixa"


def pair_events(barcelos_events, moura_events):
    pairs = []
    used_moura = set()

    for b_index, b_event in enumerate(barcelos_events):
        candidates = []

        for m_index, m_event in enumerate(moura_events):
            if m_index in used_moura:
                continue

            if (
                m_event["direction"]
                != b_event["direction"]
            ):
                continue

            lag_start_h = hours_between(
                b_event["start"],
                m_event["start"],
            )

            if (
                lag_start_h < MIN_LAG_HOURS
                or lag_start_h > MAX_LAG_HOURS
            ):
                continue

            candidates.append(
                (
                    lag_start_h,
                    m_index,
                    m_event,
                )
            )

        if not candidates:
            continue

        # Pareamento objetivo: primeiro evento equivalente
        # observado em Moura após a janela mínima.
        candidates.sort(
            key=lambda item: item[0]
        )

        lag_start_h, m_index, m_event = (
            candidates[0]
        )

        used_moura.add(m_index)

        lag_extremum_h = hours_between(
            b_event["extremum_time"],
            m_event["extremum_time"],
        )

        amplitude_ratio = (
            m_event["amplitude_cm"]
            / b_event["amplitude_cm"]
            if b_event["amplitude_cm"] != 0
            else math.nan
        )

        confidence = confidence_for_pair(
            lag_start_h,
            lag_extremum_h,
            amplitude_ratio,
        )

        pairs.append(
            {
                "event_id": len(pairs) + 1,
                "type": b_event["type"],
                "barcelos_start": b_event["start"],
                "barcelos_extremum": b_event[
                    "extremum_time"
                ],
                "barcelos_amplitude_cm": b_event[
                    "amplitude_cm"
                ],
                "moura_start": m_event["start"],
                "moura_extremum": m_event[
                    "extremum_time"
                ],
                "moura_amplitude_cm": m_event[
                    "amplitude_cm"
                ],
                "lag_start_h": lag_start_h,
                "lag_extremum_h": lag_extremum_h,
                "amplitude_ratio": amplitude_ratio,
                "confidence": confidence,
                "year": b_event["start"].year,
            }
        )

    return pairs


def percentile(values, fraction):
    values = sorted(values)

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (
        len(values) - 1
    ) * fraction

    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return values[lower]

    weight = position - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def summarize_pairs(pairs, label):
    usable = [
        pair
        for pair in pairs
        if pair["confidence"]
        in ("alta", "media")
    ]

    if not usable:
        return {
            "label": label,
            "n": 0,
        }

    lags = [
        pair["lag_start_h"]
        for pair in usable
    ]

    return {
        "label": label,
        "n": len(usable),
        "median_h": statistics.median(lags),
        "q25_h": percentile(lags, 0.25),
        "q75_h": percentile(lags, 0.75),
        "min_h": min(lags),
        "max_h": max(lags),
        "mean_h": statistics.mean(lags),
    }


def print_summary(summary):
    label = summary["label"]
    n = summary["n"]

    if not n:
        print(
            f"{label:<22} n=0"
        )
        return

    print(
        f"{label:<22} "
        f"n={n:<3} "
        f"mediana={summary['median_h']:.1f} h "
        f"({summary['median_h']/24:.2f} d)  "
        f"IQR={summary['q25_h']:.1f}-"
        f"{summary['q75_h']:.1f} h"
    )


def write_csv(pairs):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "event_id",
        "type",
        "year",
        "barcelos_start",
        "barcelos_extremum",
        "barcelos_amplitude_cm",
        "moura_start",
        "moura_extremum",
        "moura_amplitude_cm",
        "lag_start_h",
        "lag_extremum_h",
        "amplitude_ratio",
        "confidence",
    ]

    with EVENTS_CSV.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for pair in pairs:
            row = dict(pair)

            for key in (
                "barcelos_start",
                "barcelos_extremum",
                "moura_start",
                "moura_extremum",
            ):
                row[key] = row[key].strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            writer.writerow(row)


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError(
            "data/history/hourly.csv não encontrado."
        )

    series = load_series()

    barcelos_events = detect_events(
        series[BARCELOS],
        "Barcelos",
    )

    moura_events = detect_events(
        series[MOURA],
        "Moura",
    )

    pairs = pair_events(
        barcelos_events,
        moura_events,
    )

    print()
    print("============================================")
    print("EVENTOS BARCELOS -> MOURA")
    print("============================================")
    print()
    print(
        "Detector:",
        f"|delta 24h| >= {THRESHOLD_CM_24H:.0f} cm",
    )
    print(
        "Evento mínimo:",
        f"{MIN_EVENT_DURATION_HOURS} h e "
        f"{MIN_EVENT_AMPLITUDE_CM:.0f} cm",
    )
    print(
        "Janela de resposta:",
        f"{MIN_LAG_HOURS}-{MAX_LAG_HOURS} h",
    )
    print()
    print(
        "Eventos detectados em Barcelos:",
        len(barcelos_events),
    )
    print(
        "Eventos detectados em Moura:",
        len(moura_events),
    )
    print(
        "Pares encontrados:",
        len(pairs),
    )

    confidence_counts = {
        level: sum(
            1
            for pair in pairs
            if pair["confidence"] == level
        )
        for level in (
            "alta",
            "media",
            "baixa",
        )
    }

    print(
        "Confiança:",
        "alta=",
        confidence_counts["alta"],
        "media=",
        confidence_counts["media"],
        "baixa=",
        confidence_counts["baixa"],
    )

    print()
    print("============================================")
    print("PARES DE EVENTOS")
    print("============================================")
    print()

    for pair in pairs:
        print(
            f"#{pair['event_id']:02d} "
            f"{pair['type']:<7} "
            f"{pair['barcelos_start']:%Y-%m-%d %H:%M} -> "
            f"{pair['moura_start']:%Y-%m-%d %H:%M}  "
            f"lag início={pair['lag_start_h']:.0f} h  "
            f"lag extremo={pair['lag_extremum_h']:.0f} h  "
            f"amp B={pair['barcelos_amplitude_cm']:.0f} cm  "
            f"amp M={pair['moura_amplitude_cm']:.0f} cm  "
            f"{pair['confidence'].upper()}"
        )

    summaries = []

    usable_pairs = [
        pair
        for pair in pairs
        if pair["confidence"]
        in ("alta", "media")
    ]

    summaries.append(
        summarize_pairs(
            usable_pairs,
            "Todos",
        )
    )

    for event_type in (
        "subida",
        "descida",
    ):
        summaries.append(
            summarize_pairs(
                [
                    pair
                    for pair in usable_pairs
                    if pair["type"]
                    == event_type
                ],
                event_type.capitalize(),
            )
        )

    for year in (
        2024,
        2025,
        2026,
    ):
        summaries.append(
            summarize_pairs(
                [
                    pair
                    for pair in usable_pairs
                    if pair["year"] == year
                ],
                str(year),
            )
        )

    print()
    print("============================================")
    print("RESUMO DA DEFASAGEM DE INÍCIO")
    print("============================================")
    print()

    for summary in summaries:
        print_summary(summary)

    write_csv(pairs)

    result = {
        "config": {
            "change_window_hours": CHANGE_WINDOW_HOURS,
            "threshold_cm_24h": THRESHOLD_CM_24H,
            "max_neutral_gap_hours": MAX_NEUTRAL_GAP_HOURS,
            "min_event_duration_hours": MIN_EVENT_DURATION_HOURS,
            "min_event_amplitude_cm": MIN_EVENT_AMPLITUDE_CM,
            "min_lag_hours": MIN_LAG_HOURS,
            "max_lag_hours": MAX_LAG_HOURS,
        },
        "event_counts": {
            "barcelos": len(barcelos_events),
            "moura": len(moura_events),
            "pairs": len(pairs),
            "confidence": confidence_counts,
        },
        "summaries": summaries,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SUMMARY_JSON.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Arquivos gerados:")
    print(EVENTS_CSV)
    print(SUMMARY_JSON)
    print()
    print(
        "Teste histórico: não altera nenhum arquivo do painel."
    )


if __name__ == "__main__":
    main()
