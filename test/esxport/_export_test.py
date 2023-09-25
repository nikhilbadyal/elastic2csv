# Generated by CodiumAI
import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec, patch

import pytest
from typing_extensions import Self

from esxport.esxport import EsXport


@patch("esxport.esxport.EsXport._validate_fields")
class TestExport:
    """Tests that the method exports the data with valid arguments."""

    csv_header = ["age", "name"]

    @staticmethod
    def rm_export_file(file_name: str) -> None:
        """Cleaer up resources."""
        Path(f"{file_name}.tmp").unlink(missing_ok=True)

    @staticmethod
    def rm_csv_export_file(file_name: str) -> None:
        """Cleaer up resources."""
        Path(file_name).unlink(missing_ok=True)

    def test_export_with_valid_arguments(
        self: Self,
        _: Any,
        esxport_obj: EsXport,
    ) -> None:
        """Checks if the method exports the data properly when given valid arguments."""
        esxport_obj.opts.output_file = f"{inspect.stack()[0].function}.csv"
        export = create_autospec(esxport_obj.export)

        export()

        export.assert_called_once_with()
        TestExport.rm_export_file(f"{inspect.stack()[0].function}.csv")

    def test_export_invalid_format(
        self: Self,
        _: Any,
        esxport_obj: EsXport,
    ) -> None:
        """Check if exception is raised when formatting is invalid."""
        esxport_obj.opts.format = "invalid_format"
        with patch.object(EsXport, "_extract_headers", return_value=[]), pytest.raises(NotImplementedError):
            esxport_obj.export()
        TestExport.rm_export_file(f"{inspect.stack()[0].function}.csv")

    def test_headers_extraction(
        self: Self,
        _: Any,
        esxport_obj: EsXport,
    ) -> None:
        """Check if exception is raised when formatting is invalid."""
        esxport_obj.opts.output_file = f"{inspect.stack()[0].function}.csv"
        test_json = {"age": 2, "bar": "foo", "hello": "world"}
        temp_file = f"{esxport_obj.opts.output_file}.tmp"
        with Path(temp_file).open("w") as tmp_file:
            json.dump(test_json, tmp_file)
        assert esxport_obj._extract_headers() == list(test_json.keys())
        TestExport.rm_export_file(f"{inspect.stack()[0].function}.csv")
