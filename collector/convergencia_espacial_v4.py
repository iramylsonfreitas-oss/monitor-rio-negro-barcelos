import json
from datetime import datetime, timezone
from pathlib import Path

from convergencia_espacial_v3 import (
    STATIONS_FILE,
    HISTORY_FILE,
    OUTPUT_DIR,
    CORE,
    ORDER,
    CUCUI,
    load_current,
    load_history,
    signal_status,
    recent_rise_episodes,
    candidate_chain_three,
    candidate_pair,
    chain_is_current,
    serialize_chain,
)

OUTPUT_JSON = OUTPUT_DIR / "convergencia_v4.json"
DETAIL_JSON = OUTPUT_DIR / "convergencia_v4_detalhes.json"

# Limites escolhidos a partir do walk-forward V3.2.
# Nos dois folds, a configuracao de "Alta" escolhida no passado foi:
# score >= 0.70 e sobreposicao >= 8 h.
ALERT_SCORE_MIN = 0.70
ALERT_OVERLAP_H_MIN = 8.0


def main():
    if not STATIONS_FILE.exists():
        raise RuntimeError("data/estacoes.json nao encontrado.")
    if not HISTORY_FILE.exists():
        raise RuntimeError("data/history/hourly.csv nao encontrado.")

    current, _raw_current = load_current()
    history = load_history()

    signal_by_code = {}
    episodes_by_code = {}

    for code in ORDER:
        item = current.get(code)
        active, strength, reason = signal_status(item)
        signal_by_code[code] = {
            "ativo": active,
            "forca": strength,
            "motivo": reason,
            "v24": item.get("variacao_24h_cm") if item else None,
            "v72": item.get("variacao_72h_cm") if item else None,
            "v7d": item.get("variacao_7d_cm") if item else None,
        }
        episodes_by_code[code] = recent_rise_episodes(history.get(code, {}))

    full_chains = []
    for te in episodes_by_code[ORDER[0]]:
        for ce in episodes_by_code[ORDER[1]]:
            for se in episodes_by_code[ORDER[2]]:
                c = candidate_chain_three(te, ce, se)
                if c and chain_is_current(c, signal_by_code):
                    full_chains.append(c)

    full_chains.sort(
        key=lambda c: (c["score"], c["janela"]["duracao_h"]),
        reverse=True,
    )
    best_full = full_chains[0] if full_chains else None

    # Pares consecutivos so servem como diagnostico interno.
    # Nunca geram data prevista nem ALERTA PREDITIVO na V4.
    valid_pairs = []
    for source, target in ((ORDER[0], ORDER[1]), (ORDER[1], ORDER[2])):
        for se in episodes_by_code[source]:
            for te in episodes_by_code[target]:
                c = candidate_pair(source, target, se, te)
                if c and chain_is_current(c, signal_by_code):
                    valid_pairs.append(c)

    active_count = sum(1 for code in ORDER if signal_by_code[code]["ativo"])

    alert_ok = bool(
        best_full
        and best_full["score"] >= ALERT_SCORE_MIN
        and best_full["janela"]["duracao_h"] >= ALERT_OVERLAP_H_MIN
    )

    if alert_ok:
        estado = "alerta_preditivo"
        mensagem = (
            "Cadeia completa Taracua -> Curicuriari -> Serrinha "
            "compativel com propagacao ate Barcelos."
        )
        janela = {
            "inicio": serialize_chain(best_full)["janela_consenso"]["inicio"],
            "fim": serialize_chain(best_full)["janela_consenso"]["fim"],
            "duracao_h": serialize_chain(best_full)["janela_consenso"]["duracao_h"],
        }
        confianca = "alta_experimental"
    elif active_count > 0 or best_full or valid_pairs:
        estado = "observacao"
        mensagem = (
            "Ha movimentacao no corredor, mas sem evidencia suficiente "
            "para publicar uma data prevista para Barcelos."
        )
        janela = None
        confianca = "nao_aplicavel"
    else:
        estado = "sem_alerta"
        mensagem = "Sem evidencia relevante de onda de subida convergente."
        janela = None
        confianca = "nao_aplicavel"

    cucui_item = current.get(CUCUI)
    cucui_active, cucui_strength, _ = signal_status(cucui_item)

    output = {
        "modelo": "convergencia_espacial_v4_operacional",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "estado": estado,
        "mensagem": mensagem,
        "confianca": confianca,
        "janela_previsao_barcelos": janela,
        "criterio_alerta": {
            "cadeia_obrigatoria": "Taracua -> Curicuriari -> Serrinha",
            "score_min": ALERT_SCORE_MIN,
            "sobreposicao_min_h": ALERT_OVERLAP_H_MIN,
            "pares_geram_previsao": False,
        },
        "core_ativas": active_count,
        "cadeias_completas_validas": len(full_chains),
        "pares_validos_diagnosticos": len(valid_pairs),
        "melhor_cadeia_completa": serialize_chain(best_full),
        "cucui_contexto": {
            "participa_previsao": False,
            "sinal_ativo": cucui_active,
            "forca_sinal": cucui_strength,
            "v24": cucui_item.get("variacao_24h_cm") if cucui_item else None,
            "v72": cucui_item.get("variacao_72h_cm") if cucui_item else None,
            "v7d": cucui_item.get("variacao_7d_cm") if cucui_item else None,
        },
        "nota": (
            "A V4 so publica janela estimada quando existe cadeia completa "
            "e qualificada. Pares consecutivos permanecem apenas como observacao interna."
        ),
    }

    details = {
        "estacoes": signal_by_code,
        "episodios_recentes": {
            code: [
                {
                    "id": e["id"],
                    "inicio": e["inicio"].strftime("%Y-%m-%d %H:%M:%S"),
                    "ultimo_ativo": e["ultimo_ativo"].strftime("%Y-%m-%d %H:%M:%S"),
                    "idade_ultimo_ativo_h": round(e["idade_ultimo_ativo_h"], 1),
                }
                for e in episodes_by_code[code]
            ]
            for code in ORDER
        },
        "pares_validos": [serialize_chain(c) for c in valid_pairs],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    DETAIL_JSON.write_text(
        json.dumps(details, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("============================================")
    print("CONVERGENCIA ESPACIAL V4 OPERACIONAL")
    print("============================================")
    print(f"Estado: {estado}")
    print(f"Core ativas: {active_count}/3")
    print(f"Cadeias completas validas: {len(full_chains)}")
    print(f"Pares validos (diagnostico): {len(valid_pairs)}")

    if best_full:
        sc = serialize_chain(best_full)
        print(f"Melhor cadeia score: {sc['score']}")
        print(
            "Sobreposicao: "
            f"{sc['janela_consenso']['duracao_h']} h"
        )

    if janela:
        print(
            f"Janela publicada: {janela['inicio']} -> {janela['fim']}"
        )
    else:
        print("Nenhuma data prevista sera publicada.")

    print()
    print(f"Arquivos: {OUTPUT_JSON} {DETAIL_JSON}")
    print("Teste somente. Nenhum arquivo do painel foi alterado.")


if __name__ == "__main__":
    main()
