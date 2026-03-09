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

# Lista Expandida de Esportes (Mundial)
ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", "soccer_england_league1",
    "basketball_nba", "basketball_euroleague", 
    "americanfootball_nfl", "mma_mixed_martial_arts", 
    "tennis_atp_aus_open", "baseball_mlb", "icehockey_nhl",
    "cricket_ipl", "rugby_league_nrl", "volleyball_italy_superlega"
]

# =========================================================
# MOTOR DO SISTEMA
# =========================================================

class RequestManager:
    def __init__(self, api_key, proxy_url=None):
        self.api_key = api_key
        self.proxy_url = proxy_url

    async def buscar_odds(self, esporte):
        url = f"https://api.the-odds-api.com/v4/sports/{esporte}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": "br", # Foco em casas autorizadas no Brasil
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        
        # Correção do erro de Proxy
        mounts = {}
        if self.proxy_url:
            mounts = {"http://": httpx.HTTPTransport(proxy=self.proxy_url),
                      "https://": httpx.HTTPTransport(proxy=self.proxy_url)}

        async with httpx.AsyncClient(mounts=mounts, timeout=30.0) as client:
            try:
                r = await client.get(url, params=params)
                return r.json() if r.status_code == 200 else []
            except:
                return []

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
                await client.post(url, json={"chat_id": self.chat_id_tg, "text": mensagem, "parse_mode": "Markdown"})
            except: pass

    def calcular_arbitragem(self, o1, o2):
        margem = (1/o1) + (1/o2)
        if margem < 1.0:
            lucro = (1 - margem) * 100
            if lucro >= self.lucro_min:
                s1 = round(((self.banca * (1/o1)) / margem) / 5) * 5
                s2 = round((self.banca - s1) / 5) * 5
                retorno = min(s1 * o1, s2 * o2)
                return {"lucro": round(lucro, 2), "s1": s1, "s2": s2, "ret": round(retorno, 2)}
        return None

# =========================================================
# INTERFACE STREAMLIT
# =========================================================

st.set_page_config(page_title="Global Surebet Scanner", layout="wide")
st.title("🌍 Scanner de Arbitragem Mundial")

with st.sidebar:
    st.header("🛡️ Configuração de Proxy")
    ativar_px = st.checkbox("Ativar Proxy Pago")
    px_host = st.text_input("IP/Host")
    px_port = st.text_input("Porta")
    px_user = st.text_input("Usuário")
    px_pass = st.text_input("Senha", type="password")
    
    st.divider()
    banca_input = st.number_input("Banca Total (R$)", value=1000.0)
    lucro_input = st.slider("Mínimo Lucro %", 0.1, 10.0, 1.5)
    rodar = st.button("LIGAR SCANNER GLOBAL 🚀")

if rodar:
    proxy_url = None
    if ativar_px and px_host and px_port:
        proxy_url = f"http://{px_user}:{px_pass}@{px_host}:{px_port}" if px_user else f"http://{px_host}:{px_port}"

    req = RequestManager(API_KEY, proxy_url)
    proc = DataProcessor(banca_input, lucro_input, TOKEN_TELEGRAM, CHAT_ID_TELEGRAM)
    
    st.success("✅ Monitorando todos os esportes mundiais! Aguarde os alertas.")
    placeholder = st.empty()
    historico = []

    while True:
        for esporte in ESPORTES_MASTER:
            dados = asyncio.run(req.buscar_odds(esporte))
            if dados:
                for evento in dados:
                    try:
                        home, away = evento['home_team'], evento['away_team']
                        bookies = evento.get('bookmakers', [])
                        
                        # Compara as melhores odds entre as casas
                        o1 = bookies[0]['markets'][0]['outcomes'][0]['price']
                        o2 = bookies[1]['markets'][0]['outcomes'][1]['price']
                        
                        res = proc.calcular_arbitragem(o1, o2)
                        if res:
                            msg = (f"🌍 *OPORTUNIDADE MUNDIAL ({esporte})*\n"
                                   f"🏆 {home} x {away}\n"
                                   f"💰 Lucro: {res['lucro']}%\n"
                                   f"🏦 Apostar: R${res['s1']} e R${res['s2']}")
                            asyncio.run(proc.enviar_alerta(msg))
                            historico.insert(0, {"Hora": datetime.now().strftime("%H:%M"), "Esporte": esporte, "Lucro": f"{res['lucro']}%"})
                    except: continue

            with placeholder.container():
                st.write(f"🔄 Varredura Global: {datetime.now().strftime('%H:%M:%S')}")
                if historico:
                    st.table(pd.DataFrame(historico).head(15))
        
        time.sleep(40) # Delay para respeitar os limites da API gratuita
