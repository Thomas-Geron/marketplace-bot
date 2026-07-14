# src/venda/anunciados.py
"""
Trava anti-spam: registro de quais veículos já foram anunciados em quais
sites. Cada par (veículo, site) só é anunciado UMA vez — mesmo entre
execuções diferentes. Fica em %LOCALAPPDATA%\\MarketplaceBot\\anunciados.json.
"""
import json
import os
from datetime import datetime

from paths import get_anunciados_path


def carregar():
    caminho = get_anunciados_path()
    if not os.path.exists(caminho):
        return []
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def salvar(registros):
    with open(get_anunciados_path(), "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=4)


def foi_anunciado(veiculo_id, site_id, registros=None):
    registros = carregar() if registros is None else registros
    return any(
        r["veiculo_id"] == str(veiculo_id) and r["site"] == site_id
        for r in registros
    )


def registrar(veiculo_id, site_id, titulo=""):
    """Marca o par (veículo, site) como anunciado. Idempotente."""
    registros = carregar()
    if foi_anunciado(veiculo_id, site_id, registros):
        return
    registros.append({
        "veiculo_id": str(veiculo_id),
        "site": site_id,
        "titulo": titulo,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    salvar(registros)


def sites_do_veiculo(veiculo_id, registros=None):
    """Lista os sites onde o veículo já foi anunciado."""
    registros = carregar() if registros is None else registros
    return sorted(
        r["site"] for r in registros if r["veiculo_id"] == str(veiculo_id)
    )
