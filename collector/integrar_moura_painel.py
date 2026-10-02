from pathlib import Path


ANA_FILE = Path("collector/ana.py")
INDEX_FILE = Path("index.html")


def replace_once(path, old, new, label):
    text = path.read_text(encoding="utf-8")

    if new in text:
        print(f"OK: {label} ja aplicado.")
        return

    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"Nao foi possivel aplicar '{label}'. "
            f"Ocorrencias esperadas: 1; encontradas: {count}."
        )

    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"OK: {label}.")


def patch_ana():
    replace_once(
        ANA_FILE,
        '''    "14480002": "Barcelos",
    "14990000": "Manaus",''',
        '''    "14480002": "Barcelos",
    "14840000": "Moura",
    "14990000": "Manaus",''',
        "Moura adicionada a coleta principal",
    )

    replace_once(
        ANA_FILE,
        "# CONSULTA CONJUNTA DAS 6 ESTAÇÕES",
        "# CONSULTA CONJUNTA DAS 7 ESTAÇÕES",
        "comentario da quantidade de estacoes",
    )


def patch_index():
    replace_once(
        INDEX_FILE,
        "<title>Monitor Rio Negro | Barcelos — V3.7A.2</title>",
        "<title>Monitor Rio Negro | Barcelos — V3.7A.3</title>",
        "versao do painel",
    )

    replace_once(
        INDEX_FILE,
        "/* V3.7A.2 — acabamento visual do corredor completo até Manaus */",
        "/* V3.7A.3 — corredor completo com Moura entre Barcelos e Manaus */",
        "comentario de versao",
    )

    replace_once(
        INDEX_FILE,
        ".stations{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}",
        ".stations{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:10px}",
        "grade desktop com sete estacoes",
    )

    replace_once(
        INDEX_FILE,
        '''.station.downstream{border-color:rgba(245,196,81,.24);background:rgba(245,196,81,.025)}
.stationRole{''',
        '''.station.downstream{border-color:rgba(245,196,81,.24);background:rgba(245,196,81,.025)}
.station.validation{border-color:rgba(79,216,255,.28);background:rgba(79,216,255,.035)}
.stationRole{''',
        "estilo do cartao de validacao",
    )

    replace_once(
        INDEX_FILE,
        '''.station.current .stationRole{color:#bfefff;border-color:rgba(79,216,255,.25);background:rgba(79,216,255,.06)}
.station.downstream .stationRole{color:#f7d98a;border-color:rgba(245,196,81,.22);background:rgba(245,196,81,.05)}''',
        '''.station.current .stationRole{color:#bfefff;border-color:rgba(79,216,255,.25);background:rgba(79,216,255,.06)}
.station.validation .stationRole{color:#bfefff;border-color:rgba(79,216,255,.25);background:rgba(79,216,255,.06)}
.station.downstream .stationRole{color:#f7d98a;border-color:rgba(245,196,81,.22);background:rgba(245,196,81,.05)}''',
        "estilo do rotulo de validacao",
    )

    replace_once(
        INDEX_FILE,
        '''      <strong>Como comparar:</strong> cada estação usa uma referência local de nível. Para comparar o comportamento entre estações, observe principalmente as variações de 6 h, 24 h, 72 h e 7 dias. Manaus aparece como contexto a jusante de Barcelos e não entra no sinal de movimento a montante nem na confirmação de repiquete.''',
        '''      <strong>Como comparar:</strong> cada estação usa uma referência local de nível. Para comparar o comportamento entre estações, observe principalmente as variações de 6 h, 24 h, 72 h e 7 dias. Moura aparece como estação de validação a jusante de Barcelos; Manaus amplia o contexto do corredor. Nenhuma das duas entra no sinal de movimento a montante nem na confirmação de repiquete em Barcelos.''',
        "nota das estacoes monitoradas",
    )

    replace_once(
        INDEX_FILE,
        '''      A leitura segue por Curicuriari e Serrinha até Barcelos e continua até Manaus,
      usada aqui como referência a jusante.''',
        '''      A leitura segue por Curicuriari e Serrinha até Barcelos, continua por Moura
      e chega a Manaus. Moura funciona como validação a jusante; Manaus amplia o contexto do corredor.''',
        "introducao do corredor",
    )

    replace_once(
        INDEX_FILE,
        '''aria-label="Esquema topológico do corredor monitorado do Rio Negro, com Cucuí e Taracuá a montante, Barcelos como ponto central e Manaus a jusante"''',
        '''aria-label="Esquema topológico do corredor monitorado do Rio Negro, com Cucuí e Taracuá a montante, Barcelos como ponto central, Moura como validação a jusante e Manaus como referência a jusante"''',
        "acessibilidade do esquema do corredor",
    )

    replace_once(
        INDEX_FILE,
        '''      Esquema topológico das estações. Níveis usam referências locais e não representam cotas diretamente comparáveis entre estações. Manaus fornece contexto a jusante; sua variação não é tratada como causa ou sinal antecipado de Barcelos.''',
        '''      Esquema topológico das estações. Níveis usam referências locais e não representam cotas diretamente comparáveis entre estações. Moura é usada como validação a jusante de Barcelos; Manaus fornece contexto adicional. As variações a jusante não são tratadas como causa nem como sinal antecipado de Barcelos.''',
        "nota do esquema do corredor",
    )

    replace_once(
        INDEX_FILE,
        '''aria-label="Movimento relativo do Rio Negro entre as estações monitoradas, de Cucuí e Taracuá até Manaus, com Barcelos antes da referência a jusante"''',
        '''aria-label="Movimento relativo do Rio Negro entre as estações monitoradas, de Cucuí e Taracuá até Manaus, passando por Barcelos e Moura a jusante"''',
        "acessibilidade do grafico de ondas",
    )

    replace_once(
        INDEX_FILE,
        '''      Leitura relativa das variações de nível nas últimas 72 h.
      Manaus é uma referência a jusante e não entra no detector de movimento a montante.
      A curva não representa cota absoluta, velocidade da água nem previsão de chegada.''',
        '''      Leitura relativa das variações de nível nas últimas 72 h.
      Moura é uma estação de validação a jusante de Barcelos e Manaus é uma referência adicional do corredor; nenhuma entra no detector de movimento a montante.
      A curva não representa cota absoluta, velocidade da água nem previsão de chegada.''',
        "nota do grafico de ondas",
    )

    replace_once(
        INDEX_FILE,
        '''      const isBarcelos=code==="14480002";
      const isManaus=code==="14990000";
      const role=isBarcelos?"BARCELOS":isManaus?"JUSANTE":upstreamCodes.has(code)?"MONTANTE":"CORREDOR";
      const extraClass=isBarcelos?"current":isManaus?"downstream":"";''',
        '''      const isBarcelos=code==="14480002";
      const isMoura=code==="14840000";
      const isManaus=code==="14990000";
      const role=isBarcelos?"BARCELOS":isMoura?"JUSANTE • VALIDAÇÃO":isManaus?"JUSANTE • REFERÊNCIA":upstreamCodes.has(code)?"MONTANTE":"CORREDOR";
      const extraClass=isBarcelos?"current":isMoura?"validation":isManaus?"downstream":"";''',
        "papel de Moura nos cartoes",
    )

    replace_once(
        INDEX_FILE,
        '''      byCode["14420000"],
      byCode["14480002"],
      byCode["14990000"]''',
        '''      byCode["14420000"],
      byCode["14480002"],
      byCode["14840000"],
      byCode["14990000"]''',
        "Moura no esquema topologico",
    )

    replace_once(
        INDEX_FILE,
        '''    const [cucui,taraqua,curicuriari,serrinha,barcelos,manaus]=stations;''',
        '''    const [cucui,taraqua,curicuriari,serrinha,barcelos,moura,manaus]=stations;''',
        "variavel Moura no esquema",
    )

    replace_once(
        INDEX_FILE,
        '''      ${stationBlock(curicuriari,465,180,"middle","")}
      ${stationBlock(serrinha,640,180,"middle","")}
      ${stationBlock(barcelos,830,180,"middle","BARCELOS")}
      ${stationBlock(manaus,1110,180,"end","JUSANTE")}''',
        '''      ${stationBlock(curicuriari,430,180,"middle","")}
      ${stationBlock(serrinha,585,180,"middle","")}
      ${stationBlock(barcelos,740,180,"middle","BARCELOS")}
      ${stationBlock(moura,900,180,"middle","VALIDAÇÃO")}
      ${stationBlock(manaus,1110,180,"end","JUSANTE")}''',
        "posicoes das estacoes no corredor",
    )

    replace_once(
        INDEX_FILE,
        '''      <text x="735" y="313" text-anchor="middle" fill="#93a7b8" font-size="11">
        Manaus amplia a leitura do corredor após Barcelos
      </text>''',
        '''      <text x="760" y="313" text-anchor="middle" fill="#93a7b8" font-size="11">
        Moura valida o comportamento a jusante; Manaus amplia o contexto do corredor
      </text>''',
        "legenda inferior do corredor",
    )

    replace_once(
        INDEX_FILE,
        '''const orderedCodes=["14110000","14280001","14330000","14420000","14480002","14990000"];''',
        '''const orderedCodes=["14110000","14280001","14330000","14420000","14480002","14840000","14990000"];''',
        "ordem do grafico de ondas",
    )

    replace_once(
        INDEX_FILE,
        '''      const role=String(s.estacao)==="14990000"?" • jusante":String(s.estacao)==="14480002"?" • Barcelos":"";''',
        '''      const code=String(s.estacao);
      const role=code==="14990000"?" • referência jusante":code==="14840000"?" • validação":code==="14480002"?" • Barcelos":"";''',
        "rotulos da comparacao numerica",
    )

    replace_once(
        INDEX_FILE,
        '''      const isBarcelos=code==="14480002";
      const isManaus=code==="14990000";
      const anchor=i===0?"start":i===points.length-1?"end":"middle";''',
        '''      const isBarcelos=code==="14480002";
      const isMoura=code==="14840000";
      const isManaus=code==="14990000";
      const anchor=i===0?"start":i===points.length-1?"end":"middle";''',
        "identificacao de Moura no grafico de ondas",
    )

    old_badge = '''      const badge=isBarcelos
        ? `<g transform="translate(${x-38},2)">
             <rect x="0" y="0" width="76" height="22" rx="11"
                   fill="rgba(63,167,255,.12)" stroke="rgba(79,216,255,.28)"/>
             <text x="38" y="15" text-anchor="middle" fill="#bfefff"
                   font-size="9" font-weight="800" letter-spacing="1.0">BARCELOS</text>
           </g>`
        : isManaus
          ? `<g transform="translate(${x-68},2)">
               <rect x="0" y="0" width="66" height="22" rx="11"
                     fill="rgba(245,196,81,.08)" stroke="rgba(245,196,81,.24)"/>
               <text x="33" y="15" text-anchor="middle" fill="#f7d98a"
                     font-size="9" font-weight="800" letter-spacing="1.0">JUSANTE</text>
             </g>`
          : "";'''

    new_badge = '''      const badge=isBarcelos
        ? `<g transform="translate(${x-38},2)">
             <rect x="0" y="0" width="76" height="22" rx="11"
                   fill="rgba(63,167,255,.12)" stroke="rgba(79,216,255,.28)"/>
             <text x="38" y="15" text-anchor="middle" fill="#bfefff"
                   font-size="9" font-weight="800" letter-spacing="1.0">BARCELOS</text>
           </g>`
        : isMoura
          ? `<g transform="translate(${x-40},2)">
               <rect x="0" y="0" width="80" height="22" rx="11"
                     fill="rgba(79,216,255,.08)" stroke="rgba(79,216,255,.28)"/>
               <text x="40" y="15" text-anchor="middle" fill="#bfefff"
                     font-size="9" font-weight="800" letter-spacing="1.0">VALIDAÇÃO</text>
             </g>`
          : isManaus
            ? `<g transform="translate(${x-68},2)">
                 <rect x="0" y="0" width="66" height="22" rx="11"
                       fill="rgba(245,196,81,.08)" stroke="rgba(245,196,81,.24)"/>
                 <text x="33" y="15" text-anchor="middle" fill="#f7d98a"
                       font-size="9" font-weight="800" letter-spacing="1.0">JUSANTE</text>
               </g>`
            : "";'''

    replace_once(
        INDEX_FILE,
        old_badge,
        new_badge,
        "badge de Moura no grafico de ondas",
    )


