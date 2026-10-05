import csv
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import ana
import alerta
import repiquete
import convergencia_espacial_v4

DATA_DIR = Path('data')
HISTORY_FILE = DATA_DIR / 'history' / 'hourly.csv'
REALTIME_FILES = [
    DATA_DIR / 'latest.json',
    DATA_DIR / 'series_30d.json',
    DATA_DIR / 'estacoes.json',
    HISTORY_FILE,
]
STATUS_COLETA_FILE = DATA_DIR / 'status_coleta.json'
QUALIDADE_FILE = DATA_DIR / 'qualidade_dados.json'
V4_SHADOW_FILE = DATA_DIR / 'convergencia_v4_sombra.json'
V4_SHADOW_DETAILS_FILE = DATA_DIR / 'convergencia_v4_detalhes_sombra.json'
V4_HISTORY_FILE = DATA_DIR / 'history' / 'alertas_v4.csv'
V4_ARTIFACT = Path('artifacts') / 'convergencia_v4.json'
V4_DETAILS_ARTIFACT = Path('artifacts') / 'convergencia_v4_detalhes.json'
MANAUS_TZ = ZoneInfo('America/Manaus')
MAX_TENTATIVAS = 3
ESPERAS_SEGUNDOS = [20, 40]
EXPECTED_STATIONS = {
    '14110000': 'Cucuí',
    '14280001': 'Taracuá',
    '14330000': 'Curicuriari',
    '14420000': 'Serrinha',
    '14480002': 'Barcelos',
    '14840000': 'Moura',
    '14990000': 'Manaus',
}
CORE_V4 = {
    '14280001': 'Taracuá',
    '14330000': 'Curicuriari',
    '14420000': 'Serrinha',
    '14480002': 'Barcelos',
}
MAX_CORE_AGE_MIN = 180
HEARTBEAT_HISTORY_H = 6
SCORE_CHANGE_MIN = 0.05


def now_utc():
    return datetime.now(timezone.utc)


def fmt_utc(dt=None):
    return (dt or now_utc()).isoformat()


def load_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_manaus(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace('T', ' '))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MANAUS_TZ)
    return dt.astimezone(MANAUS_TZ)


def current_age_minutes(station):
    dt = parse_manaus(station.get('data_medicao_manaus'))
    if dt is None:
        return None
    age = int((now_utc() - dt.astimezone(timezone.utc)).total_seconds() / 60)
    return max(age, 0)


def snapshot_files(temp_dir):
    snapshot = {}
    for path in REALTIME_FILES:
        if path.exists():
            dst = Path(temp_dir) / path.as_posix().replace('/', '__')
            shutil.copy2(path, dst)
            snapshot[path] = dst
        else:
            snapshot[path] = None
    return snapshot


def restore_snapshot(snapshot):
    for path, backup in snapshot.items():
        if backup is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, path)


def transient_error(error):
    text = str(error).lower()
    signals = [
        'http 401', 'unauthorized', 'http 429', 'http 502', 'http 503', 'http 504',
        'timed out', 'timeout', 'temporarily unavailable', 'service unavailable',
        'connection reset', 'remote end closed connection', 'connection refused',
        'network is unreachable', '[errno 101]', 'no route to host',
        'temporary failure in name resolution', 'name or service not known',
        'zero registros', 'resposta parcial', 'faltam estacoes', 'sem dados válidos',
    ]
    return any(signal in text for signal in signals)


def validate_collected_files():
    problems = []
    payload = load_json(DATA_DIR / 'estacoes.json')
    if not isinstance(payload, dict):
        return False, ['estacoes.json ausente ou inválido'], {}
    stations = payload.get('estacoes')
    if not isinstance(stations, list):
        return False, ['campo estacoes ausente'], {}
    by_code = {
        str(item.get('estacao')): item
        for item in stations
        if isinstance(item, dict) and item.get('estacao')
    }
    missing = sorted(set(EXPECTED_STATIONS) - set(by_code))
    if missing:
        problems.append('faltam estacoes: ' + ', '.join(f'{code} ({EXPECTED_STATIONS[code]})' for code in missing))
    if len(by_code) != len(EXPECTED_STATIONS):
        problems.append(f'resposta parcial: {len(by_code)}/7 estacoes válidas')
    for code, name in EXPECTED_STATIONS.items():
        item = by_code.get(code)
        if not item:
            continue
        if item.get('nivel_cm') is None:
            problems.append(f'{name}: nivel_cm ausente')
        if not item.get('data_medicao_manaus'):
            problems.append(f'{name}: data_medicao_manaus ausente')
    latest = load_json(DATA_DIR / 'latest.json')
    if not isinstance(latest, dict) or str(latest.get('estacao')) != '14480002':
        problems.append('latest.json não contém Barcelos válido')
    series = load_json(DATA_DIR / 'series_30d.json')
    if not isinstance(series, list) or len(series) < 24:
        problems.append('series_30d.json vazio ou insuficiente')
    return len(problems) == 0, problems, by_code


