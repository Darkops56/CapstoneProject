FROM apify/actor-python:3.11

# Dependencias del sistema requeridas para librerías espaciales
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

USER myuser

# Copiar e instalar librerías Python
COPY --chown=myuser:myuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar artefactos entrenados, geo-caché y código fuente
COPY --chown=myuser:myuser artifacts/ ./artifacts/
COPY --chown=myuser:myuser reference_geo/ ./reference_geo/
COPY --chown=myuser:myuser src/ ./src/
COPY --chown=myuser:myuser .actor/ ./.actor/

ENV PYTHONPATH="/usr/src/app:${PYTHONPATH}"

# Entrypoint estándar de Apify
CMD ["python3", "-m", "src.main"]
