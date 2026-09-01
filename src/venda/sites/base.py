# src/venda/sites/base.py
"""
Contrato genérico de um site de anúncios + helpers de preenchimento.

O anunciador e a interface só conhecem esta classe — todo conhecimento
específico de um site (URLs, seletores, ordem de preenchimento, regras
de fotos) vive apenas no adaptador dele. O login NÃO é automatizado:
o anunciador abre a home do site e o usuário loga manualmente antes de
clicar em 'Prosseguir' (mesmo mecanismo do bot de compra).

Os helpers abaixo são tolerantes a falha de propósito: sites reais mudam
de HTML, então cada campo tenta uma lista de seletores candidatos e, se
nenhum funcionar, o bot AVISA no log e segue — o navegador fica visível
para o usuário completar/revisar o que faltou.
"""
import tempfile
from datetime import datetime
from pathlib import Path

import requests

import contato
from paths import get_data_dir


def fechar_cookies(pagina):
    """Fecha o banner de cookies, que costuma cobrir a página e engolir
    cliques (a Kavak usa OneTrust, que bloqueia o funil inteiro)."""
    candidatos = [
        "#onetrust-accept-btn-handler",
        "#accept-recommended-btn-handler",
        ".save-preference-btn-handler",
        'button:has-text("Aceitar todos")',
        'button:has-text("Permitir todos")',
        'button:has-text("Aceitar")',
        'button:has-text("Concordo")',
        'button:has-text("Entendi")',
    ]
    for sel in candidatos:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.click(timeout=5000)
            pagina.wait_for_timeout(1200)
            print("  OK banner de cookies fechado")
            return True
        except Exception:
            continue
    return False


# páginas de login/bloqueio: o bot não tenta contornar, só avisa e para
_BARREIRAS_URL = (
    ("accounts.icarros.com", "login do iCarros"),
    ("auth.napista.com.br", "login da NaPista"),
    ("/login", "tela de login"),
    ("openid-connect/auth", "tela de login"),
)
# distinguir os dois casos importa: o desafio o usuário resolve na janela;
# o bloqueio de firewall (Cloudflare 1020) não tem nada para resolver
_BARREIRAS_TEXTO = (
    ("you have been blocked", "bloqueio de firewall (Cloudflare)"),
    ("unable to access", "bloqueio de firewall (Cloudflare)"),
    ("acesso negado", "acesso negado pelo site"),
    ("verifique que você é humano", "verificação antibot"),
    ("verify you are human", "verificação antibot"),
    ("just a moment", "verificação antibot"),
)


def detectar_barreira(pagina):
    """Se a página for login ou bloqueio antibot, devolve o motivo (str);
    senão, None. Serve para o bot parar com uma mensagem clara em vez de
    tentar preencher campos que não existem."""
    try:
        url = (pagina.url or "").lower()
    except Exception:
        return None
    for marca, motivo in _BARREIRAS_URL:
        if marca in url:
            return motivo
    try:
        corpo = (pagina.locator("body").inner_text(timeout=5000) or "").lower()
    except Exception:
        return None
    for marca, motivo in _BARREIRAS_TEXTO:
        if marca in corpo:
            return motivo
    return None


# desafio "Pressione e segure" (Akamai/PerimeterX, usado pela Webmotors):
# é resolvido por VOCÊ na janela — o bot só reconhece, espera e confere
_DESAFIO_HUMANO = (
    "press & hold",
    "press and hold",
    "pressione e segure",
    "access to this page has been denied",
    "acesso a esta página foi negado",
)


def desafio_humano(pagina):
    """True se a página é um desafio de 'pressione e segure'."""
    try:
        corpo = (pagina.locator("body").inner_text(timeout=5000) or "").lower()
    except Exception:
        return False
    return any(marca in corpo for marca in _DESAFIO_HUMANO)


def esperar_desafio_humano(pagina, minutos=5, passo=3):
    """Pausa até VOCÊ concluir o 'Pressione e segure' na janela aberta.

    O bot não resolve nem contorna o desafio: ele reconhece, avisa, espera
    a página deixar de ser o desafio e então segue. Retorna True se
    liberou dentro do tempo.
    """
    if not desafio_humano(pagina):
        return True
    print("  ! Verificação 'Pressione e segure' na tela.")
    print("    RESOLVA na janela do navegador — o bot está esperando e "
          f"continua sozinho assim que passar (limite: {minutos} min).")
    for gasto in range(0, minutos * 60, passo):
        pagina.wait_for_timeout(passo * 1000)
        if not desafio_humano(pagina):
            print(f"  OK verificação concluída em ~{gasto + passo}s — seguindo.")
            return True
    print(f"  ! verificação não concluída em {minutos} min — parando por aqui.")
    return False


