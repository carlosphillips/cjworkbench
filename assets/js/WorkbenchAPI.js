// Wraps all API calls. Useful both to centralize and abstract these calls,
// also for dependency injection for testing

import {csrfToken} from './utils'

const apiHeaders = {
  'Accept': 'application/json',
  'Content-Type': 'application/json',
  'X-CSRFToken': csrfToken
}

// All API calls which fetch data return a promise which returns JSON
class WorkbenchAPI {
  // We send at most one data-modification request at a time, to avoid races.
  // this._serializer always resolves to the last-returned fetch result.
  _serializer = Promise.resolve(null)

  /**
   * Returns Promise of JSON on HTTP success (or `null` on HTTP 204 success).
   *
   * The Promise will fail with:
   *
   * * RangeError if the status code is not between 200 and 299.
   * * TypeError if the response Content-Type is not application/json,
   *   or if security checks (like CORS) prevent the fetch.
   * * SyntaxError if the response is invalid JSON.
   */
  _fetch(url, options) {
    const realOptions = Object.assign({ credentials: 'include' }, options || {})

    return this._serializer = this._serializer.catch(() => null)
      .then(() => fetch(url, realOptions))
      .then(res => {
        if (!res.ok) {
          throw new RangeError(`Server responded with non-200 status code ${res.status}`)
        }
        if (res.status === 204) {
          return null // No content
        }
        if (res.headers.get('content-type') && res.headers.get('content-type').toLowerCase().indexOf('application/json') === -1) {
          throw new TypeError("Server response is not JSON", res)
        }
        return res.json()
      })
  }

  _submit(method, url, body, options) {
    const realOptions = Object.assign(
      { method: method, headers: apiHeaders },
      { body: JSON.stringify(body) },
      options || {}
    )
    return this._fetch(url, realOptions)
  }

  _patch(url, body, options) {
    return this._submit('PATCH', url, body, options)
  }

  _put(url, body, options) {
    return this._submit('PUT', url, body, options)
  }

  _post(url, body, options) {
    return this._submit('POST', url, body, options)
  }

  _delete(url, options) {
    return this._submit('delete', url, null, { body: '' })
  }

  listWorkflows() {
    return this._fetch('/api/workflows')
  }

  loadWorkflow(workflowId) {
    return this._fetch(`/api/workflows/${workflowId}`)
  }

  newWorkflow() {
    return this._post('/api/workflows', {})
  }

  deleteWorkflow(workflowId) {
    return this._delete(`/api/workflows/${workflowId}`)
  }

  getAcl (workflowId) {
    return this._fetch(`/api/workflows/${workflowId}/acl`)
      .then(json => {
        // rename can_edit => canEdit
        return json.map(({ email, can_edit }) => ({ email, canEdit: can_edit }))
      })
  }

  updateAclEntry (workflowId, email, canEdit) {
    return this._put(`/api/workflows/${workflowId}/acl/${encodeURIComponent(email)}`, { can_edit: canEdit })
  }

  deleteAclEntry (workflowId, email) {
    return this._delete(`/api/workflows/${workflowId}/acl/${encodeURIComponent(email)}`)
  }

  reorderWfModules(workflowId, tabId, wfModuleIds) {
    return this._patch(`/api/workflows/${workflowId}/tabs/${tabId}`, { wf_module_ids: wfModuleIds })
  }

  addModule(workflowId, tabId, moduleId, index, values={}) {
    return this._post(`/api/workflows/${workflowId}/tabs/${tabId}/modules`, {
      position: index,
      moduleId: moduleId,
      values: values
    })
  }

