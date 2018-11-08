# -*- coding: utf-8 -*-
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0139_auto_20181102_2219'),
    ]

    operations = [
        migrations.RunSQL(["""
            INSERT INTO server_tab
               (workflow_id, position, name, selected_wf_module_position)
            SELECT id, 0, 'Tab 1', NULL
            FROM server_workflow;

            UPDATE server_wfmodule
            SET tab_id = (
                SELECT tab.id
                FROM server_tab tab
                WHERE tab.workflow_id = server_wfmodule.workflow_id
                AND tab.position = 0
            )
        """]),
    ]
