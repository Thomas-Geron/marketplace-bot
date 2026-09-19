# bot/run.py
import json
import random
import time
from playwright.sync_api import sync_playwright

import config
import contato
from parametros import Parametros, so_numeros, validar
from navegador import abrir_navegador
from filtros import pesquisar_produto, aplicar_localizacao, aplicar_preco
from coleta import calcular_alvo, coletar_links, titulo_do_anuncio
from historico import Historico, identificar_vendedor
from marcas import cita_modelo, palavra_do_modelo
from limites import detectar_limite
from mensagem import enviar_mensagem
from sinal import esperar_prosseguir
from venda.sites.base import dump_diagnostico, texto_da_pagina
from paths import get_parametros_path

DEBUG = True

def pause(sec=2):
    if DEBUG:
        time.sleep(sec)


def carregar_parametros(caminho=None):
    if caminho is None:
        caminho = get_parametros_path()
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    pessoais = contato.do_ambiente()

    return Parametros(
        produto=dados.get("produto", ""),
        # fila de produtos: o bot faz um nome por vez, do começo ao fim
        produtos=dados.get("produtos") or [],
        cep=dados["cep"],  # agora será normalizado automaticamente
        raio_km=int(dados["raio_km"]),
        mensagem=dados["mensagem"],
        preco_min=so_numeros(dados.get("preco_min")),
        preco_max=so_numeros(dados.get("preco_max")),
        quantidade=so_numeros(dados.get("quantidade")),
        dry_run=dados.get("dry_run", True),
        site=dados.get("site", "facebook"),
        # a interface manda a lista; parametros.json antigo tem só `site`
        sites=dados.get("sites") or [],
        # faixa de preço por veículo (vazio = usa o preço padrão da tela)
        faixas=dados.get("faixas") or [],
        # palavras que fazem o bot pular o anúncio (busca inteira)
        ignorar_palavras=dados.get("ignorar_palavras", ""),
        ano_min=so_numeros(dados.get("ano_min")),
        ano_max=so_numeros(dados.get("ano_max")),
        km_max=so_numeros(dados.get("km_max")),
        cambio=dados.get("cambio", ""),
        # dados pessoais NÃO vêm do JSON: a interface passa em variáveis de
        # ambiente, que morrem com este processo (ver src/contato.py)
        nome_contato=pessoais["nome"],
        email_contato=pessoais["email"],
        telefone_contato=pessoais["telefone"],
        cpf_contato=pessoais["cpf"],
    )


def pausa_humana(min_seg=0.5, max_seg=1.2):
    time.sleep(random.uniform(min_seg, max_seg))


def main():
    try:
        _executar()
    finally:
        # dados sensíveis não sobrevivem ao fim da execução
        contato.limpar_ambiente()


def _executar():
    p = carregar_parametros()

    erros = validar(p)
    if erros:
        print("Não dá pra rodar. Corrija:")
        for e in erros:
            print(" -", e)
        return

    # a interface pode mandar VÁRIAS fontes: o bot faz uma de cada vez, na
    # mesma execução, cada uma com a sua janela de navegador. Erro em uma
    # não derruba as outras.
    sites = list(getattr(p, "sites", None) or [getattr(p, "site", "facebook")])
    if len(sites) > 1:
        print(f"{len(sites)} fontes nesta execução: {', '.join(sites)}")
    for posicao, site in enumerate(sites, start=1):
        if len(sites) > 1:
            print("")
            print(f"########## fonte {posicao}/{len(sites)}: {site} ##########")
        try:
            _executar_site(site, p)
        except Exception as exc:
            print(f"[erro] a fonte {site} parou: {exc}")
            print("       As demais fontes desta execução seguem.")


