from .moduleimpl import ModuleImpl
from .utils import *
from cjworkbench.google_oauth import maybe_authorize
from django.http import JsonResponse, HttpResponseBadRequest
import httplib2
from googleapiclient.discovery import build
from .utils import *
import io
import json
import pandas as pd
from pandas.parser import CParserError
from server.versions import save_fetched_table_if_changed

class GoogleSheets(ModuleImpl):

    @staticmethod
    def get_spreadsheets(request):
        authorized, credential = maybe_authorize(request)

        if not authorized:
            return JsonResponse({'login_url':credential}, status=401)

        http = httplib2.Http()
        http = credential.authorize(http)
        service = build("drive", "v3", http=http)

        files_request = service.files().list(q="mimeType = 'application/vnd.google-apps.spreadsheet'", pageSize=1000)
        files = files_request.execute()
        return JsonResponse(files)

    @staticmethod
    def get_spreadsheet(request, id):
        authorized, credential = maybe_authorize(request)

        if not authorized:
            return credential

        http = httplib2.Http()
        http = credential.authorize(http)
        service = build("drive", "v2", http=http)

        files_request = service.files().export(fileId=id, mimeType="text/csv")
        the_file = files_request.execute()
        return the_file.decode("utf-8")
        #return JsonResponse({'file':the_file.decode("utf-8")})

    @staticmethod
    def render(wf_module, table):
        return wf_module.retrieve_fetched_table()

    @staticmethod
    def event(wfmodule, parameter=None, event=None, request=None, **kwargs):
        if not event:
            file_meta = wfmodule.get_param_raw('fileselect', 'custom')
            file_meta = json.loads(file_meta)
            sheet_id = file_meta['id']

        event_type = event.get('type', False)

        if not event_type:
            return HttpResponseBadRequest()

        if event_type == 'fetchFiles':
            return GoogleSheets.get_spreadsheets(request)

        if event_type == 'fetchFile':
            file_meta = request.data.get('file', False)
            sheet_id = file_meta['id']

        if event_type == 'click':
            file_meta = wfmodule.get_param_raw('fileselect', 'custom')
            file_meta = json.loads(file_meta)
            sheet_id = file_meta['id']

        if sheet_id:
            new_data = GoogleSheets.get_spreadsheet(request, sheet_id)

            try:
                table = pd.read_csv(io.StringIO(new_data))
            except CParserError as e:
                wfmodule.set_error(str(e))
                table = pd.DataFrame([{'result':res.text}])

            save_fetched_table_if_changed(wfmodule, table)
            # change this to no response method
            return JsonResponse({}, status=204)
