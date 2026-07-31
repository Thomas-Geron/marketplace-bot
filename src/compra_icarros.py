# src/compra_icarros.py
"""
Compra no iCarros — fluxo paralelo ao do Facebook (run.py), sem tocar nele.

Por que o iCarros entrou: o anúncio tem formulário de contato PRÓPRIO
(nome, e-mail, telefone e observações) que NÃO exige login — o bot
preenche e envia sem depender de sessão, diferente do Facebook e da OLX.

Calibrado com capturas reais (jul/2026):
- listagem que realmente filtra: `/comprar/usados/<marca>/<modelo>`
  (nacional) — os caminhos com um termo só (ex.: /comprar/carros/onix)
  devolvem anúncios de qualquer marca, então NÃO servem;
- anúncio: `/comprar/<cidade-uf>/<marca>/<modelo>/<ano>/<id>`, o que
  permite filtrar por estado a partir do CEP (a cidade está na URL);
- filtros de preço/ano por querystring (precode/precoate/anode) são
  IGNORADOS pelo site — por isso o preço é filtrado aqui, lendo o valor
  de cada card;
- contato: input#nome, input#email, input#telefoneCompleto, textarea e
  o botão "Enviar mensagem". Alguns anúncios só oferecem WhatsApp: esses
  são pulados (o bot não dispara WhatsApp).
"""
import random
import re
import sys
import time
import unicodedata
from datetime import datetime

from playwright.sync_api import sync_playwright

from coleta import calcular_alvo, carregar_visitados, salvar_visitados
from compra_olx import uf_do_cep
from navegador import abrir_navegador
from sinal import esperar_prosseguir
from venda.sites.base import (
    clicar, detectar_barreira, dump_diagnostico, fechar_cookies,
    preencher_campo)

HOST = "https://www.icarros.com.br"
# /comprar/<cidade-uf>/<marca>/<modelo>/<ano>/<id>
PADRAO_ANUNCIO = re.compile(
    r"/comprar/([a-z0-9-]+)/([a-z0-9-]+)/([a-z0-9-]+)/(\d{4})/[a-z]?\d{6,}")

MAX_SCROLLS = 12
PAUSA_SCROLL = 1.5

# lê os anúncios da listagem junto com o preço mostrado no card
JS_CARDS = r"""
() => {
  const padrao = /\/comprar\/[a-z0-9-]+\/[a-z0-9-]+\/[a-z0-9-]+\/\d{4}\/[a-z]?\d{6,}/;
  const vistos = {};
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href') || '';
    const m = href.match(padrao);
    if (!m) continue;
    const url = m[0];
    if (vistos[url]) continue;
    let caixa = a, preco = null;
    for (let i = 0; i < 6 && caixa; i++) {
      const texto = caixa.innerText || '';
      const p = texto.match(/R\$\s?([\d.]{4,})/);
      if (p) { preco = parseInt(p[1].replace(/\./g, ''), 10); break; }
      caixa = caixa.parentElement;
    }
    vistos[url] = preco;
  }
  return vistos;
}
"""


