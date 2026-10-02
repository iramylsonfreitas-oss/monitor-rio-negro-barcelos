import csv
import json
import math
import statistics

from datetime import datetime, timedelta
from pathlib import Path


HISTORY_FILE = Path("data/history/hourly.csv")

BARCELOS = "14480002"
MOURA = "14840000"

# Detector de eventos
CHANGE_WINDOW_HOURS = 24
THRESHOLD_CM_24H = 5.0
MAX_NEUTRAL_GAP_HOURS = 12
MIN_EVENT_DURATION_HOURS = 18
MIN_EVENT_AMPLITUDE_CM = 10.0

# Janela plausível de resposta Barcelos -> Moura
MIN_LAG_HOURS = 24
MAX_LAG_HOURS = 168

# Regras de coerência
MAX_START_EXTREMUM_DIFF_H = 48
MIN_AMPLITUDE_RATIO = 0.25
MAX_AMPLITUDE_RATIO = 4.00
MIN_DURATION_RATIO = 0.33
MAX_DURATION_RATIO = 3.00

# Forma da onda
SHAPE_SEARCH_RADIUS_H = 18
SHAPE_MIN_SAMPLES = 12
MIN_SHAPE_CORRELATION = 0.25

# Pareamento
MIN_PAIR_SCORE = 50.0
HIGH_CONFIDENCE_SCORE = 75.0
MEDIUM_CONFIDENCE_SCORE = 60.0

OUTPUT_DIR = Path("artifacts")
PAIRS_CSV = OUTPUT_DIR / "eventos_barcelos_moura_v2.csv"
CANDIDATES_CSV = OUTPUT_DIR / "candidatos_barcelos_moura_v2.csv"
SUMMARY_JSON = OUTPUT_DIR / "resumo_eventos_barcelos_moura_v2.json"


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


def build_changes(station_series):
    changes = {}
    delta = timedelta(hours=CHANGE_WINDOW_HOURS)

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

        duration_h = (end - start).total_seconds() / 3600

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

    for index, event in enumerate(events, start=1):
        event["event_index"] = index

    return events


def hours_between(start, end):
    return (end - start).total_seconds() / 3600


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


def shape_correlation(
    b_event,
    b_changes,
    m_changes,
    center_lag_h,
):
    best = None

    search_start = int(
        max(
            MIN_LAG_HOURS,
            round(center_lag_h) - SHAPE_SEARCH_RADIUS_H,
        )
    )
    search_end = int(
        min(
            MAX_LAG_HOURS,
            round(center_lag_h) + SHAPE_SEARCH_RADIUS_H,
        )
    )

    for lag_h in range(search_start, search_end + 1):
        lag = timedelta(hours=lag_h)

        x = []
        y = []

        for timestamp, value in b_changes.items():
            if not (
                b_event["start"]
                <= timestamp
                <= b_event["end"]
            ):
                continue

            moura_value = m_changes.get(timestamp + lag)
            if moura_value is None:
                continue

            x.append(value)
            y.append(moura_value)

        if len(x) < SHAPE_MIN_SAMPLES:
            continue

        corr = pearson(x, y)
        if corr is None:
            continue

        item = {
            "shape_lag_h": lag_h,
            "shape_r": corr,
            "shape_n": len(x),
        }

        if best is None or corr > best["shape_r"]:
            best = item

    return best


def ratio_score(ratio):
    if ratio <= 0:
        return 0.0

    # Simétrico em escala logarítmica:
    # razão 1,0 recebe 1; diferenças crescentes perdem peso.
    return math.exp(-abs(math.log(ratio)))


def lag_consistency_score(start_lag_h, extremum_lag_h):
    difference = abs(start_lag_h - extremum_lag_h)

    if difference >= MAX_START_EXTREMUM_DIFF_H:
        return 0.0

    return 1.0 - (
        difference / MAX_START_EXTREMUM_DIFF_H
    )


def shape_lag_agreement_score(shape_lag_h, center_lag_h):
    difference = abs(shape_lag_h - center_lag_h)

    if difference >= SHAPE_SEARCH_RADIUS_H:
        return 0.0

    return 1.0 - (
        difference / SHAPE_SEARCH_RADIUS_H
    )


