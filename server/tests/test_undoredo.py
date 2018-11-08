from unittest.mock import patch
from asgiref.sync import async_to_sync
from server.models import Delta
from server.models.commands import AddModuleCommand, ChangeParametersCommand, \
        ChangeWorkflowTitleCommand, ChangeWfModuleNotesCommand
from server.tests.utils import DbTestCase, load_module_version, \
        get_param_by_id_name
from server.versions import WorkflowUndo, WorkflowRedo


async def async_noop(*args, **kwargs):
    pass


@patch('server.models.Delta.schedule_execute', async_noop)
@patch('server.models.Delta.ws_notify', async_noop)
class UndoRedoTests(DbTestCase):
    # Many things tested here:
    #  - Undo with 0,1,2 commands in stack
    #  - Redo with 0,1,2 commands to redo
    #  - Start with 3 commands in stack, then undo, undo, new command -> blow
    #    away commands 2,3
    # Command types used here are arbitrary, but different so that we test
    # polymorphism
    def test_undo_redo(self):
        def assertWfModuleVersions(self, expected_versions):
            result = list(
                self.tab.live_wf_modules
                .values_list('last_relevant_delta_id', flat=True)
            )
            self.assertEqual(result, expected_versions)

        csv = load_module_version('pastecsv')
        workflow = Workflow.objects.create()
        InitWorkflowCommand.create(workflow)
        tab = workflow.tabs.create(position=0)

        all_modules = tab.live_wf_modules
        self.assertEqual(all_modules.count(), 0)
        self.assertEqual(workflow.last_delta_id, None)

        v0 = workflow.last_delta_id

        # Test undoing nothing at all. Should NOP
        async_to_sync(WorkflowUndo)(workflow)
        self.assertEqual(workflow.last_delta_id, v0)
        self.assertEqual(all_modules.count(), 0)

        # Add a module
        cmd1 = async_to_sync(AddModuleCommand.create)(workflow, tab,
                                                      csv, 0, {})
        self.assertEqual(all_modules.count(), 1)
        self.assertNotEqual(workflow.last_delta_id, None)
        v1 = workflow.last_delta_id
        self.assertGreater(v1, v0)
        assertWfModuleVersions([v1])

        # Undo, ensure we are back at start
        async_to_sync(WorkflowUndo)(workflow)
        self.assertEqual(workflow.last_delta_id, v0)
        self.assertEqual(all_modules.count(), 0)
        self.assertEqual(workflow.last_delta_id, None)
        assertWfModuleVersions([])

        # Redo, ensure we are back at v1
        async_to_sync(WorkflowRedo)(workflow)
        self.assertEqual(all_modules.count(), 1)
        self.assertNotEqual(workflow.last_delta_id, None)
        self.assertEqual(workflow.last_delta_id, v1)
        assertWfModuleVersions([v1])

        wfm = all_modules.first()

        # Change a parameter
        pval = get_param_by_id_name('csv')
        cmd2 = async_to_sync(ChangeParametersCommand.create)(
            workflow=workflow,
            wf_module=wfm,
            new_values={'csv': 'some value'}
        )
        pval.refresh_from_db()
        self.assertEqual(pval.value, 'some value')
        workflow.refresh_from_db()
        v2 = workflow.last_delta_id
        self.assertGreater(v2, v1)
        assertWfModuleVersions([v2])

        # Undo parameter change
        async_to_sync(WorkflowUndo)(workflow)
        self.assertEqual(workflow.last_delta_id, v1)
        pval.refresh_from_db()
        self.assertEqual(pval.value, '')
        assertWfModuleVersions([v1])

        # Redo
        async_to_sync(WorkflowRedo)(workflow)
        self.assertEqual(workflow.last_delta_id, v2)
        pval.refresh_from_db()
        self.assertEqual(pval.value, 'some value')
        assertWfModuleVersions([v2])

        # Redo again should do nothing
        async_to_sync(WorkflowRedo)(workflow)
        self.assertEqual(workflow.last_delta_id, v2)
        self.assertEqual(pval.value, 'some value')
        assertWfModuleVersions([v2])

        # Add one more command so the stack is 3 deep
        cmd3 = async_to_sync(ChangeWorkflowTitleCommand.create)(workflow,
                                                                "New Title")
        # workflow.refresh_from_db()
        v3 = workflow.last_delta_id
        self.assertGreater(v3, v2)
        assertWfModuleVersions([v2])

        # Undo twice
        async_to_sync(WorkflowUndo)(workflow)
        self.assertEqual(workflow.last_delta_id, v2)
        assertWfModuleVersions([v2])
        async_to_sync(WorkflowUndo)(workflow)
        self.assertEqual(workflow.last_delta_id, v1)
        assertWfModuleVersions([v1])

        # Redo twice
        async_to_sync(WorkflowRedo)(workflow)
        self.assertEqual(workflow.last_delta_id, v2)
        assertWfModuleVersions([v2])
        async_to_sync(WorkflowRedo)(workflow)
        self.assertEqual(workflow.last_delta_id, v3)
        assertWfModuleVersions([v2])

        # Undo again to get to a place where we have two commands to redo
        async_to_sync(WorkflowUndo)(workflow)
        async_to_sync(WorkflowUndo)(workflow)
        self.assertEqual(workflow.last_delta_id, v1)

        # Now add a new command. It should remove cmd2, cmd3 from the redo
        # stack and delete them from the db
        wfm = all_modules.first()
        cmd4 = async_to_sync(ChangeWfModuleNotesCommand.create)(
            wfm,
            "Note of no note"
        )
        workflow.refresh_from_db()
        self.assertEqual(workflow.last_delta_id, v4)
        self.assertFalse(Delta.objects.filter(pk=v2).exists())
        self.assertFalse(Delta.objects.filter(pk=v3).exists())

        # Undo back to start, then add a command, ensure it deletes dangling
        # commands (tests an edge case in Delta.save)
        self.assertEqual(Delta.objects.count(), 2)
        async_to_sync(WorkflowUndo)(workflow)
        async_to_sync(WorkflowUndo)(workflow)
        self.assertIsNone(workflow.last_delta)
        cmd5 = async_to_sync(ChangeWfModuleNotesCommand.create)(
            wfm,
            "Note of some note"
        )
        workflow.refresh_from_db()
        self.assertEqual(workflow.last_delta_id, v5)
        assertWfModuleVersions([v1])
        self.assertFalse(Delta.objects.filter(pk=v1).exists())
        self.assertFalse(Delta.objects.filter(pk=v4).exists())
