from integrationtests.utils import LoggedInIntegrationTest
import re

class TestNewWorkflow(LoggedInIntegrationTest):
    def test_new_workflow(self):
        b = self.browser

        b.click_button('Create Workflow')

        # Empty module stack
        b.wait_for_element('.module-stack', wait=True)

        # nav bar
        with b.scope('nav'):
            b.assert_element('button', text='Duplicate')
            b.assert_element('button', text='Share')

            b.click_button('menu')
            b.assert_element('.dropdown-item', text='Import Module')
            b.assert_element('.dropdown-item', text='My Workflows')
            b.assert_element('.dropdown-item', text='Log Out')

        # output pane
        with b.scope('.outputpane-table'):
            b.assert_element('.outputpane-header div', text='ROWS')
            b.assert_element('.outputpane-header div', text='COLUMNS')
