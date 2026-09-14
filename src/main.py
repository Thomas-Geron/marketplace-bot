# src/main.py
"""
Entrypoint do MarketplaceBot.

Modos de execução:
  MarketplaceBot.exe                    → checa update e abre o seletor Compra/Venda
  MarketplaceBot.exe --run-bot          → roda o bot de compra (subprocesso da interface)
  MarketplaceBot.exe --run-venda        → roda o bot de anúncios (subprocesso da interface)
  MarketplaceBot.exe --install-browser  → garante o navegador (usado pelo instalador)

Em desenvolvimento: python src/main.py [flags]
"""
import os
import sys


def instalar_navegador() -> int:
    """Garante que o Google Chrome existe (o bot usa channel='chrome').

    Só dispara a instalação via Playwright se o Chrome não for encontrado
    nos locais padrão — o instalador chama isto com privilégios elevados.
    """
    candidatos = [
        os.path.join(
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            "Google", "Chrome", "Application", "chrome.exe",
        ),
        os.path.join(
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            "Google", "Chrome", "Application", "chrome.exe",
        ),
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Google", "Chrome", "Application", "chrome.exe",
        ),
    ]
    if any(c and os.path.isfile(c) for c in candidatos):
        print("Google Chrome já instalado — nada a fazer.")
        return 0

    print("Chrome não encontrado. Instalando via Playwright...")
    try:
        from playwright.__main__ import main as playwright_main

        sys.argv = ["playwright", "install", "chrome"]
        playwright_main()
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # instalador não pode travar por causa disso
        print(f"Falha ao instalar o Chrome: {exc}")
        return 1
    return 0


def _preparar_stdout_sem_buffer() -> None:
    """No exe congelado não existe a flag -u do Python; força flush por
    linha para o log aparecer em tempo real na janela da interface."""
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(line_buffering=True, write_through=True)
        except (AttributeError, OSError, ValueError):
            pass


def checar_atualizacao() -> None:
    """Pergunta e aplica update se houver versão nova. Nunca impede o app
    de abrir: qualquer erro é engolido e registrado em update.log."""
    try:
        import update
        from version import __version__

        info = update.get_latest_release()
        if not info or not update.is_update_available(__version__, info["version"]):
            return

        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        quer = messagebox.askyesno(
            "MarketplaceBot — Atualização",
            f"Nova versão {info['version']} disponível "
            f"(você está na {__version__}).\n\nAtualizar agora?",
            parent=root,
        )
        if not quer:
            root.destroy()
            return

        # progresso do download no mesmo tema das telas (é a primeira
        # janela que o usuário vê numa atualização)
        from tkinter import ttk

        import ui_tema

        root.deiconify()
        root.title("MarketplaceBot")
        ui_tema.aplicar_tema(root)
        ui_tema.geometria(root, 380, 110)
        root.resizable(False, False)
        texto = tk.StringVar(value="Baixando atualização...")
        quadro = ttk.Frame(root, padding=ui_tema.px(root, 20))
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, textvariable=texto).pack(anchor="w")
        barra = ttk.Progressbar(quadro, mode="determinate", maximum=100)
        barra.pack(fill="x", pady=(ui_tema.px(root, 12), 0))

        def progresso(baixado, total):
            if total:
                porcento = baixado * 100 // total
                texto.set(f"Baixando atualização... {porcento}%")
                barra.configure(value=porcento)
            root.update()

        caminho = update.download_installer(info["url"], info["size"], progresso)
        root.destroy()
        if caminho:
            update.apply_update(caminho)  # encerra o processo (sys.exit)
    except Exception:
        try:
            from update import logger

            logger.exception("erro inesperado no fluxo de update")
        except Exception:
            pass


def main() -> None:
    # tratado antes de qualquer outra coisa: usado pelo instalador
    if "--install-browser" in sys.argv:
        sys.exit(instalar_navegador())

    from paths import migrar_dados_antigos

    migrar_dados_antigos()

    if "--run-bot" in sys.argv:
        _preparar_stdout_sem_buffer()
        import run

        run.main()
        return

    if "--run-venda" in sys.argv:
        _preparar_stdout_sem_buffer()
        from venda import anunciador

        anunciador.main()
        return

    # antes de qualquer janela: sem isto o Windows estica as janelas do Tk
    # e a fonte sai borrada (era boa parte da cara de "programa antigo")
    import ui_tema

    ui_tema.preparar_dpi()

    checar_atualizacao()
    import interface_principal

    interface_principal.iniciar()


if __name__ == "__main__":
    main()
