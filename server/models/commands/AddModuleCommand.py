import logging
from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver
from server.models import Delta, WfModule
from .util import ChangesWfModuleOutputs


logger = logging.getLogger(__name__)

# The only tricky part AddModule is what we do with the module in backward()
# We detach the WfModule from the workflow, but keep it around for possible later forward()
class AddModuleCommand(Delta, ChangesWfModuleOutputs):
    """
    Create a `WfModule` and insert it into the Workflow.

    Our "backwards()" logic is to "soft-delete": set
    `wfmodule.is_deleted=True`. Most facets of Workbench's API should pretend a
    soft-deleted WfModules does not exist.
    """

    wf_module = models.ForeignKey(WfModule, on_delete=models.PROTECT)
    dependent_wf_module_last_delta_ids = \
        ChangesWfModuleOutputs.dependent_wf_module_last_delta_ids

    def forward_impl(self):
        # Both before and after forward()/backward(), we want
        # `self.wf_module.last_relevant_delta_id == self.id`. So we don't need
        # to edit it ... _except_ during creation. During creation, we create
        # the WfModule first before creating the Delta, so we can't give it the
        # Delta's ID. Create it here.
        if not self.wf_module.last_relevant_delta_id:
            self.wf_module.last_relevant_delta_id = self.id
            self.wf_module.save(update_fields=['last_relevant_delta_id'])

        # Move subsequent modules over to make way for this one.
        self.workflow.wf_modules \
            .filter(is_deleted=False) \
            .filter(order__gte=self.wf_module.order) \
            .exclude(id=self.wf_module_id) \
            .update(order=F('order') + 1)

        self.wf_module.is_deleted = False
        self.wf_module.save(update_fields=['is_deleted'])

        self.forward_dependent_wf_module_versions(self.wf_module)

    def backward_impl(self):
        self.backward_dependent_wf_module_versions(self.wf_module)

        self.wf_module.is_deleted = True
        self.wf_module.save(update_fields=['is_deleted'])

        # Move subsequent modules back to fill the gap created by deleting
        self.workflow.wf_modules \
            .filter(is_deleted=False) \
            .filter(order__gt=self.wf_module.order) \
            .exclude(id=self.wf_module_id) \
            .update(order=F('order') - 1)

        # Prevent selected_wf_module from becoming invalid
        #
        # We can't make this exactly what the user has selected -- that's hard,
        # and it isn't worth the effort. But we _can_ make sure it's valid.
        n_modules = self.workflow.wf_modules.filter(is_deleted=False).count()
        if (
            self.workflow.selected_wf_module is None
            or self.workflow.selected_wf_module >= n_modules
        ):
            if n_modules == 0:
                self.workflow.selected_wf_module = None
            else:
                self.workflow.selected_wf_module = n_modules - 1
            self.workflow.save(update_fields=['selected_wf_module'])

    @classmethod
    def amend_create_kwargs(cls, *, workflow, module_version, order,
                            param_values):
        # When we create wf_module, it's deleted. We'll revert to deleted when
        # we undo: that way IDs further ahead in the delta chain will be able
        # to refer to self.wf_module_id.
        wf_module = workflow.wf_modules.create(
            module_version=module_version,
            order=order,
            is_deleted=True
        )
        wf_module.create_parametervals(param_values)

        return {
            'workflow': workflow,
            'wf_module': wf_module,
        }

    @classmethod
    async def create(cls, workflow, module_version, position, param_values):
        # Accept positional arguments
        return await cls.create_impl(workflow=workflow,
                                     module_version=module_version,
                                     order=position,
                                     param_values=param_values)

    @property
    def command_description(self):
        return f'Add WfModule {self.wf_module}'


# When we are deleted, hard-delete the module if applicable
@receiver(post_delete, sender=AddModuleCommand,
          dispatch_uid='addmodulecommand')
def addmodulecommand_delete_callback(sender, instance, **kwargs):
    wf_module = instance.wf_module

    if wf_module and wf_module.is_deleted:
        try:
            wf_module.delete()
        except:
            logger.exception('Error hard-deleting WfModule')
