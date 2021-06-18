FROM quay.io/blueshoe/python3.8-slim as base
RUN apt update && apt install -y git curl gnupg

FROM base as builder

ENV PYTHONUNBUFFERED 1

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt
RUN pip install --prefix=/install -r /requirements.txt

#
# Production container
#
FROM base
RUN curl https://get.helm.sh/helm-v3.1.1-linux-amd64.tar.gz | tar xvz \
    && mv linux-amd64/helm /usr/local/bin/helm

RUN curl -L https://github.com/mozilla/sops/releases/download/v3.7.1/sops_3.7.1_amd64.deb --output sops_3.7.1_amd64.deb \
    && apt install ./sops_3.7.1_amd64.deb

RUN helm repo add stable https://charts.helm.sh/stable \
    && helm plugin install https://github.com/nico-ulbricht/helm-multivalues \
    && helm plugin install https://github.com/jkroepke/helm-secrets

# puts binaries like uwsgi/celery in $PATH
COPY --from=builder /install /usr/local
RUN mkdir /app
COPY src/ /app
WORKDIR /app

EXPOSE 8000
COPY deployment/run_app.sh /usr/src/run_app.sh
RUN chmod +x /usr/src/run_app.sh
CMD /usr/src/run_app.sh