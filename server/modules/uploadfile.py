from io import BufferedReader
from server.minio import open_for_read, ResponseError
from .moduleimpl import ModuleImpl
from .types import ProcessResult
from .utils import parse_bytesio, turn_header_into_first_row
from server.utils import TempfileBackedReader
from server import versions


_ExtensionMimeTypes = {
    '.xls': 'application/vnd.ms-excel',
    '.xlsx':
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.csv': 'text/csv',
    '.tsv': 'text/tab-separated-values',
    '.json': 'application/json',
    '.txt': 'text/plain'
}


# --- Parse UploadedFile ---
# When files come in, they are stored in temporary UploadedFile objects
# This code parses the file into a table, and stores as a StoredObject

# Read an UploadedFile, parse it, store it as the WfModule's "fetched table"
# Public entrypoint, called by the view
async def parse_uploaded_file(uploaded_file) -> ProcessResult:
    ext = '.' + uploaded_file.name.split('.')[-1]
    mime_type = _ExtensionMimeTypes.get(ext, None)
    if mime_type:
        try:
            with open_for_read(uploaded_file.bucket, uploaded_file.key) as s3:
                with TempfileBackedReader(s3) as tempio:
                    with BufferedReader(tempio) as bufio:
                        result = parse_bytesio(bufio, mime_type, None)
        except ResponseError as err:
            return ProcessResult(error=str(err))
    else:
        return ProcessResult(error=(
            f'Error parsing {uploaded_file.name}: unknown content type'
        ))

    result.truncate_in_place_if_too_big()
    result.sanitize_in_place()

    # don't delete UploadedFile, so that we can reparse later or allow higher
    # row limit or download original, etc.
    return result


class UploadFile(ModuleImpl):
    @staticmethod
    def render(params, table, *, fetch_result, **kwargs):
        if not fetch_result or fetch_result.status == 'error':
            return fetch_result

        table = fetch_result.dataframe
        if not params.get_param_checkbox('has_header'):
            table = turn_header_into_first_row(table)

        return ProcessResult(table, fetch_result.error)
