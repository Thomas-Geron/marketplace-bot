# MarketplaceBot — contexto do projeto

Bot desktop Windows (Tkinter + Playwright) com dois modos, escolhidos numa
tela inicial: **Compra** (busca anúncios no Facebook Marketplace ou no
iCarros e envia mensagens) e **Venda/Anúncio** (anuncia veículos do banco
Supabase do usuário em sites de classificados). Distribuído por instalador
com auto-update.

Navegação: `interface_principal.iniciar()` é um laço — o seletor abre o modo
escolhido e cada tela devolve `"voltar"` (o seletor reaparece) ou `"sair"`
(encerra). Por isso `interface_bot` e `interface_venda` expõem `iniciar()` e
NUNCA montam a GUI no import: seria impossível abrir a tela duas vezes no
mesmo processo.

Aparência: `ui_tema.py` (paleta, estilos ttk, `secao()`, `botao()`) e
`ui_scroll.criar_area_rolavel()` (sem rolagem, o crescimento das telas
deixava os botões de ação fora de alcance). Regra de layout: campo que o
site escolhido NÃO usa **some** (`grid_remove`), em vez de ficar cinza —
`campos_do_site()` na Compra e o `trace` das checkboxes na Venda decidem o
que aparece. Na Venda, dados pessoais e usuário/senha só aparecem quando um
site que os exige está marcado (`exige_login`, `exige_dados_pessoais`), e o
bloco de login do Supabase se recolhe numa linha "Conectado: … [Sair]".

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
- Desfazer, de dois jeitos que NÃO se confundem: **"Anunciar de novo"**
  só apaga o registro local (`anunciados.esquecer`) — o anúncio segue no
  ar; **"Excluir anúncio"** roda o anunciador com `acao = "excluir"` e
  tira o anúncio DO AR no site (só sites com `suporta_exclusao`), pedindo
  confirmação antes e apagando o registro local apenas quando o site
  confirma. `excluir_anuncio` sempre CONFERE que o anúncio sumiu antes de
  responder True: seletor errado vira "não excluído" + captura em debug/,
  nunca um sucesso falso.

## Sites de anúncio (`src/venda/sites/`)

Adaptadores plugáveis (1 arquivo por site + registro no `__init__.py`):
`facebook` (form /marketplace/create/vehicle), `facebook_pagina` (post no
feed da PÁGINA), `icarros` (PAGO — pagamento
manual), `mobiauto`, `napista` (conta de loja), `webmotors` (form atrás de
login), `kavak` (funil de COTAÇÃO, não é classificado) e `demo` (formulário
local em assets/ para testes).
Opção que só faz sentido para um site (ex.: qual Página do Facebook usar)
vai em `parametros_venda.json` → `opcoes[<site_id>]` e chega no adaptador
como `self.opcoes`. `finalizar(pagina)` roda ao fim do site, mesmo com
erro, para devolver o navegador ao estado anterior.
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

- **Facebook (Página) calibrado** (ago/2026, ao vivo): Página **não pode
  usar o Marketplace** — com o perfil da Página ativo, qualquer URL do
  Marketplace cai em `/marketplace/ineligible/` com "Pages can't use
  Marketplace". O que a Página tem é o POST no feed, e é isso que o
  adaptador faz: `pages/?category=your_pages` lista as Páginas geridas →
  no perfil da Página, `[aria-label="Alternar"]` + o "Alternar" do
  diálogo "Trocar de perfil" trocam o perfil ativo → o composer
  ("No que você está pensando?") abre `[role="dialog"][aria-label="Criar
  post"]`, cujo texto é um editor **Lexical**
  (`[role="textbox"][data-lexical-editor="true"]` — tem aria-PLACEHOLDER,
  não aria-label, e ignora `fill`: escrever com `keyboard.type`) e cujas
  fotos entram pelo `input[type=file][multiple]` de dentro do diálogo →
  "Avançar" leva a "Configurações do post" e o botão final é
  `[aria-label="Postar"]`. **"Turbinar post" é anúncio pago e fica
  desligado.** No fim, `finalizar()` volta ao perfil pessoal
  (`[aria-label="Seu perfil"]` → `[aria-label^="Trocar para "]`) — sem
  isso o bot do Marketplace ficaria bloqueado na execução seguinte.
  Ensaiado ao vivo com veículo fictício: troca de perfil, texto e upload
  de fotos conferidos; nada foi publicado.
- **Exclusão de anúncio ainda não confirmada ao vivo**: a conta de teste
  não tem nenhum classificado no ar ("Seus classificados" vazio) nem post
  de veículo na Página, então o caminho menu (…) → "Excluir" → confirmar
  foi escrito a partir da estrutura do painel, com verificação e
  `dump_diagnostico`. A primeira exclusão real fecha a calibração.

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
- Compra multi-site: **OLX volta a funcionar** (ago/2026) rodando no
  **Microsoft Edge do computador**, iniciado como um atalho comum e
  dirigido por CDP (`navegador.abrir_navegador(pw, "edge")`, perfil
  próprio `perfil_edge`): o que o Cloudflare barrava era o navegador
  iniciado pelo Playwright (`navigator.webdriver`), não a marca. Nada é
  mascarado — se aparecer verificação, o bot para e espera o usuário.
  Três correções que vieram desse teste:
  **(a)** a região da busca é SEGMENTO DE CAMINHO (`/estado-rj`), não
  subdomínio — `rj.olx.com.br` redireciona a busca para a home;
  **(b)** nada de seletor genérico tipo `section a[href*="olx.com.br"]`:
  fora da página de resultados ele casa o menu inteiro e o bot "abre
  anúncios" que são links da home (os links coletados agora precisam
  terminar em `-<id numérico>`);
  **(c)** o chat do anúncio é `#price-box-button-chat` — `button:has-text
  ("Chat")` casava com o "Chat" do MENU do site.
  O campo de mensagem do chat só aparece logado (o bot procura também
  dentro dos iframes e avisa quando a sessão está deslogada).
