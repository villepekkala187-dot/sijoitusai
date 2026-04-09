"""
SijoitusAI - Automaattiset Telegram-ilmoitukset
Ajettava GitHub Actionsilla tunnin valein.
"""

import os
import time
import requests
from datetime import datetime

# --- ASETUKSET ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_CHAT_ID = "8780106046"

# Omat omistukset (ticker, nimi, kappaleet, hankintahinta euroissa)
OMAT_OMISTUKSET = [
    {"symbol": "LUG.ST",   "name": "Lundin Gold",          "kpl": 27, "hinta_eur": 58.87},
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
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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

# --- VALUUTTAKURSSIT ---
def hae_valuuttakurssit():
    """Hae EUR/USD ja SEK/EUR kurssit Yahoo Financesta."""
    kurssit = {"USD": 1.0, "EUR": 1.0, "SEK": 1.0, "CAD": 1.0, "GBP": 1.0}
    parit = [
        ("EURUSD=X", "USD"),   # 1 USD = X EUR
        ("SEKEUR=X", "SEK"),   # 1 SEK = X EUR
        ("CADEUR=X", "CAD"),   # 1 CAD = X EUR
        ("GBPEUR=X", "GBP"),   # 1 GBP = X EUR
    ]
    for symboli, valuutta in parit:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symboli}?interval=1d&range=1d"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, timeout=10, headers=headers)
            parsed = r.json()
            meta = parsed.get("chart", {}).get("result", [{}])[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price:
                kurssit[valuutta] = round(float(price), 6)
                print(f"  Valuutta 1 {valuutta} = {kurssit[valuutta]} EUR")
        except Exception as e:
            print(f"  Valuuttavirhe {symboli}: {e}")
        time.sleep(0.5)
    return kurssit

def muunna_euroiksi(hinta, valuutta, kurssit):
    """Muunna hinta euroiksi."""
    if valuutta == "EUR":
        return hinta
    kerroin = kurssit.get(valuutta)
    if kerroin and kerroin != 1.0:
        return hinta * kerroin
    return hinta  # fallback: palauta sellaisenaan

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
        valuutta = meta.get("currency", "USD")
        return {
            "hinta":  round(float(price), 2),
            "muutos": round(float(muutos), 2),
            "valuutta": valuutta,
        }
    except Exception as e:
        print(f"Virhe haussa {symbol}: {e}")
        return None

# --- CLAUDE ANALYYSI ---
def hae_analyysi(salkku_teksti, markkinat_teksti):
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY puuttuu, ohitetaan analyysi")
        return ""
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
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

# --- MARKKINAVAHTI (etsii osto/myyntimahdollisuuksia) ---
def markkinavahti(salkku_teksti, markkinat_teksti):
    """Claude analysoi web-haulla onko markkinoilla jotain poikkeavaa."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Olet markkinavahti. Hae tanaan ({datetime.now().strftime('%d.%m.%Y')}) "
                        f"tuoreimmat talousuutiset web-haulla ja arvioi onko markkinoilla juuri nyt "
                        f"jotain POIKKEUKSELLISTA joka vaatii sijoittajan huomiota.\n\n"
                        f"KAYTTAJAN SALKKU:\n{salkku_teksti}\n\n"
                        f"MARKKINATILANNE:\n{markkinat_teksti}\n\n"
                        f"Arvioi tilanne ja vastaa TASMALLISESTI nain:\n"
                        f"1. rivi: HALYTYS tai EI_HALYTYSTA (vain toinen naista)\n"
                        f"2. rivi eteenpain: Jos HALYTYS, selita lyhyesti (max 3 lausetta) "
                        f"mita tapahtui ja mita sijoittajan kannattaisi harkita.\n\n"
                        f"Herkkyys: Halyta vain kun on oikeasti merkittava tapahtuma - "
                        f"esim. yli 2% paivaliike indekseissa, yllattava keskuspankkipaatos, "
                        f"geopoliittinen kriisi, merkittava yrityskauppa salkun osakkeisiin liittyen, "
                        f"tai muu selkeasti poikkeuksellinen tilanne."
                    )
                }],
            },
            timeout=45,
        )
        data = res.json()
        vastaus = "".join(b.get("text", "") for b in data.get("content", []))
        return vastaus
    except Exception as e:
        print(f"Markkinavahti-virhe: {e}")
        return None

# --- PAAOHJELMA ---
def main():
    # Tarkista että Telegram-token on asetettu
    if not TELEGRAM_BOT_TOKEN:
        print("VIRHE: TELEGRAM_BOT_TOKEN puuttuu! Lisää se GitHub Secretsiin.")
        return

    nyt = datetime.now().strftime("%d.%m.%Y %H:%M")
    print(f"Tarkistetaan markkinat... {nyt}")

    # Hae valuuttakurssit ensin
    print("\nValuuttakurssit:")
    kurssit = hae_valuuttakurssit()

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
            # Muunna kurssi euroiksi
            hinta_eur = muunna_euroiksi(data["hinta"], data["valuutta"], kurssit)
            nykyarvo = hinta_eur * o["kpl"]
            arvo_yhteensa += nykyarvo
            tuotto_eur = nykyarvo - sijoitettu
            tuotto_pct = (tuotto_eur / sijoitettu) * 100
            muutos = data["muutos"]

            valuutta_info = f" ({data['valuutta']}→EUR)" if data["valuutta"] != "EUR" else ""
            print(f"  {o['symbol']}: {data['hinta']:.2f} {data['valuutta']} = {hinta_eur:.2f}EUR ({muutos:+.2f}%)")

            salkku_rivit.append(
                f"  {o['name']} ({o['symbol']}): {o['kpl']}kpl | "
                f"Hankinta: {o['hinta_eur']:.2f}EUR | "
                f"Nyt: {hinta_eur:.2f}EUR{valuutta_info} | "
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

        time.sleep(1)

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
        time.sleep(1)

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

    # --- MARKKINAVAHTI ---
    print("\nMarkkinavahti tarkistaa...")
    vahti_vastaus = markkinavahti(salkku_teksti, markkinat_teksti)
    if vahti_vastaus and "HALYTYS" in vahti_vastaus.upper().split("\n")[0]:
        # Poista ensimmäinen rivi (HALYTYS) ja lähetä loput
        rivit = vahti_vastaus.strip().split("\n")
        halytys_teksti = "\n".join(rivit[1:]).strip() if len(rivit) > 1 else vahti_vastaus
        vahti_viesti = (
            f"🚨 <b>MARKKINAVAHTI — HUOMIO!</b>\n\n"
            f"{halytys_teksti}\n\n"
            f"<i>⚠️ Yleista analyysia, ei sijoitusneuvontaa.</i>"
        )
        laheta_viesti(vahti_viesti)
        print("Markkinavahti: HALYTYS lahetetty!")
    else:
        print("Markkinavahti: ei halytettavaa.")

    print("\nValmis!")

if __name__ == "__main__":
    main()
