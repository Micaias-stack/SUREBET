import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
from datetime import datetime

# --- CONFIGURAÇÕES TÉCNICAS (Edite aqui ou use a barra lateral) ---
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63" # Pegue em the-odds-api.com
TOKEN_TELEGRAM = "8510184758:AAEv4k0_jOj5mDGeBVoh_OJW7mYK-nuJu7A"
CHAT_ID_TELEGRAM = "5679754900"

# --- FUNÇÃO DE ALERTA TELEGRAM ---
async def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={"chat_id": CHAT_ID_TELEGRAM, "text": mensagem, "parse_mode": "Markdown"})
        except:
            pass

# --- CÁLCULO DE ARBITRAGEM ---
def calcular_surebet(odd_h, odd_a, banca, arredondar=True):
    prob = (1/odd_h) + (1/odd_a)
    if prob < 1.0:
        lucro_p = (1 - prob) * 100
        s1 = (banca * (1/odd_h)) / prob
        s2 = banca - s1
        
        if arredondar:
            s1 = round(s1 / 5) * 5
            s2 = round(s2 / 5) * 5
            lucro_real = min(s1 * odd_h, s2 * odd_a) - (s1 + s2)
            lucro_p = (lucro_real / (s1 + s2)) * 100
            
        return {"lucro": round(lucro_p, 2), "s1": s1, "s2": s2}
    return None

# --- COLETA DE DADOS (LIVE) ---
async def buscar_odds():
    # Foca no Brasileirão e casas BR
    url = "https://api.the-odds-api.com/v4/sports/soccer_brazil_campeonato_brasileiro/odds/"
    params = {"apiKey": API_KEY, "regions": "br", "markets": "h2h"}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, params=params)
            return r.json() if r.status_code == 200 else []
        except: return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Surebet Bot BR", layout="wide")
st.title("📲 Bot de Arbitragem Live BR")

with st.sidebar:
    st.header("Configurações")
    banca_user = st.number_input("Banca Disponível (R$)", value=500.0)
    lucro_min = st.slider("Lucro Mínimo %", 0.5, 5.0, 1.5)
    delay = st.slider("Check a cada (segundos)", 5, 60, 10)
    ativo = st.button("LIGAR SCANNER 🚀")

if ativo:
    st.warning("Scanner Rodando... Mantenha a aba aberta ou verifique o Telegram.")
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            dados = asyncio.run(buscar_odds())
            current_ts = datetime.now().strftime("%H:%M:%S")
            st.write(f"Última varredura: {current_ts}")
            
            if dados:
                for evento in dados:
                    home = evento['home_team']
                    away = evento['away_team']
                    
                    # Busca melhores odds entre todas as casas autorizadas
                    m_h = {"o": 0, "c": ""}
                    m_a = {"o": 0, "c": ""}
                    
                    for book in evento.get('bookmakers', []):
                        casa = book['title']
                        for outcome in book['markets'][0]['outcomes']:
                            if outcome['name'] == home and outcome['price'] > m_h['o']:
                                m_h = {"o": outcome['price'], "c": casa}
                            if outcome['name'] == away and outcome['price'] > m_a['o']:
                                m_a = {"o": outcome['price'], "c": casa}
                    
                    # Verifica se deu Surebet
                    res = calcular_surebet(m_h['o'], m_a['o'], banca_user)
                    if res and res['lucro'] >= lucro_min:
                        msg = (f"🔥 *SUREBET {res['lucro']}%*\n"
                               f"⚽ {home} x {away}\n"
                               f"🏦 {m_h['c']}: Odd {m_h['o']} -> *R$ {res['s1']}*\n"
                               f"🏦 {m_a['c']}: Odd {m_a['o']} -> *R$ {res['s2']}*")
                        
                        st.success(msg.replace('*', ''))
                        asyncio.run(enviar_telegram(msg))
            
            time.sleep(delay)
