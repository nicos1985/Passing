from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    avatar = models.ImageField(blank=True, null=True, upload_to='static/')
    position = models.CharField(max_length=80,null=True)
    email = models.EmailField(unique=True)



     