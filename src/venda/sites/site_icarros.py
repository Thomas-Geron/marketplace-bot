# src/venda/sites/site_icarros.py
"""
iCarros — anúncio de veículo (https://www.icarros.com.br/vender).

ATENÇÃO: anunciar no iCarros é PAGO. O bot preenche tudo e PARA antes de
plano/pagamento (`publicacao_manual = True`) — quem escolhe plano e paga
é sempre você.

Calibrado ao vivo com sessão logada (ago/2026). O fluxo tem etapas em URLs
próprias e o formulário usa `<select>` nativos com ids estáveis prefixados
por `qa_` — o tipo mais confiável de automatizar:

1. `/vender/novo/meuveiculo/sobre`
   - `input#qa_txt_placa` + `button#qa_btn_proximo` ("buscar placa");
   - a busca lista as versões como `[id^="qa_rdn_modelo"]`; escolher uma
     preenche marca, modelo, anos, versão, cor, portas e combustível;
   - restam `input#qa_cmb_km` e as caixas de opcionais
     (`input[name="opcionais"]`, com rótulos legíveis).
2. `/vender/novo/meuveiculo/chassi` — pede os 8 ÚLTIMOS dígitos do chassi
   (o banco tem a coluna `chassi`); há "Validar depois" para quem não tem.
3. `/vender/novo/meuveiculo/preco` — `input#qa_txt_preco`.
4. `/vender/novo/meuveiculo/descricao` — `textarea[name="descricao"]` (o
   id do site tem um espaço no meio, então `#descricao` não casa) e o botão
   de avanço é `#qa_btn_proxima` (com A no fim — é assim no site mesmo).
5. `/vender/novo/meuveiculo/fotos` — `input#react-images-upload` (múltiplo).
6. Depois vêm os planos: o bot para aqui.
"""
import time

from venda.sites.base import (
    SiteAdapter, clicar, detectar_barreira, digitar, dump_diagnostico,
    enviar_fotos, esperar_formulario, fechar_cookies, preencher_campo,
    tentar_login)


def _clicar_proximo(pagina, etapa):
    """Botão de avanço: há mais de um com o mesmo id, então procura o
    visível e habilitado. Na tela de descrição o id é `qa_btn_proxima`."""
    for sel in ("button#qa_btn_proximo", "button#qa_btn_proxima"):
        botoes = pagina.locator(sel)
        for i in range(botoes.count()):
            botao = botoes.nth(i)
            try:
                if botao.is_visible() and botao.is_enabled():
                    botao.click()
                    print(f"  OK avançar ({etapa})")
                    pagina.wait_for_timeout(6000)
                    return True
            except Exception:
                continue
    print(f"  ! {etapa}: botão de avanço indisponível — confira na janela")
    return False


