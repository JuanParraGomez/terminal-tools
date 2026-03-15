FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
RUN pip install --no-cache-dir -e .
ENV APP_HOST=0.0.0.0 APP_PORT=8090
# Bake tool paths so they're available in ALL shells (including login shells via docker exec)
ENV PATH="/opt/google-cloud-host/google-cloud-sdk/bin:/opt/fnm-host/node-versions/v22.22.0/installation/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV CLOUDSDK_CONFIG=/root/.config/gcloud
ENV CODEX_HOME=/root/.codex
# Write to /etc/profile.d/ and /etc/environment so login shells (-l) also pick up the paths
RUN echo 'export PATH="/opt/google-cloud-host/google-cloud-sdk/bin:/opt/fnm-host/node-versions/v22.22.0/installation/bin:$PATH"' > /etc/profile.d/tool-paths.sh \
    && echo 'export CLOUDSDK_CONFIG=/root/.config/gcloud' >> /etc/profile.d/tool-paths.sh \
    && echo 'export CODEX_HOME=/root/.codex' >> /etc/profile.d/tool-paths.sh \
    && echo "PATH=/opt/google-cloud-host/google-cloud-sdk/bin:/opt/fnm-host/node-versions/v22.22.0/installation/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/environment
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
