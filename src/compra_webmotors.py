# src/compra_webmotors.py
"""
Compra na Webmotors — fluxo paralelo ao do Facebook (run.py), sem tocar nele.

Calibrado com capturas reais (ago/2026):
- busca: `/carros/estoque/<marca>/<modelo>` (o site normaliza e acrescenta
  os filtros na querystring sozinho);
- anúncio: `/comprar/<marca>/<modelo>/<versao>/<portas>/<anos>/<id>`;
- contato: o anúncio traz o formulário "Envie uma mensagem ao vendedor"
  (`fullName`, `email`, `numberPhone`, `message` + `#ButtonSendProposal`).
  Há OUTRO formulário na página, o de simulação de financiamento, que pede
  CPF — por isso tudo aqui é escopado pelo form que contém a `textarea`.

Como o site não expõe faixa de preço na URL de forma estável, o preço é
lido do card e filtrado aqui, como no iCarros.

A Webmotors usa desafio "Pressione e segure" contra navegador automatizado.
O bot NÃO tenta resolver: ele reconhece, deixa a janela aberta e espera
você concluir (`esperar_desafio_humano`).
"""
import random
import re
import sys
import time
import unicodedata

from playwright.sync_api import sync_playwright

from coleta import calcular_alvo
from historico import Historico, identificar_vendedor
from compra_olx import uf_do_cep
from navegador import abrir_navegador
from sinal import esperar_prosseguir
from venda.sites.base import (
    clicar, detectar_barreira, dump_diagnostico, esperar_desafio_humano,
    fechar_cookies, preencher_campo)

HOST = "https://www.webmotors.com.br"
PADRAO_ANUNCIO = re.compile(
    r"/comprar/[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+/[0-9-]+/\d{6,}")

# o formulário de contato é o único com textarea — o outro é financiamento
FORM_CONTATO = 'form:has(textarea[name="message"])'

MAX_SCROLLS = 12
PAUSA_SCROLL = 1.5

JS_CARDS = r"""
() => {
  const padrao = /\/comprar\/[a-z0-9-]+\/[a-z0-9-]+\/[a-z0-9-]+\/[a-z0-9-]+\/[0-9-]+\/\d{6,}/;
  const vistos = {};
  for (const a of document.querySelectorAll('a[href]')) {
    const m = (a.getAttribute('href') || '').match(padrao);
    if (!m) continue;
    if (vistos[m[0]] !== undefined) continue;
    let caixa = a, preco = null;
    for (let i = 0; i < 6 && caixa; i++) {
      const p = (caixa.innerText || '').match(/R\$\s?([\d.]{4,})/);
      if (p) { preco = parseInt(p[1].replace(/\./g, ''), 10); break; }
      caixa = caixa.parentElement;
    }
    vistos[m[0]] = preco;
  }
  return vistos;
}
"""


