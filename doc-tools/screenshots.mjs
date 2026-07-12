// Captures the screenshots for the suivi_cheques module user guide.
// Run by regen-screenshots.sh (which seeds a throwaway demo database first).
//
// Expected environment variables:
//   BASE_URL (default http://localhost:8080)
//   ADMIN_EMAIL, ADMIN_PASSWORD, CAMILLE_ID, PAY_EDIT  (provided by the seed)
//
// Output: doc/suivi_cheques/screenshots/*.png

import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync } from 'node:fs';

const BASE = process.env.BASE_URL || 'http://localhost:8080';
const EMAIL = process.env.ADMIN_EMAIL || 'joachim@jablon.fr';
const PASSWORD = process.env.ADMIN_PASSWORD || 'demo-screenshots-2026';
const CAMILLE = process.env.CAMILLE_ID || '';
const PAY_EDIT = process.env.PAY_EDIT || '';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'doc', 'suivi_cheques', 'screenshots');
mkdirSync(OUT, { recursive: true });

const M = `${BASE}/m/suivi_cheques`;

// Each entry: [file, url, options]
//   full   : capture the full page (default true)
//   waitFor: selector to wait for before capturing
const SHOTS = [
	['01-cheques-du-mois.png', `${M}/`, { waitFor: 'table.list' }],
	['02-a-venir.png', `${M}/upcoming.html`, { waitFor: 'table.list' }],
	['03-annuler-remplacer.png', `${M}/edit.html?payment=${PAY_EDIT}`, { waitFor: 'form' }],
	['04-preparer-bordereau.png', `${M}/deposit.html?month=2026-07`, { waitFor: 'table.list' }],
	['05-bordereau.png', `${M}/deposit.html?batch=DEMO`, { waitFor: 'table.list' }],
	['06-a-comptabiliser.png', `${M}/to_record.html`, { waitFor: 'table.list' }],
	['07-fiche-membre.png', `${BASE}/admin/users/details.php?id=${CAMILLE}`, { waitFor: 'table.list' }],
	['08-configuration.png', `${M}/config.html`, { waitFor: 'form' }],
];

const browser = await chromium.launch();
const context = await browser.newContext({
	viewport: { width: 1200, height: 900 },
	deviceScaleFactor: 2, // sharp (retina) captures
	colorScheme: 'light',
	locale: 'fr-FR',
});

// Paheko enables View Transitions (`@view-transition { navigation: auto }`),
// which FREEZES headless screenshots (the compositor stays blocked after
// navigation). We strip that rule on the fly — the rest of the CSS is intact.
await context.route(/\.css(\?|$)/, async (route) => {
	const resp = await route.fetch();
	const css = (await resp.text()).replace(/@view-transition\s*\{[^}]*\}/gi, '');
	await route.fulfill({ response: resp, body: css });
});

const page = await context.newPage();
page.setDefaultTimeout(15000);

// --- Login -------------------------------------------------------------------
await page.goto(`${BASE}/admin/login.php`, { waitUntil: 'domcontentloaded' });
await page.fill('input[name="id"]', EMAIL);
await page.fill('input[name="password"]', PASSWORD);
await page.click('button[type="submit"], input[type="submit"]');
await page.waitForLoadState('domcontentloaded');

if (await page.locator('input[name="password"]').count()) {
	console.error('Login FAILED — check ADMIN_EMAIL / ADMIN_PASSWORD.');
	await browser.close();
	process.exit(1);
}
console.log('Logged in.');

// --- Captures ----------------------------------------------------------------
for (const [file, url, opts = {}] of SHOTS) {
	try {
		await page.goto(url, { waitUntil: 'domcontentloaded' });
		if (opts.waitFor) {
			await page.waitForSelector(opts.waitFor, { timeout: 5000 }).catch(() => {});
		}
		await page.screenshot({ path: join(OUT, file), fullPage: opts.full !== false });
		console.log(`✓ ${file}`);
	}
	catch (e) {
		console.error(`✗ ${file} : ${e.message}`);
	}
}

await browser.close();
console.log(`\nScreenshots written to ${OUT}`);
