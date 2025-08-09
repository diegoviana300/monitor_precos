import requests
from bs4 import BeautifulSoup
from telegram import Bot
import json
import os
import gspread
from google.oauth2.service_account import Credentials
import asyncio
from dotenv import load_dotenv

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
    """Lê os produtos diretamente de uma Planilha Google."""
    print("Acessando a Planilha Google para buscar produtos...")
    try:
        # Define os 'escopos' - quais partes da API vamos usar
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]

        # Tenta carregar as credenciais do Secret do GitHub
        creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
        if creds_json_str:
            creds_info = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        else:
            # Se não estiver no GitHub, tenta carregar do arquivo local para testes
            print("Secret não encontrado. Tentando carregar 'credentials.json' local...")
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

        gc = gspread.authorize(creds)

        # IMPORTANTE: Altere o nome abaixo para o nome exato da sua planilha!
        spreadsheet = gc.open("Monitor de Preços Bot")
        worksheet = spreadsheet.sheet1

        records = worksheet.get_all_records()
        print(f"Sucesso! {len(records)} produtos encontrados na planilha.")

        # Converte os dados para o formato que o script espera
        produtos = []
        for row in records:
            produtos.append({
                "nome": row['Nome'],
                "url": row['URL'],
                "preco_desejado": float(str(row['Preco_Desejado']).replace(",", "."))
            })
        return produtos
    except Exception as e:
        print(f"ERRO CRÍTICO ao ler a Planilha Google: {e}")
        return []

def pegar_preco_exato(url):
    """Busca o preço exato de um produto usando a meta tag 'itemprop="price"'."""
    # (Esta função continua exatamente igual à versão anterior)
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
    # (Esta função continua exatamente igual à versão anterior)
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
        print(f"Verificando: {produto['nome']}...")
        preco_atual = pegar_preco_exato(produto["url"])

        if preco_atual is not None:
            print(f"-> Preço encontrado: R$ {preco_atual:.2f}")
            if preco_atual <= produto["preco_desejado"]:
                print(f"🎉 PREÇO BAIXO DETECTADO! Enviando alerta...")
                await enviar_alerta(produto["nome"], produto["url"], preco_atual)
            else:
                print(f"-> Preço acima do desejado (R$ {produto['preco_desejado']:.2f}).")
        else:
            print("-> Preço não encontrado.")

        await asyncio.sleep(2)

    print("--- Verificação concluída. O script será encerrado. ---")

# --- INICIALIZAÇÃO DO SCRIPT ---
if __name__ == "__main__":
    asyncio.run(fazer_verificacao_unica())

