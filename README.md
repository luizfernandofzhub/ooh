# Clima Portugal — Fase 1

Site público e gratuito que mostra os dados de clima recolhidos localmente, atualizado todos os dias.

**Arquitetura** (100% gratuita, sem precisar instalar `git`):
- **GitHub** — guarda o código e o ficheiro `data/clima_portugal.csv` (a "base de dados").
- **`update_data.py`** — corre no seu PC (Task Scheduler), baixa só os dias novos e envia o CSV atualizado direto para o GitHub **via API** (usa só `requests`, que já é uma dependência do projeto — não precisa do programa `git.exe` instalado).
- **Streamlit Community Cloud** — lê o repositório do GitHub e publica `app.py` como site público. Sempre que o CSV é atualizado, o site atualiza sozinho.

## Passo a passo

1. **Repositório no GitHub** — já criado (`ooh`, público).
   - Pelo site do GitHub, use **Add file → Upload files** para subir `app.py`, `requirements.txt` e `atualizar_diario.bat` diretamente (arrastar e soltar) — não precisa de terminal nem de `git` para isso.

2. **Criar um token de acesso (para o script conseguir enviar dados)**
   - Em github.com → foto do perfil → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
   - Repository access: **Only select repositories** → escolha `ooh`.
   - Permissions: **Contents → Read and write**.
   - Gere e copie o token (só aparece uma vez).

3. **Guardar o token no seu PC (sem precisar de admin)**
   - No Prompt de Comando: `setx GITHUB_TOKEN "cole_o_token_aqui"`.
   - Feche e reabra o terminal (o `setx` só aplica em janelas novas).

4. **Preparar a pasta local e as dependências**
   - Crie uma pasta qualquer no seu PC (não precisa clonar nada) e coloque `update_data.py` e `requirements.txt` dentro.
   - `python -m pip install -r requirements.txt` (use `python -m pip`, não só `pip`, por causa das restrições do PC corporativo).

5. **Backfill inicial**
   - Rode `python update_data.py`. Ele baixa o histórico completo (2015 até ontem, 7 cidades — pode demorar alguns minutos) e envia o CSV para o GitHub via API automaticamente.
   - Confirme no GitHub que `data/clima_portugal.csv` apareceu dentro do repositório.

6. **Publicar o site (Streamlit Community Cloud — gratuito)**
   - Entre em share.streamlit.io com a sua conta GitHub.
   - "New app" → repositório `ooh`, branch `main`, ficheiro principal `app.py`.
   - Deploy. Em 1–2 minutos tem uma URL pública.

7. **Agendar a atualização diária**
   - Ajuste o caminho dentro de `atualizar_diario.bat` para a pasta onde colocou `update_data.py`.
   - Agendador de Tarefas do Windows → Criar Tarefa → gatilho diário → ação: executar `atualizar_diario.bat`.
   - Como o `GITHUB_TOKEN` foi salvo com `setx`, ele fica disponível para as tarefas agendadas também.

Cada execução do `update_data.py` só baixa os dias em falta por cidade, acrescenta ao CSV local e envia a versão atualizada para o GitHub — o site em `app.py` puxa sempre a versão mais recente.

## Próximas fases (para discutirmos depois)
- Trocar CSV por Parquet/SQLite se o ficheiro crescer muito.
- Adicionar mais cidades ou variáveis (humidade, vento).
- Comparação ano a ano, alertas de anomalias, exportação em PDF.
