import logging
from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver
from server.models import Delta, WfModule
from .util import ChangesWfModuleOutputs


logger = logging.getLogger(__name__)

class AddModuleCommand(Delta, ChangesWfModuleOutputs):
    """
    Create a `WfModule` and insert it into the Workflow.

    Our "backwards()" logic is to "soft-delete": set
    `wfmodule.is_deleted=True`. Most facets of Workbench's API should pretend a
    soft-deleted WfModules does not exist.
    """

    wf_module = models.ForeignKey(WfModule, on_delete=models.PROTECT)
    wf_module_delta_ids = ChangesWfModuleOutputs.wf_module_delta_ids

    def forward_impl(self):
        # Both before and after forward()/backward(), we want
        # `self.wf_module.last_relevant_delta_id == self.id`. So we don't need
        # to edit it ... _except_ during creation. During creation, we INSERT
        # the WfModule before INSERTing the Delta, so we can't give it the
        # Delta ID. Set it here.
        if not self.wf_module.last_relevant_delta_id:
            self.wf_module.last_relevant_delta_id = self.id
            self.wf_module.save(update_fields=['last_relevant_delta_id'])

        # Move subsequent modules over to make way for this one.
        self.wf_module.tab.live_wf_modules \
            .filter(order__gte=self.wf_module.order) \
            .exclude(id=self.wf_module_id) \
            .update(order=F('order') + 1)

        self.wf_module.is_deleted = False
        self.wf_module.save(update_fields=['is_deleted'])

        self.forward_affected_delta_ids()

    def backward_impl(self):
        self.backward_affected_delta_ids()

        self.wf_module.is_deleted = True
        self.wf_module.save(update_fields=['is_deleted'])

        tab = self.wf_module.tab

        # Move subsequent modules back to fill the gap created by deleting
        tab.live_wf_modules \
            .filter(order__gt=self.wf_module.order) \
            .exclude(id=self.wf_module_id) \
            .update(order=F('order') - 1)

        # Prevent tab.selected_wf_module_position from becoming invalid
        #
        # We can't make this exactly what the user has selected -- that's hard,
        # and it isn't worth the effort. But we _can_ make sure it's valid.
        n_modules = tab.live_wf_modules.count()
        if (
            tab.selected_wf_module_position is None
            or tab.selected_wf_module_position >= n_modules
        ):
            if n_modules == 0:
                tab.selected_wf_module_position = None
            else:
                tab.selected_wf_module_position = n_modules - 1
            tab.save(update_fields=['selected_wf_module_position'])

    @classmethod
    def amend_create_kwargs(cls, *, tab, module_version, order, param_values):
        # When we create wf_module, it's deleted. We'll revert to deleted when
        # we undo: that way IDs further ahead in the delta chain will be able
        # to refer to self.wf_module_id.
        wf_module = tab.wf_modules.create(
            module_version=module_version,
            order=order,
            is_deleted=True
        )
        wf_module.create_parametervals(param_values)

        return {
            **kwargs,
            'wf_module': wf_module,

            # affected_wf_module_delta_ids doesn't include `self.wf_module`,
            # because `self.wf_module.is_deleted==True`. That's what we want:
            # self.wf_module.last_relevant_delta_id does not change during
            # forward() or backward().
            'wf_module_delta_ids': cls.affected_wf_module_delta_ids(wf_module),
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
