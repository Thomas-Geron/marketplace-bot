# src/diagnostico_venda.py
"""
Diagnóstico do módulo de venda: por que meus veículos não aparecem?

Uso:  python src/diagnostico_venda.py
Pede e-mail/senha (a senha não é exibida nem sai da sua máquina), faz as
mesmas consultas que o bot faz e mostra a resposta crua de cada etapa.
"""
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from venda import config_venda
from venda.banco import BancoVeiculos


def consultar(descricao, tabela, select, token):
    resp = requests.get(
        f"{config_venda.SUPABASE_URL}/rest/v1/{tabela}",
        params={"select": select, "limit": "5"},
        headers={
            "apikey": config_venda.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
        },
        timeout=15,
    )
    corpo = resp.text
    if len(corpo) > 400:
        corpo = corpo[:400] + "..."
    print(f"\n[{descricao}] HTTP {resp.status_code}")
    print(f"  {corpo}")
    return resp


def main():
    print("=== Diagnóstico do módulo de venda ===")
    print(f"Projeto: {config_venda.SUPABASE_URL}")

    email = input("E-mail da conta: ").strip()
    senha = getpass("Senha (não aparece ao digitar): ")

    banco = BancoVeiculos()
    ok, erro = banco.login(email, senha)
    if not ok:
        print(f"\nFALHA NO LOGIN: {erro}")
        print("Sem login não há o que diagnosticar — confira e-mail/senha.")
        return
    print(f"\nLogin OK como {banco.email}")
    token = banco._access_token

    # 1) a tabela devolve algo para o usuário logado? (sem joins)
    r = consultar("veiculos sem joins", config_venda.TABELA_VEICULOS, "*", token)

    # 2) consulta completa do bot (com joins)
    consultar("consulta completa do bot", config_venda.TABELA_VEICULOS,
              config_venda.SELECT_VEICULOS, token)

    # 3) tabelas dos joins, individualmente
    for tabela in ("marcas", "modelos", "fotos"):
        consultar(f"tabela {tabela}", tabela, "*", token)

    print("\n=== Interpretação ===")
    if r.status_code == 200 and r.text.strip() == "[]":
        print("A tabela 'veiculos' respondeu VAZIO para seu usuário logado.")
        print("Causa mais provável: falta política de RLS de SELECT para")
        print("usuários autenticados (role 'authenticated') na tabela.")
        print("Correção no Supabase (SQL Editor) — veja o SQL sugerido no chat.")
    elif r.status_code in (401, 403):
        print("Permissão negada: o role 'authenticated' não tem GRANT/política.")
    elif r.status_code == 200:
        print("A tabela respondeu dados! Se o bot não os mostra, o problema")
        print("está nos joins ou na normalização — envie esta saída no chat.")
    else:
        print("Resposta inesperada — envie esta saída completa no chat.")


if __name__ == "__main__":
    main()
