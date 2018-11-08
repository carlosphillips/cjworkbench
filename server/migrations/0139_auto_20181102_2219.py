# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0138_auto_20181031_1604'),
    ]

    operations = [
        # New Tab table
        migrations.CreateModel(
            name='Tab',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('position', models.IntegerField()),
                ('selected_wf_module_position', models.IntegerField(null=True)),
            ],
            options={
                'ordering': ['position'],
            },
        ),
        migrations.AddField(
            model_name='tab',
            name='workflow',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='server.Workflow'),
        ),
        migrations.AddField(
            model_name='wfmodule',
            name='tab',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tabs', to='server.Tab'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='workflow',
            name='selected_tab_position',
            field=models.IntegerField(default=0),
        ),
        migrations.RemoveField(
            model_name='workflow',
            name='selected_wf_module',
        ),

        # More Delta cleanups
        #
        # Assume there are no more deltas (from v0135_wipe_history)
        migrations.RemoveField(
            model_name='addmodulecommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='changedataversioncommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='changeparameterscommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='deletemodulecommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='delta',
            name='datetime',
        ),
        migrations.RemoveField(
            model_name='delta',
            name='next_delta',
        ),
        migrations.RemoveField(
            model_name='reordermodulescommand',
            name='dependent_wf_module_last_delta_ids',
        ),
        migrations.RemoveField(
            model_name='reordermodulescommand',
            name='new_order',
        ),
        migrations.RemoveField(
            model_name='reordermodulescommand',
            name='old_order',
        ),
        migrations.AddField(
            model_name='addmodulecommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='changedataversioncommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='changeparameterscommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='deletemodulecommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='delta',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reordermodulescommand',
            name='next_order',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reordermodulescommand',
            name='prev_order',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reordermodulescommand',
            name='wf_module_delta_ids',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=2), default=[], size=None),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='delta',
            name='prev_delta',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='next_delta', to='server.Delta'),
        ),
        migrations.AddField(
            model_name='reordermodulescommand',
            name='tab',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.PROTECT, to='server.Tab'),
            preserve_default=False,
        ),
    ]
