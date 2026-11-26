from django.contrib import admin
from django.utils.html import format_html
from .models import Buyurtma, BuyurtmaItem, Murojaat, Produkt, ProduktIzoh, SavatchaItem, Sevimli


@admin.register(Produkt)
class ProduktAdmin(admin.ModelAdmin):
    fields = ('nom', 'catigoriya', 'narx', 'about', 'rasm')
    list_display = ('nom', 'catigoriya', 'narx', 'rasm_preview')
    list_filter = ('catigoriya',)
    search_fields = ('nom', 'about')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'catigoriya':
            kwargs['empty_label'] = 'Catigoriyalar tanlang'
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Rasim')
    def rasm_preview(self, obj):
        if obj.rasm:
            return format_html(
                '<img src="{}" style="width:48px;height:48px;object-fit:cover;border-radius:8px;" />',
                obj.rasm.url,
            )
        return '—'


class BuyurtmaItemInline(admin.TabularInline):
    model = BuyurtmaItem
    extra = 0
    readonly_fields = ('produkt', 'product_name', 'unit_price', 'quantity')


@admin.register(Buyurtma)
class BuyurtmaAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'phone', 'items_total', 'delivery_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer_name', 'phone', 'address_text')
    inlines = [BuyurtmaItemInline]


@admin.register(SavatchaItem)
class SavatchaItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'produkt', 'quantity', 'updated_at')
    search_fields = ('user__username', 'produkt__nom')


@admin.register(Sevimli)
class SevimliAdmin(admin.ModelAdmin):
    list_display = ('user', 'produkt', 'created_at')
    search_fields = ('user__username', 'produkt__nom')


@admin.register(ProduktIzoh)
class ProduktIzohAdmin(admin.ModelAdmin):
    list_display = ('produkt', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('produkt__nom', 'user__username', 'comment')


@admin.register(Murojaat)
class MurojaatAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'phone', 'created_at')
    search_fields = ('name', 'phone', 'message')
