"""python scripts/run_all.py"""
import logging

from .app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = create_app()

if __name__ == "__main__":
    porta = app.config["SDM"]["PORT"]
    print(f"\n  Clínica Veterinária (API privada + frontend) em http://localhost:{porta}\n"
          f"  Swagger: http://localhost:{porta}/docs\n")
    app.run(host="0.0.0.0", port=porta, debug=False, threaded=True)
