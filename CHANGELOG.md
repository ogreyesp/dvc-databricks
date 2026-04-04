# CHANGELOG

<!-- version list -->

## v1.2.1 (2026-04-04)

### Bug Fixes

- Use venv instead of --system for docs dependencies
  ([`6f040b7`](https://github.com/ogreyesp/dvc-databricks/commit/6f040b7e1d89d10b8e514a2961175e683c189687))


## v1.2.0 (2026-04-04)

### Features

- Require Python >=3.11, mark stable, add 3.14 classifier, test 3.11-3.13
  ([`b9d74b8`](https://github.com/ogreyesp/dvc-databricks/commit/b9d74b8940053cfc60bbbf4129c216a0685dbeb4))


## v1.1.3 (2026-04-04)

### Bug Fixes

- Read version from pyproject.toml directly in docs
  ([`836a96b`](https://github.com/ogreyesp/dvc-databricks/commit/836a96bc79b0d134f5711eb798737f446cb6a538))


## v1.1.2 (2026-04-04)

### Bug Fixes

- Build docs after release tag, not on push to main
  ([`6c54f3f`](https://github.com/ogreyesp/dvc-databricks/commit/6c54f3f4aab5b75c13c3c8377e7c86876e5f141d))


## v1.1.1 (2026-04-04)

### Bug Fixes

- Display full package version in docs
  ([`f7feed4`](https://github.com/ogreyesp/dvc-databricks/commit/f7feed4df24faae62d0598e1e3e7d94acadeb339))


## v1.1.0 (2026-04-04)

### Bug Fixes

- Correct uvx invocation for python-semantic-release
  ([`c788ba6`](https://github.com/ogreyesp/dvc-databricks/commit/c788ba6f1e9e0aeaefd7cb4fb6f26c0b7d5574bd))

### Features

- Add tests, sphinx docs, pylint, Makefile, uv support
  ([`7a11f0d`](https://github.com/ogreyesp/dvc-databricks/commit/7a11f0d67e049d108316dad293cebeac07ee75a5))


## v1.0.4 (2026-04-03)

### Bug Fixes

- Convert Databricks NotFound error to FileNotFoundError in _open
  ([`64586c8`](https://github.com/ogreyesp/dvc-databricks/commit/64586c87566edc8861ec4a4fefd924e6b62079d4))


## v1.0.3 (2026-04-03)

### Bug Fixes

- Remove broken output command from release workflow
  ([`d91f6a1`](https://github.com/ogreyesp/dvc-databricks/commit/d91f6a1b07747430091c69689104cc27c9ddea56))


## v1.0.2 (2026-04-03)

### Bug Fixes

- Separate CI from release workflow and use twine for PyPI upload
  ([`3f8783d`](https://github.com/ogreyesp/dvc-databricks/commit/3f8783dc260a6f5d965bdde48d8ede4bd83718d3))


## v1.0.1 (2026-04-03)

### Bug Fixes

- Include .pth file in wheel root via force-include
  ([`43637ea`](https://github.com/ogreyesp/dvc-databricks/commit/43637ea1da0903c797e18a2e7f3ebd18b7fdb66d))


## v1.0.0 (2026-04-03)

- Initial Release
