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

    print("Procurando botão azul de enviar...")

    botoes = pagina.get_by_role("button", name="Enviar mensagem")

    print("Quantidade de botões:", botoes.count())

    # O último é o botão azul do modal
    botao_enviar = botoes.last

    botao_enviar.wait_for(state="visible")
    time.sleep(1)

    botao_enviar.click()

    print("Mensagem enviada!")


    time.sleep(2)