def build_candidate(
    b_event,
    m_event,
    b_changes,
    m_changes,
):
    if b_event["direction"] != m_event["direction"]:
        return None

    start_lag_h = hours_between(
        b_event["start"],
        m_event["start"],
    )

    extremum_lag_h = hours_between(
        b_event["extremum_time"],
        m_event["extremum_time"],
    )

    if not (
        MIN_LAG_HOURS
        <= start_lag_h
        <= MAX_LAG_HOURS
    ):
        return None

    if not (
        MIN_LAG_HOURS
        <= extremum_lag_h
        <= MAX_LAG_HOURS
    ):
        return None

    if (
        abs(start_lag_h - extremum_lag_h)
        > MAX_START_EXTREMUM_DIFF_H
    ):
        return None

    amplitude_ratio = (
        m_event["amplitude_cm"]
        / b_event["amplitude_cm"]
    )

    duration_ratio = (
        m_event["duration_h"]
        / b_event["duration_h"]
        if b_event["duration_h"] > 0
        else math.nan
    )

    if not (
        MIN_AMPLITUDE_RATIO
        <= amplitude_ratio
        <= MAX_AMPLITUDE_RATIO
    ):
        return None

    if not (
        MIN_DURATION_RATIO
        <= duration_ratio
        <= MAX_DURATION_RATIO
    ):
        return None

    center_lag_h = (
        start_lag_h + extremum_lag_h
    ) / 2.0

    shape = shape_correlation(
        b_event,
        b_changes,
        m_changes,
        center_lag_h,
    )

    if shape is None:
        return None

    if shape["shape_r"] < MIN_SHAPE_CORRELATION:
        return None

    shape_score = max(
        0.0,
        min(1.0, shape["shape_r"]),
    )

    lag_score = lag_consistency_score(
        start_lag_h,
        extremum_lag_h,
    )

    amplitude_score = ratio_score(
        amplitude_ratio
    )

    duration_score = ratio_score(
        duration_ratio
    )

    shape_lag_score = shape_lag_agreement_score(
        shape["shape_lag_h"],
        center_lag_h,
    )

    total_score = (
        45.0 * shape_score
        + 20.0 * lag_score
        + 15.0 * amplitude_score
        + 10.0 * duration_score
        + 10.0 * shape_lag_score
    )

    return {
        "barcelos_event_index": b_event["event_index"],
        "moura_event_index": m_event["event_index"],
        "type": b_event["type"],
        "year": b_event["start"].year,
        "barcelos_start": b_event["start"],
        "barcelos_extremum": b_event["extremum_time"],
        "barcelos_end": b_event["end"],
        "barcelos_amplitude_cm": b_event["amplitude_cm"],
        "barcelos_duration_h": b_event["duration_h"],
        "moura_start": m_event["start"],
        "moura_extremum": m_event["extremum_time"],
        "moura_end": m_event["end"],
        "moura_amplitude_cm": m_event["amplitude_cm"],
        "moura_duration_h": m_event["duration_h"],
        "start_lag_h": start_lag_h,
        "extremum_lag_h": extremum_lag_h,
        "center_lag_h": center_lag_h,
        "shape_lag_h": shape["shape_lag_h"],
        "shape_r": shape["shape_r"],
        "shape_n": shape["shape_n"],
        "amplitude_ratio": amplitude_ratio,
        "duration_ratio": duration_ratio,
        "score": total_score,
    }


def generate_candidates(
    barcelos_events,
    moura_events,
    b_changes,
    m_changes,
):
    candidates = []

    for b_event in barcelos_events:
        for m_event in moura_events:
            candidate = build_candidate(
                b_event,
                m_event,
                b_changes,
                m_changes,
            )

            if candidate is not None:
                candidates.append(candidate)

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return candidates


def confidence(score):
    if score >= HIGH_CONFIDENCE_SCORE:
        return "alta"

    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "media"

    return "baixa"


def global_one_to_one_match(candidates):
    selected = []
    used_barcelos = set()
    used_moura = set()

    for candidate in candidates:
        if candidate["score"] < MIN_PAIR_SCORE:
            continue

        b_index = candidate["barcelos_event_index"]
        m_index = candidate["moura_event_index"]

        if b_index in used_barcelos:
            continue

        if m_index in used_moura:
            continue

        item = dict(candidate)
        item["confidence"] = confidence(
            item["score"]
        )
        item["pair_id"] = len(selected) + 1

        selected.append(item)
        used_barcelos.add(b_index)
        used_moura.add(m_index)

    selected.sort(
        key=lambda item: item["barcelos_start"]
    )

    for index, item in enumerate(selected, start=1):
        item["pair_id"] = index

    return selected


def percentile(values, fraction):
    values = sorted(values)

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return values[lower]

    weight = position - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def summarize(pairs, label):
    usable = [
        pair
        for pair in pairs
        if pair["confidence"] in ("alta", "media")
    ]

    if not usable:
        return {"label": label, "n": 0}

    lags = [
        pair["shape_lag_h"]
        for pair in usable
    ]

    return {
        "label": label,
        "n": len(usable),
        "median_h": statistics.median(lags),
        "q25_h": percentile(lags, 0.25),
        "q75_h": percentile(lags, 0.75),
        "mean_h": statistics.mean(lags),
        "min_h": min(lags),
        "max_h": max(lags),
    }


def format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


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

            for key in (
                "barcelos_start",
                "barcelos_extremum",
                "barcelos_end",
                "moura_start",
                "moura_extremum",
                "moura_end",
            ):
                if key in row:
                    row[key] = format_dt(row[key])

            writer.writerow(
                {
                    field: row.get(field)
                    for field in fields
                }
            )


