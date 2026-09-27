"""Confere a licença (plano + pagamento no Giro) sem rede, com servidor falso.
Rodar:  python checar_licenca.py   (abre e fecha janelas sozinho por alguns segundos)"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()   # antes de importar paths
os.environ["MBOT_SEM_ANIMACAO"] = "1"
sys.path.insert(0, str(Path(__file__).parent / "src"))

import requests  # noqa: E402

import interface_principal  # noqa: E402
import licenca  # noqa: E402
import sinal  # noqa: E402
import termo  # noqa: E402
import ui_licenca  # noqa: E402
from paths import get_data_dir  # noqa: E402

falhas = []
LIBERADO = {"liberado": True, "bot": licenca.BOT, "loja": "Loja Teste",
            "plano": "revenda", "situacao": "ativa",
            "acesso_ate": "2026-12-31", "verificar_a_cada_minutos": 30}

# aqui o assunto é a licença: o termo entra aceito (tem teste próprio em
# checar_termo.py)
COPIA = termo._copia_local()
termo.carregar = lambda timeout=6: COPIA
termo.aceito = lambda dados: True

# ------------------------------------------------------------ servidor falso
servidor = {"status": 200, "corpo": LIBERADO, "offline": False}
pedidos = []


class Resposta:
    def __init__(self, status, corpo):
        self.status_code, self._corpo = status, corpo

    def json(self):
        return self._corpo


def fake_get(url, params=None, headers=None, timeout=None, **k):
    pedidos.append({"url": url, "params": params or {}, "headers": headers or {}})
    if servidor["offline"]:
        raise requests.ConnectionError("offline")
    return Resposta(servidor["status"], servidor["corpo"])


requests.get = fake_get


def responder(status, corpo, offline=False):
    servidor.update(status=status, corpo=corpo, offline=offline)


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


def textos(w):
    fora = []
    for x in filhos(w):
        try:
            fora.append(str(x.cget("text")))
        except Exception:
            pass
    return " | ".join(fora)


def com_roteiro(roteiro):
    """Roda `roteiro(janela_da_licenca)` depois do conferir automático."""
    original = ui_licenca.exigir

    def exigir(root, versao_app=""):
        def agir():
            janela = next(w for w in root.winfo_children()
                          if w.winfo_class() == "Toplevel")
            roteiro(janela)
        root.after(900, agir)
        return original(root, versao_app)
    ui_licenca.exigir = exigir
    return original


def fechar_janela(guardar):
    def roteiro(j):
        guardar["texto"] = textos(j)
        next(b for b in filhos(j) if b.winfo_class() == "TButton"
             and "Fechar" in str(b.cget("text"))).invoke()
    return roteiro


def esperar(root, condicao, segundos=6):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite and not condicao():
        root.update()
        time.sleep(0.05)
    return condicao()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    original = ui_licenca.exigir

    print("[consulta ao Giro]")
    try:
        licenca.consultar()
        checar(False, "sem token, não consulta")
    except licenca.Bloqueado as exc:
        checar(exc.motivo == "token" and not pedidos,
               f"sem token: pede o token sem chamar o Giro ({exc})")

    licenca.salvar_token("  tok-123  ")
    dados = licenca.consultar()
    ped = pedidos[-1]
    checar(dados["plano"] == "revenda", "liberado: devolve os dados da loja")
    checar(ped["url"].endswith("/api/bot/licenca")
           and ped["params"]["bot"] == "marketplace_bot"
           and ped["headers"]["Authorization"] == "Bearer tok-123",
           "pede /api/bot/licenca?bot=marketplace_bot com Bearer do token")
    guardado = json.loads((get_data_dir() / "licenca.json").read_text(encoding="utf-8"))
    checar(list(guardado) == ["token"],
           f"nada de licença guardado no computador, só o token ({list(guardado)})")

    for motivo, erro in (("plano", "Seu plano não inclui o MarketplaceBot."),
                         ("pagamento", "Pagamento em atraso. Regularize para usar o bot.")):
        responder(403, {"liberado": False, "motivo": motivo, "erro": erro,
                        "plano_necessario": "revenda"})
        try:
            licenca.consultar()
            checar(False, f"403 {motivo} bloqueia")
        except licenca.Bloqueado as exc:
            checar(exc.motivo == motivo and str(exc) == erro,
                   f"403 {motivo}: mostra o erro do Giro como veio ({exc})")

    responder(403, {"erro": "Aceite o termo de uso dos bots no site.", "termo": "2026-09-01"})
    try:
        licenca.consultar()
        checar(False, "403 termo bloqueia")
    except licenca.Bloqueado as exc:
        checar(exc.motivo == "termo", f"403 com termo: motivo termo ({exc})")

    responder(401, {"erro": "Token do bot inválido."})
    try:
        licenca.consultar()
        checar(False, "401 bloqueia")
    except licenca.Bloqueado as exc:
        checar(exc.motivo == "token" and "inválido" in str(exc),
               f"401: pede o token de novo ({exc})")

    responder(200, LIBERADO, offline=True)
    try:
        licenca.consultar()
        checar(False, "sem internet não libera")
    except licenca.SemResposta as exc:
        checar("Giro" in str(exc), f"sem internet: SemResposta ({exc})")

    checar(licenca.atrasada({**LIBERADO, "situacao": "atrasada"})
           and not licenca.atrasada(LIBERADO), "atrasada() só com situacao atrasada")

    print("[janela: liberado abre, recusado não abre]")
    responder(200, LIBERADO)
    app = interface_principal.App("inicio")
    checar(not app.recusou and app.paginas, "liberado: a janela abre e monta a página")
    checar(app.licenca["loja"] == "Loja Teste", "os dados da licença ficam na App")
    checar("Pagamento vencido" not in textos(app.topo),
           "pagamento em dia: sem faixa de aviso")
    app.fechar()

    responder(200, {**LIBERADO, "situacao": "atrasada"})
    app = interface_principal.App("inicio")
    checar(not app.recusou and "Pagamento vencido" in textos(app.topo),
           "atrasada: abre com a faixa de aviso no topo")
    checar("não é oficial" in app.aviso_riscos.rotulo.cget("text"),
           "o aviso de riscos continua fixo no topo")
    app.fechar()

    for status, corpo, offline, msg in (
            (403, {"liberado": False, "motivo": "plano",
                   "erro": "Seu plano não inclui o MarketplaceBot."}, False,
             "plano sem o bot"),
            (403, {"liberado": False, "motivo": "pagamento",
                   "erro": "Pagamento em atraso. Regularize para usar o bot."}, False,
             "pagamento atrasado"),
            (401, {"erro": "Token do bot inválido."}, False, "token inválido"),
            (200, LIBERADO, True, "sem internet")):
        responder(status, corpo, offline)
        visto = {}
        com_roteiro(fechar_janela(visto))
        app = interface_principal.App("inicio")
        esperado = corpo.get("erro", "Giro")
        checar(app.recusou and not getattr(app, "paginas", None),
               f"{msg}: não monta página nenhuma")
        checar(esperado.split(".")[0] in visto.get("texto", "")
               or "Giro" in visto.get("texto", ""),
               f"{msg}: a janela mostra o motivo ({msg})")
        ui_licenca.exigir = original

    print("[Configurações: trocar o token]")
    responder(200, LIBERADO)
    app = interface_principal.App("config")
    cfg = app.paginas["config"]
    checar(str(cfg.ent_token.cget("show")) == "•" and cfg.var_token.get() == "tok-123",
           "o token aparece escondido, já preenchido")
    cfg.var_mostrar.set(1)
    cfg.ent_token.configure(show="")
    cfg.var_token.set("tok-novo")
    cfg._conferir_licenca()
    checar(licenca.token() == "tok-novo" and "Loja Teste" in cfg.lbl_licenca.cget("text"),
           f"salva e confere o token novo ({cfg.lbl_licenca.cget('text')})")
    responder(403, {"liberado": False, "motivo": "plano",
                    "erro": "Seu plano não inclui o MarketplaceBot."})
    cfg._conferir_licenca()
    checar("plano não inclui" in cfg.lbl_licenca.cget("text"),
           "recusado: mostra o motivo do Giro na página")
    app.fechar()

    print("[durante a execução]")
    responder(200, LIBERADO)
    app = interface_principal.App("compra")
    pagina = app.paginas["compra"]
    vigia = pagina.vigia
    checar(vigia is not None, "a página da Compra tem vigia de licença")

    sinal.limpar_parada()
    responder(403, {"liberado": False, "motivo": "pagamento",
                    "erro": "Pagamento em atraso. Regularize para usar o bot."})
    vigia._conferir()
    checar(esperar(app.root, sinal.parada_pedida),
           "recusado no meio: pede parada (o item atual termina antes)")

    sinal.limpar_parada()
    responder(200, LIBERADO, offline=True)
    vigia._falhando_desde = None
    vigia._conferir()
    esperar(app.root, lambda: False, 1.5)
    checar(not sinal.parada_pedida() and vigia._agendado is not None,
           "falha de rede: tenta de novo em vez de parar na hora")

    vigia._falhando_desde = time.monotonic() - (licenca.MINUTOS_SEM_RESPOSTA + 1) * 60
    vigia._conferir()
    checar(esperar(app.root, sinal.parada_pedida),
           f"sem conferir por {licenca.MINUTOS_SEM_RESPOSTA} min: para")
    vigia.parar()
    sinal.limpar_parada()
    app.fechar()

    print("\nRESULTADO:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S)")
    for f in falhas:
        print(" -", f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
