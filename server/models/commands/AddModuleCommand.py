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
    order = models.IntegerField()
    # what was selected before we were added?
    selected_wf_module = models.IntegerField(null=True, blank=True)
    dependent_wf_module_last_delta_ids = \
        ChangesWfModuleOutputs.dependent_wf_module_last_delta_ids

    def forward_impl(self):
        # Move subsequent modules over to make way for this one.
        self.workflow.wf_modules \
            .filter(order__ge=self.order) \
            .exclude(id=self.wf_module_id) \
            .update(order=F('order') + 1)

        self.workflow.selected_wf_module = self.selected_wf_module
        self.workflow.save(update_fields=['selected_wf_module'])

        self.wf_module.is_deleted = False
        self.wf_module.save(update_fields=['is_deleted'])

        self.forward_dependent_wf_module_versions(self.wf_module)

    def backward_impl(self):
        self.backward_dependent_wf_module_versions(self.wf_module)

        self.wf_module.is_deleted = True
        self.wf_module.save(update_fields=['is_deleted'])

        # Move subsequent modules back to fill the gap created by deleting
        self.workflow.wf_modules \
            .filter(order__gt=self.order) \
            .exclude(id=self.wf_module_id) \
            .update(order=F('order') - 1)

        # [adamhooper, 2018-06-19] I don't think there's any hope we can
        # actually restore selected_wf_module correctly, because sometimes we
        # update it without a command. But we still need to set
        # workflow.selected_wf_module to a _valid_ integer if the
        # currently-selected module is the one we're deleting now and is also
        # the final wf_module in the list.
        self.workflow.selected_wf_module = self.selected_wf_module
        self.workflow.save(update_fields=['selected_wf_module'])

    @classmethod
    def amend_create_kwargs(cls, *, workflow, module_version, order,
                            is_collapsed, param_values):
        # When we create wf_module, it's deleted. We'll revert to deleted when
        # we undo: that way IDs further ahead in the delta chain will be able
        # to refer to self.wf_module_id.
        wf_module = workflow.wf_modules.create(
            module_version=module_version,
            order=order,
            deleted=True
        )
        wf_module.create_parametervals(param_values)

        return {
            'workflow': workflow,
            'wf_module': wf_module,
            'selected_wf_module': workflow.selected_wf_module,
        }

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
