import requests
from bs4 import BeautifulSoup
from telegram import Bot
import time
import json
import os

# ===== CONFIGURAÇÕES =====
TOKEN = os.getenv("8463919007:AAGVxb4MftwtgKafxh0FGv8VqeIfISmxhnE")        # Token do Bot (Railway → Variables)
CHAT_ID = os.getenv("68480357")    # Seu Chat ID
INTERVALO = int(os.getenv("INTERVALO", 1800))  # Intervalo em segundos (default: 30 min)
ARQUIVO_PRODUTOS = "produtos.json"

bot = Bot(token=TOKEN)

def carregar_produtos():
    """Lê o arquivo produtos.json e retorna a lista"""
    with open(ARQUIVO_PRODUTOS, "r", encoding="utf-8") as f:
        return json.load(f)

def pegar_precos(url):
    """Retorna uma lista de preços encontrados na página"""
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    precos = []
    for p in soup.select("span.andes-money-amount__fraction"):
        try:
            valor = float(p.text.replace(".", "").replace(",", "."))
            precos.append(valor)
        except:
            continue
    return precos

def enviar_alerta(nome, url, preco):
    """Envia mensagem no Telegram"""
    mensagem = (
        f"📢 *Preço baixou!*\n"
        f"Produto: {nome}\n"
        f"💰 Preço atual: R$ {preco:,.2f}\n"
        f"🔗 [Clique aqui para ver o produto]({url})"
    )
    bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode="Markdown")

def monitorar():
    """Loop de monitoramento"""
    while True:
        produtos = carregar_produtos()
        for produto in produtos:
            precos = pegar_precos(produto["url"])
            if precos:
                preco_min = min(precos)
                print(f"[{produto['nome']}] Menor preço encontrado: R$ {preco_min}")
                if preco_min <= produto["preco_desejado"]:
                    enviar_alerta(produto["nome"], produto["url"], preco_min)
            else:
                print(f"[{produto['nome']}] Nenhum preço encontrado.")
        time.sleep(INTERVALO)

if __name__ == "__main__":
    monitorar()
