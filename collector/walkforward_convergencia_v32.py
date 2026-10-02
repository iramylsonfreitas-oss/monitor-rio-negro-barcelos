import csv
import itertools
import json
import math
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
    load_history,
    build_maps,
    build_active_times,
    build_candidate_at,
    chain_signature,
    fmt_dt,
)
from backtest_convergencia_v31 import (
    detect_target_events,
    same_causal_cluster,
    new_cluster,
    update_cluster,
    metric_row,
)

FOLDS_CSV = OUTPUT_DIR / "walkforward_v32_folds.csv"
TOP_CSV = OUTPUT_DIR / "walkforward_v32_top_parametros.csv"
ALERTS_CSV = OUTPUT_DIR / "walkforward_v32_alertas_teste.csv"
REGIMES_CSV = OUTPUT_DIR / "walkforward_v32_regimes.csv"
SUMMARY_JSON = OUTPUT_DIR / "walkforward_v32_resumo.json"

# Grade deliberadamente conservadora. O teste serve para escolher limiares
# usando SOMENTE o passado; o ano de teste nunca participa da escolha.
HIGH_SCORE_GRID = [0.65, 0.70, 0.75, 0.80]
HIGH_OVERLAP_GRID = [8.0, 12.0, 18.0]

MED3_SCORE_GRID = [0.50, 0.55, 0.60, 0.65]
MED3_OVERLAP_GRID = [6.0, 12.0]

PAIR_SCORE_GRID = [0.65, 0.70, 0.75]
PAIR_OVERLAP_GRID = [8.0, 12.0]

ALERT_CLUSTER_GAP_H = 48.0

# 2026 é parcial até a data disponível no histórico.
FOLDS = [
    {
        "nome": "treina_2024_testa_2025",
        "train_years": [2024],
        "test_year": 2025,
    },
    {
        "nome": "treina_2024_2025_testa_2026",
        "train_years": [2024, 2025],
        "test_year": 2026,
    },
]


def safe_pct(v):
    return 0.0 if v is None else float(v) / 100.0


def fbeta(precision, recall, beta=0.5):
    if precision <= 0 or recall <= 0:
        return 0.0
    b2 = beta * beta
    return (1 + b2) * precision * recall / (b2 * precision + recall)


def objective_score(overall, high):
    """
    Objetivo escolhido ANTES de olhar o ano de teste.
    Prioriza precisão, mas não permite ganhar apenas emitindo pouquíssimos alertas.
    """
    p = safe_pct(overall["precisao_24h_pct"])
    r = safe_pct(overall["recall_24h_pct"])
    f05 = fbeta(p, r, beta=0.5)

    hp = safe_pct(high["precisao_24h_pct"])
    high_reliability = hp * min(high["alertas"] / 3.0, 1.0)

    score = (
        0.55 * f05
        + 0.20 * p
        + 0.15 * r
        + 0.10 * high_reliability
    )

    # Evita escolher uma configuração "perfeita" por acaso com 1–2 alertas.
    if overall["alertas"] < 5:
        score -= 0.10 * (5 - overall["alertas"]) / 5.0

    return round(score, 6)


def raw_emission(t, best, signals):
    strengths = {
        code: signals[code]["forca"]
        for code in best["estacoes"]
        if code in signals
    }

    if len(best["estacoes"]) == 3:
        regime = (
            "cadeia3_todas_fortes"
            if all(v == "forte" for v in strengths.values())
            else "cadeia3_mista"
        )
    else:
        regime = "par_consecutivo"

    return {
        "alerta_em": t,
        "tipo": best["tipo"],
        "estacoes": tuple(best["estacoes"]),
        "estacoes_nome": " -> ".join(CORE[c]["nome"] for c in best["estacoes"]),
        "score": float(best["score"]),
        "janela_inicio": best["janela"]["inicio"],
        "janela_fim": best["janela"]["fim"],
        "janela_duracao_h": float(best["janela"]["duracao_h"]),
        "assinatura": chain_signature(best),
        "regime": regime,
        "forcas": strengths,
    }


def replay_raw_candidates(levels, maps, active_times, start, common_end):
    rows = []
    t = start
    while t <= common_end:
        best, _confidence, _status, signals = build_candidate_at(
            t, maps, active_times, levels
        )
        if best:
            rows.append(raw_emission(t, best, signals))
        t += timedelta(hours=REPLAY_STEP_H)
    return rows


