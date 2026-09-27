# bot/sinal.py
"""
Ponte simples entre a INTERFACE e o BOT (que são processos separados).
A interface cria um arquivo-sinal; o bot espera esse arquivo aparecer.
Isso substitui o input()/ENTER do terminal por um botão na interface.
"""
import os
import time

from paths import get_data_dir, get_sinal_path

ARQ_SINAL = str(get_sinal_path())


def limpar_sinal():
    """Remove um sinal antigo, pra não 'prosseguir' por engano."""
    try:
        os.remove(ARQ_SINAL)
    except FileNotFoundError:
        pass


def dar_sinal():
    """Chamado pela INTERFACE (botão Prosseguir): cria o arquivo que libera o bot."""
    with open(ARQ_SINAL, "w", encoding="utf-8") as f:
        f.write("go")


def esperar_prosseguir(mensagem="Aguardando o botão 'Prosseguir' na interface..."):
    """Chamado pelo BOT: bloqueia até a interface dar o sinal.
    Faz o papel que o input()/ENTER fazia — mas via botão."""
    limpar_sinal()                       # começa 'não sinalizado'
    print(mensagem)
    while not os.path.exists(ARQ_SINAL):
        time.sleep(0.3)                  # checa ~3x por segundo
    limpar_sinal()                       # consome o sinal
    print("Prosseguindo.")


# ---------------------------------------------------------------- parada
# A interface pede para o bot parar DEPOIS de terminar o item atual (ex.: o
# Giro recusou a licença no meio da execução). Matar o processo na hora
# deixaria anúncio pela metade no site.
ARQ_PARADA = str(get_data_dir() / "parar.signal")


def limpar_parada():
    try:
        os.remove(ARQ_PARADA)
    except FileNotFoundError:
        pass


def pedir_parada():
    with open(ARQ_PARADA, "w", encoding="utf-8") as f:
        f.write("stop")


def parada_pedida():
    """Chamado pelo BOT entre um item e outro."""
    return os.path.exists(ARQ_PARADA)
