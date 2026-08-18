# MarketplaceBot — contexto do projeto

Bot desktop Windows (Tkinter + Playwright) com dois modos, escolhidos numa
tela inicial: **Compra** (busca anúncios no Facebook Marketplace ou no
iCarros e envia mensagens) e **Venda/Anúncio** (anuncia veículos do banco
Supabase do usuário em sites de classificados). Distribuído por instalador
com auto-update.

Navegação: `interface_principal.iniciar()` é um laço — o seletor abre o modo
escolhido e cada tela devolve `"voltar"` (o seletor reaparece) ou `"sair"`
(encerra). As duas telas montam o conteúdo dentro de
`ui_scroll.criar_area_rolavel()`: sem rolagem, o crescimento da tela deixava
os botões de ação fora de alcance. Por isso `interface_bot` e `interface_venda` expõem `iniciar()` e
NUNCA montam a GUI no import: seria impossível abrir a tela duas vezes no
mesmo processo.

## Distribuição e release

- PyInstaller **onedir** (`build/marketplace-bot.spec`) + Inno Setup
  (`build/installer.iss`) + GitHub Actions (`.github/workflows/release.yml`).
- Publicar versão: editar `src/version.py` → commit → `git tag vX.Y.Z` →
  `git push && git push --tags`. O CI valida tag×versão, builda e anexa ao
  Release o instalador versionado + cópia fixa `MarketplaceBot-Setup.exe`.
- Link permanente do site: `https://github.com/Thomas-Geron/marketplace-bot/releases/latest/download/MarketplaceBot-Setup.exe`
- **NUNCA** alterar o `AppId` (GUID) do installer.iss.
- Navegador: `channel="chrome"` (Chrome do sistema) — **não trocar** por
  Chromium (invalidaria o login salvo em perfil_bot).
- Dados do usuário vivem em `%LOCALAPPDATA%\MarketplaceBot` (parametros,
  visitados, anunciados, perfil do Chrome, sessão Supabase, logs) — updates
  e desinstalação nunca tocam lá.

## Módulo Venda (Supabase)

- Config e schema em `src/venda/config_venda.py` — único arquivo que conhece
  o banco. Publishable key é pública por design (RLS protege); **nunca**
  commitar service_role key.
- Schema: `veiculos(id, ano, km, cor, placa, combustivel, cambio, portas,
  versao, carroceria, chassi, renavam, preco_anunciado, valor_venda,
  valor_compra, opcionais, status, user_id, marca_id→marcas(nome),
  modelo_id→modelos(nome))` +
  `fotos(veiculo_id, url)`. Na dúvida sobre uma coluna, confirme no banco:
  `GET /rest/v1/veiculos?select=<coluna>&limit=1` responde 400 com o nome
  exato quando a coluna não existe (a RLS só esconde as linhas).
- Preço anunciado = `preco_anunciado` (campo "PREÇO ANUNCIADO" do site do
  Thomas), fallback `valor_venda`; aceita texto em formato BR.
- Modelo de acesso: **RLS por dono** (`auth.uid() = user_id`) + o bot filtra
  só `status = "disponível"` (tolerante a acento/caixa). Signup do Supabase
  fica **aberto** — o site do Thomas é quem cadastra os usuários.
- Trava anti-spam: cada par veículo×site anuncia UMA vez (`anunciados.json`).

## Sites de anúncio (`src/venda/sites/`)

Adaptadores plugáveis (1 arquivo por site + registro no `__init__.py`):
`facebook` (form /marketplace/create/vehicle), `icarros` (PAGO — pagamento
manual), `mobiauto`, `napista` (conta de loja), `webmotors` (form atrás de
login), `kavak` (funil de COTAÇÃO, não é classificado) e `demo` (formulário
local em assets/ para testes).
Site sem formulário calibrado ponta a ponta leva `disponivel = False` +
`motivo_indisponivel`: a interface o mostra cinza com "Em breve" e o
anunciador o ignora mesmo vindo de um parametros_venda.json antigo. Ao
calibrar, basta voltar a flag para True (hoje só NaPista e Kavak estão em
"Em breve"). Site pago cujo anúncio depende de escolher
plano leva `publicacao_manual = True`: o bot preenche tudo, para antes do
pagamento e o anunciador não registra o par como publicado.

Dados sensíveis (nome, CPF, telefone, e-mail e usuário/senha por site) são
digitados na interface e passados ao processo do bot em **variáveis de
ambiente** (`src/contato.py`) — nunca vão para os JSONs de parâmetros nem
para o histórico, e `limpar_ambiente()` os apaga ao fim da execução. Senha
jamais aparece em log; CPF/telefone só mascarados.

Login nos sites: `tentar_login` (base.py) preenche usuário/senha quando o
adaptador com `exige_login = True` bate numa barreira, mas 2FA/captcha
continuam exigindo o usuário na janela (bot abre abas → usuário confere →
Prosseguir);
`detectar_barreira` (base.py) reconhece tela de login/bloqueio e o adaptador
para com aviso em vez de preencher o nada. `fechar_cookies` roda antes do
formulário (o OneTrust da Kavak engolia todos os cliques).

