from django.core.validators import int_list_validator
from django.db import models
from server.models import WfModule


class ChangesWfModuleOutputs:
    # List of wf_module.last_relevant_delta_id from _before_ .forward() was
    # called, for *this* wf_module and the ones *after* it.
    dependent_wf_module_last_delta_ids = models.CharField(
        validators=[int_list_validator],
        blank=True,
        max_length=99999
    )

    def save_wf_module_versions_in_memory_for_ws_notify(self, wf_module):
        """Save data, specifically for .ws_notify()."""
        self._changed_wf_module_versions = dict(
            wf_module.dependent_wf_modules().values_list(
                'id',
                'last_relevant_delta_id'
            )
        )

    def forward_dependent_wf_module_versions(self, wf_module):
        """
        Write new last_relevant_delta_id to `wf_module` and its dependents.

        As a side-effect, this will save .last_relevant_delta_id on `wf_module`
        and its successors.
        """
        # Calculate "old" (pre-forward) last_revision_delta_ids, via DB query
        old_ids = [wf_module.last_relevant_delta_id] + list(
            wf_module.dependent_wf_modules().values_list(
                'last_relevant_delta_id',
                flat=True
            )
        )
        # Save them here -- we're about to overwrite them
        self.dependent_wf_module_last_delta_ids = ','.join(map(str, old_ids))

        # Overwrite them, for this one and previous ones
        wf_module.last_relevant_delta_id = self.id
        wf_module.save(update_fields=['last_relevant_delta_id'])
        wf_module.dependent_wf_modules() \
            .update(last_relevant_delta_id=self.id)

        self.save_wf_module_versions_in_memory_for_ws_notify(wf_module)

    def backward_dependent_wf_module_versions(self, wf_module):
        """
        Write new last_relevant_delta_id to `wf_module` and its dependents.

        You must call `wf_module.save()` after calling this method. Dependents
        will be saved as a side-effect.
        """
        old_ids = [int(i) for i in
                   self.dependent_wf_module_last_delta_ids.split(',') if i]

        if not old_ids:
            # This is an old Delta: it does not know the last relevant delta
            # IDs. Set all IDs to an over-estimate.
            wf_module.last_relevant_delta_id = self.prev_delta_id or 0
            wf_module.dependent_wf_modules() \
                .update(last_relevant_delta_id=self.prev_delta_id or 0)

            self.save_wf_module_versions_in_memory_for_ws_notify(wf_module)
            return

        wf_module.last_relevant_delta_id = old_ids[0] or 0

        dependent_ids = \
            wf_module.dependent_wf_modules().values_list('id', flat=True)
        for wfm_id, maybe_delta_id in zip(dependent_ids, old_ids[1:]):
            if not wfm_id:
                raise ValueError('More delta IDs than WfModules')
            delta_id = maybe_delta_id or 0
            WfModule.objects.filter(id=wfm_id) \
                .update(last_relevant_delta_id=delta_id)

        self.save_wf_module_versions_in_memory_for_ws_notify(wf_module)
