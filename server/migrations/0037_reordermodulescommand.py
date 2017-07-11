# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-07-11 00:16
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0036_auto_20170707_0125'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReorderModulesCommand',
            fields=[
                ('delta_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='server.Delta')),
                ('old_order', models.TextField()),
                ('new_order', models.TextField()),
            ],
            bases=('server.delta',),
        ),
    ]
