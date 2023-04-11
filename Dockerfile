FROM python:3.10 as builder

RUN pip install poetry

COPY pyproject.toml pyproject.toml

COPY poetry.lock poetry.lock

RUN poetry install --no-dev

RUN poetry run pip freeze > requirements.txt 

FROM python:3.10-alpine as prod

RUN pip install pretty_errors && python -m pretty_errors -s

COPY --from=0 requirements.txt requirements.txt 

RUN pip install -r requirements.txt

RUN mkdir -p /logs

COPY bot /app/app

WORKDIR /app

ENV PYTHONPATH /app

ENV TZ=Asia/Shanghai

ENV LOG_LEVEL=20

ENV DEBUG=f

EXPOSE 8000

CMD python app/bot.py
