import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
import random
from datetime import datetime

# --- CONFIGURAÇÕES INTEGRADAS ---
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63"
TOKEN_TELEGRAM = "8510184758:AAEv4k0_jOj5mDGeBVoh_OJW7mYK-nuJu7A"
CHAT_ID_TELEGRAM = "5679754900"

ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "basketball_nba", "americanfootball_nfl", "mma_mixed_martial_arts", 
    "tennis_atp_aus_open", "baseball_mlb", "volleyball_italy_superlega"
]

# --- CSS PERSONALIZADO PARA MOBILE ---
st.set_page_config(page_title="Surebet Pro Dashboard", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 10px; }
    .stAlert { border-radius: 12px; }
    div[data-testid="stExpander"] { border: none !important; background-color: #161b22 !important; border-radius: 12px !important; }
    .bet-card { 
        background-color: #1f2937; 
        padding: 15px; 
        border-radius: 12px; 
        border-left: 5px solid #10b981;
        margin-bottom: 10px;
    }
    .header-text { color: #f9fafb; font-weight: 800; font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

# --- CLASSES DE MOTOR (CORRIGIDAS) ---
class RequestManager:
    def __init__(self, api_key, proxy_url=None):
        self.api_key = api_key
        self.proxy_url = proxy_url

    async def buscar_odds(self, esporte):
        url = f"https://api.the-odds-api.com/v4/sports/{esporte}/odds/"
        params = {"apiKey": self.api_key, "regions": "br", "markets": "h2h,totals", "oddsFormat": "decimal"}
        mounts = {}
        if self.proxy_url:
            transport = httpx.AsyncHTTPTransport(proxy=self.proxy_url)
            mounts = {"http://": transport, "https://": transport}

        async with httpx.AsyncClient(mounts=mounts, timeout=30.0) as client:
            try:
                r = await client.get(url, params=params)
                return r.json() if r.status_code == 200 else []
            except: return []

class DataProcessor:
    def __init__(self, banca, lucro_min, token_tg, chat_id_tg):
        self.banca, self.lucro_min = banca, lucro_min
        self.token_tg, self.chat_id_tg = token_tg, chat_id_tg

    async def enviar_tg(self, msg):
        url = f"https://api.telegram.org/bot{self.token_tg}/sendMessage"
        async with httpx.AsyncClient() as client:
            try: await client.post(url, json={"chat_id": self.chat_id_tg, "text": msg, "parse_mode": "Markdown"})
            except: pass

    def calcular(self, o1, o2):
        m = (1/o1) + (1/o2)
        if m < 1.0:
            l = (1-m)*100
            if l >= self.lucro_min:
                s1 = round(((self.banca*(1/o1))/m)/5)*5
                s2 = round((self.banca-s1)/5)*5
                return {"lucro": round(l, 2), "s1": s1, "s2": s2, "ret": round(min(s1*o1, s2*o2), 2)}
        return None

# --- INTERFACE PRINCIPAL ---
st.markdown('<p class="header-text">🚀 Surebet Pro Dashboard</p>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📡 Scanner", "⚙️ Ajustes", "🛡️ Proxy"])

with tab2:
    col_b, col_l = st.columns(2)
    banca_v = col_b.number_input("Banca (R$)", value=1000.0, step=100.0)
    lucro_v = col_l.slider("Min Lucro %", 0.1, 5.0, 1.2)
    delay_v = st.slider("Velocidade (seg)", 10, 60, 30)

with tab3:
    st.info("Configure aqui seu IP Fixo ou Rotativo")
    ativar_px = st.toggle("Ativar Túnel Proxy")
    px_h = st.text_input("Host/IP")
    px_p = st.text_input("Porta")
    px_u = st.text_input("Usuário")
    px_s = st.text_input("Senha", type="password")

with tab1:
    btn_col1, btn_col2 = st.columns([1, 1])
    rodar = btn_col1.button("INICIAR SCANNER", use_container_width=True, type="primary")
    parar = btn_col2.button("PARAR", use_container_width=True)

    if rodar:
        proxy_url = f"http://{px_u}:{px_s}@{px_h}:{px_p}" if ativar_px and px_u else f"http://{px_h}:{px_p}" if ativar_px else None
        req = RequestManager(API_KEY, proxy_url)
        proc = DataProcessor(banca_v, lucro_v, TOKEN_TELEGRAM, CHAT_ID_TELEGRAM)
        
        st.toast("Scanner Conectado!", icon="🛰️")
        
        status_card = st.empty()
        monitor_card = st.empty()
        historico = []

        while True:
            for esporte in ESPORTES_MASTER:
                status_card.markdown(f"🔍 Monitorando: **{esporte.replace('_', ' ').upper()}**")
                dados = asyncio.run(req.buscar_odds(esporte))
                
                if isinstance(dados, list):
                    for ev in dados:
                        try:
                            h, a = ev['home_team'], ev['away_team']
                            bks = ev.get('bookmakers', [])
                            if len(bks) < 2: continue
                            
                            o1, o2 = bks[0]['markets'][0]['outcomes'][0]['price'], bks[1]['markets'][0]['outcomes'][1]['price']
                            c1, c2 = bks[0]['title'], bks[1]['title']
                            
                            res = proc.calcular(o1, o2)
                            if res:
                                # EXIBIÇÃO EM CARD PROFISSIONAL
                                monitor_card.markdown(f"""
                                <div class="bet-card">
                                    <h3 style='margin:0; color:#10b981;'>🔥 {res['lucro']}% DE LUCRO!</h3>
                                    <p style='margin:5px 0;'><b>{h} x {away}</b></p>
                                    <hr style='border: 0.5px solid #30363d;'>
                                    <div style='display: flex; justify-content: space-between;'>
                                        <span>🏦 {c1}: <b>@{o1}</b></span>
                                        <span>➡️ <b>R$ {res['s1']}</b></span>
                                    </div>
                                    <div style='display: flex; justify-content: space-between;'>
                                        <span>🏦 {c2}: <b>@{o2}</b></span>
                                        <span>➡️ <b>R$ {res['s2']}</b></span>
                                    </div>
                                    <p style='margin-top:10px; font-size: 0.8em; color: #9ca3af;'>Retorno: R$ {res['ret']} | {datetime.now().strftime('%H:%M:%S')}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                msg = f"🎯 *SUREBET {res['lucro']}%*\n⚽ {h} x {a}\n💰 R${res['s1']} e R${res['s2']}"
                                asyncio.run(proc.enviar_tg(msg))
                                historico.insert(0, {"Hora": datetime.now().strftime("%H:%M"), "Evento": f"{h} x {a}", "Lucro": f"{res['lucro']}%"})
                        except: continue
                
                # Histórico simplificado abaixo
                if historico:
                    with st.expander("📋 Ver Histórico de Hoje"):
                        st.table(pd.DataFrame(historico).head(5))
            
            time.sleep(delay_v)