def last_success_from_previous_status():
    previous = load_json(STATUS_COLETA_FILE, {}) or {}
    return previous.get('ultima_coleta_bem_sucedida_utc')


def collect_resilient():
    last_success = last_success_from_previous_status()
    last_error = None
    with tempfile.TemporaryDirectory(prefix='v41_snapshot_') as temp_dir:
        baseline = snapshot_files(temp_dir)
        for attempt in range(1, MAX_TENTATIVAS + 1):
            restore_snapshot(baseline)
            print('\n' + '=' * 58)
            print(f'V4.1 - COLETA ANA | tentativa {attempt}/{MAX_TENTATIVAS}')
            print('=' * 58)
            try:
                if os.getenv('V41_SIMULAR_FALHA') == '1':
                    raise RuntimeError('network is unreachable [simulado]')
                ana.main()
                valid, problems, by_code = validate_collected_files()
                if not valid:
                    raise RuntimeError('Resposta parcial/invalidada pela V4.1: ' + ' | '.join(problems))
                success_time = fmt_utc()
                status = {
                    'versao': '4.1',
                    'gerado_em_utc': success_time,
                    'status': 'ATUALIZADO',
                    'fonte': 'ANA - HidroWebService',
                    'tentativa_utilizada': attempt,
                    'fallback_ultima_leitura_valida': False,
                    'estacoes_recebidas': len(by_code),
                    'estacoes_esperadas': len(EXPECTED_STATIONS),
                    'ultima_coleta_bem_sucedida_utc': success_time,
                    'erro': None,
                }
                write_json(STATUS_COLETA_FILE, status)
                return status
            except Exception as error:
                last_error = error
                restore_snapshot(baseline)
                is_transient = transient_error(error)
                print(f'Falha detectada: {str(error)[:800]}')
                print(f'Classificada como transitória: {is_transient}')
                if not is_transient:
                    status = {
                        'versao': '4.1',
                        'gerado_em_utc': fmt_utc(),
                        'status': 'ERRO_ESTRUTURAL',
                        'fonte': 'ANA - HidroWebService',
                        'tentativa_utilizada': attempt,
                        'fallback_ultima_leitura_valida': True,
                        'ultima_coleta_bem_sucedida_utc': last_success,
                        'erro': str(error)[:1200],
                    }
                    write_json(STATUS_COLETA_FILE, status)
                    raise
                if attempt < MAX_TENTATIVAS:
                    wait_s = ESPERAS_SEGUNDOS[attempt - 1]
                    print(f'Aguardando {wait_s}s antes de repetir autenticação + consulta...')
                    time.sleep(wait_s)
        restore_snapshot(baseline)
        status = {
            'versao': '4.1',
            'gerado_em_utc': fmt_utc(),
            'status': 'FONTE_INDISPONIVEL',
            'fonte': 'ANA - HidroWebService',
            'tentativa_utilizada': MAX_TENTATIVAS,
            'fallback_ultima_leitura_valida': True,
            'ultima_coleta_bem_sucedida_utc': last_success,
            'erro': str(last_error)[:1200] if last_error else 'falha transitória',
        }
        write_json(STATUS_COLETA_FILE, status)
        return status


