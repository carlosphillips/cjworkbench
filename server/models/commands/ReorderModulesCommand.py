import json
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.dispatch import receiver
from server.models import Delta, Tab, WfModule
from .util import ChangesWfModuleOutputs


class ReorderModulesCommand(Delta, ChangesWfModuleOutputs):
    """Overwrite wf_module.order for all wf_modules in a tab."""

    tab = models.ForeignKey('Tab', on_delete=models.PROTECT)
    prev_order = ArrayField(models.IntegerField())
    next_order = ArrayField(models.IntegerField())
    wf_module_delta_ids = ChangesWfModuleOutputs.wf_module_delta_ids

    def apply_order(self, wf_module_ids):
        wf_modules = dict(self.tab.live_wf_modules.values_list('id', 'order'))

        for position, wf_module_id in enumerate(wf_module_ids):
            cur_position = wf_modules[wf_module_id]
            if cur_position != position:
                WfModule.objects.filter(pk=wf_module_id).update(order=position)

    def forward_impl(self):
        self.apply_order(self.next_order)
        self.forward_affected_delta_ids()

    def backward_impl(self):
        self.apply_order(self.prev_order)
        self.backward_affected_delta_ids()

    @classmethod
    async def amend_create_kwargs(cls, *, tab, wf_module_ids, **kwargs):
        prev_order = list(tab.live_wf_modules.values_list('id', flat=True))
        next_order = wf_module_ids

        if set(prev_order) != set(next_order):
            # This isn't a reordering: the WfModules are different
            return None

        if len(prev_order) != len(next_order):
            # This isn't a reordering: a WfModule appears twice in one list
            return None

        # Calculate affected modules: skip the matching beginnings of both
        # lists, because we know the reordering won't affect them.
        for prev_id, next_id in zip(prev_order, next_order):
            if prev_id != next_id:
                wf_module = tab.live_wf_modules.get(pk=prev_id)
                delta_ids = cls.affected_wf_module_delta_ids(wf_module)


        return {
            **kwargs,
            'tab': tab,
            'prev_order': prev_order,
            'next_order': next_order,
            'wf_module_delta_ids': delta_ids,
        }

    @property
    def command_description(self):
        return f'Reorder modules to {self.next_order}'
