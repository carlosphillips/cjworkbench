// Drop-down menu at upper right of each module in a workflow

import React from 'react'
import PropTypes from 'prop-types'
import UncontrolledDropdown from 'reactstrap/lib/UncontrolledDropdown'
import DropdownToggle from 'reactstrap/lib/DropdownToggle'
import DropdownMenu from 'reactstrap/lib/DropdownMenu'
import DropdownItem from 'reactstrap/lib/DropdownItem'
import Portal from 'reactstrap/lib/Portal'
import ExportModal from '../ExportModal'


export default class WfModuleContextMenu extends React.Component {
  constructor(props) {
    super(props);
    this.deleteOption = this.deleteOption.bind(this);
    this.toggleExportModal = this.toggleExportModal.bind(this);

    this.state = {
      exportModalOpen: false,
    };
  }

  deleteOption() {
    this.props.removeModule();
  }

  toggleExportModal() {
    this.setState({ exportModalOpen: !this.state.exportModalOpen });
  }

  ignore = (ev) => {
    ev.stopPropagation()
  }

  render() {

    return (
       <UncontrolledDropdown onClick={this.ignore}>
        <DropdownToggle title="more" className='context-button'>
          <i className='context-button--icon icon-more'></i>
        </DropdownToggle>
        <Portal>
          <DropdownMenu persist position='left'>
            <DropdownItem key={1} onClick={this.toggleExportModal} className='test-export-button'>
              <i className='icon-download'></i>
              <span>Export data</span>
              <ExportModal open={this.state.exportModalOpen} wfModuleId={this.props.id} onClose={this.toggleExportModal}/>
            </DropdownItem>

            <DropdownItem key={2} onClick={this.deleteOption} className='test-delete-button'>
              <i className='icon-bin'></i>
              <span>Delete</span>
            </DropdownItem>
          </DropdownMenu>
        </Portal>
       </UncontrolledDropdown>
    );
  }
}

WfModuleContextMenu.propTypes = {
  removeModule: PropTypes.func,
  id:           PropTypes.number,
};
