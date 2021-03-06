import React from 'react'
import PropTypes from 'prop-types'


const MimeTypesString = [
  'application/vnd.google-apps.spreadsheet',
  'text/csv',
  'text/tab-separated-values',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
].join(',')


class PickerFactory {
  constructor() {
    this.picker = null
  }

  /**
   * Opens a singleton Picker, calling onPick and onCancel.
   *
   * Calls onPick({ id, name, url, mimeType, type }) or onCancel()
   * and then destroys the picker.
   *
   * Example values:
   *
   * id: `"0BS58NKO6eAjKchvRVkhpVYZFL1lSXRaa3VIbFczR0pZX4dJN"`
   * name: `"My filename"`
   * mimeType: `"application/vnd.google-apps.spreadsheet"`, `"text/csv"`
   * url: `"https://docs.google.com/.../edit?usp=drive_web"`
   *
   * If the singleton Picker is already open, this is a no-op.
   */
  open(accessToken, onPick, onCancel) {
    if (this.picker !== null) return

    const onEvent = (data) => {
      switch (data.action) {
        case 'loaded':
          break

        case 'picked':
          const { id, name, url, mimeType } = data.docs[0]
          onPick({ id, name, url, mimeType })
          this.close()
          break

        case 'cancel':
          onCancel()
          this.close()
          break

        default:
          console.log('Unhandled picker event', data)
      }
    }

    const view = new google.picker.DocsView(google.picker.ViewId.DOCS)
      .setIncludeFolders(true)
      .setMimeTypes(MimeTypesString)

    this.picker = new google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(accessToken)
      .setCallback(onEvent)
      .build()

    this.picker.setVisible(true)
  }

  /**
   * Close the singleton picker, if it is open.
   */
  close() {
    if (this.picker !== null) {
      this.picker.dispose()
      this.picker = null
    }
  }
}


let googleApiLoadedPromise = null
/**
 * Load Google APIs globally (if they haven't been loaded already); return
 * a Promise[PickerFactory] that will resolve once the Google APIs are loaded.
 *
 * This returns a new PickerFactory each call, but it only loads the global
 * `google` and `gapi` variables once.
 */
async function loadDefaultPickerFactory() {
  if (googleApiLoadedPromise === null) {
    googleApiLoadedPromise = new Promise((resolve, reject) => {
      const callbackName = `GoogleFileSelect_onload_${String(Math.random()).slice(2, 10)}`
      window[callbackName] = function() {
        delete window[callbackName]
        gapi.load('picker', function() {
          resolve()
        })
      }

      const script = document.createElement('script')
      script.async = true
      script.defer = true
      script.src = `https://apis.google.com/js/api.js?onload=${callbackName}`

      document.querySelector('head').appendChild(script)
      this.script = script
    })
  }

  await googleApiLoadedPromise
  return new PickerFactory()
}


export default class GoogleFileSelect extends React.PureComponent {
  static propTypes = {
    api: PropTypes.shape({
      paramOauthGenerateAccessToken: PropTypes.func.isRequired,
    }).isRequired,
    isReadOnly: PropTypes.bool.isRequired,
    googleCredentialsParamId: PropTypes.number.isRequired,
    googleCredentialsSecretName: PropTypes.string, // when this changes, call api.paramOauthGenerateAccessToken
    fileMetadataJson: PropTypes.string, // may be empty/null
    onChangeJson: PropTypes.func.isRequired, // func("{ id, name, url }") => undefined
    loadPickerFactory: PropTypes.func, // func() => Promise[PickerFactory], default uses Google APIs
  }

  constructor(props) {
    super(props)

    this.state = {
      pickerFactory: null,
      loadingAccessToken: false,
      unauthenticated: false, // true after the server says we're unauthenticated
    }
  }

  /**
   * Return a Promise of an access token or null ("unauthenticated").
   *
   * Manages state: loadingAccessToken and unauthenticated.
   *
   * Access tokens are time-sensitive, so we can't just cache the return value:
   * we need to refresh from time to time. Simplest is to load on demand.
   *
   * Each call returns a new token. Only the most-recent returned token is
   * valid.
   */
  fetchAccessToken() {
    const googleCredentialsSecretName = this.props.googleCredentialsSecretName

    if (googleCredentialsSecretName === null) {
      this.setState({
        loadingAccessToken: false,
        unauthenticated: true,
      })
      return Promise.resolve(null)
    }

    this.setState({
      loadingAccessToken: true,
      unauthenticated: false,
    })

    return this.props.api.paramOauthGenerateAccessToken(this.props.googleCredentialsParamId)
      .then(accessTokenOrNull => {
        if (googleCredentialsSecretName !== this.props.googleCredentialsSecretName) {
          // avoid race: another race is happening
          return null
        }
        if (this._isUnmounted) {
          // avoid race: we're closed
          return null
        }

        this.setState({
          loadingAccessToken: false,
          unauthenticated: accessTokenOrNull === null,
        })
        return accessTokenOrNull
      })
  }

  loadPickerFactory() {
    const loadPickerFactory = this.props.loadPickerFactory || loadDefaultPickerFactory
    loadPickerFactory().then(pf => {
      if (this._isUnmounted) return
      this.setState({ pickerFactory: pf })
    })
  }

  componentDidMount() {
    this.loadPickerFactory()
  }

  componentWillUnmount() {
    if (this.state.pickerFactory) {
      this.state.pickerFactory.close()
      // we leak window.gapi, but that's probably fine
    }

    this._isUnmounted = true
  }

  openPicker = () => {
    const { pickerFactory } = this.state
    this.fetchAccessToken()
      .then(accessTokenOrNull => {
        if (accessTokenOrNull) {
          pickerFactory.open(accessTokenOrNull, this.onPick, this.onCancel)
        }
        // otherwise, we've set this.state.unauthenticated
      })
  }

  onPick = (data) => {
    this.props.onChangeJson(JSON.stringify(data))
  }

  onCancel = () => {
    // do nothing
  }

  render() {
    const { pickerFactory, loadingAccessToken, unauthenticated } = this.state
    const { fileMetadataJson, googleCredentialsSecretName, isReadOnly } = this.props

    const defaultFileName = ''
    const fileMetadata = fileMetadataJson ? JSON.parse(fileMetadataJson) : null
    const fileId = fileMetadata ? (fileMetadata.id || null) : null
    const fileName = fileMetadata ? (fileMetadata.name || defaultFileName) : defaultFileName
    const fileUrl = fileMetadata ? (fileMetadata.url || null) : null

    let button
    if (!isReadOnly) {
      if (loadingAccessToken || !pickerFactory) {
        button = (
          <p className="loading">Loading...</p>
        )
      } else if (unauthenticated) {
        button = (
          <p className="sign-in-error">failure: please reconnect</p>
        )
      } else if (!googleCredentialsSecretName) {
        button = (
          <p className="not-signed-in">(not signed in)</p>
        )
      } else {
        button = (
          <button
            className="change-file action-link"
            onClick={this.openPicker}
            >{ fileId ? 'Change' : 'Choose' }</button>
        )
      }
    }

    return (
      <div className="google-file-select">
        <a className="file-info" title={`Edit in Google Sheets: ${fileName}`} target="_blank" href={fileUrl}>{fileName}</a>
        {button}
      </div>
    )
  }
}
