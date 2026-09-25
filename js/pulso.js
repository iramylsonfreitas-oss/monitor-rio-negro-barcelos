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
      document.createElement(
        "style"
      );

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
        color: rgba(255,255,255,0.56);
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
        color: rgba(255,255,255,0.64);
        font-size: 13px;
        line-height: 1.5;
      }


      .river-pulse-legend {
        display: flex;
        flex: 0 0 auto;
        gap: 14px;
        padding: 10px 12px;
        border-radius: 16px;
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.06);
      }


      .river-pulse-legend-item {
        display: flex;
        align-items: center;
        gap: 7px;
        color: rgba(255,255,255,0.63);
        font-size: 9px;
        white-space: nowrap;
      }


      .river-pulse-legend-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        box-shadow: 0 0 12px currentColor;
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
        color: rgba(255,255,255,0.42);
        font-size: 9px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }


      .river-pulse-corridor {
        margin-top: 26px;
        overflow-x: auto;
        scrollbar-width: thin;
        scrollbar-color:
          rgba(87,181,220,0.35)
          transparent;
      }


      .river-pulse-canvas {
        min-width: 760px;
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
        text-align: center;
        min-width: 0;
      }


      .river-pulse-station-name {
        color: #ffffff;
        font-size: 13px;
        font-weight: 800;
      }


      .river-pulse-station-code {
        margin-top: 3px;
        color: rgba(255,255,255,0.38);
        font-size: 9px;
        font-weight: 600;
      }


      .river-pulse-station-value {
        margin-top: 8px;
        font-size: 22px;
        font-weight: 850;
        line-height: 1;
        letter-spacing: -0.04em;
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
        color: rgba(255,255,255,0.5);
      }


      .river-pulse-station-label {
        margin-top: 5px;
        color: rgba(255,255,255,0.47);
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
        transform: translateY(-1px);

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
        margin-top: 4px;
        height: 210px;
      }


      .river-pulse-svg {
        width: 100%;
        height: 100%;
        display: block;
        overflow: visible;
      }


      .river-pulse-baseline {
        stroke: rgba(255,255,255,0.28);
        stroke-width: 1.2;
        stroke-dasharray: 7 7;
      }


      .river-pulse-guide {
        stroke: rgba(158,214,236,0.32);
        stroke-width: 1;
        stroke-dasharray: 6 6;
      }


      .river-pulse-area {
        opacity: 0.13;
      }


      .river-pulse-path {
        fill: none;
        stroke-width: 5;
        stroke-linecap: round;
        stroke-linejoin: round;
        filter: url(#riverPulseGlow);
      }


      .river-pulse-flow-path {
        fill: none;
        stroke: rgba(233,248,255,0.72);
        stroke-width: 2.2;
        stroke-linecap: round;
        stroke-dasharray: 24 1150;

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
        fill: rgba(7,34,54,0.96);
        stroke-width: 3;
      }


      .river-pulse-marker-core {
        stroke: rgba(255,255,255,0.2);
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
      }


      .river-pulse-short-card strong {
        color: rgba(255,255,255,0.82);
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
        margin: 22px auto 0;

        display: flex;
        align-items: center;
        justify-content: center;

        gap: 10px;

        color: rgba(255,255,255,0.43);

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
        margin-top: 20px;

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
        color: rgba(255,255,255,0.62);
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


      .river-pulse-loading {
        padding: 52px 10px;

        text-align: center;

        color:
          rgba(255,255,255,0.5);

        font-size: 13px;
      }


      @media (max-width: 760px) {

        .river-pulse-section {
          padding: 22px 16px;
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
          margin-top: 12px;
        }


        .river-pulse-canvas {
          min-width: 720px;
        }


        .river-pulse-svg-wrap {
          height: 190px;
        }


        .river-pulse-insight {
          grid-template-columns: 1fr;
          gap: 12px;
        }


        .river-pulse-note {
          max-width: none;

          padding: 12px 0 0;

          border-left: 0;

          border-top:
            1px solid
            rgba(255,255,255,0.08);
        }
      }


      @media (prefers-reduced-motion: reduce) {

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

    const text =
      n.toFixed(
        decimals
      );

    return n > 0
      ? `+${text} cm`
      : `${text} cm`;
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

    let d =
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

      d +=
        ` C ${cp1x} ${cp1y}, ` +
        `${cp2x} ${cp2y}, ` +
        `${p2.x} ${p2.y}`;
    }

    return d;
  }


  // ========================================================
  // CARTÕES
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
      <div class="river-pulse-station">

        <div class="river-pulse-station-name">
          ${name}
          ${destination}
        </div>

        <div class="river-pulse-station-code">
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

        <div class="river-pulse-station-label">
          em 72 h
        </div>

      </div>
    `;
  }


  function miniClass(value) {
    const n =
      number(value);

    if (
      n === null
    ) {
      return "stable";
    }

    if (
      n > 0
    ) {
      return "up";
    }

    if (
      n < 0
    ) {
      return "down";
    }

    return "stable";
  }


  function shortCardHTML(station) {
    if (
      !station
    ) {
      return `
        <div class="river-pulse-short-card">
          <strong>6 h:</strong>
          —
          <br>
          <strong>24 h:</strong>
          —
        </div>
      `;
    }

    return `
      <div class="river-pulse-short-card">

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
        !station
      ) {
        continue;
      }

      if (
        stateFor(
          station
            .variacao_72h_cm
        ) === "up"
      ) {
        positive.push(
          station.nome ||
          STATION_LABELS[code]
        );
      }
    }


    const barcelos =
      stations[
        "14480002"
      ];


    const b72 =
      barcelos
        ? number(
            barcelos
              .variacao_72h_cm
          )
        : null;


    const b6 =
      barcelos
        ? number(
            barcelos
              .variacao_6h_cm
          )
        : null;


    if (
      positive.length
    ) {
      const title =
        `Pulso positivo observado em ` +
        `${positive.join(" e ")}`;

      let text =
        `A alta acumulada em 72 h ` +
        `aparece nessas estações.`;

      if (
        b72 !== null &&
        b72 <= -2
      ) {
        text +=
          ` Barcelos ainda permanece ` +
          `negativo no mesmo período ` +
          `(${formatSigned(b72)}).`;

      } else if (
        b72 !== null &&
        b72 >= 2
      ) {
        text +=
          ` Barcelos também já apresenta ` +
          `alta em 72 h ` +
          `(${formatSigned(b72)}).`;
      }

      if (
        b6 !== null &&
        b6 > 0 &&
        (
          b72 === null ||
          b72 < 2
        )
      ) {
        text +=
          ` Nas últimas 6 h, porém, ` +
          `Barcelos mostra reação positiva ` +
          `de ${formatSigned(b6)}.`;
      }

      return {
        title,
        text
      };
    }


    return {
      title:
        "Nenhum pulso positivo relevante em 72 h",

      text:
        "A leitura atual não mostra estações " +
        "com alta acumulada de pelo menos 2 cm " +
        "nas últimas 72 horas."
    };
  }


  // ========================================================
  // SVG
  // ========================================================

  function svgHTML(points) {
    const path =
      smoothPath(
        points
      );


    const areaPath =
      `${path} ` +
      `L ${
        points[
          points.length - 1
        ].x
      } ${BASELINE_Y} ` +
      `L ${
        points[0].x
      } ${BASELINE_Y} Z`;


    const stops =
      points.map(
        (point) => {

          const offset =
            (
              point.x /
              VIEW_W
            ) *
            100;

          return `
            <stop
              offset="${offset.toFixed(1)}%"
              stop-color="${point.color}"
            />
          `;
        }
      ).join("");


    const guides =
      points.map(
        (point) => `
          <line
            class="river-pulse-guide"
            x1="${point.x}"
            y1="${
              Math.min(
                point.y,
                BASELINE_Y
              )
            }"
            x2="${point.x}"
            y2="220"
          />
        `
      ).join("");


    const markers =
      points.map(
        (point) => `
          <g>

            <circle
              class="river-pulse-marker-ring"
              cx="${point.x}"
              cy="${point.y}"
              r="15"
              stroke="${point.color}"
            />

            <circle
              class="river-pulse-marker-core"
              cx="${point.x}"
              cy="${point.y}"
              r="8"
              fill="${point.color}"
            />

          </g>
        `
      ).join("");


    return `
      <svg
        class="river-pulse-svg"
        viewBox="0 0 ${VIEW_W} ${VIEW_H}"
        role="img"
        aria-label="Pulso do Rio Negro baseado na variação acumulada de 72 horas"
      >

        <defs>

          <linearGradient
            id="riverPulseLineGradient"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%"
          >
            ${stops}
          </linearGradient>


          <linearGradient
            id="riverPulseAreaGradient"
            x1="0%"
            y1="0%"
            x2="0%"
            y2="100%"
          >

            <stop
              offset="0%"
              stop-color="#5ce6ae"
              stop-opacity="0.75"
            />

            <stop
              offset="55%"
              stop-color="#35a8dc"
              stop-opacity="0.25"
            />

            <stop
              offset="100%"
              stop-color="#ff7078"
              stop-opacity="0.45"
            />

          </linearGradient>


          <filter
            id="riverPulseGlow"
            x="-20%"
            y="-40%"
            width="140%"
            height="180%"
          >

            <feGaussianBlur
              stdDeviation="4"
              result="blur"
            />

            <feMerge>

              <feMergeNode
                in="blur"
              />

              <feMergeNode
                in="SourceGraphic"
              />

            </feMerge>

          </filter>

        </defs>


        <line
          class="river-pulse-baseline"
          x1="28"
          y1="${BASELINE_Y}"
          x2="1152"
          y2="${BASELINE_Y}"
        />


        ${guides}


        <path
          class="river-pulse-area"
          d="${areaPath}"
          fill="url(#riverPulseAreaGradient)"
        />


        <path
          class="river-pulse-path"
          d="${path}"
          stroke="url(#riverPulseLineGradient)"
        />


        <path
          class="river-pulse-flow-path"
          d="${path}"
        />


        ${markers}

      </svg>
    `;
  }


  // ========================================================
  // ESTRUTURA
  // ========================================================

  function createSection() {
    let section =
      document.getElementById(
        "river-pulse-section"
      );

    if (
      section
    ) {
      return section;
    }


    section =
      document.createElement(
        "section"
      );


    section.id =
      "river-pulse-section";


    section.className =
      "river-pulse-section";


    section.innerHTML = `
      <div class="river-pulse-header">

        <div>

          <div class="river-pulse-kicker">
            PULSO DO RIO NEGRO
          </div>

          <h2 class="river-pulse-title">
            Comportamento ao longo
            do corredor
          </h2>

          <div class="river-pulse-subtitle">
            A curva representa a direção
            e a intensidade relativa da
            variação do nível nas últimas
            72 horas, de montante para
            jusante.
          </div>

        </div>


        <div class="river-pulse-legend">

          <div class="river-pulse-legend-item">

            <span
              class="
                river-pulse-legend-dot
                up
              "
            ></span>

            alta em 72 h

          </div>


          <div class="river-pulse-legend-item">

            <span
              class="
                river-pulse-legend-dot
                down
              "
            ></span>

            queda em 72 h

          </div>


          <div class="river-pulse-legend-item">

            <span
              class="
                river-pulse-legend-dot
                stable
              "
            ></span>

            estabilidade

          </div>

        </div>

      </div>


      <div class="river-pulse-scroll-hint">
        Deslize para acompanhar
        todo o corredor →
      </div>


      <div
        id="river-pulse-body"
        class="river-pulse-loading"
      >
        Carregando o pulso do rio...
      </div>


      <div
        id="river-pulse-insight"
        class="river-pulse-insight"
        style="display:none;"
      ></div>
    `;


    const radar =
      document.getElementById(
        "river-radar-section"
      );


    if (
      radar
    ) {
      radar.insertAdjacentElement(
        "beforebegin",
        section
      );

      return section;
    }


    const upstream =
      document.querySelector(
        ".upstream-section"
      );


    if (
      upstream
    ) {
      upstream.insertAdjacentElement(
        "afterend",
        section
      );

      return section;
    }


    const dashboard =
      document.querySelector(
        ".dashboard"
      );


    if (
      dashboard
    ) {
      dashboard.appendChild(
        section
      );
    }


    return section;
  }


  // ========================================================
  // RENDER
  // ========================================================

  function render(data) {
    const stations =
      stationMap(
        data
      );


    const points =
      makePoints(
        stations
      );


    const body =
      document.getElementById(
        "river-pulse-body"
      );


    const insightBox =
      document.getElementById(
        "river-pulse-insight"
      );


    if (
      !body ||
      !insightBox
    ) {
      return;
    }


    body.className =
      "river-pulse-corridor";


    body.innerHTML = `
      <div class="river-pulse-canvas">

        <div class="river-pulse-stations">

          ${
            STATION_ORDER.map(
              (code) =>
                stationHeaderHTML(
                  code,
                  stations[code]
                )
            ).join("")
          }

        </div>


        <div class="river-pulse-svg-wrap">
          ${svgHTML(points)}
        </div>


        <div class="river-pulse-short-grid">

          ${
            STATION_ORDER.map(
              (code) =>
                shortCardHTML(
                  stations[code]
                )
            ).join("")
          }

        </div>


        <div class="river-pulse-direction">

          <span>
            MONTANTE
          </span>

          <span
            class="
              river-pulse-direction-line
            "
          ></span>

          <span>
            JUSANTE
          </span>

        </div>

      </div>
    `;


    const insight =
      buildInsight(
        stations
      );


    insightBox.style.display =
      "grid";


    insightBox.innerHTML = `
      <div>

        <div class="river-pulse-insight-title">
          ${insight.title}
        </div>

        <div class="river-pulse-insight-text">
          ${insight.text}
        </div>

      </div>


      <div class="river-pulse-note">
        A curva mostra comportamento
        relativo entre estações nas
        últimas 72 h.

        Não representa cota absoluta,
        velocidade da água ou previsão
        de chegada da cheia.

        O brilho em movimento apenas
        indica o sentido
        montante → jusante.
      </div>
    `;
  }


  // ========================================================
  // CARREGAMENTO
  // ========================================================

  async function loadPulse() {
    try {
      const response =
        await fetch(
          `${DATA_URL}?t=${Date.now()}`,
          {
            cache: "no-store"
          }
        );


      if (
        !response.ok
      ) {
        throw new Error(
          `HTTP ${response.status}`
        );
      }


      const data =
        await response.json();


      render(
        data
      );

    } catch (
      error
    ) {
      const body =
        document.getElementById(
          "river-pulse-body"
        );


      if (
        body
      ) {
        body.className =
          "river-pulse-loading";

        body.textContent =
          "Não foi possível atualizar " +
          "o Pulso do Rio Negro agora.";
      }


      console.error(
        "Erro ao carregar Pulso do Rio Negro:",
        error
      );
    }
  }


  // ========================================================
  // INICIALIZAÇÃO
  // ========================================================

  function init() {
    installStyles();

    createSection();

    loadPulse();

    window.setInterval(
      loadPulse,
      REFRESH_MS
    );
  }


  if (
    document.readyState ===
    "loading"
  ) {
    document.addEventListener(
      "DOMContentLoaded",
      init
    );
  } else {
    init();
  }

})();
