#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor web para converter PDFs do Bionexo em Excel.
Uso: python app.py
Acesse: http://localhost:5000
"""

import os
import uuid
from flask import Flask, render_template, request, send_file, jsonify
from converter_bionexo import process_pdf_buffer, save_excel_buffer

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# Cache em memória: token -> lista de registros extraídos
_cache = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/converter", methods=["POST"])
def converter():
    if "pdf" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["pdf"]

    if not file.filename:
        return jsonify({"error": "Nome de arquivo vazio"}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "O arquivo deve ser um PDF"}), 400

    pdf_bytes = file.read()

    try:
        data = process_pdf_buffer(pdf_bytes)
    except Exception as e:
        return jsonify({"error": "Erro ao processar PDF: {}".format(str(e))}), 500

    if not data:
        return jsonify({"error": "Nenhum dado extraído. Verifique se o PDF é um relatório Bionexo válido."}), 422

    try:
        buf = save_excel_buffer(data)
    except Exception as e:
        return jsonify({"error": "Erro ao gerar Excel: {}".format(str(e))}), 500

    if buf is None:
        return jsonify({"error": "Falha ao gerar planilha Excel"}), 500

    # Guarda dados no cache para reuso no consolidado
    token = str(uuid.uuid4())
    _cache[token] = data

    base_name = os.path.splitext(file.filename)[0]
    output_name = base_name + ".xlsx"

    response = send_file(
        buf,
        as_attachment=True,
        download_name=output_name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["X-Cache-Token"] = token
    return response


@app.route("/consolidar", methods=["POST"])
def consolidar():
    tokens = request.json.get("tokens", []) if request.is_json else []

    if len(tokens) < 2:
        return jsonify({"error": "Tokens insuficientes para consolidar"}), 400

    all_data = []
    for token in tokens:
        if token not in _cache:
            return jsonify({"error": "Sessão expirada. Reconverta os arquivos."}), 400
        all_data.extend(_cache[token])

    if not all_data:
        return jsonify({"error": "Nenhum dado disponível para consolidar"}), 422

    try:
        buf = save_excel_buffer(all_data)
    except Exception as e:
        return jsonify({"error": "Erro ao gerar Excel consolidado: {}".format(str(e))}), 500

    if buf is None:
        return jsonify({"error": "Falha ao gerar planilha consolidada"}), 500

    return send_file(
        buf,
        as_attachment=True,
        download_name="Consolidado_Bionexo.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  Conversor Bionexo PDF -> Excel")
    print("  Acesse: http://localhost:{}".format(port))
    print("=" * 50)
    app.run(debug=False, port=port, host="0.0.0.0")
