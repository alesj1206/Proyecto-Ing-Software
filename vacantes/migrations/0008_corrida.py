from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacantes', '0007_ampliar_empresa_ubicacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='Corrida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paso', models.CharField(choices=[('ingesta', 'Ingesta'), ('decision', 'Decisión'), ('notificacion', 'Notificación')], max_length=12)),
                ('inicio', models.DateTimeField()),
                ('fin', models.DateTimeField(auto_now_add=True)),
                ('ok', models.BooleanField(default=True)),
                ('resumen', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'ordering': ['-fin'],
            },
        ),
    ]
