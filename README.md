# Clima Portugal — Fase 1

Site público e gratuito que mostra os dados de clima recolhidos localmente, atualizado todos os dias.

**Arquitetura** (100% gratuita):
- **GitHub** — guarda o código e o ficheiro `data/clima_portugal.csv` (a "base de dados").
- **`update_data.py`** — corre no seu PC (Task Scheduler), baixa só os dias novos, adiciona ao CSV e faz `git push`.
- **Streamlit Community Cloud** — lê o repositório do GitHub e publica `app.py` como site público (URL tipo `clima-portugal.streamlit.app`). Sempre que há um push, o site atualiza sozinho em segundos.

## Passo a passo

1. **Criar o repositório no GitHub**
   - Novo repositório público, ex.: `clima-portugal`.
   - Copie estes 4 ficheiros para dentro: `app.py`, `update_data.py`, `requirements.txt`, `atualizar_diario.bat`.

2. **Backfill inicial (uma vez, no seu PC)**
   - Dentro da pasta do repositório clonado localmente, rode:
     ```
     python update_data.py
     ```
   - Como ainda não existe `data/clima_portugal.csv`, ele vai baixar tudo desde 2015-01-01 até ontem para as 7 cidades (pode demorar alguns minutos). No fim, já faz o commit + push automaticamente.

3. **Publicar o site (Streamlit Community Cloud — gratuito)**
   - Entre em share.streamlit.io com a sua conta GitHub.
   - "New app" → escolha o repositório `clima-portugal`, branch `main`, ficheiro principal `app.py`.
   - Deploy. Em 1–2 minutos tem uma URL pública, ex.: `https://clima-portugal.streamlit.app`.

4. **Agendar a atualização diária**
   - Ajuste o caminho dentro de `atualizar_diario.bat` para a pasta real do repositório.
   - Abra o Agendador de Tarefas do Windows → Criar Tarefa → gatilho diário (ex. 07:00) → ação: executar `atualizar_diario.bat`.
   - Certifique-se de que o `git` local está autenticado (token/SSH) para conseguir dar `push` sem pedir senha.

Cada execução do `update_data.py` só baixa os dias em falta por cidade (não repete o histórico), acrescenta ao CSV e envia para o GitHub — o site em `app.py` puxa sempre a versão mais recente do repositório.

## Próximas fases (para discutirmos depois)
- Trocar CSV por Parquet/SQLite se o ficheiro crescer muito.
- Adicionar mais cidades ou variáveis (humidade, vento).
- Comparação ano a ano, alertas de anomalias, exportação em PDF.
