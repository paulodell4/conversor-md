"""
Motor do Conversor MD: esteira de conversão para Markdown.

Área de Trabalho\\Conversor MD     <- arquivos entram aqui
    Convertido MD\\                <- .md gerados
    Originais\\                    <- originais já convertidos

Documentos -> MarkItDown. Áudio e vídeo -> OpenWhispr (local, no próprio computador).
Falhas e arquivos vazios ficam na entrada; áudio/vídeo esperam o OpenWhispr abrir.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import config

INTERVALO_SEGUNDOS = 10
ESPERA_ESTABILIDADE = 5
EXT_DOCUMENTOS = {
    ".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".msg",
    ".html", ".htm", ".csv", ".json", ".xml", ".epub", ".txt",
    ".jpg", ".jpeg", ".png", ".zip",
}
EXT_AUDIO = {".ogg", ".opus", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".wma", ".amr"}
EXT_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v", ".3gp", ".mpeg", ".mpg"}
EXT_MIDIA = EXT_AUDIO | EXT_VIDEO
EXTENSOES = EXT_DOCUMENTOS | EXT_MIDIA
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

log = logging.getLogger("conversor")


class OpenWhisprIndisponivel(Exception):
    """App fechado, sem modelo ou CLI ausente: o arquivo espera e é tentado de novo."""


# ------------------------------------------------------------------ utilidades

def ambiente_com_node() -> dict:
    env = os.environ.copy()
    if config.PASTA_NODE.exists():
        env["PATH"] = str(config.PASTA_NODE) + os.pathsep + env.get("PATH", "")
    return env


def localizar_openwhispr_cli() -> str | None:
    for candidato in (
        config.PASTA_NODE / "openwhispr.cmd",
        Path(os.environ.get("APPDATA", "")) / "npm" / "openwhispr.cmd",
    ):
        if candidato.exists():
            return str(candidato)
    return shutil.which("openwhispr")


def localizar_openwhispr_app() -> str | None:
    caminho = config.ler_estado().get("openwhispr_exe")
    if caminho and Path(caminho).exists():
        return caminho
    for pasta in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OpenWhispr",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "openwhispr",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "OpenWhispr",
    ):
        exe = pasta / "OpenWhispr.exe"
        if exe.exists():
            return str(exe)
    return None


def localizar_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return shutil.which("ffmpeg")


def formatar_duracao(segundos: float | None) -> str:
    if not segundos:
        return "-"
    s = int(round(float(segundos)))
    if s >= 3600:
        return f"{s // 3600:d}h{s % 3600 // 60:02d}min{s % 60:02d}s"
    return f"{s // 60:d}min{s % 60:02d}s"


def em_paragrafos(texto: str, frases_por_paragrafo: int = 5) -> str:
    frases = re.split(r"(?<=[.!?])\s+", " ".join(texto.split()))
    blocos = [" ".join(frases[i:i + frases_por_paragrafo])
              for i in range(0, len(frases), frases_por_paragrafo)]
    return "\n\n".join(b for b in blocos if b)


def caminho_livre(caminho: Path) -> Path:
    """Se já existir, devolve 'nome (2).ext', 'nome (3).ext'..."""
    if not caminho.exists():
        return caminho
    n = 2
    while True:
        candidato = caminho.with_name(f"{caminho.stem} ({n}){caminho.suffix}")
        if not candidato.exists():
            return candidato
        n += 1


# ------------------------------------------------------------------ áudio/vídeo

def extrair_audio(origem: Path, pasta_tmp: Path) -> tuple[Path, float | None]:
    """Converte qualquer áudio/vídeo para WAV 16 kHz mono (formato ideal do Whisper)."""
    ffmpeg = localizar_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg não encontrado; reinstale o Conversor MD")
    wav = pasta_tmp / "audio.wav"
    r = subprocess.run(
        [ffmpeg, "-y", "-i", str(origem), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
        creationflags=SEM_JANELA,
    )
    if r.returncode != 0 or not wav.exists():
        if "does not contain any stream" in r.stderr or "no audio" in r.stderr.lower():
            raise RuntimeError("o arquivo não tem trilha de áudio")
        raise RuntimeError("não foi possível ler o arquivo: " + r.stderr.strip()[-300:])
    duracao = None
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if m:
        h, mi, s = m.groups()
        duracao = int(h) * 3600 + int(mi) * 60 + float(s)
    return wav, duracao


def transcrever_openwhispr(wav: Path) -> dict:
    cli = localizar_openwhispr_cli()
    if not cli:
        raise OpenWhisprIndisponivel("ferramenta do OpenWhispr não instalada; reinstale o Conversor MD")
    r = subprocess.run(
        [cli, "transcribe", str(wav), "--local", "--language", config.IDIOMA_AUDIO, "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
        creationflags=SEM_JANELA, env=ambiente_com_node(),
    )
    saida = r.stdout.strip()
    if r.returncode != 0:
        erro = (r.stderr or saida).strip()
        # O áudio já foi validado pelo ffmpeg; erro aqui é do app (fechado, sem modelo...).
        if re.search(r"bridge|not running|ECONNREFUSED|desktop app|unreachable", erro, re.I):
            raise OpenWhisprIndisponivel("OpenWhispr fechado")
        raise OpenWhisprIndisponivel("OpenWhispr respondeu com erro: " + erro[-300:])
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        dados = {"text": saida}
    if isinstance(dados, dict) and isinstance(dados.get("data"), dict):
        dados = dados["data"]
    if not isinstance(dados, dict):
        dados = {"text": str(dados)}
    texto = dados.get("text") or dados.get("transcript") or dados.get("transcription") or ""
    dados["text"] = str(texto).strip()
    return dados


def converter_midia(origem: Path) -> str:
    if not localizar_openwhispr_cli():
        raise OpenWhisprIndisponivel("ferramenta do OpenWhispr não instalada; reinstale o Conversor MD")
    tipo = "Vídeo" if origem.suffix.lower() in EXT_VIDEO else "Áudio"
    with tempfile.TemporaryDirectory(prefix="conversor_md_") as tmp:
        wav, duracao = extrair_audio(origem, Path(tmp))
        dados = transcrever_openwhispr(wav)
    if not dados["text"]:
        return ""
    duracao = dados.get("duration") or duracao
    modelo = dados.get("model") or "modelo selecionado no app"
    return (
        f"# Transcrição: {origem.name}\n\n"
        f"| | |\n|---|---|\n"
        f"| **Arquivo** | {origem.name} |\n"
        f"| **Tipo** | {tipo} |\n"
        f"| **Duração** | {formatar_duracao(duracao)} |\n"
        f"| **Idioma** | {dados.get('language') or config.IDIOMA_AUDIO} |\n"
        f"| **Transcrito em** | {datetime.now():%d/%m/%Y %H:%M} |\n"
        f"| **Ferramenta** | OpenWhispr, local ({modelo}) |\n\n"
        f"> Transcrição automática, sem revisão humana. "
        f"Pode conter erros em nomes, números e termos técnicos.\n\n"
        f"---\n\n{em_paragrafos(dados['text'])}\n"
    )


# ------------------------------------------------------------------ motor

class Motor:
    """Vigia a pasta e converte. Callbacks permitem que a bandeja mostre o status."""

    def __init__(
        self,
        pasta_entrada: Path | None = None,
        ao_mudar_status: Callable[[str, str], None] | None = None,
        ao_concluir: Callable[[str, bool, str], None] | None = None,
    ):
        self.entrada = pasta_entrada or (config.area_de_trabalho() / config.NOME_PASTA)
        self.saida = self.entrada / config.NOME_SAIDA
        self.originais = self.entrada / config.NOME_ORIGINAIS
        self.internas = (self.saida, self.originais)
        self.ao_mudar_status = ao_mudar_status or (lambda estado, texto: None)
        self.ao_concluir = ao_concluir or (lambda nome, ok, msg: None)
        self.pausado = False
        self.parar = threading.Event()
        self.falhas: dict[Path, float] = {}
        self.mover_pendente: set[Path] = set()
        self.aguardando_openwhispr: set[Path] = set()
        self._pausa_openwhispr_ate = 0.0
        self._ultima_abertura_openwhispr = 0.0
        self._md = None

    # -- estrutura
    def preparar_pastas(self) -> None:
        for p in (self.entrada, *self.internas):
            p.mkdir(parents=True, exist_ok=True)

    @property
    def markitdown(self):
        if self._md is None:
            from markitdown import MarkItDown
            self._md = MarkItDown(enable_plugins=False)
        return self._md

    def nome_md(self, origem: Path) -> Path:
        relativo = origem.relative_to(self.entrada)
        homonimos = [f for f in origem.parent.glob(origem.stem + ".*")
                     if f != origem and f.suffix.lower() in EXTENSOES]
        nome = (f"{origem.stem} ({origem.suffix[1:].lower()}).md" if homonimos
                else f"{origem.stem}.md")
        return self.saida / relativo.parent / nome

    def eh_candidato(self, origem: Path) -> bool:
        if origem.suffix.lower() not in EXTENSOES or origem.name.startswith(("~$", ".")):
            return False
        if any(p == origem.parent or p in origem.parents for p in self.internas):
            return False
        mtime = origem.stat().st_mtime
        if time.time() - mtime < ESPERA_ESTABILIDADE:
            return False
        return self.falhas.get(origem) != mtime

    def mover_original(self, origem: Path) -> None:
        relativo = origem.relative_to(self.entrada)
        destino = caminho_livre(self.originais / relativo)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origem), str(destino))
            self.mover_pendente.discard(origem)
            self._limpar_subpastas_vazias(origem.parent)
        except OSError as erro:
            self.mover_pendente.add(origem)
            log.warning("EM USO   %s (convertido; será movido quando for fechado: %s)", relativo, erro)

    def _limpar_subpastas_vazias(self, pasta: Path) -> None:
        while pasta != self.entrada and self.entrada in pasta.parents:
            try:
                pasta.rmdir()
            except OSError:
                return
            pasta = pasta.parent

    def _abrir_openwhispr(self) -> None:
        """Se o app estiver fechado, abre-o (no máximo a cada 5 minutos)."""
        if time.time() - self._ultima_abertura_openwhispr < 300:
            return
        exe = localizar_openwhispr_app()
        if exe:
            self._ultima_abertura_openwhispr = time.time()
            try:
                subprocess.Popen([exe], creationflags=SEM_JANELA)
                log.info("OpenWhispr estava fechado; abrindo o app automaticamente")
            except OSError as erro:
                log.warning("Não foi possível abrir o OpenWhispr: %s", erro)

    # -- conversão
    def processar(self, origem: Path) -> None:
        relativo = origem.relative_to(self.entrada)
        alvo = self.nome_md(origem)
        eh_midia = origem.suffix.lower() in EXT_MIDIA
        if eh_midia and time.time() < self._pausa_openwhispr_ate:
            return

        self.ao_mudar_status("convertendo", f"Convertendo {origem.name}...")
        try:
            texto = converter_midia(origem) if eh_midia else self.markitdown.convert(str(origem)).markdown
        except OpenWhisprIndisponivel as aviso:
            self._pausa_openwhispr_ate = time.time() + 60
            if origem not in self.aguardando_openwhispr:
                self.aguardando_openwhispr.add(origem)
                log.warning("AGUARDANDO %s (%s)", relativo, aviso)
                self.ao_concluir(origem.name, False,
                                 "Aguardando o OpenWhispr para transcrever. Abrindo o app...")
            self._abrir_openwhispr()
            return
        except Exception as erro:  # noqa: BLE001
            self.falhas[origem] = origem.stat().st_mtime
            log.error("FALHOU   %s -> %s", relativo, erro)
            self.ao_concluir(origem.name, False, f"Não foi possível converter: {erro}")
            return

        self.aguardando_openwhispr.discard(origem)
        if not texto.strip():
            self.falhas[origem] = origem.stat().st_mtime
            motivo = "sem fala reconhecível" if eh_midia else "sem texto, provável PDF escaneado"
            log.warning("VAZIO    %s (%s; mantido na entrada)", relativo, motivo)
            self.ao_concluir(origem.name, False, f"Arquivo {motivo}. Ficou na pasta de entrada.")
            return

        self.falhas.pop(origem, None)
        if alvo.exists() and alvo.read_text(encoding="utf-8", errors="ignore") == texto:
            log.info("IGUAL    %s (já convertido antes; original movido)", relativo)
        else:
            destino = caminho_livre(alvo)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
            log.info("OK       %s -> %s", relativo, destino.relative_to(self.saida))
        self.mover_original(origem)
        self.ao_concluir(origem.name, True, "Convertido para Markdown")

    def varrer(self) -> None:
        for origem in list(self.mover_pendente):
            if origem.exists():
                self.mover_original(origem)
            else:
                self.mover_pendente.discard(origem)
        for arquivo in sorted(self.entrada.rglob("*")):
            if self.parar.is_set() or self.pausado:
                return
            try:
                if arquivo.is_file() and arquivo not in self.mover_pendente and self.eh_candidato(arquivo):
                    self.processar(arquivo)
            except OSError as erro:
                log.warning("IGNORADO %s (%s)", arquivo, erro)

    def status_ocioso(self) -> None:
        if self.pausado:
            self.ao_mudar_status("pausado", "Pausado")
        elif any(p.exists() for p in self.aguardando_openwhispr):
            self.ao_mudar_status("aguardando", "Aguardando o OpenWhispr abrir")
        else:
            self.aguardando_openwhispr.clear()
            self.ao_mudar_status("ok", "Pronto: arraste arquivos para a pasta Conversor MD")

    def executar(self) -> None:
        self.preparar_pastas()
        log.info("Iniciado (versão %s). Vigiando: %s", config.versao_app(), self.entrada)
        while not self.parar.is_set():
            if not self.pausado:
                try:
                    self.preparar_pastas()
                    self.varrer()
                except Exception as erro:  # noqa: BLE001
                    log.exception("Erro inesperado na varredura: %s", erro)
            self.status_ocioso()
            self.parar.wait(INTERVALO_SEGUNDOS)
