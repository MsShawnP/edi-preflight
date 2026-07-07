FROM python:3.13-slim

WORKDIR /app

# Dependencies are inlined here (rather than `pip install .`) to avoid
# needing a build backend — this is a deployed web app, not a packaged
# library. The list below MUST stay in sync with [project].dependencies
# in pyproject.toml.
RUN pip install --no-cache-dir \
    "fastapi>=0.100" \
    "uvicorn[standard]>=0.20" \
    "jinja2>=3.1" \
    "python-multipart>=0.0.7" \
    "reportlab>=4.0"

COPY src/ src/
COPY rules/ rules/
COPY samples/ samples/

RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
