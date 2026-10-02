import csv
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backtest_convergencia_v3 import (
    HISTORY_FILE,
    OUTPUT_DIR,
    CORE,
    ORDER,
    BARCELOS,
    REPLAY_STEP_H,
    BACKTEST_START,
    MAX_ACTIVE_GAP_H,
    load_history,
    build_maps,
    build_active_times,
    build_candidate_at,
    chain_signature,
    fmt_dt,
)

ALERTS_CSV = OUTPUT_DIR / "backtest_v31_alertas_causais.csv"
TARGETS_CSV = OUTPUT_DIR / "backtest_v31_eventos_barcelos.csv"
METRICS_CSV = OUTPUT_DIR / "backtest_v31_metricas.csv"
YEARLY_CSV = OUTPUT_DIR / "backtest_v31_metricas_anuais.csv"
SUMMARY_JSON = OUTPUT_DIR / "backtest_v31_resumo.json"

# Avaliação sem olhar para o futuro durante a geração/deduplicação.
MATCH_TOLERANCE_H = 24.0
MAX_TARGET_LOOKAHEAD_H = 14 * 24
ALERT_CLUSTER_GAP_H = 48.0
WINDOW_JOIN_GAP_H = 24.0

# Evento real relevante em Barcelos: além de Δ24 >= 5 cm,
# exige persistência e amplitude total mínima.
TARGET_MIN_ACTIVE_DURATION_H = 12.0
TARGET_MIN_RISE_CM = 10.0
TARGET_BASELINE_H = 24
TARGET_PEAK_EXTRA_H = 24

CONF_RANK = {"media": 1, "alta": 2}


def overlap_or_near(a_start, a_end, b_start, b_end, gap_h=WINDOW_JOIN_GAP_H):
    gap = timedelta(hours=gap_h)
    return not (a_end + gap < b_start or b_end + gap < a_start)


def raw_target_groups(active_times):
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
    return groups


def detect_target_events(active_times, levels):
    events = []
    bar = levels[BARCELOS]

    for g in raw_target_groups(active_times):
        start = g[0]
        end = g[-1]
        if start < BACKTEST_START:
            continue

        active_duration_h = (end - start).total_seconds() / 3600
        baseline_t = start - timedelta(hours=TARGET_BASELINE_H)
        baseline = bar.get(baseline_t)

        peak_end = end + timedelta(hours=TARGET_PEAK_EXTRA_H)
        peak_values = [
            level for dt, level in bar.items()
            if start <= dt <= peak_end
        ]
        peak = max(peak_values) if peak_values else None
        rise_cm = (peak - baseline) if (baseline is not None and peak is not None) else None

        qualified = (
            active_duration_h >= TARGET_MIN_ACTIVE_DURATION_H
            and rise_cm is not None
            and rise_cm >= TARGET_MIN_RISE_CM
        )

        events.append({
            "event_id": len(events) + 1,
            "inicio": start,
            "ultimo_ativo": end,
            "duracao_ativa_h": round(active_duration_h, 1),
            "subida_total_cm": round(rise_cm, 1) if rise_cm is not None else None,
            "significativo": qualified,
        })

    return events


def emission_from_candidate(t, best, confidence, status):
    return {
        "alerta_em": t,
        "confianca": confidence,
        "status": status,
        "tipo": best["tipo"],
        "estacoes": tuple(best["estacoes"]),
        "estacoes_nome": " -> ".join(CORE[c]["nome"] for c in best["estacoes"]),
        "score": round(best["score"], 3),
        "janela_inicio": best["janela"]["inicio"],
        "janela_fim": best["janela"]["fim"],
        "janela_duracao_h": round(best["janela"]["duracao_h"], 1),
        "assinatura": chain_signature(best),
    }


def same_causal_cluster(cluster, emission):
    close_h = (emission["alerta_em"] - cluster["ultimo_alerta_em"]).total_seconds() / 3600
    if close_h < 0 or close_h > ALERT_CLUSTER_GAP_H:
        return False

    same_signature = emission["assinatura"] == cluster["assinatura"]
    same_chain = emission["estacoes"] == cluster["estacoes"]
    window_related = overlap_or_near(
        cluster["janela_inicio_ultima"],
        cluster["janela_fim_ultima"],
        emission["janela_inicio"],
        emission["janela_fim"],
    )

    return same_signature or (same_chain and window_related)


