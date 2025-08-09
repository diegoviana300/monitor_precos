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

def debug_planilhas_disponiveis():
    """Lista todas as planilhas disponíveis para debug."""
    print("\n=== DEBUG: Listando todas as planilhas disponíveis ===")
    try:
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
        
        if not creds_json_str:
            print("ERRO: GSPREAD_CREDENTIALS não encontrado!")
            return None
            
        print("✓ Credenciais encontradas")
        creds_info = json.loads(creds_json_str)
        print(f"✓ Email da conta de serviço: {creds_info.get('client_email', 'NÃO ENCONTRADO')}")
        
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        gc = gspread.authorize(creds)
        
        print("\n--- Listando todas as planilhas compartilhadas com esta conta ---")
        spreadsheets = gc.openall()
        
        if not spreadsheets:
            print("❌ NENHUMA planilha encontrada!")
            print("\n🔧 SOLUÇÕES:")
            print("1. Verifique se você compartilhou a planilha com o email da conta de serviço")
            print("2. Certifique-se de que deu permissão de 'Editor' para a conta")
            return None
        
        print(f"✓ Encontradas {len(spreadsheets)} planilhas:")
        for i, sheet in enumerate(spreadsheets, 1):
            print(f"  {i}. Nome: '{sheet.title}' | ID: {sheet.id}")
            
        return gc
        
    except json.JSONDecodeError:
        print("❌ ERRO: GSPREAD_CREDENTIALS não é um JSON válido!")
        return None
    except Exception as e:
        print(f"❌ ERRO ao listar planilhas: {type(e).__name__}: {e}")
        return None

def carregar_produtos_da_planilha():
    """Lê os produtos da Planilha Google com debug melhorado."""
    print("\n=== Iniciando acesso à Planilha Google ===")
    
    # Primeiro, vamos fazer debug das planilhas disponíveis
    gc = debug_planilhas_disponiveis()
    if not gc:
        return []
    
    # Agora vamos tentar encontrar a planilha "Monitor"
    sheet_names_to_try = ["Monitor", "monitor", "MONITOR"]
    
    for sheet_name in sheet_names_to_try:
        try:
            print(f"\n--- Tentando abrir planilha: '{sheet_name}' ---")
            spreadsheet = gc.open(sheet_name)
            worksheet = spreadsheet.sheet1
            
            print(f"✓ Planilha '{sheet_name}' encontrada!")
            print(f"✓ ID da planilha: {spreadsheet.id}")
            print(f"✓ URL da planilha: {spreadsheet.url}")
            
            records = worksheet.get_all_records()
            print(f"✓ Dados carregados: {len(records)} linhas encontradas")
            
            if records:
                print("\n--- Primeiras 3 linhas dos dados ---")
                for i, record in enumerate(records[:3], 1):
                    print(f"Linha {i}: {record}")
            
            produtos = []
            for i, row in enumerate(records, 1):
                try:
                    nome = row.get('Nome', '').strip()
                    url = row.get('URL', '').strip()
                    preco_str = str(row.get('Preco_Desejado', '0')).replace(",", ".").strip()
                    
                    if not nome or not url:
                        print(f"⚠️  Linha {i} ignorada: nome ou URL vazio")
                        continue
                        
                    try:
                        preco_desejado = float(preco_str)
                    except (ValueError, TypeError):
                        print(f"⚠️  Linha {i} ignorada: preço inválido '{preco_str}'")
                        continue
                    
                    produto = {
                        "nome": nome,
                        "url": url,
                        "preco_desejado": preco_desejado
                    }
                    produtos.append(produto)
                    print(f"✓ Produto {len(produtos)} adicionado: {nome} - R$ {preco_desejado}")
                    
                except Exception as e:
                    print(f"⚠️  Erro na linha {i}: {e}")
                    continue
            
            print(f"\n✓ Total de produtos válidos carregados: {len(produtos)}")
            return produtos
            
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ Planilha '{sheet_name}' não encontrada")
            continue
        except Exception as e:
            print(f"❌ Erro ao acessar planilha '{sheet_name}': {type(e).__name__}: {e}")
            continue
    
    print("\n❌ NENHUMA planilha 'Monitor' encontrada com nenhuma das variações testadas!")
    print("\n🔧 SOLUÇÕES:")
    print("1. Verifique se o nome da planilha é exatamente 'Monitor'")
    print("2. Certifique-se de que compartilhou a planilha com o email da conta de serviço")
    print("3. Verifique se as permissões são de 'Editor'")
    print("4. Tente renomear uma das planilhas listadas acima para 'Monitor'")
    
    return []

def pegar_preco_exato(url):
    """Extrai o preço do Mercado Livre com tratamento robusto."""
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
        
        # Múltiplas estratégias para encontrar o preço
        selectors = [
            'meta[itemprop="price"]',
            '.andes-money-amount__fraction',
            '.price-tag-fraction',
            '[data-testid="price"]',
            '.notranslate'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                try:
                    if element.name == 'meta' and element.get('content'):
                        price_text = element['content']
                    else:
                        price_text = element.get_text().strip()
                    
                    # Limpar e converter o preço
                    price_clean = ''.join(filter(lambda x: x.isdigit() or x == '.', price_text.replace(',', '.')))
                    if price_clean and '.' in price_clean:
                        price = float(price_clean)
                        if 10 <= price <= 1000000:  # Validação básica de preço
                            print(f"  ✓ Preço encontrado: R$ {price:,.2f} (usando {selector})")
                            return price
                except (ValueError, TypeError):
                    continue
        
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
            f"**🎯 Preço desejado:** R$ {preco_desejado:,.2f}\n"
            f"**💸 Economia:** R$ {preco_desejado - preco:,.2f}\n\n"
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
    alertas_enviados = 0
    
    for i, produto in enumerate(produtos, 1):
        nome = produto.get('nome', 'Produto sem nome')
        url = produto.get('url', '')
        preco_desejado = produto.get('preco_desejado', 0)
        
        print(f"\n[{i}/{len(produtos)}] 🛍️ {nome}")
        print(f"  💰 Preço desejado: R$ {preco_desejado:,.2f}")
        
        if not url:
            print("  ❌ URL inválida, pulando...")
            continue
        
        preco_atual = pegar_preco_exato(url)
        
        if preco_atual is not None:
            diferenca = preco_atual - preco_desejado
            if diferenca <= 0:
                print(f"  🎉 OPORTUNIDADE! Preço atual (R$ {preco_atual:,.2f}) ≤ desejado!")
                await enviar_alerta(nome, url, preco_atual, preco_desejado)
                alertas_enviados += 1
            else:
                print(f"  📈 Preço ainda alto. Diferença: +R$ {diferenca:,.2f}")
        else:
            print(f"  ⚠️  Não foi possível obter o preço")
        
        # Pausa entre verificações para evitar rate limiting
        if i < len(produtos):
            print("  ⏳ Aguardando 3s...")
            await asyncio.sleep(3)
    
    print(f"\n" + "="*50)
    print(f"✅ VERIFICAÇÃO CONCLUÍDA!")
    print(f"📊 Produtos verificados: {len(produtos)}")
    print(f"🚨 Alertas enviados: {alertas_enviados}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(fazer_verificacao_unica())
