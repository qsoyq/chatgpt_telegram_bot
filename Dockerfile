FROM python:3.10 as builder

COPY . .

RUN pip install poetry

RUN poetry config virtualenvs.create false

RUN poetry build 

FROM python:3.10-alpine as prod

ENV TZ=Asia/Shanghai

ENV LOG_LEVEL=20

ENV DEBUG=f

RUN mkdir -p /logs

COPY --from=0 /dist /dist

RUN pip install /dist/*.whl

RUN rm -rf /dist

RUN python -m pretty_errors -s

EXPOSE 8000

CMD main
