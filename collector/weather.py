#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Coletor meteorológico do Monitor Rio Negro — Barcelos.

Fonte:
    Open-Meteo Forecast API
    https://open-meteo.com/en/docs

Objetivo:
    Consultar a previsão de 5 dias para Barcelos/AM e gravar
    um JSON compacto em data/weather.json para consumo pelo GitHub Pages.

Princípio de segurança:
    Se a API falhar ou retornar dados inválidos, o arquivo anterior
    NÃO é apagado nem sobrescrito.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


LATITUDE = -0.975339
LONGITUDE = -62.9245

TIMEZONE_NAME = "America/Manaus"
FORECAST_DAYS = 5

BASE_URL = "https://api.open-meteo.com/v1/forecast"
OUTPUT_PATH = Path("data/weather.json")

DAILY_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "wind_gusts_10m_max",
    "uv_index_max",
]


def weather_description(code: int | None) -> tuple[str, str]:
    mapping = {
        0: ("Céu limpo", "clear"),
        1: ("Predomínio de sol", "mostly_clear"),
        2: ("Parcialmente nublado", "partly_cloudy"),
        3: ("Nublado", "cloudy"),
        45: ("Neblina", "fog"),
        48: ("Neblina", "fog"),
        51: ("Garoa fraca", "drizzle"),
        53: ("Garoa", "drizzle"),
        55: ("Garoa forte", "drizzle"),
        56: ("Garoa congelante", "drizzle"),
        57: ("Garoa congelante", "drizzle"),
        61: ("Chuva fraca", "rain"),
        63: ("Chuva", "rain"),
        65: ("Chuva forte", "heavy_rain"),
        66: ("Chuva congelante", "rain"),
        67: ("Chuva congelante", "rain"),
        71: ("Neve fraca", "snow"),
        73: ("Neve", "snow"),
        75: ("Neve forte", "snow"),
        77: ("Grãos de neve", "snow"),
        80: ("Pancadas de chuva", "showers"),
        81: ("Pancadas de chuva", "showers"),
        82: ("Pancadas fortes", "heavy_showers"),
        85: ("Pancadas de neve", "snow"),
        86: ("Pancadas de neve", "snow"),
        95: ("Trovoadas", "storm"),
        96: ("Trovoadas com granizo", "storm"),
        99: ("Trovoadas fortes", "storm"),
    }
    return mapping.get(code, ("Condição variável", "unknown"))


def safe_round(value, digits=1):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def build_url() -> str:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE_NAME,
        "forecast_days": FORECAST_DAYS,
        "daily": ",".join(DAILY_FIELDS),
    }
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def fetch_forecast() -> dict:
    url = build_url()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Monitor-Rio-Negro-Barcelos/1.0 "
                "(GitHub Pages weather collector)"
            )
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Open-Meteo respondeu HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError("Resposta inválida: JSON principal não é um objeto.")

    return payload


def validate_daily(daily: dict) -> None:
    if not isinstance(daily, dict):
        raise RuntimeError("Resposta inválida: bloco 'daily' ausente.")

    times = daily.get("time")
    if not isinstance(times, list) or len(times) < FORECAST_DAYS:
        raise RuntimeError(
            f"Resposta inválida: esperados {FORECAST_DAYS} dias em daily.time."
        )

    for field in DAILY_FIELDS:
        values = daily.get(field)
        if not isinstance(values, list) or len(values) < FORECAST_DAYS:
            raise RuntimeError(
                f"Resposta inválida: campo diário '{field}' incompleto."
            )


def build_output(payload: dict) -> dict:
    daily = payload.get("daily")
    validate_daily(daily)

    days = []

    for i in range(FORECAST_DAYS):
        code = safe_int(daily["weather_code"][i])
        description, category = weather_description(code)

        day = {
            "date": daily["time"][i],
            "weather_code": code,
            "condition": description,
            "condition_category": category,
            "t_max_c": safe_round(daily["temperature_2m_max"][i], 1),
            "t_min_c": safe_round(daily["temperature_2m_min"][i], 1),
            "rain_probability_pct": safe_int(
                daily["precipitation_probability_max"][i]
            ),
            "rain_mm": safe_round(daily["precipitation_sum"][i], 1),
            "wind_max_kmh": safe_round(daily["wind_speed_10m_max"][i], 1),
            "wind_direction_deg": safe_int(
                daily["wind_direction_10m_dominant"][i]
            ),
            "gust_max_kmh": safe_round(daily["wind_gusts_10m_max"][i], 1),
            "uv_index_max": safe_round(daily["uv_index_max"][i], 1),
        }
        days.append(day)

    rain_total = round(
        sum(
            d["rain_mm"]
            for d in days
            if isinstance(d.get("rain_mm"), (int, float))
        ),
        1,
    )

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo(TIMEZONE_NAME))

    return {
        "schema_version": 1,
        "source": {
            "name": "Open-Meteo",
            "url": "https://open-meteo.com/",
            "license_note": "Dados meteorológicos via Open-Meteo.",
        },
        "location": {
            "name": "Barcelos",
            "state": "AM",
            "country": "Brasil",
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "timezone": TIMEZONE_NAME,
        },
        "generated_at_utc": now_utc.isoformat(timespec="seconds"),
        "generated_at_manaus": now_local.isoformat(timespec="seconds"),
        "forecast_days": FORECAST_DAYS,
        "rain_total_5d_mm": rain_total,
        "days": days,
    }


def atomic_write_json(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            temp_name = tmp.name
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")

        os.replace(temp_name, output_path)
        temp_name = None

    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    print("======================================")
    print("PREVISÃO METEOROLÓGICA — BARCELOS/AM")
    print("======================================")
    print("Fonte: Open-Meteo")
    print(f"Coordenadas: {LATITUDE}, {LONGITUDE}")
    print(f"Horizonte: {FORECAST_DAYS} dias")
    print()

    try:
        payload = fetch_forecast()
        output = build_output(payload)
        atomic_write_json(output, OUTPUT_PATH)

    except Exception as exc:
        print("ERRO ao atualizar previsão meteorológica:")
        print(str(exc))
        print()
        print(
            "O arquivo data/weather.json anterior foi preservado, "
            "caso já exista."
        )
        return 1

    print(f"Arquivo atualizado: {OUTPUT_PATH}")
    print("Chuva prevista em 5 dias:", output["rain_total_5d_mm"], "mm")
    print()

    for day in output["days"]:
        print(
            day["date"],
            "|",
            day["condition"],
            "|",
            f'{day["t_max_c"]}/{day["t_min_c"]} °C',
            "|",
            f'{day["rain_probability_pct"]}% chuva',
            "|",
            f'{day["rain_mm"]} mm',
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