def validate():
    ana = ANA_FILE.read_text(encoding="utf-8")
    index = INDEX_FILE.read_text(encoding="utf-8")

    checks = [
        ('"14840000": "Moura"', ana, "Moura em collector/ana.py"),
        ('byCode["14840000"]', index, "Moura no esquema topologico"),
        ('"14840000","14990000"', index, "Moura na ordem do grafico"),
        ("JUSANTE • VALIDAÇÃO", index, "papel de validacao"),
        ("VALIDAÇÃO</text>", index, "badge de validacao"),
        ("V3.7A.3", index, "versao nova"),
    ]

    for expected, text, label in checks:
        if expected not in text:
            raise RuntimeError(f"Validacao falhou: {label}")

    print()
    print("======================================")
    print("INTEGRACAO DE MOURA VALIDADA")
    print("======================================")
    print("collector/ana.py: OK")
    print("index.html: OK")
    print("Moura 14840000: corredor/validacao a jusante")
    print("Modelo preditivo de Barcelos: nao alterado")


def main():
    if not ANA_FILE.exists():
        raise RuntimeError("collector/ana.py nao encontrado.")

    if not INDEX_FILE.exists():
        raise RuntimeError("index.html nao encontrado.")

    patch_ana()
    patch_index()
    validate()


if __name__ == "__main__":
    main()
