FROM jupyter/base-notebook:python-3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
USER ${NB_UID}

RUN pip install --no-cache-dir \
    pandas==2.2.3 \
    matplotlib==3.10.0 \
    -r /tmp/requirements.txt

EXPOSE 8888