- **Anti-repetição por PESSOA** (`src/historico.py`, ago/2026): o
  histórico deixou de ser só de URL — cada registro guarda também o
  `vendedor` (identificado por site em `_SELETORES_VENDEDOR`), e o bot
  pula com "você já enviou mensagem para esta pessoa" antes de escrever,
  em qualquer plataforma e em qualquer execução. Registros antigos, só
  com URL, continuam valendo. Quem não é identificado não bloqueia nada
  (o bot não inventa identidade).
- **Ordem dos anúncios**: `coletar_links` ordena pela POSIÇÃO NA TELA
  (linha por linha, com tolerância de 40px), não pela ordem do DOM — o
  Facebook injeta os cards fora de ordem e o bot abria "o primeiro do
  carregamento" em vez do primeiro visível. Sem posições legíveis, cai
  de volta na ordem do DOM.
- **CPF na Compra**: `campos_do_site` separa "contato" de "cpf". Contato
  (nome/e-mail/telefone) vai para iCarros, Webmotors e Mobiauto; o CPF só
  para **iCarros e Webmotors**, que pedem de fato — na Mobiauto quem pede
  CPF é o financiamento, que o bot não preenche, então o campo some da
  tela. Facebook, OLX e NaPista não recebem nada disso.
- Compra em **fila**: o campo Produtos aceita um nome por linha e o bot
  faz um de cada vez, do começo ao fim, na mesma sessão do navegador. A
  **quantidade máxima vale POR NOME** (não é dividida entre eles) — quem
  guarda a fila é `Parametros.produtos`, e `produto` continua sendo o
  primeiro, para o código que trata um por vez. No Facebook a localização
  é aplicada só na primeira volta (é filtro global do Marketplace e
  reabrir o modal a cada nome só aumentaria a chance de falhar), e o
  histórico de `visitados.json` é compartilhado pela fila inteira.
- **Mobiauto como fonte de Compra** (ago/2026, calibrada ao vivo): o
  anúncio tem o bloco **"Fale com o vendedor"** (nome, e-mail, celular e
  mensagem) e NÃO exige login — com os três campos preenchidos, o botão
  "Enviar Mensagem", que nasce desabilitado, libera sozinho. Pegadinha:
  a MESMA página tem o formulário de financiamento do Banco Pan, com
  nome/e-mail/celular e **CPF**, e os dois usam `input[name="name"]` —
  por isso o adaptador ancora tudo no bloco do vendedor
  (`//button[contains(.,"Enviar Mensagem")]/ancestor::*[.//textarea][1]`).
  Busca: `/comprar/carros-usados/<uf|brasil>/<marca>[/<modelo>]` (uma
  palavra só já vale, vira a marca); cards são `.deal-card` e o preço vem
  quebrado em nós diferentes, então o texto é normalizado antes do regex.
  Envio só entra no histórico quando a página confirma.
- **NaPista como fonte de Compra** (ago/2026): o site **não tem
  formulário de mensagem** — conferido em vários anúncios (`textarea` = 0).
  Só existem "Enviar WhatsApp", "Ver telefone e endereço" e um formulário
  que NÃO fala com o vendedor: é consulta de crédito (nome, celular,
  e-mail e **CPF**) para as lojas parceiras. O bot não dispara WhatsApp
  nem manda CPF para análise de crédito, então `compra_napista.py`
  **procura e LISTA** os anúncios que batem com a busca (link, preço,
  ano, km, cidade e loja) e não envia nada. Busca:
  `/busca/<marca>[/<modelo>]?pn=<página>` (o `?q=` NÃO filtra); cards são
  `a[href^="/anuncios/<uuid>"]` com tudo no texto do próprio link.
- Fontes de Compra vivem em `SITES_COMPRA` (interface_bot.py) e são
  despachadas por `site` no run.py: `facebook` (run.py), `icarros`
  (compra_icarros.py), `webmotors` (compra_webmotors.py), `mobiauto`
  (compra_mobiauto.py), `napista` (compra_napista.py, só lista) e `olx`
  (compra_olx.py). Módulo importado dentro da função precisa entrar em
  `hiddenimports` do .spec, senão some no instalador.
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
- Análise das outras fontes: **Mobiauto** e **NaPista** viraram fontes de
  Compra (ver acima) — a Mobiauto, ao contrário do que a primeira análise
  supôs, NÃO exige login para falar com o vendedor. **Kavak** segue de
  fora: é revenda, não há vendedor para abordar.
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
