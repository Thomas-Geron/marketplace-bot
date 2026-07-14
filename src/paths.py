# src/paths.py
"""
Resolução centralizada de caminhos do MarketplaceBot.

Dados do usuário (parâmetros, histórico, perfil do navegador, arquivo de
sinal e logs) vivem em %LOCALAPPDATA%\\MarketplaceBot — nunca no diretório
de instalação, que não é gravável dentro de Program Files. É isso que
garante que updates e desinstalações nunca toquem nos dados do usuário.

Recursos empacotados (assets) são resolvidos tanto em desenvolvimento
quanto congelado pelo PyInstaller (sys.frozen / sys._MEIPASS).
"""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "MarketplaceBot"

# True quando rodando o executável congelado pelo PyInstaller
IS_FROZEN = bool(getattr(sys, "frozen", False))

# Pastas de cache do Chrome que não precisam ser migradas (são regeneradas)
_CACHES_CHROME = (
    "Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache",
    "DawnGraphiteCache", "DawnWebGPUCache", "GPUPersistentCache",
    "component_crx_cache", "extensions_crx_cache",
)


def get_data_dir() -> Path:
    """Diretório de dados do usuário. Cria se não existir."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    data_dir = Path(base) / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_resource_dir() -> Path:
    """Raiz dos recursos empacotados (ex.: assets/)."""
    if IS_FROZEN:
        # No modo onedir o PyInstaller expõe a pasta _internal em sys._MEIPASS
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # Em desenvolvimento, a raiz do repositório (pai de src/)
    return Path(__file__).resolve().parent.parent


def get_parametros_path() -> Path:
    return get_data_dir() / "parametros.json"


def get_visitados_path() -> Path:
    return get_data_dir() / "visitados.json"


def get_perfil_dir() -> Path:
    return get_data_dir() / "perfil_bot"


def get_sinal_path() -> Path:
    return get_data_dir() / "prosseguir.signal"


def get_update_log_path() -> Path:
    return get_data_dir() / "update.log"


def get_parametros_venda_path() -> Path:
    return get_data_dir() / "parametros_venda.json"


def get_anunciados_path() -> Path:
    """Registro de (veículo × site) já anunciados — trava anti-spam."""
    return get_data_dir() / "anunciados.json"


def get_sessao_venda_path() -> Path:
    """Sessão salva do Supabase (refresh token) do módulo de venda."""
    return get_data_dir() / "sessao_venda.json"


def get_bot_command(flag: str = "--run-bot") -> list:
    """Comando que a interface usa para iniciar o processo do bot.

    Congelado: o próprio executável com a flag pedida.
    Em desenvolvimento: o interpretador atual rodando main.py com a flag.
    """
    if IS_FROZEN:
        return [sys.executable, flag]
    main_py = Path(__file__).resolve().parent / "main.py"
    return [sys.executable, "-u", str(main_py), flag]


def get_venda_command() -> list:
    """Comando que a interface usa para iniciar o bot de anúncios."""
    return get_bot_command("--run-venda")


def _dirs_legados() -> list:
    """Locais onde versões antigas guardavam os dados (ao lado do código)."""
    if IS_FROZEN:
        return [Path(sys.executable).resolve().parent]
    src = Path(__file__).resolve().parent
    return [src, src.parent / "bot"]  # src/ e o layout antigo bot/


def migrar_dados_antigos() -> None:
    """Copia dados de versões antigas para o data dir, uma única vez.

    Nunca apaga os originais e nunca sobrescreve dados já migrados.
    Qualquer falha aqui não pode impedir o app de abrir.
    """
    data_dir = get_data_dir()
    for legado in _dirs_legados():
        if legado == data_dir or not legado.is_dir():
            continue
        for nome in ("parametros.json", "visitados.json"):
            antigo = legado / nome
            novo = data_dir / nome
            try:
                if antigo.is_file() and not novo.exists():
                    shutil.copy2(antigo, novo)
            except OSError:
                pass
        perfil_antigo = legado / "perfil_bot"
        perfil_novo = get_perfil_dir()
        try:
            if perfil_antigo.is_dir() and not perfil_novo.exists():
                shutil.copytree(
                    perfil_antigo, perfil_novo,
                    ignore=shutil.ignore_patterns(*_CACHES_CHROME),
                )
        except OSError:
            pass
