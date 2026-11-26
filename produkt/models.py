import math
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from catigoriya.models import Catigoriya


def format_uzs(value):
    """Format decimal/int price cleanly with spaces."""
    val = Decimal(str(value or 0))
    if val == val.to_integral_value():
        return f"{int(val):,}".replace(",", " ")
    return f"{val:,.2f}".replace(",", " ")


def calculate_yandex_estimate(lat, lng, address_text=''):
    """
    Calculate road distance from Uchtepa (5-pr Quvnoq, 30-uy) and delivery price:
    - Uchtepa tumani: 50,000 UZS
    - Other districts: starts at +10,000 UZS above 50,000 (60,000, 70,000, 80,000...)
    """
    store_lat = float(getattr(settings, 'STORE_LATITUDE', 41.3204))
    store_lng = float(getattr(settings, 'STORE_LONGITUDE', 69.1905))

    r_earth = 6371.0
    lat1, lon1 = math.radians(store_lat), math.radians(store_lng)
    lat2, lon2 = math.radians(float(lat)), math.radians(float(lng))
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    straight_km = 2 * r_earth * math.asin(math.sqrt(a))
    road_km = round(max(0.5, straight_km * 1.25), 2)

    addr_lower = (address_text or '').lower()
    in_uchtepa = ('uchtepa' in addr_lower) or ('учтепа' in addr_lower) or (
        straight_km <= 3.5 and not any(
            d in addr_lower for d in (
                'chilonzor', 'чиланзар', 'shayxontohur', 'шайхантахур',
                'olmazor', 'алмазар', 'yunusobod', 'юнусабад',
                'yakkasaroy', 'яккасарай', 'mirobod', 'мирабад',
                'mirzo ulug', 'мирзо-улуг', 'sergeli', 'сергели',
                'yashnobod', 'яшнабад', 'bektemir', 'бектемир',
                'yangihayot', 'янгихаёт',
            )
        )
    )

    if in_uchtepa:
        price = 50000
    else:
        extra_steps = max(1, math.ceil(max(0.1, road_km - 4.0) / 5.0))
        price = 50000 + extra_steps * 10000

    return Decimal(str(road_km)), Decimal(str(price))


class Produkt(models.Model):
    nom = models.CharField(max_length=200, verbose_name='Nom')
    catigoriya = models.ForeignKey(
        Catigoriya,
        on_delete=models.CASCADE,
        related_name='produktlar',
        verbose_name='Catigoriyalar',
    )
    narx = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Narx')
    about = models.TextField(verbose_name='About')
    rasm = models.ImageField(upload_to='products/', verbose_name='Rasim')

    class Meta:
        verbose_name = 'Produkt'
        verbose_name_plural = 'Produktlar'
        ordering = ['-id']

    def __str__(self):
        return self.nom

    @property
    def formatted_narx(self):
        return format_uzs(self.narx)


class SavatchaItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savatcha_items', verbose_name='Foydalanuvchi')
    produkt = models.ForeignKey(Produkt, on_delete=models.CASCADE, related_name='savatcha_entries', verbose_name='Mahsulot')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Soni')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'produkt')
        verbose_name = 'Savatcha mahsuloti'
        verbose_name_plural = 'Savatcha'

    def __str__(self):
        return f"{self.user.username}: {self.produkt.nom} x {self.quantity}"


class Sevimli(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sevimlilar', verbose_name='Foydalanuvchi')
    produkt = models.ForeignKey(Produkt, on_delete=models.CASCADE, related_name='sevimli_entries', verbose_name='Mahsulot')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'produkt')
        verbose_name = 'Sevimli mahsulot'
        verbose_name_plural = 'Sevimlilar'

    def __str__(self):
        return f"{self.user.username} ❤️ {self.produkt.nom}"