def _slug(texto):
    """'Chevrolet Onix' -> 'chevrolet-onix' (sem acento)."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def montar_url_busca(produto):
    """URL da listagem a partir do texto livre do usuário.

    O iCarros exige marca E modelo no caminho: 'chevrolet onix' vira
    /comprar/usados/chevrolet/onix. Com uma palavra só não dá para montar
    a busca (o site devolveria carros de qualquer marca) — retorna None.
    """
    partes = [p for p in _slug(produto).split("-") if p]
    if len(partes) < 2:
        return None
    return f"{HOST}/comprar/usados/{partes[0]}/{'-'.join(partes[1:])}"


def pausa_humana(min_seg=1.0, max_seg=2.5):
    time.sleep(random.uniform(min_seg, max_seg))


def coletar_anuncios(pagina, p):
    """Rola a listagem, coleta (url, preço) e aplica os filtros que o site
    ignora: faixa de preço e estado do CEP."""
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

    uf = uf_do_cep(p.cep)
    links, fora_preco, fora_uf, sem_preco = [], 0, 0, 0
    for caminho, preco in achados.items():
        dados = PADRAO_ANUNCIO.search(caminho)
        if not dados:
            continue
        cidade = dados.group(1)
        if uf and not cidade.endswith(f"-{uf}"):
            fora_uf += 1
            continue
        if preco is None:
            sem_preco += 1
        else:
            if p.preco_min is not None and preco < p.preco_min:
                fora_preco += 1
                continue
            if p.preco_max is not None and preco > p.preco_max:
                fora_preco += 1
                continue
        links.append(HOST + caminho)

    if uf:
        print(f"  filtro de estado ({uf.upper()}): {fora_uf} fora")
    if fora_preco:
        print(f"  filtro de preço: {fora_preco} fora da faixa "
              "(o iCarros ignora preço na URL, então o bot filtra aqui)")
    if sem_preco:
        print(f"  {sem_preco} anúncio(s) sem preço legível no card — mantidos")
    return links


def enviar_mensagem_icarros(pagina, p, dry_run):
    """Preenche o formulário de contato do anúncio. Retorna True apenas se
    a mensagem foi ENVIADA de verdade."""
    tem_form = pagina.locator("input#nome").count()
    if not tem_form:
        if pagina.locator('button:has-text("Enviar whatsapp")').count():
            print("  - anúncio só oferece WhatsApp — pulando "
                  "(o bot não dispara WhatsApp)")
        else:
            print("  ! formulário de contato não encontrado")
            dump_diagnostico(pagina, "icarros-compra", "sem-formulario")
        return False

    preencher_campo(pagina, ["input#nome", 'input[name="nome"]'],
                    p.nome_contato, "Nome")
    preencher_campo(pagina, ["input#email", 'input[name="email"]'],
                    p.email_contato, "E-mail")
    preencher_campo(pagina, ["input#telefoneCompleto", 'input[type="tel"]'],
                    p.telefone_contato, "Telefone")
    # textarea#texto é o campo "Observações"; a página tem outra textarea
    # (modal de pesquisa do site) que não pode ser confundida com ela
    preencher_campo(pagina, ["textarea#texto", 'textarea[name="texto"]',
                             "textarea"], p.mensagem, "Mensagem")

    # alguns anúncios pedem CPF; o bot não guarda esse dado
    try:
        if pagina.locator("input#cpf").first.is_visible():
            print("  ! este anúncio pede CPF — preencha na janela antes de "
                  "enviar (o bot não guarda CPF)")
    except Exception:
        pass
    time.sleep(2)  # tempo para conferir no navegador

    if dry_run:
        print("[DRY RUN] Formulário preenchido. Nada será enviado.")
        return False

    if not clicar(pagina, [
        'button:has-text("Enviar mensagem")',
        'button[type="submit"]:has-text("Enviar")',
    ], "enviar mensagem"):
        dump_diagnostico(pagina, "icarros-compra", "sem-botao-enviar")
        return False
    pagina.wait_for_timeout(3000)
    return True


def executar(p):
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    url = montar_url_busca(p.produto)
    if not url:
        print("iCarros: escreva MARCA e MODELO no campo Produto "
              f"(ex.: 'chevrolet onix'). Recebi apenas: {p.produto!r}")
        return
    if not (p.nome_contato and p.email_contato and p.telefone_contato):
        print("iCarros: preencha Nome, E-mail e Telefone de contato na "
              "interface — o formulário do anúncio exige os três.")
        return

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        print(f"iCarros — busca: {url}")
        pagina.goto(url)
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(5000)
        fechar_cookies(pagina)

        barreira = detectar_barreira(pagina)
        if barreira:
            print(f"  ! iCarros barrou o acesso ({barreira}).")
            dump_diagnostico(pagina, "icarros-compra", "barreira")
            contexto.close()
            return

        dump_diagnostico(pagina, "icarros-compra", "busca")
        links = coletar_anuncios(pagina, p)

        visitados = carregar_visitados()
        urls_visitadas = {item["url"] for item in visitados}
        links = [link for link in links if link not in urls_visitadas]

        total = len(links)
        alvo = calcular_alvo(total, p.quantidade)
        print(f"Encontrados {total} anúncios novos. Vou processar {alvo}.")

        # o iCarros não exige login para mandar mensagem, mas a pausa
        # mantém o mesmo ritual das outras fontes (revisar antes de enviar)
        esperar_prosseguir(
            "Confira a busca no navegador e clique em 'Prosseguir'.")

        for i, link in enumerate(links[:alvo]):
            print(f"[{i + 1}/{alvo}] abrindo anúncio...")
            pagina.goto(link)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(4000)
            fechar_cookies(pagina)
            pausa_humana(1, 2)

            if i == 0:
                dump_diagnostico(pagina, "icarros-compra", "anuncio")

            enviado = enviar_mensagem_icarros(pagina, p, p.dry_run)

            if enviado:
                visitados.append({
                    "url": link,
                    "site": "icarros",
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
