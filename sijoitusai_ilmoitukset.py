"""
SijoitusAI - Automaattiset Telegram-ilmoitukset
Kaynnistaaksesi: python sijoitusai_ilmoitukset.py
"""

import requests
import schedule
import time
from datetime import datetime

# --- ASETUKSET ---
TELEGRAM_TOKEN   = "8627280901:AAFSIOdXl53aEKkGwl8fCj6IEuivy_gKIDA"
TELEGRAM_CHAT_ID = "8780106046"
ALPHA_VANTAGE_KEY = "L7RKV8GVN2HAGGKF"

SEURATTAVAT = [
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "MSFT", "name": "Microsoft"},
    {"symbol": "NVDA", "name": "NVIDIA"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "SPY",  "name": "S&P 500 ETF"},
]

LASKU_RAJA   = -3.0
NOUSU_RAJA   =  3.0
TARKISTUS_VK = 1

# --- TELEGRAM ---
def laheta_viesti(teksti):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": teksti,
            "parse_mode": "HTML",
        })
        if r.ok:
            print(f"OK Viesti lahetetty: {teksti[:60]}...")
        else:
            print(f"VIRHE: {r.text}")
    except Exception as e:
        print(f"VIRHE: {e}")

# --- KURSSIHAKU ---
def hae_kurssi(symbol):
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
    try:
        r = requests.get(url, timeout=10)
        q = r.json().get("Global Quote", {})
        hinta = q.get("05. price")
        muutos_str = q.get("10. change percent", "0%")
        if not hinta:
            return None
        muutos = float(muutos_str.replace("%", "").strip())
        return {
            "hinta":   float(hinta),
            "muutos":  muutos,
            "korkein": float(q.get("03. high", 0)),
            "matalin": float(q.get("04. low", 0)),
        }
    except Exception as e:
        print(f"  Virhe haussa {symbol}: {e}")
        return None

# --- UUTISHAKU ---
def hae_uutiset():
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{
                    "role": "user",
                    "content": f"Hae tanaan ({datetime.now().strftime('%d.%m.%Y')}) tarkeimmat talousuutiset. Listaa max 3 lyhyesti. Vastaa suomeksi."
                }],
            },
            timeout=30,
        )
        data = res.json()
        return "".join(b.get("text", "") for b in data.get("content", []))
    except:
        return ""

# --- PAAANALYYSI ---
def tarkista_markkinat():
    nyt = datetime.now().strftime("%d.%m.%Y %H:%M")
    print(f"\nTarkistetaan markkinat... {nyt}")

    ilmoitukset = []
    kaikki_kurssit = []

    for osake in SEURATTAVAT:
        data = hae_kurssi(osake["symbol"])
        if not data:
            print(f"  {osake['symbol']}: ei dataa")
            continue

        muutos = data["muutos"]
        hinta  = data["hinta"]
        print(f"  {osake['symbol']}: ${hinta:.2f} ({muutos:+.2f}%)")

        kaikki_kurssit.append(f"<b>{osake['name']}</b> ${hinta:.2f} ({muutos:+.2f}%)")

        if muutos <= LASKU_RAJA:
            ilmoitukset.append(f"LASKU: <b>{osake['name']}</b> {muutos:.1f}% -> ${hinta:.2f}")
        elif muutos >= NOUSU_RAJA:
            ilmoitukset.append(f"NOUSU: <b>{osake['name']}</b> +{muutos:.1f}% -> ${hinta:.2f}")

        time.sleep(13)

    if ilmoitukset:
        viesti = f"<b>SijoitusAI HALYTYS</b> - {nyt}\n\n" + "\n".join(ilmoitukset)
        laheta_viesti(viesti)

    if datetime.now().hour == 9:
        uutiset = hae_uutiset()
        viesti = (
            f"<b>SijoitusAI Aamuyhteenveto</b> - {nyt}\n\n"
            "<b>Kurssit:</b>\n" + "\n".join(kaikki_kurssit)
            + (f"\n\n<b>Uutiset:</b>\n{uutiset}" if uutiset else "")
            + "\n\nEi virallista sijoitusneuvontaa"
        )
        laheta_viesti(viesti)

    print(f"  Valmis. Seuraava tarkistus {TARKISTUS_VK}h paasta.")

# --- KAYNNISTYS ---
if __name__ == "__main__":
    print("=" * 50)
    print("  SijoitusAI - Automaattiset ilmoitukset")
    print("=" * 50)

    laheta_viesti(
        f"<b>SijoitusAI kaynnistetty!</b>\n"
        f"Seuraan {len(SEURATTAVAT)} osaketta.\n"
        f"Halytysrajat: lasku {LASKU_RAJA}% / nousu +{NOUSU_RAJA}%\n"
        f"Tarkistusvaeli: {TARKISTUS_VK}h\n"
        "Aamuyhteenveto klo 9:00."
    )

    tarkista_markkinat()

