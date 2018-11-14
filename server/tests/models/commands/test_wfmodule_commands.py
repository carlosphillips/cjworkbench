import asyncio
from unittest.mock import patch
from asgiref.sync import async_to_sync
from django.utils import timezone
import pandas as pd
from server.models import Module, ModuleVersion, Workflow, WfModule
from server.models.commands import AddModuleCommand, DeleteModuleCommand, \
        ChangeDataVersionCommand, ChangeWfModuleNotesCommand, \
        ChangeWfModuleUpdateSettingsCommand, ChangeParametersCommand, \
        InitWorkflowCommand
from server.tests.utils import DbTestCase


async def async_noop(*args, **kwargs):
    pass

future_none = asyncio.Future()
future_none.set_result(None)


@patch('server.rabbit.queue_render', async_noop)
@patch('server.websockets.ws_client_send_delta_async', async_noop)
class WfModuleCommandsTest(DbTestCase):
    def setUp(self):
        super().setUp()
        self.workflow = Workflow.objects.create()
        delta1 = InitWorkflowCommand.create(self.workflow)
        self.v1 = delta1.id
        self.tab = self.workflow.tabs.create(position=0)
        module = Module.objects.create()
        self.module_version = module.module_versions.create(version='1.0')

    def assertWfModuleVersions(self, expected_versions):
        positions = list(
            self.tab.live_wf_modules.values_list('order', flat=True)
        )
        self.assertEqual(positions, list(range(0, len(expected_versions))))

        versions = list(
            self.tab.live_wf_modules
            .values_list('last_relevant_delta_id', flat=True)
        )
        self.assertEqual(versions, expected_versions)

    # Add another module, then undo, redo
    def test_add_module(self):
        # beginning state: one WfModule
        all_modules = self.tab.live_wf_modules
        wfm1 = all_modules.create(
            module_version=self.module_version,
            order=0,
            last_relevant_delta_id=self.v1
        )

        # Add a module, insert before the existing one, check to make sure it
        # went there and old one is after
        cmd = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                     self.module_version, 0,
                                                     {'csv': 'A,B\n1,2'})
        self.assertEqual(all_modules.count(), 2)
        wfm1.refresh_from_db()
        added_module = all_modules.get(order=0)
        self.assertNotEqual(added_module, wfm1)
        # Test that supplied param is written
        self.assertEqual(
            len(added_module.parameter_vals.filter(value='A,B\n1,2')),
            1
        )
        bumped_module = all_modules.get(order=1)
        self.assertEqual(bumped_module, wfm1)

        # workflow revision should have been incremented
        self.workflow.refresh_from_db()
        self.assertEqual(self.workflow.last_delta, cmd)

        # undo! undo! ahhhhh everything is on fire! undo!
        async_to_sync(cmd.backward)()
        self.assertEqual(all_modules.count(), 1)
        wfm1.refresh_from_db()
        self.assertEqual(list(all_modules), [wfm1])

        # wait no, we wanted that module
        async_to_sync(cmd.forward)()
        wfm1.refresh_from_db()
        self.assertEqual(list(all_modules), [added_module, wfm1])

        # Undo and test deleting the un-applied command. Should delete dangling
        # WfModule too
        async_to_sync(cmd.backward)()
        wfm1.refresh_from_db()
        self.assertEqual(list(all_modules), [wfm1])
        cmd.delete()
        with self.assertRaises(WfModule.DoesNotExist):
            WfModule.objects.get(pk=added_module.id)  # should be gone

    # Try inserting at various positions to make sure the renumbering works
    # right Then undo multiple times
    def test_add_many_modules(self):
        # beginning state: one WfModule
        all_modules = self.tab.live_wf_modules
        wfm1 = all_modules.create(module_version=self.module_version, order=0,
                                  last_relevant_delta_id=v1)
        self.assertWfModuleVersions([v1])

        # Insert at beginning
        cmd1 = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                      self.module_version,
                                                      0, {})
        v2 = cmd1.id
        self.assertEqual(all_modules.count(), 2)
        self.assertEqual(cmd1.wf_module.order, 0)
        self.assertWfModuleVersions([v2, v2])

        # Insert at end
        cmd2 = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                      self.module_version,
                                                      2, {})
        v3 = cmd2.id
        self.assertEqual(all_modules.count(), 3)
        self.assertEqual(cmd2.wf_module.order, 2)
        self.assertWfModuleVersions([v2, v2, v3])

        # Insert in between two modules
        cmd3 = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                      self.module_version,
                                                      2, {})
        v4 = cmd3.id
        self.assertEqual(all_modules.count(), 4)
        self.assertEqual(cmd3.wf_module.order, 2)
        self.assertWfModuleVersions([v2, v2, v4, v4])

        # Check the delta chain, should be 1 <-> 2 <-> 3
        self.workflow.refresh_from_db()
        cmd1.refresh_from_db()
        cmd2.refresh_from_db()
        cmd3.refresh_from_db()
        self.assertEqual(self.workflow.last_delta, cmd3)
        self.assertIsNone(cmd3.next_delta)
        self.assertEqual(cmd3.prev_delta, cmd2)
        self.assertEqual(cmd2.next_delta, cmd3)
        self.assertEqual(cmd2.prev_delta, cmd1)
        self.assertEqual(cmd1.next_delta, cmd2)
        self.assertIsNone(cmd1.prev_delta)

        # We should be able to go all the way back
        async_to_sync(cmd3.backward)()
        self.assertWfModuleVersions([v2, v2, v3])
        async_to_sync(cmd2.backward)()
        self.assertWfModuleVersions([v2, v2])
        async_to_sync(cmd1.backward)()
        self.assertWfModuleVersions([v1])
        self.assertEqual(list(all_modules), [wfm1])

    # Delete module, then undo, redo
    def test_delete_module(self):
        # beginning state: one WfModule
        v1 = self.v1
        all_modules = self.tab.live_wf_modules
        self.assertEqual(all_modules.count(), 1)
        wfm1 = all_modules.create(module_version=self.module_version, order=0,
                                  last_relevant_delta_id=v1)
        wfm2 = all_modules.create(module_version=self.module_version, order=1,
                                  last_relevant_delta_id=v1)
        wfm3 = all_modules.create(module_version=self.module_version, order=2,
                                  last_relevant_delta_id=v1)
        self.assertWfModuleVersions([v1, v1, v1])

        # Delete it. Yeah, you better run.
        cmd = async_to_sync(DeleteModuleCommand.create)(wfm2)
        v2 = cmd.id
        self.assertWfModuleVersions([v1, v2])

        # undo
        async_to_sync(cmd.backward)()
        self.assertWfModuleVersions([v1, v1, v1])

    def test_delete_only_selected(self):
        """Deleting a module selects the previous one, server-side."""
        # beginning state: one WfModule
        v1 = self.v1
        wfm1 = self.tab.live_wf_modules.create(
            module_version=self.module_version,
            order=0,
            last_relevant_delta_id=v1,
        )
        wfm2 = self.tab.live_wf_modules.create(
            module_version=self.module_version,
            order=0,
            last_relevant_delta_id=v1,
        )

        self.tab.selected_wf_module_position = 1
        self.tab.save(update_fields=['selected_wf_module_position'])

        cmd = async_to_sync(DeleteModuleCommand.create)(wfm2)

        # test pre-refresh (in-memory) and post-refresh (in-database)
        self.assertEqual(self.tab.selected_wf_module_position, 0)
        self.tab.refresh_from_db()
        self.assertEqual(self.tab.selected_wf_module_position, 0)

        async_to_sync(cmd.backward)()  # don't crash

    def test_delete_only_selected(self):
        """Deleting the only module sets selection to None."""
        # beginning state: one WfModule
        v1 = self.v1
        wfm1 = self.tab.live_wf_modules.create(
            module_version=self.module_version,
            order=0,
            last_relevant_delta_id=v1
        )

        self.tab.selected_wf_module_position = 0
        self.tab.save(update_fields=['selected_wf_module_position'])

        cmd = async_to_sync(DeleteModuleCommand.create)(existing_module)

        self.assertIsNone(self.tab.selected_wf_module_position)  # pre-refresh
        self.tab.refresh_from_db()
        self.assertIsNone(self.tab.selected_wf_module_position)  # post-refresh

        async_to_sync(cmd.backward)()  # don't crash

    def test_undo_add_only_selected(self):
        """Undoing the only add sets selection to None."""
        cmd = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                     self.module_version,
                                                     0, {})

        self.tab.selected_wf_module_position = 0
        self.tab.save(update_fields=['selected_wf_module_position'])

        self.assertIsNone(self.tab.selected_wf_module_position)  # pre-refresh
        self.tab.refresh_from_db()
        self.assertIsNone(self.tab.selected_wf_module_position)  # post-refresh

        async_to_sync(cmd.backward)()  # don't crash

    # ensure that adding a module, selecting it, then undo add, prevents
    # dangling selected_wf_module (basically the AddModule equivalent of
    # test_delete_selected)
    def test_undo_add_selected(self):
        """Undoing an add sets selection."""
        self.tab.wf_modules.create(module_version=self.module_version, order=0,
                                   last_relevant_delta_id=self.v1)
        cmd = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                     self.module_version,
                                                     1, {})

        self.tab.selected_wf_module_position = 1
        self.tab.save(update_fields=['selected_wf_module_position'])

        self.assertIsNone(self.tab.selected_wf_module_position)  # pre-refresh
        self.tab.refresh_from_db()
        self.assertIsNone(self.tab.selected_wf_module_position)  # post-refresh

        async_to_sync(cmd.backward)()  # don't crash

    # We had a bug where add then delete caused an error when deleting
    # workflow, since both commands tried to delete the WfModule
    def test_add_delete(self):
        cmda = async_to_sync(AddModuleCommand.create)(self.workflow, self.tab,
                                                      self.module_version,
                                                      0, {})
        async_to_sync(DeleteModuleCommand.create)(cmda.wf_module)
        self.workflow.delete()  # don't crash

    def test_change_data_version(self):
        wfm = self.tab.wf_modules.create(
            module_version=self.module_version,
            order=0,
            last_relevant_delta_id=self.v1
        )

        # Create two data versions, use the second
        firstver = wfm.store_fetched_table(pd.DataFrame({'A': [1]}))
        secondver = wfm.store_fetched_table(pd.DataFrame({'B': [2]}))

        wfm.set_fetched_data_version(secondver)

        v1 = self.v1

        # Change back to first version
        cmd = async_to_sync(ChangeDataVersionCommand.create)(wfm, firstver)
        v2 = cmd.id
        self.assertEqual(wfm.get_fetched_data_version(), firstver)

        self.assertWfModuleVersions([v2])

        # undo
        async_to_sync(cmd.backward)()
        self.assertWfModuleVersions([v1])
        self.assertEqual(wfm.get_fetched_data_version(), secondver)

        # redo
        async_to_sync(cmd.forward)()
        self.assertWfModuleVersions([v2])
        self.assertEqual(self.wfm.get_fetched_data_version(), firstver)

    @patch('server.rabbitmq.queue_render')
    def test_change_version_queue_render_if_notifying(self, queue_render):
        queue_render.return_value = future_none

        df1 = pd.DataFrame({'A': [1]})
        df2 = pd.DataFrame({'B': [2]})
        date1 = self.wfm.store_fetched_table(df1)
        date2 = self.wfm.store_fetched_table(df2)

        self.wfm.notifications = True
        self.wfm.set_fetched_data_version(date1)
        self.wfm.save()

        delta = async_to_sync(ChangeDataVersionCommand.create)(self.wfm, date2)

        queue_render.assert_called_with(self.wfm.workflow_id, delta.id)

    @patch('server.websockets.queue_render_if_listening')
    @patch('server.rabbitmq.queue_render')
    def test_change_version_queue_render_if_listening_and_no_notification(
        self,
        queue_render,
        queue_render_if_listening
    ):
        queue_render_if_listening.return_value = future_none

        df1 = pd.DataFrame({'A': [1]})
        df2 = pd.DataFrame({'B': [2]})
        date1 = self.wfm.store_fetched_table(df1)
        date2 = self.wfm.store_fetched_table(df2)

        self.wfm.notifications = False
        self.wfm.set_fetched_data_version(date1)
        self.wfm.save()

        delta = async_to_sync(ChangeDataVersionCommand.create)(self.wfm, date2)

        queue_render.assert_not_called()
        queue_render_if_listening.assert_called_with(self.wfm.workflow_id,
                                                     delta.id)

    def test_change_notes(self):
        wfm = self.tab.wf_modules.create(
            module_version=self.module_version,
            order=0,
            last_relevant_delta_id=self.v1,
            notes='note1'
        )

        # do
        cmd = async_to_sync(ChangeWfModuleNotesCommand.create)(wfm, 'note2')
        self.assertEqual(wfm.notes, 'note2')
        wfm.refresh_from_db()
        self.assertEqual(wfm.notes, 'note2')

        # undo
        async_to_sync(cmd.backward)()
        self.assertEqual(wfm.notes, 'note1')
        wfm.refresh_from_db()
        self.assertEqual(wfm.notes, 'note1')

        # redo
        async_to_sync(cmd.forward)()
        self.assertEqual(wfm.notes, 'note2')
        wfm.refresh_from_db()
        self.assertEqual(wfm.notes, 'note2')

    def test_change_parameters(self):
        # Setup: workflow with loadurl module
        #
        # loadurl is a good choice because it has three parameters, two of
        # which are useful.
        module = Module.objects.create(name='loadurl', id_name='loadurl',
                                       dispatch='loadurl')
        module_version = ModuleVersion.objects.create(
            source_version_hash='1.0',
            module=module
        )
        module_version.parameter_specs.create(id_name='url', type='string',
                                              order=0, def_value='')
        module_version.parameter_specs.create(id_name='has_header',
                                              type='checkbox', order=1,
                                              def_value='')
        module_version.parameter_specs.create(id_name='version_select',
                                              type='custom', order=2,
                                              def_value='')
        wf_module = self.tab.wf_modules.create(
            module_version=module_version,
            order=0,
            last_relevant_delta_it=self.v1,
        )
        # Set original parameters
        wf_module.create_parametervals({
            'url': 'http://example.org',
            'has_header': True,
        })

        params1 = wf_module.get_params().to_painful_dict(pd.DataFrame())

        # Create and apply delta. It should change params.
        cmd = async_to_sync(ChangeParametersCommand.create)(
            workflow=workflow,
            wf_module=wf_module,
            new_values={
                'url': 'http://example.com/foo',
                'has_header': False,
            }
        )
        params2 = wf_module.get_params().to_painful_dict(pd.DataFrame())

        self.assertEqual(params2['url'], 'http://example.com/foo')
        self.assertEqual(params2['has_header'], False)
        self.assertEqual(params2['version_select'], params1['version_select'])

        # undo
        async_to_sync(cmd.backward)()
        params3 = wf_module.get_params().to_painful_dict(pd.DataFrame())
        self.assertEqual(params3, params1)

        # redo
        async_to_sync(cmd.forward)()
        params4 = wf_module.get_params().to_painful_dict(pd.DataFrame())
        self.assertEqual(params4, params2)

    def test_change_update_settings(self):
        wf_module = self.tab.wf_modules.create(
            module_version=self.module_version,
            last_relevant_delta_id=self.v1,
            order=0,
            auto_update_data=False,
            next_update=None,
            update_interval=600
        )

        # do
        mydate = timezone.now()
        cmd = async_to_sync(ChangeWfModuleUpdateSettingsCommand.create)(
            wf_module,
            True,
            mydate,
            1000
        )
        self.assertTrue(wf_module.auto_update_data)
        self.assertEqual(wf_module.next_update, mydate)
        self.assertEqual(wf_module.update_interval, 1000)
        wf_module.refresh_from_db()
        self.assertTrue(wf_module.auto_update_data)
        self.assertEqual(wf_module.next_update, mydate)
        self.assertEqual(wf_module.update_interval, 1000)

        # undo
        async_to_sync(cmd.backward)()
        self.assertFalse(wf_module.auto_update_data)
        self.assertEqual(wf_module.next_update, None)
        self.assertEqual(wf_module.update_interval, 600)
        wf_module.refresh_from_db()
        self.assertFalse(wf_module.auto_update_data)
        self.assertEqual(wf_module.next_update, None)
        self.assertEqual(wf_module.update_interval, 600)

        # redo
        async_to_sync(cmd.forward)()
        self.assertTrue(wf_module.auto_update_data)
        self.assertEqual(wf_module.next_update, mydate)
        self.assertEqual(wf_module.update_interval, 1000)
        wf_module.refresh_from_db()
        self.assertTrue(wf_module.auto_update_data)
        self.assertEqual(wf_module.next_update, mydate)
        self.assertEqual(wf_module.update_interval, 1000)

    def test_reorder_modules(self):
        all_modules = self.tab.live_wf_modules
        v1 = self.v1

        wfm1 = all_modules.create(module_version=self.module_version,
                                  last_relevant_delta_id=v1, order=0)
        wfm2 = all_modules.create(module_version=self.module_version,
                                  last_relevant_delta_id=v1, order=1)
        wfm3 = all_modules.create(module_version=self.module_version,
                                  last_relevant_delta_id=v1, order=2)

        cmd = async_to_sync(ReorderModulesCommand.create)(
            workflow=self.workflow,
            tab=self.tab,
            wf_module_ids=[wfm1.id, wfm3.id, wfm2.id]
        )
        v2 = cmd.id
        self.assertWfModuleVersions([v1, v2, v2])
        wfm2.refresh_from_db()
        wfm3.refresh_from_db()
        self.assertEqual(list(all_modules), [wfm1, wfm3, wfm2])

        # undo
        async_to_sync(cmd.backward)()
        self.assertWfModuleVersions([v1, v1, v1])
        wfm2.refresh_from_db()
        wfm3.refresh_from_db()
        self.assertEqual(list(all_modules), [wfm1, wfm2, wfm3])

        # redo
        async_to_sync(cmd.forward)()
        self.assertWfModuleVersions([v1, v2, v2])
        wfm2.refresh_from_db()
        wfm3.refresh_from_db()
        self.assertEqual(list(all_modules), [wfm1, wfm3, wfm2])

    def test_reorder_modules_reject_other_tabs(self):
        """
        User cannot game the system: only one tab is allowed.

        (A user should not be able to affect WfModules outside of his/her
        workflow. There's nothing in the architecture that could lead us there,
        but let's be absolutely sure by testing.)
        """
        all_modules = self.tab.live_wf_modules
        wfm1 = all_modules.create(module_version=self.module_version,
                                  last_relevant_delta_id=v1, order=0)
        wfm2 = all_modules.create(module_version=self.module_version,
                                  last_relevant_delta_id=v1, order=1)

        tab2 = self.workflow.tabs.create(position=1)
        wfm3 = tab2.wf_modules.create(module_version=self.module_version,
                                      last_relevant_delta_id=v1, order=2)

        cmd = async_to_sync(ReorderModulesCommand.create)(
            workflow=self.workflow,
            tab=self.tab,
            wf_module_ids=[wfm1.id, wfm3.id, wfm2.id]
        )
        self.assertIsNone(cmd)
        self.assertWfModuleVersions([self.v1, self.v1])
