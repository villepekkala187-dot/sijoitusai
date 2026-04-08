"""
SijoitusAI - Automaattiset Telegram-ilmoitukset
Ajettava GitHub Actionsilla tunnin valein.
"""

import requests
from datetime import datetime

# --- ASETUKSET ---
TELEGRAM_TOKEN   = "8627280901:AAFSIOdXl53aEKkGwl8fCj6IEuivy_gKIDA"
TELEGRAM_CHAT_ID = "8780106046"

# Omat omistukset (ticker, nimi, kappaleet, hankintahinta euroissa)
OMAT_OMISTUKSET = [
    {"symbol": "LUG.TO",   "name": "Lundin Gold",          "kpl": 27, "hinta_eur": 58.87},
    {"symbol": "LYSX.DE",  "name": "Amundi Euro Stoxx 50",  "kpl": 1,  "hinta_eur": 58.05},
    {"symbol": "MEKKO.HE", "name": "Marimekko",             "kpl": 1,  "hinta_eur": 11.40},
    {"symbol": "FIA1S.HE", "name": "Finnair",               "kpl": 4,  "hinta_eur": 3.00},
]

# Yleisesti seurattavat markkinat
SEURATTAVAT = [
    {"symbol": "SPY",  "name": "S&P 500 ETF"},
    {"symbol": "GLD",  "name": "Kulta ETF"},
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "NVDA", "name": "NVIDIA"},
]

LASKU_RAJA = -3.0
NOUSU_RAJA =  3.0

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
            print(f"OK: Viesti lahetetty")
        else:
            print(f"VIRHE: {r.text}")
    except Exception as e:
        print(f"VIRHE: {e}")

# --- KURSSIHAKU (Yahoo Finance - toimii kaikille pörsseille) ---
def hae_kurssi(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=10, headers=headers)
        parsed = r.json()
        meta = parsed.get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if not price:
            return None
        prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        muutos = ((price - prev) / prev * 100) if prev else 0
        return {
            "hinta":  round(float(price), 2),
            "muutos": round(float(muutos), 2),
        }
    except Exception as e:
        print(f"Virhe haussa {symbol}: {e}")
        return None

# --- CLAUDE ANALYYSI ---
def hae_analyysi(salkku_teksti, markkinat_teksti):
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 800,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Hae tanaan ({datetime.now().strftime('%d.%m.%Y')}) tarkeimmat talousuutiset "
                        f"ja analysoi niiden vaikutus sijoittajalle.\n\n"
                        f"KAYTTAJAN SALKKU:\n{salkku_teksti}\n\n"
                        f"MARKKINATILANNE:\n{markkinat_teksti}\n\n"
                        f"Anna lyhyt analyysi (max 5 lausetta) suomeksi:\n"
                        f"1. Mita taman paivan uutiset tarkoittavat salkun kannalta?\n"
                        f"2. Onko jotain syyta ostaa, myyda tai pitaa silmalla?\n"
                        f"3. Yksi konkreettinen vinkki tanaan.\n"
                        f"Muistuta lopussa lyhyesti etta kyseessa on yleinen analyysi eika virallinen sijoitusneuvonta."
                    )
                }],
            },
            timeout=45,
        )
        data = res.json()
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as e:
        print(f"Analyysivirhe: {e}")
        return ""

# --- PAAOHJELMA ---
def main():
    nyt = datetime.now().strftime("%d.%m.%Y %H:%M")
    print(f"Tarkistetaan markkinat... {nyt}")

    import time

    # Hae omat omistukset
    salkku_rivit = []
    halytykset = []
    sijoitettu_yhteensa = 0
    arvo_yhteensa = 0

    print("\nOmat omistukset:")
    for o in OMAT_OMISTUKSET:
        data = hae_kurssi(o["symbol"])
        sijoitettu = o["kpl"] * o["hinta_eur"]
        sijoitettu_yhteensa += sijoitettu

        if data:
            nykyarvo = data["hinta"] * o["kpl"]
            arvo_yhteensa += nykyarvo
            tuotto_eur = nykyarvo - sijoitettu
            tuotto_pct = (tuotto_eur / sijoitettu) * 100
            muutos = data["muutos"]

            print(f"  {o['symbol']}: {data['hinta']:.2f}EUR ({muutos:+.2f}%)")

            salkku_rivit.append(
                f"  {o['name']} ({o['symbol']}): {o['kpl']}kpl | "
                f"Hankinta: {o['hinta_eur']:.2f}EUR | "
                f"Nyt: {data['hinta']:.2f}EUR | "
                f"Tuotto: {tuotto_eur:+.2f}EUR ({tuotto_pct:+.1f}%)"
            )

            if muutos <= LASKU_RAJA:
                halytykset.append(f"LASKU: <b>{o['name']}</b> {muutos:.1f}% tanaan!")
            elif muutos >= NOUSU_RAJA:
                halytykset.append(f"NOUSU: <b>{o['name']}</b> +{muutos:.1f}% tanaan!")
        else:
            arvo_yhteensa += sijoitettu
            salkku_rivit.append(f"  {o['name']} ({o['symbol']}): ei kurssidataa")
            print(f"  {o['symbol']}: ei dataa")

        time.sleep(1)  # Pieni tauko pyyntöjen välillä

    # Hae markkinatilanne
    markkinat_rivit = []
    print("\nMarkkinat:")
    for s in SEURATTAVAT:
        data = hae_kurssi(s["symbol"])
        if data:
            print(f"  {s['symbol']}: {data['hinta']:.2f} ({data['muutos']:+.2f}%)")
            markkinat_rivit.append(f"  {s['name']}: {data['hinta']:.2f} ({data['muutos']:+.2f}%)")
        else:
            print(f"  {s['symbol']}: ei dataa")
        time.sleep(1)  # Pieni tauko pyyntöjen välillä

    # Laske salkun kokonaistuotto
    kokonaistuotto = arvo_yhteensa - sijoitettu_yhteensa
    kokonaistuotto_pct = (kokonaistuotto / sijoitettu_yhteensa * 100) if sijoitettu_yhteensa > 0 else 0

    salkku_teksti = "\n".join(salkku_rivit)
    markkinat_teksti = "\n".join(markkinat_rivit)

    # Hae Claude-analyysi
    print("\nHaetaan analyysia...")
    analyysi = hae_analyysi(salkku_teksti, markkinat_teksti)

    # Rakenna Telegram-viesti
    viesti = (
        f"<b>SijoitusAI paivittainen raportti</b> - {nyt}\n\n"
        f"<b>Oma salkku:</b>\n{salkku_teksti}\n\n"
        f"<b>Salkku yhteensa:</b> Sijoitettu {sijoitettu_yhteensa:.2f}EUR | "
        f"Arvo nyt {arvo_yhteensa:.2f}EUR | "
        f"Tuotto {kokonaistuotto:+.2f}EUR ({kokonaistuotto_pct:+.1f}%)\n\n"
        f"<b>Markkinat:</b>\n{markkinat_teksti}\n\n"
    )

    if halytykset:
        viesti += f"<b>HALYTYKSET:</b>\n" + "\n".join(halytykset) + "\n\n"

    if analyysi:
        viesti += f"<b>AI-analyysi:</b>\n{analyysi}"

    laheta_viesti(viesti)
    print("\nValmis!")

if __name__ == "__main__":
    main()
