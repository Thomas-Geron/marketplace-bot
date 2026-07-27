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
_BARREIRAS_TEXTO = (
    ("you have been blocked", "bloqueio antibot (Cloudflare)"),
    ("verifique que você é humano", "verificação antibot"),
    ("verify you are human", "verificação antibot"),
    ("acesso negado", "acesso negado pelo site"),
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
