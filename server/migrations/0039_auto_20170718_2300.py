# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-07-18 23:00
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0038_auto_20170714_2226'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='delta',
            name='revision',
        ),
        migrations.RemoveField(
            model_name='workflow',
            name='revision',
        ),
        migrations.RemoveField(
            model_name='workflow',
            name='revision_date',
        ),
        migrations.AddField(
            model_name='delta',
            name='next_delta',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='server.Delta'),
        ),
        migrations.AddField(
            model_name='delta',
            name='prev_delta',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='server.Delta'),
        ),
        migrations.AddField(
            model_name='workflow',
            name='last_delta',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='server.Delta'),
        ),
        migrations.AlterField(
            model_name='changedataversioncommand',
            name='old_version',
            field=models.TextField(null=True, verbose_name='old_version'),
        ),
    ]
