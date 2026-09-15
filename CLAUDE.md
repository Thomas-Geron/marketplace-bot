# MarketplaceBot — contexto do projeto

Bot desktop Windows (Tkinter + Playwright) com dois modos, escolhidos numa
tela inicial: **Compra** (busca anúncios no Facebook Marketplace ou no
iCarros e envia mensagens) e **Venda/Anúncio** (anuncia veículos do banco
Supabase do usuário em sites de classificados). Distribuído por instalador
com auto-update.

Navegação (set/2026): janela ÚNICA (`interface_principal.App`) com lateral
fixa — Início, Compra, Venda/Anúncio; "Anúncios salvos", "Histórico" e
"Configurações" aparecem como "Em breve", sem tela falsa — e a página da
vez. `interface_bot.montar(pai, app)` e `interface_venda.montar(pai, app)`
devolvem uma `Pagina` (`frame`, `ao_mostrar`, `encerrar`, `guia`): cada
página é montada na primeira visita e fica viva, então trocar de página não
perde o preenchido nem para um bot em execução; fechar a janela chama
`encerrar()` de todas. Os módulos NUNCA montam GUI no import (`iniciar()`
deles só abre o app naquela página). A sessão do Supabase é conferida uma
vez numa thread que NÃO toca no Tk (a principal consulta o resultado com
`after` — `after` chamado da thread falhava calado) e `app.banco` é o mesmo
objeto da Venda: o refresh token só vale uma vez. "Sair" fica no rodapé da
lateral e faz `banco.logout()` de verdade (antes só limpava a tela).

Aparência (set/2026, v2): lateral escura + conteúdo claro, roxo #7C3AED
como cor principal, azul de apoio e verde/âmbar/vermelho só para estado.
- `ui_tema.py`: tokens (`CORES`, `SELOS`, `ESPACO`, `RAIO`, fontes, glifos
  `ICONES` da Segoe MDL2 Assets) e os estilos ttk — botões `Primario`,
  `Secundario`, `Destaque`, `Perigo` (contorno), `PerigoCheio`,
  `Fantasma`/`FantasmaCartao`, `IconePerigo`, `Lateral`; campo
  `Campo.field` (borda #CBD5E1, hover #94A3B8, foco roxo com anel claro,
  também na Combobox só leitura); `Cartao.TFrame`; rótulos `Titulo`,
  `Subtitulo`, `Secao`, `Rotulo`, `Texto`, `Ajuda`, `Numero`.
- `ui_imagens.py`: cantos arredondados com antisserrilhado, borda, anel de
  foco, sombra, gradiente, caixa de marcação e interruptor viram PNG gerado
  em código (distância com sinal, sem Pillow).
- Componentes: `ui_componentes.py` (Cartao, CabecalhoPagina, Marcador,
  Interruptor, `placeholder()` — rótulo por cima, `.get()` continua vazio —,
  `dica_flutuante()`, Banner, `estilo_moldura()`), `ui_sites.py`
  (CartaoSite + GradeSites responsiva), `ui_execucao.py` (LogExecucao com
  hora e ícone por nível via `nivel_da_linha`, BarraAcoes fixa com o modo
  teste e os estados parado/rodando/aguardando, ResumoExecucao),
  `ui_tabela.py` (TabelaVeiculos: marcação é a verdade, busca e filtro só
  escondem linhas) e `ui_scroll.py` (UMA ligação de roda por janela, que
  rola a área rolável mais próxima do ponteiro; Combobox não troca valor
  com a roda).
- Estados: Rodar só parado; Parar e Prosseguir só rodando; "aguardando"
  (Prosseguir roxo) vem da linha em que o bot pede "'Prosseguir'"
  (`pede_prosseguir`) e acaba em "Prosseguindo.". O modo teste trava
  durante a execução e, desligado, a faixa fica âmbar.
- Pegadinhas que custaram capturas: (1) elemento de imagem ttk mistura o
  alpha com o cinza do sistema — imagem ttk é "assada" sobre a cor de trás
  (tk.Label e Canvas misturam certo); (2) `element_create(border=)` usa o
  border também como respiro interno: passar `padding=0`; (3) o sv-ttk
  liga `configure_colors` ao `<<ThemeChanged>>` — que o Tk dispara a cada
  estilo/elemento criado — e ele volta o estilo "." para #fafafa e chama
  `tk_setPalette`, cujo `RecolorTree` pinta #fafafa/#1c1c1c em toda opção
  de cor vazia de TODOS os widgets já montados: os ttk.Label perdiam o
  estilo (faixa cinza, texto preto). `aplicar_tema` embrulha o proc: a
  paleta do sv-ttk roda uma vez só, chamada direto antes de existir
  widget (esperar o evento não serve — a janela ainda não existe e ele não
  chega), e depois só as cores do bot são reaplicadas. O TLabel também
  ganhou layout com `Label.border` (sem ele o `background` não pinta nada);
  (4) `ttk.Frame` ignora padding do estilo; (5) PrintWindow devolve preto
  no fundo de janela com cor-chave.
