import os
import json
import gspread

# 1️⃣ Verificar se a variável existe
creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
if not creds_json_str:
    raise ValueError("❌ Variável de ambiente GSPREAD_CREDENTIALS não encontrada.")

print("✅ Variável GSPREAD_CREDENTIALS encontrada.")

# 2️⃣ Testar se o JSON é válido
try:
    creds_info = json.loads(creds_json_str)
    print("✅ JSON das credenciais carregado com sucesso.")
except json.JSONDecodeError:
    raise ValueError("❌ O conteúdo de GSPREAD_CREDENTIALS não é um JSON válido.")

# 3️⃣ Conectar ao Google Sheets
gc = gspread.service_account_from_dict(creds_info)

# 4️⃣ Tentar abrir a planilha
spreadsheet_name = "Monitor de Preços Bot"
try:
    sh = gc.open(spreadsheet_name)
    print(f"✅ Planilha '{spreadsheet_name}' aberta com sucesso.")
except Exception as e:
    raise ValueError(f"❌ Não foi possível abrir a planilha: {e}")

# 5️⃣ Ler a primeira aba e exibir as primeiras linhas
worksheet = sh.sheet1
rows = worksheet.get_all_values()
print(f"✅ Linhas lidas: {len(rows)}")
if rows:
    print("📄 Primeiras linhas da planilha:")
    for row in rows[:5]:
        print(row)
