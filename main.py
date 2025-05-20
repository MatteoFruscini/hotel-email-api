from flask import Flask, request, jsonify
import requests, re
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from playwright.sync_api import sync_playwright
import os
import time

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"

app = Flask(__name__)

def trova_sito(nome, indirizzo, citta):
    query = f"{nome} {indirizzo or ''} {citta} sito ufficiale"
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=5)
        for r in results:
            url = r.get('href')
            if url and "hotel" in url.lower():
                return url
    return None

def estrai_email(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)

            # Estrai tutti i mailto:
            mailto_links = page.eval_on_selector_all(
                "a[href^='mailto']",
                "els => els.map(el => el.getAttribute('href'))"
            )
            mailto_emails = []
            for href in mailto_links:
                match = re.match(r"mailto:([^?]+)", href)
                if match:
                    mailto_emails.append(match.group(1).strip())

            if mailto_emails:
                return mailto_emails[0]

            # Cerca nel testo visibile
            content = page.content()
            text = BeautifulSoup(content, "html.parser").get_text()
            email_match = re.search(EMAIL_REGEX, text)
            if email_match:
                return email_match.group(0)

            # Cerca pagina "Contatti"
            contact_links = page.eval_on_selector_all(
                "a",
                '''
                elements => elements
                    .map(el => el.href)
                    .filter(href => href && ['contatti', 'contact', 'contacts'].some(k => href.toLowerCase().includes(k)))
                '''
            )
            if contact_links:
                page.goto(contact_links[0], timeout=60000, wait_until="domcontentloaded")
                time.sleep(2)
                content = page.content()
                text = BeautifulSoup(content, "html.parser").get_text()
                email_match = re.search(EMAIL_REGEX, text)
                if email_match:
                    return email_match.group(0)

            browser.close()
    except Exception as e:
        print(f"Errore su {url}: {e}")
    return None

@app.route("/email", methods=["POST"])
def email():
    data = request.json
    nome = data.get("name")
    indirizzo = data.get("address", "")
    citta = data.get("city")

    sito = trova_sito(nome, indirizzo, citta)
    if sito:
        email = estrai_email(sito)
        return jsonify({"email": email or "", "url": sito})
    else:
        return jsonify({"email": "", "url": ""})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
