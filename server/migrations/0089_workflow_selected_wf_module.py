# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-01-31 22:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0088_workflow_module_library_collapsed'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflow',
            name='selected_wf_module',
            field=models.IntegerField(default=None, null=True),
        ),
    ]
