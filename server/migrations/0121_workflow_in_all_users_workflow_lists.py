# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-08-28 18:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0120_module_has_zen_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflow',
            name='in_all_users_workflow_lists',
            field=models.BooleanField(default=False),
        ),
    ]