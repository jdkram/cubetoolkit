FROM debian:bookworm AS base

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
  && apt-get install --yes --no-install-recommends \
  python3 \
  python3-venv \
  vim-tiny \
  libmariadb3 \
  libmagic1 \
  poppler-utils \
  wait-for-it \
  && DEBIAN_FRONTEND=noninteractive apt-get clean \
  && rm -rf /var/lib/apt/lists/*

## Use an intermediate image to build dependency wheels:
FROM base AS build

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
  && apt-get install --yes --no-install-recommends \
  python3-pip \
  pkg-config \
  build-essential \
  libmariadb-dev \
  libpython3-dev

WORKDIR "/build"

COPY ./requirements ./requirements/

RUN mkdir --parents /build/wheels/ \
    && pip wheel --wheel-dir /build/wheels/ -r /build/requirements/docker.lock

## Deployment image
FROM base AS run

COPY --from=build /build/wheels /wheels/

WORKDIR "/site"

RUN adduser --no-create-home --disabled-login --gecos x toolkit \
    && python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
    && rm -rf /wheels/

COPY --chown=toolkit:toolkit . /site/

RUN ln -s /site/containerconfig/tk_run.sh /usr/local/bin/tk_run \
     && ln -s /site/toolkit/docker_settings_starandshadow.py /site/toolkit/settings.py \
     && SECRET_KEY="X" /venv/bin/python3 /site/manage.py collectstatic --noinput --clear --settings=toolkit.docker_settings_starandshadow \
     \
     # Media upload directories — MUST list every upload_to path used by any
     # ImageField or FileField in the codebase. The container runs as a non-root
     # user (toolkit) and cannot mkdir new subdirectories at runtime if the parent
     # is root-owned. /site/media is listed FIRST so install -D creates it as
     # toolkit:toolkit; without that first entry, 'install -D' creates the parent
     # as root and uploads to any unlisted path fail with PermissionError.
     #
     # When you add a new ImageField with upload_to="foo/", add /site/media/foo
     # here and rebuild. The check_media_dirs management command (run by tk_run.sh
     # at every startup) will catch any missing paths loudly at boot time.
     && install -D --owner=toolkit --group=toolkit --directory /site/media \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/diary \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/documents \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/images \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/printedprogramme \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/printedprogramme_thumbnails \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/volunteers \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/loft-photos \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/area-photos \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/lost-and-found \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/exchange \
     && install -D --owner=toolkit --group=toolkit --directory /site/media/wagtail_uploads \
     && install -D --owner=toolkit --group=toolkit --directory /site/.seed_cache

USER toolkit:toolkit

VOLUME ["/site/media"]
VOLUME ["/log/"]

EXPOSE 8000
