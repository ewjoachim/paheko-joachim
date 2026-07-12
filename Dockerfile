# Paheko runtime image built arm64-native (the official image is amd64 -> SIGSEGV under QEMU).
# Multi-arch base php:8.5-apache, extensions replicated from the official image.
# The Paheko core comes from YOUR local source, passed via the "paheko_src" build context.
FROM php:8.5-apache

RUN apt-get update && apt-get install -y --no-install-recommends \
      libicu-dev zlib1g-dev libpng-dev libzip-dev libfreetype6-dev libjpeg62-turbo-dev libwebp-dev \
      make wget unzip ca-certificates \
 && docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
 && docker-php-ext-install -j"$(nproc)" gd intl zip calendar \
 && docker-php-ext-enable sodium \
 && rm -rf /var/lib/apt/lists/*

# Core = your local source (build context paheko_src = ../paheko-fossil/src)
COPY --from=paheko_src . /var/www/paheko
WORKDIR /var/www/paheko

# Vendor KD2 (make deps: wget + unzip from fossil.kd2.org)
# and generate the www/.htaccess for a docroot = www/ (make htaccess),
# NOT the .htaccess.www meant for a subdirectory install (which loops).
RUN make deps \
 && make htaccess \
 && chown -R www-data: /var/www/paheko

ENV APACHE_DOCUMENT_ROOT=/var/www/paheko/www
RUN a2enmod rewrite \
 && sed -ri 's!/var/www/html!/var/www/paheko/www!g' /etc/apache2/sites-available/*.conf \
 && printf '<Directory /var/www/paheko/www/>\n\tAllowOverride All\n\tRequire all granted\n</Directory>\n' \
      > /etc/apache2/conf-available/paheko.conf \
 && a2enconf paheko
