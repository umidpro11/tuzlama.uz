from django.conf import settings
from .models import Buyurtma


def site_context(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'is_site_admin': False,
            'orders_badge_count': 0,
            'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
        }

    is_site_admin = user.username.lower() == 'tuzlama.uz'
    if is_site_admin:
        badge_count = Buyurtma.objects.filter(status='new').count()
        store_lat = getattr(settings, 'STORE_LATITUDE', 41.3204)
        store_lng = getattr(settings, 'STORE_LONGITUDE', 69.1905)
        store_address = getattr(settings, 'STORE_ADDRESS', "Toshkent shahar, Uchtepa tumani, 5-pr Quvnoq, 30-uy")
        store_gmaps_url = f"https://www.google.com/maps?q={store_lat},{store_lng}"
    else:
        badge_count = Buyurtma.objects.filter(user=user).exclude(status__in=['completed', 'cancelled']).count()
        store_address = ''
        store_gmaps_url = ''

    return {
        'is_site_admin': is_site_admin,
        'orders_badge_count': badge_count,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
        'admin_store_address': store_address,
        'admin_store_gmaps_url': store_gmaps_url,
    }
