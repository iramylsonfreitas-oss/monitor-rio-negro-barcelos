const PARTIAL_DAY_URL =
  "data/barcelos_anual.json";

let partialDayLatestPoint =
  null;

let partialDayLatestYear =
  null;


function partialDayManausToday() {
  const parts =
    new Intl.DateTimeFormat(
      "en-CA",
      {
        timeZone:
          "America/Manaus",

        year:
          "numeric",

        month:
          "2-digit",

        day:
          "2-digit"
      }
    ).formatToParts(
      new Date()
    );

  const map =
    Object.fromEntries(
      parts.map(
        part => [
          part.type,
          part.value
        ]
      )
    );

  return (
    `${map.year}-` +
    `${map.month}-` +
    `${map.day}`
  );
}


function partialDayIsCurrent() {
  return Boolean(
    partialDayLatestPoint?.data &&
    partialDayLatestPoint.data ===
      partialDayManausToday()
  );
}


function partialDayApplyLabels() {
  if (
    !partialDayLatestPoint ||
    !partialDayLatestYear
  ) {
    return;
  }

  const isPartial =
    partialDayIsCurrent();

  const currentCard =
    document.querySelector(
      ".same-day-card.current"
    );

  const currentDetail =
    currentCard?.querySelector(
      ".same-day-difference.reference"
    );

  if (currentDetail) {
    const text =
      isPartial
        ? (
            "ano de referência • parcial"
          )
        : (
            "ano de referência"
          );

    if (
      currentDetail.textContent.trim() !==
      text
    ) {
      currentDetail.textContent =
        text;
    }
  }


  const reference =
    document.getElementById(
      "same-day-reference"
    );

  if (reference) {
    const text =
      isPartial
        ? (
            `Mediana diária • ` +
            `${partialDayLatestYear} • parcial`
          )
        : (
            `Mediana diária • ` +
            `${partialDayLatestYear}`
          );

    if (
      reference.textContent.trim() !==
      text
    ) {
      reference.textContent =
        text;
    }
  }


  const summary =
    document.getElementById(
      "same-day-summary"
    );

  if (
    summary &&
    isPartial
  ) {
    const note =
      " Mediana de hoje ainda parcial.";

    if (
      !summary.textContent.includes(
        "Mediana de hoje ainda parcial."
      )
    ) {
      summary.textContent =
        summary.textContent.trim() +
        note;
    }
  }
}


async function partialDayLoadData() {
  try {
    const response =
      await fetch(
        (
          `${PARTIAL_DAY_URL}` +
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

    const years =
      (
        data.anos ||
        Object.keys(
          data.series ||
          {}
        )
      )
        .map(String)
        .sort();

    partialDayLatestYear =
      years[
        years.length - 1
      ];

    const series =
      data.series?.[
        partialDayLatestYear
      ] || [];

    partialDayLatestPoint =
      series.length
        ? series[
            series.length - 1
          ]
        : null;

    partialDayApplyLabels();

  } catch (error) {
    console.error(
      "Erro ao identificar dia parcial:",
      error
    );
  }
}


function partialDayObserve() {
  const target =
    document.querySelector(
      ".annual-chart-card"
    );

  if (!target) {
    return;
  }

  const observer =
    new MutationObserver(
      () => {
        partialDayApplyLabels();
      }
    );

  observer.observe(
    target,
    {
      childList:
        true,

      subtree:
        true,

      characterData:
        true
    }
  );
}


document.addEventListener(
  "DOMContentLoaded",
  async () => {
    await partialDayLoadData();

    partialDayObserve();

    setInterval(
      partialDayLoadData,
      5 * 60 * 1000
    );
  }
);
