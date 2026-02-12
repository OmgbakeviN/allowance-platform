from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

class User(AbstractUser):
    class Role(models.TextChoices):
        PARENT = "PARENT", "Parent"
        STUDENT = "STUDENT", "Student"
        ADMIN = "ADMIN", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)