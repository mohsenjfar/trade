import unittest
from translator import english_to_french, french_to_english

class testEnglishToFrench(unittest.TestCase):

    def test_equal(self):
        self.assertEqual(english_to_french('Hello'), 'Bonjour')
    
    def test_not_equal(self):
        try:
            english_to_french('')
        except Exception as e:
            self.assertNotEqual(e, '')

class testFrenchToEnglish(unittest.TestCase):

    def test_equal(self):
        self.assertEqual(french_to_english('Bonjour'), 'Hello')

    def test_not_equal(self):
        try:
            french_to_english('')
        except Exception as e:
            self.assertNotEqual(e, '')

unittest.main()