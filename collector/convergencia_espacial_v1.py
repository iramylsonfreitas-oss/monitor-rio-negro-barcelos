import csv
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

HISTORY_FILE = Path("data/history/hourly.csv")
STATIONS_FILE = Path("data/estacoes.json")

OUTPUT_DIR = Path("artifacts")
OUTPUT_JSON = OUTPUT_DIR / "convergencia.json"
DETAIL_CSV = OUTPUT_DIR / "convergencia_detalhes.csv"

# Estações principais do modelo preditivo.
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

CUCUI = "14110000"
BARCELOS = "14480002"

# Calibrações entre trechos, apenas para teste de coerência espacial.
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

# Detecção do início de uma onda de subida.
DELTA_H = 24
RISE_THRESHOLD_CM = 5.0
MAX_ACTIVE_GAP_H = 36
MAX_RECENT_EVENT_AGE_H = 168

# Critério operacional do sinal atual.
# Forte: +5 cm/24h ou +12 cm/72h.
# Moderado: +8 cm/72h e +8 cm/7d.
STRONG_24H_CM = 5.0
STRONG_72H_CM = 12.0
MODERATE_72H_CM = 8.0
MODERATE_7D_CM = 8.0

# Tolerância extra ao testar os atrasos entre estações consecutivas.
SEGMENT_TOLERANCE_H = 24.0


def parse_dt(value):
    if not value:
        return None

    value = str(value).strip().replace(".0", "")

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return None


def fmt_dt(value):
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")


def load_current():
    data = json.loads(
        STATIONS_FILE.read_text(encoding="utf-8")
    )

    return {
        item["estacao"]: item
        for item in data.get("estacoes", [])
    }, data


def load_history():
    wanted = set(CORE) | {CUCUI, BARCELOS}
    series = {code: {} for code in wanted}

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

            dt = parse_dt(row.get("hora_manaus"))
            level = row.get("nivel_cm")

            if dt is None or level in (None, ""):
                continue

            try:
                level = float(level)
            except ValueError:
                continue

            series[code][dt] = level

    return series


def signal_status(item):
    if not item:
        return {
            "ativo": False,
            "forca": "sem_dado",
            "score": 0,
            "motivo": "estacao_sem_dado_atual",
        }

    if item.get("dado_desatualizado"):
        return {
            "ativo": False,
            "forca": "desatualizado",
            "score": 0,
            "motivo": "dado_desatualizado",
        }

    v24 = float(item.get("variacao_24h_cm") or 0.0)
    v72 = float(item.get("variacao_72h_cm") or 0.0)
    v7d = float(item.get("variacao_7d_cm") or 0.0)

    if v24 >= STRONG_24H_CM or v72 >= STRONG_72H_CM:
        return {
            "ativo": True,
            "forca": "forte",
            "score": 2,
            "motivo": "subida_confirmada_24h_ou_72h",
        }

    if v72 >= MODERATE_72H_CM and v7d >= MODERATE_7D_CM:
        return {
            "ativo": True,
            "forca": "moderado",
            "score": 1,
            "motivo": "subida_persistente_72h_e_7d",
        }

    return {
        "ativo": False,
        "forca": "fraco",
        "score": 0,
        "motivo": "sem_sinal_suficiente_de_subida",
    }


def build_delta24(levels):
    result = {}
    shift = timedelta(hours=DELTA_H)

    for dt, level in levels.items():
        previous = levels.get(dt - shift)
        if previous is not None:
            result[dt] = level - previous

    return result


def recent_rise_episode(levels):
    if not levels:
        return None

    delta = build_delta24(levels)

    active = sorted(
        dt for dt, change in delta.items()
        if change >= RISE_THRESHOLD_CM
    )

    if not active:
        return None

    groups = []
    current = [active[0]]

    for dt in active[1:]:
        gap_h = (
            dt - current[-1]
        ).total_seconds() / 3600

        if gap_h <= MAX_ACTIVE_GAP_H:
            current.append(dt)
        else:
            groups.append(current)
            current = [dt]

    groups.append(current)

    latest_data = max(levels)
    cutoff = latest_data - timedelta(
        hours=MAX_RECENT_EVENT_AGE_H
    )

    recent = [
        group for group in groups
        if group[-1] >= cutoff
    ]

    if not recent:
        return None

    group = recent[-1]
    start = group[0]
    last_active = group[-1]

    # Mede apenas a amplitude observada no episódio recente.
    inspect_end = min(
        latest_data,
        last_active + timedelta(hours=24),
    )

    episode_times = sorted(
        dt for dt in levels
        if start <= dt <= inspect_end
    )

    start_level = levels.get(start)

    if start_level is None or not episode_times:
        amplitude = None
    else:
        amplitude = (
            max(levels[dt] for dt in episode_times)
            - start_level
        )

    return {
        "inicio": start,
        "ultimo_ativo": last_active,
        "idade_ultimo_ativo_h": (
            latest_data - last_active
        ).total_seconds() / 3600,
        "amplitude_cm": amplitude,
    }


