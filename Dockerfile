FROM python:3.10 as builder

COPY . .

RUN pip install poetry

RUN poetry config virtualenvs.create false

RUN poetry build 

FROM python:3.10-alpine as prod

RUN mkdir -p /logs

COPY --from=0 /dist /dist

COPY --from=0 /config /config

RUN pip install /dist/*.whl

RUN rm -rf /dist

RUN python -m pretty_errors -s

CMD main
