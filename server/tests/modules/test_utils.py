import io
import unittest
import numpy
import pandas
from django.test import SimpleTestCase, override_settings
from pandas.testing import assert_frame_equal
from server.models import Workflow
from server.modules.types import ProcessResult
from server.modules.utils import build_globals_for_eval, parse_bytesio, \
        turn_header_into_first_row, get_id_from_url, store_external_workflow
from server.tests.utils import LoggedInTestCase, load_and_add_module, \
        create_test_user


class SafeExecTest(unittest.TestCase):
    def exec_code(self, code):
        built_globals = build_globals_for_eval()
        inner_locals = {}
        exec(code, built_globals, inner_locals)
        return inner_locals

    def test_builtin_functions(self):
        env = self.exec_code("""
ret = sorted(list([1, 2, sum([3, 4])]))
""")
        self.assertEqual(env['ret'], [1, 2, 7])


class ParseBytesIoTest(SimpleTestCase):
    def test_parse_utf8_csv(self):
        result = parse_bytesio(io.BytesIO(b'A\ncaf\xc3\xa9'),
                               'text/csv', 'utf-8')
        expected = ProcessResult(
            pandas.DataFrame({'A': ['café']}).astype('category')
        )
        self.assertEqual(result, expected)

    def test_replace_invalid_utf8(self):
        # \xe9 is ISO-8859-1 and we select 'utf-8' to test Workbench's recovery
        result = parse_bytesio(io.BytesIO(b'A\ncaf\xe9'),
                               'text/csv', 'utf-8')
        expected = ProcessResult(
            pandas.DataFrame({'A': ['caf�']}).astype('category')
        )
        self.assertEqual(result, expected)

    def test_autodetect_charset_iso8859_1(self):
        # \xe9 is ISO-8859-1 so Workbench should auto-detect it
        result = parse_bytesio(io.BytesIO(b'A\ncaf\xe9'),
                               'text/csv', None)
        expected = ProcessResult(
            pandas.DataFrame({'A': ['café']}).astype('category')
        )
        self.assertEqual(result, expected)

    def test_autodetect_charset_windows_1252(self):
        # \x96 is - in windows-1252, does not exist in UTF-8 or ISO-8859-1
        result = parse_bytesio(io.BytesIO(b'A\n2000\x962018'),
                               'text/csv', None)
        expected = ProcessResult(
            pandas.DataFrame({'A': ['2000–2018']}).astype('category')
        )
        self.assertEqual(result, expected)

    def test_autodetect_charset_utf8(self):
        result = parse_bytesio(
            io.BytesIO(b'A\n\xE8\xB0\xA2\xE8\xB0\xA2\xE4\xBD\xA0'),
            'text/csv',
            None
        )
        expected = ProcessResult(
            pandas.DataFrame({'A': ['谢谢你']}).astype('category')
        )
        self.assertEqual(result, expected)

    @override_settings(CHARDET_CHUNK_SIZE=3)
    def test_autodetect_charset_chunked(self):
        result = parse_bytesio(io.BytesIO(b'A\ncaf\xe9'),
                               'text/csv', None)
        expected = ProcessResult(
            pandas.DataFrame({'A': ['café']}).astype('category')
        )
        self.assertEqual(result, expected)

    def test_json_with_nulls(self):
        result = parse_bytesio(io.BytesIO("""[
            {"A": "a"},
            {"A": null}
        ]""".encode('utf-8')), 'application/json')
        expected = ProcessResult(
            pandas.DataFrame({'A': ['a', None]}, dtype=str)
        )
        self.assertEqual(result, expected)

    def test_json_with_undefined(self):
        result = parse_bytesio(io.BytesIO("""[
            {"A": "a"},
            {"A": "aa", "B": "b"}
        ]""".encode('utf-8')), 'application/json')
        expected = ProcessResult(
            pandas.DataFrame({'A': ['a', 'aa'], 'B': [numpy.nan, 'b']},
                             dtype=str)
        )
        self.assertEqual(result, expected)

    def test_txt_detect_separator_semicolon(self):
        result = parse_bytesio(io.BytesIO(b'A;C\nB;D'),
                               'text/plain', 'utf-8')
        expected = ProcessResult(pandas.DataFrame({'A': ['B'], 'C': ['D']}))
        self.assertEqual(result, expected)

    def test_txt_detect_separator_tab(self):
        result = parse_bytesio(io.BytesIO(b'A\tC\nB\tD'),
                               'text/plain', 'utf-8')
        expected = ProcessResult(pandas.DataFrame({'A': ['B'], 'C': ['D']}))
        self.assertEqual(result, expected)

    def test_txt_detect_separator_comma(self):
        result = parse_bytesio(io.BytesIO(b'A,C\nB,D'),
                               'text/plain', 'utf-8')
        expected = ProcessResult(pandas.DataFrame({'A': ['B'], 'C': ['D']}))
        self.assertEqual(result, expected)


class OtherUtilsTests(SimpleTestCase):
    def test_turn_header_into_first_row(self):
        result = turn_header_into_first_row(pandas.DataFrame({'A': ['B'],
                                                              'C': ['D']}))
        expected = pandas.DataFrame({'0': ['A', 'B'], '1': ['C', 'D']})
        assert_frame_equal(result, expected)

        # Function should return None when a table has not been uploaded yet
        self.assertIsNone(turn_header_into_first_row(None))

    def test_get_id_from_url(self):
        result_map = {
            'www.google.com': False,
            'https://app.workbenchdata.com/workflows/4370/': 4370,
            'https://staging.workbenchdata.com/workflows/18': 18,
            'not a url': False,
            'https://staging.workbenchdata.com/workflows/': False
        }

        for url, expected_result in result_map.items():
            if not expected_result:
                with self.assertRaises(Exception):
                    get_id_from_url(url)
            else:
                self.assertEqual(get_id_from_url(url), expected_result)


class WorkflowImport(LoggedInTestCase):
    def setUp(self):
        super(WorkflowImport, self).setUp()  # log in
        self.wfm = load_and_add_module('concaturl')
        # Second workflow loaded with data
        self.ext_wfm = load_and_add_module('uploadfile')
        self.ext_wfm.cache_render_result(
            delta_id=1,
            result=ProcessResult(self.ext_wfm.retrieve_fetched_table())
        )
        self.ext_wfm.save()

    def test_auth(self):
        # Create otheruser and try to access workflow owned by default user
        other_user = create_test_user(username='otheruser',
                                      email='otheruser@email.com')
        wf = Workflow.objects.create(name='New Workflow', owner=other_user)
        wfm = load_and_add_module('concaturl', workflow=wf)

        result = store_external_workflow(
            wfm,
            (f'https://app.workbenchdata.com/workflows/'
             f'{self.ext_wfm.workflow_id}/')
        )
        self.assertEqual(result, ProcessResult(
            error='Access denied to the target workflow'
        ))

    def test_same_workflow(self):
        result = store_external_workflow(
            self.wfm,
            f'https://app.workbenchdata.com/workflows/{self.wfm.workflow_id}/'
        )
        self.assertEqual(result, ProcessResult(
            error='Cannot import the current workflow'
        ))

    def test_workflow_does_not_exist(self):
        result = store_external_workflow(
            self.wfm,
            f'https://app.workbenchdata.com/workflows/99999999999/'
        )
        self.assertEqual(result, ProcessResult(
            error='Target workflow does not exist'
        ))

    def test_workflow_without_modules(self):
        workflow = Workflow.objects.create()
        tab = workflow.tabs.create()
        wfm = WfModule(workflow_id=1)
        result = store_external_workflow(
