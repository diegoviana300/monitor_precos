import requests
from bs4 import BeautifulSoup
from telegram import Bot
import json
import os
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import asyncio

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("ERRO: Variáveis TOKEN e CHAT_ID são obrigatórias.")

bot = Bot(token=TOKEN)

# --- FUNÇÕES DO BOT ---

def carregar_produtos_da_planilha():
    """Lê os produtos da Planilha Google com autenticação explícita."""
    print("Acessando a Planilha Google...")
    try:
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
        creds = None
        
        if creds_json_str:
            creds_info = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        else:
            print("Secret não encontrado. Tentando carregar 'credentials.json' local...")
            creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

        gc = gspread.authorize(creds)
        
        sheet_name_to_open = "Monitor"
        print(f"Tentando abrir a planilha: '{sheet_name_to_open}'")
        spreadsheet = gc.open(sheet_name_to_open)
        worksheet = spreadsheet.sheet1
        
        records = worksheet.get_all_records()
        print(f"Sucesso! {len(records)} produtos encontrados.")
        
        produtos = []
        for row in records:
            produtos.append({
                "nome": row.get('Nome'),
                "url": row.get('URL'),
                "preco_desejado": float(str(row.get('Preco_Desejado', 0)).replace(",", "."))
            })
        return produtos
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"ERRO CRÍTICO: Planilha '{sheet_name_to_open}' não encontrada. Verifique o nome e o compartilhamento.")
        return []
    except Exception as e:
        print(f"ERRO CRÍTICO ao ler a Planilha Google: {type(e).__name__}, Detalhes: {e}")
        return []

def pegar_preco_exato(url):
    """Extrai o preço do Mercado Livre com múltiplas estratégias."""
    if not url or not url.strip():
        return None
        
    print(f"  🔍 Buscando preço em: {url[:80]}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Estratégia 1: A meta tag
        meta_tag = soup.select_one('meta[itemprop="price"]')
        if meta_tag and meta_tag.get('content'):
            print(f'  ✓ Preço encontrado com Estratégia 1 (meta tag)')
            return float(meta_tag['content'])

        # Estratégia 2: O container principal
        price_container = soup.select_one(".ui-pdp-price__main-container")
        if price_container:
            fraction = price_container.select_one(".andes-money-amount__fraction")
            cents = price_container.select_one(".andes-money-amount__cents")
            if fraction:
                price_str = fraction.text.replace('.', '')
                if cents and cents.text: price_str += f".{cents.text}"
                print(f'  ✓ Preço encontrado com Estratégia 2 (container)')
                return float(price_str)

        # Estratégia 3: Seletor genérico
        fraction = soup.select_one(".price-tag-fraction, .andes-money-amount__fraction")
        if fraction:
             print(f'  ✓ Preço encontrado com Estratégia 3 (genérico)')
             return float(fraction.text.replace('.', '').replace(',', '.'))

        print(f"  ❌ Preço não encontrado para {url[:50]}...")
        return None
        
    except requests.RequestException as e:
        print(f"  ❌ Erro de rede ao buscar {url[:50]}...: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Erro inesperado ao buscar preço: {type(e).__name__}: {e}")
        return None

async def enviar_alerta(nome, url, preco, preco_desejado):
    """Envia alerta via Telegram."""
    try:
        mensagem = (
            f"🎉 *PREÇO BAIXOU!*\n\n"
            f"**Produto:** {nome}\n"
            f"**💰 Preço atual:** R$ {preco:,.2f}\n"
            f"**🎯 Preço desejado:** R$ {preco_desejado:,.2f}\n\n"
            f"🔗 [Ver produto]({url})"
        )
        await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")
        print(f"  ✓ Alerta enviado para o Telegram!")
    except Exception as e:
        print(f"  ❌ Erro ao enviar alerta: {type(e).__name__}: {e}")

async def fazer_verificacao_unica():
    """Executa uma verificação completa de preços."""
    print("\n" + "="*50)
    print("🤖 MONITOR DE PREÇOS - INICIANDO VERIFICAÇÃO")
    print("="*50)
    
    produtos = carregar_produtos_da_planilha()
    
    if not produtos:
        print("\n❌ Nenhum produto para monitorar. Verificação encerrada.")
        return
    
    print(f"\n🔍 Iniciando monitoramento de {len(produtos)} produtos...")
    
    for i, produto in enumerate(produtos, 1):
        nome = produto.get('nome', 'Produto sem nome')
        url = produto.get('url', '')
        preco_desejado = produto.get('preco_desejado', 0)
        
        print(f"\n[{i}/{len(produtos)}] 🛍️ {nome}")
        
        # --- INÍCIO DO CÓDIGO DE DEBUG ---
        print("--- DEBUG DA URL ---")
        # Imprime a URL entre aspas para ver espaços em branco
        print(f"URL lida: '{url}'")
        # Imprime o comprimento da string. Se for diferente do esperado, há algo errado.
        print(f"Comprimento da URL: {len(url)}")
        # Imprime a representação em bytes para ver caracteres invisíveis
        print(f"URL em bytes: {url.encode('utf-8')}")
        print("--- FIM DO DEBUG ---")
        # --- FIM DO CÓDIGO DE DEBUG ---
        
        if not url:
            print("  ❌ URL inválida, pulando...")
            continue
        
        preco_atual = pegar_preco_exato(url)
        
        if preco_atual is not None:
            print(f"  -> Preço atual: R$ {preco_atual:.2f} | Desejado: R$ {preco_desejado:,.2f}")
            if preco_atual <= preco_desejado:
                await enviar_alerta(nome, url, preco_atual, preco_desejado)
        else:
            print(f"  ⚠️  Não foi possível obter o preço")
        
        if i < len(produtos): await asyncio.sleep(3)
    
    print(f"\n" + "="*50)
    print(f"✅ VERIFICAÇÃO CONCLUÍDA!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(fazer_verificacao_unica())
