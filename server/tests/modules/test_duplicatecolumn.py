import unittest
import pandas as pd
from server.modules.duplicatecolumn import DuplicateColumn
from server.modules.types import ProcessResult
from .util import MockParams


def render(colnames, table):
    result = DuplicateColumn.render(MockParams(colnames=colnames), table)
    result = ProcessResult.coerce(result)
    result.sanitize_in_place()  # important: duplicate makes colname conflicts
    return result


class DuplicateColumnTests(unittest.TestCase):
    def test_duplicate_column(self):
        table = pd.DataFrame({
            'A': [1, 2],
            'B': [2, 3],
            'C': [3, 4],
        })
        result = render((['A', 'C'], []), table)

        expected = ProcessResult(pd.DataFrame({
            'A': [1, 2],
            'Copy of A': [1, 2],
            'B': [2, 3],
            'C': [3, 4],
            'Copy of C': [3, 4],
        }))
        self.assertEqual(result, expected)

    def test_duplicate_with_existing(self):
        table = pd.DataFrame({
            'A': [1, 2],
            'Copy of A': [2, 3],
            'Copy of A 1': [3, 4],
            'C': [4, 5],
        })
        result = render((['A'], []), table)

        expected = ProcessResult(pd.DataFrame({
            'A': [1, 2],
            'Copy of A 2': [1, 2],
            'Copy of A': [2, 3],
            'Copy of A 1': [3, 4],
            'C': [4, 5],
        }))
        self.assertEqual(result, expected)
