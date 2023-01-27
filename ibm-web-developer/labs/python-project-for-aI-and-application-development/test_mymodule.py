import unittest

from mymodule import square, double, add

class TestSquare(unittest.TestCase):
    def test1(self):
        self.assertEqual(square(2),4)
        self.assertEqual(square(3.0),9.0)
        self.assertNotEqual(square(-3),-9)
        
class TestDouble(unittest.TestCase):
    def test1(self):
        self.assertEqual(double(2),4)
        self.assertEqual(double(-3.1),-6.2)
        self.assertEqual(double(0),0)

class TestAdd(unittest.TestCase):
    def test1(self):
        self.assertEqual(add(1,2),3)
        self.assertEqual(add(5,7),12)
        self.assertEqual(add(20,7),27)
        self.assertNotEqual(add(20,7),20)

unittest.main()