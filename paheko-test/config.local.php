<?php
/**
 * Paheko config for the local test instance.
 * This file lives in paheko-joachim and is mounted into the container.
 */
namespace Paheko;

// Fixed (dev) key: avoids Paheko having to rewrite this mounted file.
const SECRET_KEY = 'devlocal_paheko_joachim_change_me_0123456789abcdef';

// Show technical error details (handy in dev).
const ENABLE_TECH_DETAILS = true;

// Site URL (needed in particular for the CLI bootstrap).
const WWW_URL = 'http://localhost:8080/';
const WWW_URI = '/';

// DATA_ROOT and DB_FILE keep their default values:
//   DATA_ROOT = ROOT . '/data'
//   DB_FILE   = DATA_ROOT . '/association.sqlite'
