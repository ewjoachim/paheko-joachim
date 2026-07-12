# Self-contained Paheko runtime image (core + bundled plugins + this repo's
# modules and test config). Built on the multi-arch php:8.5-apache base — the
# official Paheko image is amd64-only and SIGSEGVs under QEMU on arm64.
#
# The Paheko app tree is lifted wholesale from the official image via
# `COPY --from` (pinned to a release tag, kept current by Renovate's native
# dockerfile manager). Those are arch-agnostic PHP files (KD2 already vendored,
# www/.htaccess already generated, caisse and the other plugins already bundled),
# so copying from the amd64 image onto the arm64 base is clean — and the final
# image runs natively on both arches. No make deps / fossil.kd2.org / ADD-git.
FROM php:8.5-apache@sha256:ede24dfd13fe79fb8ea0d0bac0ac45827a9a540d2a16e45c047f9afaf69c3eaf

RUN apt-get update && apt-get install -y --no-install-recommends \
      libicu-dev zlib1g-dev libpng-dev libzip-dev libfreetype6-dev libjpeg62-turbo-dev libwebp-dev \
 && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
 && docker-php-ext-install -j"$(nproc)" gd intl zip calendar \
 && docker-php-ext-enable sodium \
 && rm -rf /var/lib/apt/lists/*

# Paheko core, KD2, www/.htaccess and the bundled plugins (incl. caisse).
COPY --from=docker.io/paheko/paheko:1.3.21@sha256:e9011f923a40161fd4748c90bf597a4a9c2d5562e5dabe4de566b12846311dae /var/www/paheko /var/www/paheko
WORKDIR /var/www/paheko

# This repo's modules and the test config. Locally these paths are bind-mounted
# over (live editing); in CI the baked copies are used as-is.
COPY modules/ /var/www/paheko/modules/
COPY config.local.php /var/www/paheko/config.local.php

RUN chown -R www-data: /var/www/paheko

ENV APACHE_DOCUMENT_ROOT=/var/www/paheko/www
# Docroot = www/. The image's bundled www/.htaccess has no routing rule, so add
# the front-controller fallback ourselves: any non-existent URL (e.g. the
# module pages /m/<name>/…) is dispatched to www/_route.php. ErrorDocument
# covers URLs ending in .php, which FallbackResource skips.
RUN a2enmod rewrite \
 && sed -ri 's!/var/www/html!/var/www/paheko/www!g' /etc/apache2/sites-available/*.conf \
 && printf '<Directory /var/www/paheko/www/>\n\tAllowOverride All\n\tRequire all granted\n\tFallbackResource /_route.php\n\tErrorDocument 404 /_route.php\n</Directory>\n' \
      > /etc/apache2/conf-available/paheko.conf \
 && a2enconf paheko