def classify(raw, params):
    n = len(raw["estacoes"])
    score = raw["score"]
    overlap = raw["janela_duracao_h"]

    if n == 3:
        if (
            score >= params["high_score"]
            and overlap >= params["high_overlap_h"]
        ):
            return "alta", "onda_de_subida_convergente"

        if (
            score >= params["med3_score"]
            and overlap >= params["med3_overlap_h"]
        ):
            return "media", "onda_de_subida_convergente_em_confirmacao"

        return None, None

    if n == 2:
        if (
            score >= params["pair_score"]
            and overlap >= params["pair_overlap_h"]
        ):
            return "media", "cadeia_parcial_de_subida_coerente"

    return None, None


def classified_emission(raw, params):
    confidence, status = classify(raw, params)
    if confidence is None:
        return None

    row = dict(raw)
    row["confianca"] = confidence
    row["status"] = status
    row["score"] = round(row["score"], 3)
    row["janela_duracao_h"] = round(row["janela_duracao_h"], 1)
    return row


def build_clusters(raw_rows, params, year_filter=None):
    clusters = []

    for raw in raw_rows:
        if year_filter is not None and raw["alerta_em"].year not in year_filter:
            continue

        emission = classified_emission(raw, params)
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
            cluster = new_cluster(len(clusters) + 1, emission)
            cluster["regime_primeiro"] = emission["regime"]
            cluster["regime_melhor"] = emission["regime"]
            clusters.append(cluster)
        else:
            before = match["melhor_emissao"]
            update_cluster(match, emission)
            if match["melhor_emissao"] is not before:
                match["regime_melhor"] = emission["regime"]

    return clusters


def units_from_clusters(clusters):
    first = []
    high = []
    medium_only = []

    for c in clusters:
        first_row = dict(c["primeira_emissao"])
        first_row["cluster_id"] = c["cluster_id"]
        first_row["grupo_avaliacao"] = "primeiro_aviso"
        first_row["confianca_final_cluster"] = c["melhor_emissao"]["confianca"]
        first_row["emissoes_cluster"] = c["emissoes"]
        first_row["regime"] = c.get("regime_primeiro", first_row.get("regime"))
        first.append(first_row)

        if c["primeira_alta"] is not None:
            high_row = dict(c["primeira_alta"])
            high_row["cluster_id"] = c["cluster_id"]
            high_row["grupo_avaliacao"] = "primeira_alta"
            high_row["confianca_final_cluster"] = c["melhor_emissao"]["confianca"]
            high_row["emissoes_cluster"] = c["emissoes"]
            high.append(high_row)

        if c["melhor_emissao"]["confianca"] == "media":
            medium_only.append(first_row)

    return first, high, medium_only


def targets_for_years(targets, years):
    years = set(years)
    return [e for e in targets if e["inicio"].year in years]


def evaluate_params(raw_rows, targets, params, years):
    clusters = build_clusters(raw_rows, params, year_filter=set(years))
    first, high, medium_only = units_from_clusters(clusters)
    yt = targets_for_years(targets, years)

    overall_metric, overall_eval = metric_row("primeiro_aviso", first, yt)
    high_metric, high_eval = metric_row("primeira_alta", high, yt)
    medium_metric, medium_eval = metric_row("media_sem_upgrade", medium_only, yt)

    return {
        "clusters": clusters,
        "first": first,
        "high": high,
        "medium_only": medium_only,
        "overall_metric": overall_metric,
        "high_metric": high_metric,
        "medium_metric": medium_metric,
        "overall_eval": overall_eval,
        "high_eval": high_eval,
        "medium_eval": medium_eval,
        "targets": yt,
    }


def param_grid():
    for hs, ho, ms, mo, ps, po in itertools.product(
        HIGH_SCORE_GRID,
        HIGH_OVERLAP_GRID,
        MED3_SCORE_GRID,
        MED3_OVERLAP_GRID,
        PAIR_SCORE_GRID,
        PAIR_OVERLAP_GRID,
    ):
        # Coerência: alta nunca pode ter score/overlap menores que média da cadeia3.
        if hs < ms or ho < mo:
            continue

        yield {
            "high_score": hs,
            "high_overlap_h": ho,
            "med3_score": ms,
            "med3_overlap_h": mo,
            "pair_score": ps,
            "pair_overlap_h": po,
        }