class ProduktIzoh(models.Model):
    produkt = models.ForeignKey(Produkt, on_delete=models.CASCADE, related_name='izohlar', verbose_name='Mahsulot')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='produkt_izohlari', verbose_name='Foydalanuvchi')
    rating = models.PositiveSmallIntegerField(default=5, verbose_name='Baho (1-5)')
    comment = models.TextField(verbose_name='Izoh')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Sana')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mahsulot izohi'
        verbose_name_plural = 'Mahsulot izohlari'

    def __str__(self):
        return f"{self.produkt.nom} — {self.user.username} ({self.rating}★)"


class Murojaat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='murojaatlar', verbose_name='Foydalanuvchi')
    name = models.CharField(max_length=150, verbose_name='Ism')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon')
    message = models.TextField(verbose_name='Xabar / Taklif')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yuborilgan vaqt')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Murojaat / Taklif'
        verbose_name_plural = 'Murojaatlar'

    def __str__(self):
        return f"{self.name}: {self.message[:40]}"


class Buyurtma(models.Model):
    STATUS_CHOICES = [
        ('new', 'Yangi zakas'),
        ('priced', 'Dastafka narxi belgilandi'),
        ('delivering', "Yo'lda"),
        ('completed', 'Yetkazildi'),
        ('cancelled', 'Bekor qilindi'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='buyurtmalar',
        verbose_name='Foydalanuvchi',
    )
    customer_name = models.CharField(max_length=150, verbose_name='Mijoz ismi')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon raqam')
    address_text = models.CharField(max_length=400, blank=True, verbose_name='Manzil')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='Longitude')
    note = models.TextField(blank=True, verbose_name='Izoh')
    items_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Mahsulotlar summasi')
    distance_km = models.DecimalField(max_digits=7, decimal_places=2, default=0, verbose_name='Masofa (km)')
    yandex_estimated_delivery = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Taxminiy Yandex Go narxi',
    )
    delivery_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Dastafka narxi',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name='Holati',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan vaqt')

    class Meta:
        verbose_name = 'Buyurtma'
        verbose_name_plural = 'Buyurtmalar'
        ordering = ['-created_at']

    def __str__(self):
        return f"Buyurtma #{self.id} — {self.customer_name}"

    @property
    def formatted_items_total(self):
        return format_uzs(self.items_total)

    @property
    def formatted_yandex_estimate(self):
        return format_uzs(self.yandex_estimated_delivery)

    @property
    def formatted_delivery_price(self):
        if self.delivery_price is None:
            return None
        return format_uzs(self.delivery_price)

    @property
    def grand_total(self):
        delivery = self.delivery_price if self.delivery_price is not None else Decimal('0')
        return Decimal(str(self.items_total)) + Decimal(str(delivery))

    @property
    def formatted_grand_total(self):
        return format_uzs(self.grand_total)

    @property
    def google_maps_url(self):
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"

    @property
    def google_maps_route_url(self):
        store_lat = getattr(settings, 'STORE_LATITUDE', 41.3204)
        store_lng = getattr(settings, 'STORE_LONGITUDE', 69.1905)
        return f"https://www.google.com/maps/dir/?api=1&origin={store_lat},{store_lng}&destination={self.latitude},{self.longitude}"

    @property
    def yandex_maps_route_url(self):
        store_lat = getattr(settings, 'STORE_LATITUDE', 41.3204)
        store_lng = getattr(settings, 'STORE_LONGITUDE', 69.1905)
        return f"https://yandex.uz/maps/?rtext={store_lat},{store_lng}~{self.latitude},{self.longitude}&rtt=auto"


class BuyurtmaItem(models.Model):
    buyurtma = models.ForeignKey(Buyurtma, on_delete=models.CASCADE, related_name='items')
    produkt = models.ForeignKey(Produkt, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200, verbose_name='Mahsulot nomi')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Narx')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Soni')

    class Meta:
        verbose_name = 'Buyurtma mahsuloti'
        verbose_name_plural = 'Buyurtma mahsulotlari'

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def line_total(self):
        return Decimal(str(self.unit_price)) * self.quantity

    @property
    def formatted_unit_price(self):
        return format_uzs(self.unit_price)

    @property
    def formatted_line_total(self):
        return format_uzs(self.line_total)
