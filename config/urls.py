from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "tuzlama.uz Admin Panel"
admin.site.site_title = "tuzlama.uz Admin"
admin.site.index_title = "tuzlama.uz boshqaruv paneli"

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/img/favicon.ico?v=2', permanent=False)),
    path('admin/', admin.site.urls),
    path('', include('acaunts.urls')),
    path('', include('produkt.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