def tentar_login(pagina, site_id):
    """Preenche a tela de login do site com as credenciais que o usuário
    digitou na interface (memória do processo, nunca disco).

    Não substitui o login manual: sites com 2FA, captcha ou fluxo em duas
    etapas continuam exigindo você na janela. Retorna True se o formulário
    foi enviado e a barreira sumiu.
    """
    acesso = contato.login_do_ambiente(site_id)
    if not acesso:
        return False

    print(f"  tentando login em {site_id} como "
          f"{contato.mascarar(acesso['usuario'])}")
    usuario_ok = preencher_campo(pagina, [
        'input[name="username"]', 'input[name="email"]',
        'input[type="email"]', 'input[id*="user" i]',
        'input[id*="email" i]',
    ], acesso["usuario"], "usuário")
    senha_ok = _preencher_senha(pagina, acesso["senha"])
    if not (usuario_ok and senha_ok):
        print("  ! campos de login não encontrados — faça o login na janela")
        return False

    clicar(pagina, [
        'button[type="submit"]', 'input[type="submit"]',
        'button:has-text("Entrar")', 'button:has-text("Acessar")',
        'button:has-text("Continuar")',
    ], "enviar login")
    pagina.wait_for_timeout(6000)

    if detectar_barreira(pagina):
        print("  ! ainda na tela de login (2FA, captcha ou dados incorretos) "
              "— conclua na janela e clique em 'Prosseguir'")
        return False
    print("  OK login aceito")
    return True


def _preencher_senha(pagina, senha):
    """Igual a preencher_campo, mas sem NADA da senha no log."""
    for sel in ('input[name="password"]', 'input[type="password"]',
                'input[id*="senha" i]'):
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.fill(str(senha))
            print("  OK senha: preenchida")
            return True
        except Exception:
            continue
    return False


def digitar(pagina, candidatos, valor, nome_campo, atraso=120):
    """Digita tecla a tecla, em vez de `fill`.

    Formulários React (Webmotors) só validam o campo e habilitam o botão
    seguinte quando recebem os eventos reais de digitação: com `fill` o
    valor aparece na tela mas o "Continuar" continua desabilitado.
    """
    if valor is None or str(valor).strip() == "":
        return False
    ultimo_erro = None
    for sel in candidatos:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.click()
            loc.fill("")
            pagina.keyboard.type(str(valor), delay=atraso)
            print(f"  OK {nome_campo}: digitado")
            return True
        except Exception as exc:
            ultimo_erro = exc
            continue
    print(f"  ! {nome_campo}: campo não encontrado{_detalhe_erro(ultimo_erro)}")
    return False


def _detalhe_erro(exc):
    """Resumo de 1 linha da última exceção, para o log de falha."""
    if exc is None:
        return ""
    linhas = str(exc).splitlines()
    resumo = linhas[0][:120] if linhas else ""
    return f" (último erro: {type(exc).__name__}: {resumo})"


def preencher_campo(pagina, candidatos, valor, nome_campo):
    """Preenche o primeiro seletor visível da lista. Retorna True/False."""
    if valor is None or str(valor).strip() == "":
        return False
    ultimo_erro = None
    for sel in candidatos:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.fill(str(valor))
            print(f"  OK {nome_campo}: preenchido")
            return True
        except Exception as exc:
            ultimo_erro = exc
            continue
    print(f"  ! {nome_campo}: campo não encontrado{_detalhe_erro(ultimo_erro)}"
          " — complete manualmente se necessário")
    return False


def clicar(pagina, candidatos, nome_acao, obrigatorio=False):
    """Clica no primeiro seletor visível da lista. Retorna True/False."""
    ultimo_erro = None
    for sel in candidatos:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.click()
            print(f"  OK {nome_acao}")
            return True
        except Exception as exc:
            ultimo_erro = exc
            continue
    msg = f"  ! {nome_acao}: botão não encontrado{_detalhe_erro(ultimo_erro)}"
    if obrigatorio:
        raise RuntimeError(msg)
    print(msg + " — faça manualmente se necessário")
    return False


