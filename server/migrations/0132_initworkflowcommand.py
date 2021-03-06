# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-10-11 16:20
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0131_auto_20181011_1618'),
    ]

    operations = [
        migrations.CreateModel(
            name='InitWorkflowCommand',
            fields=[
                ('delta_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='server.Delta')),
            ],
            options={
                'abstract': False,
            },
            bases=('server.delta',),
            managers=[
                ('objects', django.db.models.manager.Manager()),
                ('base_objects', django.db.models.manager.Manager()),
            ],
        ),
    ]