Calibração: `dump_diagnostico` (sites/base.py) salva `[diag]` no log +
screenshot + HTML em `%LOCALAPPDATA%\MarketplaceBot\debug\<site>` — ajustar
seletores sempre a partir dessas capturas. Prints de sucesso usam "OK"
(nunca ✓: console cp1252 já mascarou sucesso como falha).

Testar seletor contra HTML capturado: abrir a captura com
`new_context(java_script_enabled=False)` — com JS ligado o React/Angular
rehidrata e limpa o DOM salvo (dá falso negativo em tudo). Lembrar que
`:text-is()` só casa elemento com nó de texto DIRETO (na Kavak o texto está
num `<span>` dentro do `<button>`; use `:has(span...)` ou `:has-text()`).

## Estado atual / pendências

- **Facebook (Venda) calibrado** (jul/2026) com capturas reais: campos
  estruturados preenchidos (tipo "Carro/picape", ano, fabricante, km,
  cor, combustível, câmbio, estilo da carroceria). **Estilo da carroceria
  é obrigatório** (sem ele o botão de publicar não libera): vem do campo
  `carroceria` do banco, traduzido para o rótulo do Facebook (Perua →
  Station wagon, Crossover → SUV); sem valor no banco, é deduzido do
  modelo/versão por palavra inteira e, em último caso, "Outro". Cor interna
  e Condição do veículo seguem manuais — inventá-las seria afirmar algo
  sobre o veículo que o banco não diz.
- **Kavak calibrada** (jul/2026): funil na própria home, em cascata
  Ano → Marca → Modelo (`aui-select`, opções `button.option`), botão
  `button[aria-label="Fazer cotação"]`; não há atalho por placa.
- **iCarros (Venda) calibrado** (ago/2026, sessão logada): fluxo em URLs
  próprias — `/vender/novo/meuveiculo/sobre` (placa `#qa_txt_placa` →
  "buscar placa" → versão `[id^="qa_rdn_modelo"]`, que preenche
  marca/modelo/anos/versão/cor/portas/combustível; sobram `#qa_cmb_km` e
  as caixas `input[name="opcionais"]`), `/chassi` (8 ÚLTIMOS dígitos, com
  botão "Validar depois"), `/preco` (`#qa_txt_preco`), `/descricao`
  (`textarea[name="descricao"]` — o id do site tem um ESPAÇO no meio, então
  `#descricao` não casa; o botão é `#qa_btn_proxima`, com A) e `/fotos`
  (`#react-images-upload`). É **pago** → `publicacao_manual = True`.
- **NaPista** exige login (auth.napista.com.br) **e CNPJ da loja** no
  painel do lojista, então nem com conta pessoal dá para anunciar — segue
  em "Em breve".
- **Mobiauto calibrada** (ago/2026, sessão logada): abas
  Sobre você → Veículo → Fotos → **Planos** (é paga, daí
  `publicacao_manual = True`). A aba Veículo é uma sequência: tipo Carro
  (`[data-testid="car"]`), **placa obrigatória** (`input[name="plate"]`,
  por `digitar()` — ela preenche marca/modelo/ano/versão/câmbio/
  combustível/portas/cor sozinha), `input[name="km"]`, características
  (opcionais do banco), destaques (deixados ao usuário), descrição
  obrigatória e preço; depois as fotos (`input[type=file]` múltiplo, com
  "Pular"). Os campos de marca/modelo/etc. **repetem `id="autocomplete"`**,
  então a âncora é `label:text-is("<rótulo>") + xpath=following::input[1]`,
  e as opções são MUI (`li[role="option"]` com o texto num `<p>`).
- Compra multi-site: **OLX calibrada** com captura real (jul/2026) —
  cards `a[data-testid="adcard-link"]`, chat por `button:has-text("Chat")`,
  filtros do painel por id (`mileage_*`, `regdate_*`, `price_*`) e
  **região por subdomínio de UF** derivada do CEP (a OLX não tem raio em
  km), com fallback para busca nacional. A OLX **bloqueia** navegação
  automatizada insistente (Cloudflare): o bot detecta e para com aviso —
  nunca tentar contornar; rodar menos anúncios por vez.
- Fontes de Compra vivem em `SITES_COMPRA` (interface_bot.py) e são
  despachadas por `site` no run.py: `facebook` (run.py), `icarros`
  (compra_icarros.py), `webmotors` (compra_webmotors.py) e `olx`
  (compra_olx.py, **fora da lista** por decisão do usuário — Cloudflare;
  para voltar, reincluir na lista).
