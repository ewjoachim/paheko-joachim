# Suivi des chèques

Module Paheko pour une école de musique (ou toute asso encaissant beaucoup de chèques
en caisse). Il suit chaque chèque saisi via l'extension **Caisse**, planifie son mois
d'encaissement, gère annulations et remplacements, produit les bordereaux de remise, et
prépare pour la comptabilité des écritures « prêtes à valider ».

Guide utilisateur illustré : voir `paheko-joachim/doc/guide.html`.
Conception détaillée : `paheko-joachim/CONCEPTION.md`.

## Principe

- **Le module est la source de vérité opérationnelle**, la comptabilité un reflet aval
  (juste « à terme »). L'accueil ne manipule que les données du module. Cela vaut aussi
  pour les **créances** : une dette naît de l'annulation d'un chèque et s'éteint par un
  encaissement, deux faits opérationnels. La lire dans les comptes de tiers la rendrait
  invisible tant que personne n'a comptabilisé, et son extinction dépendrait du champ
  « membres associés », **facultatif** dans le formulaire d'écriture du cœur.
- **Un document par écriture comptable.** C'est ce qui décide si une chose mérite son
  propre type : les remplacements non-chèque vivent *dans* le chèque (leurs lignes sont
  dans l'écriture du parent), alors qu'un règlement de créance a son écriture propre,
  donc son document, son `*_txn_id` et sa ligne dans « à comptabiliser ».
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
annuler, remplacer, préparer un bordereau) exigent `membres = écriture` ; la
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
- `auto_record_cancellations` / `auto_record_settlements` / `auto_record_deposits` —
  comptabilisation automatique (défaut : désactivée, les écritures attendent dans
  « à comptabiliser »).
- correspondance moyen de paiement « chèque » → mois d'encaissement.

## Fichiers

| Fichier | Rôle |
|---|---|
| `module.ini` | métadonnées + restriction d'accès (`users` / lecture) |
| `config.html` | configuration (comptes + mapping mois) |
| `index.html` / `upcoming.html` | chèques du mois / à venir |
| `_list.html` | **partial pivot** : tableau des chèques, réutilisé partout |
| `edit.html` / `edit_replacement.html` | annuler / remplacer (données module) |
| `deposit.html` | préparer un bordereau + geler le lot + bordereau imprimable |
| `batches.html` | index des bordereaux générés + état de leur comptabilisation |
| `debtors.html` | impayés : ardoises (caisse) et créances (module) par membre |
| `settle.html` | encaisser une créance (montant, date, moyen) |
| `to_record.html` | file « à comptabiliser » (un clic = une écriture) |
| `_cancellation_shape.html` | forme d'une annulation : lignes, part couverte, **reste dû** — partagé par l'écriture et la créance, pour qu'ils ne divergent pas |
| `_creance_sync.html` | crée / ajuste / supprime la créance à l'enregistrement d'une annulation |
| `_record_cancellation.html` / `_record_settlement.html` / `_record_deposit.html` | construction + envoi des écritures `{{:api}}`, partagés par la file et le mode automatique |
| `_record_precheck.html` | pré-validation du mode automatique (exercice, comptes) |
| `_resolve_month.html` | mois d'encaissement (1-12) → mois absolu `YYYY-MM` |
| `snippets/user_details.html` | encart paiements sur la fiche membre |
| `_member_payments.html` | journal des paiements d'un membre (caisse, chèques, ardoise, créances) |
| `*.schema.json` | schémas de validation des documents `module_data` |

## Documents (`module_data_suivi_cheques`)

| Type | Clé | Rôle |
|---|---|---|
| `cheque` | `pay-<payment_id>` | **overlay** d'un paiement de caisse : uniquement ce que la caisse ignore (mois, annulation, remplacements, liens compta, lot). Montant, numéro et date restent côté caisse |
| `cheque_rempl` | uuid ou `chq-<clé du règlement>` | chèque que le module possède entièrement, jamais passé en caisse : reçu en remplacement d'un chèque annulé (`parent_key`) ou en règlement d'une créance (`reglement_key`) |
| `creance` | `creance-<origin_key>` | dette née de l'annulation d'un chèque. Clé dérivée de l'origine, donc la création est **idempotente** |
| `reglement` | `regl-<creance_key>-<horodatage>` | argent encaissé sur une créance ; plusieurs pour un règlement partiel |
| `deposit_batch` | `batch-<ref>` | bordereau de remise figé |
| `method_month_map` | `method-<id>` | configuration : moyen de paiement → mois |

Le reste dû d'une créance n'est **pas stocké** : c'est `creance.amount` moins la somme
des `reglement` qui la visent. Rien à maintenir en cohérence.

## Remplacement en cascade (chaînes A→B→C)

Un chèque de caisse **comme** un chèque de remplacement peut être remplacé (par un
autre chèque et/ou en CB/espèces), à toute profondeur. Chaque chèque de remplacement
pointe vers son parent via `parent_key` (`pay-<id>` pour un chèque de caisse, ou la clé
d'un autre `cheque_rempl`) et hérite du `member_id`. L'écriture d'annulation raisonne
« par niveau » : elle crédite le chèque annulé sur le compte d'attente, débite ses
enfants **directs** (chacun avec son n° en référence), et met le reste non couvert en
créance du membre. Annuler B qui a un enfant C se traite comme annuler A qui a B.

Un enfant **annulé** compte quand même comme couvrant son parent : le chèque a bien été
remis, et son propre rejet est l'affaire de sa propre écriture, qui recrédite le compte
d'attente et pose sa créance. L'exclure ferait compter la même somme deux fois (une
créance chez le parent *et* une chez l'enfant) et laisserait le crédit du parent sans le
débit que l'enfant contrepasse. Un enfant **supprimé** (ligne vidée), lui, disparaît
vraiment : supprimer n'est pas annuler.

## Hors périmètre (v1)

- Rejet bancaire d'un chèque **après** dépôt (à traiter à la main en comptabilité).
- Passer une créance **en perte** (se fait en comptabilité ; le module ne connaît que
  l'encaissement, et la page Impayés signalera alors l'écart).
