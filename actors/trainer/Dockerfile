FROM apify/actor-python:3.11

USER root
# Dependencias necesarias para librerías C/C++ y compilación de ML si es requerido
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

USER myuser

# Copiar dependencias de Python e instalar
COPY --chown=myuser:myuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del trainer y esquemas de Apify
COPY --chown=myuser:myuser src/ ./src/
COPY --chown=myuser:myuser .actor/ ./.actor/

ENV PYTHONPATH="/usr/src/app:${PYTHONPATH}"

# Entrypoint dual CLI / Apify SDK
CMD ["python3", "-m", "src.main"]
