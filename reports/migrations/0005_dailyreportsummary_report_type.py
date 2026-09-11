from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0004_sync_model_meta_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyreportsummary',
            name='report_type',
            field=models.CharField(
                choices=[('coal', 'Coal Production'), ('fuel', 'Fuel Management')],
                db_index=True,
                default='coal',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='dailyreportsummary',
            name='shift',
            field=models.CharField(
                choices=[
                    ('Day Shift', 'Day Shift'),
                    ('Night Shift', 'Night Shift'),
                    ('All Shift', 'All Shift'),
                    ('All_Shift', 'All Shift'),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='dailyreportsummary',
            name='delivery_shift',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Day Shift', 'Day Shift'),
                    ('Night Shift', 'Night Shift'),
                    ('All Shift', 'All Shift'),
                    ('All_Shift', 'All Shift'),
                ],
                help_text="Shift saat laporan ini 'dikirim' atau saat transaksi yang memicu pembuatan laporan dicatat.",
                max_length=30,
                null=True,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='dailyreportsummary',
            unique_together={('report_date', 'shift', 'report_type')},
        ),
    ]
