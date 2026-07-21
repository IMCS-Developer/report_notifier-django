from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('reports', '0001_initial_report_models'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE reports_mastermanpower ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",
                "UPDATE reports_mastermanpower SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;",
                "ALTER TABLE reports_mastermanpower ALTER COLUMN created_at SET NOT NULL;",
            ],
            reverse_sql=[
                "ALTER TABLE reports_mastermanpower ALTER COLUMN created_at DROP NOT NULL;",
                "ALTER TABLE reports_mastermanpower ALTER COLUMN created_at DROP DEFAULT;",
            ],
        ),
    ]
