<?php
/**
 * Headless install + enable, for a FRESH throwaway instance (CI / local tests).
 *
 * Runs INSIDE the container, on an empty data dir (no DB yet). Installs Paheko,
 * enables the caisse plugin and the suivi_cheques module, so that seed-demo.php
 * can then populate demo data. Idempotent: skips install if the DB already exists.
 *
 *   podman exec -i <container> php < doc-tools/bootstrap-instance.php
 */

namespace Paheko;

use Paheko\Plugins;
use Paheko\UserTemplate\Modules;
use Paheko\Accounting\Charts;
use Paheko\Entities\Accounting\Year;

// Before install, init.php would otherwise redirect to install.php (prints
// "Please visit …/install.php" under CLI and exits). Same escape hatch as
// www/admin/install.php.
const SKIP_STARTUP_CHECK = true;

require '/var/www/paheko/include/init.php';

if (!file_exists(DB_FILE)) {
	Install::install('FR', 'Association de démonstration', 'Administration', 'admin@example.org', 'demo-screenshots-2026');
	echo "Installed.\n";
}
else {
	echo "Already installed, skipping.\n";
}

// Caisse plugin: run its schema. Plugins::exists() only tests the on-disk dir
// (always true — caisse is bundled), so check Plugins::get() (the DB row) to
// know whether it is actually installed.
if (!Plugins::get('caisse')) {
	Plugins::getInstallable('caisse')->enable();
	echo "Caisse enabled.\n";
}
else {
	echo "Caisse already enabled.\n";
}

// Accounting: install a chart and open a year. Install::install() creates
// neither, but the module posts entries with id_year="current", which needs an
// open year (and the 512 / 5112 / 411 accounts the module defaults to live in
// the French association chart).
$db = DB::getInstance();
$chart_id = $db->firstColumn('SELECT id FROM acc_charts LIMIT 1');
if (!$chart_id) {
	$chart_id = Charts::installCountryDefault('FR')->id;
	echo "Chart installed.\n";
}
if (!$db->firstColumn('SELECT id FROM acc_years LIMIT 1')) {
	$year = new Year;
	$year->id_chart = $chart_id;
	$year->label = 'Exercice test';
	// Current calendar year, so "now" always falls inside it whenever the tests
	// run (comptabilisation dates the entry at today).
	$year->start_date = new \DateTime(date('Y') . '-01-01');
	$year->end_date = new \DateTime(date('Y') . '-12-31');
	$year->save();
	echo "Year created.\n";
}

// Modules: register the on-disk dirs as DB rows, then enable suivi_cheques.
Modules::refresh();
$module = Modules::get('suivi_cheques');
if ($module) {
	$module->set('enabled', true);
	$module->save();
	echo "Module suivi_cheques enabled.\n";
}
else {
	echo "Module suivi_cheques NOT FOUND.\n";
}
