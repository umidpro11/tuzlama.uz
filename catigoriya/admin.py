from django.contrib import admin
from .models import Catigoriya


@admin.register(Catigoriya)
class CatigoriyaAdmin(admin.ModelAdmin):
    fields = ('nom',)
    list_display = ('id', 'nom')
    search_fields = ('nom',)
