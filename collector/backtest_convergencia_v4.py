import csv
import json
from datetime import datetime, timezone

from backtest_convergencia_v3 import (
    HISTORY_FILE,
    OUTPUT_DIR,
    ORDER,
    BARCELOS,
    BACKTEST_START,
    load_history,
    build_maps,
    build_active_times,
    fmt_dt,
)
from backtest_convergencia_v31 import (
    detect_target_events,
    same_causal_cluster,
    new_cluster,
    update_cluster,
    metric_row,
)
from walkforward_convergencia_v32 import replay_raw_candidates

ALERTS_CSV = OUTPUT_DIR / "backtest_v4_alertas.csv"
METRICS_CSV = OUTPUT_DIR / "backtest_v4_metricas.csv"
YEARLY_CSV = OUTPUT_DIR / "backtest_v4_metricas_anuais.csv"
SUMMARY_JSON = OUTPUT_DIR / "backtest_v4_resumo.json"

ALERT_SCORE_MIN = 0.70
ALERT_OVERLAP_H_MIN = 8.0
ALERT_CLUSTER_GAP_H = 48.0


def to_alert(raw):
    if len(raw["estacoes"]) != 3:
        return None
    if raw["score"] < ALERT_SCORE_MIN:
        return None
    if raw["janela_duracao_h"] < ALERT_OVERLAP_H_MIN:
        return None

    row = dict(raw)
    row["confianca"] = "alta"
    row["status"] = "alerta_preditivo"
    row["score"] = round(row["score"], 3)
    row["janela_duracao_h"] = round(row["janela_duracao_h"], 1)
    return row


def build_clusters(raw_rows):
    clusters = []

    for raw in raw_rows:
        emission = to_alert(raw)
        if emission is None:
            continue

        match = None
        for cluster in reversed(clusters):
            gap_h = (
                emission["alerta_em"] - cluster["ultimo_alerta_em"]
            ).total_seconds() / 3600

            if gap_h > ALERT_CLUSTER_GAP_H:
                break

            if same_causal_cluster(cluster, emission):
                match = cluster
                break

        if match is None:
            clusters.append(new_cluster(len(clusters) + 1, emission))
        else:
            update_cluster(match, emission)

    return clusters


def first_alerts(clusters):
    rows = []
    for c in clusters:
        row = dict(c["primeira_emissao"])
        row["cluster_id"] = c["cluster_id"]
        row["grupo_avaliacao"] = "alerta_preditivo_v4"
        row["confianca_final_cluster"] = "alta"
        row["emissoes_cluster"] = c["emissoes"]
        rows.append(row)
    return rows


def yearly_metric(alerts, targets, year):
    ya = [a for a in alerts if a["alerta_em"].year == year]
    yt = [e for e in targets if e["inicio"].year == year]
    metric, evaluated = metric_row(
        f"v4_{year}",
        ya,
        yt,
    )
    return metric, evaluated


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError("data/history/hourly.csv nao encontrado.")

    levels = load_history()
    maps = build_maps(levels)
    active_times = build_active_times(maps)

    common_end = min(
        max(levels[code])
        for code in ORDER + [BARCELOS]
        if levels[code]
    )
    start = max(
        BACKTEST_START,
        max(
            min(levels[code])
            for code in ORDER + [BARCELOS]
            if levels[code]
        ),
    )

    all_targets = [
        e for e in detect_target_events(active_times, levels)
        if start <= e["inicio"] <= common_end
    ]
    targets = [e for e in all_targets if e["significativo"]]

    raw_rows = replay_raw_candidates(
        levels, maps, active_times, start, common_end
    )
    clusters = build_clusters(raw_rows)
    alerts = first_alerts(clusters)

    overall_metric, evaluated = metric_row(
        "v4_alerta_preditivo",
        alerts,
        targets,
    )

    yearly = []
    evaluated_by_year = {}
    for year in sorted({e["inicio"].year for e in targets}):
        m, ev = yearly_metric(alerts, targets, year)
        yearly.append(m)
        evaluated_by_year[year] = ev

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fields = [
        "cluster_id", "alerta_em", "score",
        "janela_inicio", "janela_fim", "janela_duracao_h",
        "acerto_estrito", "acerto_24h", "lead_h",
        "erro_centro_h", "target_id",
    ]
    with ALERTS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in evaluated:
            w.writerow({
                "cluster_id": row["cluster_id"],
                "alerta_em": fmt_dt(row["alerta_em"]),
                "score": row["score"],
                "janela_inicio": fmt_dt(row["janela_inicio"]),
                "janela_fim": fmt_dt(row["janela_fim"]),
                "janela_duracao_h": row["janela_duracao_h"],
                "acerto_estrito": row.get("acerto_estrito"),
                "acerto_24h": row.get("acerto_24h"),
                "lead_h": (
                    round(row["lead_h"], 1)
                    if row.get("lead_h") is not None else None
                ),
                "erro_centro_h": (
                    round(row["erro_centro_h"], 1)
                    if row.get("erro_centro_h") is not None else None
                ),
                "target_id": row.get("target_id"),
            })

    metric_fields = list(overall_metric.keys())
    with METRICS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=metric_fields)
        w.writeheader()
        w.writerow(overall_metric)

    with YEARLY_CSV.open("w", encoding="utf-8", newline="") as f:
        fields_y = ["ano"] + list(yearly[0].keys())
        w = csv.DictWriter(f, fieldnames=fields_y)
        w.writeheader()
        for m in yearly:
            year = int(m["grupo"].split("_")[-1])
            w.writerow({"ano": year, **m})

    summary = {
        "modelo": "backtest_v4_operacional_simplificada",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "criterio": {
            "cadeia_completa_obrigatoria": True,
            "score_min": ALERT_SCORE_MIN,
            "sobreposicao_min_h": ALERT_OVERLAP_H_MIN,
            "pares_geram_previsao": False,
        },
        "periodo": {
            "inicio": fmt_dt(start),
            "fim": fmt_dt(common_end),
        },
        "eventos_significativos_barcelos": len(targets),
        "metricas_gerais": overall_metric,
        "metricas_anuais": yearly,
        "nota": (
            "Somente cadeias completas Taracua -> Curicuriari -> Serrinha "
            "com score >= 0.70 e sobreposicao >= 8 h geram ALERTA PREDITIVO."
        ),
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("============================================")
    print("BACKTEST V4 OPERACIONAL SIMPLIFICADA")
    print("============================================")
    print(
        f"Periodo: {fmt_dt(start)} -> {fmt_dt(common_end)}"
    )
    print(f"Eventos significativos Barcelos: {len(targets)}")
    print(f"Alertas V4: {overall_metric['alertas']}")
    print(
        f"Precisao ±24h: {overall_metric['precisao_24h_pct']}% | "
        f"Recall: {overall_metric['recall_24h_pct']}% | "
        f"Lead mediano: {overall_metric['antecedencia_mediana_h']} h | "
        f"Erro centro mediano: {overall_metric['erro_abs_centro_mediano_h']} h"
    )
    print()
    for m in yearly:
        print(
            f"{m['grupo']}: alertas={m['alertas']} | "
            f"precisao ±24h={m['precisao_24h_pct']}% | "
            f"recall={m['recall_24h_pct']}% | "
            f"lead={m['antecedencia_mediana_h']} h"
        )

    print()
    print(f"Arquivos: {ALERTS_CSV} {METRICS_CSV} {YEARLY_CSV} {SUMMARY_JSON}")
    print("Teste somente. Nenhum arquivo do painel foi alterado.")


if __name__ == "__main__":
    main()
