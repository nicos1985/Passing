from django.shortcuts import render
from django.core.mail import send_mail


def home(request):
    return render(request, 'home.html')

def test_send_email(request):
    subject = 'Prueba de envío de correo'
    message = 'Este es un correo electrónico de prueba'
    from_email = 'nicolas.ferratto@previ.com.ar'
    recipient_list = ['nicolasferratto@hotmail.com']

    send_mail(subject, message, from_email, recipient_list, fail_silently=False)

    print('Correo electrónico enviado')
    return render(request, 'test_send_email.html')