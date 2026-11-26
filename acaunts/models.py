from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    ism = models.CharField(max_length=150, blank=True, verbose_name='Ism')
    familiya = models.CharField(max_length=150, blank=True, verbose_name='Familiya')
    telefon = models.CharField(max_length=30, blank=True, verbose_name='Telefon raqam')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='Avatar')

    class Meta:
        verbose_name = 'Profil'
        verbose_name_plural = 'Profillar'

    def __str__(self):
        return self.ism or self.user.username

    @property
    def display_name(self):
        return self.ism or self.user.first_name or self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults={
                'ism': instance.first_name or instance.username,
                'familiya': instance.last_name or '',
            },
        )
