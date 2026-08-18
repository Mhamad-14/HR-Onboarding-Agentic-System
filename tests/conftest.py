from pathlib import Path

import pytest

from onboardai.config import Settings


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def test_settings(tmp_path: Path, project_root: Path) -> Settings:
    return Settings(
        project_root=project_root,
        data_dir=project_root / "data",
        runtime_dir=tmp_path,
        checkpoint_path=tmp_path / "checkpoints.db",
        operations_path=tmp_path / "operations.db",
        drafts_dir=tmp_path / "drafts",
        embedding_backend="hash",
        embedding_model="hash-test-double",
        simulate_it_failure=True,
    )
