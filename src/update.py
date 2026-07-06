# src/update.py
"""
Auto-update via GitHub Releases.

Fluxo: consulta /releases/latest → compara versões (packaging) → baixa o
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
URL_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
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
    """Consulta a release mais recente no GitHub.

    Retorna {"version": "X.Y.Z", "url": str, "size": int} ou None em
    qualquer falha (sem internet, rate limit, repo sem releases...).
    """
    try:
        resp = requests.get(
            URL_LATEST,
            timeout=TIMEOUT,
            headers={"Accept": "application/vnd.github+json"},
        )
        if resp.status_code != 200:
            logger.info("releases/latest respondeu %s", resp.status_code)
            return None
        data = resp.json()
        versao = str(data.get("tag_name", "")).lstrip("vV")
        if not versao:
            logger.warning("release sem tag_name: %r", data.get("tag_name"))
            return None

        assets = data.get("assets", [])
        alvo = None
        # preferência: instalador versionado > nome fixo > qualquer setup .exe
        for nome in (f"MarketplaceBot-Setup-{versao}.exe", "MarketplaceBot-Setup.exe"):
            alvo = next((a for a in assets if a.get("name") == nome), None)
            if alvo:
                break
        if alvo is None:
            alvo = next(
                (a for a in assets if str(a.get("name", "")).endswith(".exe")), None
            )
        if alvo is None:
            logger.warning("release %s não tem asset .exe", versao)
            return None

        return {
            "version": versao,
            "url": alvo["browser_download_url"],
            "size": int(alvo.get("size", 0)),
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
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
        if expected_size and tamanho != expected_size:
            logger.error(
                "download corrompido: esperado %s bytes, obtido %s",
                expected_size, tamanho,
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
