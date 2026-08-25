FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY showdoc2md ./showdoc2md

RUN python -m pip install --no-cache-dir .

EXPOSE 18765

ENTRYPOINT ["showdoc2md"]
CMD ["mcp", "--host", "0.0.0.0", "--port", "18765", "--allowed-host", "localhost", "--allowed-host", "127.0.0.1"]
