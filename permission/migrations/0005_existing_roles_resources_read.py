from django.db import migrations


def preserve_existing_resource_read_access(apps, schema_editor):
    Role = apps.get_model('permission', 'PermissionRoles')
    for role in Role.objects.all().iterator():
        selected = list(role.module_permissions or [])
        if 'resources_read' not in selected:
            selected.append('resources_read')
            role.module_permissions = selected
            role.save(update_fields=['module_permissions'])


class Migration(migrations.Migration):
    dependencies = [('permission', '0004_expand_module_permissions')]
    operations = [migrations.RunPython(preserve_existing_resource_read_access, migrations.RunPython.noop)]
