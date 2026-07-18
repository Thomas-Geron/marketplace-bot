# src/compra_olx.py
"""
Compra na OLX — fluxo paralelo ao do Facebook (run.py), sem tocar nele.

Monta a URL de busca de autos com produto e faixa de preço (parâmetros
q/ps/pe), o usuário faz login manualmente (o chat da OLX exige conta),
o bot coleta os links dos anúncios e digita/envia a mensagem no chat de
cada um, com a mesma trava de visitados do Facebook (visitados.json).
Aqui o anúncio só entra em visitados se a mensagem foi de fato enviada.

Seletores best-effort: a primeira execução (dry-run) salva capturas em
%LOCALAPPDATA%/MarketplaceBot/debug/olx-compra — mesmo processo de
calibração usado nos sites de Venda.

Localização: a OLX não filtra por CEP+raio como o Facebook; a v1 busca
nacionalmente (produto + preço) e o filtro de região será calibrado com
as capturas da primeira rodada.
"""
import random
import sys
import time
import urllib.parse
from datetime import datetime

from playwright.sync_api import sync_playwright

from coleta import calcular_alvo, carregar_visitados, salvar_visitados
from navegador import abrir_navegador
from sinal import esperar_prosseguir
from venda.sites.base import (
    clicar, dump_diagnostico, esperar_formulario, preencher_campo)

URL_BASE = "https://www.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios"

# candidatos de seletor dos cards de anúncio na página de busca
SEL_CARDS = [
    'a[data-ds-component="DS-NewAdCard-Link"]',
    'section[data-ds-component="DS-AdCard"] a[href]',
    'a[data-lurker-detail="list_id"]',
    '#ad-list a[href*="olx.com.br"]',
]

MAX_SCROLLS = 15
PAUSA_SCROLL = 1.5


def montar_url_busca(p):
    query = {"q": p.produto}
    if p.preco_min is not None:
        query["ps"] = str(p.preco_min)
    if p.preco_max is not None:
        query["pe"] = str(p.preco_max)
    return URL_BASE + "?" + urllib.parse.urlencode(query)


def pausa_humana(min_seg=1.0, max_seg=2.5):
    time.sleep(random.uniform(min_seg, max_seg))


def _melhor_seletor(pagina, candidatos):
    """O candidato que encontra mais cards vence (o DOM da OLX muda)."""
    melhor, melhor_total = None, 0
    for sel in candidatos:
        try:
            total = pagina.locator(sel).count()
        except Exception:
            total = 0
        if total > melhor_total:
            melhor, melhor_total = sel, total
    return melhor, melhor_total


def carregar_e_coletar(pagina):
    """Rola a lista para carregar mais anúncios e coleta links únicos."""
    total_anterior = -1
    for _ in range(MAX_SCROLLS):
        _, total = _melhor_seletor(pagina, SEL_CARDS)
        if total and total == total_anterior:
            break
        total_anterior = total
        pagina.mouse.wheel(0, 4000)
        pagina.wait_for_timeout(int(PAUSA_SCROLL * 1000))
    sel, total = _melhor_seletor(pagina, SEL_CARDS)
    if not sel:
        print("  ! nenhum card de anúncio reconhecido — ver capturas de debug")
        return []
    print(f"  cards reconhecidos com: {sel} ({total})")
    cards = pagina.locator(sel)
    links, vistos = [], set()
    for i in range(cards.count()):
        href = cards.nth(i).get_attribute("href")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.olx.com.br" + href
        href = href.split("#")[0].split("?")[0]
        if "olx.com.br" not in href or href in vistos:
            continue
        vistos.add(href)
        links.append(href)
    return links


def enviar_mensagem_olx(pagina, mensagem, dry_run):
    """Abre o chat do anúncio e digita (dry-run) ou envia a mensagem.
    Retorna True somente se a mensagem foi ENVIADA de verdade."""
    if not clicar(pagina, [
        'button:has-text("Chat")',
        '[data-testid*="chat" i]',
        'button:has-text("Enviar mensagem")',
        'a:has-text("Chat")',
    ], "abrir chat"):
        dump_diagnostico(pagina, "olx-compra", "sem-botao-chat")
        return False
    pagina.wait_for_timeout(2000)
    if not preencher_campo(pagina, [
        'textarea[placeholder*="mensagem" i]',
        '[contenteditable="true"]',
        "textarea",
    ], mensagem, "mensagem do chat"):
        dump_diagnostico(pagina, "olx-compra", "sem-campo-mensagem")
        return False
    time.sleep(3)  # tempo para conferir no navegador
    if dry_run:
        print("[DRY RUN] Mensagem digitada. Não será enviada.")
        return False
    if not clicar(pagina, [
        'button[type="submit"]:has-text("Enviar")',
        'button:has-text("Enviar")',
        '[data-testid*="send" i]',
    ], "enviar mensagem"):
        dump_diagnostico(pagina, "olx-compra", "sem-botao-enviar")
        return False
    pagina.wait_for_timeout(2000)
    return True


def executar(p):
    # print nunca pode derrubar/mascarar uma ação (console cp1252)
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        url = montar_url_busca(p)
        print(f"OLX — busca: {url}")
        print("Localização: busca nacional na v1 — o filtro de região será "
              "calibrado com as capturas da primeira rodada.")
        pagina.goto(url)
        pagina.wait_for_load_state("domcontentloaded")
        esperar_formulario(pagina)

        esperar_prosseguir(
            "Faça login na OLX (o chat exige conta) e clique em 'Prosseguir'.")
        dump_diagnostico(pagina, "olx-compra", "busca")

        links = carregar_e_coletar(pagina)
        visitados = carregar_visitados()
        urls_visitadas = {item["url"] for item in visitados}
        links = [link for link in links if link not in urls_visitadas]

        total = len(links)
        alvo = calcular_alvo(total, p.quantidade)
        print(f"Encontrados {total} anúncios novos. Vou processar {alvo}.")

        for i, link in enumerate(links[:alvo]):
            print(f"[{i + 1}/{alvo}] abrindo anúncio...")
            pagina.goto(link)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(2500)
            pausa_humana(1, 2)

            if i == 0:
                dump_diagnostico(pagina, "olx-compra", "anuncio")

            enviado = enviar_mensagem_olx(pagina, p.mensagem, p.dry_run)

            if enviado and not p.dry_run:
                visitados.append({
                    "url": link,
                    "site": "olx",
                    "produto": p.produto,
                    "cep": p.cep,
                    "mensagem": p.mensagem,
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                urls_visitadas.add(link)
                salvar_visitados(visitados)
            pausa_humana(4, 9)

        print("Concluído.")
        contexto.close()