def rank_training(raw_rows, targets, train_years):
    ranked = []

    for params in param_grid():
        result = evaluate_params(raw_rows, targets, params, train_years)
        obj = objective_score(
            result["overall_metric"],
            result["high_metric"],
        )

        ranked.append({
            "params": params,
            "objective": obj,
            "overall": result["overall_metric"],
            "high": result["high_metric"],
            "medium": result["medium_metric"],
        })

    ranked.sort(
        key=lambda x: (
            x["objective"],
            safe_pct(x["overall"]["precisao_24h_pct"]),
            safe_pct(x["high"]["precisao_24h_pct"]),
            safe_pct(x["overall"]["recall_24h_pct"]),
            -x["overall"]["alertas"],
        ),
        reverse=True,
    )
    return ranked


def compact_metric(prefix, m):
    return {
        f"{prefix}_alertas": m["alertas"],
        f"{prefix}_acertos24": m["acertos_24h"],
        f"{prefix}_precisao24_pct": m["precisao_24h_pct"],
        f"{prefix}_recall24_pct": m["recall_24h_pct"],
        f"{prefix}_lead_mediano_h": m["antecedencia_mediana_h"],
        f"{prefix}_erro_centro_mediano_h": m["erro_abs_centro_mediano_h"],
    }


def serialize_eval(row, fold_name):
    return {
        "fold": fold_name,
        "cluster_id": row["cluster_id"],
        "grupo": row["grupo_avaliacao"],
        "alerta_em": fmt_dt(row["alerta_em"]),
        "confianca": row["confianca"],
        "confianca_final_cluster": row["confianca_final_cluster"],
        "regime": row.get("regime"),
        "tipo": row["tipo"],
        "estacoes": row["estacoes_nome"],
        "score": row["score"],
        "janela_inicio": fmt_dt(row["janela_inicio"]),
        "janela_fim": fmt_dt(row["janela_fim"]),
        "janela_duracao_h": row["janela_duracao_h"],
        "acerto_24h": row.get("acerto_24h"),
        "acerto_estrito": row.get("acerto_estrito"),
        "lead_h": None if row.get("lead_h") is None else round(row["lead_h"], 1),
        "erro_centro_h": None if row.get("erro_centro_h") is None else round(row["erro_centro_h"], 1),
        "target_id": row.get("target_id"),
    }


