import unittest
from unittest.mock import Mock, patch

import context

from oec.display import Dimensions, Display, encode_ascii_character, encode_string

class DisplayMoveCursorTestCase(unittest.TestCase):
    def setUp(self):
        self.interface = Mock()

        dimensions = Dimensions(24, 80)

        self.display = Display(self.interface, dimensions)

    def test_with_address(self):
        # Act
        self.display.move_cursor(address=80)

        # Assert
        self.assertEqual(self.display.address_counter, 80)

        self.interface.offload_load_address_counter.assert_called_with(80)

    def test_with_index(self):
        # Act
        self.display.move_cursor(index=15)

        # Assert
        self.assertEqual(self.display.address_counter, 95)

        self.interface.offload_load_address_counter.assert_called_with(95)

    def test_with_coordinates(self):
        # Act
        self.display.move_cursor(row=10, column=15)

        # Assert
        self.assertEqual(self.display.address_counter, 895)

        self.interface.offload_load_address_counter.assert_called_with(895)

    def test_no_change(self):
        # Arrange
        self.display.move_cursor(address=80)

        self.interface.offload_load_address_counter.reset_mock()

        # Act
        self.display.move_cursor(address=80)

        # Assert
        self.assertEqual(self.display.address_counter, 80)

        self.interface.offload_load_address_counter.assert_not_called()

    def test_no_change_force(self):
        # Arrange
        self.display.move_cursor(address=80)

        self.interface.offload_load_address_counter.reset_mock()

        # Act
        self.display.move_cursor(address=80, force_load=True)

        # Assert
        self.assertEqual(self.display.address_counter, 80)

        self.interface.offload_load_address_counter.assert_called_with(80)

class DisplayWriteBufferTestCase(unittest.TestCase):
    def setUp(self):
        self.interface = Mock()

        dimensions = Dimensions(24, 80)

        self.display = Display(self.interface, dimensions)

    def test_with_index(self):
        # Act
        self.display.write_buffer(0x01, index=15)
        self.display.write_buffer(0x02, index=97)

        # Assert
        self.assertEqual(self.display.buffer[15], 0x01)
        self.assertEqual(self.display.buffer[97], 0x02)
        self.assertSequenceEqual(self.display.dirty, [15, 97])

    def test_with_coordinates(self):
        # Act
        self.display.write_buffer(0x01, row=0, column=15)
        self.display.write_buffer(0x02, row=1, column=17)

        # Assert
        self.assertEqual(self.display.buffer[15], 0x01)
        self.assertEqual(self.display.buffer[97], 0x02)
        self.assertSequenceEqual(self.display.dirty, [15, 97])

    def test_change(self):
        self.assertTrue(self.display.write_buffer(0x01, index=0))
        self.assertTrue(self.display.write_buffer(0x02, index=0))

        self.assertEqual(self.display.buffer[0], 0x02)
        self.assertSequenceEqual(self.display.dirty, [0])

    def test_no_change(self):
        self.assertTrue(self.display.write_buffer(0x01, index=0))
        self.assertFalse(self.display.write_buffer(0x01, index=0))

        self.assertEqual(self.display.buffer[0], 0x01)
        self.assertSequenceEqual(self.display.dirty, [0])

class DisplayFlushTestCase(unittest.TestCase):
    def setUp(self):
        self.interface = Mock()

        dimensions = Dimensions(24, 80)

        self.display = Display(self.interface, dimensions)

        self.display._flush_range = Mock()

    def test_no_changes(self):
        # Act
        self.display.flush()

        # Assert
        self.display._flush_range.assert_not_called()

    def test_single_range(self):
        # Arrange
        self.display.write_buffer(0x01, index=0)
        self.display.write_buffer(0x02, index=1)
        self.display.write_buffer(0x03, index=2)

        # Act
        self.display.flush()

        # Assert
        self.display._flush_range.assert_called_with(0, 2)

    def test_multiple_ranges(self):
        # Arrange
        self.display.write_buffer(0x01, index=0)
        self.display.write_buffer(0x02, index=1)
        self.display.write_buffer(0x03, index=2)
        self.display.write_buffer(0x05, index=30)
        self.display.write_buffer(0x06, index=31)
        self.display.write_buffer(0x04, index=20)

        # Act
        self.display.flush()

        # Assert
        self.display._flush_range.assert_called_with(0, 31)

class DisplayClearTestCase(unittest.TestCase):
    def setUp(self):
        self.interface = Mock()

        dimensions = Dimensions(24, 80)

        self.display = Display(self.interface, dimensions)

    def test_excluding_status_line(self):
        # Arrange
        self.display.write_buffer(0x01, index=0)

        self.assertEqual(self.display.buffer[0], 0x01)
        self.assertTrue(self.display.dirty)

        # Act
        self.display.clear(include_status_line=False)

        # Assert
        self.interface.offload_write.assert_called_with(b'\x00', address=80, repeat=1919)
        self.interface.offload_load_address_counter.assert_called_with(80)

        self.assertEqual(self.display.buffer[0], 0x00)
        self.assertFalse(self.display.dirty)

    def test_including_status_line(self):
        # Arrange
        self.display.write_buffer(0x01, index=0)

        self.assertEqual(self.display.buffer[0], 0x01)
        self.assertTrue(self.display.dirty)

        # Act
        self.display.clear(include_status_line=True)

        # Assert
        self.interface.offload_write.assert_called_with(b'\x00', address=0, repeat=1999)
        self.interface.offload_load_address_counter.assert_called_with(80)

        self.assertEqual(self.display.buffer[0], 0x00)
        self.assertFalse(self.display.dirty)

class DisplayFlushRangeTestCase(unittest.TestCase):
    def setUp(self):
        self.interface = Mock()

        dimensions = Dimensions(24, 80)

        self.display = Display(self.interface, dimensions)

    def test_when_start_address_is_current_address_counter(self):
        # Arrange
        self.display.move_cursor(index=0)

        self.display.write_buffer(0x01, index=0)
        self.display.write_buffer(0x02, index=1)
        self.display.write_buffer(0x03, index=2)

        # Act
        self.display.flush()

        # Assert
        self.interface.offload_write.assert_called_with(bytes.fromhex('01 02 03'), address=None)

        self.assertEqual(self.display.address_counter, 83)
        self.assertFalse(self.display.dirty)

    def test_when_start_address_is_not_current_address_counter(self):
        # Arrange
        self.display.move_cursor(index=70)

        self.display.write_buffer(0x01, index=0)
        self.display.write_buffer(0x02, index=1)
        self.display.write_buffer(0x03, index=2)

        # Act
        self.display.flush()

        # Assert
        self.interface.offload_write.assert_called_with(bytes.fromhex('01 02 03'), address=80)

        self.assertEqual(self.display.address_counter, 83)
        self.assertFalse(self.display.dirty)

class EncodeAsciiCharacterTestCase(unittest.TestCase):
    def test_mapped_character(self):
        self.assertEqual(encode_ascii_character(ord('a')), 0x80)

    def test_unmapped_character(self):
        self.assertEqual(encode_ascii_character(ord('`')), 0x00)

    def test_out_of_range(self):
        self.assertEqual(encode_ascii_character(ord('✓')), 0x00)

class EncodeStringTestCase(unittest.TestCase):
    def test_mapped_characters(self):
        self.assertEqual(encode_string('Hello, world!'), bytes.fromhex('a7 84 8b 8b 8e 33 00 96 8e 91 8b 83 19'))

    def test_unmapped_characters(self):
        self.assertEqual(encode_string('Everything ✓'), bytes.fromhex('a4 95 84 91 98 93 87 88 8d 86 00 18'))
