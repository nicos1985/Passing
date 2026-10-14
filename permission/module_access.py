"""Accesos por módulo y acción para roles de cada tenant."""

MODULE_ACTIONS = ('read', 'create', 'edit', 'delete')
ACTION_LABELS = {'read': 'Lectura', 'create': 'Crear', 'edit': 'Editar', 'delete': 'Eliminar'}
MODULE_LABELS = (
    ('resources', 'Recursos'),
    ('risks', 'Riesgos'),
    ('threat_intel', 'Inteligencia de amenazas'),
    ('support', 'Central de soporte'),
    ('monitoring', 'Monitorización'),
)

_RISK_MODELS = ('threat', 'vulnerability', 'riskevaluation', 'treatment')
_RESOURCE_MODELS = {
    'read': ('informationassets', 'vendor', 'project', 'clientcompany', 'assetaction', 'checklisttemplate', 'vendorevaluation', 'vendorchecklist'),
    'create': ('informationassets', 'vendor', 'project', 'clientcompany', 'assetaction', 'checklisttemplate', 'vendorevaluation', 'vendorchecklist'),
    'edit': ('informationassets', 'vendor', 'project', 'clientcompany', 'checklisttemplate', 'vendorevaluation', 'vendorchecklist'),
    'delete': ('informationassets', 'vendor', 'project', 'clientcompany'),
}
_INTEL_READ = ('run', 'runitem', 'intelitem', 'aianalysis', 'report', 'review')
_INTEL_CREATE = ('report', 'review', 'techtag', 'intelthreatlink')
_INTEL_EDIT = ('run', 'intelitem', 'aianalysis', 'report', 'review', 'source', 'techtag')


def _model_permissions(app, models, action):
    return tuple(f'{app}.{action}_{model}' for model in models)


MODULE_ACCESS = {}
for module, label in MODULE_LABELS:
    for action in MODULE_ACTIONS:
        key = f'{module}_{action}'
        if module == 'resources':
            codes = _model_permissions('resources', _RESOURCE_MODELS[action], {
                'read': 'view', 'create': 'add', 'edit': 'change', 'delete': 'delete',
            }[action])
        elif module == 'risks':
            codes = _model_permissions('resources', _RISK_MODELS, {
                'read': 'view', 'create': 'add', 'edit': 'change', 'delete': 'delete',
            }[action])
        elif module == 'threat_intel':
            models = {
                'read': _INTEL_READ,
                'create': _INTEL_CREATE,
                'edit': _INTEL_EDIT,
                'delete': (),
            }[action]
            codes = _model_permissions('threat_intel', models, {
                'read': 'view', 'create': 'add', 'edit': 'change', 'delete': 'delete',
            }[action])
            if action in ('create', 'edit'):
                codes += ('threat_intel.view_source', 'threat_intel.view_techtag')
        elif module == 'support':
            codes = (f'supporthub.{"view_support_inbox" if action == "read" else action + "_support"}',)
        else:
            codes = (f'monitoring.{action}_monitoring',)
        if codes:
            MODULE_ACCESS[key] = (f'{label} · {ACTION_LABELS[action]}', codes)

# Los roles anteriores conservan su acceso hasta que se migren a la matriz.
LEGACY_ACCESS = {
    'support_inbox': MODULE_ACCESS['support_read'][1],
    'monitoring_manage': tuple(
        code for action in MODULE_ACTIONS for code in MODULE_ACCESS[f'monitoring_{action}'][1]
    ) + ('monitoring.manage_monitoring',),
}

MODULE_PERMISSION_CODES = {}
for key, (_, codes) in MODULE_ACCESS.items():
    for code in codes:
        MODULE_PERMISSION_CODES.setdefault(code, set()).add(key)
for key, codes in LEGACY_ACCESS.items():
    for code in codes:
        MODULE_PERMISSION_CODES.setdefault(code, set()).add(key)


def module_rows(form):
    """Organiza las casillas del formulario en filas de cuatro acciones."""
    options = iter(form['module_permissions'])
    return [
        {'name': label, 'options': [
            (ACTION_LABELS[action], next(options) if f'{module}_{action}' in MODULE_ACCESS else None)
            for action in MODULE_ACTIONS
        ]}
        for module, label in MODULE_LABELS
    ]
