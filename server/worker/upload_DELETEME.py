import logging
import msgpack
from typing import Optional, Tuple
from channels.db import database_sync_to_async
from server.models import WfModule, UploadedFile
from server.modules import uploadfile
from server.worker import save
from .util import benchmark


# DELETEME upload shouldn't be a separate step: an uploaded file should just be
# a parameter we handle in render.
# See https://www.pivotaltracker.com/story/show/161509317.


logger = logging.getLogger(__name__)


@database_sync_to_async
def load_wf_module_and_uploaded_file(
    wf_module_id: int,
    uploaded_file_id: int
) -> Optional[Tuple[WfModule, UploadedFile]]:
    try:
        wf_module = WfModule.objects.get(id=wf_module_id)
    except WfModule.DoesNotExist:
        logger.info('Skipping upload_DELETEME of deleted WfModule %d',
                    wf_module_id)
        return None

    try:
        uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
    except WfModule.DoesNotExist:
        logger.info('Skipping upload_DELETEME of deleted UploadedFile %d',
                    uploaded_file_id)
        return None

    return (wf_module, uploaded_file)


async def upload_DELETEME(*, wf_module_id: int, uploaded_file_id: int) -> None:
    """
    DELETEME: see https://www.pivotaltracker.com/story/show/161509317
    """
    data = await load_wf_module_and_uploaded_file(wf_module_id,
                                                  uploaded_file_id)
    if not data:
        return

    wf_module, uploaded_file = data

    # exceptions caught elsewhere
    task = uploadfile.parse_uploaded_file(uploaded_file)
    result = await benchmark(logger, task, 'parse_uploaded_file(%d, %d, %d)',
                             wf_module.workflow_id, wf_module_id,
                             uploaded_file_id)

    await save.save_result_if_changed(wf_module, result,
                                      stored_object_json=[{
                                          'uuid': uploaded_file.uuid,
                                          'name': uploaded_file.name,
                                      }])


async def handle_upload_DELETEME(message):
    """
    DELETEME: see https://www.pivotaltracker.com/story/show/161509317
    """
    with message.process():
        kwargs = msgpack.unpackb(message.body, raw=False)
        try:
            await upload_DELETEME(**kwargs)
        except:
            logger.exception('Error during fetch')