class SiteICarros(SiteAdapter):
    id = "icarros"
    nome = "iCarros"
    url_home = "https://www.icarros.com.br/vender"
    exige_login = True
    publicacao_manual = True   # anúncio pago: quem escolhe o plano é você

    def abrir_novo_anuncio(self, pagina):
        pagina.goto("https://www.icarros.com.br/vender")
        pagina.wait_for_load_state("domcontentloaded")
        pagina.wait_for_timeout(3000)
        fechar_cookies(pagina)
        # a landing não tem formulário: o fluxo abre por um <button>
        clicar(pagina, [
            'button:has-text("Começar anúncio")',
            'a:has-text("Começar anúncio")',
        ], "Começar anúncio")
        pagina.wait_for_timeout(6000)

    def preencher(self, pagina, veiculo):
        dump_diagnostico(pagina, self.id, "inicio")
        barreira = detectar_barreira(pagina)
        if barreira and not tentar_login(pagina, self.id):
            print(f"  ! iCarros caiu em {barreira}: entre na conta nesta aba "
                  "(ou preencha usuário/senha na interface) e rode de novo.")
            return
        esperar_formulario(pagina)

        # ---------------- 1) placa -> versão -> km -> opcionais ----------
        placa = veiculo.get("placa")
        if not placa:
            print("  ! veículo sem placa no banco — o iCarros começa por ela; "
                  "pulei este veículo.")
            return
        digitar(pagina, ["#qa_txt_placa"], placa, "Placa")
        pagina.wait_for_timeout(1500)
        _clicar_proximo(pagina, "buscar placa")
        pagina.wait_for_timeout(3000)

        # a busca devolve as versões; escolher uma preenche o resto sozinho
        versoes = pagina.locator('[id^="qa_rdn_modelo"]')
        if versoes.count():
            self._escolher_versao(versoes, veiculo).click()
            pagina.wait_for_timeout(4000)
        else:
            print("  ! nenhuma versão retornada para a placa — confira na janela")
            dump_diagnostico(pagina, self.id, "sem-versoes")

        digitar(pagina, ["#qa_cmb_km"], veiculo.get("km"), "Quilometragem")
        self._marcar_opcionais(pagina, veiculo)
        dump_diagnostico(pagina, self.id, "dados-do-veiculo")
        if not _clicar_proximo(pagina, "dados do veículo"):
            return

        # ---------------- 2) chassi (8 últimos dígitos) ------------------
        if "chassi" in (pagina.url or ""):
            chassi = str(veiculo.get("chassi") or "").strip()
            if chassi:
                digitar(pagina, ['input[id*="text-field-input"]', "input"],
                        chassi[-8:], "Chassi (8 últimos)")
                pagina.wait_for_timeout(1500)
                clicar(pagina, ['button:has-text("Validar chassi")'],
                       "validar chassi")
            else:
                print("  - sem chassi no banco: seguindo com 'Validar depois'")
                clicar(pagina, ['button:has-text("Validar depois")'],
                       "validar depois")
            pagina.wait_for_timeout(6000)

        # ---------------- 3) preço ----------------
        digitar(pagina, ["#qa_txt_preco"], veiculo.get("preco"), "Preço")
        pagina.wait_for_timeout(1500)
        _clicar_proximo(pagina, "preço")

        # ---------------- 4) descrição ----------------
        # o id da textarea tem um ESPAÇO no site ("descricao qa_txt_descricao"),
        # então #descricao nunca casa — a âncora é o name
        preencher_campo(pagina, ['textarea[name="descricao"]', "textarea"],
                        veiculo.get("descricao"), "Descrição")
        pagina.wait_for_timeout(1500)
        _clicar_proximo(pagina, "descrição")

        # ---------------- 5) fotos ----------------
        enviar_fotos(pagina, veiculo, [
            "#react-images-upload", 'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ])
        pagina.wait_for_timeout(3000)

        dump_diagnostico(pagina, self.id, "fim")
        time.sleep(2)

    def _escolher_versao(self, versoes, veiculo):
        """A opção que casa com a versão do banco; senão, a primeira."""
        desejada = str(veiculo.get("versao") or "").strip().lower()
        if desejada:
            for i in range(versoes.count()):
                item = versoes.nth(i)
                try:
                    if desejada in (item.inner_text() or "").lower():
                        print(f"  OK versão do banco encontrada: {desejada}")
                        return item
                except Exception:
                    continue
            print(f"  ! versão '{desejada}' não está na lista do iCarros — "
                  "usando a primeira; confira na janela")
        return versoes.first

    def _marcar_opcionais(self, pagina, veiculo):
        """Marca as caixas de opcionais que batem com o campo do banco."""
        opcionais = str(veiculo.get("opcionais") or "").strip()
        if not opcionais:
            print("  - sem opcionais no banco para marcar")
            return
        marcados = 0
        for item in [o.strip() for o in opcionais.split(",") if o.strip()]:
            alvo = pagina.locator(
                f'label:has-text("{item}") input[name="opcionais"]').first
            try:
                if alvo.count() and not alvo.is_checked():
                    alvo.check()
                    marcados += 1
                    pagina.wait_for_timeout(200)
            except Exception:
                continue
        print(f"  OK opcionais marcados: {marcados}")

    def publicar(self, pagina):
        # depois das fotos vêm os planos: o bot não escolhe plano nem paga
        print("  iCarros é PAGO: o bot preencheu e parou antes do plano. "
              "Revise na janela, escolha o plano e conclua você mesmo.")
        dump_diagnostico(pagina, self.id, "antes-do-plano")
