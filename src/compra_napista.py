# src/compra_napista.py
"""
Compra na NaPista — fluxo paralelo ao do Facebook (run.py), sem tocar nele.

**A NaPista não tem formulário de mensagem.** Conferido ao vivo (ago/2026)
em vários anúncios: o que existe é "Enviar WhatsApp", "Ver telefone e
endereço" e um formulário que NÃO fala com o vendedor — é uma consulta de
crédito (nome, celular, e-mail e **CPF**) enviada às lojas parceiras, sem
sequer um campo de mensagem. O bot não dispara WhatsApp e não vai mandar
o CPF de ninguém para uma análise de crédito só para "entrar em contato".

Então este modo faz o que a NaPista permite: **procura e lista** os
anúncios que batem com a sua busca — marca/modelo, faixa de preço e
estado do CEP — com link, preço, ano, km e cidade. Falar com a loja
(WhatsApp ou telefone) fica com você, na janela que o bot deixa aberta.

Busca calibrada ao vivo:
- `/busca/<marca>[/<modelo>]` (o site redireciona para `?pn=1`, que é o
  número da página); `?q=<texto>` NÃO filtra — devolve qualquer carro;
- cards são links `a[href^="/anuncios/<uuid>"]` e o texto do próprio link
  traz título, preço, ano, km e "Cidade, UF";
- o vendedor aparece como `/busca/carro-vendedor-<loja>-<id>` na página do
  anúncio — é essa a identidade usada no histórico.
"""
import random
import re
import sys
import time
import unicodedata

from playwright.sync_api import sync_playwright

from coleta import calcular_alvo
from compra_olx import uf_do_cep
from historico import Historico
from navegador import abrir_navegador
from sinal import esperar_prosseguir
from venda.sites.base import detectar_barreira, dump_diagnostico, fechar_cookies

HOST = "https://napista.com.br"
PADRAO_ANUNCIO = re.compile(r"^/anuncios/[0-9a-f-]{20,}$")

MAX_PAGINAS = 3

# cada card é o próprio link do anúncio; o texto traz tudo que o bot filtra
JS_CARDS = r"""
() => {
  const saida = {};
  for (const a of document.querySelectorAll('a[href^="/anuncios/"]')) {
    const url = (a.getAttribute('href') || '').split('?')[0];
    if (saida[url]) continue;
    const texto = (a.innerText || '').replace(/\s+/g, ' ').trim();
    if (!texto) continue;
    const preco = texto.match(/R\$\s*([\d.]{4,})/);
    const ano = texto.match(/\b(19|20)\d{2}\b/);
    const km = texto.match(/([\d.]+)\s*km/i);
    const local = texto.match(/([^,]+),\s*([A-Za-z]{2})\s*$/);
    saida[url] = {
      texto: texto.slice(0, 120),
      preco: preco ? parseInt(preco[1].replace(/\./g, ''), 10) : null,
      ano: ano ? parseInt(ano[0], 10) : null,
      km: km ? parseInt(km[1].replace(/\./g, ''), 10) : null,
      cidade: local ? local[1].trim() : null,
      uf: local ? local[2].toLowerCase() : null,
    };
  }
  return saida;
}
"""


