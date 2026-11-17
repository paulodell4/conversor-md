"""
Conversor MD: ícone na bandeja do Windows (perto do relógio).

Verde = pronto · Azul = convertendo · Amarelo = aguardando OpenWhispr · Cinza = pausado
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402

CORES = {
    "ok": (34, 139, 84),
    "convertendo": (37, 99, 235),
    "aguardando": (217, 160, 6),
    "pausado": (120, 120, 120),
    "erro": (200, 50, 50),
}


def instancia_unica():
    trava = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        trava.bind(("127.0.0.1", config.PORTA_INSTANCIA))
    except OSError:
        return None
    config.BASE.mkdir(parents=True, exist_ok=True)
    config.ARQ_PID.write_text(str(os.getpid()))
    return trava


def configurar_log() -> None:
    config.BASE.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(config.ARQ_LOG, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(handler)


def desenhar_icone(cor: tuple[int, int, int]):
    from PIL import Image, ImageDraw, ImageFont
    tam = 64
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, tam - 2, tam - 2), radius=14, fill=cor + (255,))
    try:
        fonte = ImageFont.truetype("segoeuib.ttf", 30)
    except OSError:
        try:
            fonte = ImageFont.truetype("arialbd.ttf", 30)
        except OSError:
            fonte = ImageFont.load_default()
    d.text((tam / 2, tam / 2), "MD", fill="white", font=fonte, anchor="mm")
    return img


def abrir(caminho: Path) -> None:
    if not caminho.suffix:
        caminho.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(caminho))  # type: ignore[attr-defined]
    except AttributeError:
        subprocess.Popen(["xdg-open", str(caminho)])


def main() -> None:
    trava = instancia_unica()
    if trava is None:
        return  # já está rodando
    configurar_log()

    import pystray
    from motor import Motor, localizar_openwhispr_app

    estado = {"codigo": "ok", "texto": "Iniciando..."}
    icones = {k: desenhar_icone(v) for k, v in CORES.items()}
    icone = pystray.Icon("ConversorMD", icones["ok"], "Conversor MD")

    def mudar_status(codigo: str, texto: str) -> None:
        if estado["codigo"] != codigo or estado["texto"] != texto:
            estado.update(codigo=codigo, texto=texto)
            icone.icon = icones.get(codigo, icones["ok"])
            icone.title = f"Conversor MD: {texto}"[:120]
            icone.update_menu()

    def concluido(nome: str, ok: bool, msg: str) -> None:
        try:
            icone.notify(msg, ("✓ " if ok else "⚠ ") + nome)
        except Exception:  # noqa: BLE001
            pass

    motor = Motor(ao_mudar_status=mudar_status, ao_concluir=concluido)

    def alternar_pausa(_icone, _item):
        motor.pausado = not motor.pausado
        motor.status_ocioso()

    def abrir_openwhispr(_icone, _item):
        exe = localizar_openwhispr_app()
        if exe:
            subprocess.Popen([exe])
        else:
            icone.notify("OpenWhispr não encontrado. Use 'Verificar atualizações' para reinstalar.",
                         "Conversor MD")

    def verificar_atualizacoes(_icone, _item):
        """Fecha a bandeja e roda o iniciador com atualização forçada (evita arquivos em uso)."""
        iniciar = config.PASTA_APP / "iniciar.cmd"
        if not iniciar.exists():
            icone.notify("Instalação incompleta. Rode o instalador novamente.", "Conversor MD")
            return
        icone.notify("Verificando atualizações. O Conversor MD vai reabrir em instantes.", "Conversor MD")
        subprocess.Popen(
            f'cmd.exe /c start "Conversor MD" /min "{iniciar}" --forcar',
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        sair(icone, None)

    def sair(_icone, _item):
        motor.parar.set()
        icone.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: estado["texto"], None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Abrir pasta Conversor MD", lambda i, it: abrir(motor.entrada), default=True),
        pystray.MenuItem("Abrir arquivos convertidos", lambda i, it: abrir(motor.saida)),
        pystray.MenuItem("Abrir originais", lambda i, it: abrir(motor.originais)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: "Retomar" if motor.pausado else "Pausar", alternar_pausa),
        pystray.MenuItem("Abrir OpenWhispr", abrir_openwhispr),
        pystray.MenuItem("Ver registro de atividades", lambda i, it: abrir(config.ARQ_LOG)),
        pystray.MenuItem("Verificar atualizações", verificar_atualizacoes),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Versão {config.versao_app()}", None, enabled=False),
        pystray.MenuItem("Sair", sair),
    )
    icone.menu = menu

    def checar_atualizacao_periodica():
        """Computador que fica dias sem reiniciar: atualiza sozinho uma vez por semana."""
        import time
        while not motor.parar.wait(6 * 3600):
            ultima = config.ler_estado().get("ultima_atualizacao", 0)
            ocioso = estado["codigo"] in ("ok", "pausado")
            if ocioso and time.time() - ultima > config.DIAS_ENTRE_ATUALIZACOES * 86400:
                logging.info("Atualização semanal: reiniciando pelo iniciador")
                verificar_atualizacoes(icone, None)
                return

    def ao_iniciar(ic):
        ic.visible = True
        threading.Thread(target=motor.executar, daemon=True).start()
        threading.Thread(target=checar_atualizacao_periodica, daemon=True).start()

    icone.run(setup=ao_iniciar)
    trava.close()


if __name__ == "__main__":
    main()
