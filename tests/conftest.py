"""Every git the suite starts reads an empty global configuration and no
system one.

A developer's own settings otherwise reach the repositories the tests
create. An `init.templateDir` that installs a pre-commit hook made
`install-hooks` find a foreign hook in a fresh repository and made the
commits the audit tests rely on fail. `GIT_CONFIG_GLOBAL` needs git 2.32.

Kept 3.6.8-clean like the rest of tests/.
"""

import os
import tempfile
from typing import Iterator  # noqa: F401 - resolves the type comment below

import pytest

_ISOLATED = {"GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True, scope="session")
def _no_user_git_config():
    # type: () -> Iterator[None]
    saved = {k: os.environ.get(k) for k in list(_ISOLATED) + ["GIT_CONFIG_GLOBAL"]}
    with tempfile.TemporaryDirectory(prefix="git-hygiene-config-") as tmp:
        empty = os.path.join(tmp, "gitconfig")
        open(empty, "w").close()
        os.environ.update(_ISOLATED)
        os.environ["GIT_CONFIG_GLOBAL"] = empty
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