  deleteModule(workflowId, wfModuleId) {
    return this._delete(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}`)
  }

  setWorkflowPublic(workflowId, isPublic) {
    return this._patch(`/api/workflows/${workflowId}`, { 'public': isPublic })
  }

  setWfModuleParams(workflowId, wfModuleId, params) {
    return this._patch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/params`, { 'values': params })
  }

  render(workflowId, wfModuleId, startRow, endRow) {
    if (!startRow) startRow = 0
    let url = `/api/workflows/${workflowId}/wfmodules/${wfModuleId}/render?startrow=${startRow}`

    if (endRow) {
      url += "endrow=" + endRow;
    }

    return this._fetch(url)
  }

  valueCounts(workflowId, wfModuleId, column) {
    return this._fetch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/value-counts?column=${encodeURIComponent(column)}`)
      .catch(err => {
        if (err instanceof RangeError) {
          return { values: {} }
        } else {
          throw err
        }
      })
      .then(json => json.values)
  }

  output(wfModuleId) {
    return this._fetch(`/api/wfmodules/${wfModuleId}/output`)
  }

  getTile(workflowId, wfModuleId, deltaId, tileRow, tileColumn) {
    return this._fetch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/v${deltaId}/r${tileRow}/c${tileColumn}.json`)
  }

  // All available modules in the system
  getModules() {
    return this._fetch(`/api/modules/`)
  }

  setWfModuleVersion(workflowId, wfModuleId, version) {
    return this._patch(
      `/api/workflows/${workflowId}/wfmodules/${wfModuleId}/dataversions`,
      { selected: version }
    )
  }

  setWfModuleNotes(workflowId, wfModuleId, text) {
    return this._patch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}`, { notes: text })
  }

  setWfModuleCollapsed(workflowId, wfModuleId, isCollapsed) {
    return this._patch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}`, { collapsed: isCollapsed })
  }

  setWfName(workflowId, name) {
    return this._patch(`/api/workflows/${workflowId}`, { name })
  }

  setSelectedWfModule(workflowId, tabId, index) {
    return this._put(`/api/workflows/${workflowId}/selection`, { tabId, wfModulePosition: index })
  }

  updateWfModule(workflowId, wfModuleId, params) {
    return this._patch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/params`, params)
  }

  undo(workflowId) {
    return this._post(`/api/workflows/${workflowId}/undo`, null)
  }

  redo(workflowId) {
    return this._post(`/api/workflows/${workflowId}/redo`, null)
  }

  duplicateWorkflow(workflowId) {
    return this._post(`/api/workflows/${workflowId}/duplicate`, null)
  }

  deleteWfModuleNotifications(workflowId, wfModuleId) {
    return this._delete(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/notifications`)
  }

  importFromGithub(eventData) {
    return this._post(`/api/importfromgithub/`, eventData)
  }

  // This is Bad. You should get a list of serialized data versions on the
  // workflow module instead of a 2-tuple, and there should be a generic
  // data version create/read/update/delete method. As there should be for
  // every object in the database.
  markDataVersionsRead(workflowId, wfModuleId, data_versions) {
    return this._patch(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/dataversion/read`, { versions: data_versions })
  }

  requestFetch(workflowId, wfModuleId) {
    return this._post(`/api/workflows/${workflowId}/wfmodules/${wfModuleId}/fetch`)
  }

  /**
   * Return a String access token, or null.
   */
  paramOauthGenerateAccessToken(paramId) {
    // Unlike other API methods, this one accepts 404 and 403 as valid.
    //
    // The server happens to return text instead of JSON, but the real reason
    // we can't share code is the status codes.
    return fetch(`/api/parameters/${paramId}/oauth_generate_access_token`, {
      method: 'post',
      headers: apiHeaders,
      credentials: 'include',
    })
      .then(res => {
        if (res.status === 404) {
          return null
        } else if (res.status !== 200) {
          console.warn('Server did not generate OAuth token: ', res.text())
          return null
        } else if ((res.headers.get('content-type') || '').toLowerCase().indexOf('text/plain') !== 0) {
          console.warn('Server response is not text/plain', res)
          return null
        } else {
          return res.text() || null
        }
      })
  }

  paramOauthDisconnect(paramId) {
    return this._delete(`/api/parameters/${paramId}/oauth_authorize`)
  }
}

// Singleton API object for global use
const api = new WorkbenchAPI()
export default api
