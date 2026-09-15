# src/ui_execucao.py
"""
O que as duas telas mostram em volta de uma execução do bot:

- `nivel_da_linha()`: lê uma linha que o bot imprimiu e diz se é info,
  sucesso, aviso ou erro (o bot já usa prefixos como [erro], [aviso],
  [pulado]; a espera pelo botão imprime "…clique em 'Prosseguir'");
- `LogExecucao`: log em linha do tempo — hora, ícone colorido pelo nível
  e o texto sem pintar a linha inteira —, com Copiar e Limpar e rolagem
  automática só quando o usuário já está no fim;
- `BarraAcoes`: faixa fixa no rodapé com o MODO TESTE em destaque, o
  estado da execução e Prosseguir / Parar / Rodar, que habilitam conforme
  o estado ("parado", "rodando", "aguardando");
- `ResumoExecucao`: cartão que confere o que vai rodar antes do Rodar.
"""
import re
import time
import tkinter as tk
from tkinter import ttk

import ui_tema
from ui_componentes import Cartao, Interruptor, estilo_moldura, icone

C = ui_tema.CORES

_ERRO = re.compile(r"\b(traceback|exception|error)\b", re.IGNORECASE)


def nivel_da_linha(texto):
    """'info', 'sucesso', 'aviso', 'erro', 'titulo' ou None (linha vazia)."""
    t = (texto or "").strip()
    if not t:
        return None
    baixo = t.lower()
    if t.startswith(("#####", "===")):
        return "titulo"
    if (baixo.startswith(("[erro]", "[não excluído]", "erro", "não dá pra rodar"))
            or _ERRO.search(t) or "falha" in baixo):
        return "erro"
    if (baixo.startswith(("[aviso]", "[pulado]", "[ignorado]", "[aguardando"))
            or "prosseguir'" in baixo or "aguardando" in baixo
            or "limitou" in baixo or "verificação" in baixo
            or baixo.startswith(("marque", "informe"))):
        return "aviso"
    if (baixo.startswith(("ok", "publicado:", "excluído:", "concluído",
                          "sinal enviado"))
            or "mensagem enviada" in baixo or "enviada com sucesso" in baixo):
        return "sucesso"
    return "info"


def pede_prosseguir(texto):
    """A linha é o bot parado esperando o botão Prosseguir?"""
    baixo = (texto or "").lower()
    return "prosseguir'" in baixo or "botão 'prosseguir'" in baixo


# ------------------------------------------------------------------ log
_NIVEIS = {
    "info": ("info", C["secundaria"]),
    "sucesso": ("ok", C["sucesso"]),
    "aviso": ("aviso", C["aviso"]),
    "erro": ("fechar", C["erro"]),
}


class LogExecucao(Cartao):
    """Cartão do log. `adicionar(texto)` aceita uma ou várias linhas."""

    VAZIO = "Nenhuma execução ainda. Clique em Rodar para começar."

    def __init__(self, pai, titulo="Log da execução", altura=12):
        super().__init__(pai, titulo)
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        self.selo_vivo = ui_tema.selo(self.acoes, "Ao vivo", "sucesso", ponto=True)
        ttk.Button(self.acoes, text="Copiar", style="FantasmaCartao.TButton",
                   cursor="hand2", command=self.copiar).pack(side="right")
        ttk.Button(self.acoes, text="Limpar", style="FantasmaCartao.TButton",
                   cursor="hand2", command=self.limpar).pack(side="right")

        console = ttk.Frame(self.corpo, style=estilo_moldura(
            pai, C["fundo"], C["borda"], C["cartao"], raio=8),
            padding=(px(4), px(4)))
        console.pack(fill="both", expand=True)
        console.columnconfigure(0, weight=1)
        console.rowconfigure(0, weight=1)
        self.texto = tk.Text(
            console, height=altura, wrap="word", bg=C["fundo"], fg=C["texto"],
            relief="flat", borderwidth=0, highlightthickness=0,
            font=(ui_tema.FONTE, 10), padx=px(12), pady=px(8),
            spacing1=px(3), spacing3=px(3), cursor="arrow",
            selectbackground=C["primaria_borda"], selectforeground=C["texto"],
            insertwidth=0)
        barra = ttk.Scrollbar(console, orient="vertical",
                              command=self.texto.yview)
        self.texto.configure(yscrollcommand=barra.set)
        self.texto.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")

        recuo = px(96)
        self.texto.tag_configure("hora", foreground=C["placeholder"],
                                 font=(ui_tema.FONTE_MONO, 9))
        self.texto.tag_configure("linha", lmargin2=recuo)
        self.texto.tag_configure("titulo", font=(ui_tema.FONTE_FORTE, 10),
                                 foreground=C["texto"], spacing1=px(10))
        self.texto.tag_configure("vazio", foreground=C["placeholder"],
                                 justify="center", spacing1=px(30))
        for nivel, (_, cor) in _NIVEIS.items():
            self.texto.tag_configure(f"ic_{nivel}", foreground=cor,
                                     font=(ui_tema.FONTE_ICONES, 9))
        self.texto.tag_configure("msg_erro", foreground=C["erro_texto"])
        # só leitura, mas com seleção e Ctrl+C
        self.texto.bind("<Key>", lambda e: None if (e.state & 4) else "break")
        self._vazio = False
        self.limpar()

    def ao_vivo(self, ligado):
        if ligado:
            self.selo_vivo.pack(side="right", padx=(0, ui_tema.px(self, 8)))
        else:
            self.selo_vivo.pack_forget()

    def limpar(self):
        self.texto.delete("1.0", "end")
        self.texto.insert("end", self.VAZIO, "vazio")
        self._vazio = True

    def copiar(self):
        if self._vazio:
            return
        conteudo = self.texto.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(conteudo)

    def adicionar(self, texto):
        if self._vazio:
            self.texto.delete("1.0", "end")
            self._vazio = False
        no_fim = self.texto.yview()[1] >= 0.999
        for linha in str(texto).splitlines():
            nivel = nivel_da_linha(linha)
            if nivel is None:
                continue
            fim_atual = self.texto.index("end-1c")
            if fim_atual != "1.0":
                self.texto.insert("end", "\n")
            if nivel == "titulo":
                limpo = linha.strip().strip("#=").strip()
                self.texto.insert("end", limpo, ("titulo", "linha"))
                continue
            glifo, _ = _NIVEIS[nivel]
            self.texto.insert("end", time.strftime("%H:%M:%S") + "   ",
                              ("hora", "linha"))
            self.texto.insert("end", ui_tema.ICONES[glifo],
                              (f"ic_{nivel}", "linha"))
            self.texto.insert("end", "   " + linha.strip(),
                              ("linha", "msg_erro") if nivel == "erro"
                              else ("linha",))
        if no_fim:
            self.texto.see("end")


