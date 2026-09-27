# src/licenca.py
"""
Licença: o MarketplaceBot só funciona para loja com plano que INCLUA o bot
(hoje, o plano Revenda) e com pagamento em dia. Quem decide é o Giro:

  GET {GIRO_URL}/api/bot/licenca?bot=marketplace_bot
  Authorization: Bearer <token da loja>   (a loja gera no site em Bot)

Nada de licença fica guardado no computador — só o token. Sem conseguir
conferir (sem internet, Giro fora do ar) o bot NÃO inicia: é a regra do
produto, valendo para todo bot do Giro.

`situacao == "atrasada"` é pagamento vencido ainda na carência: funciona,
com aviso. Recusa no meio da execução para o bot (ver `Vigia`).
"""
import json
import threading

import requests

from paths import get_data_dir
from termo import GIRO_URL

BOT = "marketplace_bot"
PAGINA_TOKEN = f"{GIRO_URL}/admin/bot"
PAGINA_PLANO = f"{GIRO_URL}/admin/plano"
MINUTOS_PADRAO = 30
MINUTOS_SEM_RESPOSTA = 10     # falha de rede durante a execução: tenta por 10 min


class Bloqueado(Exception):
    """O Giro recusou (plano, pagamento, termo ou token). Repetir não resolve."""

    def __init__(self, mensagem, motivo=""):
        super().__init__(mensagem)
        self.motivo = motivo


class SemResposta(Exception):
    """Não deu para conferir. Sem conferir, o bot não roda."""


def _arquivo():
    return get_data_dir() / "licenca.json"


def token():
    try:
        return json.loads(_arquivo().read_text(encoding="utf-8")).get("token", "")
    except (OSError, ValueError):
        return ""


def salvar_token(valor):
    _arquivo().write_text(json.dumps({"token": (valor or "").strip()}),
                          encoding="utf-8")


def consultar(timeout=15):
    """Dados da licença quando liberada; senão levanta Bloqueado/SemResposta."""
    chave = token()
    if not chave:
        raise Bloqueado("Cole o token da sua loja para usar o bot.", "token")
    try:
        resposta = requests.get(
            f"{GIRO_URL}/api/bot/licenca", params={"bot": BOT},
            headers={"Authorization": f"Bearer {chave}"}, timeout=timeout)
    except requests.RequestException as exc:
        raise SemResposta(f"Não deu para falar com o Giro: {exc}") from exc
    try:
        dados = resposta.json() or {}
    except ValueError:
        dados = {}
    if resposta.status_code == 200 and dados.get("liberado"):
        return dados
    if resposta.status_code in (401, 403):
        motivo = dados.get("motivo") or ("termo" if dados.get("termo") else
                                         "token" if resposta.status_code == 401 else "")
        raise Bloqueado(dados.get("erro") or "O Giro não liberou o bot.", motivo)
    raise SemResposta(dados.get("erro")
                      or f"O Giro respondeu HTTP {resposta.status_code}.")


def atrasada(dados):
    return bool(dados) and dados.get("situacao") == "atrasada"


class Vigia:
    """Confere a licença de tempos em tempos ENQUANTO o bot roda.

    A consulta vai numa thread (o Tk não pode travar) e o resultado é lido
    pela thread principal. Recusa → `ao_bloquear(motivo)`. Falha de rede →
    tenta de novo por até 10 minutos e só então bloqueia.
    """

    def __init__(self, root, ao_bloquear):
        self.root, self.ao_bloquear = root, ao_bloquear
        self.minutos = MINUTOS_PADRAO
        self._agendado = None
        self._falhando_desde = None

    def iniciar(self, minutos=None):
        self.minutos = minutos or MINUTOS_PADRAO
        self._falhando_desde = None
        self._agendar(self.minutos)

    def parar(self):
        if self._agendado is not None:
            try:
                self.root.after_cancel(self._agendado)
            except Exception:
                pass
            self._agendado = None

    def _agendar(self, minutos):
        self.parar()
        self._agendado = self.root.after(int(minutos * 60_000), self._conferir)

    def _conferir(self):
        self._agendado = None
        resultado = {}

        def consultar_fora_do_tk():
            try:
                resultado["dados"] = consultar()
            except Bloqueado as exc:
                resultado["bloqueado"] = str(exc)
            except SemResposta as exc:
                resultado["sem_resposta"] = str(exc)

        threading.Thread(target=consultar_fora_do_tk, daemon=True).start()
        self._esperar(resultado)

    def _esperar(self, resultado):
        if not resultado:
            self._agendado = self.root.after(200, lambda: self._esperar(resultado))
            return
        self._agendado = None
        if "bloqueado" in resultado:
            self.ao_bloquear(resultado["bloqueado"])
            return
        if "sem_resposta" in resultado:
            import time
            agora = time.monotonic()
            self._falhando_desde = self._falhando_desde or agora
            if agora - self._falhando_desde >= MINUTOS_SEM_RESPOSTA * 60:
                self.ao_bloquear(f"{resultado['sem_resposta']} "
                                 f"(sem conferir há {MINUTOS_SEM_RESPOSTA} minutos)")
                return
            self._agendar(1)
            return
        self._falhando_desde = None
        self._agendar(resultado["dados"].get("verificar_a_cada_minutos")
                      or MINUTOS_PADRAO)
