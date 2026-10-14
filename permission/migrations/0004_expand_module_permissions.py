from django.db import migrations


def expand_legacy_roles(apps, schema_editor):
    Role = apps.get_model('permission', 'PermissionRoles')
    replacements = {
        'support_inbox': ['support_read'],
        'monitoring_manage': [
            'monitoring_read', 'monitoring_create', 'monitoring_edit', 'monitoring_delete',
        ],
    }
    for role in Role.objects.all().iterator():
        original = role.module_permissions or []
        expanded = []
        for key in original:
            expanded.extend(replacements.get(key, [key]))
        expanded = list(dict.fromkeys(expanded))
        if expanded != original:
            role.module_permissions = expanded
            role.save(update_fields=['module_permissions'])


class Migration(migrations.Migration):
    dependencies = [('permission', '0003_permissionroles_module_permissions')]
    operations = [migrations.RunPython(expand_legacy_roles, migrations.RunPython.noop)]