def _executar_site(site, p):
    """Roda UMA fonte. Cada módulo abre e fecha o próprio navegador."""
    # cada fonte que não é o Facebook roda em módulo próprio — o fluxo do
    # Facebook abaixo fica intacto
    if site == "olx":
        from compra_olx import executar
        executar(p)
        return
    if site == "icarros":
        from compra_icarros import executar
        executar(p)
        return
    if site == "webmotors":
        from compra_webmotors import executar
        executar(p)
        return
    if site == "mobiauto":
        from compra_mobiauto import executar
        executar(p)
        return
    if site == "napista":
        from compra_napista import executar
        executar(p)
        return
    if site == "leiloes":
        from compra_leiloes import executar
        executar(p)
        return

    fila = p.produtos
    if len(fila) > 1:
        print(f"Fila de {len(fila)} produto(s): {', '.join(fila)}")
        if p.quantidade:
            print(f"Até {p.quantidade} anúncio(s) POR PRODUTO.")

    with sync_playwright() as pw:
        contexto, pagina = abrir_navegador(pw)
        pagina.set_default_timeout(120000)

        pagina.goto(config.URL_BUSCA)

        esperar_prosseguir("Faça o login no navegador e clique em 'Prosseguir'.")
        pause(3)

        historico = Historico()

        for posicao, produto in enumerate(fila, start=1):
            # cada veículo tem a SUA margem de preço
            p.usar_produto(produto)
            if len(fila) > 1:
                print(f"\n=== produto {posicao}/{len(fila)}: {produto} ===")

            if posicao > 1:
                # depois do último anúncio a página está na tela do post;
                # volta para a busca antes de procurar o próximo nome
                pagina.goto(config.URL_BUSCA)
                pause(3)

            print("Iniciando filtros...")
            pause(2)

            pesquisar_produto(pagina, produto)
            pause(3)

            if posicao == 1:
                # a localização é um filtro global do Marketplace: vale para
                # as buscas seguintes, e reabrir o modal a cada produto só
                # aumentaria a chance de falhar
                aplicar_localizacao(pagina, p.cep, p.raio_km)
                pause(3)

            aplicar_preco(pagina, p.preco_min, p.preco_max)
            pause(3)

            # rola do topo ao fim anotando os cards na ordem da tela (o
            # Marketplace descarta os do topo quando a lista rola)
            links = coletar_links(pagina, produto=produto,
                                  bastam=p.quantidade,
                                  pular=historico.urls)

            antes = len(links)
            links = historico.novos(links)
            if antes > len(links):
                print(f"  {antes - len(links)} anúncio(s) já receberam mensagem "
                      "antes e foram pulados")

            total = len(links)

            alvo = calcular_alvo(total, p.quantidade)


            print(f"Encontrados {total} posts. Vou processar {alvo}.")
            pause(2)

            for i, link in enumerate(links[:alvo]):

                print(f"[{i+1}/{alvo}] abrindo post...")

                pagina.goto(link)

                pagina.wait_for_load_state("domcontentloaded")

                pausa_humana(1, 2)

                # trava por PESSOA: o mesmo anunciante com vários carros
                # receberia uma mensagem por anúncio sem esta checagem
                vendedor = identificar_vendedor(pagina, "facebook")
                bloqueado, motivo = historico.ja_contatado(link, vendedor)
                if bloqueado:
                    print(f"    [pulado] {motivo}")
                    continue

                # o título tem de falar no modelo pedido: a busca do
                # Marketplace mistura outros carros (a BMW no meio dos Gols)
                titulo = titulo_do_anuncio(pagina)
                if not cita_modelo(titulo, produto):
                    print(f"    [pulado] o título não fala em "
                          f"'{palavra_do_modelo(produto)}': {titulo[:70]}")
                    continue

                # peneira por palavras: o que o veículo da vez exige e o
                # que a busca inteira recusa
                serve, motivo = p.anuncio_serve(texto_da_pagina(pagina))
                if not serve:
                    print(f"    [pulado] {motivo}")
                    continue

                enviar_mensagem(pagina, p.mensagem, p.dry_run)

                # o Facebook corta o envio depois de algumas mensagens e
                # avisa na tela; daí em diante toda tentativa é perdida —
                # o bot para no Marketplace em vez de insistir
                # a caixa do aviso aparece depois do clique: espera um pouco
                aviso = detectar_limite(pagina, ignorar=p.mensagem, espera=4)
                if aviso:
                    print("")
                    print("O Facebook limitou o envio de mensagens desta "
                          "conta:")
                    print(f'  "{aviso}"')
                    print("Parando o Marketplace por aqui. Tente de novo mais "
                          "tarde — insistir agora só prejudica a conta.")
                    dump_diagnostico(pagina, "facebook-compra",
                                     "limite-de-mensagens")
                    contexto.close()
                    return

                if not p.dry_run:
                    historico.registrar(link, "facebook", produto, p.mensagem,
                                        p.cep, vendedor)

                    pausa_humana(2, 3)

        print("Concluído.")
        contexto.close()

if __name__ == "__main__":
    main()
