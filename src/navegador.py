# bot/navegador.py
"""
Abertura do navegador usado pelo bot.

Dois modos:

- **chrome** (padrão): Playwright abre o Chrome do sistema com o perfil
  dedicado do bot (`perfil_bot`), onde o login feito uma vez fica salvo.
- **edge**: o Microsoft Edge do computador é iniciado NORMALMENTE, como
  qualquer atalho, e o bot se conecta a ele pelo DevTools (CDP).

Por que o modo edge existe: a OLX barra navegador iniciado pelo
Playwright — ele anuncia que está sob automação (`navigator.webdriver`,
flags de inicialização) e o Cloudflare devolve bloqueio. Iniciado à parte,
o Edge é uma sessão comum de navegador (`navigator.webdriver` é False), e
o bot apenas lê/dirige a página pelo protocolo do DevTools. Nada aqui
mascara identidade nem resolve captcha: se o site pedir verificação, o bot
continua parando e esperando VOCÊ na janela.

O perfil do Edge é próprio do bot (`perfil_edge`), separado do seu Edge
pessoal — assim o bot não mexe nas suas abas nem nas suas sessões.
"""
import os
import socket
import subprocess
import time

from paths import get_data_dir, get_perfil_dir

PASTA_PERFIL = get_perfil_dir()
PORTA_CDP = 9333

_CAMINHOS_EDGE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


class SessaoCDP:
    """Faz um navegador aberto à parte parecer o contexto que o bot já usa.

    O resto do código só chama `new_page()` e `close()`; aqui isso vira,
    respectivamente, uma aba no navegador conectado e o encerramento da
    conexão + do processo que o bot iniciou.
    """

    def __init__(self, navegador, contexto, processo):
        self._navegador = navegador
        self._contexto = contexto
        self._processo = processo

    @property
    def pages(self):
        return self._contexto.pages

    def new_page(self):
        return self._contexto.new_page()

    def close(self):
        try:
            self._navegador.close()
        except Exception:
            pass
        if self._processo is not None:
            try:
                self._processo.terminate()
            except Exception:
                pass


def _porta_aberta(porta):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def _caminho_edge():
    for caminho in _CAMINHOS_EDGE:
        if os.path.isfile(caminho):
            return caminho
    return None


def _abrir_edge(pw):
    """Sobe o Edge do computador e conecta o bot nele pelo DevTools."""
    executavel = _caminho_edge()
    if executavel is None:
        raise RuntimeError(
            "Microsoft Edge não encontrado nos caminhos padrão. Instale o "
            "Edge ou escolha outro site na interface.")

    processo = None
    if not _porta_aberta(PORTA_CDP):
        perfil = get_data_dir() / "perfil_edge"
        perfil.mkdir(parents=True, exist_ok=True)
        print(f"Abrindo o Microsoft Edge (perfil do bot: {perfil})")
        processo = subprocess.Popen([
            executavel,
            f"--remote-debugging-port={PORTA_CDP}",
            f"--user-data-dir={perfil}",
            "--no-first-run",
            "--no-default-browser-check",
        ])
        for _ in range(40):
            if _porta_aberta(PORTA_CDP):
                break
            time.sleep(0.5)
        time.sleep(3)   # o Edge ainda está montando a primeira aba

    if not _porta_aberta(PORTA_CDP):
        raise RuntimeError(
            f"o Edge não respondeu na porta {PORTA_CDP}. Feche o Edge e "
            "tente de novo.")

    navegador = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PORTA_CDP}")
    contexto = navegador.contexts[0] if navegador.contexts else None
    if contexto is None:
        raise RuntimeError("o Edge abriu sem contexto — tente de novo.")

    pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
    return SessaoCDP(navegador, contexto, processo), pagina


def abrir_navegador(pw, navegador="chrome"):
    """Devolve (contexto, pagina). `navegador`: 'chrome' ou 'edge'."""
    if navegador == "edge":
        return _abrir_edge(pw)

    contexto = pw.chromium.launch_persistent_context(
        user_data_dir=str(PASTA_PERFIL),
        channel="chrome",
        headless=False,
    )

    pagina = contexto.new_page()
    return contexto, pagina