- **Webmotors** (ago/2026): na **Compra** está calibrada — busca
  `/carros/estoque/<marca>[/<modelo>]`, anúncio
  `/comprar/.../<id>` e formulário "Envie uma mensagem ao vendedor"
  (`#ButtonSendProposal`); os seletores são escopados por
  `form:has(textarea[name="message"])` porque a página tem OUTRO form, o de
  financiamento, que pede CPF. Preço é filtrado pelo bot (lido do card) e
  não há filtro de região nesta versão. Na **Venda**, deslogado cai em
  `/login`; **logado** (ago/2026) `/vender-carro` vai direto para
  `/vender-carro/especificacoes`, cuja etapa 1 é a PLACA
  (`[data-qa="placaInput"]` + `[data-qa="btnContinuarEspec"]`) — o site puxa
  marca/modelo/versão dela. Calibrado com placa real: `fill()` NÃO funciona
  (o React só habilita o "Continuar" com eventos de digitação — usar
  `digitar()` de base.py); depois da consulta o site exige escolher a
  VERSÃO (`[data-qa="variable-select"]`); e existe o caminho alternativo
  `[data-qa="btnNaoPossuiPlaca"]`, que abre Marca/Modelo/Ano do Modelo/Ano
  de Fabricação/Versão/Cor — tudo que o bot já tem no banco, sem depender
  da consulta de placa (que falha quando repetida). Fase 2
  (`/vender-carro/informacoes`) calibrada: `input#quilometragem`,
  `input#preco` (ambos por `digitar()`) e `textarea[name="observation"]` —
  este último **bloqueia dados pessoais** por política antifraude e corta em
  500 caracteres, então o adaptador limpa telefone/e-mail/CPF antes de
  escrever. **A Webmotors é PAGA**: a 3ª fase é plano + pagamento, então o
  adaptador tem `publicacao_manual = True` — preenche tudo, para antes do
  plano e o anunciador NÃO registra como publicado (quem conclui é o
  usuário). Por isso ela está ativa (não é mais "Em breve").
- **Desafio "Pressione e segure"** (Akamai/PerimeterX, Webmotors):
  `esperar_desafio_humano` (base.py) reconhece, deixa a janela aberta e
  espera o usuário resolver — o bot nunca tenta contornar. Descoberta útil
  da calibração: o desafio some quando o navegador é aberto NORMALMENTE
  (Brave iniciado à parte + `connect_over_cdp`, `navigator.webdriver=False`)
  e aparece quando o Playwright dá `launch()` no Chrome.
- **iCarros como fonte de Compra** (jul/2026, calibrado ao vivo): o
  anúncio tem formulário próprio (nome/e-mail/telefone/observações +
  "Enviar mensagem") e **não exige login** — por isso entrou. Detalhes
  que custaram investigação: só filtra com marca E modelo no caminho
  (`/comprar/usados/<marca>/<modelo>`; `/comprar/carros/onix` devolve
  qualquer marca) e os filtros de preço/ano por querystring são
  ignorados, então o bot lê o preço do card e filtra por faixa e por UF
  (a cidade está na URL do anúncio). Anúncio só com WhatsApp é pulado.
- Análise das outras fontes: **Mobiauto** tem chat, mas exige login;
  **NaPista** só oferece WhatsApp no anúncio; **Kavak** é revenda (não
  há vendedor para abordar). Nenhum virou fonte de Compra.
- Interface da Compra habilita por site o que cada um aceita: Facebook =
  CEP + raio em km; iCarros = dados de contato (o formulário exige) e
  produto com marca+modelo; OLX = ano de/até, km até e câmbio. O gating
  é do `<<ComboboxSelected>>` em interface_bot.py.
- **Compra/Facebook verificada ao vivo** (jul/2026): os 8 seletores do
  config.py conferem (busca, cards, Localização, campo de cidade, raio,
  Aplicar, preço mín/máx) — não foi preciso mudar nada.
- **Chat da OLX ainda não capturado**: o Cloudflare barra o navegador
  AUTOMATIZADO (a mesma URL abre normal no navegador comum do usuário —
  o gatilho é o fingerprint do Playwright, não o IP). O bot não mascara
  esses sinais: ao detectar o bloqueio ele deixa a janela aberta para o
  usuário resolver a verificação e clicar em 'Prosseguir'. Os seletores
  do chat seguem como candidatos; a primeira rodada real (logado, poucos
  anúncios) grava as capturas em `debug/olx-compra` para fechar.
- Verificar se os inserts do site do Thomas gravam `user_id` (senão o
  veículo novo não aparece no bot do dono).
- Release **v1.1.0** publicada (jul/2026): modo Venda + Facebook da Venda
  calibrado + iCarros como fonte de Compra. Sites ainda não calibrados
  saem como "Em breve" na interface, o que torna a versão publicável
  mesmo com a calibração incompleta.

## Restrições

- Não alterar a lógica do bot de Compra no Facebook (filtros/coleta/
  mensagem/timing em run.py, filtros.py, coleta.py, mensagem.py e
  config.py). A OLX vive em `src/compra_olx.py` (fluxo paralelo) e pode
  evoluir livremente.
- `python src/main.py` roda em dev; `--run-bot`, `--run-venda` e
  `--install-browser` são as flags internas.
