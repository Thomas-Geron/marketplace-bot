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

A OLX barra o navegador AUTOMATIZADO: a mesma URL abre normalmente num
navegador comum, mas o Cloudflare reconhece os sinais de automação do
Playwright. Por isso a OLX roda no **Microsoft Edge do computador**,
iniciado como um atalho qualquer e dirigido pelo DevTools (CDP) — sessão
comum de navegador, sem flags de automação (ver navegador.py). Nada é
mascarado: se ainda assim aparecer verificação, o bot para e espera VOCÊ
resolver na janela. Rodar poucos anúncios por vez continua ajudando.
"""
import random
import re
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

# candidatos de seletor dos cards de anúncio (o primeiro é o atual).
# NÃO usar algo genérico como `section a[href*="olx.com.br"]`: numa página
# que não é a de resultados isso casa com o menu inteiro e o bot sai
# "abrindo anúncios" que na verdade são links da home.
SEL_CARDS = [
    'a[data-testid="adcard-link"]',
    'a[data-ds-component="DS-NewAdCard-Link"]',
    'section[data-ds-component="DS-AdCard"] a[href]',
]

# link de anúncio termina com o id numérico: .../chevrolet-onix-2013-1463780413
PADRAO_ANUNCIO = re.compile(r"-\d{6,}$")

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
    """URL da busca de carros.

    A região é um SEGMENTO DE CAMINHO (`/estado-rj`), não subdomínio: o
    `rj.olx.com.br` existe para anúncios antigos, mas numa busca ele
    redireciona para a home — foi o que fez o bot coletar links da home
    em vez de anúncios.
    """
    host = "https://www.olx.com.br"
    caminho = CAMINHO_BUSCA + (f"/estado-{uf}" if uf else "")
    query = {"q": p.produto}
    if p.preco_min is not None:
        query["ps"] = str(p.preco_min)
    if p.preco_max is not None:
        query["pe"] = str(p.preco_max)
    return host + caminho + "?" + urllib.parse.urlencode(query)


def _busca_do_produto(p, produto):
    """Cópia rasa dos parâmetros com o produto da vez — `montar_url_busca`
    lê `produto`, e a fila troca esse nome a cada volta."""
    class _Busca:
        pass
    copia = _Busca()
    copia.produto = produto
    copia.preco_min = p.preco_min
    copia.preco_max = p.preco_max
    return copia


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
        if not PADRAO_ANUNCIO.search(href):
            continue   # link de menu/serviço, não anúncio
        vistos.add(href)
        links.append(href)
    return links


SEL_CAMPO_CHAT = [
    'textarea[placeholder*="mensagem" i]',
    '[contenteditable="true"]',
    "textarea",
]


def _escrever_no_chat(pagina, mensagem):
    """Escreve no campo do chat, esteja ele na página ou num iframe.

    O anúncio da OLX carrega quase 20 iframes e o chat costuma abrir
    dentro de um deles — procurar só na página principal dá "campo não
    encontrado" mesmo com o chat aberto na tela.
    """
    if preencher_campo(pagina, SEL_CAMPO_CHAT, mensagem, "mensagem do chat"):
        return True
    for quadro in pagina.frames:
        if quadro == pagina.main_frame:
            continue
        for sel in SEL_CAMPO_CHAT:
            try:
                campo = quadro.locator(sel).first
                if campo.count() == 0 or not campo.is_visible():
                    continue
                campo.fill(str(mensagem))
                print("  OK mensagem do chat: preenchida (dentro de um iframe)")
                return True
            except Exception:
                continue
    return False


def _deslogado(pagina):
    """True se o cabeçalho ainda oferece 'Entrar' — sem conta, o chat da
    OLX não abre, e o motivo real não é 'campo não encontrado'."""
    for sel in ('a:text-is("Entrar")', 'button:text-is("Entrar")',
                'span:text-is("Entrar")'):
        try:
            alvo = pagina.locator(sel).first
            if alvo.count() and alvo.is_visible():
                return True
        except Exception:
            continue
    return False


def _parece_pedir_login(pagina):
    """True quando o que abriu foi a tela de acesso, e não o chat."""
    marcas = ("entrar sem senha", "esqueci a minha senha", "acesse sua conta",
              "entrar na conta", "faça login")
    try:
        corpo = (pagina.locator("body").inner_text(timeout=4000) or "").lower()
    except Exception:
        return False
    if any(m in corpo for m in marcas):
        return True
    for quadro in pagina.frames:
        try:
            texto = (quadro.locator("body").inner_text(timeout=2000) or "").lower()
        except Exception:
            continue
        if any(m in texto for m in marcas):
            return True
    return False


def enviar_mensagem_olx(pagina, mensagem, dry_run):
    """Abre o chat do anúncio e digita (dry-run) ou envia a mensagem.
    Retorna True somente se a mensagem foi ENVIADA de verdade."""
    # #price-box-button-chat é o chat DO ANÚNCIO. Não usar
    # `button:has-text("Chat")`: isso casa com o "Chat" do menu do site, e o
    # bot clicava no cabeçalho achando que tinha aberto a conversa.
    if not clicar(pagina, [
        "#price-box-button-chat",
        '[data-testid*="chat" i]',
        'a[href*="/chat"]',
        'button:has-text("Enviar mensagem")',
    ], "abrir chat"):
        dump_diagnostico(pagina, "olx-compra", "sem-botao-chat")
        return False
    pagina.wait_for_timeout(2500)
    if not _escrever_no_chat(pagina, mensagem):
        dump_diagnostico(pagina, "olx-compra", "sem-campo-mensagem")
        if _parece_pedir_login(pagina) or _deslogado(pagina):
            print("  ! o chat da OLX exige conta e esta sessão está "
                  "deslogada. Entre na OLX na janela do Edge que o bot abriu "
                  "e rode de novo — a sessão fica salva no perfil do bot.")
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


def _barreira_olx(pagina, momento):
    """Motivo pelo qual a OLX barrou o acesso, ou None se está tudo certo.

    São dois casos bem diferentes:
    - "verificação antibot": desafio interativo — o usuário resolve na
      janela aberta e o bot segue na mesma sessão;
    - "bloqueio de firewall": a OLX negou o acesso a esta sessão
      automatizada (Cloudflare 1020). NÃO há o que resolver na janela; a
      mesma URL costuma abrir normal num navegador comum. O bot não
      mascara os sinais de automação para contornar isso.
    """
    barreira = detectar_barreira(pagina)
    if barreira and any(t in barreira for t in
                        ("bloqueio", "antibot", "verificação", "negado")):
        print(f"  ! OLX barrou o acesso ({barreira}) em {momento}.")
        dump_diagnostico(pagina, "olx-compra", f"bloqueio-{momento}")
        return barreira
    return None


def _explicar_firewall():
    print("    Isto é bloqueio de acesso, não um desafio: não há captcha "
          "para resolver na janela.")
    print("    A OLX barra o navegador automatizado — a mesma busca costuma "
          "abrir normalmente no seu navegador do dia a dia.")
    print("    O bot NÃO disfarça os sinais de automação para contornar o "
          "bloqueio. Use a Compra no Facebook ou tente a OLX mais tarde.")


def _tentar_liberar(pagina, url, contexto):
    """Bloqueio na abertura: em vez de desistir, deixa a janela aberta para
    o usuário resolver a verificação e clicar em 'Prosseguir'. Retorna
    True se a OLX liberou."""
    print("    A janela está aberta: resolva a verificação nela (ou navegue "
          "até a OLX normalmente) e clique em 'Prosseguir'.")
    esperar_prosseguir(
        "Resolva a verificação da OLX na janela e clique em 'Prosseguir'.")
    try:
        pagina.goto(url)
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(4000)
    except Exception as exc:
        print(f"  ! não consegui recarregar a busca: {exc}")
        return False
    if _barreira_olx(pagina, "apos-verificacao"):
        print("  ! A OLX continua barrando. Tente mais tarde — e prefira "
              "poucos anúncios por rodada.")
        return False
    print("  OK OLX liberada — seguindo.")
    return True


def executar(p):
    # print nunca pode derrubar/mascarar uma ação (console cp1252)
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    fila = list(p.produtos)
    if not fila:
        print("OLX: informe ao menos um produto.")
        return
    if len(fila) > 1:
        print(f"Fila de {len(fila)} produto(s): {', '.join(fila)}")
        if p.quantidade:
            print(f"Até {p.quantidade} anúncio(s) POR PRODUTO.")

    uf = uf_do_cep(p.cep)
    if uf:
        print(f"OLX — região pelo CEP {p.cep}: {uf.upper()} "
              "(a OLX filtra por estado, não por raio em km)")
    else:
        print("OLX — CEP não reconhecido: busca nacional")

    with sync_playwright() as pw:
        # Edge iniciado NORMALMENTE (sem flags de automação) e dirigido por
        # CDP: é isso que evita o bloqueio do Cloudflare, não a marca do
        # navegador. Ver navegador.py.
        contexto, pagina = abrir_navegador(pw, "edge")
        pagina.set_default_timeout(120000)

        # histórico compartilhado pela fila: anúncio já contatado não volta
        visitados = carregar_visitados()
        urls_visitadas = {item["url"] for item in visitados}

        for posicao, produto in enumerate(fila, start=1):
            busca = _busca_do_produto(p, produto)
            url = montar_url_busca(busca, uf)
            print("")
            print(f"=== produto {posicao}/{len(fila)}: {produto} ===")
            print(f"OLX — busca: {url}")
            pagina.goto(url)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(4000)
            fechar_cookies(pagina)
            esperar_formulario(pagina)

            barreira = _barreira_olx(pagina, "busca")
            if barreira:
                liberou = False
                if "verificação" in barreira:
                    liberou = _tentar_liberar(pagina, url, contexto)
                else:
                    _explicar_firewall()
                if not liberou:
                    break

            # região inexistente/instável na OLX: cai para a busca nacional
            if uf and not _melhor_seletor(pagina, SEL_CARDS)[1]:
                url = montar_url_busca(busca, None)
                print(f"  ! nenhum anúncio na região — tentando nacional: {url}")
                pagina.goto(url)
                pagina.wait_for_load_state("domcontentloaded")
                pagina.wait_for_timeout(4000)

            aplicar_filtros(pagina, p)

            if posicao == 1:
                esperar_prosseguir(
                    "Faça login na OLX (o chat exige conta) e clique em "
                    "'Prosseguir'.")
                dump_diagnostico(pagina, "olx-compra", "busca")

            links = carregar_e_coletar(pagina)
            links = [link for link in links if link not in urls_visitadas]

            total = len(links)
            alvo = calcular_alvo(total, p.quantidade)   # vale por produto
            print(f"Encontrados {total} anúncios novos. Vou processar {alvo}.")

            for i, link in enumerate(links[:alvo]):
                print(f"[{i + 1}/{alvo}] abrindo anúncio...")
                pagina.goto(link)
                pagina.wait_for_load_state("domcontentloaded")
                pagina.wait_for_timeout(2500)
                pausa_humana(1, 2)

                if posicao == 1 and i == 0:
                    dump_diagnostico(pagina, "olx-compra", "anuncio")
                if _barreira_olx(pagina, f"anuncio-{i + 1}"):
                    _explicar_firewall()
                    break

                enviado = enviar_mensagem_olx(pagina, p.mensagem, p.dry_run)

                if enviado and not p.dry_run:
                    visitados.append({
                        "url": link,
                        "site": "olx",
                        "produto": produto,
                        "cep": p.cep,
                        "mensagem": p.mensagem,
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    urls_visitadas.add(link)
                    salvar_visitados(visitados)
                pausa_humana(4, 9)

        print("Concluído.")
        contexto.close()
