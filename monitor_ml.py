import requests
from bs4 import BeautifulSoup
from telegram import Bot
import json
import os
import gspread
from dotenv import load_dotenv
import asyncio

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv() # Carrega o .env para testes locais

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Verificação das variáveis de ambiente
if not TOKEN or not CHAT_ID:
    raise ValueError("ERRO: Variáveis TOKEN e CHAT_ID são obrigatórias.")

bot = Bot(token=TOKEN)

# --- FUNÇÕES DO BOT ---

def carregar_produtos_da_planilha():
    """Lê os produtos diretamente de uma Planilha Google usando o método recomendado."""
    print("Acessando a Planilha Google para buscar produtos...")
    try:
        creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
        
        if creds_json_str:
            # No GitHub Actions, carrega as credenciais a partir do Secret
            creds_info = json.loads(creds_json_str)
            gc = gspread.service_account_from_dict(creds_info)
        else:
            # Para testes locais, carrega a partir do arquivo
            print("Secret GSPREAD_CREDENTIALS não encontrado. Tentando carregar 'credentials.json' local...")
            gc = gspread.service_account(filename="credentials.json")

        # IMPORTANTE: O nome deve ser exatamente igual ao da sua planilha!
        spreadsheet = gc.open("Monitor de Preços Bot")
        worksheet = spreadsheet.sheet1
        
        records = worksheet.get_all_records()
        print(f"Sucesso! {len(records)} produtos encontrados na planilha.")
        
        # Converte os dados para o formato que o script espera
        produtos = []
        for row in records:
            # Garante que os valores sejam lidos corretamente
            produtos.append({
                "nome": row.get('Nome'),
                "url": row.get('URL'),
                "preco_desejado": float(str(row.get('Preco_Desejado', 0)).replace(",", "."))
            })
        return produtos
    except gspread.exceptions.SpreadsheetNotFound:
        print("ERRO CRÍTICO: Planilha 'Monitor de Preços Bot' não encontrada. Verifique o nome e se você compartilhou a planilha com o e-mail do bot.")
        return []
    except Exception as e:
        print(f"ERRO CRÍTICO ao ler a Planilha Google: {e}")
        return []

def pegar_preco_exato(url):
    """Busca o preço exato de um produto usando a meta tag 'itemprop="price"'."""
    if not url: return None # Adiciona verificação para URL vazia
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"ERRO de conexão ao acessar a URL {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    meta_tag_preco = soup.select_one('meta[itemprop="price"]')
    if not meta_tag_preco:
        return None
    try:
        return float(meta_tag_preco['content'])
    except (KeyError, ValueError, TypeError):
        return None

async def enviar_alerta(nome, url, preco):
    """Envia a notificação de preço baixo via Telegram."""
    mensagem = (
        f"📢 *Preço baixou!*\n\n"
        f"**Produto:** {nome}\n"
        f"**💰 Preço atual:** R$ {preco:,.2f}\n\n"
        f"🔗 [Clique aqui para ver o produto]({url})"
    )
    await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")

async def fazer_verificacao_unica():
    """Faz UMA ÚNICA passagem de verificação por todos os produtos."""
    print("--- Iniciando verificação de preços ---")
    produtos = carregar_produtos_da_planilha()

    if not produtos:
        print("Nenhum produto para monitorar. Verificação encerrada.")
        return

    for produto in produtos:
        print(f"Verificando: {produto.get('nome')}...")
        preco_atual = pegar_preco_exato(produto.get('url'))

        if preco_atual is not None:
            print(f"-> Preço encontrado: R$ {preco_atual:.2f}")
            if preco_atual <= produto.get('preco_desejado', 0):
                print(f"🎉 PREÇO BAIXO DETECTADO! Enviando alerta...")
                await enviar_alerta(produto.get('nome'), produto.get('url'), preco_atual)
            else:
                print(f"-> Preço acima do desejado (R$ {produto.get('preco_desejado', 0):.2f}).")
        else:
            print("-> Preço não encontrado.")
        
        await asyncio.sleep(2)

    print("--- Verificação concluída. O script será encerrado. ---")

# --- INICIALIZAÇÃO DO SCRIPT ---
if __name__ == "__main__":
    # Remove a importação desnecessária de 'Credentials'
    from dotenv import load_dotenv
    asyncio.run(fazer_verificacao_unica())
