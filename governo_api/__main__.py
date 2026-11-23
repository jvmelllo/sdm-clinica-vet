"""Execução:  python -m governo_api"""
import logging

from .app import criar_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = criar_app()

if __name__ == "__main__":
    porta = app.config["SDM"]["PORT"]
    print(f"\n  API GOVERNAMENTAL SIMULADA em http://localhost:{porta}  (Swagger: /docs)\n")
    app.run(host="0.0.0.0", port=porta, debug=False, threaded=True)
