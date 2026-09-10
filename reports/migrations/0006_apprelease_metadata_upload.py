from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0005_apprelease'),
    ]

    operations = [
        migrations.AddField(
            model_name='apprelease',
            name='metadata_file',
            field=models.FileField(
                default='',
                upload_to='apk/metadata/',
                help_text='Gradle output-metadata.json; version and build_number are read from it',
            ),
            preserve_default=False,
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='apprelease',
                    name='sha256',
                    field=models.CharField(blank=True, default='', help_text='Hex SHA-256 of apk_file, computed on save', max_length=64),
                ),
                migrations.AddField(
                    model_name='apprelease',
                    name='size',
                    field=models.PositiveBigIntegerField(default=0, help_text='apk_file size in bytes, computed on save'),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE reports_apprelease ADD COLUMN IF NOT EXISTS sha256 varchar(64) NOT NULL DEFAULT '';",
                    reverse_sql="ALTER TABLE reports_apprelease DROP COLUMN IF EXISTS sha256;",
                ),
                migrations.RunSQL(
                    "ALTER TABLE reports_apprelease ADD COLUMN IF NOT EXISTS size bigint NOT NULL DEFAULT 0;",
                    reverse_sql="ALTER TABLE reports_apprelease DROP COLUMN IF EXISTS size;",
                ),
            ],
        ),
        migrations.AlterField(
            model_name='apprelease',
            name='version',
            field=models.CharField(blank=True, default='', help_text='Auto-filled from output-metadata.json versionName', max_length=20),
        ),
        migrations.AlterField(
            model_name='apprelease',
            name='build_number',
            field=models.PositiveIntegerField(blank=True, help_text='Auto-filled from output-metadata.json versionCode', null=True),
        ),
    ]
