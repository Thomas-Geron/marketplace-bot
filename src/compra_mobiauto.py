# src/compra_mobiauto.py
"""
Compra na Mobiauto — fluxo paralelo ao do Facebook (run.py), sem tocar nele.

Por que a Mobiauto entrou: o anúncio tem o bloco **"Fale com o vendedor"**
(nome, e-mail, celular e mensagem) que NÃO exige login — calibrado ao vivo
(ago/2026): com os três campos preenchidos, o botão "Enviar Mensagem", que
nasce desabilitado, libera sozinho.

Cuidado que custou investigação: a mesma página tem OUTRO formulário, o de
**financiamento do Banco Pan** (nome, e-mail, celular e **CPF**). É por
isso que nada aqui usa `input[name="name"]` solto — todos os campos são
procurados DENTRO do bloco do vendedor, ancorado no botão "Enviar
Mensagem" (o bloco é o ancestral mais próximo que tem a caixa de texto).
A Mobiauto não pede CPF para falar com o vendedor.

Busca (calibrada ao vivo):
- `/comprar/carros-usados/<uf|brasil>/<marca>[/<modelo>]` — a região é
  segmento de caminho (`/rj/`), e um produto com uma palavra só já funciona
  (vira só a marca);
- cards são `.deal-card`, com título, km, ano e preço no texto — o preço
  vem quebrado em nós diferentes ("R$" e "87.900"), então o texto é
  normalizado antes de casar o número;
- os filtros de preço são aplicados AQUI, lendo o card.
"""
import random
import re
import sys
import time
import unicodedata

from playwright.sync_api import sync_playwright

from coleta import calcular_alvo
from compra_olx import uf_do_cep
from historico import Historico, identificar_vendedor
from navegador import abrir_navegador
from sinal import esperar_prosseguir
from venda.sites.base import (
    detectar_barreira, digitar, dump_diagnostico, fechar_cookies,
    preencher_campo)

HOST = "https://www.mobiauto.com.br"
# /comprar/carros/<uf-cidade>/<marca>/<modelo>/<ano>/<versao>/detalhes/<id>
PADRAO_ANUNCIO = re.compile(
    r"/comprar/carros/([a-z]{2})-([a-z0-9-]+)/[a-z0-9-]+/[a-z0-9-]+/"
    r"(\d{4})/[a-z0-9-]+/detalhes/\d+")

MAX_SCROLLS = 8
PAUSA_SCROLL = 1.5

# o bloco do vendedor: o ancestral mais próximo do botão que contém a
# caixa de mensagem (o de financiamento, com CPF, fica de fora)
XP_BLOCO_VENDEDOR = ('xpath=//button[contains(., "Enviar Mensagem")]'
                     '/ancestor::*[.//textarea][1]')

# lê os anúncios da listagem junto com o preço mostrado no card
JS_CARDS = r"""
() => {
  const padrao = /\/comprar\/carros\/[^\/]+\/[^\/]+\/[^\/]+\/\d{4}\/[^\/]+\/detalhes\/\d+/;
  const saida = {};
  for (const card of document.querySelectorAll('.deal-card')) {
    const href = [...card.querySelectorAll('a[href]')]
      .map(a => a.getAttribute('href') || '')
      .find(h => padrao.test(h));
    if (!href) continue;
    const url = href.split('#')[0].split('?')[0];
    const texto = (card.innerText || '').replace(/\s+/g, ' ').trim();
    const m = texto.match(/R\$\s*([\d.]{4,})/);
    saida[url] = m ? parseInt(m[1].replace(/\./g, ''), 10) : null;
  }
  return saida;
}
"""

# depois de enviar, a Mobiauto troca o formulário por uma confirmação; se
# nada disso aparecer, o bot NÃO diz que enviou (e guarda uma captura)
CONFIRMACOES = (
    "mensagem enviada", "recebemos sua mensagem", "obrigado pelo contato",
    "em breve", "entrará em contato", "enviada com sucesso",
)


