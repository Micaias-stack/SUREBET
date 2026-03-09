import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
import random
from datetime import datetime

# --- CLASSE DE GERENCIAMENTO DE REQUISIÇÕES ---
class RequestManager:
    def __init__(self, api_key, user_agents, proxies):
        self.api_key = api_key
        self.user_agents = user_agents
        self.proxies = proxies

    async def enviar_requisicao(self, url, params):
        user_agent = random.choice(self.user_agents)
        # Se os proxies estiverem vazios ou falharem, o httpx ignora se configurado adequadamente
        proxy = random.choice(self.proxies) if self.proxies else None
        
        async with httpx.AsyncClient(proxies=proxy, headers={"User-Agent": user_agent}, timeout=10.0) as client:
            try:
                r = await client.get(url, params=params)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 429:
                    st.error("Limite de requisições da API atingido (Rate Limit).")
                    return []
                else:
                    st.error(f"Erro API: {r.status_code}")
                    return []
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
                return []

# --- CLASSE DE PROCESSAMENTO DE ARBITRAGEM ---
class DataProcessor:
    def __init__(self, banca_total, lucro_alvo, token_tg, chat_id_tg):
        self.banca_total = banca_total
        self.lucro_alvo = lucro_alvo
        self.token_tg = token_tg
        self.chat_id_tg = chat_id_tg

    async def enviar_alerta_telegram(self, mensagem):
        if not self.token_tg or not self.chat_id_tg:
            return
        url = f"https://api.telegram.org/bot{self.token_tg}/sendMessage"
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json={
                    "chat_id": self.chat_id_tg, 
                    "text": mensagem, 
                    "parse_mode": "Markdown"
                })
            except:
                pass

    def calcular_surebet(self, odd_h, odd_a):
        prob = (1 / odd_h) + (1 / odd_a)
        if prob < 1.0:
            lucro_p = (1 - prob) * 100
            if lucro_p >= self.lucro_alvo:
                # Cálculo de Stake com arredondamento inteligente (múltiplos de 5)
                s1 = round(((self.banca_total * (1 / odd_h)) / prob) / 5) * 5
                s2 = round((self.banca_total - s1) / 5) * 5
                
                # Recalcula lucro real após arredondamento
                retorno_min = min(s1 * odd_h, s2 * odd_a)
                lucro_real = retorno_min - (s1 + s2)
                lucro_final_p = (lucro_real / (s1 + s2)) * 100
                
                return {
                    "lucro": round(lucro_final_p, 2),
                    "stake_h": s1,
                    "stake_a": s2,
                    "retorno": round(retorno_min, 2)
                }
        return None

    async def filtrar_oportunidades(self, dados, esporte_nome):
        oportunidades = []
        for evento in dados:
            home = evento.get('home_team')
            away = evento.get('away_team')
            bookmakers = evento.get('bookmakers', [])
            
            if not bookmakers: continue

            # Encontrar as melhores odds para Home e Away entre todas as casas
            melhor_h = {"odd": 0, "casa": ""}
            melhor_a = {"odd": 0, "casa": ""}

            for book in bookmakers:
                casa = book['title']
                markets = book.get('markets', [])
                if not markets: continue
                
                for outcome in markets[0].get('outcomes', []):
                    if outcome['name'] == home and outcome['price'] > melhor_h['odd']:
                        melhor_h = {"odd": outcome['price'], "casa": casa}
                    elif outcome['name'] == away and outcome['price'] > melhor_a['odd']:
                        melhor_a = {"odd": outcome['price'], "casa": casa}

            # Validar arbitragem
            if melhor_h['odd'] > 0 and melhor_a['odd'] > 0:
                res = self.calcular_surebet(melhor_h['odd'], melhor_a['odd'])
                if res and res['lucro'] > 0:
                    msg = (f"🔥 *SUREBET {res['lucro']}%* \n"
                           f"🏆 Esporte: {esporte_nome}\n"
                           f"⚽ {home} x {away}\n\n"
                           f"🏦 {melhor_h['casa']}: Odd {melhor_h['odd']} -> *R$ {res['stake_h']}*\n"
                           f"🏦 {melhor_a['casa']}: Odd {melhor_a['odd']} -> *R$ {res['stake_a']}*\n"
                           f"💰 Retorno: R$ {res['retorno']}")
                    
                    await self.enviar_alerta_telegram(msg)
                    oportunidades.append({
                        "Evento": f"{home} x {away}",
                        "Lucro": f"{res['lucro']}%",
                        "Detalhes": f"{melhor_h['casa']} @{melhor_h['odd']} | {melhor_a['casa']} @{melhor_a['odd']}",
                        "Stakes": f"H: R${res['stake_h']} | A: R${res['stake_a']}"
                    })
        return oportunidades

