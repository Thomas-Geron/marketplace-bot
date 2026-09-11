# src/compra_leiloes.py
"""
Leilões (Loop e Sodré Santoro) — fonte de Compra que SÓ LISTA.

Por que existe: os bancos (Santander, Bradesco, BV, Pan, Itaú) não vendem
os carros retomados no próprio site — encaminham para leiloeiro. Os dois
portais abaixo têm estoque PÚBLICO (navegar não pede login) e foram
calibrados ao vivo (set/2026):

- **Loop Leilões** (grupo Santander/Webmotors): a busca é
  `/estoque?marca=<MARCA>&modelo=<MODELO>` (em maiúsculas, como o
  autocomplete do site gera); o lote é `/leilao/<evento>/<carro>/<id>/<lote>`
  e o card traz "Lote em pregão dia 11/09 às 11h04", título com ano,
  "Km", a situação ("Aberto para Lance" / "Listagem em Andamento") e o
  lance ("R$ 14.000" ou "Em breve"). O nome do evento diz a origem
  (ex.: `exclusivo-financeiras`). A home abre um "aviso anti-golpes" que
  engole os cliques — o bot usa a URL de busca direto e não precisa dele.
- **Sodré Santoro**: `/veiculos/lotes?term=<texto>` e, para o caso
  "empresa que quebrou", `/judiciais/lotes?term=<texto>`. O lote fica em
  `leilao.sodresantoro.com.br/leilao/<id>/lote/<id>/` e o card vem em
  linhas: número do leilão, título, comitente ("BANCO, SEGURADORAS, ETC"
  ou a vara do TJ), data, lance, a ORIGEM/CONDIÇÃO ("SEGURO",
  "MÉDIA MONTA") e "CIDADE / UF". A aba Judiciais mistura imóvel,
  empilhadeira e TV — por isso todo lote precisa ter o modelo no título.

**O bot não dá lance.** Lance é compromisso financeiro com prazo curto e
habilitação pessoal; um seletor errado ali viraria dinheiro perdido. O
bot procura, filtra e lista com o link — o lance é com você.

Atenção à condição: "MÉDIA MONTA"/"GRANDE MONTA" é carro SINISTRADO
(recuperado de seguradora). O filtro "Ignorar com" da tela tira esses
lotes, porque ele olha o texto do card inteiro.
"""
import random
import re
import sys
import time
import unicodedata
import urllib.parse

from playwright.sync_api import sync_playwright

from coleta import calcular_alvo
from navegador import abrir_navegador
from venda.sites.base import detectar_barreira, dump_diagnostico, fechar_cookies

LOOP = "https://loopleiloes.com.br"
SODRE = "https://www.sodresantoro.com.br"

MAX_SCROLLS = 6
PAUSA_SCROLL = 1.5

JS_LOOP = r"""
() => {
  const re = /^\/leilao\/[^\/]+\/[^\/]+\/\d+\/\d+\/?$/;
  const saida = [];
  const vistos = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const href = (a.getAttribute('href') || '').split('?')[0];
    if (!re.test(href) || vistos.has(href)) continue;
    let caixa = a;
    for (let i = 0; i < 8 && caixa.parentElement; i++) {
      const t = caixa.innerText || '';
      if (/Lance (inicial|atual)/i.test(t) && /Km/i.test(t)) break;
      caixa = caixa.parentElement;
    }
    const texto = (caixa.innerText || '').replace(/\s+/g, ' ').trim();
    if (!/Lance/i.test(texto)) continue;
    vistos.add(href);
    saida.push({url: href, texto: texto.slice(0, 400)});
  }
  return saida;
}
"""

JS_SODRE = r"""
() => {
  const re = /leilao\.sodresantoro\.com\.br\/leilao\/\d+\/lote\/\d+/;
  const saida = [];
  const vistos = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const href = (a.href || '').split('?')[0];
    if (!re.test(href) || vistos.has(href)) continue;
    let caixa = a;
    for (let i = 0; i < 8 && caixa.parentElement; i++) {
      const t = caixa.innerText || '';
      if (/Lance/i.test(t) && /Leil[aã]o \d+/.test(t)) break;
      caixa = caixa.parentElement;
    }
    const linhas = (caixa.innerText || '').split('\n')
      .map(l => l.trim()).filter(Boolean);
    if (!linhas.some(l => /^Lance/i.test(l))) continue;
    vistos.add(href);
    saida.push({url: href, linhas: linhas.slice(0, 24)});
  }
  return saida;
}
"""

