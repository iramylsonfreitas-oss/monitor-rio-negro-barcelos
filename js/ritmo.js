const RITMO_URL =
  "data/repiquete.json";


/* =========================
   FORMATAÇÃO
========================= */

function ritmoFormatRate(
  value
) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  const n =
    Number(value);

  const abs =
    Math.abs(n)
      .toFixed(2)
      .replace(".", ",");

  if (n > 0) {
    return `+${abs} cm/h`;
  }

  if (n < 0) {
    return `-${abs} cm/h`;
  }

  return "0,00 cm/h";
}


function ritmoClass(
  value
) {
  const n =
    Number(value);

  if (
    !Number.isFinite(n) ||
    n === 0
  ) {
    return "neutral";
  }

  return (
    n > 0
      ? "positive"
      : "negative"
  );
}


/* =========================
   CÁLCULO
========================= */

function ritmoCalculate(
  data
) {
  const checkpoints =
    data
      ?.ultimos_checkpoints_barcelos ||
    [];

  if (
    checkpoints.length < 2
  ) {
    return null;
  }

  const current =
    checkpoints[
      checkpoints.length - 1
    ];

  const previous =
    checkpoints[
      checkpoints.length - 2
    ];

  const current6h =
    Number(
      current
        .variacao_6h_cm
    );

  const previous6h =
    Number(
      previous
        .variacao_6h_cm
    );

  if (
    !Number.isFinite(
      current6h
    ) ||
    !Number.isFinite(
      previous6h
    )
  ) {
    return null;
  }

  const currentRate =
    current6h / 6;

  const previousRate =
    previous6h / 6;

  const rateChange =
    currentRate -
    previousRate;

  return {
    currentRate,
    previousRate,
    rateChange,
    currentTime:
      current
        .hora_manaus,
    previousTime:
      previous
        .hora_manaus
  };
}


/* =========================
   INTERPRETAÇÃO
========================= */

function ritmoInterpret(
  result
) {
  if (!result) {
    return {
      label:
        "INDISPONÍVEL",

      detail:
        "Dados insuficientes"
    };
  }

  const current =
    result.currentRate;

  const previous =
    result.previousRate;

  const change =
    result.rateChange;

  if (
    current > 0 &&
    previous <= 0
  ) {
    return {
      label:
        "REVERSÃO RECENTE",

      detail:
        (
          "A taxa saiu de zero ou queda " +
          "para uma taxa positiva."
        )
    };
  }

  if (
    current > 0 &&
    change > 0
  ) {
    return {
      label:
        "ALTA GANHANDO FORÇA",

      detail:
        (
          "A taxa positiva aumentou " +
          "em relação ao bloco anterior."
        )
    };
  }

  if (
    current > 0 &&
    change < 0
  ) {
    return {
      label:
        "ALTA PERDENDO FORÇA",

      detail:
        (
          "O nível continua subindo, " +
          "mas em ritmo menor."
        )
    };
  }

  if (
    current === 0 &&
    previous < 0
  ) {
    return {
      label:
        "QUEDA INTERROMPIDA",

      detail:
        (
          "A taxa passou de negativa " +
          "para aproximadamente zero."
        )
    };
  }

  if (
    current === 0 &&
    previous > 0
  ) {
    return {
      label:
        "ALTA PAUSADA",

      detail:
        (
          "A taxa passou de positiva " +
          "para aproximadamente zero."
        )
    };
  }

  if (
    current < 0 &&
    change > 0
  ) {
    return {
      label:
        "QUEDA PERDENDO FORÇA",

      detail:
        (
          "A taxa ainda é negativa, " +
          "mas ficou menos negativa."
        )
    };
  }

  if (
    current < 0 &&
    change < 0
  ) {
    return {
      label:
        "QUEDA GANHANDO FORÇA",

      detail:
        (
          "A taxa negativa aumentou " +
          "em magnitude."
        )
    };
  }

  return {
    label:
      "RITMO ESTÁVEL",

    detail:
      (
        "A taxa mudou pouco entre " +
        "os dois últimos blocos."
      )
  };
}


/* =========================
   INSERIR CARDS
========================= */

