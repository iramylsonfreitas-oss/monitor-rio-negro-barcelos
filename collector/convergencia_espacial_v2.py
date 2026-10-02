import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY_FILE = Path("data/history/hourly.csv")
STATIONS_FILE = Path("data/estacoes.json")

OUTPUT_DIR = Path("artifacts")
OUTPUT_JSON = OUTPUT_DIR / "convergencia_v2.json"
DETAIL_CSV = OUTPUT_DIR / "convergencia_v2_detalhes.csv"
CHAINS_CSV = OUTPUT_DIR / "convergencia_v2_cadeias.csv"

CORE = {
    "14280001": {
        "nome": "Taracua",
        "ordem": 1,
        "lag_mediano_h": 193.5,
        "lag_q25_h": 168.5,
        "lag_q75_h": 230.5,
    },
    "14330000": {
        "nome": "Curicuriari",
        "ordem": 2,
        "lag_mediano_h": 140.0,
        "lag_q25_h": 119.5,
        "lag_q75_h": 165.0,
    },
    "14420000": {
        "nome": "Serrinha",
        "ordem": 3,
        "lag_mediano_h": 87.5,
        "lag_q25_h": 70.8,
        "lag_q75_h": 118.5,
    },
}

ORDER = ["14280001", "14330000", "14420000"]
CUCUI = "14110000"
BARCELOS = "14480002"

# Faixas observadas nos testes entre trechos.
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

DELTA_H = 24
RISE_THRESHOLD_CM = 5.0
MAX_ACTIVE_GAP_H = 36
MAX_RECENT_EVENT_AGE_H = 168
SEGMENT_TOLERANCE_H = 24.0

STRONG_24H_CM = 5.0
STRONG_72H_CM = 12.0
MODERATE_72H_CM = 8.0
MODERATE_7D_CM = 8.0

MIN_OVERLAP_H = 1.0


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


def load_current():
    data = json.loads(STATIONS_FILE.read_text(encoding="utf-8"))
    return {item["estacao"]: item for item in data.get("estacoes", [])}, data


def load_history():
    wanted = set(CORE) | {CUCUI, BARCELOS}
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


def signal_status(item):
    if not item:
        return False, "sem_dado", "estacao_sem_dado_atual"
    if item.get("dado_desatualizado"):
        return False, "desatualizado", "dado_desatualizado"

    v24 = float(item.get("variacao_24h_cm") or 0)
    v72 = float(item.get("variacao_72h_cm") or 0)
    v7d = float(item.get("variacao_7d_cm") or 0)

    if v24 >= STRONG_24H_CM or v72 >= STRONG_72H_CM:
        return True, "forte", "subida_confirmada_24h_ou_72h"
    if v72 >= MODERATE_72H_CM and v7d >= MODERATE_7D_CM:
        return True, "moderado", "subida_persistente_72h_e_7d"
    return False, "fraco", "sem_sinal_suficiente_de_subida"


def build_delta24(levels):
    shift = timedelta(hours=DELTA_H)
    return {
        dt: level - levels[dt - shift]
        for dt, level in levels.items()
        if dt - shift in levels
    }


def recent_rise_episodes(levels):
    if not levels:
        return []

    delta = build_delta24(levels)
    active = sorted(dt for dt, change in delta.items() if change >= RISE_THRESHOLD_CM)
    if not active:
        return []

    groups = []
    group = [active[0]]
    for dt in active[1:]:
        gap_h = (dt - group[-1]).total_seconds() / 3600
        if gap_h <= MAX_ACTIVE_GAP_H:
            group.append(dt)
        else:
            groups.append(group)
            group = [dt]
    groups.append(group)

    latest_data = max(levels)
    cutoff = latest_data - timedelta(hours=MAX_RECENT_EVENT_AGE_H)
    episodes = []

    for idx, g in enumerate(groups, start=1):
        if g[-1] < cutoff:
            continue

        start = g[0]
        last_active = g[-1]
        inspect_end = min(latest_data, last_active + timedelta(hours=24))
        ts = sorted(dt for dt in levels if start <= dt <= inspect_end)

        amplitude = None
        if ts and start in levels:
            amplitude = max(levels[t] for t in ts) - levels[start]

        episodes.append({
            "id": f"E{idx}",
            "inicio": start,
            "ultimo_ativo": last_active,
            "idade_ultimo_ativo_h": (latest_data - last_active).total_seconds() / 3600,
            "amplitude_cm": amplitude,
        })

    return episodes


