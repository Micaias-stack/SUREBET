import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
import random
from datetime import datetime, timezone

# --- CONFIGURAÇÕES INTEGRADAS ---
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63"
TOKEN_TELEGRAM = "8510184758:AAEv4k0_jOj5mDGeBVoh_OJW7mYK-nuJu7A"
CHAT_ID_TELEGRAM = "5679754900"

ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "soccer_england_premier_league", "soccer_spain_la_liga",
    "basketball_nba", "tennis_atp_aus_open"
]

st.set_page_config(page_title="Surebet Elite v3", layout="wide")

# --- CSS PERSONALIZADO PARA VISUALIZAÇÃO DIRETA ---
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .bet-card { 
        background-color: #1c2128; 
        padding: 20px; 
        border-radius: 15px; 
        border-left: 8px solid #00ff88;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        color: white;
    }
    .card-header { font-size: 1.3em; font-weight: bold; color: #00d4ff; }
    .profit-tag { background-color: #00ff88; color: #000; padding: 3px 10px; border-radius: 20px; font-weight: bold; float: right; }
    .house-row { display: flex; justify-content: space-between; margin-top: 10px; font-size: 1.1em; }
    </style>
    """, unsafe_allow_html=True)

def play_notif_sound():
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

class RequestManager:
    def __init__(self, api_key):
        self.api_key = api_key

    async def buscar_odds(self, esporte):
        url = f"https://api.the-odds-api.com/v4/sports/{esporte}/odds/"
        params = {"apiKey": self.api_key, "regions": "br", "markets": "h2h", "oddsFormat": "decimal"}
        # Removido proxies temporariamente para garantir estabilidade máxima no App
        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                r = await client.get(url, params=params)
                return r.json() if r.status_code == 200 else []
            except: return []

class DataProcessor:
    def __init__(self, banca, lucro_min):
        self.banca, self.lucro_min = banca, lucro_min

    def calcular(self, o1, o2):
        m = (1/o1) + (1/o2)
        if m < 1.0:
            lucro = (1-m)*100
            if lucro >= self.lucro_min:
                s1 = round(((self.banca*(1/o1))/m)/5)*5
                s2 = round((self.banca-s1)/5)*5
                return {"lucro": round(lucro, 2), "s1": s1, "s2": s2, "ret": round(min(s1*o1, s2*o2), 2)}
        return None

# --- UI PRINCIPAL ---
st.title("🛰️ Central de Entradas Diretas")

if 'historico_real' not in st.session_state:
    st.session_state.historico_real = []

tab_live, tab_pre, tab_ajustes = st.tabs(["🔴 ENTRADAS AO VIVO", "📅 PRÉ-JOGO", "⚙️ CONFIGS"])

with tab_ajustes:
    banca_v = st.number_input("Sua Banca Total (R$)", value=1000.0)
    lucro_v = st.slider("Lucro Mínimo Desejado %", 0.1, 5.0, 0.4)
    st.info("O sistema atualizará automaticamente a cada 30 segundos.")

proc = DataProcessor(banca_v, lucro_v)
req = RequestManager(API_KEY)

def mostrar_scanner(modo_live):
    placeholder_cards = st.empty()
    status_msg = st.sidebar.empty()
    
    while True:
        status_msg.write(f"🔄 Varrendo mercados às {datetime.now().strftime('%H:%M:%S')}...")
        
        novas_oportunidades = []
        for esporte in ESPORTES_MASTER:
            dados = asyncio.run(req.buscar_odds(esporte))
            if isinstance(dados, list):
                agora = datetime.now(timezone.utc).isoformat()
                eventos = [e for e in dados if (e.get('commence_time') <= agora if modo_live else e.get('commence_time') > agora)]
                
                for ev in eventos:
                    try:
                        h, a = ev['home_team'], ev['away_team']
                        bks = ev.get('bookmakers', [])
                        if len(bks) < 2: continue
                        
                        o1, o2 = bks[0]['markets'][0]['outcomes'][0]['price'], bks[1]['markets'][0]['outcomes'][1]['price']
                        res = proc.calcular(o1, o2)
                        
                        if res:
                            res.update({"h": h, "a": a, "c1": bks[0]['title'], "c2": bks[1]['title'], "o1": o1, "o2": o2})
                            novas_oportunidades.append(res)
                            
                            # Evitar duplicados no histórico da sessão
                            if not any(d['h'] == h and d['a'] == a for d in st.session_state.historico_real):
                                st.session_state.historico_real.insert(0, res)
                                play_notif_sound()
                    except: continue

        # EXIBIÇÃO EM CARDS DIRETOS NO APP
        with placeholder_cards.container():
            if novas_oportunidades:
                for op in novas_oportunidades:
                    st.markdown(f"""
                    <div class="bet-card">
                        <span class="profit-tag">{op['lucro']}%</span>
                        <div class="card-header">{op['h']} x {op['a']}</div>
                        <div class="house-row">
                            <span>🏠 {op['c1']} (@{op['o1']})</span>
                            <span><b>💰 R${op['s1']}</b></span>
                        </div>
                        <div class="house-row">
                            <span>🏠 {op['c2']} (@{op['o2']})</span>
                            <span><b>💰 R${op['s2']}</b></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("🔍 Monitorando... Nenhuma entrada detectada agora. O sistema vai bipar quando achar.")
        
        time.sleep(30)

with tab_live:
    if st.button("LIGAR SCANNER LIVE 🚀"):
        mostrar_scanner(modo_live=True)

with tab_pre:
    if st.button("LIGAR SCANNER PRÉ-JOGO 📅"):
        mostrar_scanner(modo_live=False)
