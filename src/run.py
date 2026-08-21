# bot/run.py
import json
import random
import time
from playwright.sync_api import sync_playwright
from datetime import datetime

import config
import contato
from parametros import Parametros, so_numeros, validar
from navegador import abrir_navegador
from filtros import pesquisar_produto, aplicar_localizacao, aplicar_preco
from coleta import (carregar_todos, calcular_alvo, coletar_links, carregar_visitados,salvar_visitados
)
from mensagem import enviar_mensagem
from sinal import esperar_prosseguir
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

    # cada fonte que não é o Facebook roda em módulo próprio — o fluxo do
    # Facebook abaixo fica intacto
    site = getattr(p, "site", "facebook")
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

        visitados = carregar_visitados()
        urls_visitadas = {item["url"] for item in visitados}

        for posicao, produto in enumerate(fila, start=1):
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

            carregar_todos(pagina)

            links = coletar_links(pagina)

            links = [
                link
                for link in links
                if link not in urls_visitadas
            ]

            total = len(links)

            alvo = calcular_alvo(total, p.quantidade)


            print(f"Encontrados {total} posts. Vou processar {alvo}.")
            pause(2)
            print("Garantindo início da lista...")

            # tenta resetar scroll principal
            pagina.evaluate("window.scrollTo(0, 0)")
            pagina.wait_for_timeout(1000)

            # força scroll extremo para cima várias vezes (UI tipo Facebook precisa disso)
            for _ in range(3):
                pagina.mouse.wheel(0, -5000)
                pagina.wait_for_timeout(800)


            for i, link in enumerate(links[:alvo]):

                print(f"[{i+1}/{alvo}] abrindo post...")

                pagina.goto(link)

                pagina.wait_for_load_state("domcontentloaded")

                pausa_humana(1, 2)

                enviar_mensagem(pagina, p.mensagem, p.dry_run)

                if not p.dry_run and link not in urls_visitadas:

                    registro = {
                        "url": link,
                        "produto": produto,
                        "cep": p.cep,
                        "mensagem": p.mensagem,
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    visitados.append(registro)

                    # Atualiza o conjunto para evitar duplicatas na mesma execução
                    urls_visitadas.add(link)

                    salvar_visitados(visitados)



                    pausa_humana(2, 3)

        print("Concluído.")
        contexto.close()

if __name__ == "__main__":
    main()
