@echo off
REM Ajuste o caminho abaixo para a pasta onde colocou update_data.py (nao precisa ser um repo git clonado)
cd /d "C:\Users\Luiz.Zanuto\OneDrive - Unilever\Desktop\ARK\Pessoal\Python\clima-portugal"
python update_data.py >> log_atualizacao.txt 2>&1
