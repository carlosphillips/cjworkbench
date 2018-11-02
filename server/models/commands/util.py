from typing import List
from django.contrib.postgres.fields import ArrayField
from django.core.validators import int_list_validator
from django.db import models
from server.models import WfModule


class ChangesWfModuleOutputs:
    """
    Mixin that tracks wf_module.last_relevant_delta_id on affected WfModules.

    Usage:

        class MyCommand(Delta, ChangesWfModuleOutputs):
            wf_module_delta_ids = ChangesWfModuleOutputs.wf_module_delta_ids

            # override
            @classmethod
            def amend_create_kwargs(cls, *, wf_module, **kwargs):
                # You must store affected_wf_module_delta_ids.
                return {
                    **kwargs,
                    'wf_module': wf_module,
                    'wf_module_delta_ids':
                        cls.affected_wf_module_delta_ids(wf_module),
                }

            def forward_impl(self):
                ...
                # update wf_modules in database and store
                # self._changed_wf_module_delta_ids, for websockets message.
                self.forward_affected_delta_ids()

            def backward_impl(self):
                ...
                # update wf_modules in database and store
                # self._changed_wf_module_delta_ids, for websockets message.
                self.backward_affected_delta_ids()
    """

    wf_module_delta_ids = models.ArrayField(
        models.ArrayField(
            models.IntegerField(),
            size=2
        )
    )
    """
    List of (id, last_relevant_delta_id) for WfModules, pre-`forward()`.
    """

    @classmethod
    def affected_wf_modules(cls, wf_module) -> QuerySet[WfModule]:
        """
        QuerySet of all WfModules that may change as a result of this Delta.
        """
        return wf_module.tab.live_wf_modules.filter(order__gte=wf_module.order)

    @classmethod
    def affected_wf_module_delta_ids(cls, wf_module) -> List[Tuple[int, int]]:
        return cls.affected_wf_modules(wf_module) \
            .values_list('id', 'last_relevant_delta_id')

    def forward_affected_delta_ids(self):
        """
        Write new last_relevant_delta_id to `wf_module` and its dependents.

        As a side-effect, this will save .last_relevant_delta_id on `wf_module`
        and its successors.
        """
        # Calculate "prev" (pre-forward) last_revision_delta_ids, via DB query.
        # We only need to calculate this on first forward().
        if not self.wf_module_delta_ids:
            self.wf_module_delta_ids = self.affected_wf_modules \
                    .values_list('id', 'last_relevant_delta_id'))

        prev_ids = self.wf_module_delta_ids

        # If we have a wf_module in memory, update it.
        if hasattr(self, 'wf_module_id'):
            for wfm_id, delta_id in prev_ids:
                if wfm_id == self.wf_module_id:
                    self.wf_module.last_relevant_delta_id = delta_id

        self.dependent_wf_modules(wf_module)
            .update(last_relevant_delta_id=self.id)

        # for ws_notify()
        self._changed_wf_module_versions = dict(
            (prev_id[0], self.id) for prev_id in prev_ids)
        )

    def backward_affected_delta_ids(self, wf_module):
        """
        Write new last_relevant_delta_id to `wf_module` and its dependents.

        You must call `wf_module.save()` after calling this method. Dependents
        will be saved as a side-effect.
        """
        prev_ids = self.wf_module_delta_ids

        for wfm_id, delta_id in prev_ids:
            if wfm_id == wf_module.id:
                wf_module.last_relevant_delta_id = delta_id

            WfModule.objects.filter(id=wfm_id) \
                .update(last_relevant_delta_id=delta_id)

        # for ws_notify()
        self._changed_wf_module_versions = dict(p for p in prev_ids
                                                if p[0] != wf_module.id)
