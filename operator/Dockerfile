FROM quay.io/blueshoe/python3.9-slim AS build-env

ENV BUILD_ONLY_PACKAGES='wget' \
  # python:
  PYTHONFAULTHANDLER=1 \
  PYTHONHASHSEED=random \
  PYTHONDONTWRITEBYTECODE=1 \
  # pip:
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  # dockerize:
  DOCKERIZE_VERSION=v0.6.1 \
  # tini:
  TINI_VERSION=v0.19.0 \
  # poetry:
  POETRY_VERSION=1.1.5 \
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  PATH="$PATH:/root/.poetry/bin"

RUN apt-get update && apt-get upgrade -y \
  && apt-get install --no-install-recommends -y \
    curl \
  # Installing `poetry` package manager:
  # https://github.com/python-poetry/poetry
  && curl -sSL 'https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py' | python \
  && poetry --version \
  # Removing build-time-only dependencies:
  && apt-get remove -y $BUILD_ONLY_PACKAGES

RUN mkdir /app
WORKDIR /app

COPY . /app

# Project initialization:
RUN poetry install --no-dev --no-interaction --no-ansi \
  # Upgrading pip, it is insecure, remove after `pip@21.1`
  && poetry run pip install -U pip \
  # Cleaning poetry installation's cache for production:
  && rm -rf "$POETRY_CACHE_DIR"


FROM gcr.io/distroless/python3
COPY --from=build-env /app /app
WORKDIR /app
CMD kopf run main.py