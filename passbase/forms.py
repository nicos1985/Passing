from django.forms import *
from .models import Contrasena, SeccionContra

class ContrasenaForm(ModelForm):
    
    #este def hace un loop por cada propiedad de widget para definirle los parametros de vista (class, type, placeholder, etc) a todos los campos iterables del form. Ahorra código respecto de como se realizó mas abajo en la clase meta.
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'
         
    class Meta:
        model = Contrasena
        fields = '__all__'
        exclude = ['active']
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
                    'placeholder' : 'Ingrese la contraseña'
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
            'active': RadioSelect(
                attrs={ 
                })      
        }

class ContrasenaUForm(ModelForm):
    
    """este def hace un loop por cada propiedad de widget para definirle 
    los parametros de vista (class, type, placeholder, etc) a todos 
    los campos iterables del form. Ahorra código respecto de como 
    se realizó mas abajo en la clase meta."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.visible_fields():
            form.field.widget.attrs['class']= 'form-control'
            form.field.widget.attrs['autocomplete']= 'off'

    class Meta:
        model = Contrasena
        fields = '__all__'
        exclude = ['active']
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
            'active': RadioSelect(
                attrs={              
                })     
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
            exclude = ['active']