def evaluate_quality(collection_status):
    payload = load_json(DATA_DIR / 'estacoes.json', {}) or {}
    stations = payload.get('estacoes') or []
    by_code = {
        str(item.get('estacao')): item
        for item in stations
        if isinstance(item, dict) and item.get('estacao')
    }
    core_rows = []
    problems = []
    max_age = None
    for code, name in CORE_V4.items():
        item = by_code.get(code)
        if not item:
            core_rows.append({'estacao': code, 'nome': name, 'presente': False, 'idade_min': None, 'ok': False})
            problems.append(f'{name}: ausente')
            continue
        age = current_age_minutes(item)
        ok = (
            item.get('nivel_cm') is not None
            and item.get('data_medicao_manaus')
            and age is not None
            and age <= MAX_CORE_AGE_MIN
        )
        if age is not None:
            max_age = age if max_age is None else max(max_age, age)
        if not ok:
            problems.append(f'{name}: dado inválido/desatualizado' + (f' ({age} min)' if age is not None else ''))
        core_rows.append({
            'estacao': code,
            'nome': name,
            'presente': True,
            'idade_min': age,
            'nivel_m': item.get('nivel_m'),
            'data_medicao_manaus': item.get('data_medicao_manaus'),
            'ok': bool(ok),
        })
    collection_state = collection_status.get('status')
    if collection_state == 'FONTE_INDISPONIVEL':
        status = 'FONTE_INDISPONIVEL'
    elif collection_state == 'ERRO_ESTRUTURAL':
        status = 'INVALIDO'
    elif problems:
        status = 'DESATUALIZADO'
    else:
        status = 'ATUAL'
    v4_authorized = status == 'ATUAL'
    quality = {
        'versao': '4.1',
        'gerado_em_utc': fmt_utc(),
        'status': status,
        'v4_autorizada': v4_authorized,
        'limite_idade_core_min': MAX_CORE_AGE_MIN,
        'maior_idade_core_min': max_age,
        'coleta': {
            'status': collection_state,
            'fallback_ultima_leitura_valida': collection_status.get('fallback_ultima_leitura_valida'),
            'ultima_coleta_bem_sucedida_utc': collection_status.get('ultima_coleta_bem_sucedida_utc'),
        },
        'core': core_rows,
        'problemas': problems,
    }
    write_json(QUALIDADE_FILE, quality)
    return quality


def preserve_previous_hydrologic_state():
    previous = load_json(V4_SHADOW_FILE, {}) or {}
    return previous.get('estado_hidrologico') or previous.get('estado') or previous.get('ultimo_estado_valido')


def run_v4_shadow(quality):
    if quality.get('v4_autorizada'):
        alerta.main()
        repiquete.main()
        convergencia_espacial_v4.main()
        raw = load_json(V4_ARTIFACT)
        details = load_json(V4_DETAILS_ARTIFACT)
        if not isinstance(raw, dict):
            raise RuntimeError('V4 não gerou artifacts/convergencia_v4.json')
        shadow = dict(raw)
        shadow['modelo'] = 'convergencia_espacial_v4_1_sombra'
        shadow['modo'] = 'sombra'
        shadow['publicado_no_painel'] = False
        shadow['estado_hidrologico'] = raw.get('estado')
        shadow['qualidade_dados'] = {
            'status': quality.get('status'),
            'v4_autorizada': True,
            'maior_idade_core_min': quality.get('maior_idade_core_min'),
        }
        write_json(V4_SHADOW_FILE, shadow)
        write_json(V4_SHADOW_DETAILS_FILE, {
            'modelo': 'convergencia_espacial_v4_1_sombra',
            'gerado_em_utc': fmt_utc(),
            'modo': 'sombra',
            'publicado_no_painel': False,
            'qualidade_dados': quality,
            'detalhes_v4': details,
        })
        return shadow
    preserved = preserve_previous_hydrologic_state()
    shadow = {
        'modelo': 'convergencia_espacial_v4_1_sombra',
        'gerado_em_utc': fmt_utc(),
        'modo': 'sombra',
        'publicado_no_painel': False,
        'estado': 'dados_indisponiveis',
        'estado_hidrologico': preserved,
        'ultimo_estado_valido': preserved,
        'mensagem': 'A V4 não recalculou o sinal porque a qualidade dos dados não autorizou nova inferência. A última leitura válida foi preservada.',
        'janela_previsao_barcelos': None,
        'qualidade_dados': {
            'status': quality.get('status'),
            'v4_autorizada': False,
            'maior_idade_core_min': quality.get('maior_idade_core_min'),
        },
    }
    write_json(V4_SHADOW_FILE, shadow)
    write_json(V4_SHADOW_DETAILS_FILE, {
        'modelo': 'convergencia_espacial_v4_1_sombra',
        'gerado_em_utc': fmt_utc(),
        'modo': 'sombra',
        'publicado_no_painel': False,
        'qualidade_dados': quality,
        'detalhes_v4': None,
    })
    return shadow


HISTORY_FIELDS = [
    'registrado_em_utc', 'registrado_em_manaus', 'estado', 'estado_hidrologico',
    'qualidade_dados', 'v4_autorizada', 'score', 'sobreposicao_h',
    'janela_inicio', 'janela_fim', 'core_ativas', 'cadeias_completas_validas',
    'pares_validos_diagnosticos', 'motivo_registro',
]


