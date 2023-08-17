from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    permiso_contra = models.CharField(max_length=2000,null=True)



     