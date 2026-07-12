# paheko-joachim

Tooling and documentation around my [Paheko](https://paheko.cloud/) work (modules,
mostly for a music school). The module code lives in the sibling `paheko-modules/`
repository; this repo gathers the **test environment**, the **packaging** and the
**documentation**.

## Contents

| Folder | Role |
|---|---|
| [`paheko-test/`](paheko-test/) | Docker/podman stack for a local Paheko instance (arm64), to develop and test modules/plugins outside of Cloud. |
| [`build.sh`](build.sh) | Assembles a module's `.zip` archive in the format expected by Paheko Cloud (upload via the Modules admin). |
| [`doc/`](doc/) | Documentation site published on GitHub Pages: one folder per module (e.g. `doc/suivi_cheques/`). |
| [`doc-tools/`](doc-tools/) | Tooling that generates the doc screenshots (Playwright + a throwaway demo fixture). Kept separate from the published site. |

## Test instance

```sh
cd paheko-test
./run.sh          # build image + start + bootstrap (deps, caisse, modules)
```

Served on http://localhost:8080/. The Paheko core is mounted from a local checkout;
`paheko-modules/` and `paheko-plugins/` are bind-mounted live (hot editing). Details and
gotchas are in the comments of `docker-compose.yml` / `run.sh`.

## Packaging a module for Paheko Cloud

```sh
./build.sh suivi_cheques      # -> suivi_cheques-paheko-cloud.zip
```

Then upload the archive via the *Modules* admin of the Cloud instance.

## Documentation

The site lives in [`doc/`](doc/) and is deployed automatically to GitHub Pages on every
push to `main` (workflow [`.github/workflows/deploy-doc.yml`](.github/workflows/deploy-doc.yml)).

To regenerate a guide's screenshots (requires the test instance running):

```sh
cd doc-tools
npm install
./regen-screenshots.sh        # backs up the db, seeds a demo, captures, restores
```
