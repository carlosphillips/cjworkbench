# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-12-12 02:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0077_auto_20171124_2107'),
    ]

    operations = [
        migrations.AddField(
            model_name='module',
            name='loads_data',
            field=models.BooleanField(default=False, verbose_name='loads_data'),
        ),
    ]