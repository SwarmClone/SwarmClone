import unittest

from swarmclone.panel_dummy.__main__ import *


# python -m unittest
class TestIota(unittest.TestCase):
    def test_iota_sequence(self):
        counter = Iota()
        self.assertEqual(counter(), 0)
        self.assertEqual(counter(), 1)
        self.assertEqual(counter(), 2)

class TestModuleConfiguration(unittest.TestCase):
    def test_submodule_enumeration(self):
        self.assertEqual(LLM, 0)
        self.assertEqual(ASR, 1)
        self.assertEqual(TTS, 2)
        self.assertEqual(FRONTEND, 3)
        self.assertEqual(CHAT, 4)
    
    def test_connection_table(self):
        expected = {
            0: ([2, 3], [2, 3]),
            1: ([0, 2, 3], [0, 3]),
            2: ([0, 3], [0, 3]),
            4: ([], [0, 3])
        }
        self.assertDictEqual(CONN_TABLE, expected)

