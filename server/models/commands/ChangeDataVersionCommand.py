from django.db import models
from server.models import Delta, WfModule
from .util import ChangesWfModuleOutputs


class ChangeDataVersionCommand(Delta, ChangesWfModuleOutputs):
    wf_module = models.ForeignKey(WfModule, null=True, default=None, blank=True, on_delete=models.SET_DEFAULT)
    old_version = models.DateTimeField('old_version', null=True)    # may not have had a previous version
    new_version = models.DateTimeField('new_version')
    wf_module_delta_ids = ChangesWfModuleOutputs.wf_module_delta_ids

    def forward_impl(self):
        self.wf_module.set_fetched_data_version(self.new_version)
        self.forward_affected_delta_ids()

    def backward_impl(self):
        self.backward_affected_delta_ids()
        self.wf_module.set_fetched_data_version(self.old_version)

    @classmethod
    def amend_create_kwargs(cls, *, wf_module, **kwargs):
        return {
            **kwargs,
            'wf_module': wf_module,
            'old_version': wf_module.get_fetched_data_version(),
            'wf_module_delta_ids': cls.affected_wf_module_delta_ids(wf_module)
        }

    @classmethod
    async def create(cls, wf_module, version):
        delta = await cls.create_impl(
            wf_module=wf_module,
            new_version=version,
            workflow=wf_module.workflow
        )

        return delta

    @property
    def command_description(self):
        return f'Change {self.wf_module.get_module_name()} data version to {self.version}'
