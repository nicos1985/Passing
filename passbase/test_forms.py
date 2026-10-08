"""Pruebas unitarias básicas para formularios de `passbase`."""

from django_tenants.test.cases import TenantTestCase
from passbase.forms import ContrasenaForm, ContrasenaUForm, SectionForm
from passbase.models import SeccionContra, Contrasena
from login.models import CustomUser


class SectionFormTest(TenantTestCase):
    def test_section_form_valid(self):
        form_data = {'nombre_seccion': 'Social Media', 'active': True}
        form = SectionForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_section_form_invalid(self):
        form_data = {'nombre_seccion': ''}
        form = SectionForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_section_form_widget_attrs(self):
        form = SectionForm()
        self.assertEqual(form.fields['nombre_seccion'].widget.attrs['class'], 'form-control')
        self.assertEqual(form.fields['nombre_seccion'].widget.attrs['autocomplete'], 'off')


class ContrasenaFormTest(TenantTestCase):
    def setUp(self):
        self.seccion = SeccionContra.objects.create(nombre_seccion='Work')

    def test_contrasena_form_valid(self):
        form_data = {
            'nombre_contra': 'Gmail',
            'seccion': self.seccion.id,
            'link': 'https://gmail.com',
            'usuario': 'user@example.com',
            'contraseña': 'password123',
            'actualizacion': 30,
            'info': 'My work email',
            'active': True,
            'is_personal': False
        }
        form = ContrasenaForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_contrasena_form_widget_attrs(self):
        form = ContrasenaForm()
        self.assertEqual(form.fields['nombre_contra'].widget.attrs['class'], 'form-control')
        self.assertEqual(form.fields['contraseña'].widget.input_type, 'password')


class ContrasenaUFormTest(TenantTestCase):
    def setUp(self):
        self.seccion = SeccionContra.objects.create(nombre_seccion='Work')
        self.user = CustomUser.objects.create(username='testuser', client=self.tenant)
        self.contra = Contrasena.objects.create(
            nombre_contra='Gmail',
            seccion=self.seccion,
            link='https://gmail.com',
            usuario='encrypted_user',
            contraseña='encrypted_pass',
            owner=self.user
        )

    def test_contrasena_uform_initial(self):
        form = ContrasenaUForm(instance=self.contra, decrypted_user='real_user', decrypted_password='real_password')
        self.assertEqual(form.fields['usuario'].initial, 'real_user')
        self.assertEqual(form.fields['contraseña'].initial, 'real_password')

    def test_contrasena_uform_widget_attrs(self):
        form = ContrasenaUForm(instance=self.contra)
        self.assertEqual(form.fields['is_personal'].widget.attrs['class'], 'form-check-input')
        self.assertEqual(form.fields['nombre_contra'].widget.attrs['class'], 'form-control')
