FROM python:3.13-slim

WORKDIR /app

# Install dependencies (extracted from pyproject.toml to avoid needing
# a build backend — this is a web app, not a distributable package)
RUN pip install --no-cache-dir \
    "fastapi>=0.100" \
    "uvicorn[standard]>=0.20" \
    "jinja2>=3.1" \
    "python-multipart>=0.0.7" \
    "reportlab>=4.0"

COPY src/ src/
COPY rules/ rules/
COPY samples/ samples/

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
