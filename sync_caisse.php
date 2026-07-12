<?php
namespace Paheko;

use Paheko\Plugin\Caisse\POS;
use Paheko\Accounting\Years;

require '/var/www/paheko/include/init.php';

if (!defined('Paheko\\PLUGIN_ROOT')) {
	define('Paheko\\PLUGIN_ROOT', '/var/www/paheko/data/plugins/caisse');
}

$year = Years::get(1);
if (!$year) { fwrite(STDERR, "No year\n"); exit(1); }

$added = POS::syncAccounting(1, $year);
echo "Sessions synced this run: $added\n";
