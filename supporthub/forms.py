import ipaddress
import re
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django import forms
from django.core.exceptions import ValidationError

from accounts.models import CustomUser
from .models import BitrixPortal, DutyShift, SupportChat, TelegramRecipient


ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')
WEBHOOK_PATH = re.compile(r'^/rest/([1-9][0-9]*)/([A-Za-z0-9_-]{8,})/?$')
GROUP_DIALOG = re.compile(r'^chat[1-9][0-9]*$')
BOT_TOKEN = re.compile(r'^[0-9]+:[A-Za-z0-9_-]{20,}$')


def portal_origin(value):
    value = value.strip().rstrip('/')
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError('La URL del portal no es válida.') from exc
    host = parsed.hostname or ''
    if (parsed.scheme != 'https' or not host or '.' not in host or port is not None
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or host.endswith('.localhost') or host.endswith('.local')):
        raise ValidationError('Usá la URL HTTPS del portal, sin ruta ni parámetros.')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationError('Usá el dominio público del portal, no una dirección IP.')
    return value


class PortalForm(forms.ModelForm):
    webhook_url = forms.CharField(label='Webhook de chat', widget=forms.PasswordInput(render_value=False),
                                  help_text='Webhook entrante de Bitrix24 del usuario que integra los grupos, con permiso im. Se cifra y no vuelve a mostrarse.')

    class Meta:
        model = BitrixPortal
        fields = ['name', 'base_url', 'enabled']
        labels = {'name': 'Portal', 'base_url': 'URL del Bitrix24', 'enabled': 'Activo'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['webhook_url'].required = not bool(self.instance.pk and self.instance.webhook_encrypted)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'

    def clean_base_url(self):
        return portal_origin(self.cleaned_data['base_url'])

    def clean(self):
        data = super().clean()
        webhook = data.get('webhook_url', '').strip()
        origin = data.get('base_url')
        if webhook and origin:
            try:
                parsed = urlsplit(webhook)
                port = parsed.port
            except ValueError:
                self.add_error('webhook_url', 'La URL del webhook no es válida.')
                return data
            if (parsed.scheme != 'https' or parsed.netloc != urlsplit(origin).netloc
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or port is not None or not WEBHOOK_PATH.fullmatch(parsed.path)):
                self.add_error('webhook_url', 'El webhook debe pertenecer al portal y tener formato /rest/usuario/código/.')
        if self.instance.pk and origin and origin != self.instance.base_url and not webhook:
            self.add_error('webhook_url', 'Al cambiar de portal también debés cargar el nuevo webhook.')
        return data

    def save(self, commit=True):
        portal = super().save(commit=False)
        webhook = self.cleaned_data.get('webhook_url', '').strip()
        if webhook:
            portal.set_webhook(webhook)
        if commit:
            portal.save()
        return portal


class ChatForm(forms.ModelForm):
    class Meta:
        model = SupportChat
        fields = ['portal', 'label', 'dialog_id', 'link_url', 'ignored_sender_ids', 'enabled']
        labels = {'portal': 'Portal', 'label': 'Nombre visible', 'dialog_id': 'ID del grupo',
                  'link_url': 'Enlace al chat en Bitrix24', 'ignored_sender_ids': 'IDs de personas de soporte a ignorar', 'enabled': 'Activo'}
        help_texts = {'dialog_id': 'Por ejemplo chat123. Solo se reciben eventos de grupos agregados aquí.',
                      'link_url': 'Se genera un enlace directo al grupo. Podés dejarlo vacío o usar otro enlace del mismo portal.',
                      'ignored_sender_ids': 'Seleccioná personas en la consulta de Bitrix o ingresá hasta 30 IDs separados por comas. Sus mensajes no generan avisos.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'

    def clean_dialog_id(self):
        value = self.cleaned_data['dialog_id'].strip()
        if not GROUP_DIALOG.fullmatch(value):
            raise ValidationError('Usá el ID de un grupo, por ejemplo chat123.')
        return value

    def clean_ignored_sender_ids(self):
        value = self.cleaned_data['ignored_sender_ids'].strip()
        values = [part.strip() for part in value.split(',') if part.strip()]
        if len(values) > 30 or any(not part.isdigit() for part in values):
            raise ValidationError('Ingresá hasta 30 IDs numéricos separados por comas.')
        return ','.join(values)

    def clean(self):
        data = super().clean()
        portal = data.get('portal')
        link = data.get('link_url')
        if portal and link:
            try:
                parsed = urlsplit(link)
                port = parsed.port
            except ValueError:
                self.add_error('link_url', 'La URL del chat no es válida.')
                return data
            if (parsed.scheme != 'https' or parsed.netloc != urlsplit(portal.base_url).netloc
                    or port is not None or parsed.username or parsed.password or parsed.fragment
                    or '/rest/' in parsed.path or '/rest/' in parsed.query):
                self.add_error('link_url', 'El enlace debe apuntar al mismo portal y no contener un webhook.')
        return data


class RecipientForm(forms.ModelForm):
    class Meta:
        model = TelegramRecipient
        fields = ['user', 'chat_id', 'active', 'fallback', 'notify_support', 'notify_monitoring', 'notify_password_requests', 'notify_risks']
        labels = {'user': 'Persona de Passing', 'chat_id': 'ID del chat privado de Telegram',
                  'active': 'Recibe avisos', 'fallback': 'Avisar si no hay turno activo',
                  'notify_support': 'Soporte', 'notify_monitoring': 'Incidentes de monitoreo',
                  'notify_password_requests': 'Solicitudes de acceso a contraseñas', 'notify_risks': 'Asistente de riesgos'}
        help_texts = {'chat_id': 'Solo el número del chat privado, no el token de BotFather. La persona debe enviar /start al bot; podés buscar su ID en Configurar soporte.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = CustomUser.for_current_tenant().filter(is_active=True)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'

    def clean_chat_id(self):
        value = self.cleaned_data['chat_id']
        if value <= 0:
            raise ValidationError('Usá el ID positivo de un chat privado.')
        return value

    def clean(self):
        data = super().clean()
        user = data.get('user')
        if user and data.get('notify_password_requests') and not user.is_superuser:
            self.add_error('notify_password_requests', 'Solo un superusuario puede recibir pedidos de contraseñas.')
        if user and data.get('notify_monitoring') and not (
            user.is_superuser or user.has_perm('monitoring.manage_monitoring') or user.has_perm('monitoring.read_monitoring')
        ):
            self.add_error('notify_monitoring', 'La persona necesita permiso para ver monitorización.')
        if user and data.get('notify_risks') and not (
            user.is_staff or user.is_superuser or user.has_perm('resources.view_riskevaluation')
        ):
            self.add_error('notify_risks', 'La persona necesita permiso para ver riesgos.')
        return data


class BotTokenForm(forms.Form):
    token = forms.CharField(
        label='Token de BotFather', max_length=256,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}, render_value=False),
        help_text='Se cifra al guardar y no vuelve a mostrarse. El campo ID del destinatario lleva solo el número de su chat privado.',
    )

    def clean_token(self):
        value = self.cleaned_data['token'].strip()
        if not BOT_TOKEN.fullmatch(value):
            raise ValidationError('El token debe tener el formato numérico:código que entrega BotFather.')
        return value


class ShiftForm(forms.ModelForm):
    class Meta:
        model = DutyShift
        fields = ['starts_at', 'ends_at', 'primary', 'backup', 'note']
        labels = {'starts_at': 'Inicio (Argentina)', 'ends_at': 'Fin (Argentina)',
                  'primary': 'Guardia principal', 'backup': 'Suplente', 'note': 'Nota'}
        widgets = {'starts_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
                   'ends_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = TelegramRecipient.objects.filter(active=True, notify_support=True, user__is_active=True).select_related('user')
        self.fields['primary'].queryset = active
        self.fields['backup'].queryset = active
        for name in ('starts_at', 'ends_at'):
            if self.instance.pk:
                self.initial[name] = getattr(self.instance, name).astimezone(ARGENTINA).strftime('%Y-%m-%dT%H:%M')
            self.fields[name].input_formats = ['%Y-%m-%dT%H:%M']
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        data = super().clean()
        for name in ('starts_at', 'ends_at'):
            raw = self.data.get(name, '')
            if name in data and raw:
                try:
                    data[name] = datetime.strptime(raw, '%Y-%m-%dT%H:%M').replace(tzinfo=ARGENTINA)
                except ValueError:
                    self.add_error(name, 'Ingresá fecha y hora válidas.')
        if data.get('starts_at') and data.get('ends_at') and data['ends_at'] <= data['starts_at']:
            self.add_error('ends_at', 'El fin debe ser posterior al inicio.')
        if data.get('primary') and data.get('backup') and data['primary'] == data['backup']:
            self.add_error('backup', 'Elegí otra persona como suplente.')
        if data.get('starts_at') and data.get('ends_at'):
            overlap = DutyShift.objects.filter(starts_at__lt=data['ends_at'], ends_at__gt=data['starts_at'])
            if self.instance.pk:
                overlap = overlap.exclude(pk=self.instance.pk)
            if overlap.exists():
                self.add_error('starts_at', 'Este turno se superpone con otro ya programado.')
        return data


class BitrixDirectoryForm(forms.Form):
    kind = forms.ChoiceField(choices=[('groups', 'Grupos'), ('people', 'Personas')])
    query = forms.CharField(required=False, min_length=2, max_length=100)
    dialog = forms.RegexField(GROUP_DIALOG, required=False, max_length=50)
    offset = forms.IntegerField(required=False, min_value=0, max_value=10000)
    cursor = forms.DateTimeField(required=False)

    def clean(self):
        data = super().clean()
        if data.get('kind') == 'people' and not data.get('query') and not data.get('dialog'):
            raise ValidationError('Elegí un grupo o escribí al menos dos letras para buscar personas.')
        if data.get('kind') == 'groups' and not data.get('query') and data.get('offset'):
            raise ValidationError('Para los grupos recientes usá la fecha de la siguiente página.')
        return data
