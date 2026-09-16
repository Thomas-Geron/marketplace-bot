# src/execucoes.py
"""
Histórico de execuções: cada Rodar (Compra ou Venda) vira um registro em
`execucoes.json` (%LOCALAPPDATA%\\MarketplaceBot), com o log inteiro — é o
que a página Histórico mostra.

O log já é o que a tela exibe: dado sensível não entra nele (senha nunca é
impressa; CPF/telefone saem mascarados pelo bot).
"""
import json
import time
from datetime import datetime

from paths import get_data_dir

LIMITE = 100          # execuções guardadas
LINHAS = 3000         # linhas de log por execução


def _arquivo():
    return get_data_dir() / "execucoes.json"


def carregar():
    """Mais recentes primeiro."""
    try:
        return json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def nova(tipo, sites, veiculos, teste):
    return {"inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "_t0": time.time(), "tipo": tipo, "sites": list(sites),
            "veiculos": list(veiculos), "teste": bool(teste), "log": []}


def linha(execucao, texto):
    if execucao is not None and str(texto).strip() \
            and len(execucao["log"]) < LINHAS:
        execucao["log"].append([time.strftime("%H:%M:%S"), str(texto).rstrip()])


def salvar(execucao, fim):
    """Fecha a execução (`fim`: "concluída" ou "parada") e grava."""
    from ui_execucao import nivel_da_linha

    registro = {k: v for k, v in execucao.items() if k != "_t0"}
    registro["fim"] = fim
    registro["duracao_s"] = round(time.time() - execucao["_t0"])
    niveis = [nivel_da_linha(texto) for _, texto in execucao["log"]]
    registro["contagem"] = {n: niveis.count(n) for n in ("sucesso", "aviso", "erro")}
    try:
        _arquivo().write_text(json.dumps(([registro] + carregar())[:LIMITE],
                                         ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass        # sem gravar, o pior caso é a execução não aparecer no histórico


if __name__ == "__main__":
    import pathlib
    import tempfile

    pasta = pathlib.Path(tempfile.mkdtemp())
    _arquivo = lambda: pasta / "execucoes.json"  # noqa: E731
    for i in range(LIMITE + 2):
        e = nova("Compra", ["facebook"], ["onix"], True)
        linha(e, "OK mensagem enviada")
        linha(e, "   ")
        linha(e, "[erro] timeout")
        linha(e, f"[pulado] {i}")
        salvar(e, "concluída")
    todos = carregar()
    assert len(todos) == LIMITE, len(todos)
    assert todos[0]["log"][-1][1] == f"[pulado] {LIMITE + 1}"      # mais recente 1º
    assert todos[0]["contagem"] == {"sucesso": 1, "aviso": 1, "erro": 1}
    assert len(todos[0]["log"]) == 3 and "_t0" not in todos[0]
    print("ok")