def _slug(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def montar_url_busca(produto):
    """/carros/estoque/<marca>/<modelo> a partir do texto livre.

    Com uma palavra só busca por marca (ou modelo) — a Webmotors aceita os
    dois casos, diferente do iCarros, que exige marca E modelo.
    """
    partes = [p for p in _slug(produto).split("-") if p]
    if not partes:
        return None
    return f"{HOST}/carros/estoque/" + "/".join(partes[:2])


def pausa_humana(min_seg=1.0, max_seg=2.5):
    time.sleep(random.uniform(min_seg, max_seg))


def coletar_anuncios(pagina, p):
    """Rola a lista, coleta (url, preço) e aplica a faixa de preço."""
    anterior = -1
    for _ in range(MAX_SCROLLS):
        atual = len(pagina.evaluate(JS_CARDS))
        if atual and atual == anterior:
            break
        anterior = atual
        pagina.mouse.wheel(0, 4000)
        pagina.wait_for_timeout(int(PAUSA_SCROLL * 1000))

    achados = pagina.evaluate(JS_CARDS)
    print(f"  {len(achados)} anúncio(s) na listagem")

    links, fora, sem_preco = [], 0, 0
    for caminho, preco in achados.items():
        if preco is None:
            sem_preco += 1
        else:
            if p.preco_min is not None and preco < p.preco_min:
                fora += 1
                continue
            if p.preco_max is not None and preco > p.preco_max:
                fora += 1
                continue
        links.append(HOST + caminho)
    if fora:
        print(f"  filtro de preço: {fora} fora da faixa")
    if sem_preco:
        print(f"  {sem_preco} sem preço legível no card — mantidos")
    return links


def enviar_mensagem_webmotors(pagina, p, dry_run):
    """Preenche 'Envie uma mensagem ao vendedor'. True só se ENVIOU."""
    if not pagina.locator(FORM_CONTATO).count():
        print("  ! formulário de contato não encontrado neste anúncio")
        dump_diagnostico(pagina, "webmotors-compra", "sem-formulario")
        return False

    preencher_campo(pagina, [f'{FORM_CONTATO} input[name="fullName"]'],
                    p.nome_contato, "Nome")
    preencher_campo(pagina, [f'{FORM_CONTATO} input[name="email"]'],
                    p.email_contato, "E-mail")
    preencher_campo(pagina, [f'{FORM_CONTATO} input[name="numberPhone"]'],
                    p.telefone_contato, "Telefone")
    preencher_campo(pagina, [f'{FORM_CONTATO} textarea[name="message"]'],
                    p.mensagem, "Mensagem")
    time.sleep(2)   # tempo para conferir no navegador

    if dry_run:
        print("[DRY RUN] Formulário preenchido. Nada será enviado.")
        return False

    if not clicar(pagina, ["#ButtonSendProposal",
                           f'{FORM_CONTATO} button[type="submit"]'],
                  "enviar mensagem"):
        dump_diagnostico(pagina, "webmotors-compra", "sem-botao-enviar")
        return False
    pagina.wait_for_timeout(3000)
    return True


def executar(p):
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    if not (p.nome_contato and p.email_contato and p.telefone_contato):
        print("Webmotors: preencha Nome, E-mail e Telefone na interface — "
              "o formulário do anúncio exige os três.")
        return

    fila = [nome for nome in p.produtos if montar_url_busca(nome)]
    if not fila:
        print(f"Webmotors: informe o veículo no campo Produto "
              f"(ex.: 'chevrolet onix'). Recebi: {p.produtos!r}")
        return
    if len(fila) > 1:
        print(f"Fila de {len(fila)} produto(s): {', '.join(fila)}")
        if p.quantidade:
            print(f"Até {p.quantidade} anúncio(s) POR PRODUTO.")
    if uf_do_cep(p.cep):
        print("Webmotors: a busca não filtra por região nesta versão "
              "(o site usa cidade escolhida no painel, não o CEP).")

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        # histórico compartilhado pela fila E entre execuções: nem o mesmo
        # anúncio nem a mesma pessoa recebem mensagem duas vezes
        historico = Historico()

        for posicao, produto in enumerate(fila, start=1):
            # cada veículo tem a SUA margem de preço
            p.usar_produto(produto)
            print(f"Faixa de preço: {p.texto_faixa()}")
            url = montar_url_busca(produto)
            print("")
            print(f"=== produto {posicao}/{len(fila)}: {produto} ===")
            print(f"Webmotors — busca: {url}")
            pagina.goto(url)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(6000)
            fechar_cookies(pagina)

            # o desafio "Pressione e segure" é resolvido por VOCÊ na janela
            if not esperar_desafio_humano(pagina, minutos=5):
                break
            barreira = detectar_barreira(pagina)
            if barreira:
                print(f"  ! Webmotors barrou o acesso ({barreira}).")
                dump_diagnostico(pagina, "webmotors-compra", "barreira")
                break

            if posicao == 1:
                dump_diagnostico(pagina, "webmotors-compra", "busca")
            links = coletar_anuncios(pagina, p)
            links = historico.novos(links)

            total = len(links)
            alvo = calcular_alvo(total, p.quantidade)   # vale por produto
            print(f"Encontrados {total} anúncios novos. Vou processar {alvo}.")

            if posicao == 1:
                esperar_prosseguir(
                    "Confira a busca no navegador e clique em 'Prosseguir'.")

            for i, link in enumerate(links[:alvo]):
                print(f"[{i + 1}/{alvo}] abrindo anúncio...")
                pagina.goto(link)
                pagina.wait_for_load_state("domcontentloaded")
                pagina.wait_for_timeout(5000)
                fechar_cookies(pagina)
                if not esperar_desafio_humano(pagina, minutos=5):
                    break
                pausa_humana(1, 2)

                if posicao == 1 and i == 0:
                    dump_diagnostico(pagina, "webmotors-compra", "anuncio")

                # trava por PESSOA: um anunciante com vários carros

                # receberia uma mensagem por anúncio sem esta checagem

                vendedor = identificar_vendedor(pagina, "webmotors")

                bloqueado, motivo = historico.ja_contatado(link, vendedor)

                if bloqueado:

                    print(f"  [pulado] {motivo}")

                    continue


                enviado = enviar_mensagem_webmotors(pagina, p, p.dry_run)


                if enviado:

                    historico.registrar(link, "webmotors", produto, p.mensagem,

                                        p.cep, vendedor)
                pausa_humana(4, 9)

        print("Concluído.")
        contexto.close()
