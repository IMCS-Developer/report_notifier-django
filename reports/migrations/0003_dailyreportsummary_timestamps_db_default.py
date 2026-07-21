from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('reports', '0002_mastermanpower_created_at_db_default'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;",
                "UPDATE reports_dailyreportsummary SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;",
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN created_at SET NOT NULL;",
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;",
                "UPDATE reports_dailyreportsummary SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;",
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN updated_at SET NOT NULL;",
            ],
            reverse_sql=[
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN created_at DROP NOT NULL;",
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN created_at DROP DEFAULT;",
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN updated_at DROP NOT NULL;",
                "ALTER TABLE reports_dailyreportsummary ALTER COLUMN updated_at DROP DEFAULT;",
            ],
        ),
    ]
