import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
import random
from datetime import datetime

# =========================================================
# SEUS DADOS INTEGRADOS
# =========================================================
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63"
TOKEN_TELEGRAM = "8510184758:AAEv4k0_jOj5mDGeBVoh_OJW7mYK-nuJu7A"
CHAT_ID_TELEGRAM = "5679754900"

ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "basketball_nba", "americanfootball_nfl", "mma_mixed_martial_arts", 
    "tennis_atp_aus_open", "baseball_mlb", "volleyball_italy_superlega"
]

class RequestManager:
    def __init__(self, api_key, proxy_url=None):
        self.api_key = api_key
        self.proxy_url = proxy_url

    async def buscar_odds(self, esporte):
        url = f"https://api.the-odds-api.com/v4/sports/{esporte}/odds/"
        params = {"apiKey": self.api_key, "regions": "br", "markets": "h2h,totals", "oddsFormat": "decimal"}
        mounts = {}
        if self.proxy_url:
            mounts = {"http://": httpx.HTTPTransport(proxy=self.proxy_url), "https://": httpx.HTTPTransport(proxy=self.proxy_url)}
        
        async with httpx.AsyncClient(mounts=mounts, timeout=30.0) as client:
            try:
                r = await client.get(url, params=params)
                return r.json() if r.status_code == 200 else []
            except: return []

class DataProcessor:
    def __init__(self, banca, lucro_min, token_tg, chat_id_tg):
        self.banca = banca
        self.lucro_min = lucro_min
        self.token_tg = token_tg
        self.chat_id_tg = chat_id_tg

    async def enviar_alerta(self, mensagem):
        url = f"https://api.telegram.org/bot{self.token_tg}/sendMessage"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={"chat_id": self.chat_id_tg, "text": mensagem, "parse_mode": "Markdown"})
                return resp.status_code == 200
            except: return False

    def calcular_arbitragem(self, o1, o2):
        margem = (1/o1) + (1/o2)
        if margem < 1.0:
            lucro = (1 - margem) * 100
            if lucro >= self.lucro_min:
                s1 = round(((self.banca * (1/o1)) / margem) / 5) * 5
                s2 = round((self.banca - s1) / 5) * 5
                ret = min(s1 * o1, s2 * o2)
                return {"lucro": round(lucro, 2), "s1": s1, "s2": s2, "ret": round(ret, 2)}
        return None

# --- INTERFACE ---
st.set_page_config(page_title="Global Surebet Scanner", layout="wide")
st.title("🌍 Scanner de Arbitragem Mundial")

with st.sidebar:
    st.header("⚙️ Configurações")
    banca_input = st.number_input("Banca Total (R$)", value=1000.0)
    lucro_input = st.slider("Mínimo Lucro %", 0.1, 10.0, 1.0) # Baixei para 1% para achar mais rápido
    rodar = st.button("LIGAR SCANNER GLOBAL 🚀")

if rodar:
    req = RequestManager(API_KEY)
    proc = DataProcessor(banca_input, lucro_input, TOKEN_TELEGRAM, CHAT_ID_TELEGRAM)
    
    st.success("✅ Monitorando! As oportunidades aparecerão abaixo e no Telegram.")
    
    # Espaços reservados para atualizar a tela sem recarregar
    alerta_imediato = st.empty()
    status_varredura = st.empty()
    tabela_historico = st.empty()
    
    historico = []

    while True:
        for esporte in ESPORTES_MASTER:
            status_varredura.write(f"🔍 Checando agora: **{esporte.replace('_', ' ').upper()}**...")
            dados = asyncio.run(req.buscar_odds(esporte))
            
            if dados:
                for evento in dados:
                    try:
                        home, away = evento['home_team'], evento['away_team']
                        bookies = evento.get('bookmakers', [])
                        if len(bookies) < 2: continue
                        
                        o1 = bookies[0]['markets'][0]['outcomes'][0]['price']
                        o2 = bookies[1]['markets'][0]['outcomes'][1]['price']
                        
                        res = proc.calcular_arbitragem(o1, o2)
                        if res:
                            txt = (f"🔥 **SUREBET DETECTADA!**\n\n"
                                   f"🏆 Jogo: {home} x {away}\n"
                                   f"💰 Lucro: {res['lucro']}%\n"
                                   f"🏦 Aposta 1: R${res['s1']} | Aposta 2: R${res['s2']}")
                            
                            # EXIBE NO APP IMEDIATAMENTE
                            alerta_imediato.success(txt)
                            
                            # ENVIA NO TELEGRAM
                            tg_ok = asyncio.run(proc.enviar_alerta(txt))
                            
                            historico.insert(0, {
                                "Hora": datetime.now().strftime("%H:%M:%S"),
                                "Evento": f"{home} x {away}",
                                "Lucro": f"{res['lucro']}%",
                                "Telegram": "✅ Enviado" if tg_ok else "❌ Erro"
                            })
                    except: continue

            # Atualiza a tabela de histórico no App
            with tabela_historico.container():
                st.subheader("📋 Últimas Oportunidades Encontradas")
                if historico:
                    st.table(pd.DataFrame(historico).head(10))
                else:
                    st.info("Aguardando a primeira oportunidade real aparecer...")
        
        time.sleep(20)
