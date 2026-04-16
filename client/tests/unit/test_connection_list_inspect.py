import unittest
from unittest.mock import Mock, patch, call
import json

from click.testing import CliRunner
from gefyra.cli.connections import list_connections, inspect_connection


class TestListConnections(unittest.TestCase):
    """Tests for list_connections function"""

    def setUp(self):
        self.runner = CliRunner()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.list_connections")
    def test_list_connections_text_output_with_data(self, mock_api_list, mock_console):
        """Test list_connections with text output and connections available"""
        # Setup mock connection objects
        conn1 = Mock()
        conn1.list_values = ["conn1", "1.0.0", "2026-04-01", "active"]
        conn2 = Mock()
        conn2.list_values = ["conn2", "1.0.0", "2026-04-02", "waiting"]

        mock_api_list.return_value = [conn1, conn2]

        # Execute using CliRunner
        result = self.runner.invoke(list_connections, ["--output", "text"])

        # Verify
        mock_api_list.assert_called_once()
        self.assertEqual(result.exit_code, 0)
        self.assertIn("conn1", result.output)
        self.assertIn("conn2", result.output)

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.list_connections")
    def test_list_connections_text_output_no_connections(
        self, mock_api_list, mock_console
    ):
        """Test list_connections with text output and no connections"""
        mock_api_list.return_value = []

        result = self.runner.invoke(list_connections, ["--output", "text"])

        mock_api_list.assert_called_once()
        mock_console.info.assert_called_once_with("No Gefyra connection found")
        self.assertEqual(result.exit_code, 0)

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.list_connections")
    def test_list_connections_json_output_with_data(self, mock_api_list, mock_console):
        """Test list_connections with json output"""
        # Setup mock connection objects
        conn1 = Mock()
        conn1.name = "conn1"
        conn1.list_dict = {"name": "conn1", "version": "1.0.0"}
        conn2 = Mock()
        conn2.name = "conn2"
        conn2.list_dict = {"name": "conn2", "version": "1.0.1"}

        mock_api_list.return_value = [conn1, conn2]

        result = self.runner.invoke(list_connections, ["--output", "json"])

        mock_api_list.assert_called_once()
        self.assertEqual(result.exit_code, 0)

        # Verify the JSON output
        output_json = json.loads(result.output)
        self.assertIn("conn1", output_json)
        self.assertIn("conn2", output_json)
        self.assertEqual(output_json["conn1"]["version"], "1.0.0")
        self.assertEqual(output_json["conn2"]["version"], "1.0.1")

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.list_connections")
    def test_list_connections_json_output_empty(self, mock_api_list, mock_console):
        """Test list_connections with json output and no connections"""
        mock_api_list.return_value = []

        result = self.runner.invoke(list_connections, ["--output", "json"])

        mock_api_list.assert_called_once()
        self.assertEqual(result.exit_code, 0)

        # Should output empty JSON object
        output_json = json.loads(result.output)
        self.assertEqual(output_json, {})

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.list_connections")
    def test_list_connections_single_connection_text(self, mock_api_list, mock_console):
        """Test list_connections with single connection in text format"""
        conn = Mock()
        conn.list_values = ["default", "2.0.0", "2026-04-15", "ready"]

        mock_api_list.return_value = [conn]

        result = self.runner.invoke(list_connections, ["--output", "text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("default", result.output)
        self.assertIn("2.0.0", result.output)

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.list_connections")
    def test_list_connections_many_connections(self, mock_api_list, mock_console):
        """Test list_connections with many connections"""
        connections = []
        for i in range(5):
            conn = Mock()
            conn.list_values = [f"conn{i}", "1.0.0", f"2026-04-{i + 1:02d}", "active"]
            connections.append(conn)

        mock_api_list.return_value = connections

        result = self.runner.invoke(list_connections, ["--output", "text"])

        self.assertEqual(result.exit_code, 0)
        for i in range(5):
            self.assertIn(f"conn{i}", result.output)


class TestInspectConnection(unittest.TestCase):
    """Tests for inspect_connection function"""

    def setUp(self):
        self.runner = CliRunner()

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_text_output(self, mock_api_inspect, mock_console):
        """Test inspect_connection with text output"""
        # Setup mock connection object
        conn = Mock()
        conn.name = "test-connection"
        conn.version = "1.0.0"
        conn.created = "2026-04-01"
        conn.status = "ready"
        conn.client_status = "WAITING"

        mock_api_inspect.return_value = conn

        result = self.runner.invoke(
            inspect_connection, ["test-connection", "--output", "text"]
        )

        # Verify API was called with correct connection name
        mock_api_inspect.assert_called_once_with(connection_name="test-connection")
        self.assertEqual(result.exit_code, 0)

        # Verify console output
        mock_console.heading.assert_called_once_with("test-connection")
        assert mock_console.info.call_count == 4
        mock_console.info.assert_any_call("Version: 1.0.0")
        mock_console.info.assert_any_call("Created: 2026-04-01")
        mock_console.info.assert_any_call("Cargo Status: ready")
        mock_console.info.assert_any_call("Gefyra Client (Cluster) Status: WAITING")

    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_json_output(self, mock_api_inspect):
        """Test inspect_connection with json output"""
        # Setup mock connection object
        conn = Mock()
        conn.json = '{"name": "test-connection", "version": "1.0.0"}'

        mock_api_inspect.return_value = conn

        result = self.runner.invoke(
            inspect_connection, ["test-connection", "--output", "json"]
        )

        # Verify API was called
        mock_api_inspect.assert_called_once_with(connection_name="test-connection")
        self.assertEqual(result.exit_code, 0)

        # Verify JSON output
        self.assertIn("test-connection", result.output)
        self.assertIn("1.0.0", result.output)

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_default_output_is_text(
        self, mock_api_inspect, mock_console
    ):
        """Test inspect_connection default output format is text"""
        conn = Mock()
        conn.name = "default"
        conn.version = "2.0.0"
        conn.created = "2026-04-10"
        conn.status = "active"
        conn.client_status = "READY"

        mock_api_inspect.return_value = conn

        # Call without specifying output (should default to "text")
        result = self.runner.invoke(inspect_connection, ["default"])

        self.assertEqual(result.exit_code, 0)
        mock_console.heading.assert_called_once_with("default")
        assert mock_console.info.call_count == 4

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_with_special_characters_in_name(
        self, mock_api_inspect, mock_console
    ):
        """Test inspect_connection with special characters in connection name"""
        conn = Mock()
        conn.name = "test-connection-123"
        conn.version = "1.0.0"
        conn.created = "2026-04-01"
        conn.status = "ready"
        conn.client_status = "WAITING"

        mock_api_inspect.return_value = conn

        result = self.runner.invoke(
            inspect_connection, ["test-connection-123", "--output", "text"]
        )

        self.assertEqual(result.exit_code, 0)
        mock_api_inspect.assert_called_once_with(connection_name="test-connection-123")
        mock_console.heading.assert_called_once_with("test-connection-123")

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_with_various_statuses(
        self, mock_api_inspect, mock_console
    ):
        """Test inspect_connection with various connection statuses"""
        statuses = [
            ("ready", "WAITING"),
            ("pending", "CONNECTING"),
            ("failed", "ERROR"),
            ("inactive", "DISCONNECTED"),
        ]

        for cargo_status, client_status in statuses:
            mock_console.reset_mock()
            mock_api_inspect.reset_mock()

            conn = Mock()
            conn.name = "test"
            conn.version = "1.0.0"
            conn.created = "2026-04-01"
            conn.status = cargo_status
            conn.client_status = client_status

            mock_api_inspect.return_value = conn

            result = self.runner.invoke(
                inspect_connection, ["test", "--output", "text"]
            )

            self.assertEqual(result.exit_code, 0)
            # Verify the status messages were included
            mock_console.info.assert_any_call(f"Cargo Status: {cargo_status}")
            mock_console.info.assert_any_call(
                f"Gefyra Client (Cluster) Status: {client_status}"
            )

    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_json_output_preserves_format(self, mock_api_inspect):
        """Test inspect_connection json output preserves JSON format"""
        json_data = {
            "name": "test",
            "version": "1.0.0",
            "created": "2026-04-01",
            "status": "ready",
        }

        conn = Mock()
        conn.json = json.dumps(json_data)

        mock_api_inspect.return_value = conn

        result = self.runner.invoke(inspect_connection, ["test", "--output", "json"])

        self.assertEqual(result.exit_code, 0)

        # Verify it's valid JSON
        output_json = json.loads(result.output.strip())
        self.assertEqual(output_json["name"], "test")
        self.assertEqual(output_json["version"], "1.0.0")

    @patch("gefyra.cli.connections.console")
    @patch("gefyra.api.inspect_connection")
    def test_inspect_connection_text_output_console_methods(
        self, mock_api_inspect, mock_console
    ):
        """Test inspect_connection uses correct console methods"""
        conn = Mock()
        conn.name = "my-connection"
        conn.version = "1.5.0"
        conn.created = "2026-03-15"
        conn.status = "ready"
        conn.client_status = "READY"

        mock_api_inspect.return_value = conn

        result = self.runner.invoke(
            inspect_connection, ["my-connection", "--output", "text"]
        )

        self.assertEqual(result.exit_code, 0)
        # Verify heading method is called first
        assert mock_console.method_calls[0] == call.heading("my-connection")

        # Verify info method is called for each detail
        info_calls = [c for c in mock_console.method_calls if c[0] == "info"]
        assert len(info_calls) == 4
