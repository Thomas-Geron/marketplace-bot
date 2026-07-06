# bot/sinal.py
"""
Ponte simples entre a INTERFACE e o BOT (que são processos separados).
A interface cria um arquivo-sinal; o bot espera esse arquivo aparecer.
Isso substitui o input()/ENTER do terminal por um botão na interface.
"""
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_SINAL = os.path.join(BASE, "prosseguir.signal")


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