# --------------------------------------------------------- barra de ações
class BarraAcoes(tk.Frame):
    """Rodapé fixo: modo teste + estado + Prosseguir / Parar / Rodar."""

    def __init__(self, pai, var_teste, rodar, prosseguir, parar, status,
                 verbo="envia"):
        super().__init__(pai, bg=C["cartao"])
        px = lambda v: ui_tema.px(pai, v)  # noqa: E731
        self.var_teste, self.status, self.verbo = var_teste, status, verbo
        tk.Frame(self, bg=C["borda"], height=1).pack(fill="x", side="top")
        interno = tk.Frame(self, bg=C["cartao"], padx=px(24), pady=px(12))
        interno.pack(fill="x")
        interno.columnconfigure(1, weight=1)

        # ---- modo teste: é a proteção contra envio real sem querer
        self.bloco_teste = ttk.Frame(interno, padding=(px(12), px(8)))
        self.bloco_teste.grid(row=0, column=0, sticky="w")
        self.interruptor = Interruptor(self.bloco_teste, var_teste,
                                       comando=self._teste_mudou)
        self.interruptor.grid(row=0, column=0, rowspan=2, padx=(0, px(10)))
        self.lbl_teste = tk.Label(self.bloco_teste, font=(ui_tema.FONTE_FORTE, 10),
                                  anchor="w", borderwidth=0)
        self.lbl_teste.grid(row=0, column=1, sticky="w")
        self.lbl_teste_sub = tk.Label(self.bloco_teste, font=(ui_tema.FONTE, 9),
                                      anchor="w", borderwidth=0)
        self.lbl_teste_sub.grid(row=1, column=1, sticky="w")
        for w in (self.lbl_teste, self.lbl_teste_sub):
            w.bind("<Button-1>", self.interruptor.alternar)
            w.configure(cursor="hand2")

        # ---- estado da execução
        estado = tk.Frame(interno, bg=C["cartao"])
        estado.grid(row=0, column=1, sticky="we", padx=px(20))
        self.ponto = tk.Label(estado, text="●", font=(ui_tema.FONTE, 10),
                              bg=C["cartao"], borderwidth=0)
        self.ponto.pack(side="left", padx=(0, px(8)))
        self.lbl_estado = tk.Label(estado, font=(ui_tema.FONTE_FORTE, 10),
                                   bg=C["cartao"], fg=C["texto"], borderwidth=0)
        self.lbl_estado.pack(side="left")
        self.lbl_status = tk.Label(estado, textvariable=status,
                                   font=(ui_tema.FONTE, 9), bg=C["cartao"],
                                   fg=C["texto_suave"], anchor="w",
                                   justify="left", borderwidth=0)
        self.lbl_status.pack(side="left", padx=(px(10), 0), fill="x",
                             expand=True)
        estado.bind("<Configure>", lambda e: self.lbl_status.configure(
            wraplength=max(120, e.width - px(170))), add="+")
        status.trace_add("write", lambda *_: self.after_idle(self._cor_status))

        # ---- botões (Rodar, a ação principal, na ponta direita)
        botoes = tk.Frame(interno, bg=C["cartao"])
        botoes.grid(row=0, column=2, sticky="e")
        self.bt_prosseguir = ttk.Button(botoes, text="Prosseguir  →",
                                        style="Secundario.TButton",
                                        cursor="hand2", command=prosseguir)
        self.bt_prosseguir.pack(side="left", padx=(0, px(8)))
        self.bt_parar = ttk.Button(botoes, text="■  Parar",
                                   style="Perigo.TButton", cursor="hand2",
                                   command=parar)
        self.bt_parar.pack(side="left", padx=(0, px(8)))
        self.bt_rodar = ttk.Button(botoes, text="▶  Rodar",
                                   style="Primario.TButton", cursor="hand2",
                                   command=rodar)
        self.bt_rodar.pack(side="left")

        self.estado = None
        self.definir_estado("parado")
        self._teste_mudou()

    def _teste_mudou(self):
        if self.var_teste.get():
            fundo, borda = C["primaria_suave"], C["primaria_borda"]
            titulo, cor = "Modo teste ativado", C["primaria_texto"]
            sub = f"Preenche os campos, mas não {self.verbo}."
        else:
            fundo, borda = "#fffbeb", "#fcd34d"
            titulo, cor = "Modo real", C["aviso_texto"]
            sub = ("As mensagens serão enviadas de verdade."
                   if self.verbo == "envia"
                   else "Os anúncios serão publicados de verdade.")
        self.bloco_teste.configure(style=estilo_moldura(self, fundo, borda,
                                                        C["cartao"], raio=10))
        self.interruptor.fundo(fundo)
        self.lbl_teste.configure(text=titulo, fg=cor, bg=fundo)
        self.lbl_teste_sub.configure(text=sub, fg=C["texto_suave"], bg=fundo)

    def _cor_status(self):
        nivel = nivel_da_linha(self.status.get())
        self.lbl_status.configure(fg={"erro": C["erro_texto"],
                                      "aviso": C["aviso_texto"]}.get(
            nivel, C["texto_suave"]))

    def definir_estado(self, estado):
        """'parado', 'rodando' ou 'aguardando' (bot esperando Prosseguir)."""
        if estado == self.estado:
            return
        self.estado = estado
        textos = {"parado": ("Pronto", C["borda_forte"]),
                  "rodando": ("Executando", C["sucesso"]),
                  "aguardando": ("Aguardando sua confirmação", C["aviso"])}
        texto, cor = textos[estado]
        self.lbl_estado.configure(text=texto)
        self.ponto.configure(fg=cor)
        parado = estado == "parado"
        self.bt_rodar.state(["!disabled"] if parado else ["disabled"])
        self.bt_parar.state(["disabled"] if parado else ["!disabled"])
        self.bt_parar.configure(style="Perigo.TButton" if parado
                                else "PerigoCheio.TButton")
        self.bt_prosseguir.state(["disabled"] if parado else ["!disabled"])
        self.bt_prosseguir.configure(style="Primario.TButton"
                                     if estado == "aguardando"
                                     else "Secundario.TButton")
        # durante a execução o modo já foi gravado: trocar não teria efeito
        self.interruptor.ativo(parado)


