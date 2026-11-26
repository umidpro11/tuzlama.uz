from django.db import models


class Catigoriya(models.Model):
    nom = models.CharField(max_length=150, unique=True, verbose_name='Nom')

    class Meta:
        verbose_name = 'Catigoriya'
        verbose_name_plural = 'Catigoriyalar'
        ordering = ['nom']

    def __str__(self):
        return self.nom
