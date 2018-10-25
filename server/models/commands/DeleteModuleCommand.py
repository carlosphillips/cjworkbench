import logging
from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver
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

    selected_wf_module = models.IntegerField(null=True, blank=True)

    dependent_wf_module_last_delta_ids = \
        ChangesWfModuleOutputs.dependent_wf_module_last_delta_ids

    def forward_impl(self):
        self.wf_module.deleted = True
        self.wf_module.save(update_fields=['deleted'])

        # Decrement every other module's position, to fill the gap we made
        self.workflow.wf_modules \
                .filter(order__gt=self.wf_module.order) \
                .update(order=F('order') - 1)

        # Set new delta IDs on subsequent modules.
        #
        # self.wf_module's last_relevant_delta_it doesn't change: only
        # _subsequent_ modules change.
        try:
            next_wf_module = self.workflow.wf_modules.get(
                order=self.wf_module.order
            )
            self.forward_dependent_wf_module_versions(next_wf_module)
        except WfModule.DoesNotExist:
            self._changed_wf_module_versions = dict()

        # If we are deleting the selected module, then set the previous module
        # in stack as selected (behavior same as in workflow-reducer.js)
        selected = self.workflow.selected_wf_module
        if selected is not None and selected >= self.wf_module.order:
            selected -= 1
            if selected >= 0:
                self.workflow.selected_wf_module = selected
            else:
                self.workflow.selected_wf_module = None
            self.workflow.save(update_fields=['selected_wf_module'])

    def backward_impl(self):
        self.wf_module.deleted = False
        self.wf_module.save(update_fields=['deleted'])

        # Move subsequent modules over to make way for this one.
        self.workflow.wf_modules \
                .filter(order__ge=self.wf_module.order) \
                .update(order=F('order') + 1)

        # Set new delta IDs on subsequent modules.
        #
        # self.wf_module's last_relevant_delta_it doesn't change: only
        # _subsequent_ modules change.
        try:
            next_wf_module = self.workflow.wf_modules.get(
                order=self.wf_module.order + 1
            )
            self.forward_dependent_wf_module_versions(next_wf_module)
        except WfModule.DoesNotExist:
            self._changed_wf_module_versions = dict()

        # [adamhooper, 2018-06-19] I don't think there's any hope we can
        # actually restore selected_wf_module correctly, because sometimes we
        # update it without a command. But I think focusing the restored module
        # is something a user could expect.
        self.workflow.selected_wf_module = self.selected_wf_module
        self.workflow.save(update_fields=['selected_wf_module'])

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
            'selected_wf_module': workflow.selected_wf_module,
        }

    @classmethod
    async def create(cls, wf_module):
        return await cls.create_impl(
            workflow=wf_module.workflow,
            wf_module=wf_module,
        )

    @property
    def command_description(self):
        return f'Delete WfModule {self.wf_module}'

# When we are deleted, hard-delete the module if applicable
@receiver(post_delete, sender=DeleteModuleCommand,
          dispatch_uid='deletemodulecommand')
def deletemodulecommand_delete_callback(sender, instance, **kwargs):
    wf_module = instance.wf_module

    if wf_module and wf_module.is_deleted:
        try:
            wf_module.delete()
        except:
            logger.exception('Error hard-deleting WfModule')
