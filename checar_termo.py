"""Confere o termo de riscos da janela principal (pasta de dados temporária, sem rede).
Rodar:  python checar_termo.py   (abre e fecha janelas sozinho por alguns segundos)"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()   # antes de importar paths
os.environ["MBOT_SEM_ANIMACAO"] = "1"
sys.path.insert(0, str(Path(__file__).parent / "src"))

import requests  # noqa: E402

import interface_principal  # noqa: E402
import termo  # noqa: E402
import ui_termo  # noqa: E402
from paths import get_data_dir  # noqa: E402

falhas = []
COPIA = termo._copia_local()


def checar(cond, msg):
    print(("  OK   " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def filhos(w):
    fila, todos = [w], []
    while fila:
        x = fila.pop()
        fila.extend(x.winfo_children())
        todos.append(x)
    return todos


def com_roteiro(roteiro):
    """Roda `roteiro(janela_do_termo)` quando o termo abrir — testa a janela de verdade."""
    original = ui_termo.exigir_aceite

    def exigir(root, dados, versao):
        def agir():
            termo_janela = next(w for w in root.winfo_children() if w.winfo_class() == "Toplevel")
            roteiro(termo_janela)
        root.after(500, agir)
        return original(root, dados, versao)
    ui_termo.exigir_aceite = exigir
    return original


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    print("[sem internet: vale a cópia empacotada]")
    real_get = requests.get
    requests.get = lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("offline"))
    checar(termo.carregar()["versao"] == COPIA["versao"], "sem conexão, usa assets/termo.json")
    requests.get = real_get
    termo.carregar = lambda timeout=6: COPIA   # daqui em diante, sem rede

    print("[primeira abertura: termo antes de tudo]")
    passos = {}

    def aceitar(j):
        caixas = [w for w in filhos(j) if w.winfo_class() == "Checkbutton"]
        entrada = next(w for w in filhos(j) if w.winfo_class() == "TEntry")
        botoes = [w for w in filhos(j) if w.winfo_class() == "TButton"]
        aceito = next(b for b in botoes if str(b.cget("text")).startswith("Li,"))
        passos["janela_principal_escondida"] = not j.master.winfo_viewable()
        passos["inicio"] = str(aceito.cget("state"))
        for c in caixas[:-1]:
            c.invoke()
        entrada.insert(0, "Maria Silva")
        j.update()
        passos["falta_caixa"] = str(aceito.cget("state"))
        caixas[-1].invoke()
        entrada.delete(0, "end"); entrada.insert(0, "Maria")
        j.update()
        passos["sem_sobrenome"] = str(aceito.cget("state"))
        entrada.delete(0, "end"); entrada.insert(0, "Maria Silva")
        j.update()
        passos["pronto"] = str(aceito.cget("state"))
        passos["caixas"] = len(caixas)
        aceito.invoke()

    original = com_roteiro(aceitar)
    app = interface_principal.App("inicio")
    checar(passos.get("janela_principal_escondida"), "a janela principal fica escondida enquanto o termo está aberto")
    checar(passos.get("caixas") == len(COPIA["declaracoes"]), f"uma caixa por declaração ({passos.get('caixas')})")
    checar(passos.get("inicio") == "disabled", "o botão de aceitar começa desligado")
    checar(passos.get("falta_caixa") == "disabled", "com uma declaração sem marcar, continua desligado")
    checar(passos.get("sem_sobrenome") == "disabled", "sem sobrenome, continua desligado")
    checar(passos.get("pronto") == "normal", "tudo marcado e nome completo: liga")
    checar(not app.recusou and app.root.winfo_exists(), "aceitou: a janela principal abre")
    salvo = json.loads((get_data_dir() / "termo_aceite.json").read_text(encoding="utf-8"))
    checar(salvo["versao"] == COPIA["versao"] and salvo["nome"] == "Maria Silva" and salvo["aceito_em"],
           f"aceite gravado com versão, nome e data ({salvo['versao']}, {salvo['nome']})")
    checar(app.aviso_riscos.winfo_manager() == "grid" and "não é oficial" in app.aviso_riscos.rotulo.cget("text"),
           "aviso de riscos fixo no topo")
    clicaveis = [w for w in filhos(app.aviso_riscos) if w.winfo_class() == "Label" and str(w.cget("cursor")) == "hand2"]
    checar(len(clicaveis) == 1 and clicaveis[0].cget("text") == "Ver o termo",
           f"o aviso não tem botão de fechar: o único clicável é o link ({[w.cget('text') for w in clicaveis]})")
    checar(any(w.winfo_class() == "Label" and w.cget("text") == "Ver o termo" for w in filhos(app.aviso_riscos)),
           "o aviso tem o link para ler o termo")
    app.fechar()
    ui_termo.exigir_aceite = original

    print("[segunda abertura: já aceito]")
    chamado = []
    ui_termo.exigir_aceite = lambda *a: chamado.append(1) or True
    app = interface_principal.App("inicio")
    checar(not chamado and not app.recusou, "não pergunta de novo a mesma versão")
    app.fechar()
    ui_termo.exigir_aceite = original

    print("[termo mudou: pergunta de novo; recusar fecha]")
    termo.carregar = lambda timeout=6: {**COPIA, "versao": "versao-nova"}

    def recusar(j):
        next(b for b in filhos(j) if b.winfo_class() == "TButton" and "Não aceito" in str(b.cget("text"))).invoke()

    com_roteiro(recusar)
    app = interface_principal.App("inicio")
    checar(app.recusou, "versão nova recusada: o app fecha sem abrir a janela principal")
    ui_termo.exigir_aceite = original

    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    for f in falhas:
        print(" -", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
