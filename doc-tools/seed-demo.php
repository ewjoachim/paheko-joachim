<?php
/**
 * Demo fixture for the user-guide screenshots.
 *
 * Runs INSIDE the podman container (init.php bootstrap), on the current database.
 * Idempotent: purges the previous demo data then recreates it identically.
 *
 *   podman exec -i paheko-test php < doc-tools/seed-demo.php
 *
 * NB: run against a throwaway database (see regen-screenshots.sh, which backs up /
 * restores the working database around the call).
 */

namespace Paheko;

use Paheko\DB;
use Paheko\Users\Session;

require '/var/www/paheko/include/init.php';

$db = DB::getInstance();
$db->begin();

// --- 1. Module config --------------------------------------------------------
$module = 'suivi_cheques';
$mdt = 'module_data_' . $module;

$db->exec(sprintf('CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, key TEXT NULL, document TEXT NOT NULL);', $mdt));
$db->exec(sprintf('CREATE UNIQUE INDEX IF NOT EXISTS %1$s_key ON %1$s (key);', $mdt));

$put = function (string $key, array $doc) use ($db, $mdt) {
	$db->preparedQuery(sprintf('INSERT OR REPLACE INTO %s (key, document) VALUES (?, ?);', $mdt), $key, json_encode($doc));
};

// module config (waiting / receivable / bank accounts)
$db->update('modules', ['config' => json_encode([
	'waiting_account'    => '5112',
	'receivable_account' => '411',
	'bank_account'       => '512',
])], 'name = :n', ['n' => $module]);

// "cheque" payment method -> collection month mapping
$db->exec(sprintf('DELETE FROM %s WHERE json_extract(document, \'$.type\') = \'method_month_map\';', $mdt));
foreach ([1 => 7, 2 => 1, 3 => 12] as $mid => $month) {
	$put('mm-' . $mid, ['type' => 'method_month_map', 'method_id' => $mid, 'month' => $month]);
}

// --- 2. Purge (throwaway db): start from an empty caisse for clean captures
$db->exec(sprintf('DELETE FROM %s WHERE json_extract(document, \'$.type\') IN (\'cheque\', \'cheque_rempl\', \'deposit_batch\');', $mdt));
$db->exec('DELETE FROM plugin_pos_tabs_payments;');
$db->exec('DELETE FROM plugin_pos_tabs;');

// demo member (identified by their number)
$uid = $db->firstColumn("SELECT id FROM users WHERE numero = 'DEMO-CAMILLE'");

// --- 3. Demo member ----------------------------------------------------------
if (!$uid) {
	$db->preparedQuery("INSERT INTO users (id_category, numero, nom, is_parent, lettre_infos) VALUES (1, 'DEMO-CAMILLE', 'Camille Martin', 0, 0);");
	$uid = $db->lastInsertId();
}

// --- 4. Caisse session + tab -------------------------------------------------
$sid = $db->firstColumn('SELECT id FROM plugin_pos_sessions ORDER BY id LIMIT 1');
if (!$sid) {
	$db->exec("INSERT INTO plugin_pos_sessions (opened, closed) VALUES ('2026-07-01 10:00:00', '2026-07-01 12:00:00');");
	$sid = $db->lastInsertId();
}
$db->preparedQuery("INSERT INTO plugin_pos_tabs (session, name, user_id, opened, closed) VALUES (?, 'Camille Martin', ?, '2026-07-01 10:05:00', '2026-07-01 10:10:00');", $sid, $uid);
$tab = $db->lastInsertId();

// --- 5. Caisse cheques (method 1 = "Chèque juillet", account 5112) -----------
// Insert 9 cheques; force the collection month via the overlay to tell the
// story of a member's "10 monthly cheques".
$pay = function (string $ref, int $amount) use ($db, $tab) {
	$db->preparedQuery("INSERT INTO plugin_pos_tabs_payments (tab, method, date, amount, reference, account, type) VALUES (?, 1, '2026-07-01', ?, ?, '5112', 0);", $tab, $amount, $ref);
	return (int) $db->lastInsertId();
};