def project_arrival(anchor, calibration):
    return {
        "inicio": anchor + timedelta(
            hours=calibration["lag_q25_h"]
        ),
        "centro": anchor + timedelta(
            hours=calibration["lag_mediano_h"]
        ),
        "fim": anchor + timedelta(
            hours=calibration["lag_q75_h"]
        ),
    }


def max_overlap_window(windows):
    """
    Retorna a região temporal coberta pelo maior número de janelas.
    Para confiança operacional exigimos pelo menos 2 janelas.
    """
    if not windows:
        return None

    points = sorted(
        set(
            [w["inicio"] for w in windows]
            + [w["fim"] for w in windows]
        )
    )

    best_count = 0
    best_intervals = []

    for left, right in zip(points, points[1:]):
        if left == right:
            continue

        midpoint = left + (right - left) / 2

        count = sum(
            1 for w in windows
            if w["inicio"] <= midpoint <= w["fim"]
        )

        if count > best_count:
            best_count = count
            best_intervals = [(left, right)]
        elif count == best_count and count > 0:
            best_intervals.append((left, right))

    if best_count == 0:
        return None

    # Une intervalos adjacentes com a mesma cobertura máxima.
    merged = []

    for left, right in best_intervals:
        if merged and merged[-1][1] == left:
            merged[-1] = (merged[-1][0], right)
        else:
            merged.append((left, right))

    # Escolhe o maior bloco.
    left, right = max(
        merged,
        key=lambda pair: (
            pair[1] - pair[0]
        ).total_seconds(),
    )

    return {
        "inicio": left,
        "fim": right,
        "cobertura": best_count,
    }


def chronology_check(details):
    by_code = {
        item["estacao"]: item
        for item in details
        if item.get("anchor_inicio")
    }

    tests = []

    for (source, target), cfg in SEGMENTS.items():
        src = by_code.get(source)
        dst = by_code.get(target)

        if not src or not dst:
            continue

        observed = (
            dst["anchor_inicio"]
            - src["anchor_inicio"]
        ).total_seconds() / 3600

        low = cfg["q25_h"] - SEGMENT_TOLERANCE_H
        high = cfg["q75_h"] + SEGMENT_TOLERANCE_H

        ok = low <= observed <= high

        tests.append(
            {
                "trecho": cfg["nome"],
                "atraso_observado_h": observed,
                "faixa_aceitavel_h": [low, high],
                "coerente": ok,
            }
        )

    if not tests:
        return {
            "avaliado": False,
            "coerente": None,
            "testes": [],
        }

    return {
        "avaliado": True,
        "coerente": all(
            item["coerente"]
            for item in tests
        ),
        "testes": tests,
    }