def _slug(texto):
    """'Chevrolet Onix' -> 'chevrolet-onix' (sem acento)."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")


def montar_url_busca(produto, uf=""):
    """URL da listagem a partir do texto livre do usuário.

    Primeira palavra é a marca; o resto vira o modelo. Só a marca já
    funciona — a Mobiauto aceita `/carros-usados/rj/chevrolet`.
    """
    partes = [p for p in _slug(produto).split("-") if p]
    if not partes:
        return None
    regiao = uf.lower() if uf else "brasil"
    caminho = "/".join(partes[:2]) if len(partes) > 1 else partes[0]
    return f"{HOST}/comprar/carros-usados/{regiao}/{caminho}"


def pausa_humana(min_seg=1.0, max_seg=2.5):
    time.sleep(random.uniform(min_seg, max_seg))


def coletar_anuncios(pagina, p):
    """Rola a listagem, lê (url, preço) dos cards e filtra por preço."""
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

    links, fora_preco, sem_preco = [], 0, 0
    for caminho, preco in achados.items():
        if not PADRAO_ANUNCIO.search(caminho):
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
        links.append(caminho if caminho.startswith("http") else HOST + caminho)

    if fora_preco:
        print(f"  filtro de preço: {fora_preco} fora da faixa")
    if sem_preco:
        print(f"  {sem_preco} anúncio(s) sem preço legível no card — mantidos")
    return links


def _confirmou_envio(pagina, bloco):
    """True só se a página deu algum sinal de que a mensagem saiu."""
    try:
        texto = (bloco.inner_text() or "").lower()
    except Exception:
        # o bloco sumir da tela também é sinal de que o form foi enviado
        return True
    if any(marca in texto for marca in CONFIRMACOES):
        return True
    try:
        corpo = (pagina.locator("body").inner_text() or "").lower()
    except Exception:
        return False
    return any(marca in corpo for marca in CONFIRMACOES)


def enviar_mensagem_mobiauto(pagina, p, dry_run):
    """Preenche "Fale com o vendedor". True só quando o envio é confirmado."""
    bloco = pagina.locator(XP_BLOCO_VENDEDOR).first
    if bloco.count() == 0:
        print("  ! bloco 'Fale com o vendedor' não encontrado")
        dump_diagnostico(pagina, "mobiauto-compra", "sem-formulario")
        return False

    preencher_campo(pagina, [f'{XP_BLOCO_VENDEDOR} >> input[name="name"]'],
                    p.nome_contato, "Nome")
    preencher_campo(pagina, [f'{XP_BLOCO_VENDEDOR} >> input[name="email"]'],
                    p.email_contato, "E-mail")
    # o celular tem máscara: digitar tecla a tecla, como o site espera
    digitar(pagina, [f'{XP_BLOCO_VENDEDOR} >> input[name="phone"]'],
            p.telefone_contato, "Celular", atraso=60)
    preencher_campo(pagina, [f'{XP_BLOCO_VENDEDOR} >> textarea'],
                    p.mensagem, "Mensagem")
    pagina.wait_for_timeout(1500)

    botao = pagina.locator('button:has-text("Enviar Mensagem")').first
    if not botao.is_enabled():
        print("  ! o botão 'Enviar Mensagem' continuou desabilitado — "
              "algum campo obrigatório não foi aceito")
        dump_diagnostico(pagina, "mobiauto-compra", "botao-desabilitado")
        return False

    if dry_run:
        print("[DRY RUN] Formulário preenchido. Nada será enviado.")
        return False

    botao.click()
    pagina.wait_for_timeout(5000)
    if not _confirmou_envio(pagina, bloco):
        print("  ! a Mobiauto não confirmou o envio — este anúncio NÃO entra "
              "no histórico (a captura em debug/ mostra a tela)")
        dump_diagnostico(pagina, "mobiauto-compra", "envio-sem-confirmacao")
        return False
    return True


def executar(p):
    for saida in (sys.stdout, sys.stderr):
        try:
            saida.reconfigure(errors="replace")
        except Exception:
            pass

    if not (p.nome_contato and p.email_contato and p.telefone_contato):
        print("Mobiauto: preencha Nome, E-mail e Telefone de contato na "
              "interface — o formulário do anúncio exige os três. "
              "(CPF não é usado aqui: quem pede CPF é o formulário de "
              "financiamento, e o bot não mexe nele.)")
        return

    uf = uf_do_cep(p.cep) or ""
    fila = [nome for nome in p.produtos if montar_url_busca(nome, uf)]
    if not fila:
        print("Mobiauto: escreva ao menos um produto (ex.: 'chevrolet onix').")
        return
    if len(fila) > 1:
        print(f"Fila de {len(fila)} produto(s): {', '.join(fila)}")
        if p.quantidade:
            print(f"Até {p.quantidade} anúncio(s) POR PRODUTO.")
    if uf:
        print(f"Mobiauto — região pelo CEP {p.cep}: {uf.upper()}")
    else:
        print("Mobiauto — sem CEP válido: buscando em todo o Brasil.")

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        # o histórico é compartilhado pela fila E entre execuções: nem o
        # mesmo anúncio nem a mesma pessoa recebem mensagem duas vezes
        historico = Historico()

        for posicao, produto in enumerate(fila, start=1):
            # cada veículo tem a SUA margem de preço
            p.usar_produto(produto)
            print(f"Faixa de preço: {p.texto_faixa()}")
            url = montar_url_busca(produto, uf)
            print("")
            print(f"=== produto {posicao}/{len(fila)}: {produto} ===")
            print(f"Mobiauto — busca: {url}")
            pagina.goto(url)
            pagina.wait_for_load_state("domcontentloaded")
            pagina.wait_for_timeout(6000)
            fechar_cookies(pagina)

            barreira = detectar_barreira(pagina)
            if barreira:
                print(f"  ! Mobiauto barrou o acesso ({barreira}).")
                dump_diagnostico(pagina, "mobiauto-compra", "barreira")
                break

            if posicao == 1:
                dump_diagnostico(pagina, "mobiauto-compra", "busca")
            links = historico.novos(coletar_anuncios(pagina, p))

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
                pausa_humana(1, 2)

                if posicao == 1 and i == 0:
                    dump_diagnostico(pagina, "mobiauto-compra", "anuncio")

                # trava por PESSOA: uma loja com vários carros receberia
                # uma mensagem por anúncio sem esta checagem
                vendedor = identificar_vendedor(pagina, "mobiauto")
                bloqueado, motivo = historico.ja_contatado(link, vendedor)
                if bloqueado:
                    print(f"  [pulado] {motivo}")
                    continue

                if enviar_mensagem_mobiauto(pagina, p, p.dry_run):
                    historico.registrar(link, "mobiauto", produto, p.mensagem,
                                        p.cep, vendedor)
                    print("  OK mensagem enviada")
                pausa_humana(4, 9)

        print("Concluído.")
        contexto.close()
