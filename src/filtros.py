# bot/filtros.py
import config


def pesquisar_produto(pagina, produto):
    pagina.fill(config.SEL_CAMPO_BUSCA, produto)
    pagina.press(config.SEL_CAMPO_BUSCA, "Enter")

    pagina.wait_for_load_state("domcontentloaded")
    pagina.wait_for_timeout(2000)


def aplicar_localizacao(pagina, cep, raio_km):
    print("1 - Abrindo localização")
    pagina.click(config.SEL_LINK_LOCALIZACAO)

    print("2 - Digitando CEP")
    campo = pagina.locator(config.SEL_CAMPO_CIDADE)
    campo.wait_for(state="visible")
    campo.fill("")
    campo.type(str(cep), delay=80)

    print("3 - Aguardando sugestões aparecerem")
    pagina.wait_for_timeout(1200)

    print("4 - Selecionando primeira sugestão")

    # garante foco no input
    campo.focus()

    # pequena espera pro dropdown estabilizar
    pagina.wait_for_timeout(800)

    # navega e seleciona via teclado (mais confiável nesse tipo de UI)
    pagina.keyboard.press("ArrowDown")
    pagina.wait_for_timeout(200)
    pagina.keyboard.press("Enter")

    # garante aplicação
    pagina.wait_for_timeout(800)
    
    print("5 - Abrindo raio")
    pagina.click(config.SEL_SELECT_RAIO)

    print("6 - Selecionando raio")
    pagina.click(f'text="{raio_km} quilômetros"')

    print("7 - Aplicando filtros")
    pagina.click(config.SEL_BTN_APLICAR_LOC)

    pagina.wait_for_timeout(2500)

def aplicar_preco(pagina, preco_min, preco_max):
    """Preenche preço mínimo e máximo."""

    if preco_min is not None:
        pagina.fill(config.SEL_CAMPO_PRECO_MIN, str(preco_min))

    if preco_max is not None:
        pagina.fill(config.SEL_CAMPO_PRECO_MAX, str(preco_max))
        pagina.press(config.SEL_CAMPO_PRECO_MAX, "Enter")

    pagina.wait_for_selector(config.SEL_CARD_POST)