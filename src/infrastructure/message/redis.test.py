import unittest
from unittest import IsolatedAsyncioTestCase

imports = {
    "framework": "framework/service/language.py",
    "flow": "framework/service/flow.py"
}

exports = {
    "adapter": 'adapter'
}

class AdapterTest(IsolatedAsyncioTestCase):
    async def test_builder(self, *services, **constants):
        """
        Esegue un test generico.
        """
        self.assertEqual('1', '1')