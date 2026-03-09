import streamlit as st
import pandas as pd
import httpx
import asyncio
import time
import random
from datetime import datetime

# =========================================================
# SEUS DADOS INTEGRADOS (NÃO PRECISA MAIS MEXER AQUI)
# =========================================================
API_KEY = "16616c59ffa4449f71d7f3e9f0086e63"
TOKEN_TELEGRAM = "8510184758:AAEv4k0_jOj5mDGeBVoh_OJW7mYK-nuJu7A"
CHAT_ID_TELEGRAM = "5679754900"

# Lista Global de Esportes
ESPORTES_MASTER = [
    "soccer_brazil_campeonato_brasileiro", "soccer_uefa_champs_league", 
    "basketball_nba", "americanfootball_nfl", "mma_mixed_martial_arts", 
    "tennis_atp_aus_open", "baseball_mlb", "volleyball_italy_superlega"
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
            "regions": "br",
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        
        # Configuração de Proxy (IP Fixo ou Rotativo)
        mounts = {}
        if self.proxy_url:
            # Uso de mounts para evitar erro de 'unexpected keyword argument proxies'
            transport = httpx.AsyncHTTPTransport(proxy=self.proxy_url)
            mounts = {"http://": transport, "https://": transport}

        async with httpx.AsyncClient(mounts=mounts, timeout=30.0) as client:
            try:
                r = await client.get(url, params=params)
                return r.json() if r.status_code == 200 else []
            except Exception as e:
                return []

class DataProcessor:
    def __init__(self, banca, lucro_min, token_tg, chat_id_tg):
        self.banca = banca
        self.lucro_min = lucro_min
        self.token_tg = token_tg
        self.chat_id_tg = chat_id_tg

    async def enviar_alerta_telegram(self, mensagem):
        url = f"https://api.telegram.org/bot{self.token_tg}/sendMessage"
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json={"chat_id": self.chat_id_tg, "text": mensagem, "parse_mode": "Markdown"})
                return resp.status_code == 200
            except:
                return False

    def calcular_arbitragem(self, o1, o2):
        margem = (1/o1) + (1/o2)
        if margem < 1.0:
            lucro = (1 - margem) * 100
            if lucro >= self.lucro_min:
                # Arredondamento para evitar limitação nas casas
                s1 = round(((self.banca * (1/o1)) / margem) / 5) * 5
                s2 = round((self.banca - s1) / 5) * 5
                ret = min(s1 * o1, s2 * o2)
                return {"lucro": round(lucro, 2), "s1": s1, "s2": s2, "ret": round(ret, 2)}
        return None

# =========================================================
# INTERFACE STREAMLIT
# =========================================================

st.set_page_config(page_title="Ultra Scanner Global", layout="wide")
st.title("🌍 Scanner de Arbitragem Profissional")

with st.sidebar:
    st.header("🛡️ Painel de Proxy")
    st.info("Suporta HTTP, HTTPS e SOCKS5 (IP Fixo ou Rotativo)")
    ativar_px = st.checkbox("Ativar Proxy")
    px_host = st.text_input("IP ou Host")
    px_port = st.text_input("Porta")
    px_user = st.text_input("Usuário (Opcional)")
    px_pass = st.text_input("Senha (Opcional)", type="password")
    
    st.divider()
    banca_input = st.number_input("Banca Total (R$)", value=1000.0)
    lucro_input = st.slider("Mínimo Lucro %", 0.1, 10.0, 1.0)
    delay_v = st.slider("Intervalo de Busca (seg)", 10, 60, 30)
    rodar = st.button("LIGAR SCANNER 🚀")

if rodar:
    proxy_url = None
    if ativar_px and px_host and px_port:
        if px_user and px_pass:
            proxy_url = f"http://{px_user}:{px_pass}@{px_host}:{px_port}"
        else:
            proxy_url = f"http://{px_host}:{px_port}"

    req = RequestManager(API_KEY, proxy_url)
    proc = DataProcessor(banca_input, lucro_input, TOKEN_TELEGRAM, CHAT_ID_TELEGRAM)
    
    st.success(f"✅ Scanner rodando! {'(Proxy Ativo)' if proxy_url else '(Sem Proxy)'}")
    
    # Elementos de atualização em tempo real no App
    aviso_top = st.empty()
    status_msg = st.empty()
    tabela_box = st.empty()
    
    historico = []

    while True:
        for esporte in ESPORTES_MASTER:
            status_msg.info(f"🔍 Varrendo: **{esporte.upper()}**")
            dados = asyncio.run(req.buscar_odds(esporte))
            
            if isinstance(dados, list):
                for evento in dados:
                    try:
                        home = evento.get('home_team')
                        away = evento.get('away_team')
                        bookies = evento.get('bookmakers', [])
                        if len(bookies) < 2: continue
                        
                        o1 = bookies[0]['markets'][0]['outcomes'][0]['price']
                        o2 = bookies[1]['markets'][0]['outcomes'][1]['price']
                        c1, c2 = bookies[0]['title'], bookies[1]['title']
                        
                        res = proc.calcular_arbitragem(o1, o2)
                        if res:
                            txt = (f"🔥 *SUREBET DETECTADA! ({res['lucro']}%)*\n"
                                   f"⚽ {home} x {away}\n"
                                   f"🏦 {c1}: @{o1} -> R${res['s1']}\n"
                                   f"🏦 {c2}: @{o2} -> R${res['s2']}\n"
                                   f"💰 Retorno: R${res['ret']}")
                            
                            # Alerta visual no App
                            aviso_top.success(txt.replace("*", ""))
                            
                            # Alerta no Telegram
                            tg_status = asyncio.run(proc.enviar_alerta_telegram(txt))
                            
                            historico.insert(0, {
                                "Hora": datetime.now().strftime("%H:%M:%S"),
                                "Evento": f"{home} x {away}",
                                "Lucro": f"{res['lucro']}%",
                                "Status TG": "✅" if tg_status else "❌"
                            })
                    except: continue

            # Atualiza tabela no App
            with tabela_box.container():
                if historico:
                    st.write("### 📋 Oportunidades Recentes")
                    st.table(pd.DataFrame(historico).head(10))
        
        time.sleep(delay_v + random.uniform(1, 4))
