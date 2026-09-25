(() => {
  "use strict";

  const DATA_URL = "data/estacoes.json";
  const REFRESH_MS = 5 * 60 * 1000;

  const VIEW_W = 1180;
  const VIEW_H = 250;
  const BASELINE_Y = 128;

  const STATION_ORDER = [
    "14110000",
    "14280001",
    "14330000",
    "14420000",
    "14480002"
  ];

  const STATION_LABELS = {
    "14110000": "Cucuí",
    "14280001": "Taracuá",
    "14330000": "Curicuriari",
    "14420000": "Serrinha",
    "14480002": "Barcelos"
  };

  const X_POSITIONS = [
    90,
    340,
    590,
    840,
    1090
  ];


  // ========================================================
  // ESTILOS
  // ========================================================

  function installStyles() {
    if (
      document.getElementById(
        "river-pulse-styles"
      )
    ) {
      return;
    }

    const style =
      document.createElement("style");

    style.id =
      "river-pulse-styles";

    style.textContent = `
      .river-pulse-section {
        margin-top: 24px;
        padding: 28px;
        border-radius: 24px;
        position: relative;
        overflow: hidden;

        background:
          radial-gradient(
            circle at 50% 55%,
            rgba(18,126,171,0.16),
            transparent 42%
          ),
          linear-gradient(
            145deg,
            rgba(7,28,48,0.99),
            rgba(7,46,73,0.97)
          );

        border:
          1px solid
          rgba(93,191,232,0.18);

        box-shadow:
          0 18px 45px
          rgba(0,0,0,0.18);
      }


      .river-pulse-section::after {
        content: "";
        position: absolute;
        inset: auto 0 0 0;
        height: 46%;
        pointer-events: none;

        background:
          linear-gradient(
            to bottom,
            transparent,
            rgba(20,102,142,0.07)
          ),
          repeating-linear-gradient(
            to bottom,
            rgba(83,177,214,0.035) 0,
            rgba(83,177,214,0.035) 1px,
            transparent 1px,
            transparent 7px
          );
      }


      .river-pulse-header,
      .river-pulse-corridor,
      .river-pulse-insight,
      .river-pulse-note {
        position: relative;
        z-index: 1;
      }


      .river-pulse-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 24px;
      }


      .river-pulse-kicker {
        margin-bottom: 7px;

        color:
          rgba(255,255,255,0.56);

        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.16em;
      }


      .river-pulse-title {
        margin: 0;

        color: #ffffff;

        font-size: 26px;
        line-height: 1.15;
        letter-spacing: -0.025em;
      }


      .river-pulse-subtitle {
        max-width: 720px;
        margin-top: 8px;

        color:
          rgba(255,255,255,0.64);

        font-size: 13px;
        line-height: 1.5;
      }


      .river-pulse-legend {
        display: flex;
        flex: 0 0 auto;
        gap: 14px;

        padding: 10px 12px;

        border-radius: 16px;

        background:
          rgba(255,255,255,0.035);

        border:
          1px solid
          rgba(255,255,255,0.06);
      }


      .river-pulse-legend-item {
        display: flex;
        align-items: center;
        gap: 7px;

        color:
          rgba(255,255,255,0.63);

        font-size: 9px;
        white-space: nowrap;
      }


      .river-pulse-legend-dot {
        width: 9px;
        height: 9px;

        border-radius: 50%;

        box-shadow:
          0 0 12px currentColor;
      }


      .river-pulse-legend-dot.up {
        background: #48d99b;
        color: #48d99b;
      }


      .river-pulse-legend-dot.down {
        background: #ff7078;
        color: #ff7078;
      }


      .river-pulse-legend-dot.stable {
        background: #e7c16c;
        color: #e7c16c;
      }


      .river-pulse-scroll-hint {
        display: none;

        margin-top: 14px;

        color:
          rgba(255,255,255,0.42);

        font-size: 9px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }


      .river-pulse-corridor {
        margin-top: 18px;

        overflow-x: auto;

        scrollbar-width: thin;

        scrollbar-color:
          rgba(87,181,220,0.35)
          transparent;
      }


      .river-pulse-canvas {
        min-width: 760px;

        padding:
          0 8px;

        box-sizing:
          border-box;
      }


      .river-pulse-stations,
      .river-pulse-short-grid {
        display: grid;

        grid-template-columns:
          repeat(
            5,
            minmax(0, 1fr)
          );

        gap: 10px;
      }


      .river-pulse-station {
        min-width: 0;

        text-align: center;
      }


      .river-pulse-station-name {
        color: #ffffff;

        font-size: 13px;
        font-weight: 800;

        white-space: nowrap;
      }


      .river-pulse-station-code {
        margin-top: 3px;

        color:
          rgba(255,255,255,0.38);

        font-size: 9px;
        font-weight: 600;
      }


      .river-pulse-station-value {
        margin-top: 7px;

        font-size: 22px;
        font-weight: 850;
        line-height: 1;

        letter-spacing: -0.025em;

        white-space: nowrap;

        font-variant-numeric:
          tabular-nums;
      }


      .river-pulse-station-value.up {
        color: #4be0a1;
      }


      .river-pulse-station-value.down {
        color: #ff757d;
      }


      .river-pulse-station-value.stable {
        color: #e7c16c;
      }


      .river-pulse-station-value.unknown {
        color:
          rgba(255,255,255,0.5);
      }


      .river-pulse-station-label {
        margin-top: 4px;

        color:
          rgba(255,255,255,0.47);

        font-size: 9px;
        font-weight: 700;

        text-transform: uppercase;
        letter-spacing: 0.07em;
      }


      .river-pulse-destination {
        display: inline-flex;

        margin-left: 5px;

        padding: 3px 6px;

        border-radius: 999px;

        transform:
          translateY(-1px);

        background:
          rgba(74,164,214,0.18);

        border:
          1px solid
          rgba(91,183,231,0.25);

        color:
          rgba(196,232,249,0.9);

        font-size: 7px;
        font-weight: 800;
        letter-spacing: 0.09em;
      }


      .river-pulse-svg-wrap {
        height: 210px;

        margin-top: -4px;
        margin-bottom: -10px;
      }


      .river-pulse-svg {
        width: 100%;
        height: 100%;

        display: block;

        overflow: visible;
      }


      .river-pulse-baseline {
        stroke:
          rgba(255,255,255,0.25);

        stroke-width: 1.2;

        stroke-dasharray:
          7 7;
      }


      .river-pulse-baseline-label {
        fill:
          rgba(255,255,255,0.34);

        font-size: 11px;

        font-family:
          Inter,
          system-ui,
          sans-serif;

        font-weight: 600;

        letter-spacing: 0.04em;
      }


      .river-pulse-guide {
        stroke:
          rgba(158,214,236,0.30);

        stroke-width: 1;

        stroke-dasharray:
          6 6;
      }


      .river-pulse-area {
        opacity: 0.13;
      }


      .river-pulse-path {
        fill: none;

        stroke-width: 5;

        stroke-linecap: round;
        stroke-linejoin: round;

        filter:
          url(#riverPulseGlow);
      }


      .river-pulse-flow-path {
        fill: none;

        stroke:
          rgba(233,248,255,0.72);

        stroke-width: 2.2;

        stroke-linecap: round;

        stroke-dasharray:
          24 1150;

        animation:
          riverPulseTravel
          9s linear infinite;

        pointer-events: none;
      }


      @keyframes riverPulseTravel {
        from {
          stroke-dashoffset: 0;
        }

        to {
          stroke-dashoffset: -1170;
        }
      }


      .river-pulse-marker-ring {
        fill:
          rgba(7,34,54,0.96);

        stroke-width: 3;
      }


      .river-pulse-marker-core {
        stroke:
          rgba(255,255,255,0.2);

        stroke-width: 1;
      }


      .river-pulse-short-grid {
        margin-top: 2px;
      }


      .river-pulse-short-card {
        justify-self: center;

        min-width: 106px;

        padding: 9px 11px;

        border-radius: 12px;

        text-align: left;

        background:
          rgba(255,255,255,0.05);

        border:
          1px solid
          rgba(255,255,255,0.055);

        color:
          rgba(255,255,255,0.64);

        font-size: 9px;
        line-height: 1.7;

        font-variant-numeric:
          tabular-nums;
      }


      .river-pulse-short-card strong {
        color:
          rgba(255,255,255,0.82);
      }


      .river-pulse-mini-value.up {
        color: #4be0a1;
        font-weight: 800;
      }


      .river-pulse-mini-value.down {
        color: #ff757d;
        font-weight: 800;
      }


      .river-pulse-mini-value.stable {
        color: #e7c16c;
        font-weight: 800;
      }


      .river-pulse-direction {
        margin:
          20px auto 0;

        display: flex;

        align-items: center;
        justify-content: center;

        gap: 10px;

        color:
          rgba(255,255,255,0.43);

        font-size: 9px;
        font-weight: 800;
        letter-spacing: 0.14em;
      }


      .river-pulse-direction-line {
        width: 190px;
        height: 1px;

        position: relative;

        background:
          rgba(73,184,227,0.48);
      }


      .river-pulse-direction-line::after {
        content: "";

        position: absolute;

        right: -1px;
        top: -4px;

        width: 7px;
        height: 7px;

        border-top:
          1px solid
          rgba(101,207,246,0.8);

        border-right:
          1px solid
          rgba(101,207,246,0.8);

        transform:
          rotate(45deg);
      }


      .river-pulse-insight {
        margin-top: 18px;

        display: grid;

        grid-template-columns:
          1fr auto;

        align-items: center;

        gap: 22px;

        padding: 16px 18px;

        border-radius: 17px;

        background:
          rgba(255,255,255,0.045);

        border:
          1px solid
          rgba(82,177,218,0.14);
      }


      .river-pulse-insight-title {
        color: #ffffff;

        font-size: 14px;
        font-weight: 800;
      }


      .river-pulse-insight-text {
        margin-top: 5px;

        color:
          rgba(255,255,255,0.62);

        font-size: 11px;
        line-height: 1.45;
      }


      .river-pulse-insight-text strong {
        color: #ffffff;
      }


      .river-pulse-note {
        max-width: 330px;

        padding-left: 18px;

        border-left:
          1px solid
          rgba(255,255,255,0.1);

        color:
          rgba(255,255,255,0.44);

        font-size: 9px;
        line-height: 1.45;
      }


      .river-pulse-note strong {
        color:
          rgba(255,255,255,0.62);
      }


      .river-pulse-loading {
        padding:
          52px 10px;

        text-align: center;

        color:
          rgba(255,255,255,0.5);

        font-size: 13px;
      }


      @media (max-width: 760px) {

        .river-pulse-section {
          padding:
            22px 16px;

          border-radius: 20px;
        }


        .river-pulse-header {
          display: block;
        }


        .river-pulse-title {
          font-size: 21px;
        }


        .river-pulse-legend {
          margin-top: 14px;

          width: fit-content;

          max-width: 100%;

          flex-wrap: wrap;
        }


        .river-pulse-scroll-hint {
          display: block;
        }


        .river-pulse-corridor {
          margin-top: 10px;
        }


        .river-pulse-canvas {
          min-width: 740px;

          padding:
            0 12px;
        }


        .river-pulse-svg-wrap {
          height: 190px;

          margin-top: -3px;
          margin-bottom: -8px;
        }


        .river-pulse-insight {
          grid-template-columns:
            1fr;

          gap: 12px;
        }


        .river-pulse-note {
          max-width: none;

          padding:
            12px 0 0;

          border-left: 0;

          border-top:
            1px solid
            rgba(255,255,255,0.08);
        }
      }


      @media
      (prefers-reduced-motion: reduce) {

        .river-pulse-flow-path {
          animation: none;
        }
      }
    `;

    document.head.appendChild(
      style
    );
  }


  // ========================================================
  // DADOS
  // ========================================================

  function number(value) {
    const parsed =
      Number(value);

    return Number.isFinite(
      parsed
    )
      ? parsed
      : null;
  }


  function formatSigned(
    value,
    decimals = 0
  ) {
    const n =
      number(value);

    if (
      n === null
    ) {
      return "—";
    }

    const absolute =
      Math.abs(n)
        .toFixed(
          decimals
        );

    if (
      n > 0
    ) {
      return `+${absolute} cm`;
    }

    if (
      n < 0
    ) {
      return `−${absolute} cm`;
    }

    return `${absolute} cm`;
  }


  function stateFor(value) {
    const n =
      number(value);

    if (
      n === null
    ) {
      return "unknown";
    }

    if (
      n >= 2
    ) {
      return "up";
    }

    if (
      n <= -2
    ) {
      return "down";
    }

    return "stable";
  }


  function stateColor(state) {
    if (
      state === "up"
    ) {
      return "#48d99b";
    }

    if (
      state === "down"
    ) {
      return "#ff7078";
    }

    if (
      state === "stable"
    ) {
      return "#e7c16c";
    }

    return "#8797a5";
  }


  function stationMap(data) {
    const map = {};

    for (
      const station
      of data.estacoes || []
    ) {
      map[
        String(
          station.estacao
        )
      ] = station;
    }

    return map;
  }


  // ========================================================
  // CURVA
  // ========================================================

  function amplitudeFor(value) {
    const n =
      number(value);

    if (
      n === null ||
      Math.abs(n) < 2
    ) {
      return 0;
    }

    return Math.min(
      74,
      16 +
      Math.sqrt(
        Math.abs(n)
      ) *
      12.5
    );
  }


  function makePoints(stations) {
    return STATION_ORDER.map(
      (code, index) => {

        const station =
          stations[code];

        const value =
          station
            ? number(
                station
                  .variacao_72h_cm
              )
            : null;

        const state =
          stateFor(
            value
          );

        const amplitude =
          amplitudeFor(
            value
          );

        let y =
          BASELINE_Y;

        if (
          state === "up"
        ) {
          y -= amplitude;
        }

        if (
          state === "down"
        ) {
          y += amplitude;
        }

        return {
          code,

          x:
            X_POSITIONS[index],

          y,

          value,

          state,

          color:
            stateColor(
              state
            )
        };
      }
    );
  }


  function smoothPath(points) {
    if (
      !points.length
    ) {
      return "";
    }

    if (
      points.length === 1
    ) {
      return (
        `M ${points[0].x} ` +
        `${points[0].y}`
      );
    }

    let path =
      `M ${points[0].x} ` +
      `${points[0].y}`;

    for (
      let i = 0;
      i <
      points.length - 1;
      i += 1
    ) {
      const p0 =
        points[
          Math.max(
            0,
            i - 1
          )
        ];

      const p1 =
        points[i];

      const p2 =
        points[
          i + 1
        ];

      const p3 =
        points[
          Math.min(
            points.length - 1,
            i + 2
          )
        ];

      const cp1x =
        p1.x +
        (
          p2.x -
          p0.x
        ) /
        6;

      const cp1y =
        p1.y +
        (
          p2.y -
          p0.y
        ) /
        6;

      const cp2x =
        p2.x -
        (
          p3.x -
          p1.x
        ) /
        6;

      const cp2y =
        p2.y -
        (
          p3.y -
          p1.y
        ) /
        6;

      path +=
        ` C ${cp1x} ${cp1y}, ` +
        `${cp2x} ${cp2y}, ` +
        `${p2.x} ${p2.y}`;
    }

    return path;
  }


  // ========================================================
  // ESTAÇÕES
  // ========================================================

  function stationHeaderHTML(
    code,
    station
  ) {
    const name =
      station?.nome ||
      STATION_LABELS[code];

    const value =
      station
        ? station
            .variacao_72h_cm
        : null;

    const state =
      stateFor(
        value
      );

    const destination =
      code ===
      "14480002"
        ? `
          <span
            class="river-pulse-destination"
          >
            DESTINO
          </span>
        `
        : "";

    return `
      <div
        class="river-pulse-station"
      >

        <div
          class="river-pulse-station-name"
        >
          ${name}
          ${destination}
        </div>

        <div
          class="river-pulse-station-code"
        >
          ANA ${code}
        </div>

        <div
          class="
            river-pulse-station-value
            ${state}
          "
        >
          ${formatSigned(value)}
        </div>

        <div
          class="river-pulse-station-label"
        >
          em 72 h
        </div>

      </div>
    `;
  }


  function miniClass(value) {
    const n =
      number(value);

    if (
      n === null ||
      n === 0
    ) {
      return "stable";
    }

    return n > 0
      ? "up"
      : "down";
  }


  function shortCardHTML(station) {
    if (
      !station
    ) {
      return `
        <div
          class="river-pulse-short-card"
        >
          <strong>6 h:</strong>
          —
          <br>
          <strong>24 h:</strong>
          —
        </div>
      `;
    }

    return `
      <div
        class="river-pulse-short-card"
      >

        <strong>
          6 h:
        </strong>

        <span
          class="
            river-pulse-mini-value
            ${miniClass(
              station
                .variacao_6h_cm
            )}
          "
        >
          ${formatSigned(
            station
              .variacao_6h_cm
          )}
        </span>

        <br>

        <strong>
          24 h:
        </strong>

        <span
          class="
            river-pulse-mini-value
            ${miniClass(
              station
                .variacao_24h_cm
            )}
          "
        >
          ${formatSigned(
            station
              .variacao_24h_cm
          )}
        </span>

      </div>
    `;
  }


  // ========================================================
  // INTERPRETAÇÃO
  // ========================================================

  function buildInsight(stations) {
    const positive = [];

    for (
      const code
      of STATION_ORDER
    ) {
      const station =
        stations[code];

      if (
       
