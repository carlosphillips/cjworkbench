import React from 'react'
import PropTypes from 'prop-types'
import Popover from 'reactstrap/lib/Popover'
import PopoverHeader from 'reactstrap/lib/PopoverHeader'
import PopoverBody from 'reactstrap/lib/PopoverBody'

export default class SearchResult extends React.PureComponent {
  static propTypes = {
    isActive: PropTypes.bool.isRequired,
    isLessonHighlight: PropTypes.bool.isRequired,
    id: PropTypes.number.isRequired,
    name: PropTypes.string.isRequired,
    description: PropTypes.string.isRequired,
    icon: PropTypes.string.isRequired,
    onClick: PropTypes.func.isRequired, // func(id) => undefined
    onMouseEnter: PropTypes.func.isRequired, // func(id) => undefined
  }

  liRef = React.createRef()

  onClick = () => {
    this.props.onClick(this.props.id)
  }

  onMouseEnter = () => {
    this.props.onMouseEnter(this.props.id)
  }

  getLiRef = () => {
    // deferred for when Popper asks for it -- not during render, which is too
    // soon.
    return this.liRef.current
  }

  render() {
    const { id, isActive, isLessonHighlight, isMatch, name, icon, description } = this.props

    const elId = `module-search-result-${id}`

    const className = [ 'module-search-result' ]
    if (isLessonHighlight) className.push('lesson-highlight')

    return (
      <li ref={this.liRef} className={className.join(' ')} id={elId} data-module-name={name} onClick={this.onClick} onMouseEnter={this.onMouseEnter}>
        <i className={'icon-' + icon}></i>
        <span className='name'>{name}</span>
        {isActive ? (
          <Popover placement='right' isOpen={isActive} target={this.getLiRef} boundariesElement='window' className='module-search-result'>
            <PopoverHeader>{name}</PopoverHeader>
            <PopoverBody>{description}</PopoverBody>
          </Popover>
        ) : null}
      </li>
    )
  }
}
