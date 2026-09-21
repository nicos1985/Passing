from django.forms import CheckboxInput, FileInput, ModelForm, PasswordInput, RadioSelect, Select, TextInput, Textarea  
from .models import Contrasena, SeccionContra
from passing.uploads import validate_attachment
from .crypto import encrypt_data

class CredentialInputMixin:
    def save(self, commit=True):
        # User input is always plaintext, even if it resembles a stored Fernet token.
        # Only trusted model reloads may preserve existing ciphertext.
        self.instance.usuario = encrypt_data(self.cleaned_data['usuario'])
        self.instance.contraseña = encrypt_data(self.cleaned_data['contraseña'])
        return super().save(commit=commit)


class ContrasenaForm(CredentialInputMixin, ModelForm):
    def clean_file(self):
        return validate_attachment(self.cleaned_data.get('file'))
    
    #este def hace un loop por cada propiedad de widget para definirle los parametros de vista (class, type, placeholder, etc) a todos los campos iterables del form. Ahorra código respecto de como se realizó mas abajo en la clase meta.
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'
         
    class Meta:
        model = Contrasena
        fields = ['nombre_contra', 'seccion', 'link', 'usuario', 'contraseña',
                  'actualizacion', 'info', 'file', 'is_personal']
        labels ={
            'nombre_contra' : 'Nombre',
            'active': 'Activo',
        }
        #widgets se utiliza para mandarle al formulario atributos de html como clases, placeholder, autocomplete, etc. 
        #tambien se puede utilizar una libreria de django para asignar los atributos en el html que se llama django-widgets-tweks
        widgets = {
            'nombre_contra': TextInput(
                attrs={
                    'placeholder' : 'Ingresa el nombre del registro'
                }),
            'seccion': Select(
                attrs={
                    'placeholder' : 'Elija la seccion'
                }),
            'link': TextInput(
                attrs={
                    'placeholder' : 'Ingrese el link de ingreso al usuario'
                }),
            'usuario': TextInput(
                attrs={
                    'placeholder' : 'Ingrese el usuario de ingreso'
                }),
            'contraseña': PasswordInput(
                attrs={
                    'placeholder' : 'Ingrese la contraseña',
                    'type' : 'password',
                    'id' : 'password'
                }),
            'Actualizacion': TextInput(
                attrs={
                    'placeholder' : 'Ingrese la cantidad de dias para actualizar la contraseña'
                }),
            'info': Textarea(
                attrs={
                    'placeholder' : 'Ingrese informacion adicional',
                    'row':'2' 
                }),
            'file': FileInput(
                attrs={
                    'placeholder' : 'Suba un archivo',                     
                }),
            
            'active': RadioSelect(
                attrs={ 
                })      
        }

class ContrasenaUForm(CredentialInputMixin, ModelForm):
    def clean_file(self):
        return validate_attachment(self.cleaned_data.get('file'))
    
    """este def hace un loop por cada propiedad de widget para definirle 
    los parametros de vista (class, type, placeholder, etc) a todos 
    los campos iterables del form. Ahorra código respecto de como 
    se realizó mas abajo en la clase meta."""
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        decrypted_user = kwargs.pop('decrypted_user', None)
        decrypted_password = kwargs.pop('decrypted_password', None)
        super().__init__(*args, **kwargs)
        if user is None or self.instance.owner_id != user.pk:
            self.fields.pop('is_personal', None)
        
        for form in self.visible_fields():
            try:
                if form.field.widget.attrs.get('id') == 'is_personal':
                    form.field.widget.attrs['class'] = 'form-check-input'
                
                else:
                    form.field.widget.attrs['class'] = 'form-control'
                    form.field.widget.attrs['autocomplete'] = 'off'
            except Exception as e:
                pass  # Do not log form data or secrets.
                form.field.widget.attrs['class'] = 'form-control'
                form.field.widget.attrs['autocomplete'] = 'off'

        if decrypted_user:
            self.fields['usuario'].initial = decrypted_user
        if decrypted_password:
            self.fields['contraseña'].initial = decrypted_password

    

    class Meta:
        model = Contrasena
        fields = ['nombre_contra', 'seccion', 'link', 'usuario', 'contraseña',
                  'actualizacion', 'info', 'file', 'is_personal']
        labels ={
            'nombre_contra' : 'Nombre',
            'active': 'Activo',
            'is_personal' :'Contraseña Personal'
        }
        #widgets se utiliza para mandarle al formulario atributos de html como clases, placeholder, autocomplete, etc. 
        #tambien se puede utilizar una libreria de django para asignar los atributos en el html que se llama django-widgets-tweks
        widgets = {
            'nombre_contra': TextInput(
                attrs={
                    'placeholder' : 'Ingresa el nombre del registro'
                }),
            'seccion': Select(
                attrs={
                    'placeholder' : 'Elija la seccion'
                }),
            'link': TextInput(
                attrs={
                    'placeholder' : 'Ingrese el link de ingreso al usuario'
                }),
            'usuario': TextInput(
                attrs={
                    'placeholder' : 'Ingrese el usuario de ingreso',
                    'id' : 'id_usuario'
                }),
            'contraseña': TextInput(
                attrs={
                    'placeholder' : 'Ingrese la contraseña',
                    'type' : 'password',
                    'id' : 'password'
                }),
            'Actualizacion': TextInput(
                attrs={
                    'placeholder' : 'Ingrese la cantidad de dias para actualizar la contraseña'
                }),
            'info': Textarea(
                attrs={
                    'placeholder' : 'Ingrese informacion adicional',
                    'row':'2'  
                }),
            'is_personal': CheckboxInput(
                attrs={ 'id':'is_personal',
                       'class':'form-check-input'
                }),
            'active': RadioSelect(
                attrs={              
                }),
                 'hash': TextInput(
                attrs={
                    'id' : 'hash'
                }),     
        }

class SectionForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'


    class Meta:
            model = SeccionContra
            fields = '__all__'
            exclude = ['active','owner']
