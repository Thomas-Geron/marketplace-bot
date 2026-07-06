# bot/coleta.py
import json
import os
import config
from datetime import datetime


def carregar_todos(pagina):
    """Rola a página até os posts pararem de aparecer. Retorna o total."""
    total_anterior = -1
    for _ in range(config.MAX_SCROLLS):
        total = pagina.locator(config.SEL_CARD_POST).count()
        if total == total_anterior:
            break  # não apareceu nada novo -> chegou no fim da lista
        total_anterior = total
        pagina.mouse.wheel(0, 4000)
        pagina.wait_for_timeout(int(config.PAUSA_SCROLL * 1000))
    return pagina.locator(config.SEL_CARD_POST).count()

def coletar_links(pagina):
    """Retorna uma lista de links únicos dos anúncios."""

    cards = pagina.locator(config.SEL_CARD_POST)

    links = []
    vistos = set()

    for i in range(cards.count()):
        href = cards.nth(i).get_attribute("href")

        if not href:
            continue

        # Converte links relativos em absolutos
        if href.startswith("/"):
            href = "https://www.facebook.com" + href

        if href in vistos:
            continue

        vistos.add(href)
        links.append(href)

    return links

def carregar_visitados():
    """Carrega os anúncios já processados."""

    if not os.path.exists("visitados.json"):
        return []

    try:
        with open("visitados.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def salvar_visitados(visitados):
    """Salva o histórico de anúncios."""

    with open("visitados.json", "w", encoding="utf-8") as f:
        json.dump(
            visitados,
            f,
            ensure_ascii=False,
            indent=4
        )


def calcular_alvo(total, quantidade):
    if quantidade is None:
        return total

    alvo = min(quantidade, total)

    if config.LIMITE_ENVIOS is None:
        return alvo

    return min(alvo, config.LIMITE_ENVIOS)