$p = [];
$p['0140'] = $pay('CHQ-0140', 4500);
$p['0141'] = $pay('CHQ-0141', 3000);
$p['0142'] = $pay('CHQ-0142', 4500);
$p['0143'] = $pay('CHQ-0143', 5000);
$p['0144'] = $pay('CHQ-0144', 4500);
$p['0145'] = $pay('CHQ-0145', 4500);
$p['0146'] = $pay('CHQ-0146', 4500);
$p['0147'] = $pay('CHQ-0147', 4500);
$p['0148'] = $pay('CHQ-0148', 4500);

// --- 6. Module overlays ------------------------------------------------------
// Planned months (July 2026 -> March 2027)
$months = [
	'0140' => '2026-07', '0141' => '2026-07', '0142' => '2026-07', '0143' => '2026-07',
	'0144' => '2026-08', '0145' => '2026-09', '0146' => '2026-10', '0147' => '2026-11', '0148' => '2026-12',
];
foreach ($months as $ref => $month) {
	$put('pay-' . $p[$ref], ['type' => 'cheque', 'payment_id' => $p[$ref], 'planned_month' => $month]);
}

// 0141: cancelled, replaced BY A CHEQUE (CHQ-0200) -> to record (cancellation)
$put('pay-' . $p['0141'], [
	'type' => 'cheque', 'payment_id' => $p['0141'], 'planned_month' => '2026-07',
	'cancelled' => 1, 'reason' => 'Chèque remplacé par un autre chèque',
]);
$put('rempl-demo-0200', [
	'type' => 'cheque_rempl', 'parent_key' => 'pay-' . $p['0141'], 'member_id' => (int) $uid,
	'cheque_number' => 'CHQ-0200', 'amount' => 3000,
	'planned_month' => '2026-09', 'received_date' => '2026-07-01', 'cancelled' => 0,
]);

// 0142: cancelled, partially replaced by card (20.00) -> 25.00 left as receivable 411
$put('pay-' . $p['0142'], [
	'type' => 'cheque', 'payment_id' => $p['0142'], 'planned_month' => '2026-07',
	'cancelled' => 1, 'reason' => 'Compte bancaire clôturé',
	'replacements' => [['method_id' => 7, 'account' => '512', 'amount' => 2000]],
]);

// 0143: frozen in a deposit slip (batch) -> to record (deposit)
$put('pay-' . $p['0143'], ['type' => 'cheque', 'payment_id' => $p['0143'], 'planned_month' => '2026-07', 'batch_id' => 'DEMO']);
$put('batch-DEMO', [
	'type' => 'deposit_batch', 'ref' => 'DEMO', 'date' => '2026-07-06', 'account' => '5112',
	'lines' => [['source_key' => 'pay-' . $p['0143'], 'cheque_ref' => 'CHQ-0143', 'member' => 'Camille Martin', 'amount' => 5000]],
	'total' => 5000,
]);

// --- 7. Deterministic admin password (throwaway db) --------------------------
// Lets the Playwright script log in without guessing credentials.
$admin = $db->first('SELECT id, email FROM users WHERE id_category IN (SELECT id FROM users_categories WHERE perm_config = 9) ORDER BY id LIMIT 1');
$hash = Session::getInstance()->hashPassword('demo-screenshots-2026');
$db->preparedQuery('UPDATE users SET password = ? WHERE id = ?;', $hash, $admin->id);

$db->commit();

printf("Demo seeded: member #%d (Camille Martin), tab #%d, 9 cheques, 1 cancellation+replacement, 1 cancellation+card, 1 frozen slip.\n", $uid, $tab);
printf("ADMIN_EMAIL=%s\n", $admin->email);
printf("ADMIN_PASSWORD=demo-screenshots-2026\n");
printf("CAMILLE_ID=%d\n", $uid);
printf("PAY_EDIT=%d\n", $p['0140']);
