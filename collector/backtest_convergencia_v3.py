import bisect
import csv
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY_FILE = Path("data/history/hourly.csv")
OUTPUT_DIR = Path("artifacts")

ALERTS_CSV = OUTPUT_DIR / "backtest_v3_alertas.csv"
TARGETS_CSV = OUTPUT_DIR / "backtest_v3_eventos_barcelos.csv"
METRICS_CSV = OUTPUT_DIR / "backtest_v3_metricas.csv"
SUMMARY_JSON = OUTPUT_DIR / "backtest_v3_resumo.json"

CORE = {
    "14280001": {
        "nome": "Taracua",
        "lag_mediano_h": 193.5,
        "lag_q25_h": 168.5,
        "lag_q75_h": 230.5,
    },
    "14330000": {
        "nome": "Curicuriari",
        "lag_mediano_h": 140.0,
        "lag_q25_h": 119.5,
        "lag_q75_h": 165.0,
    },
    "14420000": {
        "nome": "Serrinha",
        "lag_mediano_h": 87.5,
        "lag_q25_h": 70.8,
        "lag_q75_h": 118.5,
    },
}
ORDER = ["14280001", "14330000", "14420000"]
BARCELOS = "14480002"

SEGMENTS = {
    ("14280001", "14330000"): {
        "nome": "Taracua -> Curicuriari",
        "mediana_h": 58.0,
        "q25_h": 44.2,
        "q75_h": 77.5,
    },
    ("14330000", "14420000"): {
        "nome": "Curicuriari -> Serrinha",
        "mediana_h": 59.5,
        "q25_h": 55.5,
        "q75_h": 72.2,
    },
}

# Mesmos critérios operacionais da V3.
RISE_THRESHOLD_CM = 5.0
MAX_ACTIVE_GAP_H = 36
MAX_RECENT_EVENT_AGE_H = 168
SEGMENT_TOLERANCE_H = 24.0

STRONG_24H_CM = 5.0
STRONG_72H_CM = 12.0
MODERATE_72H_CM = 8.0
MODERATE_7D_CM = 8.0

MIN_OVERLAP_H = 1.0
HIGH_SCORE_MIN = 0.70
HIGH_OVERLAP_H_MIN = 12.0
MEDIUM_CHAIN3_SCORE_MIN = 0.45
MEDIUM_CHAIN3_OVERLAP_H_MIN = 4.0
MEDIUM_PAIR_SCORE_MIN = 0.60
MEDIUM_PAIR_OVERLAP_H_MIN = 6.0

# Replay a cada 6 h: suficiente para testar o comportamento operacional
# sem transformar pequenas oscilações horárias em alertas repetidos.
REPLAY_STEP_H = 6

# Avaliação.
MATCH_TOLERANCE_H = 24.0
MAX_TARGET_LOOKAHEAD_H = 14 * 24
DEDUP_ALERT_H = 48

BACKTEST_START = datetime(2024, 1, 1, 0, 0, 0)