def regime_metrics(evaluated, targets_total, fold_name):
    rows = []
    regimes = sorted({r.get("regime") for r in evaluated if r.get("regime")})

    for regime in regimes:
        subset = [r for r in evaluated if r.get("regime") == regime]
        hits = sum(1 for r in subset if r.get("acerto_24h"))
        rows.append({
            "fold": fold_name,
            "regime": regime,
            "alertas": len(subset),
            "acertos_24h": hits,
            "precisao_24h_pct": round(100 * hits / len(subset), 1) if subset else None,
            "eventos_teste": targets_total,
        })

    return rows


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
            min(levels[code]) + timedelta(hours=168)
            for code in ORDER + [BARCELOS]
            if levels[code]
        ),
    )

    all_targets = [
        e for e in detect_target_events(active_times, levels)
        if start <= e["inicio"] <= common_end
    ]
    targets = [e for e in all_targets if e["significativo"]]

    print("Gerando replay bruto causal uma unica vez...")
    raw_rows = replay_raw_candidates(
        levels, maps, active_times, start, common_end
    )
    print(f"Candidatos brutos: {len(raw_rows)}")

    fold_rows = []
    top_rows = []
    test_alert_rows = []
    regime_rows = []
    summary_folds = []

    for fold in FOLDS:
        print()
        print("=" * 64)
        print(f"FOLD: {fold['nome']}")
        print(
            f"Treino: {fold['train_years']} | "
            f"Teste: {fold['test_year']}"
        )

        ranked = rank_training(
            raw_rows,
            targets,
            fold["train_years"],
        )
        best = ranked[0]
        params = best["params"]

        train_result = evaluate_params(
            raw_rows,
            targets,
            params,
            fold["train_years"],
        )
        test_result = evaluate_params(
            raw_rows,
            targets,
            params,
            [fold["test_year"]],
        )

        row = {
            "fold": fold["nome"],
            "train_years": ",".join(map(str, fold["train_years"])),
            "test_year": fold["test_year"],
            "objective_treino": best["objective"],
            **params,
            **compact_metric("treino", train_result["overall_metric"]),
            **compact_metric("teste", test_result["overall_metric"]),
            **compact_metric("teste_alta", test_result["high_metric"]),
            **compact_metric("teste_media", test_result["medium_metric"]),
        }
        fold_rows.append(row)

        for rank, item in enumerate(ranked[:10], start=1):
            top_rows.append({
                "fold": fold["nome"],
                "rank": rank,
                "objective_treino": item["objective"],
                **item["params"],
                **compact_metric("treino", item["overall"]),
                **compact_metric("treino_alta", item["high"]),
                **compact_metric("treino_media", item["medium"]),
            })

        for eval_row in test_result["overall_eval"]:
            test_alert_rows.append(
                serialize_eval(eval_row, fold["nome"])
            )

        regime_rows.extend(
            regime_metrics(
                test_result["overall_eval"],
                len(test_result["targets"]),
                fold["nome"],
            )
        )

        summary_folds.append({
            "fold": fold["nome"],
            "train_years": fold["train_years"],
            "test_year": fold["test_year"],
            "parametros_escolhidos_sem_ver_teste": params,
            "objective_treino": best["objective"],
            "treino": {
                "geral": train_result["overall_metric"],
                "alta": train_result["high_metric"],
                "media": train_result["medium_metric"],
            },
            "teste_fora_da_amostra": {
                "geral": test_result["overall_metric"],
                "alta": test_result["high_metric"],
                "media": test_result["medium_metric"],
            },
        })

        print("Parametros escolhidos no TREINO:")
        print(json.dumps(params, ensure_ascii=False))
        print(
            "Treino geral: "
            f"precisao={train_result['overall_metric']['precisao_24h_pct']}% | "
            f"recall={train_result['overall_metric']['recall_24h_pct']}% | "
            f"alertas={train_result['overall_metric']['alertas']}"
        )
        print(
            "TESTE fora da amostra: "
            f"precisao={test_result['overall_metric']['precisao_24h_pct']}% | "
            f"recall={test_result['overall_metric']['recall_24h_pct']}% | "
            f"alertas={test_result['overall_metric']['alertas']}"
        )
        print(
            "TESTE alta: "
            f"precisao={test_result['high_metric']['precisao_24h_pct']}% | "
            f"recall={test_result['high_metric']['recall_24h_pct']}% | "
            f"alertas={test_result['high_metric']['alertas']}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with FOLDS_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = list(fold_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(fold_rows)

    with TOP_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = list(top_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(top_rows)

    with ALERTS_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = list(test_alert_rows[0].keys()) if test_alert_rows else [
            "fold", "cluster_id", "grupo", "alerta_em"
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(test_alert_rows)

    with REGIMES_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = list(regime_rows[0].keys()) if regime_rows else [
            "fold", "regime", "alertas", "acertos_24h",
            "precisao_24h_pct", "eventos_teste"
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(regime_rows)

    summary = {
        "modelo": "walkforward_convergencia_v32",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "periodo_disponivel": {
            "inicio": fmt_dt(start),
            "fim": fmt_dt(common_end),
        },
        "eventos_barcelos_significativos": len(targets),
        "candidatos_brutos_replay": len(raw_rows),
        "metodo": (
            "Walk-forward causal. Parametros sao escolhidos somente no periodo "
            "de treino. O ano de teste nao participa da selecao. Objetivo prioriza "
            "precisao sem permitir configuracoes triviais com poucos alertas."
        ),
        "grade": {
            "high_score": HIGH_SCORE_GRID,
            "high_overlap_h": HIGH_OVERLAP_GRID,
            "med3_score": MED3_SCORE_GRID,
            "med3_overlap_h": MED3_OVERLAP_GRID,
            "pair_score": PAIR_SCORE_GRID,
            "pair_overlap_h": PAIR_OVERLAP_GRID,
        },
        "folds": summary_folds,
    }

    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 64)
    print("WALK-FORWARD V3.2 CONCLUIDO")
    print("=" * 64)
    print(f"Arquivos: {FOLDS_CSV}")
    print(f"          {TOP_CSV}")
    print(f"          {ALERTS_CSV}")
    print(f"          {REGIMES_CSV}")
    print(f"          {SUMMARY_JSON}")
    print("Teste somente. Nenhum arquivo do painel foi alterado.")


if __name__ == "__main__":
    main()