def enviar_fotos(pagina, veiculo, candidatos_input, maximo=8):
    """Baixa as fotos (URLs do banco) para %TEMP% e sobe no input de arquivo."""
    urls = (veiculo.get("fotos") or [])[:maximo]
    if not urls:
        print("  - sem fotos no banco para este veículo")
        return False
    pasta = Path(tempfile.gettempdir()) / "MarketplaceBot_fotos" / veiculo["id"]
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for i, url in enumerate(urls):
        destino = pasta / f"foto_{i}.jpg"
        try:
            if not destino.exists():
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                destino.write_bytes(r.content)
            caminhos.append(str(destino))
        except Exception as exc:
            print(f"  ! foto {i + 1}: falha no download ({exc})")
    if not caminhos:
        return False
    ultimo_erro = None
    for sel in candidatos_input:
        try:
            loc = pagina.locator(sel).first
            if loc.count() == 0:
                continue
            loc.set_input_files(caminhos)
            print(f"  OK {len(caminhos)} foto(s) enviada(s)")
            return True
        except Exception as exc:
            ultimo_erro = exc
            continue
    print(f"  ! upload de fotos: input não encontrado{_detalhe_erro(ultimo_erro)}"
          " — suba as fotos manualmente")
    return False


def esperar_formulario(pagina, timeout=20000):
    """Espera aparecer algum campo de formulário: sites SPA montam a página
    bem depois do domcontentloaded. Tolerante: se nada aparecer, só avisa."""
    try:
        pagina.wait_for_selector(
            'input, textarea, select, [role="combobox"]', timeout=timeout)
    except Exception:
        print(f"  ! página sem campos de formulário após {timeout // 1000}s "
              f"(url atual: {pagina.url})")
    pagina.wait_for_timeout(1500)


def _atributos_campo(elemento):
    """Descrição compacta de um campo para o log de diagnóstico."""
    partes = []
    for atributo in ("aria-label", "name", "id", "placeholder", "type"):
        try:
            valor = elemento.get_attribute(atributo)
        except Exception:
            valor = None
        if valor:
            partes.append(f"{atributo}={valor[:40]}")
    return " ".join(partes)


def dump_diagnostico(pagina, site_id, momento):
    """Fotografa o estado da página para calibrar seletores: imprime no log
    a URL, os aria-label dos comboboxes e contagens de campos, e salva
    screenshot + HTML em %LOCALAPPDATA%/MarketplaceBot/debug/<site>.
    Nunca derruba o fluxo: qualquer erro vira uma linha de log."""
    try:
        print(f"  [diag/{momento}] url: {pagina.url}")
        combos = pagina.locator('[role="combobox"]')
        total_combos = combos.count()
        rotulos = []
        for i in range(min(total_combos, 25)):
            rotulo = combos.nth(i).get_attribute("aria-label")
            if not rotulo:
                # sem aria-label (nomeado via aria-labelledby): usa o texto
                texto = (combos.nth(i).inner_text() or "").strip()
                rotulo = " ".join(texto.split())[:48] or "?"
            rotulos.append(rotulo)
        print(f"  [diag/{momento}] comboboxes ({total_combos}): "
              + (" | ".join(rotulos) if rotulos else "nenhum"))
        inputs = pagina.locator("input")
        total_inputs = inputs.count()
        n_file = pagina.locator('input[type="file"]').count()
        n_textareas = pagina.locator("textarea").count()
        n_iframes = pagina.locator("iframe").count()
        n_dialogs = pagina.locator('[role="dialog"]').count()
        print(f"  [diag/{momento}] inputs: {total_inputs} (file: {n_file}) | "
              f"textareas: {n_textareas} | iframes: {n_iframes} | "
              f"dialogs: {n_dialogs}")
        rotulos_inputs = []
        for i in range(min(total_inputs, 25)):
            descricao = _atributos_campo(inputs.nth(i))
            if descricao:
                rotulos_inputs.append(descricao)
        if rotulos_inputs:
            print(f"  [diag/{momento}] inputs rotulados: "
                  + " | ".join(rotulos_inputs))
        areas = pagina.locator("textarea")
        rotulos_areas = []
        for i in range(min(areas.count(), 10)):
            descricao = _atributos_campo(areas.nth(i))
            if descricao:
                rotulos_areas.append(descricao)
        if rotulos_areas:
            print(f"  [diag/{momento}] textareas rotuladas: "
                  + " | ".join(rotulos_areas))
        botoes = pagina.locator('button, [role="button"], input[type="submit"]')
        textos_botoes = []
        for i in range(min(botoes.count(), 20)):
            try:
                texto = " ".join((botoes.nth(i).inner_text() or "").split())[:36]
            except Exception:
                texto = ""
            if texto:
                textos_botoes.append(texto)
        textos_botoes = list(dict.fromkeys(textos_botoes))
        if textos_botoes:
            print(f"  [diag/{momento}] botões: " + " | ".join(textos_botoes))
        opcoes = pagina.locator('[role="option"], [role="menuitem"]')
        total_opcoes = opcoes.count()
        if total_opcoes:
            textos_opcoes = []
            for i in range(min(total_opcoes, 30)):
                try:
                    texto = " ".join((opcoes.nth(i).inner_text() or "").split())[:40]
                except Exception:
                    texto = ""
                if texto:
                    textos_opcoes.append(texto)
            print(f"  [diag/{momento}] opções abertas ({total_opcoes}): "
                  + " | ".join(textos_opcoes))
        pasta = get_data_dir() / "debug" / site_id
        pasta.mkdir(parents=True, exist_ok=True)
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        pagina.screenshot(path=str(pasta / f"{carimbo}-{momento}.png"),
                          full_page=True)
        (pasta / f"{carimbo}-{momento}.html").write_text(
            pagina.content(), encoding="utf-8")
        print(f"  [diag/{momento}] captura salva em {pasta}")
    except Exception as exc:
        print(f"  [diag/{momento}] diagnóstico falhou: {exc}")


