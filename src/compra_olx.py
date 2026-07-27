# src/compra_olx.py
"""
Compra na OLX — fluxo paralelo ao do Facebook (run.py), sem tocar nele.

Monta a URL de busca de autos (produto + faixa de preço), aplica os
filtros extras no painel lateral, o usuário faz login manualmente (o chat
da OLX exige conta), o bot coleta os links dos anúncios e digita/envia a
mensagem no chat de cada um, com a mesma trava de visitados do Facebook
(visitados.json). Aqui o anúncio só entra em visitados se a mensagem foi
de fato enviada.

Calibrado com capturas reais da OLX (jul/2026):
- cards da busca: `a[data-testid="adcard-link"]` (os data-ds-component
  antigos não existem mais);
- filtros do painel por id: mileage_min/mileage_max (km),
  regdate_min/regdate_max (ano), price_min/price_max (preço, que também
  vai na URL como ps/pe), e câmbio por checkbox de rótulo;
- região: a OLX não usa CEP+raio como o Facebook — ela separa por
  SUBDOMÍNIO de estado (ex.: rj.olx.com.br). O CEP dos parâmetros é
  convertido em UF; se a região não responder, cai para a busca nacional.
- o chat do anúncio abre por `button:has-text("Chat")`.

A OLX limita navegação automatizada (Cloudflare). O bot DETECTA o bloqueio
e para com uma mensagem clara — não tenta contornar. Se acontecer, espere
um pouco e rode de novo, com menos anúncios por rodada.
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
    clicar, detectar_barreira, dump_diagnostico, esperar_formulario,
    fechar_cookies, preencher_campo)

CAMINHO_BUSCA = "/autos-e-pecas/carros-vans-e-utilitarios"

# candidatos de seletor dos cards de anúncio (o primeiro é o atual)
SEL_CARDS = [
    'a[data-testid="adcard-link"]',
    'a[data-ds-component="DS-NewAdCard-Link"]',
    'section[data-ds-component="DS-AdCard"] a[href]',
    'section a[href*="olx.com.br"]',
]

# faixas de CEP por estado → subdomínio da OLX (a OLX regionaliza por UF)
_FAIXAS_CEP = [
    (1000, 19999, "sp"), (20000, 28999, "rj"), (29000, 29999, "es"),
    (30000, 39999, "mg"), (40000, 48999, "ba"), (49000, 49999, "se"),
    (50000, 56999, "pe"), (57000, 57999, "al"), (58000, 58999, "pb"),
    (59000, 59999, "rn"), (60000, 63999, "ce"), (64000, 64999, "pi"),
    (65000, 65999, "ma"), (66000, 68899, "pa"), (68900, 68999, "ap"),
    (69000, 69299, "am"), (69300, 69389, "rr"), (69400, 69899, "am"),
    (69900, 69999, "ac"), (70000, 72799, "df"), (72800, 72999, "go"),
    (73000, 73699, "df"), (73700, 76799, "go"), (76800, 76999, "ro"),
    (77000, 77995, "to"), (78000, 78899, "mt"), (79000, 79999, "ms"),
    (80000, 87999, "pr"), (88000, 89999, "sc"), (90000, 99999, "rs"),
]

MAX_SCROLLS = 15
PAUSA_SCROLL = 1.5


def uf_do_cep(cep):
    """UF (minúscula) a partir do CEP; None se não reconhecer."""
    digitos = "".join(c for c in str(cep or "") if c.isdigit())[:5]
    if len(digitos) < 5:
        return None
    numero = int(digitos)
    for inicio, fim, uf in _FAIXAS_CEP:
        if inicio <= numero <= fim:
            return uf
    return None


def montar_url_busca(p, uf=None):
    """URL da busca de carros: subdomínio da UF (quando houver) + filtros
    de preço, que a OLX aceita na própria URL (ps/pe)."""
    host = f"https://{uf}.olx.com.br" if uf else "https://www.olx.com.br"
    query = {"q": p.produto}
    if p.preco_min is not None:
        query["ps"] = str(p.preco_min)
    if p.preco_max is not None:
        query["pe"] = str(p.preco_max)
    return host + CAMINHO_BUSCA + "?" + urllib.parse.urlencode(query)


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


def aplicar_filtros(pagina, p):
    """Aplica no painel lateral os filtros que não cabem na URL
    (km, ano e câmbio). Cada um é opcional e tolerante a falha."""
    def aplicar(botoes):
        clicar(pagina, botoes, "aplicar filtro")
        pagina.wait_for_timeout(3500)

    km_max = getattr(p, "km_max", None)
    if km_max is not None:
        if preencher_campo(pagina, ["#mileage_max"], km_max, "KM até"):
            aplicar(['button[aria-label*="Quilometragem" i]',
                     'button:has-text("aplicar filtro Quilometragem")'])

    ano_min = getattr(p, "ano_min", None)
    ano_max = getattr(p, "ano_max", None)
    if ano_min is not None or ano_max is not None:
        preencher_campo(pagina, ["#regdate_min"], ano_min, "Ano de")
        preencher_campo(pagina, ["#regdate_max"], ano_max, "Ano até")
        aplicar(['button[aria-label*="Ano por intervalo" i]',
                 'button:has-text("aplicar filtro Ano")'])

    cambio = (getattr(p, "cambio", "") or "").strip()
    if cambio and cambio.lower() not in ("qualquer", "todos"):
        if clicar(pagina, [
            f'label:text-is("{cambio}")',
            f'span:text-is("{cambio}")',
            f'input[type="checkbox"][name="{cambio}"]',
        ], f"filtro de câmbio: {cambio}"):
            pagina.wait_for_timeout(3500)


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
        'a[href*="/chat"]',
        'button:has-text("Enviar mensagem")',
    ], "abrir chat"):
        dump_diagnostico(pagina, "olx-compra", "sem-botao-chat")
        return False
    pagina.wait_for_timeout(2500)
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


def _bloqueada(pagina, momento):
    """True se a OLX barrou o acesso (Cloudflare/antibot)."""
    barreira = detectar_barreira(pagina)
    if barreira and any(t in barreira for t in ("bloqueio", "antibot", "negado")):
        print(f"  ! OLX barrou o acesso ({barreira}) em {momento}.")
        print("    O bot NÃO tenta contornar. Espere alguns minutos, resolva "
              "a verificação na janela aberta e rode de novo com menos "
              "anúncios por rodada.")
        dump_diagnostico(pagina, "olx-compra", f"bloqueio-{momento}")
        return True
    return False


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

        uf = uf_do_cep(p.cep)
        url = montar_url_busca(p, uf)
        if uf:
            print(f"OLX — região pelo CEP {p.cep}: {uf.upper()} "
                  "(a OLX filtra por estado, não por raio em km)")
        else:
            print("OLX — CEP não reconhecido: busca nacional")
        print(f"OLX — busca: {url}")
        pagina.goto(url)
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(4000)
        fechar_cookies(pagina)
        esperar_formulario(pagina)

        if _bloqueada(pagina, "busca"):
            contexto.close()
            return

        # região inexistente/instável na OLX: cai para a busca nacional
        if uf and not _melhor_seletor(pagina, SEL_CARDS)[1]:
            url = montar_url_busca(p, None)
            print(f"  ! nenhum anúncio na região — tentando nacional: {url}")
            pagina.goto(url)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(4000)

        aplicar_filtros(pagina, p)

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
            if _bloqueada(pagina, f"anuncio-{i + 1}"):
                break

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
