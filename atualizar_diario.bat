@echo off
REM Ajuste o caminho abaixo para a pasta onde clonou o repositorio
cd /d "C:\Users\Luiz.Zanuto\OneDrive - Unilever\Desktop\ARK\Pessoal\Python\clima-portugal"
python update_data.py >> log_atualizacao.txt 2>&1
