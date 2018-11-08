# -*- coding: utf-8 -*-
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0140_write_tabs_20181106_2044'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='wfmodule',
            name='workflow',
        ),
    ]
