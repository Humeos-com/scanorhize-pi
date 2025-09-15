#!/usr/bin/env python3
"""
Unit tests for pin_config.py
"""

import unittest
import json
from unittest.mock import patch, mock_open, MagicMock
from pin_config import (
    CHRG_PIN,
    STDBY_PIN,
    DEFAULT_PIN_ARRAY,
    get_pin_array,
    get_ch_pin,
)


class TestPinConfig(unittest.TestCase):
    """Test cases for pin_config.py"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock logger
        self.mock_logger = MagicMock()
        # Patch the getLogger function to return our mock logger
        self.logger_patcher = patch(
            "pin_config.getLogger", return_value=self.mock_logger
        )
        self.mock_get_logger = self.logger_patcher.start()

    def tearDown(self):
        """Clean up after each test method."""
        self.logger_patcher.stop()

    def test_constant_pins(self):
        """Test that constant pin values are correctly defined"""
        self.assertEqual(CHRG_PIN, 5)
        self.assertEqual(STDBY_PIN, 6)
        self.assertEqual(DEFAULT_PIN_ARRAY, [13, 22, 27, 19])

    def test_get_pin_array_default(self):
        """Test get_pin_array returns default when file doesn't exist"""
        with patch("os.path.exists", return_value=False):
            result = get_pin_array()
            self.assertEqual(result, DEFAULT_PIN_ARRAY)
            self.mock_logger.error.assert_not_called()

    def test_get_pin_array_file_not_found(self):
        """Test get_pin_array handles FileNotFoundError"""
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", side_effect=FileNotFoundError
        ):
            result = get_pin_array()
            self.assertEqual(result, DEFAULT_PIN_ARRAY)
            self.mock_logger.error.assert_called_once()

    def test_get_pin_array_json_decode_error(self):
        """Test get_pin_array handles JSONDecodeError"""
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data="invalid json")
        ):
            result = get_pin_array()
            self.assertEqual(result, DEFAULT_PIN_ARRAY)
            self.mock_logger.error.assert_called_once()

    def test_get_pin_array_missing_key(self):
        """Test get_pin_array handles missing PinArray key"""
        test_config = {"other_key": "value"}
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data=json.dumps(test_config))
        ):
            result = get_pin_array()
            self.assertEqual(result, DEFAULT_PIN_ARRAY)
            self.mock_logger.error.assert_called_once()

    def test_get_pin_array_success(self):
        """Test get_pin_array successfully reads pin array from config"""
        test_pins = [1, 2, 3, 4]
        test_config = {"PinArray": test_pins}
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data=json.dumps(test_config))
        ):
            result = get_pin_array()
            self.assertEqual(result, test_pins)
            self.mock_logger.error.assert_not_called()

    def test_get_ch_pin_valid_index(self):
        """Test get_ch_pin with valid index"""
        with patch("pin_config.get_pin_array", return_value=[1, 2, 3, 4]):
            self.assertEqual(get_ch_pin(0), 1)
            self.assertEqual(get_ch_pin(1), 2)
            self.assertEqual(get_ch_pin(2), 3)
            self.assertEqual(get_ch_pin(3), 4)

    def test_get_ch_pin_invalid_index(self):
        """Test get_ch_pin with invalid index"""
        with patch("pin_config.get_pin_array", return_value=[1, 2, 3, 4]):
            self.assertIsNone(get_ch_pin(-1))
            self.assertIsNone(get_ch_pin(4))
            self.assertIsNone(get_ch_pin(10))

    def test_get_ch_pin_empty_array(self):
        """Test get_ch_pin with empty pin array"""
        with patch("pin_config.get_pin_array", return_value=[]):
            self.assertIsNone(get_ch_pin(0))


if __name__ == "__main__":
    unittest.main()