def project_arrival(anchor, cfg):
    return {
        "inicio": anchor + timedelta(hours=cfg["lag_q25_h"]),
        "centro": anchor + timedelta(hours=cfg["lag_mediano_h"]),
        "fim": anchor + timedelta(hours=cfg["lag_q75_h"]),
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


def segment_check(source_code, target_code, source_event, target_event):
    cfg = SEGMENTS[(source_code, target_code)]
    observed = (target_event["inicio"] - source_event["inicio"]).total_seconds() / 3600
    low = cfg["q25_h"] - SEGMENT_TOLERANCE_H
    high = cfg["q75_h"] + SEGMENT_TOLERANCE_H
    ok = low <= observed <= high

    distance = abs(observed - cfg["mediana_h"])
    half_span = max((high - low) / 2, 1.0)
    score = max(0.0, 1.0 - distance / half_span)

    return {
        "trecho": cfg["nome"],
        "observado_h": observed,
        "faixa_min_h": low,
        "faixa_max_h": high,
        "mediana_h": cfg["mediana_h"],
        "coerente": ok,
        "score_proximidade": score,
    }


def event_projection(code, event):
    return project_arrival(event["inicio"], CORE[code])


def candidate_pair(source, target, source_event, target_event):
    check = segment_check(source, target, source_event, target_event)
    if not check["coerente"]:
        return None

    p1 = event_projection(source, source_event)
    p2 = event_projection(target, target_event)
    overlap = overlap_interval([p1, p2])
    if not overlap:
        return None

    recency = max(
        0.0,
        1.0 - max(source_event["idade_ultimo_ativo_h"], target_event["idade_ultimo_ativo_h"]) / MAX_RECENT_EVENT_AGE_H
    )
    overlap_score = min(overlap["duracao_h"] / 24.0, 1.0)
    score = 0.55 * check["score_proximidade"] + 0.25 * overlap_score + 0.20 * recency

    return {
        "tipo": "par",
        "estacoes": [source, target],
        "eventos": [source_event, target_event],
        "checks": [check],
        "janela": overlap,
        "score": score,
    }


def candidate_chain_three(t_event, c_event, s_event):
    c1 = segment_check(ORDER[0], ORDER[1], t_event, c_event)
    c2 = segment_check(ORDER[1], ORDER[2], c_event, s_event)

    if not (c1["coerente"] and c2["coerente"]):
        return None

    projections = [
        event_projection(ORDER[0], t_event),
        event_projection(ORDER[1], c_event),
        event_projection(ORDER[2], s_event),
    ]
    overlap = overlap_interval(projections)
    if not overlap:
        return None

    recency = max(
        0.0,
        1.0 - max(
            t_event["idade_ultimo_ativo_h"],
            c_event["idade_ultimo_ativo_h"],
            s_event["idade_ultimo_ativo_h"],
        ) / MAX_RECENT_EVENT_AGE_H
    )
    chronology_score = (c1["score_proximidade"] + c2["score_proximidade"]) / 2
    overlap_score = min(overlap["duracao_h"] / 24.0, 1.0)
    score = 0.60 * chronology_score + 0.25 * overlap_score + 0.15 * recency

    return {
        "tipo": "cadeia_3",
        "estacoes": ORDER[:],
        "eventos": [t_event, c_event, s_event],
        "checks": [c1, c2],
        "janela": overlap,
        "score": score,
    }


def chain_is_current(chain, signal_by_code):
    return all(signal_by_code.get(code, {}).get("ativo", False) for code in chain["estacoes"])


def serialize_chain(chain):
    if not chain:
        return None
    return {
        "tipo": chain["tipo"],
        "estacoes": chain["estacoes"],
        "nomes": [CORE[c]["nome"] for c in chain["estacoes"]],
        "eventos": [
            {
                "id": e["id"],
                "inicio": fmt_dt(e["inicio"]),
                "ultimo_ativo": fmt_dt(e["ultimo_ativo"]),
                "idade_ultimo_ativo_h": round(e["idade_ultimo_ativo_h"], 1),
                "amplitude_cm": None if e["amplitude_cm"] is None else round(e["amplitude_cm"], 1),
            }
            for e in chain["eventos"]
        ],
        "checks": [
            {
                **c,
                "observado_h": round(c["observado_h"], 1),
                "faixa_min_h": round(c["faixa_min_h"], 1),
                "faixa_max_h": round(c["faixa_max_h"], 1),
                "mediana_h": round(c["mediana_h"], 1),
                "score_proximidade": round(c["score_proximidade"], 3),
            }
            for c in chain["checks"]
        ],
        "janela_consenso": {
            "inicio": fmt_dt(chain["janela"]["inicio"]),
            "fim": fmt_dt(chain["janela"]["fim"]),
            "duracao_h": round(chain["janela"]["duracao_h"], 1),
        },
        "score": round(chain["score"], 3),
    }


def main():
    if not STATIONS_FILE.exists():
        raise RuntimeError("data/estacoes.json nao encontrado.")
    if not HISTORY_FILE.exists():
        raise RuntimeError("data/history/hourly.csv nao encontrado.")

    current, raw_current = load_current()
    history = load_history()

    signal_by_code = {}
    episodes_by_code = {}
    details = []

    for code in ORDER:
        item = current.get(code)
        active, strength, reason = signal_status(item)
        episodes = recent_rise_episodes(history.get(code, {}))
        signal_by_code[code] = {
            "ativo": active,
            "forca": strength,
            "motivo": reason,
        }
        episodes_by_code[code] = episodes

        details.append({
            "estacao": code,
            "nome": CORE[code]["nome"],
            "sinal_ativo": active,
            "forca_sinal": strength,
            "motivo_sinal": reason,
            "variacao_24h_cm": item.get("variacao_24h_cm") if item else None,
            "variacao_72h_cm": item.get("variacao_72h_cm") if item else None,
            "variacao_7d_cm": item.get("variacao_7d_cm") if item else None,
            "episodios_recentes": len(episodes),
            "ultimo_episodio_inicio": fmt_dt(episodes[-1]["inicio"]) if episodes else None,
            "ultimo_episodio_ativo": fmt_dt(episodes[-1]["ultimo_ativo"]) if episodes else None,
        })

    candidates = []

    # Cadeias completas.
    for te in episodes_by_code[ORDER[0]]:
        for ce in episodes_by_code[ORDER[1]]:
            for se in episodes_by_code[ORDER[2]]:
                c = candidate_chain_three(te, ce, se)
                if c and chain_is_current(c, signal_by_code):
                    candidates.append(c)

    # Pares consecutivos.
    for source, target in ((ORDER[0], ORDER[1]), (ORDER[1], ORDER[2])):
        for se in episodes_by_code[source]:
            for te in episodes_by_code[target]:
                c = candidate_pair(source, target, se, te)
                if c and chain_is_current(c, signal_by_code):
                    candidates.append(c)

    # Prioriza mais estações; depois score; depois maior sobreposição.
    candidates.sort(
        key=lambda c: (
            len(c["estacoes"]),
            c["score"],
            c["janela"]["duracao_h"],
        ),
        reverse=True,
    )
    best = candidates[0] if candidates else None

    active_count = sum(1 for code in ORDER if signal_by_code[code]["ativo"])

    if best and len(best["estacoes"]) == 3:
        confidence = "alta"
        status = "onda_de_subida_convergente"
    elif best and len(best["estacoes"]) == 2:
        confidence = "media"
        status = "cadeia_parcial_de_subida_coerente"
    elif active_count >= 2:
        confidence = "observacao"
        status = "multiplos_sinais_sem_cadeia_espacial"
    elif active_count == 1:
        confidence = "baixa"
        status = "sinal_isolado_de_subida"
    else:
        confidence = "sem_alerta"
        status = "sem_onda_de_subida_convergente"

    cucui_item = current.get(CUCUI)
    cucui_active, cucui_strength, _ = signal_status(cucui_item)

    output = {
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "modelo": "convergencia_espacial_v2",
        "status": status,
        "confianca": confidence,
        "core_ativas": active_count,
        "cadeias_validas": len(candidates),
        "melhor_cadeia": serialize_chain(best),
        "estacoes": details,
        "cucui_contexto": {
            "participa_eta": False,
            "sinal_ativo": cucui_active,
            "forca_sinal": cucui_strength,
            "variacao_24h_cm": cucui_item.get("variacao_24h_cm") if cucui_item else None,
            "variacao_72h_cm": cucui_item.get("variacao_72h_cm") if cucui_item else None,
            "variacao_7d_cm": cucui_item.get("variacao_7d_cm") if cucui_item else None,
        },
        "nota": (
            "A V2 so atribui confianca media/alta quando existe cadeia cronologica "
            "valida entre estacoes consecutivas e sobreposicao das janelas projetadas "
            "para Barcelos. Nao representa tempo fisico fixo de viagem da agua."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    with DETAIL_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "estacao", "nome", "sinal_ativo", "forca_sinal", "motivo_sinal",
            "variacao_24h_cm", "variacao_72h_cm", "variacao_7d_cm",
            "episodios_recentes", "ultimo_episodio_inicio", "ultimo_episodio_ativo",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(details)

    with CHAINS_CSV.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "tipo", "estacoes", "nomes", "score",
            "janela_inicio", "janela_fim", "janela_duracao_h",
            "eventos_inicio", "checks",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in candidates:
            sc = serialize_chain(c)
            w.writerow({
                "tipo": sc["tipo"],
                "estacoes": " | ".join(sc["estacoes"]),
                "nomes": " | ".join(sc["nomes"]),
                "score": sc["score"],
                "janela_inicio": sc["janela_consenso"]["inicio"],
                "janela_fim": sc["janela_consenso"]["fim"],
                "janela_duracao_h": sc["janela_consenso"]["duracao_h"],
                "eventos_inicio": " | ".join(e["inicio"] for e in sc["eventos"]),
                "checks": json.dumps(sc["checks"], ensure_ascii=False),
            })

    print()
    print("============================================")
    print("MOTOR DE CONVERGENCIA ESPACIAL V2")
    print("============================================")
    print()
    print(f"Status: {status}")
    print(f"Confianca: {confidence}")
    print(f"Core ativas: {active_count} / 3")
    print(f"Cadeias validas encontradas: {len(candidates)}")

    if best:
        sc = serialize_chain(best)
        print(f"Melhor cadeia: {sc['tipo']} | {' -> '.join(sc['nomes'])} | score={sc['score']}")
        print(
            "Janela consenso: "
            f"{sc['janela_consenso']['inicio']} -> {sc['janela_consenso']['fim']} "
            f"({sc['janela_consenso']['duracao_h']} h)"
        )
        print("Cronologia:")
        for chk in sc["checks"]:
            print(
                f"  {chk['trecho']} | observado={chk['observado_h']} h | "
                f"faixa=[{chk['faixa_min_h']}, {chk['faixa_max_h']}] | coerente={chk['coerente']}"
            )
    else:
        print("Nenhuma cadeia cronologica + ETA coerente foi encontrada.")

    print()
    print("ESTACOES")
    print("--------------------------------------------")
    for d in details:
        print(
            f"{d['nome']:<12} ativo={d['sinal_ativo']} "
            f"forca={d['forca_sinal']:<9} "
            f"24h={d['variacao_24h_cm']} 72h={d['variacao_72h_cm']} 7d={d['variacao_7d_cm']} "
            f"episodios={d['episodios_recentes']} ultimo={d['ultimo_episodio_inicio']}"
        )

    print()
    print(f"Cucui contexto: {output['cucui_contexto']}")
    print()
    print(f"Arquivos: {OUTPUT_JSON} {DETAIL_CSV} {CHAINS_CSV}")
    print()
    print("Teste somente. Nenhum arquivo do painel foi alterado.")


if __name__ == "__main__":
    main()
