import pytest


@pytest.mark.unit
def test_delete_files_removes_existing(tmp_path):
    from app.utils.files import delete_files

    a = tmp_path / "a.mp4"
    b = tmp_path / "b.png"
    a.write_bytes(b"x")
    b.write_bytes(b"y")

    delete_files([str(a), str(b)])

    assert not a.exists()
    assert not b.exists()


@pytest.mark.unit
def test_delete_files_ignores_missing(tmp_path):
    from app.utils.files import delete_files

    # не бросает на отсутствующем пути
    delete_files([str(tmp_path / "nope.txt")])


@pytest.mark.unit
def test_delete_files_mixed_existing_and_missing(tmp_path):
    from app.utils.files import delete_files

    a = tmp_path / "a.mp4"
    a.write_bytes(b"x")

    delete_files([str(a), str(tmp_path / "ghost.png")])

    assert not a.exists()


@pytest.mark.unit
def test_delete_files_empty_list_is_noop(tmp_path):
    from app.utils.files import delete_files

    delete_files([])  # без ошибок