def parse_dt(value):
    if not value:
        return None
    value = str(value).strip().replace(".0", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def fmt_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def load_history():
    wanted = set(CORE) | {BARCELOS}
    series = {code: {} for code in wanted}

    with HISTORY_FILE.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = row.get("estacao")
            if code not in series:
                continue
            dt = parse_dt(row.get("hora_manaus"))
            raw = row.get("nivel_cm")
            if dt is None or raw in (None, ""):
                continue
            try:
                level = float(raw)
            except ValueError:
                continue
            series[code][dt] = level

    return series


def delta_map(levels, hours):
    shift = timedelta(hours=hours)
    return {
        dt: level - levels[dt - shift]
        for dt, level in levels.items()
        if dt - shift in levels
    }


def build_maps(series):
    maps = {}
    for code, levels in series.items():
        maps[code] = {
            24: delta_map(levels, 24),
            72: delta_map(levels, 72),
            168: delta_map(levels, 168),
        }
    return maps


def signal_status_at(code, t, maps):
    v24 = maps[code][24].get(t)
    v72 = maps[code][72].get(t)
    v7d = maps[code][168].get(t)

    if v24 is None or v72 is None or v7d is None:
        return {
            "ativo": False,
            "forca": "sem_dado",
            "v24": v24,
            "v72": v72,
            "v7d": v7d,
        }

    if v24 >= STRONG_24H_CM or v72 >= STRONG_72H_CM:
        return {
            "ativo": True,
            "forca": "forte",
            "v24": v24,
            "v72": v72,
            "v7d": v7d,
        }

    if v72 >= MODERATE_72H_CM and v7d >= MODERATE_7D_CM:
        return {
            "ativo": True,
            "forca": "moderado",
            "v24": v24,
            "v72": v72,
            "v7d": v7d,
        }

    return {
        "ativo": False,
        "forca": "fraco",
        "v24": v24,
        "v72": v72,
        "v7d": v7d,
    }


def build_active_times(maps):
    active = {}
    for code in ORDER + [BARCELOS]:
        active[code] = sorted(
            dt for dt, change in maps[code][24].items()
            if change >= RISE_THRESHOLD_CM
        )
    return active


def episodes_until(code, t, active_times, levels):
    times = active_times[code]
    left = bisect.bisect_left(
        times,
        t - timedelta(hours=MAX_RECENT_EVENT_AGE_H + MAX_ACTIVE_GAP_H)
    )
    right = bisect.bisect_right(times, t)
    points = times[left:right]

    if not points:
        return []

    groups = []
    group = [points[0]]

    for dt in points[1:]:
        gap_h = (dt - group[-1]).total_seconds() / 3600
        if gap_h <= MAX_ACTIVE_GAP_H:
            group.append(dt)
        else:
            groups.append(group)
            group = [dt]
    groups.append(group)

    cutoff = t - timedelta(hours=MAX_RECENT_EVENT_AGE_H)
    episodes = []

    for idx, g in enumerate(groups, start=1):
        if g[-1] < cutoff:
            continue

        start = g[0]
        last_active = g[-1]
        amplitude = None

        sample_times = [
            dt for dt in levels[code]
            if start <= dt <= min(t, last_active + timedelta(hours=24))
        ]

        if sample_times and start in levels[code]:
            amplitude = max(levels[code][dt] for dt in sample_times) - levels[code][start]

        episodes.append({
            "id": f"{code}-{fmt_dt(start)}",
            "inicio": start,
            "ultimo_ativo": last_active,
            "idade_ultimo_ativo_h": (t - last_active).total_seconds() / 3600,
            "amplitude_cm": amplitude,
        })

    return episodes


def project_arrival(code, event):
    cfg = CORE[code]
    return {
        "inicio": event["inicio"] + timedelta(hours=cfg["lag_q25_h"]),
        "centro": event["inicio"] + timedelta(hours=cfg["lag_mediano_h"]),
        "fim": event["inicio"] + timedelta(hours=cfg["lag_q75_h"]),
    }


def overlap_interval(windows):
    if not windows:
        return None

    start = max(w["inicio"] for w in windows)
    end = min(w["fim"] for w in windows)

    if end <= start:
        return None

    hours = (end - start).total_seconds() / 3600
    if hours < MIN_OVERLAP_H:
        return None

    return {"inicio": start, "fim": end, "duracao_h": hours}


def segment_check(source, target, source_event, target_event):
    cfg = SEGMENTS[(source, target)]
    observed = (
        target_event["inicio"] - source_event["inicio"]
    ).total_seconds() / 3600

    low = cfg["q25_h"] - SEGMENT_TOLERANCE_H
    high = cfg["q75_h"] + SEGMENT_TOLERANCE_H
    ok = low <= observed <= high

    distance = abs(observed - cfg["mediana_h"])
    half_span = max((high - low) / 2, 1.0)
    score = max(0.0, 1.0 - distance / half_span)

    return {
        "trecho": cfg["nome"],
        "observado_h": observed,
        "coerente": ok,
        "score_proximidade": score,
    }


def candidate_pair(source, target, source_event, target_event, t):
    check = segment_check(source, target, source_event, target_event)
    if not check["coerente"]:
        return None

    p1 = project_arrival(source, source_event)
    p2 = project_arrival(target, target_event)
    overlap = overlap_interval([p1, p2])
    if not overlap:
        return None

    recency = max(
        0.0,
        1.0 - max(
            source_event["idade_ultimo_ativo_h"],
            target_event["idade_ultimo_ativo_h"],
        ) / MAX_RECENT_EVENT_AGE_H
    )
    overlap_score = min(overlap["duracao_h"] / 24.0, 1.0)

    score = (
        0.55 * check["score_proximidade"]
        + 0.25 * overlap_score
        + 0.20 * recency
    )

    return {
        "tipo": "par",
        "estacoes": [source, target],
        "eventos": [source_event, target_event],
        "checks": [check],
        "janela": overlap,
        "score": score,
        "alerta_em": t,
    }


def candidate_chain_three(te, ce, se, t):
    c1 = segment_check(ORDER[0], ORDER[1], te, ce)
    c2 = segment_check(ORDER[1], ORDER[2], ce, se)

    if not (c1["coerente"] and c2["coerente"]):
        return None

    overlap = overlap_interval([
        project_arrival(ORDER[0], te),
        project_arrival(ORDER[1], ce),
        project_arrival(ORDER[2], se),
    ])

    if not overlap:
        return None

    recency = max(
        0.0,
        1.0 - max(
            te["idade_ultimo_ativo_h"],
            ce["idade_ultimo_ativo_h"],
            se["idade_ultimo_ativo_h"],
        ) / MAX_RECENT_EVENT_AGE_H
    )

    chronology_score = (
        c1["score_proximidade"] + c2["score_proximidade"]
    ) / 2

    overlap_score = min(overlap["duracao_h"] / 24.0, 1.0)

    score = (
        0.60 * chronology_score
        + 0.25 * overlap_score
        + 0.15 * recency
    )

    return {
        "tipo": "cadeia_3",
        "estacoes": ORDER[:],
        "eventos": [te, ce, se],
        "checks": [c1, c2],
        "janela": overlap,
        "score": score,
        "alerta_em": t,
    }


def classify_candidate(best, active_count):
    if best and len(best["estacoes"]) == 3:
        score = best["score"]
        overlap_h = best["janela"]["duracao_h"]

        if score >= HIGH_SCORE_MIN and overlap_h >= HIGH_OVERLAP_H_MIN:
            return "alta", "onda_de_subida_convergente"

        if (
            score >= MEDIUM_CHAIN3_SCORE_MIN
            and overlap_h >= MEDIUM_CHAIN3_OVERLAP_H_MIN
        ):
            return "media", "onda_de_subida_convergente_em_confirmacao"

        return "observacao", "cadeia_completa_porem_qualidade_insuficiente"

    if best and len(best["estacoes"]) == 2:
        score = best["score"]
        overlap_h = best["janela"]["duracao_h"]

        if (
            score >= MEDIUM_PAIR_SCORE_MIN
            and overlap_h >= MEDIUM_PAIR_OVERLAP_H_MIN
        ):
            return "media", "cadeia_parcial_de_subida_coerente"

        return "observacao", "cadeia_parcial_em_observacao"

    if active_count >= 2:
        return "observacao", "multiplos_sinais_sem_cadeia_espacial"
    if active_count == 1:
        return "baixa", "sinal_isolado_de_subida"
    return "sem_alerta", "sem_onda_de_subida_convergente"


def build_candidate_at(t, maps, active_times, levels):
    signals = {
        code: signal_status_at(code, t, maps)
        for code in ORDER
    }

    active_count = sum(1 for code in ORDER if signals[code]["ativo"])

    episodes = {
        code: episodes_until(code, t, active_times, levels)
        for code in ORDER
    }

    candidates = []

    for te in episodes[ORDER[0]]:
        for ce in episodes[ORDER[1]]:
            for se in episodes[ORDER[2]]:
                c = candidate_chain_three(te, ce, se, t)
                if (
                    c
                    and all(signals[code]["ativo"] for code in c["estacoes"])
                ):
                    candidates.append(c)

    for source, target in (
        (ORDER[0], ORDER[1]),
        (ORDER[1], ORDER[2]),
    ):
        for se in episodes[source]:
            for te in episodes[target]:
                c = candidate_pair(source, target, se, te, t)
                if (
                    c
                    and signals[source]["ativo"]
                    and signals[target]["ativo"]
                ):
                    candidates.append(c)

    candidates.sort(
        key=lambda c: (
            len(c["estacoes"]),
            c["score"],
            c["janela"]["duracao_h"],
        ),
        reverse=True,
    )

    best = candidates[0] if candidates else None
    confidence, status = classify_candidate(best, active_count)

    return best, confidence, status, signals


def chain_signature(chain):
    if not chain:
        return None
    return "|".join(
        f"{code}:{fmt_dt(event['inicio'])}"
        for code, event in zip(chain["estacoes"], chain["eventos"])
    )


def detect_target_events(active_times):
    times = active_times[BARCELOS]
    if not times:
        return []

    groups = []
    group = [times[0]]

    for dt in times[1:]:
        gap_h = (dt - group[-1]).total_seconds() / 3600
        if gap_h <= MAX_ACTIVE_GAP_H:
            group.append(dt)
        else:
            groups.append(group)
            group = [dt]

    groups.append(group)

    return [
        {
            "event_id": idx,
            "inicio": g[0],
            "ultimo_ativo": g[-1],
        }
        for idx, g in enumerate(groups, start=1)
        if g[0] >= BACKTEST_START
    ]


def evaluate_alert(alert, target_events):
    start = alert["janela_inicio"]
    end = alert["janela_fim"]
    center = start + (end - start) / 2

    eligible = [
        e for e in target_events
        if alert["alerta_em"] <= e["inicio"]
        <= alert["alerta_em"] + timedelta(hours=MAX_TARGET_LOOKAHEAD_H)
    ]

    if not eligible:
        return {
            "target_id": None,
            "target_inicio": None,
            "acerto_estrito": False,
            "acerto_24h": False,
            "lead_h": None,
            "erro_centro_h": None,
        }

    nearest = min(
        eligible,
        key=lambda e: abs((e["inicio"] - center).total_seconds())
    )

    strict = start <= nearest["inicio"] <= end
    tolerant = (
        start - timedelta(hours=MATCH_TOLERANCE_H)
        <= nearest["inicio"]
        <= end + timedelta(hours=MATCH_TOLERANCE_H)
    )

    return {
        "target_id": nearest["event_id"] if tolerant else None,
        "target_inicio": nearest["inicio"] if tolerant else None,
        "acerto_estrito": strict,
        "acerto_24h": tolerant,
        "lead_h": (
            (nearest["inicio"] - alert["alerta_em"]).total_seconds() / 3600
            if tolerant else None
        ),
        "erro_centro_h": (
            (nearest["inicio"] - center).total_seconds() / 3600
            if tolerant else None
        ),
    }


def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


def metric_row(label, alerts, target_events):
    strict_hits = sum(1 for a in alerts if a["acerto_estrito"])
    tolerant_hits = sum(1 for a in alerts if a["acerto_24h"])
    matched_targets = {
        a["target_id"] for a in alerts
        if a["target_id"] is not None
    }

    return {
        "grupo": label,
        "alertas": len(alerts),
        "acertos_estritos": strict_hits,
        "acertos_24h": tolerant_hits,
        "falsos_alertas_24h": len(alerts) - tolerant_hits,
        "precisao_estrita_pct": pct(strict_hits, len(alerts)),
        "precisao_24h_pct": pct(tolerant_hits, len(alerts)),
        "eventos_barcelos_cobertos": len(matched_targets),
        "eventos_barcelos_total": len(target_events),
        "recall_24h_pct": pct(len(matched_targets), len(target_events)),
        "antecedencia_mediana_h": median(
            [a["lead_h"] for a in alerts if a["acerto_24h"]]
        ),
        "erro_abs_centro_mediano_h": median(
            [abs(a["erro_centro_h"]) for a in alerts if a["acerto_24h"]]
        ),
    }


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError("data/history/hourly.csv nao encontrado.")

    levels = load_history()
    maps = build_maps(levels)
    active_times = build_active_times(maps)

    common_end = min(
        max(levels[code]) for code in ORDER + [BARCELOS]
        if levels[code]
    )

    start = max(
        BACKTEST_START,
        max(
            min(levels[code]) + timedelta(hours=168)
            for code in ORDER + [BARCELOS]
            if levels[code]
        ),
    )

    target_events = [
        e for e in detect_target_events(active_times)
        if start <= e["inicio"] <= common_end
    ]

    alerts = []
    last_signature_time = {}

    t = start
    while t <= common_end:
        best, confidence, status, signals = build_candidate_at(
            t, maps, active_times, levels
        )

        if best and confidence in ("media", "alta"):
            sig = chain_signature(best)
            previous = last_signature_time.get(sig)

            if previous is None or (
                t - previous
            ).total_seconds() / 3600 >= DEDUP_ALERT_H:
                row = {
                    "alerta_em": t,
                    "confianca": confidence,
                    "status": status,
                    "tipo": best["tipo"],
                    "estacoes": " -> ".join(
                        CORE[c]["nome"] for c in best["estacoes"]
                    ),
                    "score": round(best["score"], 3),
                    "janela_inicio": best["janela"]["inicio"],
                    "janela_fim": best["janela"]["fim"],
                    "janela_duracao_h": round(
                        best["janela"]["duracao_h"], 1
                    ),
                    "assinatura": sig,
                }

                evaluation = evaluate_alert(row, target_events)
                row.update(evaluation)
                alerts.append(row)
                last_signature_time[sig] = t

        t += timedelta(hours=REPLAY_STEP_H)

    # Evita contar o mesmo sinal várias vezes por 48 h como alertas independentes.
    deduped = []
    for row in alerts:
        if not deduped:
            deduped.append(row)
            continue

        prev = deduped[-1]
        same_target = (
            row["target_id"] is not None
            and row["target_id"] == prev["target_id"]
        )
        close_h = (
            row["alerta_em"] - prev["alerta_em"]
        ).total_seconds() / 3600

        if same_target and close_h < DEDUP_ALERT_H:
            # Mantém o alerta de maior confiança/score, mas preserva a primeira emissão
            rank = {"media": 1, "alta": 2}
            if (
                rank[row["confianca"]] > rank[prev["confianca"]]
                or (
                    rank[row["confianca"]] == rank[prev["confianca"]]
                    and row["score"] > prev["score"]
                )
            ):
                row["alerta_em"] = prev["alerta_em"]
                deduped[-1] = row
            continue

        deduped.append(row)

    alerts = deduped

    metrics = [
        metric_row(
            "media+alta",
            [a for a in alerts if a["confianca"] in ("media", "alta")],
            target_events,
        ),
        metric_row(
            "alta",
            [a for a in alerts if a["confianca"] == "alta"],
            target_events,
        ),
        metric_row(
            "media",
            [a for a in alerts if a["confianca"] == "media"],
            target_events,
        ),
    ]

    matched_target_ids = {
        a["target_id"] for a in alerts
        if a["target_id"] is not None
    }

    for e in target_events:
        e["coberto_24h"] = e["event_id"] in matched_target_ids

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    alert_fields = [
        "alerta_em", "confianca", "status", "tipo", "estacoes",
        "score", "janela_inicio", "janela_fim", "janela_duracao_h",
        "target_id", "target_inicio", "acerto_estrito", "acerto_24h",
        "lead_h", "erro_centro_h", "assinatura",
    ]

    with ALERTS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alert_fields)
        w.writeheader()
        for row in alerts:
            out = dict(row)
            for key in ("alerta_em", "janela_inicio", "janela_fim", "target_inicio"):
                out[key] = fmt_dt(out.get(key))
            for key in ("lead_h", "erro_centro_h"):
                if out.get(key) is not None:
                    out[key] = round(out[key], 1)
            w.writerow({field: out.get(field) for field in alert_fields})

    with TARGETS_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = ["event_id", "inicio", "ultimo_ativo", "coberto_24h"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in target_events:
            w.writerow({
                "event_id": row["event_id"],
                "inicio": fmt_dt(row["inicio"]),
                "ultimo_ativo": fmt_dt(row["ultimo_ativo"]),
                "coberto_24h": row["coberto_24h"],
            })

    metric_fields = list(metrics[0].keys())
    with METRICS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=metric_fields)
        w.writeheader()
        w.writerows(metrics)

    summary = {
        "modelo": "backtest_convergencia_espacial_v3",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "periodo": {
            "inicio": fmt_dt(start),
            "fim": fmt_dt(common_end),
            "passo_replay_h": REPLAY_STEP_H,
        },
        "avaliacao": {
            "tolerancia_janela_h": MATCH_TOLERANCE_H,
            "lookahead_max_h": MAX_TARGET_LOOKAHEAD_H,
            "dedup_alerta_h": DEDUP_ALERT_H,
        },
        "metricas": metrics,
        "nota_metodologica": (
            "Replay retrospectivo sem uso de leituras futuras na geracao de cada alerta. "
            "Eventos reais de Barcelos sao detectados por subida >=5 cm em 24h. "
            "Acerto estrito exige inicio do evento dentro da janela prevista; "
            "acerto 24h aceita margem de 24h antes/depois da janela."
        ),
    }

    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("============================================")
    print("BACKTEST MOTOR CONVERGENCIA ESPACIAL V3")
    print("============================================")
    print(f"Periodo: {fmt_dt(start)} -> {fmt_dt(common_end)}")
    print(f"Passo do replay: {REPLAY_STEP_H} h")
    print(f"Eventos reais de subida em Barcelos: {len(target_events)}")
    print(f"Alertas preditivos deduplicados: {len(alerts)}")
    print()

    for m in metrics:
        print(
            f"{m['grupo']:<12} "
            f"alertas={m['alertas']} | "
            f"acerto estrito={m['acertos_estritos']} "
            f"({m['precisao_estrita_pct']}%) | "
            f"acerto ±24h={m['acertos_24h']} "
            f"({m['precisao_24h_pct']}%) | "
            f"recall={m['recall_24h_pct']}% | "
            f"lead mediano={m['antecedencia_mediana_h']} h | "
            f"erro centro mediano={m['erro_abs_centro_mediano_h']} h"
        )

    print()
    print(f"Arquivos: {ALERTS_CSV} {TARGETS_CSV} {METRICS_CSV} {SUMMARY_JSON}")
    print("Teste somente. Nenhum arquivo do painel foi alterado.")


if __name__ == "__main__":
    main()
