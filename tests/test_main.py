"""Unit tests for main.py CLI argument parsing and transport dispatch."""

from unittest.mock import MagicMock, patch

import pytest

import main


@pytest.fixture
def mock_mcp_run():
    with patch.object(main, "mcp") as mock_mcp:
        yield mock_mcp.run


@pytest.fixture
def mock_set_transport_mode():
    with patch.object(main, "set_transport_mode") as mock_fn:
        yield mock_fn


def test_default_transport_is_stdio(mock_mcp_run, mock_set_transport_mode):
    with patch("sys.argv", ["main.py"]):
        main.main()

    mock_set_transport_mode.assert_called_once_with("stdio")
    mock_mcp_run.assert_called_once_with(transport="stdio")


def test_transport_http_uses_settings_defaults(mock_mcp_run, mock_set_transport_mode):
    mock_settings = MagicMock(mcp_host="127.0.0.1", mcp_port=8000)
    with patch("sys.argv", ["main.py", "--transport", "http"]), patch.object(
        main, "load_settings", return_value=mock_settings
    ):
        main.main()

    mock_set_transport_mode.assert_called_once_with("http")
    mock_mcp_run.assert_called_once_with(transport="http", host="127.0.0.1", port=8000)


def test_transport_http_host_port_override_settings(mock_mcp_run, mock_set_transport_mode):
    mock_settings = MagicMock(mcp_host="127.0.0.1", mcp_port=8000)
    with patch(
        "sys.argv",
        ["main.py", "--transport", "http", "--host", "0.0.0.0", "--port", "9999"],
    ), patch.object(main, "load_settings", return_value=mock_settings):
        main.main()

    mock_mcp_run.assert_called_once_with(transport="http", host="0.0.0.0", port=9999)


def test_invalid_transport_raises_system_exit(mock_mcp_run, mock_set_transport_mode):
    with patch("sys.argv", ["main.py", "--transport", "sse"]), pytest.raises(SystemExit):
        main.main()
