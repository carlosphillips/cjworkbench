from django.contrib.auth.models import User
from django.test import TestCase
from server.tests.utils import LoggedInTestCase, add_new_wf_module, add_new_module_version, create_testdata_workflow
from server.models import Workflow
from server.models.commands import InitWorkflowCommand


class MockSession:
    def __init__(self, session_key):
        self.session_key = session_key


class MockRequest:
    def __init__(self, user, session_key):
        self.user = user
        self.session = MockSession(session_key)

    @staticmethod
    def logged_in(user):
        return MockRequest(user, 'user-' + user.username)

    @staticmethod
    def anonymous(session_key):
        return MockRequest(None, session_key)

    @staticmethod
    def uninitialized():
        return MockRequest(None, None)


class WorkflowTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()

        self.otheruser = User.objects.create(username='user2',
                                             email='user2@users.com',
                                             password='password')

    def test_workflow_duplicate(self):
        # Create workflow with two WfModules
        wf1 = Workflow.objects.create(name='Foo')
        InitWorkflowCommand.create(wf1)
        tab = wf1.tabs.create(position=0)
        wfm1 = tab.wf_modules.create(order=0)

        wf2 = wf1.duplicate(self.otheruser)

        self.assertNotEqual(wf1.id, wf2.id)
        self.assertEqual(wf2.owner, self.otheruser)
        self.assertEqual(wf2.name, 'Copy of Foo')
        self.assertEqual(wf2.deltas.all().count(), 1)
        self.assertIsInstance(wf2.last_delta, InitWorkflowCommand)
        self.assertFalse(wf2.public)
        self.assertEqual(wf1.wf_modules.count(), wf2.wf_modules.count())

    def test_auth_shared_workflow(self):
        wf = Workflow.objects.create(owner=self.user, public=True)

        # Read: anybody
        self.assertTrue(wf.request_authorized_read(MockRequest.logged_in(self.user)))
        self.assertTrue(wf.request_authorized_read(MockRequest.logged_in(self.otheruser)))
        self.assertTrue(wf.request_authorized_read(MockRequest.anonymous('session1')))
        self.assertTrue(wf.request_authorized_read(MockRequest.uninitialized()))

        # Write: only owner
        self.assertTrue(wf.request_authorized_write(MockRequest.logged_in(self.user)))
        self.assertFalse(wf.request_authorized_write(MockRequest.logged_in(self.otheruser)))
        self.assertFalse(wf.request_authorized_write(MockRequest.anonymous('session1')))
        self.assertFalse(wf.request_authorized_write(MockRequest.uninitialized()))

    def test_auth_private_workflow(self):
        wf = Workflow.objects.create(owner=self.user, public=False)

        # Read: anybody
        self.assertTrue(wf.request_authorized_read(MockRequest.logged_in(self.user)))
        self.assertFalse(wf.request_authorized_read(MockRequest.logged_in(self.otheruser)))
        self.assertFalse(wf.request_authorized_read(MockRequest.anonymous('session1')))
        self.assertFalse(wf.request_authorized_read(MockRequest.uninitialized()))

        # Write: only owner
        self.assertTrue(wf.request_authorized_write(MockRequest.logged_in(self.user)))
        self.assertFalse(wf.request_authorized_write(MockRequest.logged_in(self.otheruser)))
        self.assertFalse(wf.request_authorized_write(MockRequest.anonymous('session1')))
        self.assertFalse(wf.request_authorized_write(MockRequest.uninitialized()))

    def test_auth_anonymous_workflow(self):
        wf = Workflow.objects.create(owner=None,
                                     anonymous_owner_session_key='session1',
                                     public=False)

        # Read: just the anonymous user, logged in or not
        self.assertTrue(wf.request_authorized_read(MockRequest.anonymous('session1')))
        self.assertTrue(wf.request_authorized_read(MockRequest(self.user, 'session1')))
        self.assertFalse(wf.request_authorized_read(MockRequest.logged_in(self.user)))
        self.assertFalse(wf.request_authorized_read(MockRequest.anonymous('session2')))
        self.assertFalse(wf.request_authorized_read(MockRequest.uninitialized()))

        # Write: ditto
        self.assertTrue(wf.request_authorized_write(MockRequest.anonymous('session1')))
        self.assertTrue(wf.request_authorized_write(MockRequest(self.user, 'session1')))
        self.assertFalse(wf.request_authorized_write(MockRequest.logged_in(self.user)))
        self.assertFalse(wf.request_authorized_write(MockRequest.anonymous('session2')))
        self.assertFalse(wf.request_authorized_read(MockRequest.uninitialized()))