# ---------------------------------------------------------------- resumo
class ResumoExecucao(Cartao):
    """Cartão "Resumo": rótulo à esquerda, valor à direita."""

    def __init__(self, pai, titulo="Resumo"):
        super().__init__(pai, titulo)
        self.corpo.columnconfigure(1, weight=1)
        self._valores = {}

    def linha(self, chave, rotulo, nome_icone):
        px = lambda v: ui_tema.px(self, v)  # noqa: E731
        n = len(self._valores)
        icone(self.corpo, nome_icone, 11, C["texto_suave"]).grid(
            row=n, column=0, sticky="nw", padx=(0, px(10)), pady=px(5))
        ttk.Label(self.corpo, text=rotulo, style="Ajuda.TLabel").grid(
            row=n, column=1, sticky="nw", pady=px(5))
        valor = tk.Frame(self.corpo, bg=C["cartao"])
        valor.grid(row=n, column=2, sticky="ne", pady=px(3))
        self._valores[chave] = valor

    def valor(self, chave, texto, tipo=None, detalhe=None):
        """Texto do valor; com `tipo`, vira selo (ex.: modo Teste/Real)."""
        quadro = self._valores[chave]
        assinatura = (texto, tipo, detalhe)
        if getattr(quadro, "_assinatura", None) == assinatura:
            return
        quadro._assinatura = assinatura
        for filho in quadro.winfo_children():
            filho.destroy()
        if tipo:
            ui_tema.selo(quadro, texto, tipo).pack(anchor="e")
        else:
            tk.Label(quadro, text=texto, bg=C["cartao"], fg=C["texto"],
                     font=(ui_tema.FONTE_FORTE, 10), anchor="e",
                     justify="right").pack(anchor="e")
        if detalhe:
            tk.Label(quadro, text=detalhe, bg=C["cartao"], fg=C["texto_suave"],
                     font=(ui_tema.FONTE, 9), anchor="e", justify="right",
                     wraplength=ui_tema.px(self, 220)).pack(anchor="e")
