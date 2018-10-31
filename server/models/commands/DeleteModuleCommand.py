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

    dependent_wf_module_last_delta_ids = \
        ChangesWfModuleOutputs.dependent_wf_module_last_delta_ids

    def forward_impl(self):
        self.wf_module.is_deleted = True
        self.wf_module.save(update_fields=['is_deleted'])

        # Decrement every other module's position, to fill the gap we made
        self.workflow.wf_modules \
                .filter(is_deleted=False) \
                .filter(order__gt=self.wf_module.order) \
                .update(order=F('order') - 1)

        # Set new delta IDs on subsequent modules.
        #
        # self.wf_module's last_relevant_delta_it doesn't change: only
        # _subsequent_ modules change.
        try:
            next_wf_module = self.workflow.wf_modules.get(
                is_deleted=False,
                order=self.wf_module.order
            )
            self.forward_dependent_wf_module_versions(next_wf_module)
        except WfModule.DoesNotExist:
            self._changed_wf_module_versions = dict()

        # Mark the previous module in the stack as selected
        selected = max(0, self.wf_module.order - 1)
        if self.workflow.wf_modules.filter(is_deleted=False).exists():
            self.workflow.selected_wf_module = selected
        else:
            self.workflow.selected_wf_module = None
        self.workflow.save(update_fields=['selected_wf_module'])

    def backward_impl(self):
        # Move subsequent modules over to make way for this one.
        self.workflow.wf_modules \
                .filter(is_deleted=False) \
                .filter(order__gte=self.wf_module.order) \
                .update(order=F('order') + 1)

        self.wf_module.is_deleted = False
        self.wf_module.save(update_fields=['is_deleted'])

        # Set new delta IDs on subsequent modules.
        #
        # self.wf_module's last_relevant_delta_it doesn't change: only
        # _subsequent_ modules change.
        try:
            next_wf_module = self.workflow.wf_modules.get(
                order=self.wf_module.order + 1,
                is_deleted=False
            )
            self.forward_dependent_wf_module_versions(next_wf_module)
        except WfModule.DoesNotExist:
            self._changed_wf_module_versions = dict()

        # Don't set workflow.selected_wf_module. We can't restore it, and we
        # shouldn't bother trying.

    @classmethod
    def amend_create_kwargs(cls, *, workflow, wf_module):
        # If wf_module is already deleted, ignore this Delta.
        #
        # This works around a race: what if two users delete the same WfModule
        # at the same time? We want only one Delta to be created.
        # amend_create_kwargs() is called within workflow.cooperative_lock(),
        # so we can check without racint whether wf_module is already deleted.
        wf_module.refresh_from_db()
        if wf_module.is_deleted:
            return None

        return {
            'workflow': workflow,
            'wf_module': wf_module,
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
