# src/update.py
"""
Auto-update via GitHub Releases.

Fluxo: descobre a última release (redirecionamento de /releases/latest) → compara versões (packaging) → baixa o
setup.exe para %TEMP% → executa o instalador em modo silencioso e encerra
o app (o Inno Setup instala por cima e reinicia o programa).

Regra de ouro: NENHUM erro aqui pode impedir o bot de abrir. Toda função
de rede retorna None em caso de falha e registra em update.log.
"""
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from packaging.version import InvalidVersion, Version

from paths import get_update_log_path

REPO = "Thomas-Geron/marketplace-bot"
# a PÁGINA, não a API: a API sem login aceita só 60 consultas por hora por
# conexão (somadas com tudo o que a rede usa) e o update falhava com 403
URL_LATEST = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 10  # segundos

logger = logging.getLogger("update")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    try:
        _handler = logging.FileHandler(get_update_log_path(), encoding="utf-8")
        _handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(_handler)
    except OSError:
        logger.addHandler(logging.NullHandler())


def get_latest_release():
    """Descobre a release mais recente no GitHub.

    /releases/latest redireciona para /releases/tag/vX.Y.Z; o instalador sai
    do link direto da tag (o download não conta no limite da API).
    Retorna {"version": "X.Y.Z", "url": str, "size": 0} ou None em qualquer
    falha (sem internet, repo sem releases...). size 0 = o download confere
    pelo Content-Length.
    """
    try:
        resp = requests.head(URL_LATEST, timeout=TIMEOUT, allow_redirects=False)
        destino = resp.headers.get("Location", "")
        if "/releases/tag/" not in destino:
            logger.info("releases/latest respondeu %s sem tag", resp.status_code)
            return None
        tag = destino.rsplit("/releases/tag/", 1)[1].strip("/")
        versao = tag.lstrip("vV")

        # preferência: instalador versionado > nome fixo (os dois saem do release.yml)
        for nome in (f"MarketplaceBot-Setup-{versao}.exe", "MarketplaceBot-Setup.exe"):
            url = f"https://github.com/{REPO}/releases/download/{tag}/{nome}"
            if requests.head(url, timeout=TIMEOUT, allow_redirects=False).status_code in (301, 302):
                return {"version": versao, "url": url, "size": 0}
        logger.warning("release %s não tem instalador", versao)
        return None
    except requests.RequestException as exc:
        logger.info("falha ao consultar releases: %s", exc)
        return None


def is_update_available(current: str, latest: str) -> bool:
    """Compara versões semanticamente (1.10.0 > 1.9.0)."""
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        logger.warning("versão inválida: current=%r latest=%r", current, latest)
        return False


def download_installer(url: str, expected_size: int = 0, progresso=None):
    """Baixa o instalador em streaming para %TEMP%.

    `progresso`, se fornecido, é chamado com (bytes_baixados, total).
    Retorna o caminho do .exe ou None em falha.
    """
    destino = Path(tempfile.gettempdir()) / url.rsplit("/", 1)[-1]
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", expected_size) or 0)
            baixado = 0
            with open(destino, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    f.write(chunk)
                    baixado += len(chunk)
                    if progresso:
                        progresso(baixado, total)

        tamanho = destino.stat().st_size
        esperado = expected_size or total
        if esperado and tamanho != esperado:
            logger.error(
                "download corrompido: esperado %s bytes, obtido %s",
                esperado, tamanho,
            )
            destino.unlink(missing_ok=True)
            return None

        logger.info("instalador baixado: %s (%s bytes)", destino, tamanho)
        return str(destino)
    except (requests.RequestException, OSError) as exc:
        logger.error("falha no download: %s", exc)
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def apply_update(installer_path: str) -> None:
    """Dispara o instalador silencioso e encerra o app.

    /RELAUNCH=1 é lido pelo installer.iss para reabrir o programa ao final.
    O processo atual sai imediatamente para liberar os arquivos instalados.
    """
    logger.info("aplicando update: %s", installer_path)
    subprocess.Popen(
        [
            installer_path,
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
            "/RELAUNCH=1",
        ],
        close_fds=True,
    )
    sys.exit(0)


if __name__ == "__main__":  # autoteste contra o GitHub de verdade: cd src && python update.py
    info = get_latest_release()
    print(info)
    assert info and info["url"].endswith(f"MarketplaceBot-Setup-{info['version']}.exe"), info
    assert is_update_available("1.12.3", info["version"]) and not is_update_available(info["version"], info["version"])
    print("update ok")
