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
    """Lê os produtos da Planilha Google com debug melhorado."""
    print("\n=== Iniciando acesso à Planilha Google ===")
    
    try:
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
        
        if not creds_json_str:
            print("ERRO: GSPREAD_CREDENTIALS não encontrado!")
            return []
            
        creds_info = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        gc = gspread.authorize(creds)
        
        print("✓ Autenticação bem-sucedida!")
        
        sheet_name_to_open = "Monitor"
        print(f"--- Tentando abrir planilha: '{sheet_name_to_open}' ---")
        spreadsheet = gc.open(sheet_name_to_open)
        worksheet = spreadsheet.sheet1
        
        print(f"✓ Planilha '{sheet_name_to_open}' encontrada!")
        
        records = worksheet.get_all_records()
        print(f"✓ Dados carregados: {len(records)} linhas encontradas")
        
        produtos = []
        for row in records:
            # Limpa espaços em branco da URL logo na leitura
            url_limpa = row.get('URL', '').strip()
            
            produtos.append({
                "nome": row.get('Nome', '').strip(),
                "url": url_limpa,
                "preco_desejado": float(str(row.get('Preco_Desejado', '0')).replace(",", ".").strip())
            })
        
        print(f"✓ Total de produtos válidos carregados: {len(produtos)}")
        return produtos
        
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Planilha '{sheet_name_to_open}' não encontrada")
        return []
    except Exception as e:
        print(f"❌ Erro ao acessar planilha: {type(e).__name__}: {e}")
        return []

def pegar_preco_exato(url):
    """Extrai o preço do Mercado Livre com tratamento robusto."""
    if not url:
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        selectors = [
            'meta[itemprop="price"]',
            '.andes-money-amount__fraction',
            '.price-tag-fraction'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                price_text = ''
                if element.name == 'meta' and element.get('content'):
                    price_text = element['content']
                else:
                    price_text = element.get_text()
                
                price_clean = ''.join(filter(lambda x: x.isdigit() or x == '.', price_text.replace(',', '.')))
                if price_clean:
                    print(f"  ✓ Preço encontrado: R$ {float(price_clean):,.2f} (usando {selector})")
                    return float(price_clean)
        
        print(f"  ❌ Preço não encontrado para {url[:50]}...")
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
        
        # --- INÍCIO DO CÓDIGO DE DEBUG DA URL ---
        print("--- DEBUG DA URL ---")
        # repr() mostra caracteres invisíveis como \n ou \t
        print(f"URL lida (repr): {repr(url)}")
        print(f"Comprimento da URL: {len(url)}")
        # Marcadores para ver espaços no início ou fim
        print(f"URL entre marcadores: >{url}<")
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
        
        if i < len(produtos):
            await asyncio.sleep(3)
    
    print(f"\n" + "="*50)
    print(f"✅ VERIFICAÇÃO CONCLUÍDA!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(fazer_verificacao_unica())

