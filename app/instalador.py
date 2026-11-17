"""
Instalador do Conversor MD.

    pythonw instalador.py            -> janela de instalação (usada pelo "Instalar Conversor MD.cmd")
    python  instalador.py --rotina   -> atualização semanal silenciosa (usada no login)
    python  instalador.py --rotina --forcar  -> atualização agora (menu "Verificar atualizações")
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import componentes as c  # noqa: E402
import config  # noqa: E402

log = logging.getLogger("instalador")


def configurar_log() -> None:
    config.BASE.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(config.ARQ_LOG, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(h)


# Cada passo: (título, função(avisar) -> mensagem, obrigatório?)
def passos_instalacao():
    estado = {"node_mudou": False}

    def node(avisar):
        msg, mudou = c.instalar_node(avisar)
        estado["node_mudou"] = mudou
        return msg

    return [
        ("Python", lambda avisar: c.registrar_python() + ". " + _seguro(c.verificar_atualizacao_python), True),
        ("Bibliotecas de conversão (MarkItDown, ffmpeg)", c.instalar_bibliotecas, True),
        ("Node.js (necessário para o OpenWhispr)", node, False),
        ("Ferramenta de transcrição do OpenWhispr", c.instalar_cli_openwhispr, False),
        ("Aplicativo OpenWhispr", c.instalar_openwhispr, False),
        ("Pasta Conversor MD na Área de Trabalho", lambda avisar: c.criar_pastas(), True),
        ("Início automático com o Windows", lambda avisar: c.criar_atalhos(), False),
    ]


def _seguro(func) -> str:
    try:
        return func()
    except Exception as erro:  # noqa: BLE001
        return f"(verificação de versão indisponível: {erro})"


# ------------------------------------------------------------------ rotina silenciosa

def rotina(forcar: bool) -> int:
    configurar_log()
    ultima = config.ler_estado().get("ultima_atualizacao", 0)
    if not forcar and time.time() - ultima < config.DIAS_ENTRE_ATUALIZACOES * 86400:
        return 0
    log.info("=== Verificação de atualizações ===")
    avisar = lambda texto: print("  " + texto)  # noqa: E731
    tarefas = [
        ("Conversor MD", lambda: c.atualizar_app(avisar)),
        ("Python", c.verificar_atualizacao_python),
        ("Bibliotecas", lambda: c.instalar_bibliotecas(avisar)),
    ]

    def node_e_cli():
        msg, mudou = c.instalar_node(avisar)
        return msg + ". " + c.instalar_cli_openwhispr(avisar)

    tarefas += [
        ("Node.js e ferramenta OpenWhispr", node_e_cli),
        ("OpenWhispr", lambda: c.instalar_openwhispr(avisar)),
    ]
    for nome, tarefa in tarefas:
        print(f"Verificando {nome}...")
        try:
            log.info("ATUALIZAÇÃO %s: %s", nome, tarefa())
        except Exception as erro:  # noqa: BLE001
            log.warning("ATUALIZAÇÃO %s falhou: %s", nome, erro)
    config.gravar_estado(ultima_atualizacao=time.time())
    return 0


# ------------------------------------------------------------------ janela

def janela() -> int:
    import tkinter as tk
    from tkinter import ttk

    configurar_log()
    passos = passos_instalacao()
    fila: queue.Queue = queue.Queue()

    raiz = tk.Tk()
    raiz.title("Conversor MD: instalação")
    raiz.geometry("620x560")
    raiz.resizable(False, False)
    try:
        raiz.iconbitmap(str(Path(__file__).with_name("icone.ico")))
    except Exception:  # noqa: BLE001
        pass
    raiz.configure(bg="white")
    estilo = ttk.Style()
    estilo.configure("TProgressbar", thickness=8)

    tk.Label(raiz, text="Conversor MD", font=("Segoe UI", 18, "bold"), bg="white",
             fg="#1f2937").pack(anchor="w", padx=24, pady=(20, 0))
    tk.Label(raiz, text="Instalando tudo o que é necessário. Não feche esta janela.",
             font=("Segoe UI", 10), bg="white", fg="#6b7280").pack(anchor="w", padx=24)

    quadro = tk.Frame(raiz, bg="white")
    quadro.pack(fill="x", padx=24, pady=16)
    linhas = []
    for titulo, _, _ in passos:
        f = tk.Frame(quadro, bg="white")
        f.pack(fill="x", pady=3)
        icone = tk.Label(f, text="○", width=2, font=("Segoe UI", 12), bg="white", fg="#9ca3af")
        icone.pack(side="left")
        bloco = tk.Frame(f, bg="white")
        bloco.pack(side="left", fill="x", expand=True)
        tk.Label(bloco, text=titulo, font=("Segoe UI", 10, "bold"), bg="white",
                 fg="#111827", anchor="w").pack(fill="x")
        detalhe = tk.Label(bloco, text="", font=("Segoe UI", 9), bg="white", fg="#6b7280",
                           anchor="w", justify="left", wraplength=540)
        detalhe.pack(fill="x")
        linhas.append((icone, detalhe))

    barra = ttk.Progressbar(raiz, mode="determinate", maximum=len(passos), length=572)
    barra.pack(padx=24)
    rodape = tk.Frame(raiz, bg="white")
    rodape.pack(fill="both", expand=True, padx=24, pady=12)

    def trabalhar():
        problemas = []
        for i, (titulo, func, obrigatorio) in enumerate(passos):
            fila.put(("inicio", i, "em andamento..."))
            try:
                msg = func(lambda texto, i=i: fila.put(("detalhe", i, texto)))
                fila.put(("ok", i, msg))
                log.info("INSTALAÇÃO %s: %s", titulo, msg)
            except Exception as erro:  # noqa: BLE001
                log.error("INSTALAÇÃO %s falhou: %s\n%s", titulo, erro, traceback.format_exc())
                fila.put(("erro" if obrigatorio else "aviso", i, str(erro)[:300]))
                problemas.append((titulo, obrigatorio))
                if obrigatorio:
                    fila.put(("fim", problemas))
                    return
        try:
            c.iniciar_bandeja()
        except Exception as erro:  # noqa: BLE001
            problemas.append((f"Abrir o Conversor MD ({erro})", True))
        config.gravar_estado(ultima_atualizacao=time.time(), instalado_em=time.time())
        fila.put(("fim", problemas))

    def finalizar(problemas):
        for w in rodape.winfo_children():
            w.destroy()
        criticos = [t for t, obrig in problemas if obrig]
        if criticos:
            texto = ("A instalação não foi concluída. Feche esta janela e rode o instalador de novo.\n"
                     f"Se persistir, envie o arquivo de registro ao Paulo:\n{config.ARQ_LOG}")
            cor = "#b91c1c"
        else:
            texto = (
                "Pronto! Um ícone \"MD\" verde apareceu perto do relógio do Windows.\n\n"
                "COMO USAR: arraste qualquer documento, áudio ou vídeo para a pasta\n"
                "\"Conversor MD\" na Área de Trabalho. O .md aparece em \"Convertido MD\".\n\n"
                "ÚLTIMO PASSO (só uma vez), para áudio e vídeo: abra o OpenWhispr, conclua a\n"
                "configuração inicial e, em Configurações > AI Models > Speech-to-Text, escolha\n"
                "\"Local\" e baixe um modelo multilíngue (ex.: Whisper Small ou Turbo)."
            )
            if problemas:
                texto += "\n\nAviso: áudio e vídeo podem não funcionar ainda. Os documentos funcionam."
            cor = "#065f46"
        tk.Label(rodape, text=texto, font=("Segoe UI", 9), bg="white", fg=cor,
                 justify="left", anchor="w").pack(fill="x")
        botoes = tk.Frame(rodape, bg="white")
        botoes.pack(anchor="e", pady=(10, 0))
        if not criticos:
            def abrir_ow():
                from motor import localizar_openwhispr_app
                import subprocess
                exe = localizar_openwhispr_app()
                if exe:
                    subprocess.Popen([exe])
            ttk.Button(botoes, text="Abrir OpenWhispr", command=abrir_ow).pack(side="left", padx=6)
        ttk.Button(botoes, text="Concluir", command=raiz.destroy).pack(side="left")

    def atualizar_tela():
        try:
            while True:
                item = fila.get_nowait()
                tipo = item[0]
                if tipo == "fim":
                    finalizar(item[1])
                    continue
                _, i, texto = item
                icone, detalhe = linhas[i]
                detalhe.config(text=texto)
                if tipo == "inicio":
                    icone.config(text="◐", fg="#2563eb")
                elif tipo == "ok":
                    icone.config(text="✔", fg="#16a34a")
                    barra["value"] = i + 1
                elif tipo == "aviso":
                    icone.config(text="!", fg="#d97706")
                    detalhe.config(fg="#b45309")
                    barra["value"] = i + 1
                elif tipo == "erro":
                    icone.config(text="✖", fg="#dc2626")
                    detalhe.config(fg="#b91c1c")
        except queue.Empty:
            pass
        raiz.after(150, atualizar_tela)

    threading.Thread(target=trabalhar, daemon=True).start()
    atualizar_tela()
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    if "--rotina" in sys.argv:
        sys.exit(rotina(forcar="--forcar" in sys.argv))
    sys.exit(janela())
