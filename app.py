import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
from datetime import datetime, timezone

# --- CONFIGURAÇÕES INTEGRADAS ---
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63"

ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "soccer_england_premier_league", "soccer_spain_la_liga",
    "basketball_nba", "tennis_atp_aus_open"
]

st.set_page_config(page_title="Surebet Turbo v4", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; }
    .bet-card { 
        background-color: #1c2128; padding: 15px; border-radius: 12px; 
        border-left: 8px solid #00ff88; margin-bottom: 15px; color: white;
    }
    .profit-tag { background-color: #00ff88; color: #000; padding: 2px 8px; border-radius: 10px; font-weight: bold; float: right; }
    .speed-tag { color: #8b949e; font-size: 0.8em; }
    </style>
    """, unsafe_allow_html=True)

class TurboScanner:
    def __init__(self, api_key, banca, lucro_min):
        self.api_key = api_key
        self.banca = banca
        self.lucro_min = lucro_min
        self.url_base = "https://api.the-odds-api.com/v4/sports/{}/odds/"

    def calcular_instantaneo(self, evento):
        try:
            bks = evento.get('bookmakers', [])
            if len(bks) < 2: return None
            
            # Pega as melhores odds em micro-segundos
            o1 = bks[0]['markets'][0]['outcomes'][0]['price']
            o2 = bks[1]['markets'][0]['outcomes'][1]['price']
            
            m = (1/o1) + (1/o2)
            if m < 1.0:
                lucro = (1-m)*100
                if lucro >= self.lucro_min:
                    s1 = round(((self.banca*(1/o1))/m)/5)*5
                    s2 = round((self.banca-s1)/5)*5
                    return {
                        "h": evento['home_team'], "a": evento['away_team'],
                        "l": round(lucro, 2), "c1": bks[0]['title'], "c2": bks[1]['title'],
                        "o1": o1, "o2": o2, "s1": s1, "s2": s2
                    }
        except: return None
        return None

    async def fetch_esporte(self, client, esporte):
        params = {"apiKey": self.api_key, "regions": "br", "markets": "h2h", "oddsFormat": "decimal"}
        try:
            start_time = time.time()
            r = await client.get(self.url_base.format(esporte), params=params)
            end_time = time.time()
            process_speed = round((end_time - start_time) * 1000, 2) # Milissegundos
            return r.json(), process_speed
        except: return [], 0

# --- UI PRINCIPAL ---
st.title("⚡ Surebet Turbo Scanner")

if 'log_turbo' not in st.session_state:
    st.session_state.log_turbo = []

col1, col2 = st.columns([1, 2])
with col1:
    banca_v = st.number_input("Banca Total (R$)", value=1000.0)
    lucro_v = st.slider("Lucro Mínimo %", 0.1, 5.0, 0.3)
    modo = st.radio("Foco", ["Ao Vivo", "Pré-Jogo"])
    btn_limpar = st.button("Limpar Tela")

if btn_limpar:
    st.session_state.log_turbo = []
    st.rerun()

scanner = TurboScanner(API_KEY, banca_v, lucro_v)
placeholder = st.empty()

if st.sidebar.button("ATIVAR TURBO MODE 🚀"):
    async def main_loop():
        # Cliente HTTP de alta performance (mantém conexão aberta)
        async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=20)) as client:
            while True:
                # DISPARA TODAS AS REQUISIÇÕES AO MESMO TEMPO (Async Gather)
                tasks = [scanner.fetch_esporte(client, esp) for esp in ESPORTES_MASTER]
                resultados = await asyncio.gather(*tasks)
                
                agora = datetime.now(timezone.utc).isoformat()
                is_live = (modo == "Ao Vivo")
                
                with placeholder.container():
                    for (dados, speed) in resultados:
                        if not isinstance(dados, list): continue
                        
                        for ev in dados:
                            # Filtro instantâneo de tempo
                            evento_in_play = ev.get('commence_time') <= agora
                            if evento_in_play != is_live: continue
                            
                            res = scanner.calcular_instantaneo(ev)
                            if res:
                                # Adiciona ao histórico se for novo
                                if not any(d['h'] == res['h'] for d in st.session_state.log_turbo[:10]):
                                    st.session_state.log_turbo.insert(0, res)
                                    st.toast(f"🔥 {res['l']}% encontrado!", icon="💰")

                                # Exibe o card imediatamente
                                st.markdown(f"""
                                <div class="bet-card">
                                    <span class="profit-tag">{res['l']}%</span>
                                    <div style="font-size:1.2em; font-weight:bold;">{res['h']} x {res['a']}</div>
                                    <div style="display:flex; justify-content:space-between; margin-top:10px;">
                                        <span>🏦 {res['c1']} (@{res['o1']}) ⮕ <b>R${res['s1']}</b></span>
                                        <span>🏦 {res['c2']} (@{res['o2']}) ⮕ <b>R${res['s2']}</b></span>
                                    </div>
                                    <div class="speed-tag">⚡ Latência API: {speed}ms | {datetime.now().strftime('%H:%M:%S')}</div>
                                </div>
                                """, unsafe_allow_html=True)
                
                await asyncio.sleep(5) # Delay curto para não ser bloqueado por IP

    asyncio.run(main_loop())
