from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=10)

    def __str__(self):
        return self.user.username