- `main.py` chama `preparar_dpi()` antes da primeira janela; medidas em
  pixel por `px()`. O .spec leva `collect_data_files("sv_ttk")`.
- Layout: páginas em duas colunas (uma só abaixo de ~1040 px na Compra e
  ~1100 px na Venda), log embaixo e barra de ações fixa no rodapé. Campo
  que o site escolhido NÃO usa **some** (`grid_remove`): `campos_do_site()`
  na Compra e o `trace` dos sites na Venda decidem; na Venda, dados
  pessoais e logins só aparecem com um site que os exige marcado
  (`exige_login`, `exige_dados_pessoais`).

Passo a passo (`src/tutorial.py`, set/2026): cada página (Início, Compra,
Venda) monta uma lista de `Passo(titulo, texto, alvos, opcional)` e um
`Tutorial` (chaves `inicio`, `compra-v2`, `venda-v2` — o "-v2" fez o passo a
passo reaparecer uma vez depois do redesenho). Abre sozinho só na primeira
visita (na Venda, já conectada); "Concluir" ou "Pular" gravam em
`%LOCALAPPDATA%\MarketplaceBot\tutorial.json`, trocar de página no meio
fecha SEM marcar (`encerrar_sem_marcar`) e o botão "? Ajuda" do topo reabre.
`alvos` é função (os widgets podem estar escondidos na montagem) e passo
`opcional` sem alvo visível some da contagem. O Tk não tem camada
semitransparente sobre os próprios widgets: o destaque são janelas sem
borda — 4 faixas com `-alpha` em volta do furo (a união dos alvos, que
continua clicável), 1 janela com `-transparentcolor` só com o contorno roxo
e o cartão do passo —,
reposicionadas a cada 150 ms (mover, redimensionar, rolar, minimizar). Ao
mudar um campo ou botão de lugar ou de nome, atualizar o texto do passo.
Para conferir: capturar cada janela por PrintWindow e compor (PrintWindow
devolve PRETO no fundo da janela com cor-chave).

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
feed da PÁGINA), `olx` (assistente "desapega", roda no **Edge**),
`icarros` (PAGO — pagamento
manual), `mobiauto`, `napista` (conta de loja), `webmotors` (form atrás de
login), `kavak` (funil de COTAÇÃO, não é classificado) e `demo` (formulário
local em assets/ para testes).
Cada adaptador declara em que navegador roda (`navegador = "chrome"` ou
`"edge"`); `anunciador.abrir_abas` agrupa os sites por navegador e abre
uma janela para cada grupo — misturar tudo numa só perderia o login salvo
do outro perfil.
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
- **OLX (Venda) calibrada** (ago/2026, ao vivo no Edge): assistente de
  uma URL só (`www2.olx.com.br/desapega`), sempre avançando pelo
  "Continuar" — categoria → "Carros, vans e utilitários" → "Entendi,
  vamos começar" → **placa** em sete caixas (`#digit-0`…`#digit-6`; sem
  placa não dá para anunciar) → diálogo "Encontramos seu veículo" com a
  versão em `input[type=radio]` (aria-label = versão) → selects nativos
  `#cartype #gearbox #doors #fuel #car_steering #motorpower #carcolor`
  (já pré-preenchidos pela placa) → `#mileage` (máscara: digitar) →
  itens de série em chips `button.olx-core-chip` com **`data-selected`**
  (clicar num marcado DESMARCA, então só entram os `false`) → detalhes
  opcionais (quitado/IPVA/único dono: o bot não marca nada) → fotos em
  `#lastStepImageInput` (**obrigatórias**, mínimo 50×50; com menos de 6
  aparece "Continuar sem adicionar") → vídeo (pulado) →
  `#body-text-area` → `#zipcode` (vem da conta) → preço: "Inserir preço
  manual" libera `#price`, e a OLX ainda oferece baixar o valor — o bot
  clica em "Continuar com R$<seu preço>". O "Continuar" desabilitado é
  `aria-disabled`, não `disabled`.
- **Cota grátis da OLX**: acabando os anúncios de carro gratuitos, o
  último passo cai em `adquirir.olx.com.br/destaques` (planos) e o
  anúncio fica em "Meus anúncios → **Acima do Limite**", NÃO publicado.
  `publicar()` reconhece essa tela, avisa e liga `publicacao_manual`
  para o anunciador não registrar nada. Foi o que aconteceu na
  calibração (a conta de teste está sem cota até 24/11/2026), então a
  publicação gratuita ponta a ponta ainda não foi vista.