def new_cluster(cluster_id, emission):
    first_high = emission if emission["confianca"] == "alta" else None
    return {
        "cluster_id": cluster_id,
        "assinatura": emission["assinatura"],
        "estacoes": emission["estacoes"],
        "primeira_emissao": emission,
        "ultimo_alerta_em": emission["alerta_em"],
        "janela_inicio_ultima": emission["janela_inicio"],
        "janela_fim_ultima": emission["janela_fim"],
        "melhor_emissao": emission,
        "primeira_alta": first_high,
        "emissoes": 1,
    }


def update_cluster(cluster, emission):
    cluster["ultimo_alerta_em"] = emission["alerta_em"]
    cluster["janela_inicio_ultima"] = emission["janela_inicio"]
    cluster["janela_fim_ultima"] = emission["janela_fim"]
    cluster["emissoes"] += 1

    best = cluster["melhor_emissao"]
    if (
        CONF_RANK[emission["confianca"]] > CONF_RANK[best["confianca"]]
        or (
            CONF_RANK[emission["confianca"]] == CONF_RANK[best["confianca"]]
            and emission["score"] > best["score"]
        )
    ):
        cluster["melhor_emissao"] = emission

    if cluster["primeira_alta"] is None and emission["confianca"] == "alta":
        cluster["primeira_alta"] = emission


def build_causal_clusters(levels, maps, active_times, start, common_end):
    clusters = []
    t = start

    while t <= common_end:
        best, confidence, status, _signals = build_candidate_at(
            t, maps, active_times, levels
        )

        if best and confidence in ("media", "alta"):
            emission = emission_from_candidate(t, best, confidence, status)

            match = None
            for cluster in reversed(clusters):
                if (t - cluster["ultimo_alerta_em"]).total_seconds() / 3600 > ALERT_CLUSTER_GAP_H:
                    break
                if same_causal_cluster(cluster, emission):
                    match = cluster
                    break

            if match is None:
                clusters.append(new_cluster(len(clusters) + 1, emission))
            else:
                update_cluster(match, emission)

        t += timedelta(hours=REPLAY_STEP_H)

    return clusters


def evaluation_units(clusters):
    units = []
    for c in clusters:
        first = dict(c["primeira_emissao"])
        first["cluster_id"] = c["cluster_id"]
        first["grupo_avaliacao"] = "primeiro_aviso"
        first["confianca_final_cluster"] = c["melhor_emissao"]["confianca"]
        first["emissoes_cluster"] = c["emissoes"]
        units.append(first)

        if c["primeira_alta"] is not None:
            high = dict(c["primeira_alta"])
            high["cluster_id"] = c["cluster_id"]
            high["grupo_avaliacao"] = "primeira_alta"
            high["confianca_final_cluster"] = c["melhor_emissao"]["confianca"]
            high["emissoes_cluster"] = c["emissoes"]
            units.append(high)

    return units


def candidate_matches(alert, targets):
    center = alert["janela_inicio"] + (alert["janela_fim"] - alert["janela_inicio"]) / 2
    pairs = []

    for e in targets:
        if e["inicio"] < alert["alerta_em"]:
            continue
        lead_h = (e["inicio"] - alert["alerta_em"]).total_seconds() / 3600
        if lead_h > MAX_TARGET_LOOKAHEAD_H:
            continue

        strict = alert["janela_inicio"] <= e["inicio"] <= alert["janela_fim"]
        tolerant = (
            alert["janela_inicio"] - timedelta(hours=MATCH_TOLERANCE_H)
            <= e["inicio"]
            <= alert["janela_fim"] + timedelta(hours=MATCH_TOLERANCE_H)
        )
        if not tolerant:
            continue

        error_h = (e["inicio"] - center).total_seconds() / 3600
        pairs.append({
            "alert_cluster_id": alert["cluster_id"],
            "target_id": e["event_id"],
            "strict": strict,
            "lead_h": lead_h,
            "erro_centro_h": error_h,
        })

    return pairs


def one_to_one_match(alerts, targets):
    # Pareamento feito somente DEPOIS que todos os alertas foram produzidos.
    # Prioriza acerto estrito e menor erro temporal, sem reutilizar alerta/evento.
    possible = []
    by_alert_key = {}

    for idx, alert in enumerate(alerts):
        key = (idx, alert["cluster_id"], alert["grupo_avaliacao"])
        by_alert_key[key] = alert
        for p in candidate_matches(alert, targets):
            possible.append((
                0 if p["strict"] else 1,
                abs(p["erro_centro_h"]),
                p["lead_h"],
                key,
                p,
            ))

    possible.sort(key=lambda x: (x[0], x[1], x[2]))
    used_alerts = set()
    used_targets = set()
    matches = {}

    for _strict_rank, _err, _lead, key, p in possible:
        if key in used_alerts or p["target_id"] in used_targets:
            continue
        used_alerts.add(key)
        used_targets.add(p["target_id"])
        matches[key] = p

    evaluated = []
    for idx, alert in enumerate(alerts):
        key = (idx, alert["cluster_id"], alert["grupo_avaliacao"])
        row = dict(alert)
        p = matches.get(key)
        row.update({
            "target_id": p["target_id"] if p else None,
            "acerto_estrito": bool(p and p["strict"]),
            "acerto_24h": bool(p),
            "lead_h": p["lead_h"] if p else None,
            "erro_centro_h": p["erro_centro_h"] if p else None,
        })
        evaluated.append(row)

    return evaluated, used_targets


def pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def med(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


def metric_row(label, alerts, targets):
    evaluated, matched_targets = one_to_one_match(alerts, targets)
    strict_hits = sum(1 for a in evaluated if a["acerto_estrito"])
    tolerant_hits = sum(1 for a in evaluated if a["acerto_24h"])

    return {
        "grupo": label,
        "alertas": len(alerts),
        "acertos_estritos": strict_hits,
        "acertos_24h": tolerant_hits,
        "falsos_alertas_24h": len(alerts) - tolerant_hits,
        "precisao_estrita_pct": pct(strict_hits, len(alerts)),
        "precisao_24h_pct": pct(tolerant_hits, len(alerts)),
        "eventos_barcelos_cobertos": len(matched_targets),
        "eventos_barcelos_total": len(targets),
        "recall_24h_pct": pct(len(matched_targets), len(targets)),
        "antecedencia_mediana_h": med([a["lead_h"] for a in evaluated if a["acerto_24h"]]),
        "erro_abs_centro_mediano_h": med([
            abs(a["erro_centro_h"]) for a in evaluated if a["acerto_24h"]
        ]),
    }, evaluated


def slice_year(alerts, targets, year):
    ya = [a for a in alerts if a["alerta_em"].year == year]
    yt = [e for e in targets if e["inicio"].year == year]
    return ya, yt


def serialize_alert(row):
    out = dict(row)
    out["estacoes"] = "|".join(out.get("estacoes", ()))
    for key in ("alerta_em", "janela_inicio", "janela_fim"):
        out[key] = fmt_dt(out.get(key))
    for key in ("lead_h", "erro_centro_h"):
        if out.get(key) is not None:
            out[key] = round(out[key], 1)
    return out


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError("data/history/hourly.csv nao encontrado.")

    levels = load_history()
    maps = build_maps(levels)
    active_times = build_active_times(maps)

    common_end = min(
        max(levels[code]) for code in ORDER + [BARCELOS] if levels[code]
    )
    start = max(
        BACKTEST_START,
        max(
            min(levels[code]) + timedelta(hours=168)
            for code in ORDER + [BARCELOS] if levels[code]
        ),
    )

    all_targets = [
        e for e in detect_target_events(active_times, levels)
        if start <= e["inicio"] <= common_end
    ]
    targets = [e for e in all_targets if e["significativo"]]

    clusters = build_causal_clusters(levels, maps, active_times, start, common_end)
    units = evaluation_units(clusters)

    first_alerts = [u for u in units if u["grupo_avaliacao"] == "primeiro_aviso"]
    high_alerts = [u for u in units if u["grupo_avaliacao"] == "primeira_alta"]
    medium_only = [
        u for u in first_alerts if u["confianca_final_cluster"] == "media"
    ]

    metrics = []
    evaluated_groups = {}
    for label, group in (
        ("primeiro_aviso_media+alta", first_alerts),
        ("primeira_alta", high_alerts),
        ("media_sem_upgrade", medium_only),
    ):
        m, evaluated = metric_row(label, group, targets)
        metrics.append(m)
        evaluated_groups[label] = evaluated

    yearly = []
    for year in sorted({e["inicio"].year for e in targets}):
        for label, group in (
            ("primeiro_aviso_media+alta", first_alerts),
            ("primeira_alta", high_alerts),
            ("media_sem_upgrade", medium_only),
        ):
            ya, yt = slice_year(group, targets, year)
            m, _ = metric_row(f"{label}_{year}", ya, yt)
            m["ano"] = year
            m["grupo_base"] = label
            yearly.append(m)

    primary_eval = evaluated_groups["primeiro_aviso_media+alta"]
    high_eval = evaluated_groups["primeira_alta"]
    medium_eval = evaluated_groups["media_sem_upgrade"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    alert_fields = [
        "cluster_id", "grupo_avaliacao", "alerta_em", "confianca",
        "confianca_final_cluster", "status", "tipo", "estacoes",
        "estacoes_nome", "score", "janela_inicio", "janela_fim",
        "janela_duracao_h", "emissoes_cluster", "target_id",
        "acerto_estrito", "acerto_24h", "lead_h", "erro_centro_h",
        "assinatura",
    ]
    with ALERTS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alert_fields)
        w.writeheader()
        for row in primary_eval + high_eval + medium_eval:
            out = serialize_alert(row)
            w.writerow({field: out.get(field) for field in alert_fields})

    target_fields = [
        "event_id", "inicio", "ultimo_ativo", "duracao_ativa_h",
        "subida_total_cm", "significativo",
    ]
    with TARGETS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=target_fields)
        w.writeheader()
        for row in all_targets:
            out = dict(row)
            out["inicio"] = fmt_dt(out["inicio"])
            out["ultimo_ativo"] = fmt_dt(out["ultimo_ativo"])
            w.writerow(out)

    metric_fields = list(metrics[0].keys())
    with METRICS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=metric_fields)
        w.writeheader()
        w.writerows(metrics)

    yearly_fields = ["ano", "grupo_base"] + metric_fields
    with YEARLY_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=yearly_fields)
        w.writeheader()
        for row in yearly:
            w.writerow({field: row.get(field) for field in yearly_fields})

    summary = {
        "modelo": "backtest_convergencia_espacial_v3_1_causal",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "periodo": {
            "inicio": fmt_dt(start),
            "fim": fmt_dt(common_end),
            "passo_replay_h": REPLAY_STEP_H,
        },
        "eventos_barcelos": {
            "brutos": len(all_targets),
            "significativos": len(targets),
            "criterios": {
                "delta24_min_cm": 5.0,
                "duracao_ativa_min_h": TARGET_MIN_ACTIVE_DURATION_H,
                "subida_total_min_cm": TARGET_MIN_RISE_CM,
            },
        },
        "alertas": {
            "clusters_causais": len(clusters),
            "clusters_com_upgrade_alta": len(high_alerts),
            "clusters_media_sem_upgrade": len(medium_only),
        },
        "avaliacao": {
            "tolerancia_janela_h": MATCH_TOLERANCE_H,
            "lookahead_max_h": MAX_TARGET_LOOKAHEAD_H,
            "dedup_cluster_gap_h": ALERT_CLUSTER_GAP_H,
            "pareamento": "1 alerta <-> 1 evento, feito somente apos o replay",
        },
        "metricas": metrics,
        "metricas_anuais": yearly,
        "nota_metodologica": (
            "Barcelos nao participa da geracao nem da deduplicacao dos alertas. "
            "A primeira emissao e o primeiro upgrade para alta sao preservados separadamente. "
            "Somente apos o replay os alertas sao pareados, 1:1, aos eventos reais significativos de Barcelos."
        ),
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print("================================================")
    print("BACKTEST MOTOR CONVERGENCIA ESPACIAL V3.1 CAUSAL")
    print("================================================")
    print(f"Periodo: {fmt_dt(start)} -> {fmt_dt(common_end)}")
    print(f"Passo do replay: {REPLAY_STEP_H} h")
    print(f"Eventos Barcelos brutos: {len(all_targets)}")
    print(f"Eventos Barcelos significativos: {len(targets)}")
    print(f"Clusters de alerta causais: {len(clusters)}")
    print(f"Clusters que chegaram a ALTA: {len(high_alerts)}")
    print()
    for m in metrics:
        print(
            f"{m['grupo']:<26} "
            f"alertas={m['alertas']} | "
            f"estrito={m['acertos_estritos']} ({m['precisao_estrita_pct']}%) | "
            f"±24h={m['acertos_24h']} ({m['precisao_24h_pct']}%) | "
            f"recall={m['recall_24h_pct']}% | "
            f"lead mediano={m['antecedencia_mediana_h']} h | "
            f"erro centro mediano={m['erro_abs_centro_mediano_h']} h"
        )

    print()
    print("Metricas por ano:")
    for m in yearly:
        print(
            f"{m['ano']} {m['grupo_base']:<26} "
            f"alertas={m['alertas']} | ±24h={m['acertos_24h']} "
            f"({m['precisao_24h_pct']}%) | recall={m['recall_24h_pct']}% | "
            f"lead={m['antecedencia_mediana_h']} h"
        )

    print()
    print(
        f"Arquivos: {ALERTS_CSV} {TARGETS_CSV} {METRICS_CSV} "
        f"{YEARLY_CSV} {SUMMARY_JSON}"
    )
    print("Teste somente. Nenhum arquivo do painel foi alterado.")


if __name__ == "__main__":
    main()
