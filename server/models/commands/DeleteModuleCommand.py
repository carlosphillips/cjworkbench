import logging
from django.db import models
from django.db.models import F
from server.models import Delta, WfModule
from .util import ChangesWfModuleOutputs


logger = logging.getLogger(__name__)


class DeleteModuleCommand(Delta, ChangesWfModuleOutputs):
    """
    Remove `wf_module` from its Workflow.

    Our logic is to "soft-delete": set `wf_module.is_deleted=True`. Most facets
    of Workbench's API should pretend a soft-deleted WfModule does not exist.
    """

    wf_module = models.ForeignKey(WfModule, on_delete=models.PROTECT)
    wf_module_delta_ids = ChangesWfModuleOutputs.wf_module_delta_ids

    @classmethod
    def affected_wf_modules(self, wf_module):
        # Delete doesn't affect the output of wf_module itself: only its
        # dependents.
        return super().affected_wf_modules(wf_module) \
                .exclude(id=wf_module.id)

    def forward_impl(self):
        self.wf_module.is_deleted = True
        self.wf_module.save(update_fields=['is_deleted'])

        tab = self.wf_module.tab

        # Decrement every other module's position, to fill the gap we made
        tab.live_wf_modules \
                .filter(order__gt=self.wf_module.order) \
                .update(order=F('order') - 1)

        # Mark the previous module in the stack as selected
        selected = max(0, self.wf_module.order - 1)
        if tab.live_wf_modules.exists():
            tab.selected_wf_module_position = selected
        else:
            tab.selected_wf_module_position = None
        tab.save(update_fields=['selected_wf_module'])

        self.forward_affected_delta_ids()

    def backward_impl(self):
        self.backward_affected_delta_ids()

        tab = self.wf_module.tab

        # Move subsequent modules over to make way for this one.
        tab.live_wf_modules \
                .filter(order__gte=self.wf_module.order) \
                .update(order=F('order') + 1)

        self.wf_module.is_deleted = False
        self.wf_module.save(update_fields=['is_deleted'])

        # Don't set tab.selected_wf_module_position. We can't restore it, and
        # this operation can't invalidate any value that was there previously.

    @classmethod
    def amend_create_kwargs(cls, *, wf_module, **kwargs):
        # If wf_module is already deleted, ignore this Delta.
        #
        # This works around a race: what if two users delete the same WfModule
        # at the same time? We want only one Delta to be created.
        # amend_create_kwargs() is called within workflow.cooperative_lock(),
        # so we can check without racing whether wf_module is already deleted.
        wf_module.refresh_from_db()
        if wf_module.is_deleted:
            return None

        return {
            **kwargs,
            'wf_module': wf_module,
            'wf_module_delta_ids': cls.affected_wf_module_delta_ids(wf_module),
        }

    @classmethod
    async def create(cls, wf_module):
        # Accept positional arguments
        return await cls.create_impl(workflow=wf_module.workflow,
                                     wf_module=wf_module)

    @property
    def command_description(self):
        return f'Delete WfModule {self.wf_module}'


# Don't hard-delete the WfModule in post_delete.
#
# Normally, we get AddModuleCommand, maybe some ChangeParametersCommands, and
# then a DeleteModuleCommand. If we're deleting, we _should_ delete in reverse
# order -- so the post_delete hook should be on AddModuleCommand alone.
#
# "But I have an edge case," you say. Maybe we're deleting out of order -- in
# which case, DeleteModuleCommand should delete the WfModule. But what about
# all the other out-of-order deletions we can get? If we delete the garbage
# WfModule in DeleteModuleCommand's post_delete because we expect bulk-deleters
# to call us incorrectly, then we also need to delete the garbage WfModule in
# any _other_ command -- e.g., ChangeParametersCommand -- in case _they're_
# being deleted out of order. It's complicated to handle out-of-order deletion.
# Let's simplify and declare here, once and for all: out-of-order deletion is
# an error. Delete commands in the reverse order you've created them.
#
# There. Now we don't need (or want) to hard-delete a WfModule here.