- **Exclusão na OLX**: `conta.olx.com.br/anuncios` (e a aba
  `/anuncios/acima-do-limite`) lista cards
  `[data-testid="myads-ad-item"]` (`myads-ad-title-label`,
  `myads-ad-price-label`); "Excluir" abre um diálogo que **pede o
  motivo** (labels "Vendi em outra plataforma", "Desisti de vender", …,
  "Outro Motivo") antes do `button[type=submit]` "Excluir". O adaptador
  marca "Outro Motivo" — o bot não inventa motivo comercial.
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
- **Só veículos na Compra do Facebook** (set/2026, com aval do Thomas):
  o Marketplace NÃO tem busca por termo dentro de Veículos — conferido
  ao vivo: `category_id=546583916084032` (Veículos) junto com `query` é
  ignorado, `/category/vehicles?query=` e `/vehicles?query=` ignoram o
  termo, e o link "Veículos" da lateral troca o termo por "Veículos".
  Por isso a restrição é no card, em `coleta.eh_card_de_veiculo`: fica o
  card no formato do formulário de veículo ("<preço> <ano> <marca>
  <modelo>") e o card com ano no texto que não fala em imóvel nem em
  peça (carro anunciado como item comum, ex. "REPASSE - VOYAGE 1.6
  2015"); sai imóvel, peça/sucata e oferta de serviço sem ano. Card sem
  texto passa. Nas buscas reais do Thomas (Mobi/Uno/Sandero) nenhum
  carro saiu — só peça, sucata e retrovisor.
- **CPF na Compra**: `campos_do_site` separa "contato" de "cpf". Contato
  (nome/e-mail/telefone) vai para iCarros, Webmotors e Mobiauto; o CPF só
  para o **iCarros** (alguns anúncios pedem). Na Webmotors e na Mobiauto o
  formulário do vendedor NÃO pede CPF — nos dois, quem pede é o
  formulário de financiamento, que o bot não preenche —, então o campo
  some da tela. Facebook, OLX e NaPista não recebem nada disso.
- **Só o modelo basta** (`src/marcas.py`, set/2026): Webmotors, iCarros e
  Mobiauto exigem a MARCA no caminho da busca; com uma palavra só, a
  Webmotors lê "palio" como marca (`?marca1=palio`) e devolve qualquer
  carro. `marcas.separar()` põe a marca quando reconhece o modelo (tabela
  local dos modelos mais comuns — o catálogo de marcas/modelos do
  Supabase não é legível sem login), troca apelidos (vw, gm, mercedes,
  chery) pelo nome que os sites usam e, sem reconhecer nada, deixa como
  antes (1ª palavra = marca) e avisa no log. Conferido ao vivo: "palio" →
  Webmotors 47/47, iCarros 6/6 e Mobiauto 24/24 anúncios de Fiat Palio.
  Slugs compostos (onix-plus, hr-v, caoa-chery…) seguem o padrão dos
  sites, mas ainda não foram vistos na Webmotors.
- **Várias fontes por execução** (ago/2026): a tela de Compra virou
  caixas de seleção (`sites_escolhidos()`), o JSON leva `sites` (e mantém
  `site` = a primeira, para compatibilidade) e o run.py roda uma fonte
  por vez em `_executar_site`, cada uma com a sua janela e o seu
  "Prosseguir". Erro numa fonte não derruba as outras. Os campos da tela
  são a UNIÃO do que as fontes marcadas usam (`campos_dos_sites`).
- **Limite de mensagens do Facebook** (`src/limites.py`): o Marketplace
  corta o envio depois de algumas mensagens e mostra o aviso na tela
  ("atingiu o limite", "ação bloqueada", "temporariamente bloqueado",
  "rápido demais"…). `detectar_limite` reconhece o aviso, o bot PARA no
  Facebook (as outras fontes seguem) e grava a tela em
  `debug/facebook-compra` — é de lá que sai o texto exato para ampliar a
  lista. O bot não tenta contornar, não espera em loop e não troca de
  conta.
- **Faixa de preço POR veículo** (ago/2026): a tela de Compra virou uma
  tabela — cada linha é um veículo com "Preço de/até" próprio, porque um
  hatch popular e uma picape não se procuram na mesma margem. O JSON leva
  `faixas: [{produto, preco_min, preco_max}]`; `Parametros.usar_produto()`
  troca `preco_min/preco_max` para a faixa do veículo da vez (chamado no
  começo de cada volta da fila, em todas as fontes) e cai no **preço
  padrão** da tela quando a linha fica vazia — campo a campo, então dá
  para preencher só o máximo. `validar` recusa faixa invertida dizendo
  qual veículo é.
- Compra em **fila**: a tabela de veículos define a ordem e o bot
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
  (compra_mobiauto.py), `napista` (compra_napista.py, só lista),
  `leiloes` (compra_leiloes.py, só lista — Loop e Sodré Santoro) e `olx`
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
  e aparece quando o Playwright dá `launch()` no Chrome. Cuidado na
  calibração: carregar várias páginas da Webmotors em sequência rápida
  (dezenas de URLs em segundos, ou duas abas ao mesmo tempo) dispara o
  desafio mesmo no navegador aberto normalmente — espaçar as cargas.
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

## Plano de novas features (set/2026)

Ordem combinada com o Thomas, a partir das ideias das duas anotações:

1. **Publicar em grupos (Página)** — FEITO no código. A linha
   "Compartilhar nos grupos" das Configurações do post abre uma sub-tela
   com os grupos de que a PÁGINA participa e um "Concluir". Na
   calibração a resposta foi **"Nenhum grupo encontrado"**: a Página não
   entrou em nenhum grupo (e o perfil pessoal só participa de 1, sem
   relação com carros). O adaptador marca os nomes escritos na interface
   (`opcoes.grupos_facebook`), avisa quais não achou e nunca troca um
   grupo por outro parecido; a lista real de grupos sai no log na
   primeira execução com grupos de verdade. **Falta**: a Página entrar
   nos grupos para fechar a calibração — 25 grupos públicos da região
   (Niterói/São Gonçalo/RJ) foram levantados, só leitura; quem escolhe
   em quais entrar é o Thomas (o bot não entra em grupo sozinho).
2. **Filtro por palavras na Compra** — FEITO. Cada linha da tabela de
   veículos tem "Deve conter" (o anúncio precisa falar em pelo menos uma
   das palavras) e a busca inteira tem "Ignorar com" (leilão, sinistro,
   batido…). É assim que se garimpa repasse/quitação: basta uma linha
   com o termo de busca e as palavras exigidas. `anuncio_serve()` em
   parametros.py decide, e sem texto lido o anúncio PASSA (não ler não é
   motivo para descartar). Testado contra anúncios reais do Marketplace:
   o filtro separou certo, mas a busca genérica trazia CASAS e
   APARTAMENTOS — resolvido pela peneira "só veículos" da coleta (ver
   Estado atual).
3. **Portais de banco / leilão** — FEITO como fonte de Compra "só lista"
   (`src/compra_leiloes.py`, "Leilões: Loop e Sodré"). Calibrado ao vivo
   (set/2026): Loop busca em `/estoque?marca=<MARCA>&modelo=<MODELO>`
   (maiúsculas, como o autocomplete gera) e o card traz pregão, título
   com ano, km, situação e lance; Sodré busca em
   `/veiculos/lotes?term=` e `/judiciais/lotes?term=`, com o card em
   linhas (título, comitente, data, lance, ORIGEM/CONDIÇÃO — "SEGURO",
   "MÉDIA MONTA" = sinistrado —, CIDADE / UF, km). A aba Judiciais mistura
   imóvel, empilhadeira e TV, então todo lote precisa ter o modelo no
   título (`titulo_casa`). Faixa de preço vale sobre o lance; "Ignorar
   com" olha o card inteiro (ex.: "monta"). Leilão é nacional: não há
   filtro de UF. O pesquisado antes:
   Os bancos (Santander, Bradesco, BV, Pan, Itaú) **não vendem no
   próprio site**: encaminham para leiloeiro. Dois portais conferidos ao
   vivo, ambos com estoque PÚBLICO e sem login para navegar:
   `loopleiloes.com.br` (grupo Santander/Webmotors — 1828 veículos,
   busca por marca/modelo, lotes em `/leilao/<evento>/<carro>/<id>`) e
   `sodresantoro.com.br/veiculos` (843 veículos, filtros por
   querystring `?lot_category=carros`, com aba **Judiciais**, que é o
   caso "empresa que quebrou"). Venda direta de banco existe, mas é para
   lojista credenciado (CNPJ) — precisa de credenciamento antes de
   virar automação. Decisão registrada: **monitorar sim, dar lance
   não** — lance é compromisso financeiro com prazo, e um seletor errado
   viraria dinheiro perdido.
4. **Painel de chats agregados** — não começado; escopo grande, começar
   por leitura no Facebook.

## Restrições

- Não alterar a lógica do bot de Compra no Facebook (filtros/coleta/
  mensagem/timing em run.py, filtros.py, coleta.py, mensagem.py e
  config.py). Três exceções pedidas pelo Thomas: a coleta ordena por
  posição na tela, a coleta descarta o que não é veículo
  (`coleta.eh_card_de_veiculo`) e o laço para quando
  `limites.detectar_limite` reconhece o aviso de limite de mensagens do
  Facebook. A OLX vive em `src/compra_olx.py` (fluxo paralelo) e pode
  evoluir livremente.
- `python src/main.py` roda em dev; `--run-bot`, `--run-venda` e
  `--install-browser` são as flags internas.
