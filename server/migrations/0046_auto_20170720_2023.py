# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-07-20 20:23
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0045_changewfmodulenotecommand'),
    ]

    operations = [
        migrations.RenameField(
            model_name='wfmodule',
            old_name='notes',
            new_name='note',
        ),
    ]
