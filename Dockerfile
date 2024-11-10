FROM python:3.12-slim

WORKDIR /code

COPY pyproject.toml .
COPY pdm.lock .

RUN pip3 install "pdm<3"

RUN pdm install --global --project . --production --fail-fast --frozen-lockfile

COPY . .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