function ritmoInsertCards() {
  const grid =
    document.querySelector(
      ".repiquete-context-grid"
    );

  if (!grid) {
    return false;
  }

  if (
    document.getElementById(
      "ritmo-current-rate"
    )
  ) {
    return true;
  }

  grid.insertAdjacentHTML(
    "beforeend",
    `
      <div class="repiquete-context-card">

        <div class="repiquete-context-label">
          TAXA DO ÚLTIMO BLOCO
        </div>

        <div
          id="ritmo-current-rate"
          class="repiquete-context-value"
        >
          —
        </div>

        <div
          id="ritmo-current-detail"
          class="repiquete-context-detail"
        >
          Média nas últimas 6 h do checkpoint
        </div>

      </div>


      <div class="repiquete-context-card">

        <div class="repiquete-context-label">
          MUDANÇA DA TAXA
        </div>

        <div
          id="ritmo-rate-change"
          class="repiquete-context-value"
        >
          —
        </div>

        <div
          id="ritmo-change-detail"
          class="repiquete-context-detail"
        >
          Comparação com o bloco anterior
        </div>

      </div>


      <div class="repiquete-context-card">

        <div class="repiquete-context-label">
          RITMO RECENTE
        </div>

        <div
          id="ritmo-status"
          class="repiquete-context-value"
        >
          —
        </div>

        <div
          id="ritmo-status-detail"
          class="repiquete-context-detail"
        >
          —
        </div>

      </div>
    `
  );

  return true;
}


/* =========================
   RENDER
========================= */

function ritmoRender(
  data
) {
  const result =
    ritmoCalculate(
      data
    );

  if (!result) {
    return;
  }

  const interpretation =
    ritmoInterpret(
      result
    );


  const current =
    document.getElementById(
      "ritmo-current-rate"
    );

  const change =
    document.getElementById(
      "ritmo-rate-change"
    );

  const status =
    document.getElementById(
      "ritmo-status"
    );

  const currentDetail =
    document.getElementById(
      "ritmo-current-detail"
    );

  const changeDetail =
    document.getElementById(
      "ritmo-change-detail"
    );

  const statusDetail =
    document.getElementById(
      "ritmo-status-detail"
    );


  if (current) {
    current.textContent =
      ritmoFormatRate(
        result.currentRate
      );

    current.classList.remove(
      "positive",
      "negative",
      "neutral"
    );

    current.classList.add(
      ritmoClass(
        result.currentRate
      )
    );
  }


  if (change) {
    change.textContent =
      ritmoFormatRate(
        result.rateChange
      );

    change.classList.remove(
      "positive",
      "negative",
      "neutral"
    );

    change.classList.add(
      ritmoClass(
        result.rateChange
      )
    );
  }


  if (status) {
    status.textContent =
      interpretation.label;
  }


  if (currentDetail) {
    currentDetail.textContent =
      (
        "Taxa média calculada a partir " +
        "da variação do bloco de 6 h."
      );
  }


  if (changeDetail) {
    changeDetail.textContent =
      (
        `Bloco anterior: ` +
        `${ritmoFormatRate(
          result.previousRate
        )}`
      );
  }


  if (statusDetail) {
    statusDetail.textContent =
      interpretation.detail;
  }
}


/* =========================
   CARREGAR
========================= */

async function ritmoLoad() {
  try {
    const response =
      await fetch(
        (
          `${RITMO_URL}` +
          `?v=${Date.now()}`
        ),
        {
          cache:
            "no-store"
        }
      );

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    const data =
      await response.json();

    const inserted =
      ritmoInsertCards();

    if (!inserted) {
      setTimeout(
        () => {
          ritmoInsertCards();
          ritmoRender(data);
        },
        250
      );

      return;
    }

    ritmoRender(
      data
    );

  } catch (error) {
    console.error(
      "Erro ao calcular ritmo do nível:",
      error
    );
  }
}


/* =========================
   INICIALIZAÇÃO
========================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {
    setTimeout(
      ritmoLoad,
      150
    );

    setInterval(
      ritmoLoad,
      5 * 60 * 1000
    );
  }
);
