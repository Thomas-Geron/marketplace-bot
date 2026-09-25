# src/termo.py
"""Termo de riscos dos bots de mensagens — o MESMO do site (Giro).

Texto oficial: GET {GIRO_URL}/api/bot/termo. Sem internet, vale a cópia
empacotada em assets/termo.json (gerada desse endpoint a cada release).
O aceite fica em %LOCALAPPDATA%\\MarketplaceBot\\termo_aceite.json; versão nova
do termo = aceitar de novo. Sem aceite, a janela nem deixa usar o bot.
"""
import json
import os
import platform
from datetime import datetime

import requests

from paths import get_data_dir, get_resource_dir

GIRO_URL = "https://revendedora-web.onrender.com"


def _copia_local() -> dict:
    return json.loads((get_resource_dir() / "assets" / "termo.json").read_text(encoding="utf-8"))


def carregar(timeout: float = 6) -> dict:
    """Termo atual do site; sem resposta (offline, site dormindo), a cópia empacotada."""
    try:
        termo = requests.get(f"{GIRO_URL}/api/bot/termo", timeout=timeout).json()
        if termo.get("versao") and termo.get("declaracoes") and termo.get("riscos"):
            return termo
    except (requests.RequestException, ValueError):
        pass
    return _copia_local()


def _arquivo():
    return get_data_dir() / "termo_aceite.json"


def aceito(termo: dict) -> bool:
    try:
        salvo = json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return salvo.get("versao") == termo.get("versao")


def registrar(termo: dict, nome: str, versao_app: str) -> None:
    """Prova local do aceite: quem, quando, em que máquina, qual versão."""
    _arquivo().write_text(json.dumps({
        "versao": termo.get("versao"),
        "nome": nome.strip(),
        "aceito_em": datetime.now().isoformat(timespec="seconds"),
        "computador": platform.node(),
        "usuario_windows": os.environ.get("USERNAME", ""),
        "aplicativo": f"MarketplaceBot {versao_app}",
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def nome_valido(nome: str) -> bool:
    """Nome completo: ao menos duas palavras com duas letras ou mais (regra do site)."""
    return len([p for p in (nome or "").split() if len(p) >= 2]) >= 2


def texto(termo: dict) -> str:
    """Texto corrido do termo, para a janela de leitura."""
    linhas = [termo.get("titulo", ""), f"Versão de {termo.get('versao_legivel', '')}", ""]
    for secao in termo.get("secoes", []):
        lista = secao.get("titulo", "").startswith("2.")
        linhas += [secao.get("titulo", ""), ""]
        linhas += [("•  " if lista else "") + p + "\n" for p in secao.get("paragrafos", [])]
    return "\n".join(linhas).strip()


if __name__ == "__main__":
    assert nome_valido("Maria Silva") and not nome_valido("Maria") and not nome_valido("a b")
    copia = _copia_local()
    assert copia["versao"] and len(copia["declaracoes"]) >= 4 and len(copia["riscos"]) >= 8
    assert "Facebook" in texto(copia), "a cópia precisa falar do Facebook (risco do MarketplaceBot)"
    print("termo ok —", copia["versao"])
