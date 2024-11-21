from django.shortcuts import render
from django.contrib import messages
from client.forms import ClientRegisterForm
from django.shortcuts import get_object_or_404, render, redirect

# Create your views here.


def client_register(request):
    if request.method == 'POST':
        form = ClientRegisterForm(request.POST)
        if form.is_valid():
            form.save()  # Guarda el cliente en la base de datos
            client_name = form.cleaned_data['client_name']
            messages.success(request, f'El cliente "{client_name}" ha sido creado exitosamente.')
            return redirect('listpass')  # Cambia esto a la vista correspondiente si no es `listpass`
        else:
            messages.warning(request, 'La creación del cliente ha tenido un problema.')
    else:
        form = ClientRegisterForm()

    context = {
        'form': form,
        'title': 'Registrar Cliente',
        'Action': 'create',
    }

    return render(request, 'client_register.html', context)