# Conversor MD

Uma pasta na Área de Trabalho que converte para **Markdown (.md)** tudo o que você colocar nela:

- **Documentos:** PDF, Word, Excel, PowerPoint, e-mails do Outlook (.msg), HTML, CSV, TXT, EPUB e ZIP (via [MarkItDown](https://github.com/microsoft/markitdown))
- **Áudio e vídeo:** áudios do WhatsApp (.ogg/.opus), MP3, M4A, WAV, MP4, MOV e outros. A transcrição é feita pelo [OpenWhispr](https://github.com/OpenWhispr/openwhispr) **no próprio computador**: nada é enviado para a internet e não há custo.

Uso interno da Baraldi Advocacia.

---

## Como instalar (só uma vez)

1. Baixe o arquivo **[Instalar Conversor MD.cmd](../../raw/main/Instalar%20Conversor%20MD.cmd)**. Se o navegador abrir o texto do arquivo, use **Ctrl+S** para salvar.
2. Dê **dois cliques** no arquivo baixado.
   - Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**.
3. Aguarde. O instalador cuida de tudo sozinho:
   - instala o **Python**, se o computador não tiver;
   - instala o **OpenWhispr** e as ferramentas de conversão;
   - cria a pasta **Conversor MD** na Área de Trabalho;
   - coloca o ícone **MD** perto do relógio do Windows.
4. **Último passo, só uma vez, para áudio e vídeo:** abra o **OpenWhispr**, faça a configuração inicial e, em
   *Configurações › AI Models › Speech-to-Text*, escolha **Local** e baixe um modelo multilíngue
   (por exemplo, *Whisper Small* ou *Turbo*).

## Como usar

Arraste o arquivo para a pasta **Conversor MD** na Área de Trabalho. Pronto.

```
Conversor MD\            ← solte os arquivos aqui (a pasta se esvazia sozinha)
├── Convertido MD\       ← os arquivos .md
└── Originais\           ← os originais, guardados depois da conversão
```

Uma notificação avisa quando cada arquivo termina. O ícone **MD** perto do relógio mostra o estado:

| Cor | Significado |
|---|---|
| 🟢 Verde | Pronto |
| 🔵 Azul | Convertendo |
| 🟡 Amarelo | Aguardando o OpenWhispr abrir (ele é aberto automaticamente) |
| ⚪ Cinza | Pausado |

Clique com o botão direito no ícone para: abrir as pastas, pausar, ver o registro de atividades ou verificar atualizações.

**Quando o arquivo não é convertido,** ele fica na pasta de entrada. Os casos mais comuns são PDF escaneado (sem texto), arquivo com senha e vídeo sem som. O motivo aparece na notificação e no registro.

## Atualizações

Tudo se atualiza sozinho, uma vez por semana, quando o computador é ligado: o Conversor MD, as bibliotecas, a ferramenta do OpenWhispr e o Python instalado por ele. O Python que já existia no computador antes não é alterado, para não afetar outros programas. O OpenWhispr também se atualiza pelo próprio app.

## Desinstalar

Menu Iniciar › **Conversor MD** › **Desinstalar Conversor MD**. A pasta da Área de Trabalho e os arquivos convertidos são mantidos.

---

### Para quem mantém o projeto

- Para publicar uma versão nova: altere o código, **aumente o número em `VERSION`** e envie para o ramo `main`. Os computadores recebem a atualização em até 7 dias, ou na hora pelo menu "Verificar atualizações".
- Instalação: `%LOCALAPPDATA%\ConversorMD` (registro de atividades em `registro.txt`).
- Estrutura: `app/motor.py` (conversão), `app/bandeja.py` (ícone), `app/instalador.py` + `app/componentes.py` (instalação e atualizações), `app/iniciar.cmd` (executado no login).