def print_summary(item):
    if item["n"] == 0:
        print(f"{item['label']:<18} n=0")
        return

    print(
        f"{item['label']:<18} "
        f"n={item['n']:<3} "
        f"mediana={item['median_h']:.1f} h "
        f"({item['median_h']/24:.2f} d)  "
        f"IQR={item['q25_h']:.1f}-"
        f"{item['q75_h']:.1f} h"
    )


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

    b_changes = build_changes(
        series[BARCELOS]
    )

    m_changes = build_changes(
        series[MOURA]
    )

    candidates = generate_candidates(
        barcelos_events,
        moura_events,
        b_changes,
        m_changes,
    )

    pairs = global_one_to_one_match(
        candidates
    )

    print()
    print("============================================")
    print("EVENTOS BARCELOS -> MOURA V2")
    print("PAREAMENTO POR SIMILARIDADE")
    print("============================================")
    print()
    print(
        "Eventos Barcelos:",
        len(barcelos_events),
    )
    print(
        "Eventos Moura:",
        len(moura_events),
    )
    print(
        "Candidatos coerentes:",
        len(candidates),
    )
    print(
        "Pares selecionados:",
        len(pairs),
    )
    print(
        "Janela plausível:",
        f"{MIN_LAG_HOURS}-{MAX_LAG_HOURS} h",
    )
    print()

    counts = {
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
        f"alta={counts['alta']}",
        f"media={counts['media']}",
        f"baixa={counts['baixa']}",
    )

    print()
    print("============================================")
    print("PARES SELECIONADOS")
    print("============================================")
    print()

    for pair in pairs:
        print(
            f"#{pair['pair_id']:02d} "
            f"{pair['type']:<7} "
            f"B {pair['barcelos_start']:%Y-%m-%d %H:%M} -> "
            f"M {pair['moura_start']:%Y-%m-%d %H:%M} | "
            f"lag forma={pair['shape_lag_h']:>3} h | "
            f"início={pair['start_lag_h']:.0f} h | "
            f"extremo={pair['extremum_lag_h']:.0f} h | "
            f"r={pair['shape_r']:.3f} | "
            f"score={pair['score']:.1f} | "
            f"{pair['confidence'].upper()}"
        )

    summaries = []

    summaries.append(
        summarize(
            pairs,
            "Todos",
        )
    )

    for event_type in (
        "subida",
        "descida",
    ):
        summaries.append(
            summarize(
                [
                    pair
                    for pair in pairs
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
            summarize(
                [
                    pair
                    for pair in pairs
                    if pair["year"] == year
                ],
                str(year),
            )
        )

    print()
    print("============================================")
    print("RESUMO DA DEFASAGEM PELA FORMA DA ONDA")
    print("============================================")
    print()

    for item in summaries:
        print_summary(item)

    pair_fields = [
        "pair_id",
        "barcelos_event_index",
        "moura_event_index",
        "type",
        "year",
        "barcelos_start",
        "barcelos_extremum",
        "barcelos_end",
        "barcelos_amplitude_cm",
        "barcelos_duration_h",
        "moura_start",
        "moura_extremum",
        "moura_end",
        "moura_amplitude_cm",
        "moura_duration_h",
        "start_lag_h",
        "extremum_lag_h",
        "center_lag_h",
        "shape_lag_h",
        "shape_r",
        "shape_n",
        "amplitude_ratio",
        "duration_ratio",
        "score",
        "confidence",
    ]

    candidate_fields = [
        "barcelos_event_index",
        "moura_event_index",
        "type",
        "year",
        "barcelos_start",
        "moura_start",
        "start_lag_h",
        "extremum_lag_h",
        "center_lag_h",
        "shape_lag_h",
        "shape_r",
        "shape_n",
        "amplitude_ratio",
        "duration_ratio",
        "score",
    ]

    write_csv(
        PAIRS_CSV,
        pairs,
        pair_fields,
    )

    write_csv(
        CANDIDATES_CSV,
        candidates,
        candidate_fields,
    )

    result = {
        "config": {
            "change_window_hours": CHANGE_WINDOW_HOURS,
            "threshold_cm_24h": THRESHOLD_CM_24H,
            "min_lag_hours": MIN_LAG_HOURS,
            "max_lag_hours": MAX_LAG_HOURS,
            "max_start_extremum_diff_h":
                MAX_START_EXTREMUM_DIFF_H,
            "min_shape_correlation":
                MIN_SHAPE_CORRELATION,
            "min_pair_score":
                MIN_PAIR_SCORE,
        },
        "counts": {
            "barcelos_events":
                len(barcelos_events),
            "moura_events":
                len(moura_events),
            "candidates":
                len(candidates),
            "pairs":
                len(pairs),
            "confidence":
                counts,
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
    print(PAIRS_CSV)
    print(CANDIDATES_CSV)
    print(SUMMARY_JSON)
    print()
    print(
        "Teste histórico. Nenhum arquivo do painel foi alterado."
    )


if __name__ == "__main__":
    main()
