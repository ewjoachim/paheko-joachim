# Suivi des chèques

Module Paheko pour une école de musique (ou toute asso encaissant beaucoup de chèques
en caisse). Il suit chaque chèque saisi via l'extension **Caisse**, planifie son mois
d'encaissement, gère les annulations et ce qu'elles laissent dû, produit les bordereaux de remise, et
prépare pour la comptabilité des écritures « prêtes à valider ».

Guide utilisateur illustré : `doc/suivi_cheques/` (une page par tâche, `index.html` pour commencer).

## Principe

- **Le module est la source de vérité opérationnelle**, la comptabilité un reflet aval
  (juste « à terme »). L'accueil ne manipule que les données du module — y compris les
  créances (pourquoi : en tête de `_creance_sync.html`).
- **Un fait, un document, une écriture.** Annuler un chèque ouvre une créance du
  montant plein ; ce que le membre rend ensuite est un *règlement*, jamais une
  soustraction sur l'annulation. Chacun a son document, son `*_txn_id` et sa ligne
  dans « à comptabiliser ». Un chèque rendu en règlement est un chèque suivi comme un
  autre : s'il rejette à son tour, il ouvre sa propre créance — l'argent manque une
  fois, à un endroit.
- **La dette est celle du membre, pas celle d'un chèque.** Une créance par chèque
  revenu, parce que c'est le fait qui s'est produit ; mais on ne rembourse pas chèque
  par chèque, donc un règlement porte l'identifiant du membre et rien d'autre
  (`_member_debt.html`).
- **La comptabilité** poste les écritures en un clic, via la fonction Brindille `{{:api}}`.
  Le module retient l'`id` de chaque écriture créée (lien robuste, insensible au
  renommage : on ne relit la comptabilité que pour vérifier l'existence de nos `id`).
- **Comptabilisation automatique** (optionnelle, trois cases en configuration) : le module
  passe l'écriture lui-même au moment de l'action opérationnelle, sans exiger de droit
  comptable de l'opérateur — comme le réglage équivalent de la caisse, c'est la case
  cochée par l'admin qui vaut autorisation. Si l'écriture est refusée, l'action reste
  enregistrée et l'élément reste dans « à comptabiliser » (voir `_record_precheck.html`).

## Deux acteurs, deux droits (section *Membres* / *Comptabilité*)

| | Accueil / caisse | Comptabilité |
|---|---|---|
| Membres | écriture | lecture |
| Comptabilité | lecture | écriture |

Le module s'ouvre dès `membres = lecture`. Les actions opérationnelles (planifier,
annuler, préparer un bordereau) exigent `membres = écriture` ; la
comptabilisation (`{{:api}}`) exige `comptabilité = écriture`. La configuration est
réservée à `config = admin`.

## Pré-requis

- Extension **Caisse** active, avec des moyens de paiement « chèque » (idéalement datés :
  « Chèque janvier », « Chèque février »…).
- Un exercice comptable ouvert couvrant la date du jour, pour les écritures. Il ne joue
  aucun rôle dans la planification : l'année d'encaissement d'un chèque se déduit de sa
  date de réception (cf. `_resolve_month.html`).
- Désactiver le module natif **`cheque_deposit`** : ce module produit ses propres
  bordereaux et écritures de dépôt.

## Configuration (`config.html`, admin)

- `waiting_account` — compte d'attente des chèques (défaut `5112`).
- `receivable_account` — compte de créance des membres pour le non-couvert d'une
  annulation (défaut `411`).
- `bank_account` — compte bancaire des remises (défaut `512`).
- `gesture_account` / `bad_debt_account` — comptes débités par un abandon de dette,
  selon sa raison : geste accordé (défaut `709`) ou impayé (défaut `654`).
  `auto_record_settlements` couvre aussi les abandons et les remboursements.
- `auto_record_cancellations` / `auto_record_settlements` / `auto_record_deposits` —
  comptabilisation automatique (défaut : désactivée, les écritures attendent dans
  « à comptabiliser »).
- correspondance moyen de paiement « chèque » → mois d'encaissement.

## Documents (`module_data_suivi_cheques`)

| Type | Clé | Rôle |
|---|---|---|
| `cheque` | `pay-<payment_id>` | **overlay** d'un paiement de caisse : uniquement ce que la caisse ignore (mois, annulation, liens compta, lot). Montant et date restent côté caisse ; le numéro aussi, sauf correction (`cheque_number`) |
| `cheque_rempl` | `chq-<clé du règlement>` | chèque reçu en règlement d'une créance (`reglement_key`), jamais passé en caisse : le module en possède tout |
| `creance` | `creance-<origin_key>` | dette née de l'annulation d'un chèque. Clé dérivée de l'origine, donc la création est **idempotente** |
| `reglement` | `regl-<id du membre>-<horodatage>` | argent versé par un membre sur ce qu'il doit ; plusieurs documents pour un règlement en plusieurs fois |
| `abandon` | `aband-<id du membre>-<horodatage>` | part de ce que doit un membre à laquelle le bureau renonce (geste accordé ou impayé) ; aucun argent ne bouge |
| `remboursement` | `rmb-<id du membre>-<horodatage>` | argent rendu à un membre, saisi une fois parti ; son écriture débite `gesture_account` et crédite le compte d'où l'argent est sorti |
| `deposit_batch` | `batch-<ref>` | bordereau de remise figé |
| `method_month_map` | `method-<id>` | configuration : moyen de paiement → mois |

Ce qu'un membre doit n'est **pas stocké** : c'est la somme de ses `creance` moins celle
de ses `reglement` et `abandon`. Rien à répartir entre les chèques revenus, donc rien à maintenir en
cohérence quand une créance naît ou disparaît.

## Hors périmètre (v1)

- Rejet bancaire d'un chèque **après** dépôt (à traiter à la main en comptabilité).