# --- CLASSE SCANNER ---
class Scanner:
    def __init__(self, request_manager, data_processor):
        self.request_manager = request_manager
        self.data_processor = data_processor

    async def scan(self, esporte_chave):
        # URL Real da The Odds API
        url = f"https://api.the-odds-api.com/v4/sports/{esporte_chave}/odds/"
        params = {
            "apiKey": self.request_manager.api_key,
            "regions": "br", # Casas brasileiras
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        dados = await self.request_manager.enviar_requisicao(url, params)
        if dados:
            return await self.data_processor.filtrar_oportunidades(dados, esporte_chave)
        return []

# --- CONFIGURAÇÕES E INTERFACE STREAMLIT ---
st.set_page_config(page_title="Ultra Scanner Multi-Sport", layout="wide")
st.title("🏆 Scanner de Arbitragem Global Live")

# Chaves e Configurações (Substitua pelos seus dados)
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63"
TOKEN_TELEGRAM = "8510184758:AAEv4k0_jOj5mDGeBVoh_OJW7mYK-nuJu7A"
CHAT_ID_TELEGRAM = "5679754900"

ESPORTES = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "americanfootball_nfl", "basketball_nba", "volleyball_italy_superlega",
    "tennis_atp_aus_open"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
]

PROXIES = [] # Adicione se tiver, ex: "http://usuario:senha@ip:porta"

with st.sidebar:
    st.header("⚙️ Painel de Controle")
    banca_total = st.number_input("Banca Total (R$)", value=1000.0)
    lucro_alvo = st.slider("Mínimo Lucro %", 0.1, 10.0, 1.0)
    delay_scan = st.slider("Intervalo de Busca (seg)", 10, 120, 30)
    rodar = st.button("INICIAR SCANNER TOTAL 🚀")

if rodar:
    st.success("✅ Scanner Ativo! Verifique seu Telegram e a tabela abaixo.")
    
    req_manager = RequestManager(API_KEY, USER_AGENTS, PROXIES)
    processor = DataProcessor(banca_total, lucro_alvo, TOKEN_TELEGRAM, CHAT_ID_TELEGRAM)
    scanner = Scanner(req_manager, processor)

    tabela_placeholder = st.empty()
    historico_oportunidades = []

    while True:
        for esporte in ESPORTES:
            try:
                # Executa o scan assíncrono
                novas_ops = asyncio.run(scanner.scan(esporte))
                
                if novas_ops:
                    for op in novas_ops:
                        op['Horário'] = datetime.now().strftime("%H:%M:%S")
                        historico_oportunidades.insert(0, op)
                
                # Atualiza a interface
                with tabela_placeholder.container():
                    st.write(f"🔍 Varrendo: {esporte.replace('_', ' ').title()}")
                    if historico_oportunidades:
                        st.table(pd.DataFrame(historico_oportunidades).head(10))
                    else:
                        st.info("Buscando discrepâncias nas casas autorizadas...")

            except Exception as e:
                st.error(f"Erro no ciclo: {e}")

        # Delay com variação aleatória para evitar detecção
        time.sleep(delay_scan + random.uniform(2, 7))
