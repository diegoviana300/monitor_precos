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
        # Testando diferentes escopos de permissão
        SCOPES_TO_TRY = [
            # Escopo mais amplo (recomendado)
            [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
            # Escopo original
            [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
            ],
            # Escopo mais restritivo
            [
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
        ]
        
        creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
        
        if not creds_json_str:
            print("ERRO: GSPREAD_CREDENTIALS não encontrado!")
            return None
            
        print("✓ Credenciais encontradas")
        creds_info = json.loads(creds_json_str)
        print(f"✓ Email da conta de serviço: {creds_info.get('client_email', 'NÃO ENCONTRADO')}")
        print(f"✓ Projeto: {creds_info.get('project_id', 'NÃO ENCONTRADO')}")
        
        gc = None
        for i, scopes in enumerate(SCOPES_TO_TRY, 1):
            print(f"\n--- Tentativa {i}: Testando escopos {scopes} ---")
            try:
                creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
                gc = gspread.authorize(creds)
                
                print("✓ Autenticação bem-sucedida!")
                spreadsheets = gc.openall()
                
                if spreadsheets:
                    print(f"✓ Encontradas {len(spreadsheets)} planilhas com estes escopos:")
                    for j, sheet in enumerate(spreadsheets, 1):
                        print(f"  {j}. Nome: '{sheet.title}' | ID: {sheet.id}")
                    return gc
                else:
                    print("❌ Nenhuma planilha encontrada com estes escopos")
                    
            except Exception as e:
                print(f"❌ Erro com escopos {i}: {type(e).__name__}: {e}")
                continue
        
        # Se chegou aqui, nenhum escopo funcionou
        print("\n❌ NENHUMA planilha encontrada com nenhum escopo!")
        
        # Vamos tentar buscar por ID específico se fornecido
        print("\n--- Tentativa alternativa: Buscar por URL/ID ---")
        print("💡 DICA: Se você souber o ID da planilha, podemos tentar acessá-la diretamente")
        print("   O ID está na URL: https://docs.google.com/spreadsheets/d/[ID_AQUI]/edit")
        
        return None
        
    except json.JSONDecodeError:
        print("❌ ERRO: GSPREAD_CREDENTIALS não é um JSON válido!")
        return None
    except Exception as e:
        print(f"❌ ERRO geral ao listar planilhas: {type(e).__name__}: {e}")
        return None

def carregar_produtos_da_planilha():
    """Lê os produtos da Planilha Google com debug melhorado."""
    print("\n=== Iniciando acesso à Planilha Google ===")
    
    # Primeiro, vamos fazer debug das planilhas disponíveis
    gc = debug_planilhas_disponiveis()
    if not gc:
        # Vamos tentar uma abordagem alternativa: buscar por ID
        print("\n=== TENTATIVA ALTERNATIVA: Acesso direto por ID ===")
        print("💡 Vamos tentar diferentes métodos de acesso...")
        
        try:
            SCOPES = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds_json_str = os.getenv("GSPREAD_CREDENTIALS")
            creds_info = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            gc = gspread.authorize(creds)
            
            # Tentar listar arquivos do Drive diretamente
            print("\n--- Tentando listar via Google Drive API ---")
            
            # Se não conseguimos listar, vamos tentar um método mais direto
            print("🔍 Buscando planilhas com diferentes filtros...")
            
            # Método alternativo: tentar abrir por diferentes nomes
            possible_names = ["Monitor", "monitor", "MONITOR", "Monitor de Preços", "Monitor de Precos"]
            
            for name in possible_names:
                try:
                    print(f"  Tentando nome: '{name}'")
                    spreadsheet = gc.open(name)
                    print(f"  ✓ SUCESSO! Planilha encontrada: '{name}'")
                    print(f"  📋 ID: {spreadsheet.id}")
                    print(f"  🔗 URL: {spreadsheet.url}")
                    
                    worksheet = spreadsheet.sheet1
                    records = worksheet.get_all_records()
                    print(f"  📊 {len(records)} linhas encontradas")
                    
                    # Processar produtos...
                    produtos = []
                    for i, row in enumerate(records, 1):
                        try:
                            nome = row.get('Nome', '').strip()
                            url = row.get('URL', '').strip()
                            preco_str = str(row.get('Preco_Desejado', '0')).replace(",", ".").strip()
                            
                            if not nome or not url:
                                continue
                                
                            preco_desejado = float(preco_str)
                            produtos.append({
                                "nome": nome,
                                "url": url,
                                "preco_desejado": preco_desejado
                            })
                            
                        except Exception:
                            continue
                    
                    print(f"  ✅ {len(produtos)} produtos válidos carregados!")
                    return produtos
                    
                except gspread.exceptions.SpreadsheetNotFound:
                    print(f"  ❌ '{name}' não encontrada")
                    continue
                except Exception as e:
                    print(f"  ❌ Erro com '{name}': {e}")
                    continue
            
            print("\n❌ Nenhuma planilha encontrada com os nomes testados")
            
        except Exception as e:
            print(f"❌ Erro na tentativa alternativa: {e}")
        
        return []
    
    # Se gc existe, continuar com o processo normal...
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
    
    print("\n❌ NENHUMA planilha 'Monitor' encontrada!")
    print("\n🔧 PRÓXIMOS PASSOS:")
    print("1. Aguarde 5-10 minutos e tente novamente (sincronização do Google)")
    print("2. Verifique se o nome da planilha é exatamente 'Monitor'")
    print("3. Tente remover e re-adicionar as permissões")
    print("4. Se possível, copie o ID da planilha da URL para tentarmos acesso direto")
    
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
