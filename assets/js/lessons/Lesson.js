import React from 'react'
import PropTypes from 'prop-types'
import LessonFooter from './LessonFooter'
import LessonSection from './LessonSection'
import LessonNav from './LessonNav'
import LessonAnalyticsTracker from './LessonAnalyticsTracker'
import lessonSelector from './lessonSelector'
import { connect } from 'react-redux'
import { LessonHighlightsType } from '../util/LessonHighlight'

export class Lesson extends React.PureComponent {
  static propTypes = {
    header: PropTypes.shape({
      title: PropTypes.string.isRequired,
      html: PropTypes.string.isRequired
    }).isRequired,
    sections: PropTypes.arrayOf(PropTypes.shape({
      title: PropTypes.string.isRequired,
      html: PropTypes.string.isRequired,
      steps: PropTypes.arrayOf(PropTypes.shape({
        html: PropTypes.string.isRequired
      })).isRequired
    })).isRequired,
    footer: PropTypes.shape({
      title: PropTypes.string.isRequired,
      html: PropTypes.string.isRequired
    }).isRequired,

    /*
     * activeSectionIndex, activeStepIndex: the step the user needs to
     * complete next in order to finish the lesson.
     *
     * Two examples illustrate why activeSectionIndex != currentSectionIndex:
     *
     * 1. The first section might contain introductory text and no steps. We want
     *    the user to read it anyway.
     * 2. Once a user has completed all steps in a section, we want to _prompt_
     *    to switch sections -- not navigate automatically.
     */
    activeSectionIndex: PropTypes.number, // or null
    activeStepIndex: PropTypes.number, // or null

    logUserEvent: PropTypes.func.isRequired, // for tracking progress
  }

  state = {
    // The section the user is reading right now (selected via LessonNav)
    currentSectionIndex: 0
  }

  setCurrentSectionIndex = (index) => {
    this.setState({ currentSectionIndex: index })
  }

  trackMaxProgress = (slug, sectionIndex, sectionTitle, stepIndex) => {
    const log = this.props.logUserEvent
    if (sectionIndex === null) {
      log(`Lesson ${slug}: done`, {
        help: 'The user has completed this Lesson'
      })
    } else {
      log(`Lesson ${slug}: section ${sectionIndex + 1}`, {
        help: 'The user has opened this Lesson section and not completed it',
        sectionTitle,
        atStep: stepIndex + 1
      })
    }
  }

  render() {
    const { slug, header, footer, sections, activeSectionIndex, activeStepIndex } = this.props

    const sectionComponents = sections.map((s, i) => {
      return <LessonSection
        key={i}
        index={i}
        isCurrent={this.state.currentSectionIndex === i}
        activeSectionIndex={this.props.activeSectionIndex}
        activeStepIndex={this.props.activeStepIndex}
        {...s}
      />
    })

    return (
      <article className="lesson">
        <LessonAnalyticsTracker
          slug={slug}
          sections={sections}
          activeSectionIndex={activeSectionIndex}
          activeStepIndex={activeStepIndex}
          trackMaxProgress={this.trackMaxProgress}
          />
        <h1>{header.title}</h1>
        <div className="description" dangerouslySetInnerHTML={({__html: header.html})}></div>
        <div className="sections">
          {sectionComponents}
          <LessonFooter
            key='footer'
            isCurrent={this.state.currentSectionIndex === sections.length}
            isFinished={this.props.activeSectionIndex === null}
            {...footer}
          />
        </div>
        <LessonNav
          nSections={sections.length}
          activeSectionIndex={activeSectionIndex}
          currentSectionIndex={this.state.currentSectionIndex}
          setCurrentSectionIndex={this.setCurrentSectionIndex}
          />
      </article>
    )
  }
}

const mapStateToProps = (state) => {
  const { activeSectionIndex, activeStepIndex } = lessonSelector(state)
  return { activeSectionIndex, activeStepIndex }
}

export default connect(mapStateToProps)(Lesson)
