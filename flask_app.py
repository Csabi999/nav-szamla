import hashlib
import time
import uuid
import requests
from flask import Flask, render_template_string, request
import os

application = Flask(__name__)

NAV_URL = "https://api-test.onlineszamla.nav.gov.hu/invoiceService/v3/queryInvoiceDigest"

def generate_nav_signature(signature_key, request_id, timestamp):
    data = request_id + timestamp + signature_key
    hasher = hashlib.sha3_512()
    hasher.update(data.encode('utf-8'))
    return hasher.hexdigest().upper()

HTML_TEMPLATE = """
<!doctype html>
<html lang="hu">
<head>
    <meta charset="utf-8">
    <title>NAV Számla Nézegető</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <h2 class="mb-4">NAV Élő Számla Lekérdező (Render)</h2>

        <div class="card p-3 mb-4 shadow-sm">
            <h5>Technikai Felhasználó Adatai</h5>
            <form method="POST" action="/lekerdezes">
                <div class="mb-3">
                    <label class="form-label">Adószám:</label>
                    <input type="text" name="adoszam" class="form-control" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Technikai Felhasználó Neve:</label>
                    <input type="text" name="tech_user" class="form-control" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Aláíró Kulcs (Signature Key):</label>
                    <input type="password" name="sig_key" class="form-control" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Technikai Felhasználó Jelszava:</label>
                    <input type="password" name="tech_password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-success">Kapcsolódás a NAV-hoz</button>
            </form>
        </div>

        {% if hiba %}
        <div class="alert alert-danger">{{ hiba }}</div>
        {% endif %}

        {% if szamlak %}
        <div class="card p-3 shadow-sm">
            <h5>Lekérdezett számlák</h5>
            <table class="table table-striped mt-3">
                <thead>
                    <tr>
                        <th>Számlaszám</th>
                        <th>Irány</th>
                        <th>Dátum</th>
                    </tr>
                </thead>
                <tbody>
                    {% for szamla in szamlak %}
                    <tr>
                        <td>{{ szamla.invoiceNumber }}</td>
                        <td>{{ szamla.invoiceDirection }}</td>
                        <td>{{ szamla.invoiceDate }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@application.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, szamlak=None, hiba=None)

@application.route('/lekerdezes', methods=['POST'])
def lekerdezes():
    adoszam = request.form.get('adoszam')
    tech_user = request.form.get('tech_user')
    sig_key = request.form.get('sig_key')
    tech_password = request.form.get('tech_password')

    if not tech_password:
        return render_template_string(HTML_TEMPLATE, szamlak=None, hiba="A jelszó mező kitöltése kötelező!")

    password_hash = hashlib.sha256(tech_password.encode('utf-8')).hexdigest().upper()

    request_id = str(uuid.uuid4()).replace("-", "").upper()[:30]
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    signature = generate_nav_signature(sig_key, request_id, timestamp)

    xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
    <QueryInvoiceDigestRequest xmlns="http://schemas.nav.gov.hu/OSA/3.0/api" xmlns:common="http://schemas.nav.gov.hu/OSA/3.0/common">
        <common:header>
            <common:requestId>{request_id}</common:requestId>
            <common:timestamp>{timestamp}</common:timestamp>
            <common:requestVersion>3.0</common:requestVersion>
            <common:headerVersion>1.0</common:headerVersion>
        </common:header>
        <common:user>
            <common:login>{tech_user}</common:login>
            <common:passwordHash>{password_hash}</common:passwordHash>
            <common:taxNumber>{adoszam}</common:taxNumber>
            <common:signature>{signature}</common:signature>
        </common:user>
        <page>1</page>
        <mandatoryQueryParams>
            <invoiceIssueDate>
                <dateFrom>2026-01-01</dateFrom>
                <dateTo>2026-03-03</dateTo>
            </invoiceIssueDate>
        </mandatoryQueryParams>
    </QueryInvoiceDigestRequest>
    """

    headers = {'Content-Type': 'application/xml; charset=utf-8'}

    try:
        response = requests.post(NAV_URL, data=xml_payload.encode('utf-8'), headers=headers, timeout=15)

        if response.status_code == 200:
            minta_eredmeny = [
                {"invoiceNumber": "RENDER-SIKERES-KAPCSOLODAS", "invoiceDirection": "ONLINE", "invoiceDate": "2026-03-03"}
            ]
            return render_template_string(HTML_TEMPLATE, szamlak=minta_eredmeny, hiba=None)
        else:
            return render_template_string(HTML_TEMPLATE, szamlak=None, hiba=f"NAV Hiba (Státusz: {response.status_code}): {response.text}")

    except Exception as e:
        return render_template_string(HTML_TEMPLATE, szamlak=None, hiba=f"Hálózati hiba történt: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    application.run(host="0.0.0.0", port=port)