class SiteAdapter:
    # identificador curto e estável (vai para anunciados.json — não mudar depois)
    id = ""
    # nome exibido na interface
    nome = ""
    # página inicial/login — aberta primeiro para o usuário autenticar
    url_home = ""
    # False enquanto o formulário do site não foi calibrado ponta a ponta:
    # a interface mostra "Em breve" e não deixa marcar o site, e o
    # anunciador ignora o site mesmo se ele vier num parametros_venda.json
    # antigo. Ao calibrar, basta voltar para True.
    disponivel = True
    motivo_indisponivel = ""
    # True quando o site esconde o formulário atrás de login: a interface
    # oferece campos de usuário/senha (guardados só em memória) e o
    # adaptador chama tentar_login antes de desistir
    exige_login = False
    # True quando a publicação depende de escolher plano/pagar: o bot
    # preenche tudo e PARA — quem conclui é o usuário. O anunciador não
    # registra o par veículo×site como publicado nesses casos.
    publicacao_manual = False
    # True quando o FORMULÁRIO do site pede dados pessoais do vendedor
    # (nome/CPF/telefone/e-mail) além do login. A interface só mostra esses
    # campos quando um site assim está marcado.
    exige_dados_pessoais = False
    # True quando o adaptador sabe EXCLUIR um anúncio publicado (ver
    # excluir_anuncio). A interface só oferece o botão para esses sites.
    suporta_exclusao = False
    # opções que a interface manda no parametros_venda.json e só fazem
    # sentido para um site (ex.: qual Página do Facebook usar)
    opcoes = {}
    # em qual navegador este site roda: "chrome" (perfil do bot) ou "edge"
    # (janela normal do PC, dirigida por CDP). A OLX bloqueia navegador
    # iniciado pelo Playwright, então ela pede "edge".
    navegador = "chrome"

    def abrir_novo_anuncio(self, pagina):
        """Navega até o formulário de novo anúncio, pronto para preencher."""
        raise NotImplementedError

    def preencher(self, pagina, veiculo):
        """Preenche o formulário com os dados do veículo (dict padronizado:
        id, titulo, marca, modelo, ano, preco, km, descricao, fotos, placa,
        status, versao, cor, cambio, combustivel, portas, opcionais)."""
        raise NotImplementedError

    def publicar(self, pagina):
        """Confirma/publica o anúncio preenchido. Só é chamado fora do
        modo teste (dry-run)."""
        raise NotImplementedError

    def finalizar(self, pagina):
        """Devolve o navegador ao estado de antes. Roda sempre, mesmo se o
        anúncio falhou (o Facebook/Página, por exemplo, precisa voltar ao
        perfil pessoal, senão o Marketplace fica bloqueado depois)."""
        return None

    def excluir_anuncio(self, pagina, veiculo):
        """Tira do ar o anúncio deste veículo. Retorna True se excluiu.

        É a única operação DESTRUTIVA do bot: a interface pede confirmação
        antes e o anunciador só apaga o registro local quando o site
        confirma a exclusão.
        """
        raise NotImplementedError(
            f"{self.nome}: exclusão de anúncio ainda não calibrada")
