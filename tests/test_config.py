# minifluxsearch - Search Miniflux v2 RSS entries by keyword
# Copyright (C) 2026 mplx <developer@mplx.eu>
#
# Licensed under the GNU Lesser General Public License v3.0 or later.
# See <https://www.gnu.org/licenses/lgpl-3.0> for details.

import pytest

from minifluxsearch.config import (
    GuiSettings,
    load_config,
    load_gui_settings,
    save_config,
    save_gui_settings,
)


# -- load_config ---------------------------------------------------------------

def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("MINIFLUX_URL", "https://env.example.com")
    monkeypatch.setenv("MINIFLUX_API_KEY", "env-key")
    cfg = load_config()
    assert cfg.base_url == "https://env.example.com"
    assert cfg.api_key == "env-key"


def test_load_config_env_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("MINIFLUX_URL", "https://env.example.com/")
    monkeypatch.setenv("MINIFLUX_API_KEY", "key")
    assert load_config().base_url == "https://env.example.com"


def test_load_config_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[miniflux]\nurl = "https://file.example.com"\napi_key = "file-key"\n')
    cfg = load_config(cfg_file)
    assert cfg.base_url == "https://file.example.com"
    assert cfg.api_key == "file-key"


def test_load_config_file_strips_trailing_slash(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[miniflux]\nurl = "https://file.example.com/"\napi_key = "k"\n')
    assert load_config(cfg_file).base_url == "https://file.example.com"


def test_load_config_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="credentials not found"):
        load_config(tmp_path / "nonexistent.toml")


def test_load_config_malformed_toml_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    bad = tmp_path / "config.toml"
    bad.write_text("this is not [ valid toml ===")
    with pytest.raises(RuntimeError, match="parse"):
        load_config(bad)


def test_load_config_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    bad = tmp_path / "config.toml"
    bad.write_text('[miniflux]\nurl = "https://example.com"\n')  # no api_key
    with pytest.raises(RuntimeError, match="api_key"):
        load_config(bad)


# -- save_config ---------------------------------------------------------------

def test_save_config_creates_file(tmp_path):
    path = tmp_path / "sub" / "config.toml"
    save_config("https://example.com", "my-key", path)
    assert path.exists()
    content = path.read_text()
    assert 'url = "https://example.com"' in content
    assert 'api_key = "my-key"' in content


def test_save_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    path = tmp_path / "config.toml"
    save_config("https://example.com", "key123", path)
    cfg = load_config(path)
    assert cfg.base_url == "https://example.com"
    assert cfg.api_key == "key123"


def test_save_config_preserves_gui_section(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[miniflux]\nurl = "https://old.example.com"\napi_key = "old"\n\n[gui]\nstatus = "unread"\n')
    save_config("https://new.example.com", "new-key", path)
    content = path.read_text()
    assert "https://new.example.com" in content
    assert "new-key" in content
    assert 'status = "unread"' in content


def test_save_config_escapes_special_chars(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    path = tmp_path / "config.toml"
    save_config('https://example.com', 'key"with"quotes', path)
    cfg = load_config(path)
    assert cfg.api_key == 'key"with"quotes'


# -- GuiSettings ---------------------------------------------------------------

def test_load_gui_settings_defaults_when_no_file(tmp_path):
    s = load_gui_settings(tmp_path / "nonexistent.toml")
    assert s.status == "all"
    assert s.starred is False
    assert s.fetch_limit == 1000
    assert s.max_results == ""
    assert s.any_keyword is False
    assert s.after_enabled is False
    assert s.before_enabled is False
    assert s.keyword_history == []
    assert s.window_geometry == ""


def test_save_and_load_gui_settings_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    s = GuiSettings(
        status="unread",
        starred=True,
        fetch_limit=500,
        max_results="20",
        any_keyword=True,
        after_enabled=True,
        after_date="2026-04-01",
        before_enabled=True,
        before_date="2026-04-30",
        keyword_history=["einhell bosch", "python"],
        window_geometry="1200x700+80+120",
    )
    save_gui_settings(s, path)
    loaded = load_gui_settings(path)
    assert loaded.status == "unread"
    assert loaded.starred is True
    assert loaded.fetch_limit == 500
    assert loaded.max_results == "20"
    assert loaded.any_keyword is True
    assert loaded.after_enabled is True
    assert loaded.after_date == "2026-04-01"
    assert loaded.before_enabled is True
    assert loaded.before_date == "2026-04-30"
    assert loaded.keyword_history == ["einhell bosch", "python"]
    assert loaded.window_geometry == "1200x700+80+120"


def test_save_gui_settings_preserves_miniflux_section(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIFLUX_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)
    path = tmp_path / "config.toml"
    save_config("https://example.com", "my-key", path)
    save_gui_settings(GuiSettings(status="read"), path)
    cfg = load_config(path)
    assert cfg.base_url == "https://example.com"
    assert cfg.api_key == "my-key"
    s = load_gui_settings(path)
    assert s.status == "read"


def test_keyword_history_capped_at_10(tmp_path):
    path = tmp_path / "config.toml"
    s = GuiSettings(keyword_history=[str(i) for i in range(20)])
    save_gui_settings(s, path)
    loaded = load_gui_settings(path)
    assert len(loaded.keyword_history) == 10