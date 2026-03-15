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

# Foco: Futebol, NBA e Tênis
ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "soccer_england_premier_league", "soccer_spain_la_liga",
    "basketball_nba", "tennis_atp_aus_open"
]

# --- CSS E COMPONENTES DE INTERFACE ---
st.set_page_config(page_title="Surebet Elite v2", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .bet-card { 
        background-color: #161b22; 
        padding: 18px; 
        border-radius: 12px; 
        border-left: 5px solid #00d4ff;
        margin-bottom: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    .live-tag { color: #ff4b4b; font-weight: bold; border: 1px solid #ff4b4b; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; }
    .pre-tag { color: #00d4ff; font-weight: bold; border: 1px solid #00d4ff; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; }
    </style>
    """, unsafe_allow_html=True)

# Função para Alerta Sonoro (Beep de Notificação)
def play_notif_sound():
    audio_html = """
        <audio autoplay>
            <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

class RequestManager:
    def __init__(self, api_key, proxy_url=None):
        self.api_key = api_key
        self.proxy_url = proxy_url

    async def buscar_odds(self, esporte):
        url = f"https://api.the-odds-api.com/v4/sports/{esporte}/odds/"
        params = {"apiKey": self.api_key, "regions": "br", "markets": "h2h", "oddsFormat": "decimal"}
        mounts = {}
        if self.proxy_url:
            transport = httpx.AsyncHTTPTransport(proxy=self.proxy_url)
            mounts = {"http://": transport, "https://": transport}

        async with httpx.AsyncClient(mounts=mounts, timeout=25.0) as client:
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
            lucro = (1-m)*100
            if lucro >= self.lucro_min:
                s1 = round(((self.banca*(1/o1))/m)/5)*5
                s2 = round((self.banca-s1)/5)*5
                return {"lucro": round(lucro, 2), "s1": s1, "s2": s2, "ret": round(min(s1*o1, s2*o2), 2)}
        return None

# --- UI PRINCIPAL ---
st.title("🛰️ Elite Scanner: Fut | NBA | Tênis")

tab_live, tab_pre, tab_config = st.tabs(["🔴 AO VIVO", "📅 PRÉ-JOGO", "⚙️ CONFIGS"])

with tab_config:
    st.subheader("Configurações Gerais")
    banca_v = st.number_input("Banca Total (R$)", value=1000.0)
    lucro_v = st.slider("Lucro Mínimo %", 0.1, 5.0, 0.7)
    
    st.divider()
    ativar_px = st.toggle("Usar Proxy Pago")
    px_h = st.text_input("IP/Host")
    px_p = st.text_input("Porta")
    px_u = st.text_input("Usuário")
    px_s = st.text_input("Senha", type="password")

# Configuração de Proxy e Motores
proxy = f"http://{px_u}:{px_s}@{px_h}:{px_p}" if ativar_px and px_u else f"http://{px_h}:{px_p}" if ativar_px else None
req = RequestManager(API_KEY, proxy)
proc = DataProcessor(banca_v, lucro_v, TOKEN_TELEGRAM, CHAT_ID_TELEGRAM)

def rodar_scanner(modo_live):
    placeholder = st.empty()
    status_log = st.empty()
    
    while True:
        for esporte in ESPORTES_MASTER:
            status_log.write(f"🔄 Varrendo {esporte.replace('_',' ')}...")
            dados = asyncio.run(req.buscar_odds(esporte))
            
            if isinstance(dados, list):
                # Lógica de separação por tempo de início
                agora = datetime.utcnow().isoformat()
                eventos = [e for e in dados if e.get('bookmakers')]
                
                if modo_live:
                    # Filtra apenas o que começou ou está para começar em minutos (In-play)
                    filtrados = [e for e in eventos if e.get('commence_time') <= agora]
                else:
                    # Filtra apenas o que ainda vai começar (Pré-jogo)
                    filtrados = [e for e in eventos if e.get('commence_time') > agora]
                
                for ev in filtrados:
                    try:
                        h, a = ev['home_team'], ev['away_team']
                        bks = ev['bookmakers']
                        if len(bks) < 2: continue
                        
                        o1, o2 = bks[0]['markets'][0]['outcomes'][0]['price'], bks[1]['markets'][0]['outcomes'][1]['price']
                        res = proc.calcular(o1, o2)
                        
                        if res:
                            # TOCA O SOM DE ALERTA
                            play_notif_sound()
                            
                            tag = "<span class='live-tag'>LIVE</span>" if modo_live else "<span class='pre-tag'>PRÉ</span>"
                            card_html = f"""
                            <div class="bet-card">
                                {tag} <b style='font-size:1.1em;'>{h} x {a}</b>
                                <hr style='border:0.1px solid #30363d; margin:10px 0;'>
                                <p style='margin:0; color:#00ff88;'>💰 <b>LUCRO: {res['lucro']}%</b></p>
                                <p style='margin:0;'>🏦 {bks[0]['title']}: @{o1} ⮕ <b>R${res['s1']}</b></p>
                                <p style='margin:0;'>🏦 {bks[1]['title']}: @{o2} ⮕ <b>R${res['s2']}</b></p>
                            </div>
                            """
                            placeholder.markdown(card_html, unsafe_allow_html=True)
                            
                            msg = f"{'🔴 LIVE' if modo_live else '📅 PRÉ'} *SUREBET {res['lucro']}%*\n🏆 {h} x {a}\n💰 R${res['s1']} e R${res['s2']}"
                            asyncio.run(proc.enviar_tg(msg))
                    except: continue
        time.sleep(25)

with tab_live:
    if st.button("LIGAR SCANNER AO VIVO 🚀", use_container_width=True):
        rodar_scanner(modo_live=True)

with tab_pre:
    if st.button("LIGAR SCANNER PRÉ-JOGO 📅", use_container_width=True):
        rodar_scanner(modo_live=False)