def _slug(texto):
    """'Chevrolet Onix' -> 'chevrolet/onix' (sem acento)."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def montar_url_busca(produto, pagina_n=1):
    """`/busca/<marca>[/<modelo>]?pn=<n>` — só a marca já funciona."""
    partes = [p for p in _slug(produto).split("-") if p]
    if not partes:
        return None
    caminho = "/".join(partes[:2])
    return f"{HOST}/busca/{caminho}?pn={pagina_n}"


def pausa_humana(min_seg=1.0, max_seg=2.5):
    time.sleep(random.uniform(min_seg, max_seg))


def coletar_anuncios(pagina, p, uf=""):
    """Lê os cards da página atual e aplica preço e estado."""
    achados = pagina.evaluate(JS_CARDS)
    achados = {u: d for u, d in achados.items() if PADRAO_ANUNCIO.match(u)}
    encontrados, fora_preco, fora_uf = [], 0, 0
    for caminho, dados in achados.items():
        if uf and dados.get("uf") and dados["uf"] != uf.lower():
            fora_uf += 1
            continue
        preco = dados.get("preco")
        if preco is not None:
            if p.preco_min is not None and preco < p.preco_min:
                fora_preco += 1
                continue
            if p.preco_max is not None and preco > p.preco_max:
                fora_preco += 1
                continue
        dados["url"] = HOST + caminho
        encontrados.append(dados)
    print(f"  {len(achados)} anúncio(s) na página; {len(encontrados)} dentro "
          "dos filtros")
    if fora_uf:
        print(f"  filtro de estado ({uf.upper()}): {fora_uf} fora")
    if fora_preco:
        print(f"  filtro de preço: {fora_preco} fora da faixa")
    return encontrados


def _vendedor_do_anuncio(pagina):
    """Nome da loja que anuncia, lido do link de vendedor (ou None)."""
    try:
        alvo = pagina.locator('a[href*="carro-vendedor-"]').first
        if alvo.count() == 0:
            return None
        href = alvo.get_attribute("href") or ""
        nome = href.split("carro-vendedor-")[-1].rsplit("-", 1)[0]
        return nome.replace("-", " ").title() or None
    except Exception:
        return None


def _formas_de_contato(pagina):
    """O que este anúncio oferece para falar com a loja."""
    formas = []
    try:
        if pagina.locator('button:has-text("Enviar WhatsApp")').count():
            formas.append("WhatsApp")
        if pagina.locator('a:has-text("Ver telefone")').count():
            formas.append("telefone")
    except Exception:
        pass
    return formas


def executar(p):
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    fila = [nome for nome in p.produtos if montar_url_busca(nome)]
    if not fila:
        print("NaPista: escreva ao menos um produto (ex.: 'chevrolet onix').")
        return

    print("NaPista: este site NÃO tem formulário de mensagem — só WhatsApp e "
          "telefone da loja.")
    print("O bot procura e LISTA os anúncios que batem com a sua busca; falar "
          "com a loja é com você, na janela aberta.")
    print("(O formulário que a NaPista mostra no anúncio é consulta de "
          "crédito, com CPF — o bot não preenche isso.)")

    uf = uf_do_cep(p.cep) or ""
    if uf:
        print(f"Região pelo CEP {p.cep}: {uf.upper()}")
    if len(fila) > 1:
        print(f"Fila de {len(fila)} produto(s): {', '.join(fila)}")
        if p.quantidade:
            print(f"Até {p.quantidade} anúncio(s) POR PRODUTO.")

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        # o histórico não recebe nada aqui (nenhuma mensagem é enviada),
        # mas serve para não listar de novo quem você já contatou
        historico = Historico()

        for posicao, produto in enumerate(fila, start=1):
            print("")
            print(f"=== produto {posicao}/{len(fila)}: {produto} ===")

            achados, vistos = [], set()
            for numero in range(1, MAX_PAGINAS + 1):
                url = montar_url_busca(produto, numero)
                print(f"NaPista — busca (página {numero}): {url}")
                pagina.goto(url)
                pagina.wait_for_load_state("domcontentloaded")
                pagina.wait_for_timeout(6000)
                fechar_cookies(pagina)

                barreira = detectar_barreira(pagina)
                if barreira:
                    print(f"  ! NaPista barrou o acesso ({barreira}).")
                    dump_diagnostico(pagina, "napista-compra", "barreira")
                    break

                if posicao == 1 and numero == 1:
                    dump_diagnostico(pagina, "napista-compra", "busca")
                novos = [d for d in coletar_anuncios(pagina, p, uf)
                         if d["url"] not in vistos]
                if not novos:
                    break
                vistos.update(d["url"] for d in novos)
                achados.extend(novos)

            achados = [d for d in achados
                       if not historico.ja_contatado(d["url"])[0]]
            total = len(achados)
            alvo = calcular_alvo(total, p.quantidade)   # vale por produto
            print(f"Encontrados {total} anúncios novos. Vou abrir {alvo}.")

            if posicao == 1:
                esperar_prosseguir(
                    "Confira a busca no navegador e clique em 'Prosseguir'.")

            for i, dados in enumerate(achados[:alvo]):
                print(f"[{i + 1}/{alvo}] {dados['texto'][:80]}")
                pagina.goto(dados["url"])
                pagina.wait_for_load_state("domcontentloaded")
                pagina.wait_for_timeout(5000)
                fechar_cookies(pagina)

                if posicao == 1 and i == 0:
                    dump_diagnostico(pagina, "napista-compra", "anuncio")

                loja = _vendedor_do_anuncio(pagina)
                formas = _formas_de_contato(pagina) or ["nenhum contato direto"]
                print(f"    {dados['url']}")
                print(f"    loja: {loja or 'não identificada'} | contato: "
                      f"{', '.join(formas)}")
                if dados.get("preco"):
                    print(f"    R$ {dados['preco']:,}".replace(",", ".")
                          + f" | {dados.get('ano') or '?'} | "
                            f"{dados.get('km') or '?'} km | "
                            f"{dados.get('cidade') or '?'}")
                pausa_humana(2, 4)

        print("")
        print("Concluído. Nenhuma mensagem foi enviada: a NaPista não tem "
              "esse caminho — use o WhatsApp ou o telefone da loja.")
        contexto.close()
