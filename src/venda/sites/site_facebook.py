# src/venda/sites/site_facebook.py
"""
Facebook Marketplace — anúncio de veículo (/marketplace/create/vehicle).

Usa o MESMO perfil do Chrome do bot de compra. Seletores calibrados com
capturas reais da interface pt-BR (jul/2026):
- os campos não têm mais aria-label: os comboboxes (Tipo de veículo, Ano)
  são <label role="combobox"> nomeados via aria-labelledby, e os campos de
  texto (Fabricante, Modelo, Preço, Descrição) têm o rótulo num <span>
  dentro do <label> — daí os seletores role=...[name=...] e :has-text.
- Fabricante deixou de ser combobox: hoje é campo de texto.
- Quilometragem, Cor, Combustível e Câmbio só entram no DOM depois que o
  Tipo de veículo é selecionado.
"""
import time
import unicodedata

from venda.sites.base import (
    SiteAdapter, preencher_campo, clicar, enviar_fotos, dump_diagnostico)


def _chave(texto):
    """minúsculas e sem acentos, para casar valores do banco com opções do FB."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip().lower()


# cor do banco (normalizada por _chave) → rótulo da opção "Cor exterior" no FB
CORES_FB = {
    "preto": "Preto", "branco": "Branco", "prata": "Prata", "cinza": "Cinza",
    "grafite": "Cinza", "vermelho": "Vermelho", "vinho": "Vermelho",
    "azul": "Azul", "verde": "Verde", "amarelo": "Amarelo",
    "laranja": "Laranja", "marrom": "Marrom", "dourado": "Dourado",
    "bege": "Bege",
}

# combustível do banco (normalizado) → rótulos candidatos da opção no FB
COMBUSTIVEL_FB = {
    "flex": ["Flex"],
    "gasolina": ["Gasolina"],
    "diesel": ["Diesel"],
    "eletrico": ["Elétrico"],
    "hibrido": ["Híbrido"],
    "alcool": ["Outra", "Outro"],
    "etanol": ["Outra", "Outro"],
    "gnv": ["Outra", "Outro"],
}


def _opcoes_cambio(valor):
    """Rótulos candidatos no FB para o câmbio do banco (None se não mapear)."""
    chave = _chave(valor)
    if "manual" in chave:
        return ["Câmbio manual", "Transmissão manual"]
    if "autom" in chave or "cvt" in chave:
        return ["Câmbio automático", "Transmissão automática"]
    return None


def _selecionar_combobox(pagina, rotulos_campo, rotulos_opcao, nome_campo):
    """Abre um combobox do formulário e clica na primeira opção candidata.
    Se a opção não aparecer, salva um diagnóstico com o dropdown ABERTO
    (para calibrar os rótulos reais) e fecha com Escape. Retorna True/False."""
    candidatos_campo = []
    for rotulo in rotulos_campo:
        candidatos_campo.append(f'role=combobox[name="{rotulo}"]')
    for rotulo in rotulos_campo:
        candidatos_campo.append(f'label[role="combobox"]:has-text("{rotulo}")')
    for rotulo in rotulos_campo:
        candidatos_campo.append(f'label[role="combobox"][aria-label="{rotulo}"]')
    if not clicar(pagina, candidatos_campo, f"abrir '{nome_campo}'"):
        return False
    pagina.wait_for_timeout(600)
    candidatos_opcao = []
    for opcao in rotulos_opcao:
        candidatos_opcao.append(f'[role="option"]:text-is("{opcao}")')
    for opcao in rotulos_opcao:
        candidatos_opcao.append(f'[role="option"]:has-text("{opcao}")')
    for opcao in rotulos_opcao:
        candidatos_opcao.append(f'[role="menuitem"]:has-text("{opcao}")')
    for opcao in rotulos_opcao:
        candidatos_opcao.append(f'li:has-text("{opcao}")')
    for opcao in rotulos_opcao:
        candidatos_opcao.append(f'span:text-is("{opcao}")')
    if clicar(pagina, candidatos_opcao, f"{nome_campo}: '{rotulos_opcao[0]}'"):
        pagina.wait_for_timeout(600)
        return True
    # captura com o dropdown aberto: o diagnóstico lista as opções reais
    momento = "opcoes-" + _chave(nome_campo).replace(" ", "-")
    dump_diagnostico(pagina, "facebook", momento)
    pagina.keyboard.press("Escape")  # não deixar o dropdown aberto travando o resto
    pagina.wait_for_timeout(300)
    return False


class SiteFacebook(SiteAdapter):
    id = "facebook"
    nome = "Facebook Marketplace"
    url_home = "https://www.facebook.com/marketplace/"

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.facebook.com/marketplace/create/vehicle")
        pagina.wait_for_load_state("domcontentloaded")
        # o formulário é montado por JS bem depois do domcontentloaded —
        # espera o primeiro combobox aparecer em vez de um tempo fixo
        try:
            pagina.wait_for_selector('[role="combobox"]', timeout=30000)
        except Exception:
            print(f"  ! formulário não apareceu em 30s (url atual: {pagina.url})")
        pagina.wait_for_timeout(2000)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        # o que não couber em campo estruturado é somado à descrição no final
        descricao_extra = []

        # tipo de veículo — primeiro passo: destrava os demais campos
        # (Quilometragem, Cor, Combustível e Câmbio só entram no DOM depois)
        _selecionar_combobox(
            pagina, ["Tipo de veículo"], ["Carro/caminhão", "Carro"],
            "Tipo de veículo")
        pagina.wait_for_timeout(1500)

        enviar_fotos(pagina, veiculo, [
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ])
        pagina.wait_for_timeout(1500)

        if veiculo.get("ano"):
            _selecionar_combobox(pagina, ["Ano"], [str(veiculo["ano"])], "Ano")

        # fabricante: combobox depois que o Tipo de veículo é escolhido;
        # na variante antiga do formulário era campo de texto — tenta os dois
        marca = str(veiculo.get("marca") or "").strip()
        if marca:
            opcoes_marca = list(dict.fromkeys([marca, marca.split()[0]]))
            if not _selecionar_combobox(
                    pagina, ["Fabricante"], opcoes_marca, "Fabricante"):
                preencher_campo(pagina, [
                    'label:has-text("Fabricante") input',
                    'input[aria-label="Fabricante"]',
                    'role=textbox[name="Fabricante"]',
                ], marca, "Fabricante (texto)")

        # modelo + versão juntos: o FB monta o título como "Ano Fabricante Modelo"
        modelo = " ".join(
            str(p) for p in (veiculo.get("modelo"), veiculo.get("versao")) if p)
        preencher_campo(pagina, [
            'label:has-text("Modelo") input',
            'input[aria-label="Modelo"]',
            'role=textbox[name="Modelo"]',
        ], modelo, "Modelo")

        preencher_campo(pagina, [
            'label:has-text("Quilometragem") input',
            'input[aria-label="Quilometragem"]',
            'role=textbox[name="Quilometragem"]',
        ], veiculo.get("km"), "Quilometragem")

        preencher_campo(pagina, [
            'label:has-text("Preço") input',
            'input[aria-label="Preço"]',
            'role=textbox[name="Preço"]',
        ], veiculo.get("preco"), "Preço")

        cor = veiculo.get("cor")
        if cor:
            rotulo = CORES_FB.get(_chave(cor))
            if not (rotulo and _selecionar_combobox(
                    pagina, ["Cor exterior", "Cor externa"], [rotulo],
                    "Cor exterior")):
                descricao_extra.append(f"Cor {cor}")

        combustivel = veiculo.get("combustivel")
        if combustivel:
            rotulos = COMBUSTIVEL_FB.get(_chave(combustivel))
            ok = bool(rotulos) and _selecionar_combobox(
                pagina, ["Combustível", "Tipo de combustível"], rotulos,
                "Combustível")
            # 'Outra' no FB não diz qual é o combustível — registra na descrição
            if not ok or rotulos == ["Outra", "Outro"]:
                descricao_extra.append(f"Combustível {combustivel}")

        cambio = veiculo.get("cambio")
        if cambio:
            rotulos = _opcoes_cambio(cambio)
            if not (rotulos and _selecionar_combobox(
                    pagina, ["Câmbio", "Transmissão"], rotulos, "Câmbio")):
                descricao_extra.append(f"Câmbio {cambio}")

        # descrição: apenas o que não tem campo estruturado no formulário
        partes = []
        if veiculo.get("portas"):
            partes.append(f"{veiculo['portas']} portas")
        if veiculo.get("opcionais"):
            partes.append(f"Opcionais: {veiculo['opcionais']}")
        partes.extend(descricao_extra)
        descricao = "\n".join(partes) or (veiculo.get("descricao") or "")
        preencher_campo(pagina, [
            'label:has-text("Descrição") textarea',
            'textarea[aria-label="Descrição"]',
            'role=textbox[name="Descrição"]',
            "textarea",
        ], descricao, "Descrição")

        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)  # tempo para revisar visualmente

    def publicar(self, pagina):
        # o formulário pode ter etapa intermediária "Avançar" antes de "Publicar"
        if clicar(pagina, [
            'div[aria-label="Avançar"][role="button"]',
            'div[role="button"]:has-text("Avançar")',
        ], "Avançar"):
            pagina.wait_for_timeout(1500)
        clicar(pagina, [
            'div[aria-label="Publicar"][role="button"]',
            'div[role="button"]:has-text("Publicar")',
        ], "Publicar", obrigatorio=True)
        pagina.wait_for_timeout(4000)