RE_LOOP_TITULO = re.compile(r"([A-ZÀ-Ú][A-ZÀ-Ú0-9 .\-]+?)\s+(\d{4}/\d{4})")
RE_LOOP_DATA = re.compile(r"preg[aã]o dia (\d{2}/\d{2}) [àa]s (\d{2}h\d{2})",
                          re.I)
RE_LOOP_KM = re.compile(r"\bKm\s*([\d.]+)", re.I)
RE_LOOP_LANCE = re.compile(
    r"Lance (?:inicial|atual):\s*(R\$\s*[\d.]+|Em breve|Sem lance atual)",
    re.I)
RE_SODRE_DATA = re.compile(r"^\d{2}/\d{2}/\d{2} \d{2}:\d{2}$")
RE_VALOR_BR = re.compile(r"^[\d.]+,\d{2}$")
RE_LOCAL = re.compile(r"^(.+?)\s*/\s*([A-Z]{2})$")
RE_KM = re.compile(r"^([\d.]+)\s*KM$", re.I)


def _chave(texto):
    """Sem acento, minúsculo e só letras/números separados por espaço."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _partes(produto):
    return [p for p in _chave(produto).split() if p]


def titulo_casa(titulo, produto):
    """O lote é do veículo procurado?

    Com marca + modelo, exige o MODELO no título (o leiloeiro às vezes
    abrevia a marca); com uma palavra só, exige essa palavra. É o que
    tira da aba Judiciais o terreno, a empilhadeira e a TV.
    """
    partes = _partes(produto)
    if not partes:
        return False
    exigidas = partes[1:] if len(partes) > 1 else partes
    chave = _chave(titulo)
    return all(p in chave for p in exigidas)


def montar_url_loop(produto, so_primeira_palavra=False):
    """`/estoque?marca=CHEVROLET&modelo=ONIX` — maiúsculas, como o site."""
    partes = _partes(produto)
    if not partes:
        return None
    query = {"marca": partes[0].upper()}
    if len(partes) > 1:
        modelo = partes[1] if so_primeira_palavra else " ".join(partes[1:])
        query["modelo"] = modelo.upper()
    return f"{LOOP}/estoque?" + urllib.parse.urlencode(query)


def montar_url_sodre(produto, judicial=False):
    base = "judiciais" if judicial else "veiculos"
    return (f"{SODRE}/{base}/lotes?"
            + urllib.parse.urlencode({"term": produto,
                                      "sort": "auction_date_init_asc"}))


def _rolar(pagina, js):
    anterior = -1
    for _ in range(MAX_SCROLLS):
        atual = len(pagina.evaluate(js))
        if atual and atual == anterior:
            break
        anterior = atual
        pagina.mouse.wheel(0, 4000)
        pagina.wait_for_timeout(int(PAUSA_SCROLL * 1000))
    return pagina.evaluate(js)


def _abrir(pagina, url, portal):
    pagina.goto(url)
    pagina.wait_for_load_state("domcontentloaded")
    pagina.wait_for_timeout(7000)
    fechar_cookies(pagina)
    barreira = detectar_barreira(pagina)
    if barreira:
        print(f"  ! {portal} barrou o acesso ({barreira}).")
        dump_diagnostico(pagina, f"leilao-{portal.lower()}", "barreira")
        return False
    return True


def _parse_loop(item):
    texto = item["texto"]
    titulo = RE_LOOP_TITULO.search(texto)
    data = RE_LOOP_DATA.search(texto)
    km = RE_LOOP_KM.search(texto)
    lance = RE_LOOP_LANCE.search(texto)
    lance_texto = lance.group(1) if lance else "sem lance"
    valor = None
    if "R$" in lance_texto:
        valor = int(re.sub(r"\D", "", lance_texto) or 0) or None
    situacao = ("aberto para lance" if "Aberto para Lance" in texto
                else "listagem em andamento"
                if "Listagem em Andamento" in texto else "")
    evento = item["url"].strip("/").split("/")[1]
    detalhes = [evento.replace("-", " ")]
    if situacao:
        detalhes.append(situacao)
    if texto.startswith("Financiamento") or " Financiamento " in texto[:40]:
        detalhes.append("aceita financiamento")
    return {
        "portal": "Loop",
        "url": LOOP + item["url"],
        "titulo": (f"{titulo.group(1)} {titulo.group(2)}" if titulo else ""),
        "data": (f"{data.group(1)} {data.group(2)}" if data else ""),
        "lance": valor,
        "lance_texto": lance_texto.lower() if not valor
                       else f"lance R$ {lance_texto.split('$')[-1].strip()}",
        "local": "",
        "uf": "",
        "km": km.group(1) if km else "",
        "detalhes": detalhes,
        "texto": texto,
    }


def _parse_sodre(item, judicial):
    linhas = item["linhas"]
    i_leilao = next((i for i, l in enumerate(linhas)
                     if l.startswith("Leilão ") or l.startswith("Leilao ")),
                    None)
    if i_leilao is None:
        return None
    j = i_leilao + 1
    if j < len(linhas) and linhas[j].isdigit():
        j += 1                         # contador de visualizações
    titulo = linhas[j] if j < len(linhas) else ""
    comitente = linhas[j + 1] if j + 1 < len(linhas) else ""
    data = next((l for l in linhas if RE_SODRE_DATA.match(l)), "")

    valor, lance_texto, k_valor = None, "sem lance", j + 1
    for k, linha in enumerate(linhas):
        baixa = linha.lower()
        if baixa.startswith("lance atual") or baixa.startswith("lance inicial"):
            if k + 1 < len(linhas) and RE_VALOR_BR.match(linhas[k + 1]):
                reais = linhas[k + 1].split(",")[0]
                valor = int(reais.replace(".", ""))
                tipo = "atual" if "atual" in baixa else "inicial"
                lance_texto = f"lance {tipo} R$ {reais}"
                k_valor = k + 1
            break

    local, uf, i_local = "", "", None
    for k in range(k_valor + 1, len(linhas)):
        achado = RE_LOCAL.match(linhas[k])
        if achado:
            local, uf, i_local = achado.group(1).title(), achado.group(2), k
            break
    km = next((RE_KM.match(l).group(1) for l in linhas if RE_KM.match(l)),
              "")
    fim = i_local if i_local is not None else min(len(linhas), k_valor + 5)
    detalhes = [comitente] + [l for l in linhas[k_valor + 1:fim]
                              if not RE_KM.match(l)]
    return {
        "portal": "Sodré (judicial)" if judicial else "Sodré",
        "url": item["url"],
        "titulo": titulo,
        "data": data,
        "lance": valor,
        "lance_texto": lance_texto,
        "local": local,
        "uf": uf,
        "km": km,
        # "Financiar" é o botão do card: vira a informação que ele dá
        "detalhes": ["aceita financiamento" if d.lower() == "financiar"
                     else d for d in detalhes if d],
        "texto": " ".join(linhas),
    }


def coletar_loop(pagina, produto):
    """Lotes da Loop para este veículo."""
    url = montar_url_loop(produto)
    if not url:
        return []
    print(f"  Loop: {url}")
    if not _abrir(pagina, url, "Loop"):
        return []
    brutos = _rolar(pagina, JS_LOOP)
    # modelo com duas palavras ("onix plus") pode não existir com esse
    # nome na Loop: tenta de novo só com a primeira
    if not brutos and len(_partes(produto)) > 2:
        url = montar_url_loop(produto, so_primeira_palavra=True)
        print(f"  Loop (só a 1ª palavra do modelo): {url}")
        if _abrir(pagina, url, "Loop"):
            brutos = _rolar(pagina, JS_LOOP)
    return [_parse_loop(item) for item in brutos]


def coletar_sodre(pagina, produto, judicial=False):
    """Lotes da Sodré Santoro (veículos ou judiciais) para este veículo."""
    url = montar_url_sodre(produto, judicial)
    rotulo = "Sodré judiciais" if judicial else "Sodré"
    print(f"  {rotulo}: {url}")
    if not _abrir(pagina, url, "Sodre"):
        return []
    brutos = _rolar(pagina, JS_SODRE)
    lotes = [_parse_sodre(item, judicial) for item in brutos]
    return [lote for lote in lotes if lote]


def filtrar(lotes, produto, p):
    """Aplica modelo no título, faixa de preço (sobre o lance) e palavras."""
    aceitos = []
    fora_modelo = fora_preco = fora_palavra = 0
    for lote in lotes:
        if not titulo_casa(lote["titulo"], produto):
            fora_modelo += 1
            continue
        valor = lote["lance"]
        if valor is not None:
            if p.preco_min is not None and valor < p.preco_min:
                fora_preco += 1
                continue
            if p.preco_max is not None and valor > p.preco_max:
                fora_preco += 1
                continue
        serve, _ = p.anuncio_serve(lote["texto"])
        if not serve:
            fora_palavra += 1
            continue
        aceitos.append(lote)
    if fora_modelo:
        print(f"  {fora_modelo} lote(s) de outro veículo/categoria descartado(s)")
    if fora_preco:
        print(f"  filtro de preço (sobre o lance): {fora_preco} fora da faixa")
    if fora_palavra:
        print(f"  filtro de palavras: {fora_palavra} pulado(s)")
    return aceitos


def imprimir_lote(posicao, total, lote):
    local = f"{lote['local']}/{lote['uf']}" if lote["uf"] else ""
    km = f"{lote['km']} km" if lote["km"] else ""
    print(f"[{posicao}/{total}] [{lote['portal']}] {lote['titulo']} — "
          f"{lote['lance_texto']}" + (f" — {lote['data']}" if lote["data"] else ""))
    extras = [d for d in lote["detalhes"] if d] + [x for x in (local, km) if x]
    if extras:
        print(f"      {' · '.join(extras)}")
    print(f"      {lote['url']}")


def pausa_humana(min_seg=1.0, max_seg=2.5):
    time.sleep(random.uniform(min_seg, max_seg))


def executar(p):
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    fila = [nome for nome in p.produtos if _partes(nome)]
    if not fila:
        print("Leilões: escreva ao menos um veículo (ex.: 'chevrolet onix').")
        return

    print("Leilões (Loop e Sodré Santoro): o bot PROCURA e LISTA os lotes — "
          "não dá lance.")
    print("Lance é compromisso financeiro com prazo: fica com você, no link.")
    print("Leilão é nacional: a região não filtra aqui, a cidade vem no "
          "resultado.")

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)
        viu_sinistro = False

        for posicao, produto in enumerate(fila, start=1):
            # cada veículo tem a SUA margem de preço
            p.usar_produto(produto)
            print("")
            print(f"=== veículo {posicao}/{len(fila)}: {produto} ===")
            print(f"Faixa de preço (sobre o lance): {p.texto_faixa()}")

            lotes = []
            for coletor in (lambda: coletar_loop(pagina, produto),
                            lambda: coletar_sodre(pagina, produto),
                            lambda: coletar_sodre(pagina, produto, True)):
                try:
                    lotes.extend(coletor())
                except Exception as exc:
                    print(f"  ! um dos portais falhou: {exc}")
                pausa_humana(1, 2)

            print(f"  {len(lotes)} lote(s) encontrados nos portais")
            aceitos = filtrar(lotes, produto, p)
            alvo = calcular_alvo(len(aceitos), p.quantidade)   # por veículo
            print(f"Dentro dos filtros: {len(aceitos)}. Listando {alvo}.")
            print("")
            for i, lote in enumerate(aceitos[:alvo], start=1):
                imprimir_lote(i, alvo, lote)
                if "monta" in _chave(lote["texto"]):
                    viu_sinistro = True

        if viu_sinistro:
            print("")
            print("Legenda: 'média/grande monta' = carro SINISTRADO, recuperado "
                  "de seguradora. Para tirar esses lotes, ponha 'monta' em "
                  "'Ignorar com'.")
        print("")
        print("Concluído. Nenhum lance foi dado — os links acima levam ao lote.")
        contexto.close()
