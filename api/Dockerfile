FROM python:3.14-slim AS build

WORKDIR /src
COPY . ./
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ELCOURTSIDE_DB=/data/elcourtside.db

COPY --from=build /install /usr/local

RUN rm -rf /usr/local/lib/python*/site-packages/pip* \
           /usr/local/lib/python*/site-packages/setuptools* \
           /usr/local/lib/python*/site-packages/pkg_resources* \
           /usr/local/bin/pip*

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown app:app /data

USER app
WORKDIR /home/app

VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