def extract_shadow_row(shadow, quality):
    chain = shadow.get('melhor_cadeia_completa') or {}
    consensus = chain.get('janela_consenso') or {}
    window = shadow.get('janela_previsao_barcelos') or {}
    now = now_utc()
    return {
        'registrado_em_utc': now.isoformat(),
        'registrado_em_manaus': now.astimezone(MANAUS_TZ).strftime('%Y-%m-%d %H:%M:%S'),
        'estado': shadow.get('estado'),
        'estado_hidrologico': shadow.get('estado_hidrologico'),
        'qualidade_dados': quality.get('status'),
        'v4_autorizada': str(bool(quality.get('v4_autorizada'))).lower(),
        'score': chain.get('score'),
        'sobreposicao_h': consensus.get('duracao_h') if consensus else None,
        'janela_inicio': window.get('inicio'),
        'janela_fim': window.get('fim'),
        'core_ativas': shadow.get('core_ativas'),
        'cadeias_completas_validas': shadow.get('cadeias_completas_validas'),
        'pares_validos_diagnosticos': shadow.get('pares_validos_diagnosticos'),
        'motivo_registro': '',
    }


def read_last_history_row():
    if not V4_HISTORY_FILE.exists():
        return None
    try:
        with V4_HISTORY_FILE.open('r', encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        return rows[-1] if rows else None
    except Exception:
        return None


def as_float(value):
    try:
        if value in (None, ''):
            return None
        return float(value)
    except Exception:
        return None


def should_append_history(current, previous):
    if previous is None:
        return True, 'primeiro_registro'
    if current['estado'] != previous.get('estado'):
        return True, 'mudanca_estado'
    if current['estado_hidrologico'] != previous.get('estado_hidrologico'):
        return True, 'mudanca_estado_hidrologico'
    if current['qualidade_dados'] != previous.get('qualidade_dados'):
        return True, 'mudanca_qualidade'
    if current['janela_inicio'] != previous.get('janela_inicio') or current['janela_fim'] != previous.get('janela_fim'):
        return True, 'mudanca_janela'
    current_score = as_float(current.get('score'))
    previous_score = as_float(previous.get('score'))
    if current_score is not None and previous_score is not None and abs(current_score - previous_score) >= SCORE_CHANGE_MIN:
        return True, 'mudanca_score'
    try:
        prev_dt = datetime.fromisoformat(previous.get('registrado_em_utc'))
        if prev_dt.tzinfo is None:
            prev_dt = prev_dt.replace(tzinfo=timezone.utc)
        if now_utc() - prev_dt >= timedelta(hours=HEARTBEAT_HISTORY_H):
            return True, 'heartbeat_6h'
    except Exception:
        return True, 'timestamp_anterior_invalido'
    return False, None


def update_shadow_history(shadow, quality):
    current = extract_shadow_row(shadow, quality)
    previous = read_last_history_row()
    append, reason = should_append_history(current, previous)
    if not append:
        print('Histórico V4.1: sem mudança relevante; nenhuma linha adicionada.')
        return False
    current['motivo_registro'] = reason
    V4_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    exists = V4_HISTORY_FILE.exists()
    with V4_HISTORY_FILE.open('a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not exists or V4_HISTORY_FILE.stat().st_size == 0:
            writer.writeheader()
        writer.writerow(current)
    print(f'Histórico V4.1: linha adicionada ({reason}).')
    return True


def main():
    print('\n' + '=' * 64)
    print('MONITOR RIO NEGRO - V4.1 OPERACIONAL EM SOMBRA')
    print('=' * 64)
    collection_status = collect_resilient()
    quality = evaluate_quality(collection_status)
    shadow = run_v4_shadow(quality)
    history_updated = update_shadow_history(shadow, quality)
    print('\n' + '=' * 64)
    print('RESUMO V4.1')
    print('=' * 64)
    print('Coleta:', collection_status.get('status'))
    print('Fallback:', collection_status.get('fallback_ultima_leitura_valida'))
    print('Qualidade:', quality.get('status'))
    print('V4 autorizada:', quality.get('v4_autorizada'))
    print('Estado sombra:', shadow.get('estado'))
    print('Estado hidrológico:', shadow.get('estado_hidrologico'))
    print('Histórico atualizado:', history_updated)
    print('Publicado no painel: NÃO')


if __name__ == '__main__':
    main()
