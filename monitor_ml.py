import requests
from bs4 import BeautifulSoup
from telegram import Bot
import json
import os
from dotenv import load_dotenv
import asyncio

# --- CONFIGURAÇÃO INICIAL ---

# 1. Carrega as variáveis do arquivo .env (para rodar no seu PC)
load_dotenv()

# 2. Pega os valores do ambiente usando os NOMES das variáveis
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
INTERVALO = int(os.getenv("INTERVALO", 60)) # Intervalo em segundos
ARQUIVO_PRODUTOS = "produtos.json"

# 3. Verificação para garantir que as variáveis foram carregadas
if not TOKEN:
    raise ValueError("Variável de ambiente 'TOKEN' não encontrada! Verifique seu arquivo .env ou as configurações do Railway.")
if not CHAT_ID:
    raise ValueError("Variável de ambiente 'CHAT_ID' não encontrada! Verifique seu arquivo .env ou as configurações do Railway.")

# Inicializa o bot do Telegram
bot = Bot(token=TOKEN)

# --- FUNÇÕES DO BOT ---

def carregar_produtos():
    """Lê o arquivo produtos.json e retorna a lista de dicionários."""
    try:
        with open(ARQUIVO_PRODUTOS, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERRO: O arquivo '{ARQUIVO_PRODUTOS}' não foi encontrado.")
        return [] # Retorna lista vazia para não quebrar o script
    except json.JSONDecodeError:
        print(f"ERRO: O arquivo '{ARQUIVO_PRODUTOS}' contém um erro de formatação (JSON inválido).")
        return []

def pegar_preco_exato(url):
    """
    Busca o preço exato de um produto usando a meta tag 'itemprop="price"'.
    Este método é muito mais preciso e confiável.
    Retorna um float com o preço, ou None se não encontrar.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Lança um erro para status HTTP 4xx/5xx
    except requests.RequestException as e:
        print(f"ERRO de conexão ao acessar a URL {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # A grande descoberta! Buscamos diretamente pela meta tag com o preço.
    meta_tag_preco = soup.select_one('meta[itemprop="price"]')

    if not meta_tag_preco:
        return None # Se não encontrou a tag, produto pode estar indisponível

    try:
        # Pega o valor do atributo 'content' da tag e converte para float
        preco = float(meta_tag_preco['content'])
        return preco
    except (KeyError, ValueError, TypeError) as e:
        print(f"ERRO ao extrair ou converter o preço da meta tag: {e}")
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

async def monitorar():
    """Loop principal que orquestra o monitoramento."""
    while True:
        print("--- Iniciando nova verificação de preços ---")
        produtos = carregar_produtos()
        
        if not produtos:
            print("Nenhum produto para monitorar. Verifique seu arquivo 'produtos.json'.")
        
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
                print("-> Preço não encontrado (produto indisponível ou página diferente).")
            
            await asyncio.sleep(2) # Pequena pausa para não sobrecarregar o site

        print(f"--- Verificação concluída. Aguardando {INTERVALO} segundos... ---")
        await asyncio.sleep(INTERVALO)

# --- INICIALIZAÇÃO DO SCRIPT ---

if __name__ == "__main__":
    try:
        asyncio.run(monitorar())
    except KeyboardInterrupt:
        print("\nBot interrompido pelo usuário. Encerrando...")