def main():
    if not STATIONS_FILE.exists():
        raise RuntimeError(
            "data/estacoes.json não encontrado."
        )

    if not HISTORY_FILE.exists():
        raise RuntimeError(
            "data/history/hourly.csv não encontrado."
        )

    current, raw_current = load_current()
    history = load_history()

    details = []
    windows = []

    for code, cfg in CORE.items():
        current_item = current.get(code)
        signal = signal_status(current_item)
        episode = recent_rise_episode(
            history.get(code, {})
        )

        anchor = (
            episode["inicio"]
            if episode and signal["ativo"]
            else None
        )

        projection = (
            project_arrival(anchor, cfg)
            if anchor
            else None
        )

        detail = {
            "estacao": code,
            "nome": cfg["nome"],
            "ordem": cfg["ordem"],
            "sinal_ativo": signal["ativo"],
            "forca_sinal": signal["forca"],
            "score_sinal": signal["score"],
            "motivo_sinal": signal["motivo"],
            "variacao_24h_cm": (
                current_item.get("variacao_24h_cm")
                if current_item else None
            ),
            "variacao_72h_cm": (
                current_item.get("variacao_72h_cm")
                if current_item else None
            ),
            "variacao_7d_cm": (
                current_item.get("variacao_7d_cm")
                if current_item else None
            ),
            "tendencia_atual": (
                current_item.get("tendencia")
                if current_item else None
            ),
            "anchor_inicio": anchor,
            "anchor_ultimo_ativo": (
                episode["ultimo_ativo"]
                if episode else None
            ),
            "anchor_amplitude_cm": (
                episode["amplitude_cm"]
                if episode else None
            ),
            "janela_inicio": (
                projection["inicio"]
                if projection else None
            ),
            "janela_centro": (
                projection["centro"]
                if projection else None
            ),
            "janela_fim": (
                projection["fim"]
                if projection else None
            ),
        }

        details.append(detail)

        if projection:
            windows.append(
                {
                    "estacao": code,
                    "nome": cfg["nome"],
                    **projection,
                }
            )

    chronology = chronology_check(details)
    overlap = max_overlap_window(windows)

    active_core = [
        item for item in details
        if item["sinal_ativo"]
    ]

    anchored_core = [
        item for item in details
        if item["anchor_inicio"] is not None
    ]

    active_count = len(active_core)
    anchored_count = len(anchored_core)
    max_coverage = (
        overlap["cobertura"]
        if overlap else 0
    )

    if (
        active_count == 3
        and anchored_count == 3
        and max_coverage == 3
        and chronology.get("coerente") is not False
    ):
        confidence = "alta"
        status = "onda_de_subida_convergente"
    elif (
        active_count >= 2
        and anchored_count >= 2
        and max_coverage >= 2
    ):
        confidence = "media"
        status = "sinais_de_subida_convergentes"
    elif active_count >= 1:
        confidence = "baixa"
        status = "sinal_de_subida_em_observacao"
    else:
        confidence = "sem_alerta"
        status = "sem_onda_de_subida_convergente"

    # Cucuí é contexto, não participa da ETA.
    cucui_current = current.get(CUCUI)
    cucui_signal = signal_status(cucui_current)

    barcelos_current = current.get(BARCELOS)

    output = {
        "gerado_em_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "modelo": "convergencia_espacial_v1",
        "objetivo": (
            "detectar convergencia de sinais de subida "
            "a montante e estimar janela historica para Barcelos"
        ),
        "status": status,
        "confianca": confidence,
        "estacoes_core_ativas": active_count,
        "estacoes_core_ancoradas": anchored_count,
        "cobertura_maxima_janelas": max_coverage,
        "janela_consenso": (
            {
                "inicio_manaus": fmt_dt(
                    overlap["inicio"]
                ),
                "fim_manaus": fmt_dt(
                    overlap["fim"]
                ),
                "cobertura_estacoes": overlap[
                    "cobertura"
                ],
            }
            if overlap and overlap["cobertura"] >= 2
            else None
        ),
        "coerencia_espacial": {
            "avaliado": chronology["avaliado"],
            "coerente": chronology["coerente"],
            "testes": [
                {
                    **item,
                    "atraso_observado_h": round(
                        item["atraso_observado_h"],
                        1,
                    ),
                    "faixa_aceitavel_h": [
                        round(item["faixa_aceitavel_h"][0], 1),
                        round(item["faixa_aceitavel_h"][1], 1),
                    ],
                }
                for item in chronology["testes"]
            ],
        },
        "barcelos_agora": (
            {
                "nivel_m": barcelos_current.get("nivel_m"),
                "variacao_24h_cm": barcelos_current.get(
                    "variacao_24h_cm"
                ),
                "variacao_72h_cm": barcelos_current.get(
                    "variacao_72h_cm"
                ),
                "tendencia": barcelos_current.get(
                    "tendencia"
                ),
                "data_medicao_manaus": barcelos_current.get(
                    "data_medicao_manaus"
                ),
            }
            if barcelos_current else None
        ),
        "cucui_contexto": {
            "participa_eta": False,
            "sinal_ativo": cucui_signal["ativo"],
            "forca_sinal": cucui_signal["forca"],
            "variacao_24h_cm": (
                cucui_current.get("variacao_24h_cm")
                if cucui_current else None
            ),
            "variacao_72h_cm": (
                cucui_current.get("variacao_72h_cm")
                if cucui_current else None
            ),
            "variacao_7d_cm": (
                cucui_current.get("variacao_7d_cm")
                if cucui_current else None
            ),
        },
        "estacoes": [],
        "observacao": (
            "Janela estatistica baseada em defasagens historicas "
            "observadas do sinal hidrologico. Nao representa tempo "
            "fixo de viagem da agua."
        ),
    }

    for item in details:
        output["estacoes"].append(
            {
                "estacao": item["estacao"],
                "nome": item["nome"],
                "ordem": item["ordem"],
                "sinal_ativo": item["sinal_ativo"],
                "forca_sinal": item["forca_sinal"],
                "motivo_sinal": item["motivo_sinal"],
                "variacao_24h_cm": item["variacao_24h_cm"],
                "variacao_72h_cm": item["variacao_72h_cm"],
                "variacao_7d_cm": item["variacao_7d_cm"],
                "tendencia_atual": item["tendencia_atual"],
                "inicio_evento_manaus": fmt_dt(
                    item["anchor_inicio"]
                ),
                "janela_prevista_inicio_manaus": fmt_dt(
                    item["janela_inicio"]
                ),
                "janela_prevista_centro_manaus": fmt_dt(
                    item["janela_centro"]
                ),
                "janela_prevista_fim_manaus": fmt_dt(
                    item["janela_fim"]
                ),
            }
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_JSON.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fields = [
        "estacao",
        "nome",
        "ordem",
        "sinal_ativo",
        "forca_sinal",
        "variacao_24h_cm",
        "variacao_72h_cm",
        "variacao_7d_cm",
        "tendencia_atual",
        "inicio_evento_manaus",
        "janela_prevista_inicio_manaus",
        "janela_prevista_centro_manaus",
        "janela_prevista_fim_manaus",
    ]

    with DETAIL_CSV.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )
        writer.writeheader()

        for item in output["estacoes"]:
            writer.writerow(
                {
                    field: item.get(field)
                    for field in fields
                }
            )

    print()
    print("============================================")
    print("MOTOR DE CONVERGENCIA ESPACIAL V1")
    print("============================================")
    print()
    print("Status:", output["status"])
    print("Confianca:", output["confianca"])
    print(
        "Core ativas:",
        output["estacoes_core_ativas"],
        "/ 3",
    )
    print(
        "Core ancoradas:",
        output["estacoes_core_ancoradas"],
        "/ 3",
    )
    print(
        "Cobertura maxima das janelas:",
        output["cobertura_maxima_janelas"],
    )

    if output["janela_consenso"]:
        print(
            "Janela consenso:",
            output["janela_consenso"][
                "inicio_manaus"
            ],
            "->",
            output["janela_consenso"][
                "fim_manaus"
            ],
        )
    else:
        print("Janela consenso: nenhuma")

    print()
    print("ESTACOES")
    print("--------------------------------------------")

    for item in output["estacoes"]:
        print(
            f"{item['nome']:<12} "
            f"ativo={item['sinal_ativo']} "
            f"forca={item['forca_sinal']:<9} "
            f"24h={item['variacao_24h_cm']} "
            f"72h={item['variacao_72h_cm']} "
            f"7d={item['variacao_7d_cm']} "
            f"inicio={item['inicio_evento_manaus']} "
            f"janela={item['janela_prevista_inicio_manaus']} "
            f"-> {item['janela_prevista_fim_manaus']}"
        )

    print()
    print("COERENCIA ESPACIAL")
    print("--------------------------------------------")

    if chronology["testes"]:
        for item in output["coerencia_espacial"]["testes"]:
            print(
                item["trecho"],
                "| observado=",
                item["atraso_observado_h"],
                "h | faixa=",
                item["faixa_aceitavel_h"],
                "| coerente=",
                item["coerente"],
            )
    else:
        print("Sem pares suficientes para avaliar.")

    print()
    print(
        "Cucui contexto:",
        output["cucui_contexto"],
    )
    print()
    print(
        "Arquivos:",
        OUTPUT_JSON,
        DETAIL_CSV,
    )
    print()
    print(
        "Teste somente. Nenhum arquivo do painel foi alterado."
    )


if __name__ == "__main__":
    main()
