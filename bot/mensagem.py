# bot/mensagem.py
import config
import time


def enviar_mensagem(pagina, mensagem, dry_run):
    print("Abrindo conversa...")

    # Clica no botão "Enviar mensagem"
    botao = pagina.locator(config.SEL_BTN_ENVIAR_MSG)
    botao.wait_for(state="visible")
    botao.click()

    time.sleep(2)

    print("Aguardando campo de mensagem...")

    campo = pagina.get_by_role("textbox").last
    campo.wait_for(state="visible")

    print("Digitando mensagem...")

    campo.fill(mensagem)

    # Tempo para você visualizar no navegador
    time.sleep(5)

    if dry_run:
        print("[DRY RUN] Mensagem digitada. Não será enviada.")
        return

    print("Enviando mensagem...")
    campo.press("Enter")

    time.sleep(2)