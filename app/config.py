"""Configurações e caminhos compartilhados do Conversor MD."""

import json
import os
from pathlib import Path

# Repositório de onde o Conversor MD baixa as próprias atualizações.
REPO = "paulodell4/conversor-md"
RAMO = "main"
URL_VERSAO = f"https://raw.githubusercontent.com/{REPO}/{RAMO}/VERSION"
URL_ZIP = f"https://github.com/{REPO}/archive/refs/heads/{RAMO}.zip"

NOME_PASTA = "Conversor MD"
NOME_SAIDA = "Convertido MD"
NOME_ORIGINAIS = "Originais"
IDIOMA_AUDIO = "pt"
PORTA_INSTANCIA = 47653          # impede dois conversores rodando ao mesmo tempo
DIAS_ENTRE_ATUALIZACOES = 7

BASE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ConversorMD"
PASTA_APP = BASE / "app"
PASTA_NODE = BASE / "node"
ARQ_ESTADO = BASE / "estado.json"
ARQ_PID = BASE / "pid.txt"
ARQ_LOG = BASE / "registro.txt"
ARQ_PYTHON = BASE / "python.txt"              # caminho do python.exe usado
ARQ_PYTHON_NOSSO = BASE / "python_nosso.txt"  # existe se o Python foi instalado por nós
ARQ_ATUALIZAR_PYTHON = BASE / "atualizar_python.txt"


def versao_app() -> str:
    for candidato in (PASTA_APP / "VERSION", Path(__file__).resolve().parent.parent / "VERSION"):
        if candidato.exists():
            return candidato.read_text(encoding="utf-8").strip()
    return "0.0.0"


def comparar_versoes(a: str, b: str) -> int:
    """-1 se a < b, 0 se iguais, 1 se a > b. Aceita 'v1.2.3', '1.2', '3.13.17'."""
    def partes(v: str) -> list[int]:
        nums = []
        for p in v.strip().lstrip("vV").split("."):
            digitos = "".join(ch for ch in p if ch.isdigit())
            nums.append(int(digitos) if digitos else 0)
        return nums + [0] * (4 - len(nums))
    pa, pb = partes(a), partes(b)
    return (pa > pb) - (pa < pb)


def area_de_trabalho() -> Path:
    """Acha a Área de Trabalho real, inclusive quando redirecionada para o OneDrive."""
    try:
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        valor, _ = winreg.QueryValueEx(chave, "Desktop")
        caminho = Path(os.path.expandvars(valor))
        if caminho.exists():
            return caminho
    except Exception:  # noqa: BLE001
        pass
    return Path.home() / "Desktop"


def ler_estado() -> dict:
    try:
        return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def gravar_estado(**valores) -> None:
    estado = ler_estado()
    estado.update(valores)
    BASE.mkdir(parents=True, exist_ok=True)
    ARQ_ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
